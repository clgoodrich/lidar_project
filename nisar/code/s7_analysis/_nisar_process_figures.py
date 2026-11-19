"""Figures for nisar/docs/NISAR_PROCESS_AND_OUTCOMES.md (2026-11-18).

The style is plain and editorial. No flowchart boxes. Each figure shows one idea from the doc.
  1 nisar_dates_on_hand.png       every NISAR pass per track and area. Empty passes, the spring gap and beta/provisional
  2 nisar_excess_number_line.png  how the +0.25 dB pit excess is built, on one dB line
  3 nisar_ps_selection_plane.png  persistent-scatterer selection (step 1) as a region of steadiness x brightness
  4 nisar_position_cross_section.png  why NASA's placement was 8-12 m off under canopy, and what we used
  5 nisar_evidence_ladder.png     how far each marker idea climbed before it stopped
  6 nisar_band_count_waffle.png   the 346 bands, one square each, by product

Dates come from the window index CSVs. Every other number is quoted from the process doc, sections 2-7.
Palette: #1F5FA8 blue, #D97706 orange, #A31515 dark red; greys are context only, never a category.
Validator (dataviz validate_palette.js, light, --pairs all) on the three colours: the repo's lost/found
palette, worst pair dE 21.1 deutan, 22.6 normal (CLAUDE.md). Grey #6B7280 fails the chroma floor, so it is
used only for neutral context and always with a direct label.

Writes nisar/docs/figures/<name>.png
  python nisar/code/s7_analysis/_nisar_process_figures.py
"""
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon, Rectangle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "nisar" / "docs" / "figures"
BLUE, ORANGE, RED = "#1F5FA8", "#D97706", "#A31515"
INK, MUTED, FAINT, PAPER = "#1C1F24", "#6B7280", "#D9DCE0", "#FCFCFB"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "text.color": INK, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "figure.facecolor": PAPER, "axes.facecolor": PAPER, "savefig.facecolor": PAPER})


def bare(ax, keep=()):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print(OUT / name)


def fig_dates():
    rows = []
    for area in ("9t", "613590"):
        d = pd.read_csv(ROOT / "nisar" / "derived" / area / "nisar_gslc_5m" / f"nisar_gslc_window_index_{area}_5m.csv")
        d["area"] = area
        rows.append(d)
    d = pd.concat(rows)
    d["t"] = pd.to_datetime(d.date)
    fig, ax = plt.subplots(figsize=(11, 4.2))
    lanes = [("9t", 26), ("9t", 90), ("9t", 162), ("613590", 26), ("613590", 90), ("613590", 162)]
    gap0, gap1 = pd.Timestamp("2026-01-21"), pd.Timestamp("2026-06-19")
    ax.axvspan(gap0, gap1, color=FAINT, alpha=0.45, lw=0, hatch="////", ec="#B8BEC6")
    ax.text(gap0 + (gap1 - gap0) / 2, 6.35, "spring gap\nrecorded, not yet released\nover our frames",
            ha="center", va="bottom", fontsize=8.5, color=MUTED)
    for i, (area, trk) in enumerate(lanes):
        y = len(lanes) - i
        ax.hlines(y, pd.Timestamp("2025-10-15"), pd.Timestamp("2026-10-31"), color=FAINT, lw=0.8)
        s = d[(d.area == area) & (d.track == trk)]
        ok = s[s.valid_fraction >= 0.5]
        bad = s[s.valid_fraction < 0.5]
        for c, col in (("beta", BLUE), ("provisional", ORANGE)):
            k = ok[ok.collection == c]
            ax.vlines(k.t, y - 0.32, y + 0.32, color=col, lw=2.4)
        ax.scatter(bad.t, [y] * len(bad), marker="x", s=22, color=MUTED, lw=1)
        ax.text(pd.Timestamp("2025-10-08"), y, f"{area}  t{trk:03d}", ha="right", va="center", fontsize=9)
        ax.text(pd.Timestamp("2026-11-06"), y, f"{len(ok)}", ha="left", va="center", fontsize=10, weight="bold")
    ax.axhline(3.5, color=MUTED, lw=0.6)
    ax.text(pd.Timestamp("2026-11-06"), 6.75, "usable", fontsize=8, color=MUTED)
    ax.set_ylim(0.4, 7.4)
    ax.set_yticks([])
    bare(ax, keep=("bottom",))
    ax.xaxis.set_major_formatter(plt.matplotlib.dates.DateFormatter("%b\n%Y"))
    ax.text(pd.Timestamp("2025-10-20"), 7.25, "▍beta (not fully calibrated)", color=BLUE, fontsize=9)
    ax.text(pd.Timestamp("2026-07-20"), 7.25, "▍provisional", color=ORANGE, fontsize=9)
    ax.text(pd.Timestamp("2026-09-20"), 7.25, "× window empty", color=MUTED, fontsize=9)
    ax.set_title("Every NISAR pass over the two tiles. Season and processing level move together.",
                 loc="left", fontsize=11, pad=22)
    save(fig, "nisar_dates_on_hand.png")


