"""Rebuild ground_density_9t_1m.tif using ONLY non-overlap ground returns.

PA 2019 D20 LAZ has each point flagged with an `Overlap` boolean. Including
overlap-flag-1 points doubles the density in flight-strip overlap zones,
which dominates Beck's density attribute and produces ~1.5 km grid artifacts.

Solution: PDAL filter `Overlap[0:0]` before counting ground returns per cell.
"""
import json
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
LAZ_DIR = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz" / "PA_WesternPA_2019_D20"
DERIV = ROOT / "data" / "derivatives"
OUT = DERIV / "ground_density_noverlap_9t_1m.tif"
TMP = DERIV / "_tmp_density_no_pipeline.json"

X0, Y0, X1, Y1 = 619500.0, 4593000.0, 624000.0, 4597500.0
RES = 1.0
W = int((X1 - X0) / RES)
H = int((Y1 - Y0) / RES)
CRS = "EPSG:6346"
PDAL = shutil.which("pdal") or "pdal"


def main():
    tiles = sorted(LAZ_DIR.glob("*.laz"))
    print(f"input LAZ tiles: {len(tiles)}")

    pipeline = []
    for p in tiles:
        pipeline.append({"type": "readers.las", "filename": str(p)})
    pipeline.append({"type": "filters.merge"})
    pipeline.append({"type": "filters.crop",
                     "bounds": f"([{X0},{X1}],[{Y0},{Y1}])"})
    pipeline.append({"type": "filters.range",
                     "limits": "Classification[2:2],Overlap[0:0]"})
    pipeline.append({
        "type": "writers.gdal",
        "filename": str(OUT),
        "output_type": "count",
        "resolution": RES,
        "origin_x": X0,
        "origin_y": Y0,
        "width": W,
        "height": H,
        "data_type": "uint16",
        "nodata": 0,
        "gdaldriver": "GTiff",
        "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES",
        "override_srs": CRS,
    })
    with open(TMP, "w") as f:
        json.dump({"pipeline": pipeline}, f, indent=2)

    t0 = time.time()
    r = subprocess.run([PDAL, "pipeline", str(TMP)],
                       capture_output=True, text=True, timeout=1800)
    print(f"pdal exit={r.returncode}  elapsed={time.time()-t0:.0f}s")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("pipeline failed")
    print(f"OK: {OUT}")


if __name__ == "__main__":
    main()
