"""Run ICP to align 2006-2008 PA Statewide N LiDAR (data/older_files/) onto the
2019 USGS 3DEP WesternPA D20 LiDAR (data/files/).

Older data is EPSG:2271 (NAD83 / PA State Plane North, US survey feet).
Current data is EPSG:6346 (NAD83(2011) / UTM 17N, metres).

Pilot pair (best overlap, ~2.9 km x 3.3 km in UTM):
  older  = USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz
  newer  = 17TPF{619,621} x {594,596,597} (6 tiles from data/files/)

Pipeline per pair:
  1. Reproject older LAZ to EPSG:6346, keep Classification=2 (ground), write LAS.
  2. Build a ground-only LAS from the matching current tiles, cropped to the
     older tile's reprojected bbox.
  3. Voxel-downsample both to ~1 m grid for ICP stability.
  4. PDAL filters.icp with fixed=newer, moving=older. Write aligned LAS and a
     JSON report containing the 4x4 transform and MSE.

CLI:
  python notebooks/wellsight/build/_icp_old_vs_new.py --pilot
  python notebooks/wellsight/build/_icp_old_vs_new.py             # all overlapping older tiles
"""
from __future__ import annotations
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path
from pyproj import Transformer

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OLDER_DIR = ROOT / "data" / "older_files"
NEW_DIR = ROOT / "data" / "files"
OUT_ROOT = ROOT / "data" / "derivatives" / "icp"
PDAL_EXE = shutil.which("pdal") or "pdal"

OLD_CRS = "EPSG:2271"
NEW_CRS = "EPSG:6346"
VOXEL = 5.0  # 5 m voxel downsample before ICP (~400k pts/cloud; ICP runs in seconds)
# Older PA Statewide N tiles store Z in US survey feet. filters.reprojection
# only converts horizontal, so we scale Z explicitly to metres.
Z_FT_TO_M = 0.3048

# Older tiles -> approximate PA SP North bbox (feet) inferred from the file
# name index. The 6-digit tile id splits as <x_lo><y_lo> where _57_=block 57
# along X (X starts at 1460000+ (57-?)) etc. We just read the actual bbox via
# pdal info at runtime; this mapping is only used to find candidate older tiles.

OLDER_TILES = [
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002957.laz",
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002958.laz",
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_002959.laz",
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003110.laz",
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz",
    "USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003112.laz",
]

# Current tiles tessellate the 18x18 km area built in _build_3x3_hillshades.py.
# Tile naming: 17TPF<E><N> where E,N are 3-digit codes and the tile is 1500 m
# wide with its lower-left at (utm_x_for_code, utm_y_for_code). Use the
# calibration from _build_3x3_hillshades.py.

E_CODES = ["604","606","607","609","610","612","613","615","616","618","619","621","622","624"]
NF_CODES = ["590","591","593","594","596","597","599"]
NG_CODES = ["600","602","603","605","606","608"]
TILE_M = 1500.0
E_ORIGIN = 619500.0 - E_CODES.index("619") * TILE_M
N_ORIGIN_F = 4593000.0 - NF_CODES.index("593") * TILE_M
N_ORIGIN_G = N_ORIGIN_F + len(NF_CODES) * TILE_M


def utm_for_e(code):
    return E_ORIGIN + E_CODES.index(code) * TILE_M


def utm_for_n(band, code):
    if band == "F":
        return N_ORIGIN_F + NF_CODES.index(code) * TILE_M
    return N_ORIGIN_G + NG_CODES.index(code) * TILE_M


def laz_bbox_utm(older_path):
    """Reproject the older LAZ bbox (PA SP North ft) to UTM 17N (m)."""
    r = subprocess.run([PDAL_EXE, "info", "--metadata", str(older_path)],
                       capture_output=True, text=True, check=True)
    meta = json.loads(r.stdout)["metadata"]
    xs = (meta["minx"], meta["maxx"])
    ys = (meta["miny"], meta["maxy"])
    t = Transformer.from_crs(OLD_CRS, NEW_CRS, always_xy=True)
    corners = [t.transform(x, y) for x in xs for y in ys]
    xs_u = [c[0] for c in corners]; ys_u = [c[1] for c in corners]
    return (min(xs_u), min(ys_u), max(xs_u), max(ys_u))


def find_new_tiles_intersecting(x0, y0, x1, y1):
    """Return list of 17TPF/17TPG LAZ paths whose 1500 m footprint overlaps the box."""
    out = []
    for e in E_CODES:
        ux = utm_for_e(e)
        if ux + TILE_M <= x0 or ux >= x1:
            continue
        for band, ncodes in (("F", NF_CODES), ("G", NG_CODES)):
            for n in ncodes:
                uy = utm_for_n(band, n)
                if uy + TILE_M <= y0 or uy >= y1:
                    continue
                p = NEW_DIR / f"USGS_LPC_PA_WesternPA_2019_D20_17TP{band}{e}{n}.laz"
                if p.exists():
                    out.append(p)
    return out


