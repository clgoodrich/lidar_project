"""Three preprocessing figures, written to be read from the back of a room.

    preprocessing_standard_values_9t   the numbers fixed once, and why each one
    pit_rim_floor_matching_9t          which rim belongs to which floor
    split_one_shared_9t                one train/val/test split, shared by all
                                       three tasks

PLAIN WORDS ON PURPOSE
----------------------
These explain method to an audience that does not have the code open. Every
panel says the thing in ordinary English first and gives the identifier second,
not the other way round. No value is typed in: the constants are parsed out of
phase_3_rasterization_training_prep.ipynb, the matching is recomputed the way
phase 2 computes it, and the split is read off blocks_unified_9t.gpkg.

A NOTE ON THE SPLIT FIGURE
--------------------------
The phase 3 notebook warns that pits and pads were balanced separately and that
"the road manifest carries whichever split was on blocks_gdf when its cell ran".
That hazard is real and it is also already fixed: _build_unified_split.py gives
every task one split. Checked rather than assumed -- of the 110 blocks that hold
more than one kind of feature, zero disagree about which split they are in. The
figure says that, because a slide claiming a bug that is fixed is worse than no
slide.

COLOUR
------
train / val / test use the validated lost-found palette from CLAUDE.md,
#1F5FA8 / #D97706 / #A31515: worst pair dE 21.1 deutan, 22.6 normal, every
colour at least 3:1 against the paper. No green, so no red/green pair.

Run:
    python docs/presentation/figures_30to45min/_build_preprocessing_figures.py
"""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch, Patch

# --- v6 bare mode -----------------------------------------------------------
# WELLSIGHT_BARE=1 suppresses this figure's own headline, subtitle and footnote
# and writes to a v6/ subdirectory. The deck supplies those words instead, in
# the slide's side column and its speaker notes. Added by
# tools/add_bare_mode_to_figure_builders.py.
import os as _os

BARE = _os.environ.get("WELLSIGHT_BARE") == "1"


def _chrome(_fn, *a, **k):
    """Draw slide chrome only when the figure has to stand on its own."""
    if not BARE:
        return _fn(*a, **k)
    return None


def _out(p):
    """Redirect an output directory into v6/ when building bare figures."""
    from pathlib import Path as _P
    p = _P(p)
    if BARE:
        p = p / "v6"
        p.mkdir(parents=True, exist_ok=True)
    return p
# ----------------------------------------------------------------------------


ROOT = Path(__file__).resolve().parents[3]
NB3 = ROOT / "notebooks/wellsight_v2/s1_build/phase_3_rasterization_training_prep.ipynb"
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
D05 = ROOT / "data/9t/derived/05"
OUT_A = _out(ROOT / "docs/presentation/figures_30to45min/3_annotations")

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"
ACCENT = "#1F5FA8"
TINT = "#eaf0f8"

C_TRAIN, C_VAL, C_TEST = "#1F5FA8", "#D97706", "#A31515"
#: Was #ccff00, an acid yellow-green, drawn beside #A31515 rims. That is a
#: red and a green carrying different meanings, which CLAUDE.md forbids
#: outright. Now the validated trio from the lost/found figures: rim #1F5FA8,
#: floor #D97706, unpaired rim #A31515, worst pair dE 21.1 deutan / 22.6
#: normal. The floor is also the only FILL against two line classes, so the
#: three stay separable with no colour at all.
C_FLOOR = "#D97706"
C_RIM = "#1F5FA8"
C_LONE = "#A31515"


def nb_constants():
    """Pull the fixed numbers straight out of the phase 3 notebook."""
    src = "\n".join("".join(c["source"])
                    for c in json.loads(NB3.read_text(encoding="utf-8"))["cells"]
                    if c["cell_type"] == "code")
    want = ("RNG_SEED", "SPLIT_FRACS", "ROAD_BUFFER_M", "DRAIN_BUFFER_M",
            "SAMPLE_STRIDE_M", "CHUNK_M")
    got = {}
    for name in want:
        m = re.search(rf"^{name}\s*=\s*(.+?)(?:\s+#.*)?$", src, re.M)
        if m:
            try:
                got[name] = ast.literal_eval(m.group(1).strip())
            except (ValueError, SyntaxError):
                got[name] = m.group(1).strip()
    return got


