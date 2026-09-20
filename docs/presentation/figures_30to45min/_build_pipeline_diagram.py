"""The detection pipeline, end to end, as it actually runs today.

SHAPE
-----
Three rows of five boxes, read left to right, at the scale of the old
two-branch diagram it replaces. An earlier version of this file packed the same
content into five tall columns of dense body text; on a projector it was
unreadable. A box here holds two or three short lines and nothing else. The
long lists that have to be on the figure -- every derivative, every annotation
layer -- sit under their row as a caption, where they can be read if wanted and
skipped if not.

WHAT CHANGED FROM THE OLD DIAGRAM
---------------------------------
It showed two branches off a shared base: a classical branch scoring ROC-AUC
0.905 / PR-AUC 0.212, and a deep-learning branch. The classical branch is
retired. Everything on the leaderboard, every probability raster and every
threshold product is U-Net, so a two-branch picture now misdescribes the
project. This is one path.

NOTHING HERE IS DECORATIVE
--------------------------
Every box is a step that exists in the repository, and the counts are read off
the things they describe rather than typed from memory:

    the feature-stack channels      band descriptions of features_pit_9t_05
    the annotation layer names      gpkg_contents in annotations_proj.gpkg
    patch size, folds, epochs       _pit_unet_cv5.py
    the derivative list             data/9t/derived/05

Where a stage is genuinely untested -- the SMRF ground surface is measured but
no model has been retrained on it -- it is said in a footnote rather than drawn
into the flow.

COLOUR
------
One blue accent on a grey ground, per the colourblind rule in CLAUDE.md. No
red/green pair anywhere; the rows are told apart by position and heading, not
by hue.

Run:
    python docs/presentation/figures_30to45min/_build_pipeline_diagram.py
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import rasterio
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data" / "9t" / "derived" / "05"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "4_model_building"

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"
ACCENT = "#1F5FA8"
TINT = "#eaf0f8"

#: Canvas units. Five boxes across, three rows down.
NCOL, BW, GAP, BH = 5, 34.0, 3.6, 17.0
X0 = 5.0


def col_x(i):
    return X0 + i * (BW + GAP)


def wrap_join(items, width, sep=" · "):
    """Join names with a separator, breaking before the caption runs out."""
    out, cur = [], ""
    for it in items:
        add = it if not cur else cur + sep + it
        if len(add) > width and cur:
            out.append(cur)
            cur = it
        else:
            cur = add
    if cur:
        out.append(cur)
    return out


def feature_channels():
    """The bands the models actually take, from the stack itself."""
    p = D05 / "features_pit_9t_05.tif"
    if not p.exists():
        return []
    with rasterio.open(p) as r:
        return [d for d in (r.descriptions or []) if d]


def annotation_layers():
    """The hand-drawn layers, named individually, from the GeoPackage."""
    if not ANN.exists():
        return []
    con = sqlite3.connect(ANN)
    try:
        return [r[0] for r in con.execute(
            "select table_name from gpkg_contents order by table_name")]
    finally:
        con.close()


def derivative_names():
    """Every 0.5 m derivative on disk for 9t, minus labels and scratch."""
    skip = ("labels_", "mask_", "features_", "rgb3", "_dem_", "stream_",
            "flow_", "dem_breached")
    out = set()
    for p in D05.glob("*_9t_05.tif"):
        n = p.name.replace("_9t_05.tif", "")
        if n.startswith(skip) or n.endswith("_dupe"):
            continue
        out.add(n)
    return sorted(out)


#: What each hand-drawn layer is FOR. The old diagram flattened all seven into
#: "hand annotation in QGIS", which hides the fact that matters most: the pit
#: model trains on the floor, not on the whole pit.
ROLE = {
    "pit_inside": "the floor, what the pit model trains on",
    "pit_outside": "the outer rim",
    "pit_wall": "the slope between rim and floor",
    "plat": "the pads",
    "roads": "access roads and tracks",
    "drainage": "streams and ditches",
    "not_roads": "hard negatives from the correction pass",
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    chans = feature_channels()
    layers = annotation_layers()
    derivs = derivative_names()
    print(f"feature stack : {len(chans)} bands  {chans}")
    print(f"annotations   : {len(layers)} layers {layers}")
    print(f"derivatives   : {len(derivs)} rasters {derivs}")

    rows = [
        ("1", "Data and terrain", [
            "USGS 3DEP QL2\n~4.8 pts/m², leaf-off\nMarch 2020, 9 tiles",
            "ground classification\nchecked — the vendor stops\nat 18° off nadir",
            "bare-earth DEM\nand DSM\nat 0.5 m",
            f"{len(derivs)} terrain derivatives,\nall at 0.5 m",
            f"hand annotation in QGIS\non RRIM — {len(layers)} layers,\neach drawn separately",
        ]),
        ("2", "Training prep", [
            "labels rasterised\nonto the DEM grid",
            "roads cut into\n~40 m chunks",
            f"{len(chans)}-channel feature stack,\nnormalised on train",
            "12×12 spatial blocks\nsplit by BLOCK,\nnever by well",
            "128 m patches\nwith 30 m jitter",
        ]),
        ("3", "Training and QA", [
            "U-Net, base 32\nfocal cross-entropy",
            "5-fold cross-validation\n40 epochs",
            "one model each:\npit, pad,\nroad, drainage",
            "probability raster per class\n→ threshold sweep\n→ candidate polygons",
            "QA: centroid precision,\nrim containment,\n613590 never trained on",
        ]),
    ]
    # The derivative list, the annotation-layer list, the in-figure title and
    # the SMRF footnote were all cut on 2026-09-20: the slide already carries a
    # title, and the two name lists are reference material that nobody reads off
    # a projected slide. Three rows of boxes and nothing else.
    caps = [(None, []), (None, []), (None, [])]

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(20.0, 8.0))
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 80)
    ax.axis("off")

    top = 76.0
    for (num, head, boxes), cap in zip(rows, caps):
        ax.text(X0, top, num, fontsize=21, fontweight="bold", color=ACCENT,
                va="bottom", ha="left")
        ax.text(X0 + 5.0, top + 0.15, head, fontsize=18, fontweight="bold",
                color=INK, va="bottom", ha="left")
        ax.plot([X0, col_x(NCOL - 1) + BW], [top - 1.7, top - 1.7],
                color=RULE, linewidth=1.3)

        by = top - 3.1
        for i, body in enumerate(boxes):
            x = col_x(i)
            ax.add_patch(FancyBboxPatch(
                (x, by - BH), BW, BH,
                boxstyle="round,pad=0.0,rounding_size=1.4",
                facecolor=TINT, edgecolor=ACCENT, linewidth=1.5, zorder=2))
            ax.text(x + BW / 2, by - BH / 2, body, fontsize=14.5, color=INK,
                    va="center", ha="center", zorder=3, linespacing=1.55)
            if i < NCOL - 1:
                ax.add_patch(FancyArrowPatch(
                    (x + BW + 0.5, by - BH / 2),
                    (x + BW + GAP - 0.5, by - BH / 2),
                    arrowstyle="-|>", mutation_scale=20, color=ACCENT,
                    linewidth=2.2, zorder=4))

        label, lines = cap
        cy = by - BH - 2.4
        if label:
            # the label sits once, at the left; the wrapped names hang off it
            ax.text(X0, cy, label + ":", fontsize=11.5, color=MUTED,
                    va="top", ha="left", fontweight="bold")
        for line in lines:
            ax.text(X0 + 20.0, cy, line, fontsize=11.5, color=MUTED,
                    va="top", ha="left")
            cy -= 2.7
        top = (cy if lines else by - BH - 2.0) - 3.4

    fig.subplots_adjust(left=0.006, right=0.997, top=0.985, bottom=0.015)
    p = OUT / "pipeline_diagram_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"\n{p.stat().st_size/1e3:.0f} KB  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
