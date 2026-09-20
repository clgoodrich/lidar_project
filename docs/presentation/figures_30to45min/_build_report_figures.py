"""Charts for the plain-language report. One idea per image, nothing crammed.

Every figure here is a single chart with a sentence for a title, sized so it
reads on a phone. Nothing is hand-typed: each one loads the CSV that the
measurement script wrote, so a re-measurement redraws the report.

Sources
-------
    data/9t/results/nonground_classification/
        scan_angle_rate_curves.csv            the cliff, on one map square
        scan_angle_ground_stops_all_tiles.csv every map square in both surveys
        class1_height_by_return_position.csv  what the unlabelled points are
        excluded_returns_vertical_accuracy.csv how wrong the discarded ones are
        veg_structure_pad_pit_vs_ring.csv     canopy over old well sites
    data/9t/results/smrf_ground/
        smrf_vs_vendor_<tile>.csv             holes closed, surface movement
        ground_cell_status_<tile>_0p5m.tif    the map of holes

Run:
    python docs/presentation/figures_30to45min/_build_report_figures.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

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


ROOT = Path(__file__).resolve().parents[3]   # repo root; this file sits three deep
NGC = ROOT / "data" / "9t" / "results" / "nonground_classification"
SMRF = ROOT / "data" / "9t" / "results" / "smrf_ground"
OUT = _out(Path(__file__).resolve().parent / "1_data_qa")

#: A figure is a printed plate: one light ground in both page themes, so a
#: single PNG never has to serve two backgrounds.
PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
RULE = "#d7dad4"
#: Colourblind rule: a red/green pair is the one a deuteranope or
#: protanope cannot read, so no figure here contains both. Checked with
#: the dataviz validator over ALL pairs, not just adjacent ones.
#:   blue #1F5FA8  amber #D97706  deep red #A31515
#:   worst pair dE 21.1 deutan / 21.5 protan / 22.6 normal, all >= 3:1
GROUND = "#1F5FA8"      # kept by the vendor
LOST = "#A31515"        # thrown away
FOUND = "#D97706"       # recovered by our own pass
NEUTRAL = "#b9bdb6"
RECOVER = FOUND

plt.rcParams.update({
    "figure.facecolor": PAPER, "axes.facecolor": PAPER,
    "savefig.facecolor": PAPER, "font.family": "DejaVu Sans",
    "text.color": INK, "axes.labelcolor": INK2,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.titlesize": 19, "axes.labelsize": 13.5,
    "xtick.labelsize": 12.5, "ytick.labelsize": 12.5,
})


def frame(ax, xlab=None, ylab=None, title=None, grid="y"):
    if title:
        _chrome(ax.set_title, title, fontsize=19, fontweight="bold", loc="left", pad=14,
                     wrap=True)
    if xlab:
        ax.set_xlabel(xlab, labelpad=10)
    if ylab:
        ax.set_ylabel(ylab, labelpad=10)
    if grid:
        ax.grid(axis=grid, color=RULE, linewidth=0.9)
    ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(RULE)


def save(fig, name):
    p = OUT / name
    fig.savefig(p, dpi=170, bbox_inches="tight", pad_inches=0.28)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:6.0f} KB  {name}")


# --------------------------------------------------------------------------
def chart_cliff(cur):
    """The cliff, on every map square in the affected batch of flights.

    This was one map square until the census was run. One square could be a
    quirk of one square; 183 of them doing the same thing at the same angle
    cannot be.
    """
    block = "Venango 2020-03"
    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    n_sq = 0
    if "block" in cur:
        sq = cur[cur.block == block]
        n_sq = sq.tile.nunique()
        for _, g in sq.groupby("tile"):
            ax.plot(g.angle, g.pct_called_ground, color=GROUND,
                    linewidth=0.9, alpha=0.10, zorder=2)
        # median only where at least half the batch still has returns
        n = sq.groupby("angle").tile.nunique()
        v = (sq.groupby("angle", as_index=False).median(numeric_only=True)
             [lambda d: d.angle.map(n) >= 0.5 * n_sq])
    else:
        v = cur[cur.tile == "17TPF619593"]
    ax.plot(v.angle, v.pct_called_ground, color=GROUND, linewidth=3.4,
            marker="o", markersize=7, zorder=3)
    ax.fill_between(v.angle, 0, v.pct_called_ground, color=GROUND, alpha=0.12)
    if n_sq:
        ax.text(0.5, 8, f"one faint line for each of the {n_sq} map squares\n"
                "the thick line is the middle of them",
                fontsize=11.5, color=INK2, ha="left", va="bottom",
                linespacing=1.6)
    cut = 18.0
    ax.axvline(cut, color=LOST, linewidth=2.0, linestyle="--", zorder=2)
    ax.annotate("everything past here\nwas thrown away",
                xy=(cut + 0.25, 46), fontsize=13.5, color=LOST,
                fontweight="bold", ha="left", va="center")
    ax.set_ylim(-4, 108)
    ax.set_xlim(0, float(v.angle.max()) + 1)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    frame(ax, "how far off to the side the laser was aimed (degrees)",
          "kept as ground",
          "Laser hits that reached the ground, and whether they were kept")
    save(fig, "report_1_the_cliff_9t.png")


def chart_two_surveys(stops):
    """Every map square in both surveys, not a sample of seven.

    Two dots per square: where ground stops, and where the survey stopped
    recording. The bar between them is the band that was barred to ground.
    """
    d = stops[stops.data_stops > 1.0].copy()      # drop tiles with no angle recorded
    d["blk"] = d.area + " " + d.flown.str[:7]
    groups = [
        ("Venango 2020-03", "Venango, flown March 2020", "our study area"),
        ("Venango 2019-11", "Venango, flown November 2019", "same county, different flight"),
        ("McKean 2019-04", "McKean, flown April 2019", "a different survey"),
    ]
    groups = [g for g in groups if (d.blk == g[0]).any()]
    fig, ax = plt.subplots(figsize=(10.2, 6.6))
    rng = np.random.default_rng(42)
    for i, (key, name, sub) in enumerate(groups):
        g = d[d.blk == key]
        y = len(groups) - 1 - i + rng.uniform(-0.19, 0.19, len(g))
        for gs, ds, yy in zip(g.ground_stops, g.data_stops, y):
            if ds - gs > 0.05:
                ax.plot([gs, ds], [yy, yy], color=LOST, linewidth=1.3,
                        alpha=0.45, zorder=2, solid_capstyle="butt")
        ax.scatter(g.data_stops, y, s=26, color=LOST, alpha=0.8, zorder=3,
                   linewidths=0)
        ax.scatter(g.ground_stops, y, s=26, color=GROUND, alpha=0.9, zorder=4,
                   linewidths=0)
        yb = len(groups) - 1 - i
        ngap = int((g.data_stops - g.ground_stops >= 1.0).sum())
        tag = (f"{len(g)} map squares  \u00b7  {sub}  \u00b7  "
               f"{ngap} with a gap")
        ax.text(0.4, yb + 0.30, name, fontsize=14.5, fontweight="bold",
                color=INK, va="bottom")
        ax.text(0.4, yb + 0.30, "\n" + tag, fontsize=11.5, color=INK2,
                va="top")
    ax.scatter([], [], s=46, color=GROUND, label="widest angle that still has ground")
    ax.scatter([], [], s=46, color=LOST, label="widest angle the survey recorded")
    ax.legend(frameon=False, fontsize=12.5, loc="lower right", ncol=1)
    ax.set_ylim(-0.6, len(groups) - 0.05)
    ax.set_xlim(0, 34)
    ax.set_yticks([])
    frame(ax, "how far off to the side the laser was aimed (degrees)", None,
          "Where the ground stops, for every map square", grid="x")
    ax.spines["left"].set_visible(False)
    save(fig, "report_2_two_surveys_9t.png")


def chart_accuracy(acc):
    a = acc[acc.n > 0].copy()
    tiles = sorted(a.tile.unique())
    groups = [("excluded, wide angle", LOST, "thrown away"),
              ("accepted, wide angle", GROUND, "kept")]
    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    w = 0.33
    xs = np.arange(len(tiles))
    for i, (g, col, lab) in enumerate(groups):
        vals = [float(a[(a.tile == t) & (a.group == g)].rmse.iloc[0]) * 100
                for t in tiles]
        b = ax.bar(xs + (i - 0.5) * w, vals, width=w, color=col, label=lab)
        ax.bar_label(b, fmt="%.1f cm", fontsize=13, color=INK, padding=4,
                     fontweight="bold")
    ax.axhline(10, color=INK, linewidth=2.0, linestyle="--")
    ax.text(len(tiles) - 0.52, 10.4, "the limit allowed by the national standard",
            fontsize=12.5, color=INK, ha="right", va="bottom")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"map square {int(t)}" for t in tiles], fontsize=13)
    ax.set_ylim(0, 14)
    ax.legend(frameon=False, fontsize=13, loc="upper left")
    frame(ax, None, "how far off, on average (cm)",
          "The thrown-away hits are just as accurate as the kept ones")
    save(fig, "report_3_how_accurate_9t.png")


def chart_what_they_are(xt):
    p = xt.groupby("band").points.sum()
    order = ["high veg", "at ground", "medium veg", "low veg", "below ground"]
    nice = {"high veg": "high up in the trees",
            "at ground": "sitting right on the ground",
            "medium veg": "in the middle of the trees",
            "low veg": "in low bushes",
            "below ground": "below the ground surface"}
    cols = {"high veg": FOUND, "medium veg": FOUND, "low veg": FOUND,
            "at ground": LOST, "below ground": NEUTRAL}
    order = [b for b in order if b in p.index]
    vals = [100 * p[b] / p.sum() for b in order]
    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    y = np.arange(len(order))[::-1]
    ax.barh(y, vals, color=[cols[b] for b in order], height=0.68)
    for yy, v in zip(y, vals):
        ax.text(v + 1.0, yy, f"{v:.0f}%", va="center", fontsize=14,
                fontweight="bold", color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels([nice[b] for b in order], fontsize=13.5)
    ax.set_xlim(0, max(vals) + 10)
    ax.set_xticks([])
    frame(ax, None, None,
          "Where the unlabelled hits actually are", grid=None)
    ax.spines["left"].set_visible(False)
    save(fig, "report_4_what_they_are_9t.png")


def chart_holes(rows):
    fig, ax = plt.subplots(figsize=(9.6, 6.0))
    tiles = [r["tile"] for r in rows]
    before = [r["void_vendor_pct"] for r in rows]
    after = [r["void_smrf_pct"] for r in rows]
    xs = np.arange(len(tiles))
    w = 0.33
    b1 = ax.bar(xs - w / 2, before, width=w, color=LOST, label="before")
    b2 = ax.bar(xs + w / 2, after, width=w, color=FOUND, label="after")
    for b in (b1, b2):
        ax.bar_label(b, fmt="%.1f%%", fontsize=13.5, color=INK, padding=4,
                     fontweight="bold")
    ax.set_xticks(xs)
    ax.set_xticklabels([f"map square {int(t)}" for t in tiles], fontsize=13)
    ax.set_ylim(0, max(before) * 1.35)
    ax.set_yticks([])
    ax.legend(frameon=False, fontsize=13, loc="upper right")
    frame(ax, None, None,
          "Share of the map with no ground measurement at all", grid=None)
    ax.spines["left"].set_visible(False)
    save(fig, "report_5_holes_closed_9t.png")


def chart_where_changed(rows):
    r = rows[-1]
    labs = ["places that already had\na ground measurement",
            "the holes we just filled",
            "holes that are still empty"]
    vals = [r.get("dz_over10_status0", np.nan), r.get("dz_over10_status1", np.nan),
            r.get("dz_over10_status2", np.nan)]
    cols = [NEUTRAL, FOUND, LOST]
    fig, ax = plt.subplots(figsize=(9.6, 5.8))
    y = np.arange(len(labs))[::-1]
    ax.barh(y, vals, color=cols, height=0.62)
    for yy, v in zip(y, vals):
        ax.text(v + 0.6, yy, f"{v:.1f}%", va="center", fontsize=14.5,
                fontweight="bold", color=INK)
    ax.set_yticks(y)
    ax.set_yticklabels(labs, fontsize=13)
    ax.set_xlim(0, max(vals) * 1.25)
    ax.set_xticks([])
    frame(ax, None, None,
          "Where the ground map actually changed", grid=None)
    ax.spines["left"].set_visible(False)
    save(fig, "report_6_where_changed_9t.png")


def chart_trees(vs):
    h = vs[vs.metric == "h95"].copy()
    nice = {"pad": "flat work areas", "pit": "pits"}
    h["lab"] = [f"{nice.get(f.split('/')[1], f.split('/')[1])}\nin map square "
                f"{f.split('/')[0]}" for f in h.feature]
    h = h.sort_values("delta")
    fig, ax = plt.subplots(figsize=(9.6, 6.4))
    y = np.arange(len(h))[::-1]
    ax.barh(y + 0.19, h.ring, height=0.34, color=NEUTRAL,
            label="the forest around it")
    ax.barh(y - 0.19, h.inside, height=0.34, color=LOST,
            label="over the old well site")
    for yy, v in zip(y, h.delta):
        ax.text(max(h.ring) + 0.6, yy, f"{v:+.1f} m", va="center", fontsize=13.5,
                fontweight="bold", color=LOST)
    ax.set_yticks(y)
    ax.set_yticklabels(h.lab, fontsize=12)
    ax.set_xlim(0, max(h.ring) + 4.5)
    ax.legend(frameon=False, fontsize=13, loc="lower right")
    frame(ax, "how tall the trees are (metres)", None,
          "The trees are shorter over old well sites", grid="x")
    save(fig, "report_7_trees_shorter_9t.png")


def map_holes():
    import rasterio
    from matplotlib.colors import ListedColormap
    import matplotlib.patches as mp
    p = SMRF / "ground_cell_status_621594_0p5m.tif"
    if not p.exists():
        print(f"  MISSING {p}")
        return
    with rasterio.open(p) as r:
        a = r.read(1, out_shape=(1500, 1500)).astype("float32")
        b = r.bounds
    a[a == 3] = np.nan
    fig, ax = plt.subplots(figsize=(8.6, 8.8))
    ax.imshow(a, extent=[b.left, b.right, b.bottom, b.top], origin="upper",
              cmap=ListedColormap(["#e7e9e4", FOUND, LOST]), vmin=0, vmax=2,
              interpolation="nearest")
    ax.set_xticks([]); ax.set_yticks([]); ax.set_aspect("equal")
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.legend(handles=[
        mp.Patch(color="#e7e9e4", label="already had a ground measurement"),
        mp.Patch(color=FOUND, label="hole we filled"),
        mp.Patch(color=LOST, label="still empty")],
        frameon=True, facecolor="#ffffffdd", edgecolor=RULE, fontsize=12,
        loc="lower left")
    _chrome(ax.set_title, "The holes line up in stripes",
                 fontsize=19, fontweight="bold", loc="left", pad=14)
    bar = 300.0
    x0, y0 = b.left + 120, b.bottom + 120
    ax.plot([x0, x0 + bar], [y0, y0], color="white", linewidth=6,
            solid_capstyle="butt")
    ax.plot([x0, x0 + bar], [y0, y0], color=INK, linewidth=2.6,
            solid_capstyle="butt")
    ax.text(x0 + bar / 2, y0 + 60, "300 m", ha="center", fontsize=12.5,
            color=INK)
    save(fig, "report_8_holes_in_stripes_9t.png")


def main() -> int:
    print(f"writing to {OUT}")
    f = NGC / "scan_angle_rate_curves_all_tiles.csv"
    cur = pd.read_csv(f if f.exists() else NGC / "scan_angle_rate_curves.csv")
    chart_cliff(cur)
    chart_two_surveys(pd.read_csv(NGC / "scan_angle_ground_stops_all_tiles.csv"))
    chart_accuracy(pd.read_csv(NGC / "excluded_returns_vertical_accuracy.csv"))
    chart_what_they_are(pd.read_csv(NGC / "class1_height_by_return_position.csv"))
    rows = [pd.read_csv(SMRF / f"smrf_vs_vendor_{t}.csv").iloc[0].to_dict()
            for t in ("616591", "621594")
            if (SMRF / f"smrf_vs_vendor_{t}.csv").exists()]
    if rows:
        chart_holes(rows)
        chart_where_changed(rows)
    chart_trees(pd.read_csv(NGC / "veg_structure_pad_pit_vs_ring.csv"))
    map_holes()
    return 0


if __name__ == "__main__":
    sys.exit(main())
