"""Every terrain derivative at once, on one 300 m square of ground.

The talk already shows these one slide at a time. This is the opening frame for
that run: the same patch of hillside rendered eleven ways, so the audience sees
what "terrain derivative" means before any one of them is discussed.

WHAT THE FIGURE HAS TO SAY, AND SAYS
------------------------------------
1. They are all the same ground. Identical window, identical extent, so the
   only thing changing between panels is the maths.
2. Only seven of them go into the model. The panel titles say which, read off
   the band descriptions of the feature stack rather than typed in, so the
   figure cannot disagree with what the network is actually fed.
3. Local relief is the one that mattered most for pits, which is what the
   slide's own caption claims, so it is called out rather than left to chance.

Styling is read from `qgis/wellsight.qgz` through `_build_derivative_panel`, so
these thumbnails and the full-slide versions of the same layers are the same
picture at different sizes.

Run:
    python docs/presentation/figures_30to45min/_build_derivative_overview.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.patches import FancyBboxPatch, Patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _build_derivative_panel import (  # noqa: E402
    D05, OUT, SIDE_M, draw_gray, draw_rgb, qgis_styles, read_window,
    style_for, window_bounds)

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"
ACCENT = "#1F5FA8"
TINT = "#eaf0f8"

#: Aerial imagery is not a derivative and needs the network, so the overview
#: leaves it out; the twelfth cell carries the key instead.
PANELS = [
    ("dem_9t_05.tif", "Bare-earth elevation", "dem"),
    ("hillshade_9t_05.tif", "Hillshade", "hillshade"),
    ("slope_9t_05.tif", "Slope", "slope"),
    ("lrm_5_9t_05.tif", "Local relief, 5 m", "lrm_5"),
    ("lrm_25_9t_05.tif", "Local relief, 25 m", "lrm_25"),
    ("tpi_05_9t_05.tif", "Topographic position", "tpi_05"),
    ("openness_pos_9t_05.tif", "Openness, positive", "openness_pos"),
    ("openness_neg_9t_05.tif", "Openness, negative", "openness_neg"),
    ("roughness_11_9t_05.tif", "Roughness", "roughness_11"),
    ("chm_9t_05.tif", "Canopy height", "chm"),
    ("rrim_openness_9t_05.tif", "RRIM", "rrim_openness"),
]


def stack_channels():
    """The bands the model is actually fed, from the stack itself."""
    p = D05 / "features_pit_9t_05.tif"
    if not p.exists():
        return set()
    with rasterio.open(p) as r:
        return {d for d in (r.descriptions or []) if d}


def main() -> int:
    bb = window_bounds()
    ext = [bb[0], bb[2], bb[1], bb[3]]
    styles = qgis_styles()
    chans = stack_channels()
    print(f"feature stack: {len(chans)} bands  {sorted(chans)}")

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(19.2, 8.2))
    gs = fig.add_gridspec(2, 6, left=0.012, right=0.988, top=0.775,
                          bottom=0.175, wspace=0.055, hspace=0.20)

    fig.text(0.012, 0.975, "One hillside, eleven ways of looking at it",
             fontsize=27, fontweight="bold", color=INK, va="top")
    fig.text(0.012, 0.895,
             f"The same {SIDE_M:.0f} m square of ground every time — only "
             f"the maths changes. Each one is drawn the way QGIS draws it, so "
             f"these are the layers as we\nactually work with them. Seven of "
             f"the eleven go into the model; the panel labels say which.",
             fontsize=13.5, color=INK2, va="top", linespacing=1.6)

    for i, (fname, title, slug) in enumerate(PANELS):
        ax = fig.add_subplot(gs[i // 6, i % 6])
        path = D05 / fname
        used = slug in chans
        if not path.exists():
            ax.text(0.5, 0.5, "missing", transform=ax.transAxes, ha="center",
                    va="center", color=MUTED, fontsize=11)
        else:
            arr = read_window(path, bb)
            st = style_for(path.stem, styles, path)
            if st["kind"] == "rgb":
                draw_rgb(ax, arr, st, ext)
            else:
                draw_gray(ax, arr[0] if arr.ndim == 3 else arr, st, ext)
            print(f"  {slug:14s} {st['kind']:4s} {st['source']:22s}"
                  f"{'  [in the model]' if used else ''}")
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_color(ACCENT if used else RULE)
            sp.set_linewidth(2.2 if used else 0.9)
        ax.set_title(title, fontsize=12.5,
                     fontweight="bold" if used else "normal",
                     color=INK if used else INK2, loc="left", pad=5)
        if used:
            # a word, not just a colour: the border alone is not an encoding
            # anyone can be expected to decode from the back of a room
            ax.text(0.985, 0.022, "in the model", transform=ax.transAxes,
                    fontsize=9.5, fontweight="bold", color="#ffffff",
                    ha="right", va="bottom", zorder=6,
                    bbox=dict(boxstyle="round,pad=0.22", fc=ACCENT, ec="none"))

    # twelfth cell: the key, rather than a gap
    ax = fig.add_subplot(gs[1, 5])
    ax.axis("off")
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.add_patch(FancyBboxPatch((1, 2), 98, 96,
                                boxstyle="round,pad=0.0,rounding_size=4",
                                facecolor=TINT, edgecolor=ACCENT,
                                linewidth=1.5))
    ax.text(8, 92, "Reading this", fontsize=13.5, fontweight="bold",
            color=INK, va="top")
    ax.text(8, 78,
            "A blue border and the\nlabel mark the seven\nchannels the U-Net "
            "is fed.\n\nThe other four are for\nlooking at. RRIM is what\nthe "
            "annotations sit on.",
            fontsize=11, color=INK2, va="top", linespacing=1.6)

    fig.text(0.012, 0.035,
             "Local relief subtracts a smoothed copy of the ground from "
             "itself, leaving the bumps and dips with the hillside taken out. "
             "It was the single most\nuseful input for finding pits, which is "
             "why it appears twice, at two different smoothing radii.",
             fontsize=12.5, color=INK, va="bottom", linespacing=1.6)

    p = OUT / "derivative_overview_eleven_channels_300m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"\n{p.stat().st_size/1e3:.0f} KB  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
