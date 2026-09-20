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
D05 = ROOT / "data/9t/derived/05"
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


# ---------------------------------------------------------------------------
# slide 37 -- rim/floor pairing, MAP ONLY
# ---------------------------------------------------------------------------
def fig_rim_floor_map():
    """Just the corner of the map. The five counts move to the slide.

    The v5 figure was a 2:1 composition: a map on the left and a column of five
    big numbers on the right, under a headline and a four-line paragraph. Asked
    for the map large on the right of the slide with the text beside it, the
    right answer is to stop drawing the numbers inside the PNG at all -- the
    slide's left column holds them, in 16 pt, where they can be read.
    """
    import geopandas as gpd
    from matplotlib.lines import Line2D

    ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
    #: On a busy RRIM background a 2 px line disappears, so every outline
    #: gets a dark halo underneath it (path_effects) and the floor keeps a
    #: semi-transparent fill so the terrain still shows through.
    C_FLOOR, C_RIM, C_LONE = "#f2ff5a", "#2f8fff", "#ff3b30"
    ins = gpd.read_file(ANN, layer="pit_inside", engine="pyogrio")
    out = gpd.read_file(ANN, layer="pit_outside", engine="pyogrio")
    ins = ins[ins.geometry.notna()]
    out = out[out.geometry.notna()]
    ov = gpd.overlay(ins[["pit_inside_id", "geometry"]],
                     out[["pit_outside_id", "geometry"]],
                     how="intersection", keep_geom_type=True)
    ov["a"] = ov.area
    m = ov.sort_values("a", ascending=False).drop_duplicates("pit_inside_id")
    paired = set(m.pit_outside_id)

    cent = out.geometry.centroid
    h = 175
    # The annotation layers run far past 9t -- rims exist out to easting
    # 700,697. Picking the busiest window anywhere put the map outside every
    # terrain raster we have, which is why the basemap came back solid black.
    # Restrict the search to the 9t footprint, inset by the half-window so the
    # whole frame has terrain under it.
    T = (619500.0, 4593000.0, 624000.0, 4597500.0)
    inside = ((cent.x > T[0] + h) & (cent.x < T[2] - h)
              & (cent.y > T[1] + h) & (cent.y < T[3] - h))
    cand = out[inside.values]
    cc = cand.geometry.centroid
    # Rank every candidate window by how many rims it holds, and prefer one
    # that also contains an unpaired rim so the red case can be shown. Taking
    # the FIRST window with a lone rim gave a frame with two pits in it.
    ranked = []
    for i in range(len(cand)):
        x, y = cc.iloc[i].x, cc.iloc[i].y
        n = ((cc.x - x).abs() < h * 0.92) & ((cc.y - y).abs() < h * 0.92)
        lone = any(r not in paired
                   for r in cand.loc[n.values, "pit_outside_id"])
        ranked.append((int(n.sum()), bool(lone), float(x), float(y)))
    with_lone = [r for r in ranked if r[1]]
    pick = max(with_lone or ranked, key=lambda r: r[0])
    best, has_lone, bx, by = pick
    print(f"    window centre {bx:.0f},{by:.0f}  {best} rims"
          f"{' incl. an unpaired one' if has_lone else ''}")

    style()
    fig, ax = plt.subplots(figsize=(8.4, 8.4))

    # TERRAIN FIRST. Without it this is outlines floating on blank paper and
    # there is no way to see that the things being outlined are real dents in
    # the ground. RRIM if it is there, hillshade otherwise.
    import rasterio
    from rasterio.windows import from_bounds
    ext = (bx - h, by - h, bx + h, by + h)
    base = None
    for cand, is_rgb in ((D05 / "rrim_openness_9t_05.tif", True),
                         (D05 / "hillshade_9t_05.tif", False)):
        if not cand.exists():
            continue
        with rasterio.open(cand) as r:
            w = from_bounds(*ext, transform=r.transform)
            a = r.read(window=w, boundless=True, fill_value=0)
        if is_rgb and a.shape[0] >= 3:
            base = np.moveaxis(a[:3], 0, -1).astype("float32") / 255.0
            ax.imshow(np.clip(base, 0, 1),
                      extent=(ext[0], ext[2], ext[1], ext[3]),
                      origin="upper", interpolation="bilinear", zorder=0)
        else:
            g = a[0].astype("float32")
            g[g <= 0] = np.nan
            ax.imshow(g, extent=(ext[0], ext[2], ext[1], ext[3]),
                      origin="upper", cmap="gray", interpolation="bilinear",
                      zorder=0)
        base = cand.name
        break
    print(f"    basemap: {base}")

    so = out[(cent.x - bx).abs().lt(h) & (cent.y - by).abs().lt(h)]
    ci = ins.geometry.centroid
    si = ins[(ci.x - bx).abs().lt(h) & (ci.y - by).abs().lt(h)]
    import matplotlib.patheffects as pe
    halo = [pe.Stroke(linewidth=5.0, foreground="#14181c", alpha=0.85),
            pe.Normal()]
    for art in so.boundary.plot(ax=ax, color=C_RIM, linewidth=2.8,
                                zorder=3).collections[-1:]:
        art.set_path_effects(halo)
    si.plot(ax=ax, facecolor=C_FLOOR, edgecolor="#14181c", linewidth=1.4,
            alpha=0.55, zorder=4)
    lone = so[~so.pit_outside_id.isin(paired)]
    if len(lone):
        for art in lone.boundary.plot(ax=ax, color=C_LONE, linewidth=3.8,
                                      zorder=5).collections[-1:]:
            art.set_path_effects(halo)
        c = lone.geometry.centroid
        g = lone.geometry.iloc[
            int(((c.x - bx) ** 2 + (c.y - by) ** 2).to_numpy().argmin())]
        # Put the label on whichever side of the rim has room. Fixed to the
        # right, it ran straight off the frame for any rim near the east edge.
        to_left = g.centroid.x > bx
        ax.annotate("this rim has no floor inside it",
                    xy=(g.centroid.x, g.centroid.y),
                    xytext=(-18 if to_left else 18, 34),
                    ha="right" if to_left else "left",
                    textcoords="offset points", fontsize=14,
                    fontweight="bold", color=C_LONE,
                    arrowprops=dict(arrowstyle="-", color=C_LONE, lw=2.2),
                    zorder=6,
                    path_effects=[pe.withStroke(linewidth=4.0,
                                                foreground="#14181c")],
                    bbox=dict(boxstyle="round,pad=0.30", facecolor="#14181c",
                              edgecolor="none", alpha=0.72))
    ax.set_xlim(bx - h, bx + h)
    ax.set_ylim(by - h, by + h)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.legend(handles=[
        Patch(facecolor=C_FLOOR, edgecolor="#3a3a3a", label="floor"),
        Line2D([], [], color=C_RIM, lw=2.8, label="rim, paired with a floor"),
        Line2D([], [], color=C_LONE, lw=3.4, label="rim with no floor")],
        loc="upper center", bbox_to_anchor=(0.5, -0.012), ncol=1,
        fontsize=13, framealpha=1.0, facecolor="#ffffff", edgecolor=RULE)
    ax.text(0.5, 1.012, f"a real corner of the map, {2*h:.0f} m across",
            transform=ax.transAxes, fontsize=13, color=INK2, ha="center",
            va="bottom")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.955, bottom=0.135)
    return save(fig, "rim_floor_pairing_map_only_9t.png")