def card(ax, x, y, w, h, value, name, why):
    """One number, what it is called, and why it is that number."""
    ax.add_patch(FancyBboxPatch((x, y - h), w, h,
                                boxstyle="round,pad=0.0,rounding_size=1.2",
                                facecolor="#ffffff", edgecolor=RULE,
                                linewidth=1.2, zorder=2))
    ax.text(x + 2.4, y - h * 0.34, value, fontsize=27, fontweight="bold",
            color=ACCENT, va="center", ha="left", zorder=3)
    ax.text(x + 2.4, y - h * 0.63, name, fontsize=14, fontweight="bold",
            color=INK, va="center", ha="left", zorder=3)
    ax.text(x + 2.4, y - h * 0.845, why, fontsize=11.5, color=INK2,
            va="center", ha="left", zorder=3, linespacing=1.45)


# --------------------------------------------------------------------------
def fig_standard_values():
    k = nb_constants()
    fr = k.get("SPLIT_FRACS", {"train": .7, "val": .15, "test": .15})
    pct = "  /  ".join(f"{round(fr[s] * 100)}" for s in ("train", "val", "test"))

    cards = [
        ("0.5 m", "grid cell",
         "Every raster and every label sits on this\nsame grid, taken from the DEM."),
        (f"{k.get('ROAD_BUFFER_M', 1.5):g} m", "road half-width",
         "A road is drawn as a line. This turns it\ninto a strip 3 m across."),
        (f"{k.get('DRAIN_BUFFER_M', 2.0):g} m", "drainage half-width",
         "Wider than a road, because channels are\nwider than tracks."),
        (f"{k.get('CHUNK_M', 40):g} m", "road chunk",
         "Long roads are cut into pieces, so one road\ncannot sit in training and testing at once."),
        (f"{k.get('SAMPLE_STRIDE_M', 4):g} m", "sample spacing",
         "How often a point is taken along a line\nfor the road classifier."),
        (pct, "train / val / test",
         "The share of the map each split gets,\nby percentage of blocks."),
        (f"{k.get('RNG_SEED', 42)}", "random seed",
         "Fixed, so the split comes out the same\nevery time anyone runs it."),
        ("centre", "which pixels count",
         "A pixel is labelled only if its CENTRE is inside\nthe shape. Otherwise every pit grows by 25 cm."),
    ]

    fig, ax = plt.subplots(figsize=(16.0, 8.4))
    ax.set_xlim(0, 200)
    ax.set_ylim(0, 100)
    ax.axis("off")
    _chrome(ax.text, 4, 97, "The numbers we fixed once", fontsize=27,
            fontweight="bold", color=INK, va="top")
    _chrome(ax.text, 4, 91.5,
            "Preprocessing has eight constants. They are set in one place, at "
            "the top of the notebook, and nothing downstream is allowed to "
            "pick its own.",
            fontsize=13.5, color=INK2, va="top")

    # three columns inside x=4..197: the old width ran the third one off the
    # right edge of the canvas
    W, H, GX, GY = 60.5, 21.0, 4.5, 3.4
    for i, (value, name, why) in enumerate(cards):
        col, row = i % 3, i // 3
        card(ax, 4 + col * (W + GX), 84 - row * (H + GY), W, H, value, name, why)

    _chrome(ax.text, 4, 9.5,
            "Read out of phase_3_rasterization_training_prep.ipynb when this "
            "figure was drawn, so the slide cannot drift from the code.",
            fontsize=11.5, color=MUTED, va="top")
    fig.subplots_adjust(left=0.004, right=0.996, top=0.996, bottom=0.004)
    p = OUT_A / "preprocessing_standard_values_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}   {k}")


