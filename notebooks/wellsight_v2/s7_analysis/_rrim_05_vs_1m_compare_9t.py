"""RRIM at 0.5 m against 1 m, over the three windows that matter.

WHY THIS EXISTS
---------------
The corn rows are visible on the RRIM, so the obvious move is to rebuild the
RRIM at 1 m. `_stripe_strength_by_layer_9t.py` says that will not work, and this
draws the two side by side so the claim can be checked by eye rather than taken
from a table.

WHAT THE MEASUREMENT SAYS, AND WHY IT CHANGES THE DIAGNOSIS
-----------------------------------------------------------
Directional power at each bearing, the peak bearing named:

                        corduroy    worst void   flight seam
  DSM      0.5 m        78 deg       78 deg        144 deg
                        x5.3         x28.4         x1.8
  RRIM     0.5 m        120 deg      147 deg       168 deg
                        x2.0         x2.4          x3.1
  slope    0.5 m -> 1 m 2.58 -> 2.73  3.45 -> 3.64  4.26 -> 5.45
  op_neg   0.5 m -> 1 m 1.47 -> 1.47  2.21 -> 2.49  3.53 -> 3.93

Two things fall out.

THE CORN ROWS ARE A DSM PROBLEM, NOT AN RRIM ONE. The DSM striping at the
scan-line bearing is enormous -- 28x in the worst window. The RRIM shows 0.96 at
that same bearing, which is no preference at all. The RRIM is built from slope
and openness, both of which come from the DEM, and the DEM is a Delaunay TIN
with no voids. The corn rows never enter it.

WHAT IS ON THE RRIM RUNS THE OTHER WAY. Its grain peaks at 120 to 168 degrees,
strongest at 168 in the seam window. The flight bearing is 355.8, which is 176
modulo 180. So the RRIM's grain runs ALONG THE FLIGHT LINES, not across them --
the signature of a flight-line registration step, where two passes disagree
slightly about the ground and slope and openness amplify the edge.

AND COARSENING DOES NOT TOUCH IT. Every 1 m ratio equals or exceeds its 0.5 m
counterpart. A metre-scale step between passes is not a sub-metre sampling gap,
so a bigger cell cannot help; if anything the smoothing sharpens the step
relative to the texture around it.

DO NOT READ A HIGH RATIO AS A DEFECT ON ITS OWN. The DEM scores 17x at 3 degrees
in the corduroy window, and that is the hillside. Only two comparisons carry
meaning: the same layer at two resolutions, and the scan-line bearing against
the median bearing in the same raster.

Run:
    python notebooks/wellsight_v2/s7_analysis/_rrim_05_vs_1m_compare_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/rrim_05_vs_1m_9t.png
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

RRIM_05 = ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif"
RRIM_1M = ROOT / "data/9t/derived/1m/rrim_openness_9t_1m.tif"

#: Three windows, each chosen for a reason rather than by eye.
#:   corduroy    the CHM panel's own square, where the corn rows live
#:   worst void  the 300 m square holding the most DSM void, found by a
#:               summed-area scan over the 5 m void grid
#:   seam        a square straddling a flight-line edge
WINDOWS = [
    ("The corn-row window", (621209.6, 4594317.4, 621509.6, 4594617.4)),
    ("Worst DSM void", (621520.0, 4593725.0, 621820.0, 4594025.0)),
    ("A flight-line seam", (621600.0, 4595000.0, 621900.0, 4595300.0)),
]

SCAN_BRG, FLIGHT_BRG = 78.0, 176.0
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read_rgb(path, b):
    with rasterio.open(path) as r:
        a = r.read(window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=255).astype("uint8")
    return np.moveaxis(a[:3], 0, -1)


def main() -> int:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, len(WINDOWS),
                             figsize=(4.9 * len(WINDOWS), 10.6))
    fig.patch.set_facecolor(PAPER)

    for col, (name, b) in enumerate(WINDOWS):
        for row, (label, path) in enumerate((("0.5 m", RRIM_05),
                                             ("1 m", RRIM_1M))):
            ax = axes[row][col]
            ax.imshow(read_rgb(path, b), interpolation="nearest")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_edgecolor("#c8c8c0")
            if row == 0:
                ax.set_title(name, loc="left", fontsize=14,
                             fontweight="bold", color=INK)
            ax.set_ylabel(label, fontsize=13, fontweight="bold", color=INK)

    for col, (name, b) in enumerate(WINDOWS):
        axes[1][col].set_xlabel(f"{int(b[2]-b[0])} m  ·  "
                                f"{b[0]:.0f} E {b[1]:.0f} N",
                                fontsize=11, color=MUTED)

    fig.suptitle("RRIM at both resolutions — the grain runs with the "
                 "flight lines, not the scan lines",
                 x=0.012, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    # the subtitle needs its own line; at y=0.955 it sat on the title
    fig.text(0.012, 0.945,
             f"scan lines {SCAN_BRG:.0f}° (the corn rows)   ·   "
             f"flight lines {FLIGHT_BRG:.0f}°   ·   "
             "RRIM peaks at 120–168° in every window, and 1 m does "
             "not reduce it",
             fontsize=12, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.925))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "rrim_05_vs_1m_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
