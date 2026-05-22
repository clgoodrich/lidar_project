"""Generate a 2006-2008 -> 2019 surface-change map over the area where the
older PA Statewide N tiles overlap the 2019 D20 mosaic, using the ICP
transforms from data/derivatives/icp/<id>/_meta_icp*.json.

For each older tile:
  1. Read full LAZ -> keep ground (Class 2) -> reproject EPSG:2271 -> EPSG:6346
     -> Z * 0.3048 -> filters.transformation(composed_matrix from ICP) ->
     filters.delaunay -> filters.faceraster -> DEM @ 2 m.

Newer DEM:
  Read existing 1 m DEMs from data/derivatives/mosaic_3x3/{613594,618594,
  613599,618599}/dem_1m.tif and resample to the same 2 m grid.

Output (data/derivatives/icp/change_map/):
  dem_old_aligned_2m.tif      mosaicked aligned older DEM
  dem_new_2m.tif              resampled newer DEM
  dem_diff_2m.tif             new - old (m)
  change_map.png              diverging-colormap render with hillshade context
"""
from __future__ import annotations
import glob, json, subprocess, time
from pathlib import Path
import numpy as np
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import reproject, Resampling
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OLDER_DIR = ROOT / "data" / "older_files"
ICP_ROOT = ROOT / "data" / "derivatives" / "icp"
MOSAIC_DIR = ROOT / "data" / "derivatives" / "mosaic_3x3"
OUT_DIR = ICP_ROOT / "change_map"
OUT_DIR.mkdir(exist_ok=True)
PDAL_EXE = "pdal"
RES = 2.0
CRS = "EPSG:6346"

OLD_CRS = "EPSG:2271"
Z_FT_TO_M = 0.3048

TILES = [
    ("002957", ICP_ROOT / "002957" / "_meta_icp.json"),
    ("002958", ICP_ROOT / "002958" / "_meta_icp.json"),
    ("002959", ICP_ROOT / "002959" / "_meta_icp.json"),
    ("003110", ICP_ROOT / "003110" / "_meta_icp.json"),
    ("003111", ICP_ROOT / "003111" / "_meta_icp_zm.json"),  # corrected meta file
    ("003112", ICP_ROOT / "003112" / "_meta_icp.json"),
]


def composed_matrix(meta_path: Path):
    m = json.loads(meta_path.read_text())["stages"]["filters.icp"]
    # PDAL prints rows separated by newlines, values space-delimited
    vals = [float(x) for row in m["composed"].strip().split("\n") for x in row.split()]
    return vals  # 16 floats, row-major


def tile_bbox_utm(older_laz: Path, mat: list[float]):
    """Reproject the tile bbox to UTM via PDAL info + apply the ICP rotation to
    get a tight aligned bbox. For ~1 m residual we just take the reprojected
    bbox and round outward."""
    r = subprocess.run([PDAL_EXE, "info", "--metadata", str(older_laz)],
                       capture_output=True, text=True, check=True)
    meta = json.loads(r.stdout)["metadata"]
    from pyproj import Transformer
    t = Transformer.from_crs(OLD_CRS, CRS, always_xy=True)
    corners = [t.transform(x, y) for x in (meta["minx"], meta["maxx"])
                                 for y in (meta["miny"], meta["maxy"])]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    x0 = np.floor(min(xs) / RES) * RES
    y0 = np.floor(min(ys) / RES) * RES
    x1 = np.ceil(max(xs) / RES) * RES
    y1 = np.ceil(max(ys) / RES) * RES
    return x0, y0, x1, y1


