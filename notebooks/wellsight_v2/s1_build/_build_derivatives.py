"""Generic LAZ -> derivative-stack builder.

Reads one or more LAS/LAZ tiles, merges + (optionally) reprojects + crops to a
target bbox, classifies ground points, and writes the full WellSight
derivative stack at the chosen resolution. Single entry point that replaced
the older per-area builders (now in ``archive/wellsight/build/``).

Outputs land under ``data/derivatives/<sfx>/`` with the suffix kept in every
filename so individual files remain self-describing if pulled out:
    dem_<sfx>.tif                 ground DEM      (PDAL delaunay -> faceraster)
    dsm_<sfx>.tif                 DSM             (PDAL writers.gdal max, return 1)
    chm_<sfx>.tif                 CHM = DSM - DEM
    hillshade_<sfx>.tif           WBT hillshade   (315/45)
    slope_<sfx>.tif               WBT slope       (degrees)
    ground_density_<sfx>.tif      uint16          ground returns per cell
    intensity_ground_<sfx>.tif    float32         mean intensity of ground returns
    roughness_5_<sfx>.tif         stdev DEM 5x5
    local_relief_10_<sfx>.tif     max-min DEM in 10 m disk
    lrm_{3,5,11,25}_<sfx>.tif     local relief model at multiple kernel sizes
    tpi_{05,15,25}_<sfx>.tif      TPI at 5/15/25 m disk radii
    tpi_grad_{mag,dir}_<sfx>.tif  gradient of tpi_15
    openness_{pos,neg}_<sfx>.tif  Yokoyama 1998 openness, L = 25 cells
    tile_overview_<sfx>.png       12-panel quick-look

CLI examples:
  # Venango 9-tile (already in UTM 17N, no reprojection needed)
  python notebooks/wellsight/build/_build_derivatives.py \\
      --tiles "data/source_laz/westernpa/USGS_LPC_PA_WesternPA_2019_D20_17TPF619*.laz" \\
      --bbox 619500,4593000,624000,4597500 --suffix 9t_1m

  # Full McKean (source in Albers, reproject on the fly)
  python notebooks/wellsight/build/_build_derivatives.py \\
      --tiles "data/source_laz/mckean/USGS_LPC_PA_Northcentral_2019_B19_*.laz" \\
      --bbox 696000,4645000,706000,4655000 --suffix mkf_1m \\
      --src-crs EPSG:6350
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import laspy
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.transform import from_origin
from scipy import ndimage as ndi
from scipy.ndimage import uniform_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, make_profile, read_tif, run_pdal, write_tif, path_for


# ---------------------------------------------------------------------------
# Kernel / derivative helpers
# ---------------------------------------------------------------------------

def disk_kernel(r_cells: float) -> np.ndarray:
    r = int(round(r_cells))
    y, x = np.ogrid[-r:r+1, -r:r+1]
    return (x * x + y * y) <= r * r


def nanmean_filter(a: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    valid = np.isfinite(a).astype(np.float32)
    a0 = np.where(valid.astype(bool), a, 0).astype(np.float32)
    k = kernel.astype(np.float32)
    s = ndi.convolve(a0, k, mode="nearest")
    c = ndi.convolve(valid, k, mode="nearest")
    out = np.full_like(a, np.nan, dtype=np.float32)
    np.divide(s, c, out=out, where=c > 0)
    return out


def _nanmax_disk(a: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    big = np.where(np.isfinite(a), a, -np.inf)
    r = ndi.maximum_filter(big, footprint=kernel, mode="nearest")
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)


def _nanmin_disk(a: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    small = np.where(np.isfinite(a), a, np.inf)
    r = ndi.minimum_filter(small, footprint=kernel, mode="nearest")
    return np.where(np.isfinite(r), r, np.nan).astype(np.float32)


def openness(z: np.ndarray, *, L_cells: int, cellsize: float):
    """Yokoyama 1998 positive and negative openness, 8 directions."""
    dirs = [(-1,0),(-1,1),(0,1),(1,1),(1,0),(1,-1),(0,-1),(-1,-1)]
    valid = np.isfinite(z)
    z0 = np.where(valid, z, 0).astype(np.float32)
    phi = np.zeros_like(z, dtype=np.float32)
    psi = np.zeros_like(z, dtype=np.float32)
    for dr, dc in dirs:
        step = cellsize * np.hypot(dr, dc)
        mtu = np.full_like(z, -np.inf, dtype=np.float32)
        mtd = np.full_like(z, np.inf, dtype=np.float32)
        for k in range(1, L_cells + 1):
            zs = np.roll(z0, shift=(dr * k, dc * k), axis=(0, 1))
            vs = np.roll(valid, shift=(dr * k, dc * k), axis=(0, 1))
            if dr > 0:   vs[:dr*k, :] = False
            elif dr < 0: vs[dr*k:, :] = False
            if dc > 0:   vs[:, :dc*k] = False
            elif dc < 0: vs[:, dc*k:] = False
            ta = np.where(vs, (zs - z0) / (k * step), np.nan).astype(np.float32)
            np.fmax(mtu, ta, out=mtu, where=vs)
            np.fmin(mtd, ta, out=mtd, where=vs)
        phi += (np.pi / 2 - np.arctan(np.where(np.isfinite(mtu), mtu, 0))).astype(np.float32)
        psi += (np.pi / 2 + np.arctan(np.where(np.isfinite(mtd), mtd, 0))).astype(np.float32)
    phi = np.degrees(phi / 8).astype(np.float32)
    psi = np.degrees(psi / 8).astype(np.float32)
    phi[~valid] = np.nan; psi[~valid] = np.nan
    return phi, psi


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def resolve_tiles(spec: str) -> list[Path]:
    """Resolve a glob (relative to repo root) OR comma-separated paths."""
    if "," in spec:
        return [(Path(p.strip()) if Path(p.strip()).is_absolute() else ROOT / p.strip())
                for p in spec.split(",")]
    p = Path(spec)
    if p.is_absolute():
        return sorted(Path(p.anchor).glob(str(p.relative_to(p.anchor)).replace("\\", "/")))
    return sorted(ROOT.glob(spec))


def build(
    tiles: list[Path],
    *,
    x0: float, y0: float, x1: float, y1: float,
    res: float, sfx: str, dst_crs: str,
    src_crs: str | None = None,
    merge_path: Path | None = None,
    skip_existing: bool = True,
    out_dir: Path | None = None,
    dem_method: str = "delaunay",
    openness_only: bool = False,
) -> None:
    W = int(round((x1 - x0) / res))
    H = int(round((y1 - y0) / res))
    transform = from_origin(x0, y1, res, res)
    if out_dir is None:
        out_dir = path_for("derived") / sfx / "derived"
    out_dir.mkdir(parents=True, exist_ok=True)
    # Files inside the suffix subdir keep the full suffix in their name so they
    # remain self-describing if pulled out of the directory.
    def out(stem: str, ext: str = "tif") -> Path:
        return out_dir / f"{stem}_{sfx}.{ext}"
    print(f"\n=== {sfx} ===  grid {W}x{H} @ {res} m  CRS={dst_crs}  tiles={len(tiles)}")
    print(f"  output dir: {out_dir.relative_to(ROOT)}")

    # 0) Merge (and optionally reproject + crop) if multiple inputs or reproj needed.
    if len(tiles) == 1 and src_crs is None:
        las_path = tiles[0]
    else:
        if merge_path is None:
            merge_path = path_for("source") / "westernpa" / f"_merged_{sfx}.las"
        if merge_path.exists() and skip_existing:
            print(f"  merge: reusing existing {merge_path.name}")
        else:
            stages: list = [{"type": "readers.las", "filename": str(p)} for p in tiles]
            if src_crs:
                stages.append({"type": "filters.reprojection",
                               "in_srs": src_crs, "out_srs": dst_crs})
            stages.append({"type": "filters.crop",
                           "bounds": f"([{x0},{x1}],[{y0},{y1}])"})
            # offset:auto recomputes header offset from the data so large UTM
            # coords don't overflow int32 when the source offset is 0 (seen on
            # some 3DEP tiles, e.g. TX zone-14 northings ~3.3e6). scale 0.01 (1 cm)
            # keeps scaled values well inside int32 for any 3 km block.
            # NOTE: do NOT forward source VLRs ("forward":"all"). Some 3DEP tiles
            # (e.g. TX West Central B4) carry a malformed vendor VLR that, once
            # copied into the merged LAS, makes PDAL reject the re-read with
            # "VLR size too large -- flows into point data". We set CRS (a_srs),
            # scale, offset, and format explicitly, so forwarding is unnecessary.
            stages.append({"type": "writers.las", "filename": str(merge_path),
                           "minor_version": 4, "dataformat_id": 7, "a_srs": dst_crs,
                           "compression": "false",
                           "offset_x": "auto", "offset_y": "auto", "offset_z": "auto",
                           "scale_x": 0.01, "scale_y": 0.01, "scale_z": 0.01})
            run_pdal(stages, label=f"merge_{sfx}")
            print(f"  merged: {merge_path.stat().st_size/1e9:.2f} GB")
        las_path = merge_path

    # 1) DEM
    #   delaunay -> faceraster gives a gap-free TIN DEM but holds the whole
    #   triangulation in RAM; on dense QL1 3DEP 3x3 mosaics (~200M ground pts,
    #   multi-GB) it dies with "bad allocation". For those, dem_method="gdal"
    #   uses writers.gdal IDW, which streams points into cells (low memory) and
    #   fills small gaps via window_size.
    dem_path = out("dem")
    if not (dem_path.exists() and skip_existing):
        ground = [
            {"type": "readers.las", "filename": str(las_path)},
            {"type": "filters.range", "limits": "Classification[2:2]"},
        ]
        if dem_method == "gdal":
            stages = ground + [
                {"type": "writers.gdal", "filename": str(dem_path),
                 "output_type": "idw", "resolution": res,
                 "origin_x": x0, "origin_y": y0, "width": W, "height": H,
                 "window_size": 3, "data_type": "float32"},
            ]
        else:
            stages = ground + [
                {"type": "filters.delaunay"},
                {"type": "filters.faceraster",
                 "resolution": res, "origin_x": x0, "origin_y": y0,
                 "width": W, "height": H},
                {"type": "writers.raster", "filename": str(dem_path),
                 "data_type": "float32"},
            ]
        run_pdal(stages, label=f"dem_{sfx}")
    dem = read_tif(dem_path)
    print(f"  DEM: nan={100*np.isnan(dem).mean():.2f}%  "
          f"z={np.nanmin(dem):.1f}..{np.nanmax(dem):.1f} m")

    # openness_only: skip the full analytical stack; emit just openness pos/neg
    # (Yokoyama) from the DEM. Used for the lean Permian annotation grids.
    if openness_only:
        op_pos, op_neg = openness(dem, L_cells=int(25 / res), cellsize=res)
        write_tif(out("openness_pos"), op_pos, transform=transform, crs=dst_crs)
        write_tif(out("openness_neg"), op_neg, transform=transform, crs=dst_crs)
        print(f"  openness_only: wrote openness_pos + openness_neg for {sfx}")
        return

    # 2) DSM + CHM
    dsm_path = out("dsm")
    if not (dsm_path.exists() and skip_existing):
        run_pdal([
            {"type": "readers.las", "filename": str(las_path)},
            {"type": "filters.range", "limits": "ReturnNumber[1:1]"},
            {"type": "writers.gdal", "filename": str(dsm_path),
             "output_type": "max", "resolution": res,
             "origin_x": x0, "origin_y": y0, "width": W, "height": H,
             "data_type": "float32"},
        ], label=f"dsm_{sfx}")
    dsm = read_tif(dsm_path)
    chm = np.where(np.isnan(dsm) | np.isnan(dem), np.nan,
                   np.maximum(dsm - dem, 0)).astype(np.float32)
    write_tif(out("chm"), chm, transform=transform, crs=dst_crs)

    # 3) Density + intensity (chunked laspy pass -> bounded RAM on multi-GB merges;
    #    laspy.read() would pull all ~200M pts of a dense QL1 3x3 into memory at once).
    print("  reading LAS for density + intensity...")
    density_flat = np.zeros(H * W, dtype=np.int64)
    sum_i = np.zeros(H * W, dtype=np.float64)
    cnt = np.zeros(H * W, dtype=np.float64)
    with laspy.open(str(las_path)) as lf:
        for pts in lf.chunk_iterator(5_000_000):
            cls = np.asarray(pts.classification)
            gm = cls == 2
            if not gm.any():
                continue
            xs = np.asarray(pts.x)[gm]; ys = np.asarray(pts.y)[gm]
            iv = np.asarray(pts.intensity).astype(np.float64)[gm]
            col = np.floor((xs - x0) / res).astype(np.int64)
            row = np.floor((y1 - ys) / res).astype(np.int64)
            ok = (col >= 0) & (col < W) & (row >= 0) & (row < H)
            fi = row[ok] * W + col[ok]
            density_flat += np.bincount(fi, minlength=H * W)
            sum_i += np.bincount(fi, weights=iv[ok], minlength=H * W)
            cnt += np.bincount(fi, minlength=H * W)
    density = density_flat.reshape(H, W).astype(np.uint16)
    write_tif(out("ground_density"), density,
              transform=transform, crs=dst_crs, dtype="uint16", nodata=0)
    mean_i = np.full(H * W, np.nan, dtype=np.float32)
    with np.errstate(invalid="ignore"):
        np.divide(sum_i, cnt, out=mean_i, where=cnt > 0)
    write_tif(out("intensity_ground"), mean_i.reshape(H, W),
              transform=transform, crs=dst_crs)
    del density_flat, sum_i, cnt, mean_i, density

    # 4) WBT hillshade + slope
    import whitebox
    wbt = whitebox.WhiteboxTools()
    wbt.set_working_dir(str(out_dir.resolve()))
    wbt.set_verbose_mode(False)
    wbt.hillshade(dem=f"dem_{sfx}.tif", output=f"hillshade_{sfx}.tif",
                  azimuth=315.0, altitude=45.0)
    wbt.slope(dem=f"dem_{sfx}.tif", output=f"slope_{sfx}.tif", units="degrees")
    print(f"  wrote hillshade_{sfx} + slope_{sfx}")

    # 5) Python derivatives
    # Roughness: stdev of DEM in 5x5 window.
    WIN = 5
    k = np.ones((WIN, WIN), dtype=np.float32)
    v = np.isfinite(dem).astype(np.float32)
    z0 = np.where(v.astype(bool), dem, 0).astype(np.float32)
    s = ndi.convolve(z0, k, mode="nearest")
    s2 = ndi.convolve(z0 * z0, k, mode="nearest")
    n = ndi.convolve(v, k, mode="nearest")
    var = np.where(n > 1, (s2 - s * s / np.maximum(n, 1)) / np.maximum(n - 1, 1), np.nan)
    rough = np.sqrt(np.clip(var, 0, None)).astype(np.float32)
    rough[n < WIN * WIN] = np.nan
    write_tif(out("roughness_5"), rough, transform=transform, crs=dst_crs)

    rk = disk_kernel(10 / res)
    lr = (_nanmax_disk(dem, rk) - _nanmin_disk(dem, rk)).astype(np.float32)
    write_tif(out("local_relief_10"), lr, transform=transform, crs=dst_crs)

    for size in (3, 5, 11, 25):
        valid = np.isfinite(dem).astype(np.float32)
        z0 = np.where(valid.astype(bool), dem, 0).astype(np.float32)
        sm = uniform_filter(z0, size=size, mode="nearest")
        sc = uniform_filter(valid, size=size, mode="nearest")
        smooth = np.where(sc > 0, sm / sc, np.nan)
        lrm = (dem - smooth).astype(np.float32)
        write_tif(out(f"lrm_{size}"), lrm, transform=transform, crs=dst_crs)

    def tpi(z: np.ndarray, r_m: float) -> np.ndarray:
        return (z - nanmean_filter(z, disk_kernel(r_m / res))).astype(np.float32)

    write_tif(out("tpi_05"), tpi(dem, 5.0),  transform=transform, crs=dst_crs)
    t15 = tpi(dem, 15.0)
    write_tif(out("tpi_15"), t15,            transform=transform, crs=dst_crs)
    write_tif(out("tpi_25"), tpi(dem, 25.0), transform=transform, crs=dst_crs)
    gy, gx = np.gradient(t15, res)
    write_tif(out("tpi_grad_mag"), np.hypot(gx, gy).astype(np.float32),
              transform=transform, crs=dst_crs)
    write_tif(out("tpi_grad_dir"),
              (np.degrees(np.arctan2(gx, -gy)) % 360).astype(np.float32),
              transform=transform, crs=dst_crs)

    print("  openness ...")
    op_pos, op_neg = openness(dem, L_cells=int(25 / res), cellsize=res)
    write_tif(out("openness_pos"), op_pos, transform=transform, crs=dst_crs)
    write_tif(out("openness_neg"), op_neg, transform=transform, crs=dst_crs)

    # 6) Overview PNG — stems are looked up via out() which adds the suffix.
    panels = [
        ("hillshade",        "hillshade",           "gray",   (None, None)),
        ("dem",              "DEM (m)",             "terrain",(None, None)),
        ("slope",            "slope (deg)",         "magma",  (0, 30)),
        ("intensity_ground", "ground intensity",    "cividis",(None, None)),
        ("ground_density",   "ground density",      "viridis",(0, 8)),
        ("chm",              "CHM (m)",             "Greens", (0, 30)),
        ("lrm_5",            "LRM 5",               "RdBu_r", (-0.6, 0.6)),
        ("lrm_11",           "LRM 11",              "RdBu_r", (-0.8, 0.8)),
        ("tpi_15",           "TPI 15 m",            "RdBu_r", (-0.5, 0.5)),
        ("openness_pos",     "openness_pos",        "viridis",(None, None)),
        ("openness_neg",     "openness_neg",        "viridis",(None, None)),
        ("local_relief_10",  "local relief (10 m)", "magma",  (0, 3)),
    ]
    fig, axes = plt.subplots(3, 4, figsize=(20, 18))
    for ax, (stem, title, cmap, lim) in zip(axes.ravel(), panels):
        a = read_tif(out(stem))
        kw = {"cmap": cmap, "extent": [x0, x1, y0, y1]}
        if lim[0] is not None:
            kw["vmin"], kw["vmax"] = lim
        im = ax.imshow(a, **kw)
        ax.set_title(title, fontsize=10)
        ax.set_xticks([]); ax.set_yticks([])
        plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.suptitle(f"{sfx} — {res:g} m derivative stack", fontsize=14)
    fig.tight_layout(rect=[0, 0, 1, 0.98])
    fig.savefig(out("tile_overview", "png"), dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote tile_overview_{sfx}.png")
    print(f"=== {sfx} DONE ===\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tiles", required=True,
                    help="Glob (relative to repo root) or comma-separated paths")
    ap.add_argument("--bbox", required=True, help="X0,Y0,X1,Y1 in target CRS (m)")
    ap.add_argument("--suffix", required=True, help="Output suffix (e.g. 9t_1m)")
    ap.add_argument("--res", type=float, default=1.0)
    ap.add_argument("--crs", default=DST_CRS, help=f"Target CRS (default {DST_CRS})")
    ap.add_argument("--src-crs", default=None,
                    help="Source CRS for reprojection (omit if source already in target CRS)")
    ap.add_argument("--merge-path", default=None,
                    help="Optional path for the intermediate merged LAS")
    ap.add_argument("--overwrite", action="store_true",
                    help="Rebuild outputs that already exist")
    ap.add_argument("--out-dir", default=None,
                    help="Explicit output directory (default: data/derivatives/<suffix>/)")
    ap.add_argument("--dem-method", default="delaunay", choices=["delaunay", "gdal"],
                    help="DEM interpolation: delaunay (TIN, high RAM) or gdal (IDW, streams — use for dense QL1)")
    args = ap.parse_args()

    tiles = resolve_tiles(args.tiles)
    if not tiles:
        print(f"no tiles matched: {args.tiles}", file=sys.stderr)
        return 1
    x0, y0, x1, y1 = (float(v) for v in args.bbox.split(","))
    merge = Path(args.merge_path) if args.merge_path else None
    build(tiles, x0=x0, y0=y0, x1=x1, y1=y1,
          res=args.res, sfx=args.suffix, dst_crs=args.crs,
          src_crs=args.src_crs, merge_path=merge,
          skip_existing=(not args.overwrite),
          out_dir=Path(args.out_dir) if args.out_dir else None,
          dem_method=args.dem_method)
    return 0


if __name__ == "__main__":
    sys.exit(main())
