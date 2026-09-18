"""Sniff test: are points being withheld from class 2 that ought to be ground?

RESULT SUPERSEDED, 2026-09-18
-----------------------------
This screen raised a real flag and pointed at the wrong conclusion. It found that
non-ground points inside annotated pit floors are 2.6x more likely to sit below
the ground surface than elsewhere, which looked like the ground classifier
bridging over our pits.

It is not. `_reclaim_ground_pit_depth_experiment.py` tested that directly on 216
annotated floors across four tiles at full density: ground density inside floors
is 92% of the surrounding ring, none of the 216 floors is empty of class 2, and
reclaiming every withheld point below the surface changes the median pit depth by
0.000 m. The share was large because the denominator -- non-ground points inside a
pit floor -- is small.

Keep running this as a screen on new deliveries. Do not quote its pit ratio as
evidence of anything. See `docs/iterations/ground_reclassification_pit_depth.md`.

WHY ASK
-------
Every terrain product in this project is built from the ground-classified
returns. If the vendor's classifier is systematically dropping real ground --
inside pits, under dense canopy, on steep banks -- then a pit floor is shallower
than it really is, and the model is learning a damped version of the signal.

THE TEST
--------
For each non-ground point, compute its height above the ground surface built
from the class-2 returns (PDAL `filters.hag_nn`, nearest-ground-neighbour). A
non-ground point sitting essentially ON that surface is suspicious: it is either
real ground the classifier passed over, or a low object. The distribution of how
many there are, and which classes they sit in, is the sniff.

This is a screen, not a proof. A point 4 cm above the ground surface could be a
rock, a log, or a stray return. What matters is the SHARE, how it varies by
class, and whether it clusters anywhere spatial.

METHOD
------
PDAL CLI via subprocess with a pipeline JSON -- the Python bindings do not
function in this environment (CLAUDE.md).

    readers.las -> filters.decimation -> filters.hag_nn -> writers.las

then the decimated copy is read with laspy and analysed in numpy. Decimation is
for speed only; it does not bias the height calculation, which is computed
before the sample is written.

Run:
    python notebooks/wellsight_v2/s7_analysis/_sniff_ground_classification_9t.py
    ... --laz <path> --step 5 --near 0.15
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "data" / "_source" / "lidar" / "westernpa"
DEFAULT_LAZ = SRC / "USGS_LPC_PA_WesternPA_2019_D20_17TPF621597.laz"
PDAL = "pdal"

#: ASPRS classes, as they appear in USGS 3DEP deliveries.
ASPRS = {
    0: "never classified", 1: "unassigned", 2: "ground",
    3: "low vegetation", 4: "medium vegetation", 5: "high vegetation",
    6: "building", 7: "low point (noise)", 8: "reserved", 9: "water",
    10: "rail", 11: "road surface", 12: "overlap", 13: "wire guard",
    14: "wire conductor", 15: "transmission tower", 17: "bridge deck",
    18: "high noise",
}


def run_pipeline(stages, label):
    """Write the pipeline to a temp file and shell out. See CLAUDE.md."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump({"pipeline": stages}, f, indent=2)
        tmp = f.name
    r = subprocess.run([PDAL, "pipeline", tmp], capture_output=True, text=True)
    Path(tmp).unlink(missing_ok=True)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        raise SystemExit(f"{label} failed, exit {r.returncode}")
    return r


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--laz", default=str(DEFAULT_LAZ))
    ap.add_argument("--step", type=int, default=5,
                    help="decimation: keep 1 point in N")
    ap.add_argument("--near", type=float, default=0.15,
                    help="metres above the ground surface to call 'on the ground'")
    args = ap.parse_args()

    laz = Path(args.laz)
    if not laz.exists():
        raise SystemExit(f"missing {laz}")
    print(f"source : {laz.name}  ({laz.stat().st_size/1e6:.0f} MB)")
    print(f"params : decimate 1-in-{args.step}, near-ground < {args.near} m\n")

    out = Path(tempfile.gettempdir()) / f"_sniff_{laz.stem}.las"
    run_pipeline([
        {"type": "readers.las", "filename": str(laz)},
        {"type": "filters.decimation", "step": args.step},
        # hag_nn measures each point against the nearest GROUND returns, so it
        # is unaffected by how the non-ground points are classified.
        {"type": "filters.hag_nn", "count": 8, "allow_extrapolation": True},
        {"type": "writers.las", "filename": str(out),
         "extra_dims": "HeightAboveGround=float32", "compression": "false"},
    ], "hag")

    import laspy
    las = laspy.read(str(out))
    cls = np.asarray(las.classification)
    hag = np.asarray(las.HeightAboveGround, dtype="float64")
    n = cls.size
    print(f"sampled {n:,} points\n")

    print("classification breakdown")
    print(f"  {'code':>4}  {'class':22s} {'points':>12s}  {'share':>7s}")
    for c in sorted(np.unique(cls)):
        m = cls == c
        print(f"  {c:>4}  {ASPRS.get(int(c), '?'):22s} {int(m.sum()):12,d}  "
              f"{100*m.mean():6.2f}%")

    ground = cls == 2
    nonground = ~ground
    print(f"\nground {int(ground.sum()):,} ({100*ground.mean():.1f}%)   "
          f"non-ground {int(nonground.sum()):,} ({100*nonground.mean():.1f}%)")

    # --- the sniff --------------------------------------------------------
    finite = np.isfinite(hag)
    near = nonground & finite & (np.abs(hag) < args.near)
    print(f"\nNON-GROUND POINTS SITTING ON THE GROUND SURFACE (|HAG| < "
          f"{args.near} m)")
    print(f"  {int(near.sum()):,} points = {100*near.sum()/max(nonground.sum(),1):.2f}%"
          f" of non-ground, {100*near.sum()/n:.2f}% of all points\n")

    print(f"  {'code':>4}  {'class':22s} {'non-ground':>12s} {'near-ground':>12s}"
          f" {'share':>7s}")
    rows = []
    for c in sorted(np.unique(cls[nonground])):
        m = (cls == c) & nonground & finite
        k = m & (np.abs(hag) < args.near)
        if not m.sum():
            continue
        share = 100 * k.sum() / m.sum()
        rows.append((int(c), int(m.sum()), int(k.sum()), share))
        print(f"  {c:>4}  {ASPRS.get(int(c), '?'):22s} {int(m.sum()):12,d} "
              f"{int(k.sum()):12,d} {share:6.2f}%")

    # --- how far below the surface do non-ground points go? ---------------
    below = nonground & finite & (hag < -0.05)
    print(f"\nNON-GROUND POINTS BELOW THE GROUND SURFACE (HAG < -0.05 m)")
    print(f"  {int(below.sum()):,} points = "
          f"{100*below.sum()/max(nonground.sum(),1):.2f}% of non-ground")
    if below.sum():
        q = np.percentile(hag[below], [50, 25, 10, 1])
        print(f"  median {q[0]:+.2f} m, 25th {q[1]:+.2f}, 10th {q[2]:+.2f}, "
              f"1st {q[3]:+.2f}")
        print("  A point BELOW the ground surface is either real ground the "
              "classifier missed,\n  or noise. Class 7 is the vendor's own "
              "noise flag -- compare the two.")

    # --- height distribution of the low non-ground points -----------------
    print(f"\nHEIGHT DISTRIBUTION, non-ground points under 2 m")
    lo = nonground & finite & (hag < 2.0) & (hag > -1.0)
    if lo.sum():
        edges = [-1.0, -0.15, -0.05, 0.05, 0.15, 0.30, 0.50, 1.0, 2.0]
        h, _ = np.histogram(hag[lo], bins=edges)
        for i in range(len(edges) - 1):
            bar = "#" * int(60 * h[i] / max(h.max(), 1))
            print(f"  {edges[i]:+5.2f} to {edges[i+1]:+5.2f} m  "
                  f"{h[i]:9,d}  {bar}")

    print("\nREAD IT LIKE THIS")
    print("  A few percent of non-ground points within 15 cm of the surface is "
          "normal -- rocks,\n  logs, stumps and low returns are genuinely not "
          "ground.")
    print("  A LARGE share, or a large share concentrated in class 1 "
          "(unassigned), suggests the\n  classifier gave up rather than "
          "decided, and real ground is being withheld.")
    out.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
