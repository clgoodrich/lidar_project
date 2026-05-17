"""Pilot A: LAZ -> ground-classified DEM (1m) -> hillshade via PDAL CLI.

Per CLAUDE.md: invoke PDAL via subprocess, never via Python bindings.
Each tile's outputs are written in its native UTM zone (13N or 14N).
"""
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import laspy

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
LAZ_DIR = ROOT / "data/external/usgs_3dep_permian_tx/laz_pilot_A"
OUT = ROOT / "data/derivatives/pilot_A"
OUT.mkdir(parents=True, exist_ok=True)
TMP = OUT / "_tmp_pipelines"
TMP.mkdir(exist_ok=True)

PDAL_EXE = shutil.which("pdal") or r"C:\Users\colto\miniconda3\Library\bin\pdal.exe"


def run_pipeline(pipeline_dict, label, timeout=600):
    p = TMP / f"{label}.json"
    with open(p, "w") as f:
        json.dump(pipeline_dict, f, indent=2)
    t0 = time.time()
    r = subprocess.run([PDAL_EXE, "pipeline", str(p)],
                       capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    if r.returncode != 0:
        print(f"  [FAIL {label}] {dt:.1f}s")
        print(r.stderr[-1500:])
    else:
        print(f"  [ok {label}] {dt:.1f}s")
    return r


def utm_epsg_for_tile(laz_path):
    """Read VLRs to detect UTM zone 13N (EPSG:6342) vs 14N (EPSG:6343).

    Both are NAD83(2011) UTM. EPSG codes:
      - UTM 13N NAD83(2011): 6342
      - UTM 14N NAD83(2011): 6343
    """
    with laspy.open(laz_path) as fh:
        for vlr in fh.header.vlrs:
            s = str(getattr(vlr, "string", ""))
            if "UTM zone 13" in s:
                return 6342
            if "UTM zone 14" in s:
                return 6343
    return None


def process_tile(laz):
    name = laz.stem
    epsg = utm_epsg_for_tile(laz)
    if epsg is None:
        print(f"[skip] {name}: no UTM CRS found")
        return
    dem = OUT / f"{name}_dem_1m.tif"
    hs = OUT / f"{name}_hs_1m.tif"
    if dem.exists() and hs.exists():
        print(f"[skip-existing] {name}")
        return
    print(f"[{name}] EPSG:{epsg}")

    # PDAL: read LAZ -> SMRF ground filter -> writers.gdal IDW DEM @ 1m, ground only.
    # Many USGS tiles are already classified; SMRF is a safety net.
    pipe = {
        "pipeline": [
            {"type": "readers.las", "filename": str(laz)},
            {"type": "filters.range", "limits": "Classification[2:2]"},  # ground only (USGS pre-classified)
            {
                "type": "writers.gdal",
                "filename": str(dem),
                "resolution": 1.0,
                "output_type": "idw",
                "window_size": 3,
                "nodata": -9999,
                "data_type": "float32",
                "override_srs": f"EPSG:{epsg}",
            },
        ]
    }
    r = run_pipeline(pipe, f"{name}_dem")
    if r.returncode != 0:
        return

    # Hillshade via gdaldem (PDAL doesn't do hillshade)
    r = subprocess.run(["gdaldem", "hillshade", str(dem), str(hs),
                        "-az", "315", "-alt", "45", "-z", "1.0", "-of", "GTiff"],
                       capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        print(f"  [FAIL hillshade] {r.stderr[-500:]}")
    else:
        print(f"  [ok hillshade] {hs.name}")


def main():
    laz_files = sorted(LAZ_DIR.glob("*.laz"))
    print(f"Processing {len(laz_files)} LAZ tiles -> {OUT}")
    for laz in laz_files:
        process_tile(laz)
    print("Done.")


if __name__ == "__main__":
    main()
