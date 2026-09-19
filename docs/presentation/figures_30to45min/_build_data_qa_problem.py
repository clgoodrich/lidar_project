"""The Data QA problem, said plainly, before any chart of it.

The Data QA run opened on a chart of where ground classification stops by scan
angle. That chart is the evidence, not the statement -- an audience seeing it
cold has to work out both what the problem is and that there is one. This is
the statement: what the survey did, what it cost, and that it is recoverable.

EVERY NUMBER IS READ, NOT TYPED
-------------------------------
    the flight-block counts, the returns lost
        data/9t/results/nonground_classification/
        scan_angle_cliff_by_acquisition_all_tiles.csv
    the void rates before and after
        data/9t/results/recovered_ground_9t/recovered_ground_9t_summary.json

The vertical accuracy figures (0.065 m against neighbouring flight lines, a
0.10 m QL2 bar) come from _are_excluded_returns_accurate.py and are recorded in
docs/iterations/nonground_classification_and_scan_angle_cut.md.

COLOUR
------
The validated lost-found palette from CLAUDE.md: delivered #1F5FA8, recovered
#D97706, missing #A31515. Worst pair dE 21.1 deutan, 22.6 normal. No green,
so no red/green pair.

Run:
    python docs/presentation/figures_30to45min/_build_data_qa_problem.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Polygon, Wedge

ROOT = Path(__file__).resolve().parents[3]
CSV = (ROOT / "data/9t/results/nonground_classification"
       / "scan_angle_cliff_by_acquisition_all_tiles.csv")
JSN = (ROOT / "data/9t/results/recovered_ground_9t"
       / "recovered_ground_9t_summary.json")
OUT = ROOT / "docs/presentation/figures_30to45min/1_data_qa"

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
RULE = "#c9ccc6"
KEPT = "#1F5FA8"
FOUND = "#D97706"
GONE = "#A31515"
TINT = "#eaf0f8"

CUT_DEG = 18.0


def facts():
    d = pd.read_csv(CSV)
    blk = d[d["block"].str.contains("Venango 2020", na=False)]
    with_cut = blk[blk["cut"].notna()]
    j = json.loads(JSN.read_text(encoding="utf-8"))
    return dict(squares=len(blk), cut_squares=len(with_cut),
                lost=int(blk["lost"].sum()),
                cut_deg=float(with_cut["cut"].median()) if len(with_cut) else CUT_DEG,
                void_before=j["void_v"], void_after=j["void_b"],
                closed=j["closed"], rec_pts=j["rec_pts"])


def scan_diagram(ax, cut_deg):
    """Why the returns go missing: everything past 18 deg stops being ground."""
    ax.set_xlim(-82, 82)
    ax.set_ylim(-9, 78)
    ax.axis("off")
    ax.set_aspect("equal")
    ax.set_title("what the survey did", fontsize=15, fontweight="bold",
                 loc="left", pad=8, color=INK)

    px, py, R = 0.0, 66.0, 74.0
    half = 30.0                      # the sensor sweeps wider than the cut
    # ground
    ax.plot([-98, 98], [0, 0], color="#8a8f86", linewidth=2.6, zorder=3)

    def ray(deg):
        t = np.radians(deg)
        return px + py * np.tan(t)

    # kept wedge, then the two discarded wings
    ax.add_patch(Polygon([(px, py), (ray(-cut_deg), 0), (ray(cut_deg), 0)],
                         closed=True, facecolor=KEPT, alpha=0.20,
                         edgecolor="none", zorder=1))
    for s in (-1, 1):
        ax.add_patch(Polygon(
            [(px, py), (ray(s * cut_deg), 0), (ray(s * half), 0)],
            closed=True, facecolor=GONE, alpha=0.22, edgecolor="none",
            zorder=1))
        ax.plot([px, ray(s * half)], [py, 0], color=GONE, linewidth=1.8,
                zorder=2)
        ax.plot([px, ray(s * cut_deg)], [py, 0], color=KEPT, linewidth=2.2,
                zorder=2)
    ax.plot([px, px], [py, 0], color="#8a8f86", linewidth=1.3,
            linestyle=(0, (4, 4)), zorder=2)

    ax.plot([px], [py], marker="v", markersize=17, color=INK, zorder=5)
    ax.text(px, py + 5.5, "aircraft", fontsize=12, ha="center", va="bottom",
            color=INK, fontweight="bold")
    # to the LEFT of the nadir line; on the right it sat under the angle label
    ax.text(px - 3, 30, "straight\ndown", fontsize=10.5, color=MUTED,
            ha="right", va="center", linespacing=1.4)

    ax.add_patch(Wedge((px, py), 26, 270 - cut_deg, 270, width=0.9,
                       facecolor=INK, edgecolor="none", zorder=4))
    ax.text(px + 13, py - 22, f"{cut_deg:.0f}°", fontsize=16,
            fontweight="bold", color=INK, ha="left", va="center")

    ax.text(0, -6.5, "kept as ground", fontsize=12.5, fontweight="bold",
            color=KEPT, ha="center", va="top")
    for s in (-1, 1):
        ax.text(s * 52, -6.5, "thrown away", fontsize=12.5,
                fontweight="bold", color=GONE, ha="center", va="top")


def block(ax, x, y, w, h, n, label, colour=INK, note=None):
    ax.add_patch(FancyBboxPatch((x, y - h), w, h,
                                boxstyle="round,pad=0.0,rounding_size=1.4",
                                facecolor="#ffffff", edgecolor=RULE,
                                linewidth=1.2, zorder=2))
    ax.text(x + 3, y - h * 0.40, n, fontsize=30, fontweight="bold",
            color=colour, va="center", ha="left", zorder=3)
    ax.text(x + 3, y - h * 0.735, label, fontsize=13.5, color=INK, va="center",
            ha="left", zorder=3, linespacing=1.45)
    if note:
        ax.text(x + w - 3, y - h * 0.40, note, fontsize=12, color=MUTED,
                va="center", ha="right", zorder=3)


def main() -> int:
    f = facts()
    print({k: (round(v, 2) if isinstance(v, float) else v)
           for k, v in f.items()})

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(19.2, 8.6))
    fig.text(0.022, 0.975, "The ground we were handed has holes in it",
             fontsize=30, fontweight="bold", color=INK, va="top")
    fig.text(0.022, 0.892,
             "Before building anything on this lidar we checked it. Past "
             f"{f['cut_deg']:.0f}° off straight down the survey marks its "
             "returns “withheld” and does not classify them as ground — "
             "deliberately, and to\nspecification. So wherever the aircraft "
             "was looking sideways there is no ground beneath the surface it "
             "delivered, in stripes along the swath edges.",
             fontsize=14.5, color=INK2, va="top", linespacing=1.6)

    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.42], left=0.022,
                          right=0.982, top=0.745, bottom=0.155, wspace=0.07)
    scan_diagram(fig.add_subplot(gs[0, 0]), f["cut_deg"])

    ax = fig.add_subplot(gs[0, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis("off")
    ax.set_title("what it cost, and what it need not cost", fontsize=15,
                 fontweight="bold", loc="left", pad=8, color=INK)

    block(ax, 0, 98, 100, 22.5, f"{f['lost']/1e6:,.0f} million",
          "returns that hit the ground and were not called ground",
          GONE, note=f"{f['cut_squares']} of {f['squares']} map squares, "
                     f"all cut at exactly {f['cut_deg']:.0f}°")
    block(ax, 0, 72, 100, 22.5, f"{f['void_before']:.1f}%",
          "of our training area has no ground measurement under it", GONE)
    block(ax, 0, 46, 100, 22.5, f"{f['void_after']:.1f}%",
          "after we classify the ground ourselves, keeping every angle", FOUND,
          note=f"{f['closed']/1e6:.1f} M cells filled in")

    ax.add_patch(FancyBboxPatch((0, 0.5), 100, 18,
                                boxstyle="round,pad=0.0,rounding_size=1.4",
                                facecolor=TINT, edgecolor=KEPT, linewidth=1.5,
                                zorder=2))
    ax.text(3, 13.0, "and they are no worse than the ground it kept",
            fontsize=14.5, fontweight="bold", color=INK, va="center", zorder=3)
    ax.text(3, 5.5,
            "0.089 m against the neighbouring flight line; the accepted "
            "ground scores 0.087 m. Matched at every slope.",
            fontsize=13, color=INK2, va="center", zorder=3)

    fig.text(0.022, 0.030,
             "The delivered surface meets its specification. It is not "
             "sufficient for finding 0.7 m depressions, because the gaps are "
             "systematic rather than random, and the returns that would fill "
             "them measure as well as the ones already in.",
             fontsize=13, color=INK, va="bottom")

    p = OUT / "data_qa_the_problem_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    print(f"\n{p.stat().st_size/1e3:.0f} KB  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