def run_pipeline(pipeline, label, out_dir, timeout=3600):
    tmp = out_dir / f"_tmp_{label}.json"
    tmp.write_text(json.dumps(pipeline, indent=2))
    t0 = time.time()
    r = subprocess.run([PDAL_EXE, "pipeline", "--metadata", str(out_dir / f"_meta_{label}.json"),
                        str(tmp)], capture_output=True, text=True, timeout=timeout)
    dt = time.time() - t0
    print(f"  [{label}] rc={r.returncode} in {dt:.1f}s")
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise RuntimeError(label)
    tmp.unlink(missing_ok=True)


def process_pair(older_path: Path, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[{older_path.name}] reading bbox")
    bx0, by0, bx1, by1 = laz_bbox_utm(older_path)
    print(f"  UTM bbox: X[{bx0:.0f}..{bx1:.0f}] Y[{by0:.0f}..{by1:.0f}]")

    new_inputs = find_new_tiles_intersecting(bx0, by0, bx1, by1)
    if not new_inputs:
        print("  no overlapping 2019 tiles found -> skip")
        return None
    print(f"  matched {len(new_inputs)} new tile(s)")

    older_out = out_dir / "older_ground_utm.las"
    newer_out = out_dir / "newer_ground_utm.las"
    aligned_out = out_dir / "older_aligned.las"

    # 1. Reproject + ground filter + voxel sample on older
    run_pipeline({"pipeline": [
        {"type": "readers.las", "filename": str(older_path)},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.reprojection", "in_srs": OLD_CRS, "out_srs": NEW_CRS},
        {"type": "filters.assign", "value": f"Z = Z * {Z_FT_TO_M}"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(older_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": NEW_CRS},
    ]}, "older_prep", out_dir)

    # 2. Merge + ground filter + crop + voxel sample on newer
    run_pipeline({"pipeline": [
        *[str(p) for p in new_inputs],
        {"type": "filters.merge"},
        {"type": "filters.range", "limits": "Classification[2:2]"},
        {"type": "filters.crop", "bounds": f"([{bx0},{bx1}],[{by0},{by1}])"},
        {"type": "filters.voxelcenternearestneighbor", "cell": VOXEL},
        {"type": "writers.las", "filename": str(newer_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": NEW_CRS},
    ]}, "newer_prep", out_dir)

    # 3. ICP: fixed=newer, moving=older
    icp_meta = out_dir / "icp_meta.json"
    run_pipeline({"pipeline": [
        {"type": "readers.las", "filename": str(newer_out), "tag": "fixed"},
        {"type": "readers.las", "filename": str(older_out), "tag": "moving"},
        {"type": "filters.icp", "inputs": ["fixed", "moving"]},
        {"type": "writers.las", "filename": str(aligned_out),
         "minor_version": 4, "dataformat_id": 6, "a_srs": NEW_CRS},
    ]}, "icp", out_dir, timeout=7200)

    # Read ICP metadata from the auto-generated _meta_icp.json
    meta_path = out_dir / "_meta_icp.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text())
        try:
            icp = meta["stages"]["filters.icp"]
        except Exception:
            icp = meta
        summary = {
            "older_tile": older_path.name,
            "newer_tiles": [p.name for p in new_inputs],
            "overlap_bbox_utm": [bx0, by0, bx1, by1],
            "voxel_cell_m": VOXEL,
            "icp": icp,
        }
        (out_dir / "icp_summary.json").write_text(json.dumps(summary, indent=2))
        # Pretty-print the key parts
        t = icp.get("transform") or icp.get("composed")
        conv = icp.get("converged")
        fit = icp.get("fitness") or icp.get("fitness_score")
        mse = icp.get("mse")
        print(f"  converged={conv}  fitness={fit}  mse={mse}")
        print(f"  transform: {t}")
        return summary
    print("  WARNING: no _meta_icp.json found")
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true",
                    help="only the 003111 <-> block 618594 pair")
    ap.add_argument("--only", help="comma-separated older tile basenames (no .laz)")
    args = ap.parse_args()

    OUT_ROOT.mkdir(parents=True, exist_ok=True)

    if args.pilot:
        targets = ["USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_003111.laz"]
    elif args.only:
        keep = set(args.only.split(","))
        targets = [t for t in OLDER_TILES if Path(t).stem in keep]
    else:
        targets = OLDER_TILES

    results = []
    for name in targets:
        older_path = OLDER_DIR / name
        if not older_path.exists():
            print(f"missing: {older_path}")
            continue
        out_dir = OUT_ROOT / older_path.stem.split("_")[-1]  # e.g. "003111"
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


if __name__ == "__main__":
    main()