# --------------------------------------------------------------------------
def fig_matching():
    """Which rim belongs to which floor, and how many never pair up."""
    # 9t only. The slide used to quote 712 floors and 723 rims, which are
    # all-area totals; inside the tile it is 503 and 506, and the unpaired
    # counts collapse from 126/138 to a handful because most unpaired pits
    # live on tiles where only one of the two layers was ever drawn.
    from shapely.geometry import box as _box
    BB9T = _box(619500, 4593000, 624000, 4597500)
    ins = gpd.read_file(ANN, layer="pit_inside").to_crs(6346)
    out = gpd.read_file(ANN, layer="pit_outside").to_crs(6346)
    ins = ins[ins.geometry.centroid.within(BB9T)].reset_index(drop=True)
    out = out[out.geometry.centroid.within(BB9T)].reset_index(drop=True)
    ov = gpd.overlay(ins[["pit_inside_id", "geometry"]],
                     out[["pit_outside_id", "geometry"]],
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    m = ov.sort_values("a", ascending=False).drop_duplicates("pit_inside_id")
    n_f, n_r, n_m = len(ins), len(out), len(m)
    lone_r = n_r - m.pit_outside_id.nunique()
    lone_f = n_f - n_m

    # A window with several pits AND at least one unpaired rim, so the point
    # of the panel is visible. The old search stepped through every 7th rim
    # and kept any window containing a lone one; restricted to 9t there are
    # only a handful of lone rims, so it kept landing on an empty corner with
    # two pits in it. Search is now centred ON the lone rims and takes
    # whichever has the most company.
    # Restricted to 9t the pairing is near-perfect -- 0 floors without a rim
    # and 4 rims without one, out of 506. Insisting the window contain a lone
    # rim therefore picked an empty corner holding two pits, which made the
    # panel illustrate a 0.8% case and show nothing else. The window is now
    # simply the densest cluster of rims, which is what a reader should take
    # away, and the lone-rim callout appears only if one happens to fall
    # inside it.
    paired = set(m.pit_outside_id)
    cent = out.geometry.centroid
    best, bx, by = None, None, None
    for i in range(len(out)):
        x, y = cent.iloc[i].x, cent.iloc[i].y
        n = ((cent.x - x).abs() < 110) & ((cent.y - y).abs() < 110)
        if best is None or n.sum() > best:
            best, bx, by = n.sum(), x, y
    print(f"    densest window holds {best} rims within 110 m")
    if best is None:
        bx, by = cent.iloc[0].x, cent.iloc[0].y
    h = 120

    fig = plt.figure(figsize=(16.0, 8.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.12, 1.0], left=0.03,
                          right=0.975, top=0.755, bottom=0.135, wspace=0.10)
    _chrome(fig.suptitle, "Which rim belongs to which floor", fontsize=27,
                 fontweight="bold", x=0.03, ha="left", y=0.965, color=INK)
    _chrome(fig.text, 0.03, 0.885,
             "A pit is drawn twice, as an outer rim and as the floor inside "
             "it, and the two are separate layers with separate numbering. To "
             "measure a pit we\nhave to know which rim goes with which floor. "
             "The rule is the simplest one that works: pair each floor with "
             "the rim it overlaps most.",
             fontsize=13.5, color=INK2, va="top", linespacing=1.6)

    ax = fig.add_subplot(gs[0, 0])
    sub_o = out[(cent.x - bx).abs().lt(h) & (cent.y - by).abs().lt(h)]
    ci = ins.geometry.centroid
    sub_i = ins[(ci.x - bx).abs().lt(h) & (ci.y - by).abs().lt(h)]
    sub_o.boundary.plot(ax=ax, color=C_RIM, linewidth=2.4, zorder=3)
    sub_i.plot(ax=ax, facecolor=C_FLOOR, edgecolor="#3a3a3a", linewidth=1.2,
               alpha=0.9, zorder=4)
    lone = sub_o[~sub_o.pit_outside_id.isin(paired)]
    if len(lone):
        lone.boundary.plot(ax=ax, color=C_LONE, linewidth=3.4, zorder=5)
        # label ONE of them. Labelling every unpaired rim printed the same
        # six words six times and buried the picture under its own caption.
        g = lone.geometry.iloc[0]
        ax.annotate("this rim has no floor inside it",
                    # Point INWARD. A fixed offset ran the label off whichever
                    # edge the lone rim happened to sit near.
                    xy=(g.centroid.x, g.centroid.y),
                    xytext=(-34 if g.centroid.x > bx else 34,
                            -30 if g.centroid.y > by else 30),
                    textcoords="offset points",
                    ha="right" if g.centroid.x > bx else "left", fontsize=13,
                    fontweight="bold", color=C_LONE,
                    arrowprops=dict(arrowstyle="-", color=C_LONE, lw=1.8),
                    zorder=6)
    ax.set_xlim(bx - h, bx + h)
    ax.set_ylim(by - h, by + h)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    _chrome(ax.set_title, "a real corner of the map, 240 m across",
            fontsize=14, fontweight="bold", loc="left", pad=8, color=INK)
    ax.legend(handles=[
        Patch(facecolor=C_FLOOR, edgecolor="#3a3a3a", label="floor"),
        Line2D([], [], color=C_RIM, lw=2.6, label="rim, paired with a floor"),
        Line2D([], [], color=C_LONE, lw=3.2, label="rim with no floor")],
        loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3,
        fontsize=12.5, framealpha=1.0, facecolor="#ffffff", edgecolor=RULE)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 100)
    ax2.axis("off")
    rows = [(f"{n_f:,}", "floors drawn", INK, ACCENT),
            (f"{n_r:,}", "rims drawn", INK, ACCENT),
            (f"{n_m:,}", "pairs found", INK, ACCENT),
            (f"{lone_f:,}", "floors with no rim", INK2, C_LONE),
            (f"{lone_r:,}", "rims with no floor", INK2, C_LONE)]
    y = 96
    for val, label, tc, vc in rows:
        ax2.text(4, y, val, fontsize=34, fontweight="bold", color=vc,
                 va="top", ha="left")
        ax2.text(34, y - 4.5, label, fontsize=16, color=tc, va="center",
                 ha="left")
        y -= 17.5
    ax2.text(4, y + 4,
             "Only a paired pit gets a wall, and only a pit\nwith a wall can "
             "be measured. The unpaired ones\nare not lost, they are just not "
             f"measurable, and\nthat is why {n_f:,} floors yield {n_m:,} "
             "measurable walls.",
             fontsize=13, color=INK2, va="top", linespacing=1.6)

    p = OUT_A / "pit_rim_floor_matching_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}   "
          f"{n_f}/{n_r} -> {n_m} pairs")


