# -*- coding: utf-8 -*-
"""Slide 14's flight-block bars, with the 2011 Venango row removed.

WHY THE ROW GOES
----------------
The 2011 Venango delivery stores 0.000 in the scan-angle field for every one of
its map squares -- the angle was never populated, so the block cannot be tested
for the cut at all. The v6 figure kept it as a hatched row labelled "this
delivery records no scan angle - it cannot be checked".

That was the honest choice when the row was the only place the exclusion was
stated. It no longer is: slide 13 now carries the line "Venango 2011 is
excluded: those squares record no scan angle at all". So the row repeats in
pictures what the previous slide already says in words, and it does it in the
weakest way a bar chart can -- a bar that means "no data" sitting in a chart
where every other bar means "measured angle". A reader comparing bar lengths
reads it as a fourth result. It is not a result.

Removing it leaves three blocks that were actually measured, which is what the
slide's own title claims: one survey, not all of them.

WHAT IS UNCHANGED
-----------------
Every number, the palette, the split-bar construction, the labels. Only the
unusable row is dropped and the canvas shortened to suit three rows instead of
four. Palette is imported from _build_v6_figures rather than copied, so it
cannot drift: kept #1F5FA8, discarded #D97706. That is the validated
lost/found pair -- worst pair dE 21.1 deutan, 22.6 normal, from the dataviz
validator run with --pairs all. No red/green pair appears in this figure.

Run:
    python docs/presentation/figures_30to45min/_where_ground_stops_by_flight_block_excl2011_9t.py
Reads:  data/9t/results/nonground_classification/
            scan_angle_cliff_by_acquisition_all_tiles.csv
Writes: docs/presentation/figures_30to45min/v6/
            where_ground_stops_by_flight_block_excl2011_9t.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from _build_v6_figures import (  # noqa: E402  palette and helpers, not copied
    GONE, INK, INK2, KEPT, MUTED, NGC, OUT, RULE, clean, style,
)

CSV = NGC / "scan_angle_cliff_by_acquisition_all_tiles.csv"
NAME = "where_ground_stops_by_flight_block_excl2011_9t.png"


def main() -> int:
    if not CSV.exists():
        raise SystemExit(f"missing: {CSV}")
    d = pd.read_csv(CSV)

    rows, dropped = [], []
    for blk, g in d.groupby("block"):
        cut = g["cut"].dropna()
        mx = float(g["max_ang"].median())
        rec = dict(block=blk, n=len(g), n_cut=len(cut),
                   cut=float(cut.median()) if len(cut) else None,
                   mx=mx, lost=int(g["lost"].sum()))
        (dropped if mx <= 0.0 else rows).append(rec)
    rows.sort(key=lambda r: -r["n_cut"])

    for r in dropped:
        print(f"  dropped  {r['block']}  {r['n']} map squares  "
              f"(scan angle never populated)")
    if not dropped:
        print("  note: no unusable block found in the CSV; nothing was dropped")
    print(f"  keeping {len(rows)} measured blocks")

    style()
    # 6.4 in carried four rows; three rows keep the same row pitch.
    fig, ax = plt.subplots(figsize=(12.6, 6.4 * len(rows) / 4 + 0.55))
    h = 0.44
    for i, r in enumerate(rows):
        y = len(rows) - 1 - i
        stop = r["cut"] if r["cut"] else r["mx"]
        ax.barh(y, stop, height=h, color=KEPT, zorder=3)
        ax.text(stop / 2, y, "called ground", color="white", fontsize=13,
                fontweight="bold", ha="center", va="center", zorder=4)
        if r["cut"]:
            ax.barh(y, r["mx"] - stop, left=stop, height=h, color=GONE,
                    zorder=3)
            ax.text(r["mx"] + 0.7, y,
                    f"{r['lost']/1e6:.0f} million returns thrown away",
                    fontsize=13, fontweight="bold", color=GONE,
                    va="center", ha="left")
            ax.text(stop, y + h / 2 + 0.07, f"stops at {stop:.0f}\u00b0",
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
    fig.subplots_adjust(left=0.215, right=0.995, top=0.96, bottom=0.145)

    p = OUT / NAME
    fig.savefig(p, dpi=150)
    plt.close(fig)
    from PIL import Image
    print(f"\n  {Image.open(p).size[0]}x{Image.open(p).size[1]} px")
    print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
