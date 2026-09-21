"""Two stripes, one nickname. One is empty cells; the other is measured ground.

THE DISTINCTION THIS FIGURE MAKES
---------------------------------
"Corn rows" has been used for two different things in this project, and
conflating them led the deck to offer a fix for one as though it fixed both.

  canopy height (CHM/DSM)   the stripes are LITERALLY EMPTY CELLS. No first
                            return came back, so there is nothing to draw.
                            A grid-size artefact: the half-metre grid asks for
                            more detail than the survey delivered.
                            2.044% of cells at 0.5 m -> 0.029% at 1 m. Fixed.

  RRIM / LRM / openness     the stripes sit in a surface with NO empty cells
                            at all. The DEM is 0.000% void at 0.5 m AND at
                            1 m, because the triangulation spans every gap.
                            So this cannot be missing data. It is structure in
                            the measurements themselves, and coarsening only
                            REDUCES it.

Whole-tile void, measured over the full 9000x9000 and 4500x4500 rasters:

    DEM  0.5 m  0.000%      DEM  1 m  0.000%
    DSM  0.5 m  2.044%      DSM  1 m  0.029%
    CHM  0.5 m  2.044%      CHM  1 m  0.029%

That DEM row is the whole argument. A layer that never has a hole still
stripes.

WINDOW
------
623822 E 4594949 N, 240 m -- the spot the RRIM striping was reported at by eye,
so the right-hand panel is showing the phenomenon at its reported location
rather than somewhere chosen to help.

COLOUR
------
NoData is #D97706, the repo's validated orange (worst pair dE 21.1 deutan,
22.6 normal against #1F5FA8). Canopy is a single-hue grey ramp; RRIM is its own
composite. Nothing green carries a meaning, so the red/green pair rule is not
engaged, and the NoData cells are labelled as well as coloured.

Run:
    python docs/presentation/figures_30to45min/_two_kinds_of_corn_rows_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/two_kinds_of_corn_rows_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import Patch
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
CHM = ROOT / "data/9t/derived/05/chm_9t_05.tif"
RRIM = ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "two_kinds_of_corn_rows_9t.png")

CX, CY = 623822.4, 4594948.6
SIDE = 240.0

NODATA = "#D97706"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def window(path, b, bands=None):
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(indexes=bands, window=w, boundless=True,
                   fill_value=s.nodata if s.nodata is not None else np.nan)
        nd = s.nodata
    return a, nd


def main() -> int:
    h = SIDE / 2.0
    b = (CX - h, CY - h, CX + h, CY + h)

    chm, nd = window(CHM, b, bands=1)
    chm = chm.astype("float32")
    void = np.isnan(chm) if nd is None else ((chm == nd) | np.isnan(chm))

    rr, _ = window(RRIM, b)
    rr = rr[:3].astype("float32")
    if rr.max() > 1.5:
        rr /= 255.0
    rr = np.clip(np.moveaxis(rr, 0, -1), 0, 1)

    fig, axes = plt.subplots(1, 2, figsize=(13.6, 7.2))
    fig.patch.set_facecolor(PAPER)

    ax = axes[0]
    lo, hi = np.nanpercentile(chm[~void], (2, 98)) if (~void).any() else (0, 1)
    ax.imshow(np.where(void, np.nan, chm), cmap="gray", vmin=lo, vmax=hi)
    # paint the empty cells on top, so they are unmistakably the subject
    mask = np.zeros(chm.shape + (4,), dtype="float32")
    rgba = matplotlib.colors.to_rgba(NODATA)
    mask[void] = rgba
    ax.imshow(mask)
    ax.set_title("Canopy height, 0.5 m\nthe stripes are empty cells",
                 loc="left", fontsize=16, fontweight="bold", color=INK, pad=10)
    ax.set_xlabel(f"{void.mean()*100:.1f}% of cells have no value",
                  fontsize=14, color=NODATA, fontweight="bold")
    ax.legend(handles=[Patch(facecolor=NODATA, label="no data")],
              loc="upper right", fontsize=12, framealpha=0.92)

    ax = axes[1]
    ax.imshow(rr)
    ax.set_title("RRIM, 0.5 m, same ground\nthe stripes are measured surface",
                 loc="left", fontsize=16, fontweight="bold", color=INK, pad=10)
    ax.set_xlabel("0.0% of cells have no value",
                  fontsize=14, color=MUTED, fontweight="bold")

    for ax in axes:
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("Two different stripes, one nickname",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=22,
                 fontweight="bold", color=INK)
    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.095, 1, 0.945))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=PAPER)
    plt.close(fig)
    print(f"  CHM void in window: {void.mean()*100:.2f}%")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
