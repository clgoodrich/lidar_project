# -*- coding: utf-8 -*-
"""A small key showing which blocks were train, validation and test.

WHY A KEY AND NOT A REDRAW
--------------------------
The outcome slides carry probability maps the reader can already see the block
grid in, and those maps are not being replaced. This is a separate, small
figure that sits in the margin beside them, drawn on exactly the same extent
and the same orientation, so a reader can look across from a block on the map
to the same block here and read off which pile it came from.

    train  100 blocks
    val     22
    test    22
    total  144, a 12 by 12 grid over 9t

Read from data/9t/derived/05/blocks_unified_9t.gpkg, which is the split every
task shares, so the key cannot drift from what the models were actually
trained on.

EXTENT MUST MATCH, AND IS ASSERTED
----------------------------------
The key is only useful if it lines up with the map beside it. The block table's
total bounds are checked against the 9t bounding box and the script stops if
they differ, rather than quietly producing a key that points at the wrong
squares.

COLOUR, AND THE SECOND ENCODING
-------------------------------
The validated trio from CLAUDE.md: train #1F5FA8, val #D97706, test #A31515.
Worst pair dE 21.1 deutan, 22.6 normal. No green, so no red/green pair.

Blue against dark red is the weakest pair here at small size, so each category
also carries a hatch: train plain, val diagonal, test crossed. That is a second
encoding, so the key still reads with no colour at all, which matters more than
usual for a figure printed at 1.6 inches.

ALSO WRITTEN
------------
blocks_by_split_9t.gpkg, the same thing as a vector layer, for dropping over a
probability raster in QGIS when the printed key is too small to settle a
question.

Run:
    python docs/presentation/figures_30to45min/_block_split_key_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/block_split_key_9t.png
    data/9t/derived/05/blocks_by_split_9t.gpkg
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[3]
BLOCKS = ROOT / "data/9t/derived/05/blocks_unified_9t.gpkg"
OUT = ROOT / "docs/presentation/figures_30to45min/v6"
GPKG = ROOT / "data/9t/derived/05/blocks_by_split_9t.gpkg"

BB = (619500.0, 4593000.0, 624000.0, 4597500.0)
PAPER = "#f7f8f6"
INK = "#141a1f"
MUTED = "#8a887e"

#: split -> (fill, hatch). Hatch is the second encoding, so the key survives
#: being printed small, in greyscale, or read by someone who cannot separate
#: the blue from the dark red.
STYLE = {
    "train": ("#1F5FA8", ""),
    "val":   ("#D97706", "///"),
    "test":  ("#A31515", "xxx"),
}
ORDER = ["train", "val", "test"]
LABEL = {"train": "train", "val": "validation", "test": "test"}


def main() -> int:
    if not BLOCKS.exists():
        raise SystemExit(f"missing: {BLOCKS}")
    d = gpd.read_file(BLOCKS).to_crs(6346)

    tb = d.total_bounds
    if max(abs(a - b) for a, b in zip(tb, BB)) > 1.0:
        raise SystemExit(f"blocks cover {tb}, not the 9t box {BB}; a key that "
                         "does not line up with the map is worse than none")
    counts = d["split"].value_counts().to_dict()
    missing = [s for s in ORDER if s not in counts]
    if missing:
        raise SystemExit(f"no blocks marked {missing}")
    side = int(round(len(d) ** 0.5))
    print(f"  {len(d)} blocks, {side} x {side} grid over 9t")
    for s in ORDER:
        print(f"    {LABEL[s]:11s} {counts[s]:3d} blocks   "
              f"{d.loc[d['split'] == s, 'n_feat'].sum():5d} features")

    plt.rcParams.update({"figure.facecolor": PAPER, "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(2.30, 2.86))

    for s in ORDER:
        face, hatch = STYLE[s]
        sub = d[d["split"] == s]
        sub.plot(ax=ax, facecolor=face, edgecolor="white", linewidth=0.7,
                 hatch=hatch, alpha=0.92, zorder=2)
    # matplotlib draws hatch in the edge colour, so restate the outlines on top
    d.boundary.plot(ax=ax, color="white", linewidth=0.7, zorder=3)

    ax.set_xlim(BB[0], BB[2])
    ax.set_ylim(BB[1], BB[3])
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("which blocks went where", fontsize=9.5, fontweight="bold",
                 color=INK, pad=5, loc="center")

    handles = [Patch(facecolor=STYLE[s][0], hatch=STYLE[s][1],
                     edgecolor="white", linewidth=0.7,
                     label=f"{LABEL[s]}  {counts[s]}")
               for s in ORDER]
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.02),
              fontsize=8.5, frameon=False, handlelength=1.5,
              handleheight=1.1, borderpad=0.2, labelspacing=0.45)
    fig.text(0.5, 0.012, "same extent as the map", fontsize=7.5,
             color=MUTED, ha="center")

    fig.subplots_adjust(left=0.03, right=0.97, top=0.93, bottom=0.30)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "block_split_key_9t.png"
    fig.savefig(p, dpi=220)
    plt.close(fig)

    d[["block_id", "n_feat", "split", "geometry"]].to_file(
        GPKG, layer="blocks_by_split", driver="GPKG")

    from PIL import Image
    print(f"\n  {Image.open(p).size[0]}x{Image.open(p).size[1]} px")
    print(f"  {p}")
    print(f"  {GPKG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
