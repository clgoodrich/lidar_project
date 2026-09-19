"""The WellSight pipeline, end to end, as it actually runs today.

WHAT CHANGED FROM THE OLD DIAGRAM
---------------------------------
The previous figure showed two branches off a shared base -- a classical
branch scoring ROC-AUC 0.905 / PR-AUC 0.212, and a deep-learning branch. The
classical branch is retired. Everything on the leaderboard, every probability
raster and every threshold product is U-Net, so a two-branch picture now
misdescribes the project. This is one path.

NOTHING HERE IS DECORATIVE
--------------------------
Every box is a step that exists in the repository, and the numbers are read off
the things they describe rather than typed from memory:

    the seven feature-stack channels     band descriptions of features_pit_9t_05
    the annotation layer names           gpkg_contents in annotations_proj.gpkg
    patch size, folds, epochs, loss      _pit_unet_cv5.py
    the derivative list                  data/9t/derived/05

If a step is not in the repo it is not on the diagram. Where a stage is genuinely
untested -- the SMRF ground surface is measured but no model has been retrained
on it -- the box says so rather than implying it is wired in.

COLOUR
------
One blue accent on a grey ground, per the colourblind rule in CLAUDE.md. No
red/green pair anywhere; the two tinted stages are distinguished by position and
label, not by hue alone.

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
RULE = "#d7dad4"
ACCENT = "#1F5FA8"
BOX = "#ffffff"
TINT = "#e7eef7"


def wrap_join(items, width):
    """Join names with a separator, breaking before the box edge."""
    out, cur = [], ""
    for it in items:
        add = it if not cur else cur + " · " + it
        if len(add) > width and cur:
            out.append(cur); cur = it
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
        names = [r[0] for r in con.execute(
            "select table_name from gpkg_contents order by table_name")]
    finally:
        con.close()
    return names


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


# --------------------------------------------------------------------------
def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    chans = feature_channels()
    layers = annotation_layers()
    derivs = derivative_names()
    print(f"feature stack : {len(chans)} bands  {chans}")
    print(f"annotations   : {len(layers)} layers {layers}")
    print(f"derivatives   : {len(derivs)} rasters {derivs}")

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(19.2, 9.4))
    ax.set_xlim(0, 192); ax.set_ylim(0, 94)
    ax.axis("off")

    #: (x, stage number, heading, one-line summary, [(body, is_tinted)])
    #: Grouped by what the channel measures. Twenty-one names in one
    #: alphabetical run ran straight through the next three columns.
    FAMILY = [
        ("surfaces",      ("dem", "dsm", "chm")),
        ("shading",       ("hillshade", "hillshade_az090_alt25",
                           "hillshade_az270_alt25", "hillshade_az315_alt25",
                           "hillshade_az315_alt70", "rrim_openness")),
        ("slope and shape", ("slope", "tpi_05", "tpi_15", "roughness_11")),
        ("local relief",  ("lrm_5", "lrm_11", "lrm_25", "local_relief_10")),
        ("openness",      ("openness_pos", "openness_neg")),
        ("point statistics", ("ground_density", "intensity_ground")),
    ]
    seen, lines = set(), []
    for fam, names in FAMILY:
        have = [n for n in names if n in derivs]
        if not have:
            continue
        seen.update(have)
        lines.append(fam)
        lines += ["   " + t for t in wrap_join(have, 34)]
    rest = sorted(set(derivs) - seen)
    if rest:
        lines.append("other")
        lines += ["   " + t for t in wrap_join(rest, 34)]
    hs = "\n".join(lines)
    ch = "\n".join(f"{i+1}.  {c}" for i, c in enumerate(chans))
    ann = "\n".join(f"·  {n}" for n in layers)

    STAGES = [
        (2.0, "1", "Data QA",
         "is the lidar we were handed any good",
         [("USGS 3DEP  PA WesternPA 2019 D20\nQL2, ~4.8 pts/m², flown March 2020\n"
           "leaf-off, 9 tiles over the 9t area", False),
          ("ground classification checked\n"
           "vendor stops calling ground past 18°\n"
           "off nadir — 13.8% of the area has no\n"
           "ground measurement under it", True),
          ("SMRF reclassification\nhalves that to 8.2%\n"
           "MEASURED, NOT YET WIRED IN — the\n"
           "stack below is still vendor ground", True)]),

        (40.0, "2", "Terrain derivatives",
         f"{len(derivs)} rasters at 0.5 m from the ground surface",
         [(hs, False),
          ("bare-earth DEM and DSM first, then\n"
           "everything else derives from them\n"
           "RRIM = openness + slope, Chiba 2008", False)]),

        (78.0, "3", "Hand annotation",
         f"{len(layers)} layers drawn in QGIS on RRIM",
         [(ann, False),
          ("pit_inside is the FLOOR and is what the\n"
           "pit model trains on; pit_outside is the\n"
           "rim and pit_wall the slope between.\n"
           "plat holds the pads. not_roads are hard\n"
           "negatives from a correction pass.", True)]),

        (116.0, "4", "Training prep",
         "labels and channels onto one grid",
         [("labels rasterised to the DEM grid\n"
           "roads cut into ~40 m chunks\n"
           "12×12 spatial blocks, split by BLOCK\n"
           "and never by well", False),
          (f"feature stack, {len(chans)} bands:\n{ch}", True)]),

        (154.0, "5", "Training and QA",
         "U-Net per task, then check it honestly",
         [("U-Net, base 32, focal cross-entropy\n"
           "128 m patches with 30 m jitter\n"
           "5-fold cross-validation, 40 epochs\n"
           "one model each: pit, pad, road, drainage", False),
          ("probability raster per class\n"
           "→ threshold sweep → candidate polygons", False),
          ("QA / QC\n"
           "centroid precision at 6 m tolerance\n"
           "rim containment on held-out pits\n"
           "613590: a tile never trained on\n"
           "every result on one leaderboard", True)]),
    ]

    W = 34.0
    for x, num, head, sub, blocks in STAGES:
        ax.text(x, 89.5, num, fontsize=25, fontweight="bold", color=ACCENT,
                va="top", ha="left")
        ax.text(x + 6.2, 89.1, head, fontsize=16.5, fontweight="bold",
                color=INK, va="top", ha="left")
        ax.text(x + 6.2, 84.3, sub, fontsize=10.5, color=INK2, va="top",
                ha="left")
        ax.plot([x, x + W], [81.8, 81.8], color=RULE, linewidth=1.2)

        y = 78.6
        for body, tinted in blocks:
            n = body.count("\n") + 1
            h = 2.6 + n * 2.62
            ax.add_patch(FancyBboxPatch(
                (x, y - h), W, h, boxstyle="round,pad=0.0,rounding_size=1.1",
                facecolor=TINT if tinted else BOX,
                edgecolor=ACCENT if tinted else RULE,
                linewidth=1.1 if tinted else 0.9, zorder=2))
            ax.text(x + 1.6, y - h / 2, body, fontsize=9.3, color=INK,
                    va="center", ha="left", zorder=3, linespacing=1.5)
            y -= h + 2.2

        if x < 150:
            ax.add_patch(FancyArrowPatch(
                (x + W + 0.8, 52.0), (x + W + 3.0, 52.0),
                arrowstyle="-|>", mutation_scale=22, color=ACCENT,
                linewidth=2.4, zorder=4))

    ax.text(0, 7.6, "Everything here exists in the repository. The classical "
            "branch that used to sit beside this one is retired — every "
            "model on the leaderboard, every probability\nraster and every "
            "threshold product is U-Net, so there is one path and not two.",
            fontsize=11, color=INK2, va="top", ha="left", linespacing=1.7)
    ax.text(0, 2.2, "The SMRF ground surface is measured but no model has been "
            "retrained on it yet, so it is marked as such rather than drawn "
            "into the flow.",
            fontsize=10, color=MUTED, va="top", ha="left")

    fig.subplots_adjust(left=0.012, right=0.994, top=0.985, bottom=0.01)
    p = OUT / "pipeline_diagram_9t.png"
    fig.savefig(p, dpi=170)
    plt.close(fig)
    print(f"\n{p.stat().st_size/1e3:.0f} KB  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