def build_aligned_dem(tile_id: str, meta_path: Path) -> Path:
    laz = OLDER_DIR / f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_{tile_id}.laz"
    mat = composed_matrix(meta_path)
    x0, y0, x1, y1 = tile_bbox_utm(laz, mat)
    W = int((x1 - x0) / RES); H = int((y1 - y0) / RES)
    out_dem = OUT_DIR / f"dem_old_{tile_id}_2m.tif"

    pipeline = {"pipeline": [
        {"type": "readers.las", "filename": str(laz)},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": OLD_CRS, "out_srs": CRS},
        {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M}"},
        {"type": "filters.transformation",
         "matrix": " ".join(f"{v:.12g}" for v in mat)},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster",
         "resolution": RES, "origin_x": x0, "origin_y": y0,
         "width": W, "height": H},
        {"type": "writers.raster", "filename": str(out_dem),
         "data_type": "float32"},
    ]}
    pj = OUT_DIR / f"_tmp_{tile_id}.json"
    pj.write_text(json.dumps(pipeline, indent=2))
    print(f"[{tile_id}] build aligned DEM ({W}x{H}) ...", end="", flush=True)
    t0 = time.time()
    r = subprocess.run([PDAL_EXE, "pipeline", str(pj)],
                       capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        print(" FAILED")
        print(r.stderr[-1500:])
        raise RuntimeError(tile_id)
    pj.unlink(missing_ok=True)
    print(f" {time.time()-t0:.1f}s")
    return out_dem


def mosaic_to_grid(input_tifs: list[Path], x0, y0, x1, y1, out_path: Path,
                   resampling=Resampling.bilinear):
    W = int((x1 - x0) / RES); H = int((y1 - y0) / RES)
    dst_transform = from_origin(x0, y1, RES, RES)
    dst = np.full((H, W), np.nan, dtype=np.float32)
    for p in input_tifs:
        with rasterio.open(p) as src:
            src_arr = src.read(1).astype(np.float32)
            nd = src.nodata
            if nd is not None:
                src_arr = np.where(src_arr == nd, np.nan, src_arr)
            buf = np.full((H, W), np.nan, dtype=np.float32)
            reproject(
                source=src_arr, destination=buf,
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=dst_transform, dst_crs=CRS,
                resampling=resampling,
                src_nodata=np.nan, dst_nodata=np.nan,
            )
            mask = np.isfinite(buf)
            dst = np.where(mask & ~np.isfinite(dst), buf,
                           np.where(mask & np.isfinite(dst), 0.5*(dst+buf), dst))
    with rasterio.open(out_path, "w", driver="GTiff",
                       height=H, width=W, count=1, dtype="float32",
                       crs=CRS, transform=dst_transform, nodata=-9999.0,
                       tiled=True, compress="deflate", predictor=3) as ds:
        ds.write(np.where(np.isfinite(dst), dst, -9999.0).astype(np.float32), 1)
    return out_path


def main():
    # 1) Build per-tile aligned older DEMs.
    older_dems = []
    bbox = [np.inf, np.inf, -np.inf, -np.inf]
    for tile_id, meta in TILES:
        p = build_aligned_dem(tile_id, meta)
        with rasterio.open(p) as ds:
            b = ds.bounds
            bbox = [min(bbox[0], b.left), min(bbox[1], b.bottom),
                    max(bbox[2], b.right), max(bbox[3], b.top)]
        older_dems.append(p)

    # Snap union to RES grid
    x0 = np.floor(bbox[0] / RES) * RES
    y0 = np.floor(bbox[1] / RES) * RES
    x1 = np.ceil(bbox[2] / RES) * RES
    y1 = np.ceil(bbox[3] / RES) * RES
    print(f"common grid UTM bbox: X[{x0:.0f}..{x1:.0f}] Y[{y0:.0f}..{y1:.0f}]")

    # 2) Mosaic older DEMs into common grid.
    old_path = OUT_DIR / "dem_old_aligned_2m.tif"
    print("mosaic older ...")
    mosaic_to_grid(older_dems, x0, y0, x1, y1, old_path)

    # 3) Mosaic + resample newer 1m DEMs from the overlapping 3x3 blocks.
    new_tifs = [MOSAIC_DIR / k / "dem_1m.tif" for k in
                ("613594", "618594", "613599", "618599")
                if (MOSAIC_DIR / k / "dem_1m.tif").exists()]
    print(f"mosaic newer from {len(new_tifs)} tiles ...")
    new_path = OUT_DIR / "dem_new_2m.tif"
    mosaic_to_grid(new_tifs, x0, y0, x1, y1, new_path)

    # 4) Diff.
    with rasterio.open(old_path) as o, rasterio.open(new_path) as n:
        old = o.read(1); old = np.where(old == o.nodata, np.nan, old)
        new = n.read(1); new = np.where(new == n.nodata, np.nan, new)
    diff = new - old

    # Crop to rows/cols where both exist (the actual overlap)
    valid_mask = np.isfinite(diff)
    rows = np.where(valid_mask.any(axis=1))[0]
    cols = np.where(valid_mask.any(axis=0))[0]
    if rows.size and cols.size:
        r0, r1 = rows.min(), rows.max() + 1
        c0, c1 = cols.min(), cols.max() + 1
        old = old[r0:r1, c0:c1]
        new = new[r0:r1, c0:c1]
        diff = diff[r0:r1, c0:c1]
        H_c, W_c = diff.shape
        x0 = x0 + c0 * RES
        y1 = y1 - r0 * RES
        x1 = x0 + W_c * RES
        y0 = y1 - H_c * RES
        print(f"cropped to overlap: X[{x0:.0f}..{x1:.0f}] Y[{y0:.0f}..{y1:.0f}] ({W_c}x{H_c})")
    diff_path = OUT_DIR / "dem_diff_2m.tif"
    with rasterio.open(new_path) as ref:
        with rasterio.open(diff_path, "w", driver="GTiff",
                           height=ref.height, width=ref.width, count=1,
                           dtype="float32", crs=ref.crs, transform=ref.transform,
                           nodata=-9999.0, tiled=True, compress="deflate",
                           predictor=3) as ds:
            ds.write(np.where(np.isfinite(diff), diff, -9999.0).astype(np.float32), 1)

    valid = diff[np.isfinite(diff)]
    print(f"diff stats (m): n={valid.size:_}  mean={valid.mean():+.3f}  "
          f"median={np.median(valid):+.3f}  std={valid.std():.3f}  "
          f"p1={np.percentile(valid,1):+.2f}  p99={np.percentile(valid,99):+.2f}  "
          f"min={valid.min():+.2f}  max={valid.max():+.2f}")

    # 5) Render: hillshade context (from newer DEM) + diverging diff overlay
    #    Thresholded to |dz| > 0.5 m to suppress sub-residual noise.
    from matplotlib.colors import LightSource
    ls = LightSource(azdeg=315, altdeg=45)
    new_for_hs = np.where(np.isfinite(new), new, np.nanmean(new))
    hs = ls.hillshade(new_for_hs, vert_exag=2.0, dx=RES, dy=RES)

    NOISE = 0.5  # metres
    masked = np.where(np.isfinite(diff) & (np.abs(diff) >= NOISE), diff, np.nan)

    # Use a fixed +/-5 m colour range; clip extremes so a few outlier pixels
    # don't wash out the rest of the map.
    vmax = 5.0

    fig, axes = plt.subplots(1, 2, figsize=(22, 10))

    ax = axes[0]
    ax.imshow(hs, cmap="gray",
              extent=[x0, x1, y0, y1])
    ax.set_title("2019 hillshade (context)", fontsize=11)
    ax.set_xlabel("UTM 17N E (m)"); ax.set_ylabel("UTM 17N N (m)")

    ax = axes[1]
    ax.imshow(hs, cmap="gray", alpha=0.6,
              extent=[x0, x1, y0, y1])
    im = ax.imshow(masked, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                   extent=[x0, x1, y0, y1], alpha=0.85)
    cb = plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cb.set_label("DEM diff: 2019 − 2006/2008 (m)")
    ax.set_title(f"surface change |dz| >= {NOISE:.1f} m  "
                 f"(red = surface raised, blue = surface lowered)", fontsize=11)
    ax.set_xlabel("UTM 17N E (m)"); ax.set_ylabel("UTM 17N N (m)")

    fig.suptitle(
        "DEM change: 2006-2008 PA Statewide N vs. 2019 USGS 3DEP D20 "
        f"(ICP-aligned, {RES:.0f} m grid)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = OUT_DIR / "change_map.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")


if __name__ == "__main__":
    main()
