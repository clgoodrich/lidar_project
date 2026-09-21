"""The corn-row window in four layers. Images only, no annotation.

The RRIM slide asserts that the stripes appear "in every layer built from
shape". This shows it instead: the same 240 m window, at the same 0.5 m cells,
rendered as hillshade, LRM, negative openness and slope.

No titles inside the panels beyond the layer name, no arrows, no callouts. The
slide it sits on carries no text either -- the point is to let the room look.

Each layer is stretched on its own 2-98 percentile, which is how the QGIS
project renders these, so each panel looks the way it does on screen rather
than being pushed to make a point.

COLOUR
------
All four are single-hue grey ramps, black to white, matching the project
convention for single-band layers. No colour carries meaning, so the red/green
rule is not engaged.

Run:
    python docs/presentation/figures_30to45min/_cornrow_four_layers_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/cornrow_four_layers_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "cornrow_four_layers_9t.png")

#: the same window the RRIM corn-row figure uses, so the slides line up
CX, CY = 623822.4, 4594948.6
#: landscape, not square. Four square panels in a 2x2 make a figure of
#: ratio ~1.0, which on a 16:9 slide leaves a third of the width empty.
#: A 16:9 window makes the 2x2 grid itself roughly 16:9, so the slide
#: fills edge to edge.
WIN_W, WIN_H = 320.0, 180.0

PANELS = [
    ("hillshade_9t_05.tif", "Hillshade"),
    ("lrm_5_9t_05.tif", "Local relief"),
    ("openness_neg_9t_05.tif", "Openness, negative"),
    ("slope_9t_05.tif", "Slope"),
]

INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read(path, b):
    with rasterio.open(path) as s:
        a = s.read(1, window=from_bounds(*b, transform=s.transform),
                   boundless=True,
                   fill_value=s.nodata if s.nodata is not None else np.nan)
        nd = s.nodata
    a = a.astype("float32")
    if nd is not None:
        a[a == nd] = np.nan
    return a


def main() -> int:
    missing = [n for n, _ in PANELS if not (D05 / n).exists()]
    if missing:
        raise SystemExit("missing layers:\n  " + "\n  ".join(missing))

    b = (CX - WIN_W / 2, CY - WIN_H / 2, CX + WIN_W / 2, CY + WIN_H / 2)

    fig, axes = plt.subplots(2, 2, figsize=(14.2, 8.6))
    fig.patch.set_facecolor(PAPER)
    for ax, (name, label) in zip(axes.ravel(), PANELS):
        a = read(D05 / name, b)
        lo, hi = np.nanpercentile(a, (2, 98))
        ax.imshow(a, cmap="gray", vmin=lo, vmax=hi)
        ax.set_title(label, loc="left", fontsize=17, fontweight="bold",
                     color=INK, pad=8)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    # No caption baked into the image: explanatory text belongs in the
    # slide's own left-hand column, not burned into the PNG where it
    # cannot be edited, re-wrapped or read at presentation size.
    fig.tight_layout(rect=(0, 0.028, 1, 1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
