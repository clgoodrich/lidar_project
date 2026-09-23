# -*- coding: utf-8 -*-
"""A schematic of how a detector is scored: found, missed, extra.

Built for the v19 "How we score a detector" slide. It is a diagram, not data:
it shows what the three words mean before any real number appears.

    dashed ring    a feature drawn by hand (the answer key)
    blob in ring   the model flagged it            -> FOUND
    empty ring     the model did not flag it        -> MISSED
    blob, no ring  flagged, nothing drawn there     -> EXTRA

COLOUR -- the repo's validated lost/found palette (CLAUDE.md):
    found #1F5FA8, extra #D97706, missed #A31515.
    dataviz validate_palette.js --pairs all, light surface: worst pair
    #A31515/#D97706 dE 21.1 deutan, 22.6 normal; all >= 3:1 contrast on the
    validator's default surface #fcfcfb.
Against the slide background #F7F8F6 the validator WARNs that #D97706 sits
at 2.99:1 contrast. The relief it asks for is a visible label, which every
group has.
Colour is never the only encoding. Position carries it (inside a ring, empty
ring, no ring) and every group has a direct text label.

Run:
    .venv/Scripts/python.exe docs/presentation/v19_maps_and_plain_results/_build_scoring_schematic.py
Writes:
    docs/presentation/v19_maps_and_plain_results/figures/scoring_found_missed_extra_schematic.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Ellipse

OUT = Path(__file__).resolve().parent / "figures" / "scoring_found_missed_extra_schematic.png"
PAPER = "#F7F8F6"
INK = "#141A1F"
INK2 = "#545C63"
FOUND, EXTRA, MISSED = "#1F5FA8", "#D97706", "#A31515"


def ring(ax, x, y, color=INK, lw=2.2, ls=(0, (4, 3))):
    ax.add_patch(Circle((x, y), 0.62, fill=False, ec=color, lw=lw, ls=ls, zorder=3))


def blob(ax, x, y, color, w=0.78, h=0.62, ang=20):
    ax.add_patch(Ellipse((x, y), w, h, angle=ang, fc=color, ec="white",
                         lw=2, zorder=2))


fig, ax = plt.subplots(figsize=(8, 4.6), dpi=220)
fig.patch.set_facecolor(PAPER); ax.set_facecolor(PAPER)
ax.set_xlim(0, 12); ax.set_ylim(0, 6.6); ax.set_aspect("equal"); ax.axis("off")

# FOUND group: five rings, each with a blob inside
for i, (x, y) in enumerate([(0.9, 4.6), (2.5, 4.9), (1.6, 3.2), (3.3, 3.4), (0.9, 1.7)]):
    ring(ax, x, y)
    blob(ax, x + 0.05, y - 0.03, FOUND, ang=15 + 25 * i)
ax.text(2.1, 0.55, "found", ha="center", va="center", fontsize=17,
        color=INK, weight="bold", family="Calibri")
ax.text(2.1, 0.0, "drawn, and flagged", ha="center", va="center",
        fontsize=12, color=INK2, family="Calibri")

# MISSED group: rings with nothing inside, drawn solid in the missed colour
for x, y in [(5.6, 4.4), (6.9, 2.9)]:
    ring(ax, x, y, color=MISSED, lw=3.0, ls="solid")
ax.text(6.25, 0.55, "missed", ha="center", va="center", fontsize=17,
        color=INK, weight="bold", family="Calibri")
ax.text(6.25, 0.0, "drawn, not flagged", ha="center", va="center",
        fontsize=12, color=INK2, family="Calibri")

# EXTRA group: blobs with no ring
for i, (x, y) in enumerate([(9.5, 4.7), (10.9, 3.1), (9.3, 2.4)]):
    blob(ax, x, y, EXTRA, ang=40 * i)
ax.text(10.1, 0.55, "extra", ha="center", va="center", fontsize=17,
        color=INK, weight="bold", family="Calibri")
ax.text(10.1, 0.0, "flagged, nothing drawn", ha="center", va="center",
        fontsize=12, color=INK2, family="Calibri")

# thin separators between the groups
for x in (4.45, 8.15):
    ax.plot([x, x], [1.1, 6.2], color="#C9CDC6", lw=1.2, zorder=1)

OUT.parent.mkdir(parents=True, exist_ok=True)
fig.savefig(OUT, facecolor=PAPER, bbox_inches="tight", pad_inches=0.15)
print(f"wrote {OUT}")
