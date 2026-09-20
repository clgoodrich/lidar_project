"""How do the two final DEMs actually compare, once the discarded ground is in?

THE QUESTION
------------
The Data QA section shows that 13.8% of the training area has no ground
measurement, and that putting the discarded returns back closes most of it.
What it never answered is the obvious follow-up: so how different are the two
surfaces? A void that gets filled is only interesting if the filled value
differs from what interpolation was already guessing.

WHAT IS COMPARED
----------------
    A  dem_vendorground_9t_0p5m.tif                  the vendor's ground only
    B  dem_vendorplusrecovered_slope0p35_9t_0p5m.tif vendor + the returns it
                                                     discarded, SMRF-classified

Both are on the same 0.5 m grid over the same bounds, built by the same
gridding code in _recovered_ground_maps_9t.py, so a cell-by-cell difference is
meaningful without any resampling.

THE SPLIT THAT MATTERS
----------------------
Averaging dz over the whole tile answers nothing, because most cells had ground
in both and are identical by construction. The tile is cut three ways:

    HAD GROUND IN BOTH   the control. If these move, something is wrong.
    FILLED               no vendor ground, ground after recovery. This is the
                         population the whole exercise is about.
    STILL EMPTY          no ground either way, mostly canopy.

For FILLED cells there is no vendor elevation to difference against, so the
comparison is against what the vendor surface INTERPOLATED there -- which is
exactly the number a downstream model would have consumed.

Outputs (data/9t/results/recovered_ground_9t/):
    vendor_vs_recovered_dem_comparison_9t.json
    docs/presentation/figures_30to45min/v6/
        dem_vendor_vs_recovered_difference_9t.png

Run:
    python notebooks/wellsight_v2/s7_analysis/_compare_vendor_vs_recovered_dem_9t.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio

ROOT = Path(__file__).resolve().parents[3]
RG = ROOT / "data/9t/results/recovered_ground_9t"
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

A_PATH = RG / "dem_vendorground_9t_0p5m.tif"
B_PATH = RG / "dem_vendorplusrecovered_slope0p35_9t_0p5m.tif"
CNT_V = RG / "count_vendorground_9t_0p5m.tif"
CNT_R = RG / "count_recoveredground_slope0p35_9t_0p5m.tif"

PAPER, INK, INK2 = "#f7f8f6", "#141a1f", "#545c63"
MUTED, RULE = "#8a887e", "#c9ccc6"
KEPT, GONE, MISS = "#1F5FA8", "#D97706", "#A31515"


def read(p):
    with rasterio.open(p) as r:
        a = r.read(1).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    a[a < -1000] = np.nan
    return a


def main() -> int:
    A, B = read(A_PATH), read(B_PATH)
    cv = np.nan_to_num(read(CNT_V))
    cr = np.nan_to_num(read(CNT_R))
    print(f"grid {A.shape}, {A.size/1e6:.1f} M cells at 0.5 m")

    had = (cv > 0)                       # vendor already had ground here
    filled = (cv == 0) & (cr > 0)        # recovered ground where there was none
    both_val = np.isfinite(A) & np.isfinite(B)

    dz = B - A
    out = {"grid_cells": int(A.size)}

    for name, m in (("had_ground_in_both", had & both_val),
                    ("filled_by_recovery", filled & both_val)):
        d = dz[m]
        d = d[np.isfinite(d)]
        out[name] = dict(
            cells=int(m.sum()), n=int(d.size),
            median=float(np.median(d)) if d.size else None,
            mean=float(d.mean()) if d.size else None,
            p95_abs=float(np.percentile(np.abs(d), 95)) if d.size else None,
            pct_over_10cm=float(100 * np.mean(np.abs(d) > 0.10)) if d.size else None,
            pct_over_50cm=float(100 * np.mean(np.abs(d) > 0.50)) if d.size else None)
        s = out[name]
        print(f"\n{name}: {s['cells']:,} cells")
        if s["n"]:
            print(f"   median dz {s['median']:+.4f} m   p95|dz| {s['p95_abs']:.3f} m"
                  f"   >10 cm {s['pct_over_10cm']:.1f}%"
                  f"   >50 cm {s['pct_over_50cm']:.1f}%")

    # ---- the figure: two histograms, one per population -----------------
    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(12.6, 6.2))
    bins = np.linspace(-1.5, 1.5, 121)
    for m, col, lab in ((had & both_val, KEPT,
                         "cells the vendor already had ground for"),
                        (filled & both_val, GONE,
                         "cells filled in by the recovered ground")):
        d = dz[m]
        d = d[np.isfinite(d)]
        if not d.size:
            continue
        ax.hist(d, bins=bins, density=True, histtype="step", linewidth=2.6,
                color=col, label=f"{lab}   (n = {d.size:,})")
    ax.axvline(0, color=MUTED, linewidth=1.2, zorder=0)
    ax.set_xlabel("new surface minus old surface, metres", fontsize=13)
    ax.set_ylabel("share of cells", fontsize=13)
    ax.set_xlim(-1.5, 1.5)
    for s, sp in ax.spines.items():
        sp.set_visible(s == "bottom")
        sp.set_color(RULE)
    ax.tick_params(length=0)
    ax.set_yticks([])
    ax.grid(axis="x", color=RULE, linewidth=0.7)
    lg = ax.legend(loc="upper left", frameon=False, fontsize=13)
    for t in lg.get_texts():
        t.set_color(INK)

    f = out["filled_by_recovery"]
    h = out["had_ground_in_both"]
    ax.text(0.985, 0.94,
            f"where ground already existed, the surface does not move\n"
            f"median {h['median']:+.3f} m, {h['pct_over_10cm']:.1f}% of cells "
            f"beyond 10 cm\n\n"
            f"where it was filled in, it moves and it should\n"
            f"median {f['median']:+.3f} m, {f['pct_over_10cm']:.0f}% of cells "
            f"beyond 10 cm",
            transform=ax.transAxes, ha="right", va="top", fontsize=12.5,
            color=INK2, linespacing=1.6)
    fig.subplots_adjust(left=0.05, right=0.985, top=0.97, bottom=0.12)
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "dem_vendor_vs_recovered_difference_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)

    j = RG / "vendor_vs_recovered_dem_comparison_9t.json"
    j.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n  {p}\n  {j}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