# ---------------------------------------------------------------------------
# slide 40a -- the 12x12 block split, MAP ONLY
# ---------------------------------------------------------------------------
def fig_block_grid_map():
    """The split map on its own. Panel b is a separate slide now.

    Dropped from the v5 panel: the UTM easting/northing axes. A grid reference
    in kilometres tells an audience nothing about whether the split is fair,
    and it was the busiest thing on the figure.
    """
    import geopandas as gpd
    import matplotlib.patches as mpatches

    b = gpd.read_file(ROOT / "data/9t/derived/05/pit_blocks_9t.gpkg",
                      layer="blocks", engine="pyogrio")
    style()
    fig, ax = plt.subplots(figsize=(8.4, 8.4))
    for _, r in b.iterrows():
        x0, y0, x1, y1 = r.geometry.bounds
        ax.add_patch(mpatches.Rectangle(
            (x0 / 1000, y0 / 1000), (x1 - x0) / 1000, (y1 - y0) / 1000,
            facecolor=SPLIT[r["split"]], alpha=0.88, edgecolor=PAPER,
            linewidth=1.8))
        if r["n_pits"] > 0:
            ax.text((x0 + x1) / 2000, (y0 + y1) / 2000, int(r["n_pits"]),
                    ha="center", va="center", fontsize=11,
                    color="white" if r["split"] != "unused" else INK2,
                    fontweight="bold")
    bl, bb, br, bt = b.total_bounds
    ax.set_xlim(bl / 1000, br / 1000)
    ax.set_ylim(bb / 1000, bt / 1000)
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_visible(False)
    ax.legend(handles=[mpatches.Patch(facecolor=SPLIT[s], label=s)
                       for s in ("train", "val", "test", "unused")],
              frameon=False, fontsize=14, ncol=4, loc="upper center",
              bbox_to_anchor=(0.5, -0.005))
    ax.text(0.5, 1.012, "each square is one block; the number is how many pit "
            "floors it holds", transform=ax.transAxes, fontsize=13,
            color=INK2, ha="center", va="bottom")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.955, bottom=0.085)
    return save(fig, "spatial_block_split_map_only_9t.png")


def main() -> int:
    print("v6 figures ->", OUT)
    fig_scan_angle_cone()
    fig_what_the_cut_cost()
    fig_where_ground_stops()
    fig_discarded_returns_accuracy()
    fig_split_blocks_vs_pits()
    fig_rim_floor_map()
    fig_block_grid_map()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
