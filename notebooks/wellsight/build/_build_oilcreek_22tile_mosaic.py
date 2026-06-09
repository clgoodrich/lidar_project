"""Build a 1 m DEM + hillshade mosaic for the 22-tile contiguous patch over
Oil Creek State Park.

Inputs are the two seed WesternPA D20 tiles already in data/source_laz/westernpa (610597 +
610599) plus the 20 tiles enumerated in
data/external/oil_creek/contiguous_20_plan.txt.

Outputs go to data/derivatives/tiles/extras/oilcreek_22tile/:
  dem_oilcreek_22tile_1m.tif
  hillshade_oilcreek_22tile_1m.tif         az=315 alt=45
  hillshade_az135_oilcreek_22tile_1m.tif   az=135 alt=45
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import laspy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, run_pdal

RES = 1.0
KEY = "oilcreek_22tile"
OUT_DIR = DERIV / "tiles" / "extras" / KEY
SRC_DIR = ROOT / "data" / "source_laz" / "westernpa"
PLAN = ROOT / "data" / "external" / "oil_creek" / "contiguous_20_plan.txt"

SEED = [
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610597.laz",
    "USGS_LPC_PA_WesternPA_2019_D20_17TPF610599.laz",
]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    dem_path = OUT_DIR / f"dem_{KEY}_1m.tif"
    hs315 = OUT_DIR / f"hillshade_{KEY}_1m.tif"
    hs135 = OUT_DIR / f"hillshade_az135_{KEY}_1m.tif"

    plan_names = [u.rsplit("/", 1)[-1] for u in PLAN.read_text().splitlines() if u.strip()]
    all_names = sorted(set(SEED + plan_names))
    paths = [SRC_DIR / n for n in all_names]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"ERROR: {len(missing)} missing LAZ:\n  " +
              "\n  ".join(p.name for p in missing[:5]), file=sys.stderr)
        return 1
    print(f"{len(paths)} tiles found")

    # Compute union bbox in UTM 17N (m) from headers.
    xs = []; ys = []
    for p in paths:
        h = laspy.open(p).header
        xs += [h.x_min, h.x_max]; ys += [h.y_min, h.y_max]
    x0 = min(xs); x1 = max(xs); y0 = min(ys); y1 = max(ys)
    # Snap to RES.
    import math
    x0 = math.floor(x0 / RES) * RES; y0 = math.floor(y0 / RES) * RES
    x1 = math.ceil(x1 / RES) * RES;  y1 = math.ceil(y1 / RES) * RES
    W = int(round((x1 - x0) / RES)); H = int(round((y1 - y0) / RES))
    print(f"union bbox UTM17N: {x0:.0f}..{x1:.0f}  {y0:.0f}..{y1:.0f}  "
          f"(grid {W}x{H} @ 1m)")

    if not dem_path.exists():
        stages: list = [str(p) for p in paths]
        stages.append({"type": "filters.merge"})
        stages.append({"type": "filters.range", "limits": "Classification[2:2]"})
        stages.append({"type": "filters.delaunay"})
        stages.append({"type": "filters.faceraster",
                       "resolution": RES, "origin_x": x0, "origin_y": y0,
                       "width": W, "height": H})
        stages.append({"type": "writers.raster",
                       "filename": str(dem_path), "data_type": "float32"})
        t0 = time.time()
        run_pdal(stages, label=f"dem_{KEY}", tmp_dir=OUT_DIR, timeout=7200)
        print(f"DEM built in {time.time()-t0:.1f}s")
    else:
        print(f"DEM already exists: {dem_path.name}")

    import whitebox
    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(OUT_DIR.resolve()))
    for hs_name, az in ((hs315.name, 315.0), (hs135.name, 135.0)):
        if (OUT_DIR / hs_name).exists():
            print(f"  skip (exists) {hs_name}"); continue
        rc = wbt.hillshade(dem=dem_path.name, output=hs_name,
                           azimuth=az, altitude=45.0)
        if rc != 0:
            print(f"  hillshade az={az} FAILED rc={rc}")
        else:
            print(f"  wrote {hs_name}")

    print(f"\nDONE.  outputs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
