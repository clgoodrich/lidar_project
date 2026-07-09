#!/usr/bin/env python3
"""Regenerate Figure 2 (detection-to-attribution workflow schematic).

The original PNG was committed without its generator. This script rebuilds it
faithfully and applies Glennie's margin-comment fixes:
  #1/#5  O2 relabeled "valley floor" -> "stream corridor"
  #5     ICESat-2 external control added as an explicit NASA-instrument input
         to the co-registration step (co-register to airborne lidar + ICESat-2)

Method schematic only -- no results shown (FINESST plan-only, DAPR-anonymous).

Reproduce:  python barlow/build/_fig_workflow.py
"""
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

OUT = Path(__file__).resolve().parents[1] / "docs" / "figures" / "fig_workflow.png"

BLUE = "#cfe0f3"; GRAY = "#e6e6e6"; GREEN = "#d6e8ce"
ORANGE = "#f6dcc0"; PURPLE = "#e0d4ee"; CTRL = "#dbe9f6"
EDGE = "#333333"

fig, ax = plt.subplots(figsize=(13.65, 9.53))
ax.set_xlim(0, 100); ax.set_ylim(0, 100); ax.axis("off")


def box(cx, cy, w, h, text, fc, fs=13, pad=0.35, lw=1.4, ec=EDGE, weight="normal"):
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle=f"round,pad={pad},rounding_size=1.4",
        fc=fc, ec=ec, lw=lw, mutation_aspect=1.0, zorder=2))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs,
            zorder=3, weight=weight)


def arrow(x0, y0, x1, y1, style="-|>", lw=1.6, ls="-", color=EDGE):
    ax.add_patch(FancyArrowPatch(
        (x0, y0), (x1, y1), arrowstyle=style, mutation_scale=18,
        lw=lw, ls=ls, color=color, shrinkA=0, shrinkB=0, zorder=1))


# ---- title ---------------------------------------------------------------
ax.text(50, 96.5, "Detection-to-attribution workflow (planned)",
        ha="center", va="center", fontsize=19)

# ---- top: three DEM epochs (w=19 at 22-unit pitch -> ~3-unit gaps) --------
box(30, 86, 19, 8, "2001 lidar DEM\nNASA ATM · 2 m", BLUE, fs=12)
box(52, 86, 19, 8, "2014 lidar DEM\nNCALM · 1 m", BLUE, fs=12)
box(74, 86, 19, 8, "2021–23 REMA\nsatellite · 2 m", BLUE, fs=12)

# ---- ICESat-2 external control (NASA instrument) -------------------------
# Glennie #5: show a current NASA instrument used as external control.
box(11, 69, 18, 10, "ICESat-2 control\nNASA · ATL06/08\nexternal elevation\ntie-point",
    CTRL, fs=10.5)

# ---- co-register bar -----------------------------------------------------
box(53, 69, 52, 8,
    "Co-register to airborne lidar + ICESat-2 control\n"
    "median bias → optional ICP · reproject EPSG:3294 · common grid",
    GRAY, fs=11)

for x in (30, 52, 74):
    arrow(x, 81.6, x, 73.2)        # epochs -> co-register bar
arrow(20.4, 69, 26.6, 69)          # ICESat-2 -> co-register bar

# ---- DEM-of-Difference ---------------------------------------------------
box(48, 58.5, 36, 6.4, "DEM-of-Difference (DoD)", GRAY, fs=13)
arrow(51, 64.6, 49, 61.9)

# ---- per-pixel detection floor ------------------------------------------
box(38, 48, 54, 6.6,
    "Per-pixel detection floor:  LOD95 = 1.96·√(NMAD₁² + NMAD₂²)",
    GRAY, fs=12)
arrow(46, 55.1, 42, 51.5)

# ---- O3 uncertainty (feeds the floor) -----------------------------------
box(83, 48, 27, 11,
    "O3 · uncertainty\nNMAD(slope, aspect, sensor)\n→ per-pixel threshold\n"
    "5% stable-ground check", PURPLE, fs=10.5)
arrow(69.1, 48, 65.4, 48)

# ---- O1 branch (green) ---------------------------------------------------
box(23, 33.5, 32, 8.4,
    "O1 · channels\nsum change in outline → rate (mm/yr)", GREEN, fs=11.5)
box(23, 21, 32, 8.4,
    "Driver table: PDD, insolation,\ndischarge, thaw, lake, glacier", GREEN, fs=11.5)
box(23, 8.5, 32, 8.4,
    "Attribution: hierarchical + RF\n(leave-one-stream-out CV)", GREEN, fs=11.5)

# ---- O2 branch (orange) --  Glennie #1/#5: valley floor -> stream corridor
box(67, 33.5, 32, 8.4,
    "O2 · stream corridor\nchange patches + attributes", ORANGE, fs=11.5)
box(67, 21, 32, 8.4,
    "Process classifier: channel /\nthermokarst / slope / fan / lake-margin",
    ORANGE, fs=11.5)
box(67, 8.5, 32, 8.4,
    "Per-class rates →\ndriver fingerprints (H2)", ORANGE, fs=11.5)

# floor -> O1 and O2
arrow(30, 44.4, 25, 38.1)
arrow(48, 44.4, 63, 38.1)
# vertical chains
arrow(23, 28.9, 23, 25.6); arrow(23, 16.4, 23, 13.1)
arrow(67, 28.9, 67, 25.6); arrow(67, 16.4, 67, 13.1)
# O1 attribution -> O2 per-class (dashed cross-link)
arrow(39.4, 8.5, 50.6, 8.5, ls="--", lw=1.5)

fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"wrote {OUT}")
