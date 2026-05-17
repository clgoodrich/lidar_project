"""Merge the 9 LAZ tiles covering the 9t study area into a single LAS file.

9t bbox: X 619500-624000, Y 4593000-4597500 (EPSG:6346, UTM 17N).
Source tiles: USGS PA_WesternPA_2019_D20, 1500m tiles {619,621,622} x {593,594,596}.
Output: data/files/9t_merged.las (~2-3 GB, gitignored via *.las pattern).
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
SRC_DIR = ROOT / "data" / "files"
OUT_LAS = SRC_DIR / "9t_merged.las"
PDAL_EXE = "pdal"

TILE_KEYS = [f"{e}{n}" for e in ("619", "621", "622") for n in ("593", "594", "596")]
INPUTS = [str(SRC_DIR / f"USGS_LPC_PA_WesternPA_2019_D20_17TPF{k}.laz") for k in TILE_KEYS]


def main() -> int:
    missing = [p for p in INPUTS if not Path(p).exists()]
    if missing:
        print("MISSING:", *missing, sep="\n  ")
        return 1

    pipeline = {
        "pipeline": [
            *INPUTS,
            {"type": "filters.merge"},
            {
                "type": "writers.las",
                "filename": str(OUT_LAS),
                "compression": "false",
                "minor_version": 4,
                "dataformat_id": 6,
                "forward": "all",
            },
        ]
    }

    tmp = SRC_DIR / "_tmp_merge_9t_pipeline.json"
    tmp.write_text(json.dumps(pipeline, indent=2))

    print(f"Merging {len(INPUTS)} tiles -> {OUT_LAS.name}")
    t0 = time.time()
    r = subprocess.run([PDAL_EXE, "pipeline", str(tmp)], capture_output=True, text=True, timeout=3600)
    dt = time.time() - t0
    if r.returncode != 0:
        print("PDAL stderr:\n", r.stderr)
        return r.returncode
    sz_mb = OUT_LAS.stat().st_size / 1e6
    print(f"OK in {dt:.1f}s -> {OUT_LAS} ({sz_mb:.0f} MB)")
    tmp.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
