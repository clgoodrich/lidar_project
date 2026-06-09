"""One-off hillshade builder for the three LAZ tiles in
data/external/usgs_3dep_pa_lidar/downloadlist_7.txt.

Two 2019 WesternPA D20 tiles (UTM 17N, m, contiguous N-S strip) get merged
into one DEM + hillshade for visual continuity. The 2006-2008 PA Statewide
North tile (PA SP N, US ft, Z in US ft) is reprojected to UTM 17N with a
Z*0.3048 conversion to metres, matching project canonical units.

Outputs land under data/derivatives/tiles/extras/<key>/ with the standard pair:
  dem_<key>_1m.tif
  hillshade_<key>_1m.tif           az=315 alt=45
  hillshade_az135_<key>_1m.tif     az=135 alt=45

CLI:  python notebooks/wellsight/build/_build_hillshades_downloadlist7.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DST_CRS, ROOT, run_pdal

RES = 1.0
OUT_BASE = DERIV / "tiles" / "extras"

WP_DIR = ROOT / "data" / "source_laz" / "westernpa"
OLD_DIR = ROOT / "data" / "source_laz" / "westernpa" / "older_files"

JOBS = [
    {
        "key": "wp_2019_610597_610599",
        "tiles": [
            WP_DIR / "USGS_LPC_PA_WesternPA_2019_D20_17TPF610597.laz",
            WP_DIR / "USGS_LPC_PA_WesternPA_2019_D20_17TPF610599.laz",
        ],
        "src_crs": None,  # already EPSG:6346 (Z in m)
        "z_scale": None,
        # combined bbox of the two stacked tiles (UTM 17N m)
        "bbox": (610500.0, 4597500.0, 612000.0, 4600500.0),
    },
    {
        "key": "statewide_2006_003252",
        "tiles": [OLD_DIR / "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003252.laz"],
        "src_crs": "EPSG:32128",  # NAD83 / PA SP North (US ft)
        "z_scale": 0.3048,        # source Z in US ft -> m
        # will compute UTM 17N bbox after reprojecting first/last point in pipeline;
        # using a conservative pre-computed bbox derived from source extent.
        "bbox": None,
    },
]


def utm_bbox_from_statewide() -> tuple[float, float, float, float]:
    """Reproject the PA SP N (US ft) source extent corners to UTM 17N (m).

    Source extent from header: X 1440000..1450000 ft, Y 500000..510000 ft.
    """
    from pyproj import Transformer
    t = Transformer.from_crs("EPSG:32128", DST_CRS, always_xy=True)
    corners = [t.transform(x, y) for x in (1440000.0, 1450000.0)
                                  for y in (500000.0, 510000.0)]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    # Snap to RES grid, small inset to be safe with edge points.
    import math
    return (math.floor(min(xs)/RES)*RES, math.floor(min(ys)/RES)*RES,
            math.ceil(max(xs)/RES)*RES,  math.ceil(max(ys)/RES)*RES)


def build_one(job: dict) -> None:
    import whitebox
    key = job["key"]
    out_dir = OUT_BASE / key
    out_dir.mkdir(parents=True, exist_ok=True)
    dem_path = out_dir / f"dem_{key}_1m.tif"
    hs_path = out_dir / f"hillshade_{key}_1m.tif"
    hs135_path = out_dir / f"hillshade_az135_{key}_1m.tif"

    if hs_path.exists() and hs135_path.exists():
        print(f"[{key}] hillshades already present, skip"); return

    bbox = job["bbox"] or utm_bbox_from_statewide()
    x0, y0, x1, y1 = bbox
    W = int(round((x1 - x0) / RES))
    H = int(round((y1 - y0) / RES))
    print(f"[{key}] DEM grid {W}x{H}  bbox {x0:.0f},{y0:.0f},{x1:.0f},{y1:.0f}")

    if not dem_path.exists():
        stages: list = [str(p) for p in job["tiles"]]
        if len(job["tiles"]) > 1:
            stages.append({"type": "filters.merge"})
        if job["z_scale"]:
            stages.append({"type": "filters.assign",
                           "value": f"Z = Z * {job['z_scale']}"})
        if job["src_crs"]:
            stages.append({"type": "filters.reprojection",
                           "in_srs": job["src_crs"], "out_srs": DST_CRS})
        stages += [
            {"type": "filters.range", "limits": "Classification[2:2]"},
            {"type": "filters.delaunay"},
            {"type": "filters.faceraster",
             "resolution": RES, "origin_x": x0, "origin_y": y0,
             "width": W, "height": H},
            {"type": "writers.raster", "filename": str(dem_path),
             "data_type": "float32"},
        ]
        t0 = time.time()
        run_pdal(stages, label=f"dem_{key}", tmp_dir=out_dir, timeout=3600)
        print(f"[{key}] DEM in {time.time()-t0:.1f}s")

    wbt = whitebox.WhiteboxTools(); wbt.set_verbose_mode(False)
    wbt.set_working_dir(str(out_dir.resolve()))
    for hs_name, az in ((hs_path.name, 315.0), (hs135_path.name, 135.0)):
        rc = wbt.hillshade(dem=dem_path.name, output=hs_name,
                           azimuth=az, altitude=45.0)
        if rc != 0:
            print(f"[{key}] hillshade az={az} FAILED rc={rc}")
        else:
            print(f"[{key}] -> {hs_name}")


def main() -> int:
    OUT_BASE.mkdir(parents=True, exist_ok=True)
    for job in JOBS:
        build_one(job)
    return 0


if __name__ == "__main__":
    sys.exit(main())