def fig_excess():
    fig, ax = plt.subplots(figsize=(10, 3.3))
    ax.axhline(0, color=INK, lw=1)
    for v in np.arange(-0.5, 0.31, 0.1):
        ax.vlines(v, -0.04, 0.04, color=INK, lw=0.8)
        ax.text(v, -0.13, f"{v:+.1f}" if abs(v) > 1e-9 else "0", ha="center", fontsize=8.5, color=MUTED)
    ax.text(0.33, -0.13, "dB, fall HH, contrast with own ring", fontsize=8.5, color=MUTED, va="center")
    ax.plot(-0.12, 0, "o", ms=11, color=BLUE, mec=PAPER, mew=2, zorder=3)
    ax.plot(-0.39, 0, "s", ms=11, color=ORANGE, mec=PAPER, mew=2, zorder=3)
    ax.text(-0.12, 0.17, "pits\n−0.12", ha="center", fontsize=9.5, color=INK)
    ax.text(-0.39, 0.17, "control spots\n−0.39", ha="center", fontsize=9.5, color=INK)
    ax.annotate("", xy=(-0.12, -0.42), xytext=(-0.39, -0.42), arrowprops=dict(arrowstyle="<->", color=INK, lw=1.2))
    ax.text(-0.255, -0.36, "excess +0.25 dB (p 0.0002)", ha="center", fontsize=10, weight="bold")
    ax.plot([-0.29, 0.04], [-0.55, -0.55], color=BLUE, lw=5, alpha=0.35, solid_capstyle="butt")
    ax.vlines([-0.29, 0.04], -0.59, -0.51, color=BLUE, lw=1)
    ax.text(0.06, -0.55, "where the pits could sit, given the 95% interval\nof the excess (0.10 to 0.43 dB above control spots)",
            va="center", fontsize=8.5, color=INK)
    ax.text(-0.52, 0.55, "Most of the excess is control spots being dark, not pits standing out.",
            fontsize=11, ha="left")
    ax.set_xlim(-0.55, 0.62)
    ax.set_ylim(-0.7, 0.68)
    ax.axis("off")
    save(fig, "nisar_excess_number_line.png")


def fig_ps():
    fig, ax = plt.subplots(figsize=(8, 5.2))
    ax.add_patch(Rectangle((0, 6), 0.25, 16, color=BLUE, alpha=0.12, lw=0))
    ax.plot([0.25, 0.25], [6, 22], color=BLUE, lw=1.5)
    ax.plot([0, 0.25], [6, 6], color=BLUE, lw=1.5)
    ax.text(0.012, 21, "selected\npersistent scatterers", color=BLUE, fontsize=9.5, va="top", weight="bold")
    ax.text(0.012, 9.0, "0.004 to 0.03% of pixels\nqualify", color=INK, fontsize=8.5, va="top")
    ax.axvspan(0.44, 0.58, color=FAINT, alpha=0.6, lw=0)
    ax.text(0.51, 19, "forest\nnear 0.5", ha="center", fontsize=9, color=MUTED)
    ax.axvline(0.53, color=MUTED, lw=0.8, ls=(0, (2, 2)))
    ax.text(0.535, 1.2, "pure speckle 0.53", fontsize=8, color=MUTED, rotation=90, va="bottom")
    ax.plot(0.09, 17.7, marker="*", ms=17, color=ORANGE, mec=PAPER, mew=1.5, zorder=4)
    ax.text(0.105, 18.3, "the building, 2026-11-13\nall 3 tracks, D_A 0.09, +17.7 dB", fontsize=8.5)
    ax.text(0.27, 10.5, "what a well must do:\nlight up a 5 m pixel\nalso holding trees and ground", fontsize=8.5,
            color=INK)
    ax.text(0.27, 3.6, "Wells within 15 m of a selected pixel\n9t 1 to 2%  ·  control spots 0.3 to 1%\nWarren 3.9%  ·  random 5.2%",
            fontsize=8.5, color=INK)
    ax.set_xlim(0, 0.62)
    ax.set_ylim(0, 22)
    ax.set_xlabel("steadiness D_A  (spread of brightness over dates / mean)   ← steadier")
    ax.set_ylabel("brightness above 250 m median (dB)")
    bare(ax, keep=("left", "bottom"))
    ax.set_title("Persistent-scatterer selection is a corner of this plane. Wells rarely reach it.",
                 loc="left", fontsize=11)
    save(fig, "nisar_ps_selection_plane.png")


