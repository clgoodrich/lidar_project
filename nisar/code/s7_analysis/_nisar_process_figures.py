"""Figures for nisar/docs/NISAR_PROCESS_AND_OUTCOMES.md (2026-11-18; restyled formal the same day).

Journal style: serif type, boxed axes, inward ticks, real legends, no titles. Captions live in the doc.
  1 nisar_dates_on_hand.png          every NISAR pass per track and tile, with beta/provisional and the spring gap
  2 nisar_excess_number_line.png     pit and control-spot contrast with their rings, summer 2026 HV, and the excess
  3 nisar_ps_selection_plane.png     persistent-scatterer selection region (step 1), steadiness x brightness
  4 nisar_position_cross_section.png schematic of the canopy placement error and the surface used instead
  5 nisar_evidence_ladder.png        evidence stage reached by each marker idea
  6 nisar_band_count_waffle.png      the 346 bands by product and family (now a bar chart; name kept)

Dates come from the window index CSVs. Every other number is quoted from the process doc, sections 2-7.
Palette: #1F5FA8 blue, #D97706 orange, #A31515 dark red, the repo's lost/found palette. Validator
(dataviz validate_palette.js, light, --pairs all): worst pair dE 21.1 deutan, 22.6 normal (CLAUDE.md).
Greys are neutral context only and are always labelled. Every coloured category also differs in marker shape.

Writes nisar/docs/figures/<name>.png
  python nisar/code/s7_analysis/_nisar_process_figures.py
"""
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Rectangle

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "nisar" / "docs" / "figures"
sys.path.insert(0, str(ROOT / "nisar" / "code"))
import _nisar_fig_style as S  # noqa: E402  (shared formal style)
S.apply()
BLUE, ORANGE, RED = S.BLUE, S.ORANGE, S.RED
K, GREY, LIGHT = S.K, S.GREY, S.LIGHT


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(OUT / name)


def fig_dates():
    d = pd.concat([pd.read_csv(ROOT / "nisar" / "derived" / a / "nisar_gslc_5m" / f"nisar_gslc_window_index_{a}_5m.csv")
                   .assign(area=a) for a in ("9t", "613590")])
    d["t"] = pd.to_datetime(d.date)
    lanes = [("9t", 26), ("9t", 90), ("9t", 162), ("613590", 26), ("613590", 90), ("613590", 162)]
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    ax.axvspan(pd.Timestamp("2026-01-21"), pd.Timestamp("2026-06-19"), facecolor="none", edgecolor=GREY,
               hatch="///", lw=0, alpha=0.5)
    labels = []
    for i, (area, trk) in enumerate(lanes):
        y = len(lanes) - i
        s = d[(d.area == area) & (d.track == trk)]
        ok, bad = s[s.valid_fraction >= 0.5], s[s.valid_fraction < 0.5]
        ax.scatter(ok[ok.collection == "beta"].t, [y] * (ok.collection == "beta").sum(), marker="o", s=18, c=BLUE)
        ax.scatter(ok[ok.collection == "provisional"].t, [y] * (ok.collection == "provisional").sum(), marker="s",
                   s=16, c=ORANGE)
        ax.scatter(ok[ok.collection == "standard"].t, [y] * (ok.collection == "standard").sum(), marker="^",
                   s=20, c=RED)
        ax.scatter(bad.t, [y] * len(bad), marker="x", s=14, c=GREY, lw=0.8)
        labels.append(f"{area}, track {trk} (n = {len(ok)})")
    ax.axhline(3.5, color=K, lw=0.5)
    # amplitude seasons (provisional rule, 2026-11-19): summer 06-01..09-30, fall 10-21..11-30
    for a, b, lab in (("2026-06-01", "2026-09-30", "Summer"), ("2026-10-21", "2026-11-30", "Fall")):
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=LIGHT, alpha=0.5, lw=0, zorder=0)
        ax.text(pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2, len(lanes) + 0.45, lab,
                ha="center", va="center", fontsize=7)
    ax.axvline(pd.Timestamp("2026-06-01"), color=K, lw=0.8, ls="--")
    ax.text(pd.Timestamp("2026-05-28"), 0.6, "amplitude\nuses dates\nfrom here", ha="right", va="bottom", fontsize=6.5)
    ax.set_yticks(range(len(lanes), 0, -1), labels)
    ax.set_ylim(0.4, len(lanes) + 0.6)
    ax.set_xlim(pd.Timestamp("2025-10-15"), pd.Timestamp("2026-12-05"))
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=range(1, 13, 2)))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_xlabel("Acquisition date")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", c=BLUE, label="Beta, valid"),
                       Line2D([], [], marker="s", ls="", c=ORANGE, label="Provisional, valid"),
                       Line2D([], [], marker="^", ls="", c=RED, label="Standard, valid"),
                       Line2D([], [], marker="x", ls="", c=GREY, label="Image, no valid pixels over tile"),
                       Patch(facecolor="none", edgecolor=GREY, hatch="///", label="Raw data only (spring 2026)")],
              loc="upper center", bbox_to_anchor=(0.5, 1.2), ncol=3, fontsize=7.5, handletextpad=0.3, columnspacing=1)
    save(fig, "nisar_dates_on_hand.png")


