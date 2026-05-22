"""Build 1 m DEM + hillshade for every non-overlapping 3x3 mosaic available in data/files/.

Source: USGS_LPC_PA_WesternPA_2019_D20 (EPSG:6346, UTM 17N). Each LAZ tile is
1500 m on a side. Tiles are named ..._17T<P><F|G><E><N>.laz where E/N are 3-digit
codes whose UTM start is recovered from the sorted code index (every tile = +1500 m).

For every complete 3x3 block of present tiles aligned to the SW corner of the
discovered grid, we run a single PDAL pipeline that reads 9 LAZs -> merges ->
keeps Classification=2 (ground) -> delaunay -> faceraster (DEM), then runs
WhiteboxTools hillshade on the DEM.

Outputs go to data/derivatives/mosaic_3x3/<key>/ where <key> is the SW tile
code (e.g. 604590, 619593, ...). Files: dem_1m.tif, hillshade_1m.tif.

CLI:
  python notebooks/wellsight/build/_build_3x3_hillshades.py            # all complete blocks
  python notebooks/wellsight/build/_build_3x3_hillshades.py --pilot    # just first complete block
  python notebooks/wellsight/build/_build_3x3_hillshades.py --list     # enumerate, no work
  python notebooks/wellsight/build/_build_3x3_hillshades.py --skip-existing
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
SRC_DIR = ROOT / "data" / "files"
OUT_ROOT = ROOT / "data" / "derivatives" / "mosaic_3x3"
PDAL_EXE = shutil.which("pdal") or "pdal"
RES = 1.0
TILE_M = 1500.0
CRS = "EPSG:6346"

FNAME_RE = re.compile(
    r"^USGS_LPC_PA_WesternPA_2019_D20_17TP(?P<band>[FG])(?P<e>\d{3})(?P<n>\d{3})\.laz$"
)


def discover_tiles():
    """Return dict {(band, e_code, n_code): path} for plain .laz only (skip .copc.laz)."""
    found = {}
    for p in sorted(SRC_DIR.glob("USGS_LPC_PA_WesternPA_2019_D20_17T*.laz")):
        if ".copc." in p.name:
            continue
        m = FNAME_RE.match(p.name)
        if not m:
            continue
        found[(m["band"], m["e"], m["n"])] = p
    return found


def build_axis_index(codes):
    """Given the unique sorted 3-digit codes seen along one axis, return a
    dict code -> integer index where consecutive indices differ by 1500 m.

    Codes alternate +2,+1 (e.g. 604,606,607,609,...). We just sort numerically
    and assign sequential indices; the alternation is handled by the sort order
    because both half-km and full-km codes interleave correctly.
    """
    return {c: i for i, c in enumerate(sorted(codes))}


def utm_from_index(axis_min_m, idx):
    return axis_min_m + idx * TILE_M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true", help="only first block")
    ap.add_argument("--list", action="store_true", help="enumerate blocks and exit")
    ap.add_argument("--skip-existing", action="store_true")
    ap.add_argument("--only", help="comma-separated SW tile keys to process (e.g. 619593,604590)")
    args = ap.parse_args()

    tiles = discover_tiles()
    if not tiles:
        print("no LAZ tiles found in data/files/", file=sys.stderr)
        return 1
    print(f"discovered {len(tiles)} LAZ tiles")

    # Build a single shared easting and shared northing index across F+G bands.
    e_codes = sorted({k[1] for k in tiles})
    # Northings need band-aware indexing because F and G are spatially contiguous.
    # F codes: 590..599 ; G codes: 600..608. Stack F first, then G (band F is south).
    n_codes_f = sorted({k[2] for k in tiles if k[0] == "F"})
    n_codes_g = sorted({k[2] for k in tiles if k[0] == "G"})

    e_idx = {c: i for i, c in enumerate(e_codes)}
    n_idx = {}
    for i, c in enumerate(n_codes_f):
        n_idx[("F", c)] = i
    offset = len(n_codes_f)
    for i, c in enumerate(n_codes_g):
        n_idx[("G", c)] = offset + i

    # Pin axis origins to the lowest-indexed tile's UTM start. The lowest east
    # code's UTM start we anchor from the 9t calibration: code 619 -> 619500 m.
    # Walk back from 619 to e_codes[0].
    if "619" not in e_idx:
        print("calibration tile code '619' not in dataset; can't anchor easting", file=sys.stderr)
        return 1
    e_origin = 619500.0 - e_idx["619"] * TILE_M
    # Northing: 9t southmost tile north code is 593 (F) -> 4593000 m.
    if ("F", "593") not in n_idx:
        print("calibration tile (F,593) missing; can't anchor northing", file=sys.stderr)
        return 1
    n_origin = 4593000.0 - n_idx[("F", "593")] * TILE_M

    # Build an (ei, ni) -> (band, e_code, n_code, path) map
    grid = {}
    for (band, e, n), p in tiles.items():
        grid[(e_idx[e], n_idx[(band, n)])] = (band, e, n, p)

    # Non-overlapping 3x3 blocks anchored at (ei % 3 == 0, ni % 3 == 0). Origin
    # of the block index is the dataset's SW corner. That keeps blocks aligned
    # to a single global tessellation rather than wherever F/G boundaries fall.
    blocks = []
    max_ei = max(k[0] for k in grid)
    max_ni = max(k[1] for k in grid)
    for ei0 in range(0, max_ei + 1, 3):
        for ni0 in range(0, max_ni + 1, 3):
            members = []
            for de in range(3):
                for dn in range(3):
                    members.append(grid.get((ei0 + de, ni0 + dn)))
            if all(m is not None for m in members):
                sw = members[0]  # (de=0, dn=0)
                key = f"{sw[1]}{sw[2]}"  # SW tile e+n codes
                x0 = utm_from_index(e_origin, ei0)
                y0 = utm_from_index(n_origin, ni0)
                blocks.append({
                    "key": key,
                    "members": [m[3] for m in members],
                    "x0": x0, "y0": y0,
                    "x1": x0 + 3 * TILE_M, "y1": y0 + 3 * TILE_M,
                })

    blocks.sort(key=lambda b: (b["y0"], b["x0"]))
    print(f"complete 3x3 blocks: {len(blocks)}")
    for b in blocks:
        print(f"  {b['key']}  x={b['x0']:.0f}..{b['x1']:.0f}  y={b['y0']:.0f}..{b['y1']:.0f}")

    if args.list:
        return 0

    if args.only:
        keep = set(args.only.split(","))
        blocks = [b for b in blocks if b["key"] in keep]
        print(f"--only filter: {len(blocks)} block(s)")

    if args.pilot:
        blocks = blocks[:1]
        print(f"--pilot: running first block only ({blocks[0]['key'] if blocks else 'none'})")

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    import whitebox

    for b in blocks:
        out_dir = OUT_ROOT / b["key"]
        dem_tif = out_dir / "dem_1m.tif"
        hs_tif = out_dir / "hillshade_1m.tif"
        if args.skip_existing and dem_tif.exists() and hs_tif.exists():
            print(f"[{b['key']}] skip (outputs exist)")
            continue
        out_dir.mkdir(exist_ok=True)

        W = int(round((b["x1"] - b["x0"]) / RES))
        H = int(round((b["y1"] - b["y0"]) / RES))

        pipeline = {
            "pipeline": [
                *[str(p) for p in b["members"]],
                {"type": "filters.merge"},
                {"type": "filters.range", "limits": "Classification[2:2]"},
                {"type": "filters.delaunay"},
                {
                    "type": "filters.faceraster",
                    "resolution": RES,
                    "origin_x": b["x0"],
                    "origin_y": b["y0"],
                    "width": W,
                    "height": H,
                },
                {
                    "type": "writers.raster",
                    "filename": str(dem_tif),
                    "data_type": "float32",
                },
            ]
        }
        tmp = out_dir / "_tmp_dem_pipeline.json"
        tmp.write_text(json.dumps(pipeline, indent=2))

        print(f"[{b['key']}] DEM ({W}x{H}) from {len(b['members'])} tiles...")
        t0 = time.time()
        r = subprocess.run(
            [PDAL_EXE, "pipeline", str(tmp)],
            capture_output=True, text=True, timeout=3600,
        )
        if r.returncode != 0:
            print(f"[{b['key']}] PDAL FAILED rc={r.returncode}")
            print(r.stderr[-2000:])
            continue
        print(f"[{b['key']}] DEM ok in {time.time()-t0:.1f}s")
        tmp.unlink(missing_ok=True)

        wbt = whitebox.WhiteboxTools()
        wbt.set_working_dir(str(out_dir.resolve()))
        wbt.set_verbose_mode(False)
        rc = wbt.hillshade(
            dem="dem_1m.tif",
            output="hillshade_1m.tif",
            azimuth=315.0,
            altitude=45.0,
        )
        if rc != 0:
            print(f"[{b['key']}] WBT hillshade FAILED rc={rc}")
            continue
        print(f"[{b['key']}] hillshade ok -> {hs_tif}")

    print("\nDONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
