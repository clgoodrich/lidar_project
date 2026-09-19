"""Where does ground stop? Every map square in both surveys.

WHY A DIFFERENT STATISTIC
-------------------------
The rigorous version of this test conditions on returns that demonstrably
reached the ground, which needs `filters.hag_nn` and about 85 seconds a tile.
Across 258 map squares that is six hours, and the resulting 258-line chart is
spaghetti nobody can read.

This asks a blunter question that needs no height model at all:

    the widest angle at which GROUND points still exist
    the widest angle at which the survey recorded ANY point

If a survey simply gets less reliable towards the edge of its sweep, those two
numbers are close together -- ground thins out gradually and runs to the edge.
If somebody wrote a rule, ground stops dead while the data carries on past it,
and the gap between the two is the size of the discarded band.

One number per map square, no interpretation needed, and it runs on every tile
in both surveys rather than a sample of seven.

Only Classification and ScanAngle are read, so the cost is LAZ decompression.
Tiles are processed in parallel.

METHOD
------
laspy reads the tile directly; no PDAL stage is needed because nothing is being
computed per point. A bin counts only if it holds at least MIN_PTS points, so a
handful of strays cannot stretch either edge.

Run:
    python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_all_tiles.py
    ... --workers 6
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore", category=RuntimeWarning)

ROOT = Path(__file__).resolve().parents[3]
SRCROOT = ROOT / "data" / "_source" / "lidar"
CSV = ROOT / "data" / "9t" / "results" / "nonground_classification"

BIN = 0.5            # degrees
EDGES = np.arange(0, 40.0 + BIN, BIN)
MIN_PTS = 100        # a bin must hold this many to count as "reached"

AREAS = [("Venango", "westernpa"), ("McKean", "mckean")]


def tile_code(path):
    """The map-square code a source file covers."""
    m = re.search(r"(e\d+n\d+|17T..\d{6})", path.name)
    return m.group(1) if m else path.stem[-10:]


def unique_tiles(root):
    """One file per map square.

    Counting files instead of squares inflated every total in the first pass.
    Six squares under `westernpa` are on disk twice: four are byte-identical
    copies in `separate_sections/test_section/` (already flagged in
    `docs/_ledgers/duplicates_proposed_moves.csv`), and two are a `.copc.laz`
    cloud-optimised re-encoding sitting beside the plain `.laz` of the same
    tile. Either way the square is one square.

    Kept copy: the plain `.laz` over a `.copc.laz`, then the shallower path --
    the same order `tools/find_duplicates.py` uses.
    """
    best = {}
    for f in sorted(root.rglob("*.laz")):
        if f.name.startswith("_merged"):
            continue
        key = tile_code(f)
        rank = (f.name.endswith(".copc.laz"), len(f.relative_to(root).parts),
                str(f))
        if key not in best or rank < best[key][0]:
            best[key] = (rank, f)
    return [f for _, f in sorted(best.values(), key=lambda t: str(t[1]))]


def one_tile(args):
    """Widest angle with ground, widest angle with anything. One map square."""
    label, path = args
    import laspy
    try:
        las = laspy.read(str(path))
        cls = np.asarray(las.classification)
        for a in ("scan_angle", "scan_angle_rank"):
            if hasattr(las, a):
                v = np.asarray(getattr(las, a), dtype="float32")
                ang = np.abs(v * 0.006 if a == "scan_angle" else v)
                break
        else:
            return None
        gps = np.asarray(las.gps_time)
        flown = (datetime(1980, 1, 6) +
                 timedelta(seconds=float(gps.min()) + 1e9 - 18)).strftime("%Y-%m-%d")
        del las
    except Exception as e:
        return dict(area=label, tile=path.stem[-10:], error=str(e)[:80])

    g2 = cls == 2
    n_all, _ = np.histogram(ang, bins=EDGES)
    n_g2, _ = np.histogram(ang[g2], bins=EDGES)
    mid = 0.5 * (EDGES[:-1] + EDGES[1:])

    have_all = np.flatnonzero(n_all >= MIN_PTS)
    have_g2 = np.flatnonzero(n_g2 >= MIN_PTS)
    if have_all.size == 0 or have_g2.size == 0:
        return dict(area=label, tile=path.stem[-10:], error="too few points")

    data_stops = float(mid[have_all[-1]])
    ground_stops = float(mid[have_g2[-1]])
    return dict(
        area=label, tile=tile_code(path),
        flown=flown, points=int(cls.size),
        ground_pct=100 * float(g2.mean()),
        ground_stops=ground_stops, data_stops=data_stops,
        gap=data_stops - ground_stops,
        # how much of the survey's own sweep is barred to ground
        barred_pct=100 * (data_stops - ground_stops) / max(data_stops, 1e-9),
        pts_beyond=int(n_all[have_g2[-1] + 1:].sum()),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    CSV.mkdir(parents=True, exist_ok=True)

    jobs = []
    for label, sub in AREAS:
        files = unique_tiles(SRCROOT / sub)
        if args.limit:
            files = files[:args.limit]
        print(f"{label:9s} {len(files)} map squares")
        jobs += [(label, f) for f in files]

    rows, done = [], 0
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(one_tile, j): j for j in jobs}
        for fu in as_completed(futs):
            r = fu.result()
            done += 1
            if r:
                rows.append(r)
            if done % 20 == 0 or done == len(jobs):
                print(f"  {done}/{len(jobs)}")

    df = pd.DataFrame(rows)
    bad = df[df.get("error").notna()] if "error" in df else df.iloc[0:0]
    if len(bad):
        print(f"\n{len(bad)} tiles failed to read")
    df = df[df.get("error").isna()] if "error" in df else df
    df = df.sort_values(["area", "tile"])
    df.to_csv(CSV / "scan_angle_ground_stops_all_tiles.csv", index=False)

    line = "=" * 74
    print(f"\n{line}\nWHERE GROUND STOPS, EVERY MAP SQUARE\n{line}")
    print(f"  {'survey':9s} {'squares':>8s} {'ground stops':>21s} "
          f"{'data stops':>19s} {'gap':>14s}")
    print(f"  {'':9s} {'':>8s} {'median':>10s} {'range':>10s} "
          f"{'median':>9s} {'range':>9s} {'median':>7s} {'max':>6s}")
    for a, g in df.groupby("area"):
        print(f"  {a:9s} {len(g):>8d} {g.ground_stops.median():>10.2f} "
              f"{g.ground_stops.min():>4.1f}-{g.ground_stops.max():<5.1f} "
              f"{g.data_stops.median():>9.2f} "
              f"{g.data_stops.min():>4.1f}-{g.data_stops.max():<4.1f} "
              f"{g.gap.median():>7.2f} {g.gap.max():>6.2f}")

    print(f"\n  A gap near zero means ground runs all the way to the edge of "
          f"the sweep.\n  A gap of two degrees means ground stops dead while "
          f"the survey keeps recording.\n")
    for a, g in df.groupby("area"):
        big = g[g.gap >= 1.0]
        print(f"  {a}: {len(big)} of {len(g)} squares have a gap of 1 degree "
              f"or more ({100*len(big)/len(g):.0f}%)")
        if len(big):
            print(f"      those squares hold {int(big.pts_beyond.sum()):,} "
                  f"points past the point where ground stops")
    print(f"\nwrote {CSV / 'scan_angle_ground_stops_all_tiles.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
