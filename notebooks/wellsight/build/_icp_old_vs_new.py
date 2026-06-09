"""Align 2006-2008 PA Statewide N LiDAR onto 2019 USGS 3DEP WesternPA D20 via ICP.

Older data is **EPSG:2271** (NAD83 / PA State Plane North, US survey feet) — Z
also in feet. Current data is **EPSG:6346** (NAD83(2011) / UTM 17N, metres).
``filters.reprojection`` handles horizontal only; we scale Z by 0.3048 inline.

Per older tile:
  1. Reproject + ground-only filter + Z * 0.3048 + voxel sample -> LAS.
  2. Merge + ground-only + crop + voxel sample on overlapping 2019 tiles -> LAS.
  3. PDAL filters.icp (fixed=newer, moving=older) -> aligned LAS + meta JSON.

CLI:
  python notebooks/wellsight/build/_icp_old_vs_new.py --pilot
  python notebooks/wellsight/build/_icp_old_vs_new.py
  python notebooks/wellsight/build/_icp_old_vs_new.py --only 003111,002958
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DST_CRS, PDAL_EXE, ROOT, run_pdal

OLDER_DIR = ROOT / "data" / "older_files"
NEW_DIR = ROOT / "data" / "source_laz" / "westernpa"
OUT_ROOT = ROOT / "data" / "derivatives" / "icp"

OLD_CRS = "EPSG:2271"
VOXEL = 5.0  # ~400k pts/cloud at 5 m; ICP runs in seconds
Z_FT_TO_M = 0.3048

OLDER_TILES = [
    f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_{tile}.laz"
    for tile in ("002957", "002958", "002959", "003110", "003111", "003112")
]

# Current 17TPF/17TPG tile grid (calibrated against the 9t mosaic; matches
# build/_build_3x3_hillshades.py).
E_CODES  = ("604","606","607","609","610","612","613","615","616","618",
            "619","621","622","624")
NF_CODES = ("590","591","593","594","596","597","599")
NG_CODES = ("600","602","603","605","606","608")
TILE_M = 1500.0
E_ORIGIN  = 619500.0 - E_CODES.index("619") * TILE_M
N_ORIGIN_F = 4593000.0 - NF_CODES.index("593") * TILE_M
N_ORIGIN_G = N_ORIGIN_F + len(NF_CODES) * TILE_M


def _utm_e(code: str) -> float:
    return E_ORIGIN + E_CODES.index(code) * TILE_M


def _utm_n(band: str, code: str) -> float:
    return (N_ORIGIN_F if band == "F" else N_ORIGIN_G) + \
        (NF_CODES if band == "F" else NG_CODES).index(code) * TILE_M


def older_bbox_utm(older_path: Path) -> tuple[float, float, float, float]:
    """Reproject the older LAZ bbox (PA SP North ft) to UTM 17N (m)."""
    r = subprocess.run([PDAL_EXE, "info", "--metadata", str(older_path)],
                       capture_output=True, text=True, check=True)
    meta = json.loads(r.stdout)["metadata"]
    t = Transformer.from_crs(OLD_CRS, DST_CRS, always_xy=True)
    corners = [t.transform(x, y)
               for x in (meta["minx"], meta["maxx"])
               for y in (meta["miny"], meta["maxy"])]
    xs = [c[0] for c in corners]; ys = [c[1] for c in corners]
    return min(xs), min(ys), max(xs), max(ys)


def find_new_tiles(x0: float, y0: float, x1: float, y1: float) -> list[Path]:
    """All 17TPF/G LAZs whose 1500 m footprint intersects the bbox."""
    out: list[Path] = []
    for e in E_CODES:
        ux = _utm_e(e)
        if ux + TILE_M <= x0 or ux >= x1:
            continue
        for band, ncodes in (("F", NF_CODES), ("G", NG_CODES)):
            for n in ncodes:
                uy = _utm_n(band, n)
                if uy + TILE_M <= y0 or uy >= y1:
                    continue
                p = NEW_DIR / f"USGS_LPC_PA_WesternPA_2019_D20_17TP{band}{e}{n}.laz"
                if p.exists():
                    out.append(p)
    return out


def process_pair(older_path: Path, out_dir: Path) -> dict | None:
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[{older_path.name}] reading bbox")
    bx0, by0, bx1, by1 = older_bbox_utm(older_path)
    print(f"  UTM bbox: X[{bx0:.0f}..{bx1:.0f}] Y[{by0:.0f}..{by1:.0f}]")

    new_inputs = find_new_tiles(bx0, by0, bx1, by1)
    if not new_inputs:
        print("  no overlapping 2019 tiles -> skip")
        return None
    print(f"  matched {len(new_inputs)} new tile(s)")

    older_out = out_dir / "older_ground_utm.las"
    newer_out = out_dir / "newer_ground_utm.las"
    aligned_out = out_dir / "older_aligned.las"

    # 1) older: reproj + ground + Z scale + voxel.
    run_pdal([
        {"type": "readers.las", "filename": str(older_path)},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": OLD_CRS, "out_srs": DST_CRS},
        {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M}"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(older_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="older_prep", tmp_dir=out_dir)

    # 2) newer: merge + ground + crop + voxel.
    run_pdal([
        *[str(p) for p in new_inputs],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.crop", "bounds": f"([{bx0},{bx1}],[{by0},{by1}])"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(newer_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="newer_prep", tmp_dir=out_dir)

    # 3) ICP, capturing metadata.
    meta_path = run_pdal([
        {"type": "readers.las", "filename": str(newer_out), "tag": "fixed"},
        {"type": "readers.las", "filename": str(older_out), "tag": "moving"},
        {"type": "filters.icp", "inputs": ["fixed", "moving"]},
        {"type": "writers.las", "filename": str(aligned_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": DST_CRS},
    ], label="icp", tmp_dir=out_dir, capture_meta=True, timeout=7200)

    if meta_path is None or not meta_path.exists():
        print("  WARNING: no ICP metadata produced")
        return None
    meta = json.loads(meta_path.read_text())
    icp = meta.get("stages", {}).get("filters.icp", meta)
    summary = {
        "older_tile": older_path.name,
        "newer_tiles": [p.name for p in new_inputs],
        "overlap_bbox_utm": [bx0, by0, bx1, by1],
        "voxel_cell_m": VOXEL,
        "icp": icp,
    }
    (out_dir / "icp_summary.json").write_text(json.dumps(summary, indent=2))
    print(f"  converged={icp.get('converged')}  fitness={icp.get('fitness')}")
    print(f"  transform: {icp.get('transform') or icp.get('composed')}")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="only the 003111 <-> block 618594 pair")
    ap.add_argument("--only", help="comma-separated tile-IDs (e.g. 003111,002958)")
    args = ap.parse_args()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    if args.pilot:
        targets = [f"USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz"]
    elif args.only:
        keep = set(args.only.split(","))
        targets = [t for t in OLDER_TILES if t.split("_")[-1].split(".")[0] in keep]
    else:
        targets = OLDER_TILES

    results: list[dict] = []
    for name in targets:
        older_path = OLDER_DIR / name
        if not older_path.exists():
            print(f"missing: {older_path}")
            continue
        out_dir = OUT_ROOT / older_path.stem.split("_")[-1]  # "003111"
        try:
            res = process_pair(older_path, out_dir)
        except Exception as e:
            print(f"FAILED on {name}: {e}")
            continue
        if res:
            results.append(res)

    if results:
        (OUT_ROOT / "icp_all_summary.json").write_text(json.dumps(results, indent=2))
    print("DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
