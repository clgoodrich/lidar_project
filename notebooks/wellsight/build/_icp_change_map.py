"""2006-2008 -> 2019 surface-change map over the area where the older PA
Statewide N tiles overlap the 2019 D20 mosaic, using ICP composed transforms
from data/derivatives/icp/<id>/_meta_icp*.json.

Pipeline per older tile:
  read LAZ -> ground -> reproject EPSG:2271 -> EPSG:6346 -> Z * 0.3048 ->
  filters.transformation(composed) -> delaunay -> faceraster -> DEM @ 2 m.

Newer DEMs: reuse the existing 1 m DEMs from data/derivatives/mosaic_3x3/
{613594,618594,613599,618599}/dem_1m.tif, resampled to the same 2 m grid.

Outputs (data/derivatives/icp/change_map/):
  dem_old_aligned_2m.tif      mosaicked aligned older DEM
  dem_new_2m.tif              resampled newer DEM
  dem_diff_2m.tif             new - old (m)
  change_map.png              diverging-colormap render with hillshade context
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LightSource
from pyproj import Transformer
from rasterio.transform import from_origin
from rasterio.warp import Resampling, reproject

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, PDAL_EXE, ROOT, run_pdal, write_tif

OLDER_DIR = ROOT / "data" / "older_files"
ICP_ROOT = DERIV / "icp"
MOSAIC_DIR = DERIV / "mosaic_3x3"
OUT_DIR = ICP_ROOT / "change_map"
OUT_DIR.mkdir(parents=True, exist_ok=True)
RES = 2.0
OLD_CRS = "EPSG:2271"
Z_FT_TO_M = 0.3048

TILES: list[tuple[str, Path]] = [
    ("002957", ICP_ROOT / "002957" / "_meta_icp.json"),
    ("002958", ICP_ROOT / "002958" / "_meta_icp.json"),
    ("002959", ICP_ROOT / "002959" / "_meta_icp.json"),
    ("003110", ICP_ROOT / "003110" / "_meta_icp.json"),
    ("003111", ICP_ROOT / "003111" / "_meta_icp_zm.json"),  # corrected file
    ("003112", ICP_ROOT / "003112" / "_meta_icp.json"),
]


def composed_matrix(meta_path: Path) -> list[float]:
    m = json.loads(meta_path.read_text())["stages"]["filters.icp"]
    return [float(x) for row in m["composed"].strip().split("\n") for x in row.split()]


def tile_bbox_utm(older_laz: Path) -> tuple[float, float, float, float]:
    """Reproject the older LAZ bbox to UTM and snap outward to the RES grid."""
    r = subprocess.run([PDAL_EXE, "info", "--metadata", str(older_laz)],
                       capture_output=True, text=True, check=True)
    meta = json.loads(r.stdout)["metadata"]
    t = Transformer.from_crs(OLD_CRS, DST_CRS, always_xy=True)
    corners = [t.transform(x, y) for x in (meta["minx"], meta["maxx"])
                                 for y in (meta["miny"], meta["maxy"])]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    return (np.floor(min(xs) / RES) * RES,
            np.floor(min(ys) / RES) * RES,
            np.ceil(max(xs) / RES) * RES,
            np.ceil(max(ys) / RES) * RES)


def build_aligned_dem(tile_id: str, meta_path: Path) -> Path:
    laz = OLDER_DIR / f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_{tile_id}.laz"
    mat = composed_matrix(meta_path)
    x0, y0, x1, y1 = tile_bbox_utm(laz)
    W = int((x1 - x0) / RES); H = int((y1 - y0) / RES)
    out_dem = OUT_DIR / f"dem_old_{tile_id}_2m.tif"
    run_pdal([
        {"type": "readers.las", "filename": str(laz)},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": OLD_CRS, "out_srs": DST_CRS},
        {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M}"},
        {"type": "filters.transformation",
         "matrix": " ".join(f"{v:.12g}" for v in mat)},
        {"type": "filters.delaunay"},
        {"type": "filters.faceraster",
         "resolution": RES, "origin_x": x0, "origin_y": y0, "width": W, "height": H},
        {"type": "writers.raster", "filename": str(out_dem), "data_type": "float32"},
    ], label=tile_id, tmp_dir=OUT_DIR, timeout=1800)
    return out_dem


def mosaic_to_grid(tifs: list[Path], x0: float, y0: float, x1: float, y1: float,
                   out_path: Path) -> None:
    """Reproject each input onto a common 2 m grid; average where overlapping."""
    W = int((x1 - x0) / RES); H = int((y1 - y0) / RES)
    dst_transform = from_origin(x0, y1, RES, RES)
    dst = np.full((H, W), np.nan, dtype=np.float32)
    for p in tifs:
        with rasterio.open(p) as src:
            src_arr = src.read(1).astype(np.float32)
            if src.nodata is not None:
                src_arr = np.where(src_arr == src.nodata, np.nan, src_arr)
            buf = np.full((H, W), np.nan, dtype=np.float32)
            reproject(source=src_arr, destination=buf,
                      src_transform=src.transform, src_crs=src.crs,
                      dst_transform=dst_transform, dst_crs=DST_CRS,
                      resampling=Resampling.bilinear,
                      src_nodata=np.nan, dst_nodata=np.nan)
            mask = np.isfinite(buf)
            dst = np.where(mask & ~np.isfinite(dst), buf,
                           np.where(mask & np.isfinite(dst), 0.5 * (dst + buf), dst))
    write_tif(out_path, dst, transform=dst_transform, crs=DST_CRS, dtype="float32")


def main() -> int:
    # 1) Build per-tile aligned older DEMs and the union bbox.
    older_dems: list[Path] = []
    bbox = [np.inf, np.inf, -np.inf, -np.inf]
    for tile_id, meta in TILES:
        p = build_aligned_dem(tile_id, meta)
        with rasterio.open(p) as ds:
            b = ds.bounds
        bbox = [min(bbox[0], b.left),  min(bbox[1], b.bottom),
                max(bbox[2], b.right), max(bbox[3], b.top)]
        older_dems.append(p)
    x0 = np.floor(bbox[0] / RES) * RES
    y0 = np.floor(bbox[1] / RES) * RES
    x1 = np.ceil(bbox[2] / RES)  * RES
    y1 = np.ceil(bbox[3] / RES)  * RES
    print(f"common grid UTM bbox: X[{x0:.0f}..{x1:.0f}] Y[{y0:.0f}..{y1:.0f}]")

    # 2) Mosaic older DEMs and the overlapping newer DEMs onto the common grid.
    old_path = OUT_DIR / "dem_old_aligned_2m.tif"
    print("mosaic older ...")
    mosaic_to_grid(older_dems, x0, y0, x1, y1, old_path)

    new_tifs = [MOSAIC_DIR / k / "dem_1m.tif" for k in
                ("613594", "618594", "613599", "618599")
                if (MOSAIC_DIR / k / "dem_1m.tif").exists()]
    print(f"mosaic newer from {len(new_tifs)} tiles ...")
    new_path = OUT_DIR / "dem_new_2m.tif"
    mosaic_to_grid(new_tifs, x0, y0, x1, y1, new_path)

    # 3) Diff.
    with rasterio.open(old_path) as o, rasterio.open(new_path) as n:
        old = o.read(1); old = np.where(old == o.nodata, np.nan, old)
        new = n.read(1); new = np.where(new == n.nodata, np.nan, new)
    diff = new - old

    # Crop to the rows/cols where both exist.
    valid = np.isfinite(diff)
    rows = np.where(valid.any(axis=1))[0]
    cols = np.where(valid.any(axis=0))[0]
    if rows.size and cols.size:
        r0, r1 = int(rows.min()), int(rows.max() + 1)
        c0, c1 = int(cols.min()), int(cols.max() + 1)
        old  = old[r0:r1, c0:c1]
        new  = new[r0:r1, c0:c1]
        diff = diff[r0:r1, c0:c1]
        H_c, W_c = diff.shape
        x0 = x0 + c0 * RES
        y1 = y1 - r0 * RES
        x1 = x0 + W_c * RES
        y0 = y1 - H_c * RES
        print(f"cropped to overlap: X[{x0:.0f}..{x1:.0f}] Y[{y0:.0f}..{y1:.0f}] ({W_c}x{H_c})")

    diff_transform = from_origin(x0, y1, RES, RES)
    write_tif(OUT_DIR / "dem_diff_2m.tif", diff,
              transform=diff_transform, crs=DST_CRS, dtype="float32")

    valid_arr = diff[np.isfinite(diff)]
    print(f"diff stats (m): n={valid_arr.size:_}  mean={valid_arr.mean():+.3f}  "
          f"median={np.median(valid_arr):+.3f}  std={valid_arr.std():.3f}  "
          f"p1={np.percentile(valid_arr, 1):+.2f}  "
          f"p99={np.percentile(valid_arr, 99):+.2f}  "
          f"min={valid_arr.min():+.2f}  max={valid_arr.max():+.2f}")

    # 4) Render (mask sub-residual noise, fixed +/-5 m colour scale).
    new_for_hs = np.where(np.isfinite(new), new, np.nanmean(new))
    hs = LightSource(azdeg=315, altdeg=45).hillshade(new_for_hs, vert_exag=2.0,
                                                     dx=RES, dy=RES)
    noise = 0.5
    masked = np.where(np.isfinite(diff) & (np.abs(diff) >= noise), diff, np.nan)
    vmax = 5.0

    fig, axes = plt.subplots(1, 2, figsize=(22, 10))
    axes[0].imshow(hs, cmap="gray", extent=[x0, x1, y0, y1])
    axes[0].set_title("2019 hillshade (context)", fontsize=11)
    axes[0].set_xlabel("UTM 17N E (m)"); axes[0].set_ylabel("UTM 17N N (m)")

    axes[1].imshow(hs, cmap="gray", alpha=0.6, extent=[x0, x1, y0, y1])
    im = axes[1].imshow(masked, cmap="RdBu_r", vmin=-vmax, vmax=vmax,
                        extent=[x0, x1, y0, y1], alpha=0.85)
    cb = plt.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04)
    cb.set_label("DEM diff: 2019 − 2006/2008 (m)")
    axes[1].set_title(f"surface change |dz| >= {noise:.1f} m  "
                      "(red = surface raised, blue = surface lowered)", fontsize=11)
    axes[1].set_xlabel("UTM 17N E (m)"); axes[1].set_ylabel("UTM 17N N (m)")

    fig.suptitle("DEM change: 2006-2008 PA Statewide N vs. 2019 USGS 3DEP D20 "
                 f"(ICP-aligned, {RES:.0f} m grid)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.97])
    png = OUT_DIR / "change_map.png"
    fig.savefig(png, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"wrote {png}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