def fig_cross_section():
    fig, ax = plt.subplots(figsize=(10, 4.6))
    x = np.linspace(0, 100, 400)
    ground = 4 + 2 * np.sin(x / 18)
    ax.fill_between(x, 0, ground, color="#C9B79C", lw=0)
    rng = np.random.default_rng(3)
    for cx in np.arange(4, 100, 7.5):
        h = rng.uniform(17, 23)
        g = 4 + 2 * np.sin(cx / 18)
        ax.plot([cx, cx], [g, g + h * 0.6], color="#8C7A62", lw=1.2)
        ax.add_patch(plt.Circle((cx, g + h * 0.75), 4.3, color="#BFC6CC", alpha=0.7, lw=0))
    ax.plot(x, ground + 11, color=RED, lw=2, ls=(0, (5, 3)))
    ax.text(101, ground[-1] + 11, "NASA's elevation model\npartway up the canopy", color=RED, fontsize=8.5, va="center")
    ax.plot(x, ground + 0.1 * 20, color=BLUE, lw=2)
    ax.text(101, ground[-1] + 2, "what we used: lidar ground\n+10% of canopy height (1-2 m)", color=BLUE,
            fontsize=8.5, va="center")
    ax.text(101, ground[-1] - 2.5, "lidar bare earth", color=MUTED, fontsize=8.5, va="center")
    sx, sy = 2, 44
    px = 52
    gy = 4 + 2 * np.sin(px / 18)
    t = (gy + 11 - sy) / (gy + 2 - sy)
    hx = sx + (px - sx) * t
    ax.plot([sx, px], [sy, gy + 2], color=INK, lw=1)
    ax.text(sx, sy + 1, "radar line of sight", fontsize=8.5)
    ax.plot(hx, gy + 11, "o", color=RED, ms=7)
    ax.plot(px, gy + 2, "o", color=BLUE, ms=7)
    ax.annotate("", xy=(px, gy - 3), xytext=(hx, gy - 3), arrowprops=dict(arrowstyle="<->", color=INK))
    ax.text((px + hx) / 2, gy - 6, "8 to 12 m shift, away from the satellite on all 3 tracks", ha="center", fontsize=9)
    ax.text(0, -9.5, "Evidence the error is real: same height error on 3 geometries (8-10 m). Shift grows with canopy (r 0.55-0.62).\n"
            "Lidar-placed stack agrees with a lidar simulation in 46 of 48 blocks on 9t (bare earth 40). Not a surveyed check.",
            fontsize=8.5, color=MUTED)
    ax.set_xlim(0, 125)
    ax.set_ylim(-11, 47)
    ax.set_aspect("auto")
    ax.axis("off")
    ax.set_title("Placement. A surface inside the canopy puts the echo in the wrong place.", loc="left", fontsize=11)
    save(fig, "nisar_position_cross_section.png")


