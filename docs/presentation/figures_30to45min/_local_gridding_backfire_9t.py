"""Local gridding on the RRIM: triangulated against averaged. No scores.

WHY NOT REUSE destripe_dem_mean_radius_9t.png
---------------------------------------------
That figure labels each panel with a spike-prominence ratio ("RRIM spike
x0.84", "x2.00"). Those numbers are not quotable: the metric is window-size
dependent -- the same raster at the same place scored x3.70 in a 90 m window
and x0.84 in a 600 m one -- so a reader comparing them across figures, or
against anything else in the deck, would be comparing nothing. Its title and
subtitle also overlap, and the panel labels clip.

This shows the same comparison with the claim the slide actually makes and
nothing else: triangulating between the points, against averaging them in a
disc, on the layer where it matters. The starbursts around trees in the right
panel are the whole point, and they need no number.

Two panels, not four. Radius 1.5 m is the best of the averaged three, so
showing it rather than the 0.75 m disaster is the conservative choice -- it
makes the weaker case for my own conclusion.

COLOUR
------
Both panels are RRIM composites rendered as raw RGB, exactly as the QGIS
project does. The Chiba ramp runs red to cyan-grey with no green carrying a
separate meaning, so the CLAUDE.md red/green pair rule is not engaged.

Run:
    python docs/presentation/figures_30to45min/_local_gridding_backfire_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/local_gridding_backfire_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
SPOT = ROOT / "data/9t/derived/destripe_spot"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "local_gridding_backfire_9t.png")

#: The destripe run saved a RRIM for each AVERAGED surface but not for the
#: triangulated one, so the left panel comes from the production RRIM cropped
#: to the same window. That IS the triangulated build at 0.5 m -- same recipe,
#: same cells -- so it is the honest left-hand side. Falling back to the DEM
#: instead, as a first version did, compared a raw elevation raster against a
#: RRIM and was not a comparison at all.
PROD_RRIM = ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif"
MEAN = "rrim_mean_r1p5_spot_9t_0p5m.tif"
TITLES = [("Triangulated between the points", "what we build now"),
          ("Averaged in a 1.5 m disc", "what local gridding does")]

INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


def read_rgb_window(path, b):
    """Same as read_rgb, cropped to another raster's bounds."""
    from rasterio.windows import from_bounds
    with rasterio.open(path) as s:
        a = s.read(window=from_bounds(*b, transform=s.transform),
                   boundless=True, fill_value=0)
    a = a[:3].astype("float32")
    if a.max() > 1.5:
        a /= 255.0
    return np.clip(np.moveaxis(a, 0, -1), 0, 1)


def read_rgb(path):
    with rasterio.open(path) as s:
        a = s.read()
    if a.shape[0] < 3:                       # single band -> grey composite
        b = a[0].astype("float32")
        lo, hi = np.nanpercentile(b, (2, 98))
        b = np.clip((b - lo) / max(hi - lo, 1e-9), 0, 1)
        return np.dstack([b, b, b])
    a = a[:3].astype("float32")
    if a.max() > 1.5:
        a /= 255.0
    return np.clip(np.moveaxis(a, 0, -1), 0, 1)


def main() -> int:
    mean_p = SPOT / MEAN
    if not (mean_p.exists() and PROD_RRIM.exists()):
        raise SystemExit(f"missing: {mean_p if not mean_p.exists() else PROD_RRIM}")
    # The destripe window runs 122 m past the tile's eastern edge at 624000,
    # so the production RRIM has nothing there. Crop BOTH panels to the
    # overlap, or the left one carries a black band the right one does not and
    # the two stop being the same ground.
    with rasterio.open(mean_p) as s:
        mb = s.bounds
    with rasterio.open(PROD_RRIM) as s:
        pb = s.bounds
    b = (max(mb.left, pb.left), max(mb.bottom, pb.bottom),
         min(mb.right, pb.right), min(mb.top, pb.top))
    imgs = [read_rgb_window(PROD_RRIM, b), read_rgb_window(mean_p, b)]

    fig, axes = plt.subplots(1, 2, figsize=(13.4, 7.1))
    fig.patch.set_facecolor(PAPER)
    for ax, img, (title, sub) in zip(axes, imgs, TITLES):
        ax.imshow(img)
        ax.set_title(f"{title}\n{sub}", loc="left", fontsize=16,
                     fontweight="bold", color=INK, pad=10)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")

    fig.suptitle("Averaging smooths the heights and roughens the shape",
                 x=0.008, y=0.985, ha="left", va="top", fontsize=21,
                 fontweight="bold", color=INK)
    fig.text(0.008, 0.045,
             "Same ground, same 0.5 m cells, same RRIM recipe. Only the way "
             "the points become a surface changes. Every tree in the right "
             "panel has grown a starburst.",
             fontsize=11.5, color=MUTED)
    fig.tight_layout(rect=(0, 0.065, 1, 0.945))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=160, facecolor=PAPER)
    plt.close(fig)
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
