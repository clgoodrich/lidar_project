"""Build a 1 m mean-intensity raster of GROUND returns for the 9t study area
from the freshly-downloaded PA_WesternPA_2019_D20 LAZ tiles.

Output: data/derivatives/intensity_ground_9t_1m.tif (float32, EPSG:6346).
This is Beck et al. 2015's primary attribute. Per CLAUDE.md, PDAL is invoked
via subprocess (Python bindings disabled).
"""
import json
import subprocess
import shutil
import time
from pathlib import Path

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
LAZ_DIR = ROOT / "data" / "external" / "usgs_3dep_pa_lidar" / "laz" / "PA_WesternPA_2019_D20"
DERIV = ROOT / "data" / "derivatives"
OUT = DERIV / "intensity_ground_9t_1m.tif"
TMP = DERIV / "_tmp_intensity_9t_pipeline.json"

# 9t grid (matches dem_9t_1m.tif)
X0, Y0, X1, Y1 = 619500.0, 4593000.0, 624000.0, 4597500.0
RES = 1.0
W = int((X1 - X0) / RES)
H = int((Y1 - Y0) / RES)
CRS = "EPSG:6346"

PDAL = shutil.which("pdal") or "pdal"


def main():
    tiles = sorted(LAZ_DIR.glob("*.laz"))
    print(f"input LAZ tiles: {len(tiles)}")
    if not tiles:
        raise SystemExit("no tiles found")

    pipeline = []
    for p in tiles:
        pipeline.append({"type": "readers.las", "filename": str(p)})
    pipeline.append({"type": "filters.merge"})
    pipeline.append({
        "type": "filters.crop",
        "bounds": f"([{X0},{X1}],[{Y0},{Y1}])",
    })
    pipeline.append({
        "type": "filters.range",
        "limits": "Classification[2:2]",
    })
    pipeline.append({
        "type": "writers.gdal",
        "filename": str(OUT),
        "output_type": "mean",
        "dimension": "Intensity",
        "resolution": RES,
        "origin_x": X0,
        "origin_y": Y0,
        "width": W,
        "height": H,
        "data_type": "float32",
        "nodata": -9999.0,
        "gdaldriver": "GTiff",
        "gdalopts": "COMPRESS=DEFLATE,PREDICTOR=2,TILED=YES",
        "override_srs": CRS,
    })

    with open(TMP, "w") as f:
        json.dump({"pipeline": pipeline}, f, indent=2)
    print(f"pipeline -> {TMP}")
    print(f"output   -> {OUT}  ({W}x{H} @ {RES} m, {CRS})")

    t0 = time.time()
    r = subprocess.run([PDAL, "pipeline", str(TMP)],
                       capture_output=True, text=True, timeout=1800)
    print(f"pdal exit={r.returncode}  elapsed={time.time()-t0:.0f}s")
    if r.stdout:
        print("STDOUT:")
        print(r.stdout[-2000:])
    if r.stderr:
        print("STDERR:")
        print(r.stderr[-2000:])
    if r.returncode != 0:
        raise SystemExit("pdal pipeline failed")
    print(f"OK: {OUT}")


if __name__ == "__main__":
    main()
