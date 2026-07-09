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
ax.text(50, 97.5, "Detection-to-attribution workflow (planned)",
        ha="center", va="center", fontsize=19)

# ---- top: three DEM epochs ----------------------------------------------
box(31, 83, 21, 8, "2001 lidar DEM\nNASA ATM  ·  2 m", BLUE)
box(52, 83, 21, 8, "2014 lidar DEM\nNCALM  ·  1 m", BLUE)
box(73, 83, 21, 8, "2021–23 REMA\nsatellite  ·  2 m", BLUE)

# ---- ICESat-2 external control (NASA instrument) -------------------------
# Glennie #5: show a current NASA instrument used as external control.
box(11.5, 68, 19, 9, "ICESat-2 control\nNASA · ATL06/08\nexternal elevation\ntie-point",
    CTRL, fs=11)

# ---- co-register bar -----------------------------------------------------
box(52, 68, 54, 8,
    "Co-register to airborne lidar + ICESat-2 control\n"
    "median bias → optional ICP  ·  reproject EPSG:3294  ·  common grid",
    GRAY, fs=11)

for x in (31, 52, 73):
    arrow(x, 79, x, 72.2)          # epochs -> co-register bar
arrow(21.2, 68, 24.8, 68)          # ICESat-2 -> co-register bar

# ---- DEM-of-Difference ---------------------------------------------------
box(46, 58, 40, 6.4, "DEM-of-Difference (DoD)", GRAY, fs=14)
arrow(48, 63.8, 46, 61.3)

# ---- per-pixel detection floor ------------------------------------------
box(43, 47.5, 58, 6.6,
    "Per-pixel detection floor:  LOD95 = 1.96·√(NMAD₁² + NMAD₂²)",
    GRAY, fs=13)
arrow(46, 54.8, 44, 50.8)

# ---- O3 uncertainty (feeds the floor) -----------------------------------
box(84, 47.5, 28, 11,
    "O3 · uncertainty\nNMAD(slope, aspect, sensor)\n→ per-pixel threshold\n"
    "5% stable-ground check", PURPLE, fs=11.5)
arrow(69.8, 47.5, 72.2, 47.5)

# ---- O1 branch (green) ---------------------------------------------------
box(24, 33.5, 30, 8.4,
    "O1 · channels\nsum change in outline → rate (mm/yr)", GREEN, fs=12)
box(24, 21, 30, 8.4,
    "Driver table: PDD, insolation,\ndischarge, thaw, lake, glacier", GREEN, fs=12)
box(24, 8.5, 30, 8.4,
    "Attribution: hierarchical + RF\n(leave-one-stream-out CV)", GREEN, fs=12)

# ---- O2 branch (orange) --  Glennie #1/#5: valley floor -> stream corridor
box(66, 33.5, 30, 8.4,
    "O2 · stream corridor\nchange patches + attributes", ORANGE, fs=12)
box(66, 21, 30, 8.4,
    "Process classifier: channel /\nthermokarst / slope / fan / lake-margin",
    ORANGE, fs=12)
box(66, 8.5, 30, 8.4,
    "Per-class rates →\ndriver fingerprints (H2)", ORANGE, fs=12)

# floor -> O1 and O2
arrow(35, 44.2, 26, 37.7)
arrow(52, 44.2, 63, 37.7)
# vertical chains
arrow(24, 29.3, 24, 25.2); arrow(24, 16.8, 24, 12.7)
arrow(66, 29.3, 66, 25.2); arrow(66, 16.8, 66, 12.7)
# O1 attribution -> O2 per-class (dashed cross-link)
arrow(39, 8.5, 51, 8.5, ls="--", lw=1.5)

fig.savefig(OUT, dpi=200, bbox_inches="tight", facecolor="white")
plt.close(fig)
print(f"wrote {OUT}")