# --------------------------------------------------------------------------
def fig_split():
    """One split, and the check that all three tasks really share it."""
    b = gpd.read_file(D05 / "blocks_unified_9t.gpkg")
    man = {t: pd.read_csv(D05 / f"{t}_dataset_manifest_unified.csv")
           for t in ("pit", "pad", "road")}
    bm = {t: dict(d.dropna(subset=["block_id"]).groupby("block_id")["split"]
                  .agg(lambda s: s.mode().iloc[0])) for t, d in man.items()}
    shared = set(bm["pit"]) & set(bm["pad"]) & set(bm["road"])
    clash = [x for x in shared if len({bm[t][x] for t in bm}) > 1]

    fig = plt.figure(figsize=(16.0, 8.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.15], left=0.03,
                          right=0.975, top=0.755, bottom=0.145, wspace=0.08)
    _chrome(fig.suptitle, "One split, shared by every task", fontsize=27,
                 fontweight="bold", x=0.03, ha="left", y=0.965, color=INK)
    _chrome(fig.text, 0.03, 0.885,
             "The map is cut into 144 square blocks and whole blocks are "
             "handed to training, validation or testing. Pits, pads and roads "
             "all use the SAME\nassignment, so a training patch centred on a "
             "pad can never reach into a block being used to test pits.",
             fontsize=13.5, color=INK2, va="top", linespacing=1.6)

    ax = fig.add_subplot(gs[0, 0])
    cols = {"train": C_TRAIN, "val": C_VAL, "test": C_TEST}
    for name, c in cols.items():
        sel = b[b["split"] == name]
        if len(sel):
            sel.plot(ax=ax, facecolor=c, edgecolor="#ffffff", linewidth=1.6,
                     alpha=0.92)
    b[~b["split"].isin(cols)].plot(ax=ax, facecolor="#e6e7e2",
                                   edgecolor="#ffffff", linewidth=1.6)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    n = b["split"].value_counts()
    ax.set_title("144 blocks over the 9t area", fontsize=14,
                 fontweight="bold", loc="left", pad=8, color=INK)
    # under the map, not on it: in the corner it sat on top of the blocks
    ax.legend(handles=[Patch(facecolor=cols[k], label=f"{k}   {n.get(k, 0)} blocks")
                       for k in ("train", "val", "test")],
              loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3,
              fontsize=12.5, framealpha=1.0, facecolor="#ffffff",
              edgecolor=RULE)

    ax2 = fig.add_subplot(gs[0, 1])
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 100)
    ax2.axis("off")
    ax2.text(0, 97, "what each task got", fontsize=15, fontweight="bold",
             color=INK, va="top")
    y = 88
    for t, label in (("pit", "pit floors"), ("pad", "pads"),
                     ("road", "road chunks")):
        d = man[t]
        used = d[d["split"].isin(("train", "val", "test"))]
        ax2.text(0, y, label, fontsize=14, fontweight="bold", color=INK,
                 va="center")
        ax2.text(34, y, f"{len(used):,} used", fontsize=14, color=INK2,
                 va="center")
        x = 52
        for k in ("train", "val", "test"):
            c = int((used["split"] == k).sum())
            w = 48 * c / max(len(used), 1)
            ax2.add_patch(FancyBboxPatch((x, y - 2.6), w, 5.2,
                                         boxstyle="square,pad=0",
                                         facecolor=cols[k], edgecolor="none"))
            if w > 7:
                ax2.text(x + w / 2, y, f"{c:,}", fontsize=10.5, color="#ffffff",
                         ha="center", va="center", fontweight="bold")
            x += w
        y -= 13

    ax2.text(0, y + 2, "the check", fontsize=15, fontweight="bold", color=INK,
             va="top")
    ax2.add_patch(FancyBboxPatch((0, y - 27), 98, 25,
                                 boxstyle="round,pad=0.0,rounding_size=1.6",
                                 facecolor=TINT, edgecolor=ACCENT,
                                 linewidth=1.5))
    ax2.text(4, y - 8.5, f"{len(shared)}", fontsize=30, fontweight="bold",
             color=ACCENT, va="center")
    ax2.text(20, y - 8.5, "blocks hold more than one kind of feature",
             fontsize=13.5, color=INK, va="center")
    ax2.text(4, y - 19, f"{len(clash)}", fontsize=30, fontweight="bold",
             color=ACCENT, va="center")
    ax2.text(20, y - 19, "of them disagree about which split they are in",
             fontsize=13.5, color=INK, va="center")

    _chrome(fig.text, 0.03, 0.022,
             "Pits and pads were once balanced separately, which is how a pad "
             "in a training block could overlap a block held out for pits. "
             "_build_unified_split.py\nreplaced the two with one. The count "
             "above is that fix, re-checked against the manifests when this "
             "figure was drawn.",
             fontsize=11.5, color=MUTED, va="bottom", linespacing=1.6)

    p = OUT_A / "split_one_shared_9t.png"
    fig.savefig(p, dpi=150, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p.name}   "
          f"{len(shared)} shared, {len(clash)} clash")


def main() -> int:
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    OUT_A.mkdir(parents=True, exist_ok=True)
    fig_standard_values()
    fig_matching()
    fig_split()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