def fig_dates_postjune():
    """Dates actually used (2026-06-01 onward), for slides. Pre-June dates are not shown at all."""
    d = pd.concat([pd.read_csv(ROOT / "nisar" / "derived" / a / "nisar_gslc_5m" / f"nisar_gslc_window_index_{a}_5m.csv")
                   .assign(area=a) for a in ("9t", "613590")])
    d["t"] = pd.to_datetime(d.date)
    bad_dates = {(pd.Timestamp(x), t) for x, t in (("2026-07-22", 26), ("2026-09-08", 26))}
    d = d[(d.t >= pd.Timestamp("2026-06-01")) & (d.valid_fraction >= 0.5)]
    d = d[[(t, k) not in bad_dates for t, k in zip(d.t, d.track)]]
    lanes = [("9t", 26), ("9t", 90), ("9t", 162)]   # 2026-11-23: present scope is 9t only
    fig, ax = plt.subplots(figsize=(7.2, 2.0))
    for a, b, lab in (("2026-06-01", "2026-09-30", "Summer"), ("2026-10-21", "2026-11-30", "Fall")):
        ax.axvspan(pd.Timestamp(a), pd.Timestamp(b), color=LIGHT, alpha=0.6, lw=0, zorder=0)
        ax.text(pd.Timestamp(a) + (pd.Timestamp(b) - pd.Timestamp(a)) / 2, len(lanes) + 0.45, lab,
                ha="center", va="center", fontsize=7.5)
    labels = []
    for i, (area, trk) in enumerate(lanes):
        y = len(lanes) - i
        s_ = d[(d.area == area) & (d.track == trk)]
        mk = "v" if trk == 26 else "o"
        ax.scatter(s_.t, [y] * len(s_), marker=mk, s=18, c=BLUE if trk == 26 else ORANGE, zorder=3)
        labels.append(f"Track {trk} {'desc.' if trk == 26 else 'asc.'} (n = {len(s_)})")
    ax.set_yticks(range(len(lanes), 0, -1), labels)
    ax.set_ylim(0.4, len(lanes) + 0.8)
    ax.set_xlim(pd.Timestamp("2026-06-05"), pd.Timestamp("2026-12-05"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_xlabel("Acquisition date")
    ax.legend(handles=[Line2D([], [], marker="v", ls="", c=BLUE, label="Descending pass"),
                       Line2D([], [], marker="o", ls="", c=ORANGE, label="Ascending pass")],
              loc="upper center", bbox_to_anchor=(0.5, 1.22), ncol=2, fontsize=7.5)
    save(fig, "nisar_dates_postjune.png")


def fig_excess():
    fig, ax = plt.subplots(figsize=(5.0, 2.0))
    ax.axvline(0, color=GREY, lw=0.6, ls="--")
    # 9t, summer 2026 HV, lidar-placed stack, nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_swap40_9t_slc_5m.csv
    ax.plot(-0.149, 1, "s", ms=6, c=ORANGE)
    ax.plot(0.062, 2, "o", ms=6, c=BLUE)
    ax.annotate("", xy=(0.062, 1.5), xytext=(-0.149, 1.5), arrowprops=dict(arrowstyle="<->", lw=0.8))
    ax.text(-0.04, 1.58, "median per-pit excess +0.18 dB\n95% interval 0.09 to 0.26, $p$ < 0.001",
            ha="center", va="bottom", fontsize=7.5)
    ax.set_yticks([1, 2], ["Control spots", "Pits (n = 506)"])
    ax.set_ylim(0.5, 2.6)
    ax.set_xlim(-0.4, 0.3)
    ax.set_xlabel("Feature minus ring, summer 2026 HV (dB)")
    save(fig, "nisar_excess_number_line.png")


def fig_ps():
    fig, ax = plt.subplots(figsize=(4.6, 3.4))
    ax.add_patch(Rectangle((0, 6), 0.25, 18, facecolor=BLUE, alpha=0.10, edgecolor=BLUE, lw=1))
    ax.text(0.01, 22.5, "PS selection\n$D_A$ < 0.25, ≥ 6 dB", fontsize=7.5, va="top", color=K)
    ax.axvspan(0.44, 0.58, color=LIGHT, lw=0)
    ax.text(0.51, 22.5, "Forest", ha="center", va="top", fontsize=7.5)
    ax.axvline(0.53, color=GREY, lw=0.8, ls=":")
    ax.text(0.537, 1, "Speckle limit 0.53", rotation=90, fontsize=7, va="bottom", color=GREY)
    ax.plot(0.09, 17.7, "^", ms=7, c=ORANGE, label="Building (all 3 tracks)")
    ax.legend(loc="center right", fontsize=7.5)
    ax.set_xlim(0, 0.62)
    ax.set_ylim(0, 24)
    ax.set_xlabel("Amplitude dispersion $D_A$ = $\\sigma_A / \\mu_A$")
    ax.set_ylabel("Brightness above 250 m median (dB)")
    save(fig, "nisar_ps_selection_plane.png")


def fig_cross_section():
    fig, ax = plt.subplots(figsize=(6.4, 2.8))
    x = np.linspace(0, 100, 400)
    g = 4 + 2 * np.sin(x / 18)
    gf = lambda v: 4 + 2 * np.sin(v / 18)
    ax.fill_between(x, -2, g, facecolor="none", edgecolor=K, hatch="....", lw=0)
    ax.plot(x, g, c=K, lw=0.8, label="Lidar bare earth")
    rng = np.random.default_rng(3)
    for cx in np.arange(4, 100, 7.5):
        h = rng.uniform(17, 23)
        ax.plot([cx, cx], [gf(cx), gf(cx) + h], c=GREY, lw=0.6)
        ax.plot(cx + np.array([-3.5, 0, 3.5]), gf(cx) + h * np.array([0.55, 1.0, 0.55]), c=GREY, lw=0.6)
    ax.plot(x, g + 11, c=RED, lw=1.2, ls="--", label="Elevation model in NASA product")
    ax.plot(x, g + 2, c=BLUE, lw=1.2, label="Surface used: ground + 10% canopy height")
    sx, sy, px = 2, 40, 52
    hx = sx + (px - sx) * (gf(px) + 11 - sy) / (gf(px) + 2 - sy)
    ax.plot([sx, px], [sy, gf(px) + 2], c=K, lw=0.7)
    ax.text(10, 31, "Line of sight", fontsize=7.5, rotation=-30)
    ax.plot(hx, gf(px) + 11, "o", ms=4, c=RED)
    ax.plot(px, gf(px) + 2, "s", ms=4, c=BLUE)
    ax.annotate("", xy=(px, -0.8), xytext=(hx, -0.8), arrowprops=dict(arrowstyle="<->", lw=0.7))
    ax.text((px + hx) / 2, -1.6, "8–12 m", ha="center", va="top", fontsize=7.5)
    ax.set_xlim(0, 100)
    ax.set_ylim(-5, 42)
    ax.set_xlabel("Ground range (schematic, m)")
    ax.set_ylabel("Height (schematic, m)")
    ax.legend(loc="upper right", fontsize=7)
    save(fig, "nisar_position_cross_section.png")


def fig_ladder():
    stages = ["Measured", "Survives\nposition fix", "Exceeds\ncontrol spots", "Repeats across\nseasons", "Specific to\nwell sites"]
    ideas = [("Pit brightness", 3), ("Pad coherence loss", 3), ("Pad darkening, leaf-off", 3), ("Steel (PS selection)", 2),
             ("Water in pits", 2), ("Motion", 2), ("Sentinel-1 C-band", 2)]  # pits: summer HV holds, fall HH fails; pads: dark in fall 2026, at chance in summer (2026-11-20)
    fig, ax = plt.subplots(figsize=(5.6, 3.0))
    for i, (name, n) in enumerate(ideas):
        y = len(ideas) - 1 - i
        ax.plot(range(n), [y] * n, "-o", c=BLUE, ms=5, lw=1)
        ax.plot([n], [y], "x", c=RED, ms=6, mew=1.2)
        ax.plot(range(n + 1, len(stages)), [y] * (len(stages) - n - 1), "o", mfc="none", mec=GREY, ms=5, ls="")
    ax.set_yticks(range(len(ideas) - 1, -1, -1), [n for n, _ in ideas])
    ax.set_xticks(range(len(stages)), stages, fontsize=7.5)
    ax.set_xlim(-0.5, len(stages) - 0.5)
    ax.set_ylim(-0.6, len(ideas) - 0.4)
    ax.grid(axis="x", color=LIGHT, lw=0.6)
    ax.set_axisbelow(True)
    ax.legend(handles=[Line2D([], [], marker="o", c=BLUE, ms=5, lw=1, label="Passed"),
                       Line2D([], [], marker="x", c=RED, ls="", ms=6, mew=1.2, label="Failed or inconclusive"),
                       Line2D([], [], marker="o", mfc="none", mec=GREY, ls="", ms=5, label="Not reached")],
              loc="upper center", bbox_to_anchor=(0.5, 1.15), ncol=3, fontsize=7.5)
    save(fig, "nisar_evidence_ladder.png")


def fig_waffle():
    prods = [("Spatial", 63, 0), ("Temporal", 43, 0), ("Amplitude trend and season", 42, 0), ("Amplitude statistics", 32, 0),
             ("Dual-pol", 21, 0), ("Texture", 15, 0), ("Coherence", 43, 1), ("Events", 15, 1),
             ("Line-of-sight motion", 12, 1), ("Height residual", 9, 1), ("Rain and freeze", 22, 2),
             ("Sub-aperture", 15, 2), ("Geometry", 14, 2)]
    cols, hatch = [BLUE, ORANGE, GREY], ["", "////", ".."]
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    y = np.arange(len(prods))[::-1]
    for yi, (name, n, f) in zip(y, prods):
        ax.barh(yi, n, color=cols[f], hatch=hatch[f], edgecolor="white", lw=0, height=0.7)
        ax.text(n + 0.8, yi, str(n), va="center", fontsize=7.5)
    ax.set_yticks(y, [p[0] for p in prods], fontsize=7.5)
    ax.set_xlim(0, 72)
    ax.set_xlabel("Number of bands (total 346)")
    ax.legend(handles=[Patch(facecolor=c, hatch=h, edgecolor="white", label=l) for c, h, l in
                       zip(cols, hatch, ["Amplitude", "Phase / coherence", "Other"])], loc="lower right", fontsize=7.5)
    save(fig, "nisar_band_count_waffle.png")


if __name__ == "__main__":
    for f in (fig_dates, fig_dates_postjune, fig_excess, fig_ps, fig_cross_section, fig_ladder, fig_waffle):
        f()