def fig_ladder():
    rungs = ["measured", "survives\nposition fix", "beats control\nspots", "repeats across\nseasons/tracks",
             "tied to wells,\nnot depressions"]
    # how many rungs each idea cleared; the reason it stopped (doc sections 2, 5-8)
    ideas = [("Pit brightness", 3, "lead. Small, control spots are dark. Season change not conclusive"),
             ("Pad coherence loss", 3, "weaker lead. 169 vs 136.4 events. No winter excess"),
             ("Pad brightness", 1, "early -0.3 dB vanished after the fix"),
             ("Steel / persistent scatterers", 1, "wells hit at chance. Not rerun on lidar stack"),
             ("Water in pits", 1, "wet and dry overlap. 23 pool pits match others"),
             ("Motion", 1, "0 of 15 coherent wells after correction"),
             ("Sentinel-1 C-band", 1, "no pit signal in coherence, motion or bright spots")]
    fig, ax = plt.subplots(figsize=(12, 4.6))
    X = 1.45  # rung spacing
    for j, r in enumerate(rungs):
        ax.text(j * X, len(ideas) + 0.15, r, ha="center", va="bottom", fontsize=8.5, color=MUTED)
        ax.vlines(j * X, -0.5, len(ideas) - 0.5, color=FAINT, lw=0.8)
    for i, (name, n, why) in enumerate(ideas):
        y = len(ideas) - 1 - i
        col = BLUE if n >= 3 else MUTED
        ax.plot(np.arange(n) * X, [y] * n, "-", color=col, lw=2.5, solid_capstyle="round")
        ax.scatter(np.arange(n) * X, [y] * n, s=46, color=col, zorder=3, edgecolor=PAPER, lw=1.5)
        if n < len(rungs):
            ax.scatter([n * X], [y], s=46, facecolor=PAPER, edgecolor=RED, lw=1.5, marker="X", zorder=3)
        ax.text(-0.35, y, name, ha="right", va="center", fontsize=9.5, weight="bold" if n >= 3 else "normal")
        ax.text((len(rungs) - 1) * X + 0.5, y, why, ha="left", va="center", fontsize=8.5)
    ax.set_xlim(-2.6, 12.6)
    ax.set_ylim(-0.7, len(ideas) + 1.0)
    ax.axis("off")
    ax.text(-2.6, len(ideas) + 0.95, "How far each marker idea got. ✕ marks where it stopped. No idea reached the last rung.",
            fontsize=11)
    save(fig, "nisar_evidence_ladder.png")


def fig_waffle():
    prods = [("Spatial", 63), ("Coherence", 43), ("Temporal", 43), ("Amplitude trend and season", 42),
             ("Amplitude statistics", 32), ("Rain and freeze", 22), ("Dual-pol", 21), ("Events", 15),
             ("Sub-aperture", 15), ("Texture", 15), ("Geometry", 14), ("Line-of-sight motion", 12),
             ("Height residual", 9)]
    amp = {"Amplitude trend and season", "Amplitude statistics", "Dual-pol", "Texture", "Spatial", "Temporal"}
    phase = {"Coherence", "Line-of-sight motion", "Height residual", "Events"}
    fam = lambda nm: 0 if nm in amp else 1 if nm in phase else 2
    prods = sorted(prods, key=lambda p: (fam(p[0]), -p[1]))
    fig, ax = plt.subplots(figsize=(11, 4.4))
    cols, k, y0 = 30, 0, 0
    for name, n in prods:
        col = BLUE if name in amp else ORANGE if name in phase else MUTED
        start = k
        for _ in range(n):
            r, c = divmod(k, cols)
            ax.add_patch(Rectangle((c, -r), 0.86, 0.86, color=col, lw=0))
            k += 1
        r0, c0 = divmod(start, cols)
        ax.add_patch(Rectangle((cols + 0.8, -y0 * 0.82 + 0.1), 0.6, 0.6, color=col, lw=0))
        ax.text(cols + 1.8, -y0 * 0.82 + 0.4, f"{n:>3}  {name}", fontsize=8.5, va="center", family="DejaVu Sans Mono")
        y0 += 1
    ax.text(0, 1.6, "▇ amplitude-based", color=BLUE, fontsize=9)
    ax.text(7, 1.6, "▇ phase / coherence-based", color=ORANGE, fontsize=9)
    ax.text(16.5, 1.6, "▇ other (weather, geometry, focusing)", color=MUTED, fontsize=9)
    ax.text(0, -12.7, "346 bands, one square each. PCA on 9t finds about 100-130 real directions; the first holds only 6.9%.",
            fontsize=9, color=MUTED)
    ax.set_xlim(-0.5, cols + 14)
    ax.set_ylim(-13.3, 2.6)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("The band count is arithmetic: 13 scripts, run once per track.", loc="left", fontsize=11)
    save(fig, "nisar_band_count_waffle.png")


if __name__ == "__main__":
    for f in (fig_dates, fig_excess, fig_ps, fig_cross_section, fig_ladder, fig_waffle):
        f()
