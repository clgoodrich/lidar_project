"""Rebuilt figures for deck v6. Bare graphics, no baked-in chrome.

WHY A NEW FILE RATHER THAN EDITS TO THE OLD BUILDERS
-----------------------------------------------------
The v5 figures are self-contained mini-posters: each one carries its own
headline, subtitle, legend and footnote. On a slide that already has a title
that is a double title, and the footnote lands at 11 pt on a projector where
nobody reads it. The fix is not to shrink that text, it is to move it OFF the
image -- into the slide's left column and the speaker notes -- so the graphic
carries only the graphic.

The old builders are left untouched. They are referenced from
docs/iterations/*.md as the record of how each number was produced, and several
of them write analysis products that are not presentation figures. This file
produces presentation figures only, with one design language, and each function
returns the text that belongs beside it so the deck builder can place it.

DESIGN RULES, applied to every figure here
------------------------------------------
1. No title, no subtitle, no footnote inside the image. The slide owns those.
2. Label the thing directly. A reader should never have to travel to a legend
   and back to learn what a mark means.
3. Show the reference. A measurement without the bar it has to clear is not a
   finding, it is a number.
4. One question per image. If it takes two sentences to say what the image is
   for, it is two images.
5. Paper matches the slide (#f7f8f6), so the figure has no visible edge.

COLOUR, validated with the dataviz skill's validate_palette.js, --pairs all,
run as two- and three-slot palettes (a greyscale ramp or a neutral "unused"
category is sequential/neutral and is not a categorical slot):
    kept vs recovered    #1F5FA8 / #D97706   CVD worst dE 26.1 protan
    found vs missed      #1F5FA8 / #A31515   CVD worst dE 22.8 deutan, ALL PASS
    three-way split      #2a78d6 / #eb6834 / #1baf7a   worst dE 9.2 deutan
The three-way sits in the 9-10 band, which the validator allows only with a
second encoding, so every category in those figures also carries a direct text
label. Neutral grey #b8bcb4 is used only for "not applicable" and is always
labelled.

Run:
    python docs/presentation/figures_30to45min/_build_v6_figures.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Patch

ROOT = Path(__file__).resolve().parents[3]
NGC = ROOT / "data/9t/results/nonground_classification"
OUT = ROOT / "docs/presentation/figures_30to45min/v6"

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"

KEPT = "#1F5FA8"
GONE = "#D97706"
MISS = "#A31515"
NEUTRAL = "#b8bcb4"

SPLIT = {"train": "#2a78d6", "val": "#eb6834", "test": "#1baf7a",
         "unused": NEUTRAL}


def style():
    plt.rcParams.update({
        "figure.facecolor": PAPER, "axes.facecolor": PAPER,
        "savefig.facecolor": PAPER, "font.family": "DejaVu Sans",
        "text.color": INK, "axes.labelcolor": INK,
        "xtick.color": INK2, "ytick.color": INK2,
        "axes.edgecolor": RULE,
    })


def clean(ax, keep=("bottom",)):
    for s, sp in ax.spines.items():
        sp.set_visible(s in keep)
        sp.set_color(RULE)
    ax.tick_params(length=0)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {p}")
    return p


# ---------------------------------------------------------------------------
# slide 12 -- where ground classification stops, per flight block
# ---------------------------------------------------------------------------
def fig_where_ground_stops():
    """A gap chart. The old version was two overlapping dot swarms.

    The finding is a GAP -- the scanner kept recording past the angle where the
    vendor stopped calling returns ground -- and a gap is the one thing two
    piles of dots on a shared axis cannot show, because they land on top of each
    other. One bar per flight block, split at the cut, with the discarded wedge
    drawn as the thing it is: the right-hand end of the same bar.
    """
    d = pd.read_csv(NGC / "scan_angle_cliff_by_acquisition_all_tiles.csv")
    rows, unusable = [], []
    for blk, g in d.groupby("block"):
        cut = g["cut"].dropna()
        mx = float(g["max_ang"].median())
        rec = dict(block=blk, n=len(g), n_cut=len(cut),
                   cut=float(cut.median()) if len(cut) else None,
                   mx=mx, lost=int(g["lost"].sum()), area=g["area"].iloc[0])
        # The 2011 Venango delivery stores 0.000 in the scan-angle field for
        # every square: the angle was never populated. Drawing that as a
        # zero-length bar would read as "no gap", which is the opposite of the
        # truth -- it cannot be checked at all. It gets its own labelled row.
        (unusable if mx <= 0.0 else rows).append(rec)
    rows.sort(key=lambda r: -r["n_cut"])
    rows.extend(unusable)

    style()
    fig, ax = plt.subplots(figsize=(12.6, 6.4))
    h = 0.44
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        if r["mx"] <= 0.0:
            ax.barh(y, 31.0, height=h, color="#e4e5e0", zorder=3,
                    hatch="////", edgecolor=NEUTRAL, linewidth=0)
            ax.text(31.0 / 2, y, "this delivery records no scan angle — "
                    "it cannot be checked", color=INK2, fontsize=12.5,
                    fontstyle="italic", ha="center", va="center", zorder=4)
            ax.text(-0.6, y + 0.13, r["block"], fontsize=14,
                    fontweight="bold", color=INK2, ha="right", va="bottom")
            ax.text(-0.6, y - 0.13, f"{r['n']} map squares", fontsize=11.5,
                    color=MUTED, ha="right", va="top")
            continue
        stop = r["cut"] if r["cut"] else r["mx"]
        ax.barh(y, stop, height=h, color=KEPT, zorder=3)
        ax.text(stop / 2, y, "called ground", color="white", fontsize=13,
                fontweight="bold", ha="center", va="center", zorder=4)
        if r["cut"]:
            ax.barh(y, r["mx"] - stop, left=stop, height=h, color=GONE,
                    zorder=3)
            # to the RIGHT of the bar, never below -- below collides with the
            # next row's label block
            ax.text(r["mx"] + 0.7, y,
                    f"{r['lost']/1e6:.0f} million returns thrown away",
                    fontsize=13, fontweight="bold", color=GONE,
                    va="center", ha="left")
            ax.text(stop, y + h / 2 + 0.07, f"stops at {stop:.0f}°",
                    fontsize=13, fontweight="bold", color=INK,
                    ha="center", va="bottom")
        else:
            ax.text(r["mx"] + 0.7, y, "no gap", fontsize=13, color=INK2,
                    va="center", ha="left")
        ax.text(-0.6, y + 0.13, r["block"], fontsize=14, fontweight="bold",
                color=INK, ha="right", va="bottom")
        note = (f"{r['n_cut']} of {r['n']} map squares cut"
                if r["cut"] else f"{r['n']} map squares, none cut")
        ax.text(-0.6, y - 0.13, note, fontsize=11.5, color=MUTED,
                ha="right", va="top")

    ax.set_xlim(0, 52)
    ax.set_ylim(-0.7, len(rows) - 0.25)
    ax.set_yticks([])
    ax.set_xlabel("how far off straight down the laser was aimed  (degrees)",
                  fontsize=13)
    ax.set_xticks(range(0, 35, 5))
    clean(ax)
    ax.grid(axis="x", color=RULE, linewidth=0.7, zorder=0)
    fig.subplots_adjust(left=0.215, right=0.995, top=0.97, bottom=0.12)
    return save(fig, "where_ground_stops_by_flight_block_9t.png")


# ---------------------------------------------------------------------------
# slide 13 -- are the discarded returns any good?
# ---------------------------------------------------------------------------
def fig_discarded_returns_accuracy():
    """Two dots and the bar they have to clear.

    REPLACES A RULE VIOLATION. The v5 figure coloured "accepted" green and
    "excluded" red -- a red/green pair carrying different meanings, which
    CLAUDE.md forbids outright and which is the single most common form of
    colour blindness. Recoloured to the validated kept/recovered pair,
    #1F5FA8 against #D97706, CVD worst dE 26.1 protan.

    It also drops the twin histograms. They sat exactly on top of each other,
    which WAS the finding, but a reader sees one lump and learns nothing. The
    claim is "both are under the spec", so the figure is two dots and the spec.
    """
    d = pd.read_csv(NGC / "excluded_returns_vertical_accuracy.csv")
    d = d[d["n"] > 0]
    label = {"accepted, wide angle": "kept by the survey",
             "excluded, wide angle": "thrown away by the survey"}
    colour = {"accepted, wide angle": KEPT, "excluded, wide angle": GONE}
    tiles = sorted(d["tile"].unique())

    style()
    fig, ax = plt.subplots(figsize=(12.6, 5.6))
    SPEC = 0.10
    ax.axvspan(SPEC, 0.132, color=MISS, alpha=0.06, zorder=0)
    ax.axvline(SPEC, color=MISS, linewidth=2.0, zorder=2)
    # centred ON the line, in the headroom above the top row, so it cannot be
    # clipped by the right edge the way a left-anchored label was
    ax.text(SPEC, 1.92, "the 10 cm specification\neverything has to be "
            "left of this line", fontsize=12.5, color=MISS,
            fontweight="bold", va="top", ha="center", linespacing=1.45)

    # the two dots can land within a millimetre of each other, so the value
    # labels go one above and one below rather than both below
    offset = {"accepted, wide angle": +0.20, "excluded, wide angle": -0.20}
    valign = {"accepted, wide angle": "bottom", "excluded, wide angle": "top"}
    for i, t in enumerate(tiles):
        y = len(tiles) - 1 - i
        sub = d[d["tile"] == t]
        xs = {r["group"]: r["rmse"] for _, r in sub.iterrows()}
        a, b = xs["accepted, wide angle"], xs["excluded, wide angle"]
        ax.plot([min(a, b), max(a, b)], [y, y], color=RULE, linewidth=3.0,
                solid_capstyle="round", zorder=3)
        for g, x in xs.items():
            ax.scatter([x], [y], s=290, color=colour[g], zorder=4,
                       edgecolor=PAPER, linewidth=2.0)
            ax.text(x, y + offset[g], f"{x:.3f} m", fontsize=12.5,
                    fontweight="bold", color=colour[g], ha="center",
                    va=valign[g], zorder=5)
        ax.text(-0.004, y, f"map square\n{t}", fontsize=13.5,
                fontweight="bold", color=INK, ha="right", va="center",
                linespacing=1.4)

    ax.scatter([], [], s=200, color=KEPT, label=label["accepted, wide angle"])
    ax.scatter([], [], s=200, color=GONE, label=label["excluded, wide angle"])
    lg = ax.legend(loc="lower left", frameon=False, fontsize=13,
                   handletextpad=0.5, borderpad=0.2,
                   bbox_to_anchor=(0.0, -0.02))
    for txt in lg.get_texts():
        txt.set_color(INK)

    ax.set_xlim(0.0, 0.132)
    ax.set_ylim(-0.85, 2.15)
    ax.set_yticks([])
    ax.set_xlabel("how far each return sits from the ground surveyed by the "
                  "neighbouring flight line  (metres, lower is better)",
                  fontsize=13)
    clean(ax)
    ax.grid(axis="x", color=RULE, linewidth=0.7, zorder=1)
    fig.subplots_adjust(left=0.155, right=0.985, top=0.99, bottom=0.17)
    return save(fig, "discarded_returns_accuracy_vs_spec_9t.png")


# ---------------------------------------------------------------------------
# slide 40b -- why the split balances on pit count, not on area
# ---------------------------------------------------------------------------
def fig_split_blocks_vs_pits():
    """Blocks against pits, with ONE colour meaning one thing.

    The v5 panel had a legend reading "share of pit floors" beside a blue
    swatch while the val bar was orange and the test bar green -- three colours
    for one quantity. Here grey is always "share of the map" and blue is always
    "share of the pits", on every row, and the split name is the row label.
    """
    rows = [("train", 77, 352), ("val", 14, 77),
            ("test", 24, 74), ("unused", 29, 0)]
    nb = sum(r[1] for r in rows)
    npit = sum(r[2] for r in rows)

    style()
    fig, ax = plt.subplots(figsize=(12.6, 6.0))
    h = 0.34
    for i, (name, blocks, pits) in enumerate(rows):
        y = len(rows) - 1 - i
        pb, pp = 100 * blocks / nb, 100 * pits / npit
        ax.barh(y + h / 2 + 0.02, pb, height=h, color=NEUTRAL, zorder=3)
        ax.barh(y - h / 2 - 0.02, pp, height=h, color=KEPT, zorder=3)
        # a long bar puts its label inside, or the label runs off the axes
        for val, yy, txt, col in (
                (pb, y + h / 2 + 0.02, f"{pb:.0f}% of the map   "
                 f"({blocks} blocks)", INK2),
                (pp, y - h / 2 - 0.02, f"{pp:.0f}% of the pits   "
                 f"({pits} pits)", KEPT)):
            inside = val > 42
            ax.text(val - 1.2 if inside else val + 1.2, yy, txt,
                    fontsize=12.5, fontweight="bold",
                    color="white" if inside else col,
                    va="center", ha="right" if inside else "left", zorder=4)
        ax.text(-1.5, y, name, fontsize=15, fontweight="bold", color=INK,
                ha="right", va="center")

    ax.set_xlim(0, 84)
    ax.set_ylim(-0.7, len(rows) - 0.3)
    ax.set_yticks([])
    ax.set_xlabel("share of the tile  (%)", fontsize=13)
    clean(ax)
    ax.grid(axis="x", color=RULE, linewidth=0.7, zorder=0)
    fig.subplots_adjust(left=0.115, right=0.985, top=0.97, bottom=0.11)
    return save(fig, "split_share_of_map_vs_share_of_pits_9t.png")


# ---------------------------------------------------------------------------
# slide 10 -- what the cut cost, without the fourth box
# ---------------------------------------------------------------------------
def fig_what_the_cut_cost():
    """Three numbers. The fourth box moved to the speaker notes.

    The v5 card stack ended with a blue box reading "and they are no worse than
    the ground it kept", which is a sentence, not a number, and it is the one
    thing on the slide a speaker would say out loud anyway.
    """
    j = json.loads((ROOT / "data/9t/results/recovered_ground_9t"
                    / "recovered_ground_9t_summary.json").read_text())
    d = pd.read_csv(NGC / "scan_angle_cliff_by_acquisition_all_tiles.csv")
    blk = d[d["block"].str.contains("Venango 2020", na=False)]
    cut = blk[blk["cut"].notna()]

    cards = [
        (f"{blk['lost'].sum()/1e6:,.0f} million", MISS,
         "returns hit the ground and were not called ground",
         f"{len(cut)} of {len(blk)} map squares, every one cut at 18°"),
        (f"{j['void_v']:.1f}%", MISS,
         "of our training area has no ground measurement under it", ""),
        (f"{j['void_b']:.1f}%", GONE,
         "after we classify the ground ourselves, keeping every angle",
         f"{j['closed']/1e6:.1f} million cells filled in"),
    ]

    style()
    fig, ax = plt.subplots(figsize=(7.9, 7.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    top, gap, bh = 97.0, 5.0, 29.0
    for big, col, lab, note in cards:
        ax.add_patch(FancyBboxPatch(
            (0, top - bh), 100, bh,
            boxstyle="round,pad=0.0,rounding_size=1.6",
            facecolor="#ffffff", edgecolor=RULE, linewidth=1.2))
        ax.text(3, top - bh * 0.38, big, fontsize=40, fontweight="bold",
                color=col, va="center", ha="left")
        ax.text(3, top - bh * 0.70, lab, fontsize=14, color=INK,
                va="center", ha="left")
        if note:
            ax.text(3, top - bh * 0.95, note, fontsize=11.5, color=MUTED,
                    va="center", ha="left")
        top -= bh + gap
    fig.subplots_adjust(left=0.015, right=0.985, top=0.99, bottom=0.01)
    return save(fig, "what_the_scan_angle_cut_cost_9t.png")


# ---------------------------------------------------------------------------
# slide 9 (left half) -- the scan-angle cone, with no text of its own
# ---------------------------------------------------------------------------
def fig_scan_angle_cone():
    """The cone alone. The sentence that used to sit above it is now the
    slide title, and repeating it inside the image is the double-titling this
    whole pass is meant to remove."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _build_data_qa_problem import scan_diagram

    style()
    fig = plt.figure(figsize=(7.8, 7.0))
    ax = fig.add_axes([0.02, 0.04, 0.96, 0.92])
    scan_diagram(ax, 18.0, title=None)
    return save(fig, "scan_angle_cone_bare_9t.png")


def main() -> int:
    print("v6 figures ->", OUT)
    fig_scan_angle_cone()
    fig_what_the_cut_cost()
    fig_where_ground_stops()
    fig_discarded_returns_accuracy()
    fig_split_blocks_vs_pits()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
