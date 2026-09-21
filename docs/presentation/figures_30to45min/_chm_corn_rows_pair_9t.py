"""The canopy-height corn rows, in two steps: what you see, then what they are.

WHY TWO FIGURES
---------------
The canopy-height story is now told on its own two slides and nowhere else, so
it needs two images that work in sequence rather than one that argues both
halves at once:

  1  chm_corn_rows_05_9t.png
     Canopy height at 0.5 m, plain. The stripes are obvious and nothing is
     annotated. This is the "look at this" slide -- let the room notice them
     before being told what they are.

  2  chm_corn_rows_are_empty_cells_9t.png
     The same window twice. Left: 0.5 m with the cells that hold no value
     painted orange, which lands exactly on the stripes. Right: 1 m, where
     they are gone. This is the "here is what they are" slide.

Nothing here mentions the RRIM. The RRIM stripes are a different phenomenon
with a different cause and they are dealt with on their own slides; mixing the
two is what made the earlier version of this section misleading.

WINDOW
------
621359.6 E 4594467.4 N, 300 m -- the window the terrain-derivative panels all
use, so canopy height lines up with slope, openness and the rest.

COLOUR
------
Canopy is a single-hue grey ramp. No-data is #D97706, the repo's validated
orange (worst pair dE 21.1 deutan, 22.6 normal against #1F5FA8). Nothing green
carries a meaning here, so the red/green pair rule is not engaged, and the
no-data cells carry a legend entry as well as a colour.

Run:
    python docs/presentation/figures_30to45min/_chm_corn_rows_pair_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/chm_corn_rows_05_9t.png
    docs/presentation/figures_30to45min/v6/chm_corn_rows_are_empty_cells_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Patch
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
OUTDIR = ROOT / "docs/presentation/figures_30to45min/v6"
SRC = {0.5: ROOT / "data/9t/derived/05/chm_9t_05.tif",
       1.0: ROOT / "data/9t/derived/1m/chm_9t_1m.tif"}

CX, CY = 621359.6, 4594467.4
SIDE = 300.0

NODATA = "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read(path, b):
    with rasterio.open(path) as s:
        a = s.read(1, window=from_bounds(*b, transform=s.transform),
                   boundless=True,
                   fill_value=s.nodata if s.nodata is not None else np.nan)
        nd = s.nodata
    a = a.astype("float32")
    void = np.isnan(a) if nd is None else ((a == nd) | np.isnan(a))
    return a, void


def grey(ax, a, void, lo, hi):
    ax.imshow(np.where(void, np.nan, a), cmap="gray", vmin=lo, vmax=hi)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_edgecolor("#c8c8c0")


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)
    a05, v05 = read(SRC[0.5], b)
    a1, v1 = read(SRC[1.0], b)
    lo, hi = np.nanpercentile(a05[~v05], (2, 98))

    OUTDIR.mkdir(parents=True, exist_ok=True)

    # ---- 1. plain, unannotated -----------------------------------------
    fig, ax = plt.subplots(figsize=(9.6, 9.9))
    fig.patch.set_facecolor(PAPER)
    grey(ax, a05, v05, lo, hi)
    ax.set_title("Canopy height, 0.5 m cells", loc="left", fontsize=21,
                 fontweight="bold", color=INK, pad=12)
    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.045, 1, 1))
    p1 = OUTDIR / "chm_corn_rows_05_9t.png"
    fig.savefig(p1, dpi=165, facecolor=PAPER)
    plt.close(fig)

    # ---- 2. the same cells, named --------------------------------------
    fig, axes = plt.subplots(1, 2, figsize=(13.6, 7.3))
    fig.patch.set_facecolor(PAPER)

    grey(axes[0], a05, v05, lo, hi)
    mask = np.zeros(a05.shape + (4,), dtype="float32")
    mask[v05] = matplotlib.colors.to_rgba(NODATA)
    axes[0].imshow(mask)
    axes[0].set_title("0.5 m cells", loc="left", fontsize=17,
                      fontweight="bold", color=INK, pad=9)
    axes[0].set_xlabel(f"{v05.mean()*100:.2f}% of cells hold no value",
                       fontsize=14, color=NODATA, fontweight="bold")
    axes[0].legend(handles=[Patch(facecolor=NODATA, label="no data")],
                   loc="upper right", fontsize=12, framealpha=0.92)

    grey(axes[1], a1, v1, lo, hi)
    mask1 = np.zeros(a1.shape + (4,), dtype="float32")
    mask1[v1] = matplotlib.colors.to_rgba(NODATA)
    axes[1].imshow(mask1)
    axes[1].set_title("1 m cells", loc="left", fontsize=17,
                      fontweight="bold", color=INK, pad=9)
    axes[1].set_xlabel(f"{v1.mean()*100:.2f}% of cells hold no value",
                       fontsize=14, color=MUTED, fontweight="bold")

    fig.suptitle("The stripes are cells with nothing in them",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=22,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.075, 1, 0.945))
    p2 = OUTDIR / "chm_corn_rows_are_empty_cells_9t.png"
    fig.savefig(p2, dpi=160, facecolor=PAPER)
    plt.close(fig)

    print(f"  0.5 m void in window {v05.mean()*100:.2f}%   "
          f"1 m void {v1.mean()*100:.2f}%")
    for p in (p1, p2):
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
