"""Extract LAS class 9 (Water) points from the 22-tile Oil Creek mosaic and
rasterize them on the same grid as ``dem_oilcreek_22tile_1m.tif``.

Outputs (next to the DEM):
  water_count_oilcreek_22tile_1m.tif   uint16, water returns per 1 m cell
  water_mask_oilcreek_22tile_1m.tif    uint8,  1 where any water return, 0 elsewhere
  dist_to_water_oilcreek_22tile_1m.tif float32, Euclidean dist in metres
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import distance_transform_edt

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, make_profile, run_pdal

KEY = "oilcreek_22tile"
RES = 1.0
OUT_DIR = DERIV / "tiles" / "extras" / KEY
SRC_DIR = ROOT / "data" / "source_laz" / "westernpa"
PLAN = ROOT / "data" / "external" / "oil_creek" / "contiguous_20_plan.txt"

SEED = [
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610597.laz",
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610599.laz",
]


def main() -> int:
    dem_path = OUT_DIR / f"dem_{KEY}_1m.tif"
    if not dem_path.exists():
        print(f"missing DEM template: {dem_path}", file=sys.stderr); return 1

    with rasterio.open(dem_path) as r:
        H, W = r.height, r.width
        transform = r.transform
        crs = r.crs
        left, top = transform.c, transform.f
        bottom = top - H * RES
    print(f"grid {W}x{H}  bbox left={left:.0f} bottom={bottom:.0f} top={top:.0f}")

    plan_names = [u.rsplit('/', 1)[-1] for u in PLAN.read_text().splitlines() if u.strip()]
    all_names = sorted(set(SEED + plan_names))
    paths = [SRC_DIR / n for n in all_names]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"ERROR {len(missing)} missing LAZ", file=sys.stderr); return 1
    print(f"{len(paths)} LAZ inputs")

    count_path = OUT_DIR / f"water_count_{KEY}_1m.tif"
    mask_path = OUT_DIR / f"water_mask_{KEY}_1m.tif"
    dist_path = OUT_DIR / f"dist_to_water_{KEY}_1m.tif"

    if not count_path.exists():
        stages: list = [str(p) for p in paths]
        stages.append({"type": "filters.merge"})
        stages.append({"type": "filters.range", "limits": "Classification[9:9]"})
        stages.append({"type": "writers.gdal",
                       "filename": str(count_path),
                       "resolution": RES, "output_type": "count",
                       "data_type": "uint16",
                       "origin_x": left, "origin_y": bottom,
                       "width": W, "height": H, "nodata": 0})
        t0 = time.time()
        run_pdal(stages, label=f"water_{KEY}", tmp_dir=OUT_DIR, timeout=3600)
        print(f"water count raster in {time.time()-t0:.1f}s")

    with rasterio.open(count_path) as r:
        cnt = r.read(1)
    n_water_px = int((cnt > 0).sum())
    print(f"water cells: {n_water_px:,}  ({n_water_px/(H*W)*100:.2f}% of grid)")
    if n_water_px == 0:
        print("WARNING: zero water cells — pipeline produced no class-9 hits")
        return 0

    mask = (cnt > 0).astype(np.uint8)
    mprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(mask_path, "w", **mprof) as ds:
        ds.write(mask, 1)
    print(f"wrote {mask_path.name}")

    dist = distance_transform_edt(mask == 0).astype(np.float32) * RES
    dprof = make_profile(width=W, height=H, transform=transform, crs=crs,
                         dtype="float32", nodata=-1.0, bigtiff=True)
    with rasterio.open(dist_path, "w", **dprof) as ds:
        ds.write(dist, 1)
    print(f"wrote {dist_path.name}  "
          f"(max d-to-water = {float(dist.max()):.1f} m, "
          f"median = {float(np.median(dist)):.1f} m)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
