"""Draw every figure for nisar_writeup/README.md.

Real data: pit outlines, NISAR scenes, lidar hillshade, leaf-off photo, scene calendar, wet/dry pit tables.
Numbers copied from the project record (each has a source comment): NISAR_FINDINGS.md, docs/analysis_log.md,
docs/iterations/nisar_*.md.

Palette (checked with the dataviz validator, --pairs all, light surface #fcfcfb):
  #1F5FA8 blue, #D97706 orange, #5FB4E0 light blue. Worst pair dE 23.3 deutan, 25.4 normal.
  #8E959B grey is a neutral ("place only", "other"), never a category, and is always directly labelled.
  The light blue is 2.25:1 against the paper, so it is always directly labelled too.
No red and green anywhere. Where colour carries meaning, a marker shape or a text label carries it as well.

Run:
  python nisar_writeup/_make_figures.py
"""
from __future__ import annotations

import glob
import textwrap
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from matplotlib import dates as mdates
from matplotlib import pyplot as plt
from matplotlib.patches import Rectangle
from pyproj import Transformer
from rasterio.windows import from_bounds
from scipy.stats import norm
from shapely.geometry import box

matplotlib.use("Agg")
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "nisar_writeup" / "figures"
OUT.mkdir(parents=True, exist_ok=True)
G = ROOT / "qgis/annotations/annotations_proj_v2.gpkg"

BLUE, ORANGE, LBLUE, GREY, INK, PAPER, GRID = "#1F5FA8", "#D97706", "#5FB4E0", "#8E959B", "#2B2F36", "#fcfcfb", "#DADDE1"
plt.rcParams.update({
    "font.size": 10, "axes.edgecolor": INK, "axes.labelcolor": INK, "text.color": INK, "xtick.color": INK, "ytick.color": INK,
    "axes.facecolor": PAPER, "figure.facecolor": PAPER, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 12, "axes.titleweight": "bold", "axes.titlelocation": "left", "savefig.facecolor": PAPER,
})
T = Transformer.from_crs(6346, 32617, always_xy=True)
PIT = 288  # pit_inside_id, pit_full_id 495, pad 818, area 35 m2


def save(fig, name):
    f = OUT / name
    fig.savefig(f, dpi=140, bbox_inches="tight")
    plt.close(fig)
    print(f)


def pit_geoms():
    pi = gpd.read_file(G, layer="pit_inside").set_index("pit_inside_id")
    pf = gpd.read_file(G, layer="pit_full")
    inner = pi.loc[PIT].geometry
    full = pf[pf.pit_inside_id == PIT].geometry.iloc[0]
    return inner, full


def to_utm(g):
    from shapely.ops import transform
    return transform(lambda x, y, z=None: T.transform(x, y), g)


def draw_poly(ax, g, cx, cy, **kw):
    for p in getattr(g, "geoms", [g]):
        x, y = p.exterior.xy
        ax.plot(np.array(x) - cx, np.array(y) - cy, **kw)


# ---------------------------------------------------------------- 1. five ideas
def fig_ideas():
    rng = np.random.default_rng(7)
    cards = [
        ("1  Steel is bright", "A pumpjack or wellhead is metal.\nMetal can return a strong, steady bright spot.",
         "Wells were no more likely to have a bright spot than random ground (3.9% against 5.2% at Warren).", "none"),
        ("2  A pad is a scar", "A cleared, levelled pad should return a different amount of energy than forest.",
         "Pads read slightly darker, but only because they are clearings. The effect did not survive a location check.", "weak"),
        ("3  Seasons differ", "Bare trees in winter, leaves in summer. A pit might change differently.",
         "A change of about +0.2 dB. A single scene scatters by about 2.8 dB, so the change is under a tenth of the noise.", "weak"),
        ("4  Old wells move", "Radar phase can sense millimetres of ground motion between passes.",
         "Pit coherence was +0.0001 higher than decoys. Not one of 282 wells was flagged as moving.", "none"),
        ("5  Wet pits are dark", "Calm water reflects radar away from the satellite, so it should look dark.",
         "Wet pits averaged +1.57 dB and dry pits +1.75 dB. The two groups overlap completely.", "none"),
    ]
    fig, axes = plt.subplots(2, 5, figsize=(15, 6.6), gridspec_kw={"height_ratios": [1.05, 1.25], "hspace": 0.04, "wspace": 0.12})
    for k, (title, look, found, verdict) in enumerate(cards):
        a = axes[0, k]
        base = rng.normal(0, 0.55, (7, 7))
        if k == 0:
            base[3, 3] = 4.0
        if k == 1:
            base[2:5, 2:5] -= 0.9
        if k == 2:
            base[3, 3] += 0.35
        if k == 3:
            yy, xx = np.mgrid[:7, :7]
            base = 1.2 * np.sin((xx + yy) * 1.1)
        if k == 4:
            base[3, 3] = -3.0
            base[3, 4] = -2.4
        a.imshow(base, cmap="gray", vmin=-3.2, vmax=3.2, interpolation="nearest")
        a.set_xticks(np.arange(-.5, 7, 1), minor=True)
        a.set_yticks(np.arange(-.5, 7, 1), minor=True)
        a.grid(which="minor", color=PAPER, lw=1.2)
        a.tick_params(which="both", length=0, labelbottom=False, labelleft=False)
        for s in a.spines.values():
            s.set_visible(False)
        a.set_title(title, fontsize=11)
        b = axes[1, k]
        b.axis("off")
        b.set_xlim(0, 1)
        b.set_ylim(0, 1)
        b.text(0, 0.98, "What we hoped", fontsize=8.5, color=GREY, fontweight="bold", va="top")
        b.text(0, 0.90, textwrap.fill(look.replace("\n", " "), 30), fontsize=9, va="top")
        b.text(0, 0.50, "What we found", fontsize=8.5, color=GREY, fontweight="bold", va="top")
        b.text(0, 0.42, textwrap.fill(found, 30), fontsize=9, va="top")
        mk, col, txt = ("X", ORANGE, "no usable signal") if verdict == "none" else ("D", LBLUE, "weak, not reliable")
        b.plot([0.03], [0.02], marker=mk, color=col, ms=9, mec=INK, mew=0.8, clip_on=False)
        b.text(0.09, 0.02, txt, fontsize=9, va="center", fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.99, top=0.88, bottom=0.03)
    fig.suptitle("Five things we hoped the radar would show. None held up.", x=0.02, ha="left", fontsize=14, fontweight="bold")
    save(fig, "nisar_five_ideas_9t.png")


# ---------------------------------------------------------------- 2. pit vs pixel scale
def fig_scale():
    inner, full = pit_geoms()
    ui, uf = to_utm(inner), to_utm(full)
    cx, cy = ui.centroid.coords[0]
    H = 30
    fig, axes = plt.subplots(1, 2, figsize=(11, 5.6))
    for ax, (px, label, ox) in zip(axes, [(5, "NISAR pixel, 5 m", 619295.0), (10, "Sentinel-1 pixel, 10 m", 0.0)]):
        x0 = ox + np.floor((cx - H - ox) / px) * px
        y0 = np.floor((cy - H) / px) * px if px == 10 else 4597705.0 - np.ceil((4597705.0 - (cy - H)) / px) * px
        xs = np.arange(x0, cx + H + px, px)
        ys = np.arange(y0, cy + H + px, px)
        for xv in xs:
            for yv in ys:
                cell = box(xv, yv, xv + px, yv + px)
                fi = cell.intersection(ui).area / (px * px)
                ff = cell.intersection(uf).area / (px * px)
                shade = min(1.0, ff * 0.55 + fi * 1.0)
                ax.add_patch(Rectangle((xv - cx, yv - cy), px, px, facecolor=BLUE, alpha=shade * 0.75, edgecolor=GRID, lw=0.8))
        draw_poly(ax, uf, cx, cy, color=ORANGE, lw=1.8)
        draw_poly(ax, ui, cx, cy, color=INK, lw=1.8)
        bx, by = 12.0, -4.0
        ax.add_patch(Rectangle((bx, by), 1.5, 1.5, facecolor=ORANGE, edgecolor=INK, lw=0.8, zorder=5))
        ax.annotate("1.5 m box\n(size only, position\nillustrative)", (bx + 1.5, by + 0.7), xytext=(bx + 3, by - 8), fontsize=8.5,
                    arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
        ax.set_xlim(-H, H)
        ax.set_ylim(-H, H)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(False)
        ax.set_title(label, fontsize=11)
        print(f"scale {label}: interior {ui.area / px**2:.2f} px, exterior {uf.area / px**2:.2f} px, box {1.5**2 / px**2:.3f} px")
        ax.text(-H + 1, H - 2.5, f"Pit interior: {ui.area / px**2:.1f} pixels\nPit exterior: {uf.area / px**2:.1f} pixels\nBox: {1.5**2 / px**2:.2f} pixel",
                fontsize=10, va="top", bbox=dict(fc=PAPER, ec=GRID, boxstyle="round,pad=0.3"))
    fig.subplots_adjust(left=0.02, right=0.98, top=0.86, bottom=0.08)
    fig.suptitle(f"A pit covers about 1 to 10 NISAR pixels, and the box covers a fraction of one  (pit {PIT}: interior {ui.area:.0f} m², exterior {uf.area:.0f} m²)",
                 x=0.02, ha="left", fontsize=12.5, fontweight="bold")
    fig.text(0.02, 0.01, "Black line: pit_inside. Orange line: pit_full. Blue shade: share of each pixel the pit covers. 5 m grid is the real grid of our NISAR files.", fontsize=8.5, color=GREY)
    save(fig, "nisar_pit_vs_pixel_9t.png")


# ---------------------------------------------------------------- 3. four views of one pit
def fig_views():
    inner, full = pit_geoms()
    cx6, cy6 = inner.centroid.coords[0]
    cxu, cyu = T.transform(cx6, cy6)
    H = 50.0
    fig, axes = plt.subplots(1, 4, figsize=(16, 4.6))
    # photo
    with rasterio.open(ROOT / "data/9t/results/pit/photo/pit_leafoff_photo_288_9t.tif") as s:
        ph = np.moveaxis(s.read([1, 2, 3]), 0, -1)
    axes[0].imshow(ph, extent=(-H, H, -H, H))
    axes[0].set_title("Aerial photo, leaf-off\n0.14 m pixels", fontsize=10.5)
    # hillshade
    with rasterio.open(ROOT / "data/9t/derived/05/hillshade_9t_05.tif") as s:
        w = from_bounds(cx6 - H, cy6 - H, cx6 + H, cy6 + H, s.transform)
        hs = s.read(1, window=w, boundless=True, fill_value=0).astype(float)
    axes[1].imshow(hs, cmap="gray", extent=(-H, H, -H, H))
    axes[1].set_title("Lidar hillshade, 2019\n0.5 m pixels", fontsize=10.5)
    # NISAR
    files = sorted(glob.glob(str(ROOT / "data/9t/derived/nisar_slc_lidar_5m/nisar_slc_lidar_*_9t.tif")))

    def hhdb(f):
        with rasterio.open(f) as s:
            w = from_bounds(cxu - H, cyu - H, cxu + H, cyu + H, s.transform)
            a = s.read(1, window=w, boundless=True, fill_value=0)
        return 20 * np.log10(np.abs(a) + 1e-9)
    one = hhdb(next(f for f in files if "20251121_t162A" in f))
    stack = np.array([hhdb(f) for f in files])
    stack[stack < -60] = np.nan
    mean = np.nanmean(stack, axis=0)
    axes[2].imshow(one, cmap="gray", extent=(-H, H, -H, H), interpolation="nearest", vmin=np.percentile(one, 2), vmax=np.percentile(one, 98))
    axes[2].set_title("NISAR L-band HH, one date\n(2025-11-21) 5 m pixels", fontsize=10.5)
    axes[3].imshow(mean, cmap="gray", extent=(-H, H, -H, H), interpolation="nearest", vmin=np.nanpercentile(mean, 2), vmax=np.nanpercentile(mean, 98))
    axes[3].set_title(f"NISAR L-band HH, average of\n{len(files)} dates, 5 m pixels", fontsize=10.5)
    ui, uf = to_utm(inner), to_utm(full)
    for k, ax in enumerate(axes):
        if k < 2:
            draw_poly(ax, full, cx6, cy6, color=ORANGE, lw=1.4)
            draw_poly(ax, inner, cx6, cy6, color="white" if k else "white", lw=1.4)
        else:
            draw_poly(ax, uf, cxu, cyu, color=ORANGE, lw=1.4)
            draw_poly(ax, ui, cxu, cyu, color="white", lw=1.4)
        ax.set_xticks([])
        ax.set_yticks([])
        ax.set_xlim(-H, H)
        ax.set_ylim(-H, H)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.82, bottom=0.02, wspace=0.05)
    fig.suptitle(f"The same 100 m square of ground through three sensors  (pit {PIT}: white = interior, orange = exterior)", x=0.01, ha="left", fontsize=12.5, fontweight="bold")
    save(fig, "nisar_same_pit_three_sensors_9t.png")


# ---------------------------------------------------------------- 4. scene calendar
def fig_calendar():
    idx = pd.read_csv(ROOT / "data/9t/derived/nisar_gslc_5m/nisar_gslc_window_index_9t_5m.csv", parse_dates=["date"])
    leaf = pd.read_csv(ROOT / "data/9t/derived/weather/nisar_dates_leaf_and_snow_9t.csv", parse_dates=["date"])
    bad = [("2026-07-22", 26), ("2026-09-08", 26)]  # bad granules, docs/analysis_log.md 2026-10-13
    clean = [("2025-11-21", 162), ("2025-12-18", 26), ("2026-01-08", 162)]  # docs/iterations/nisar_leaf_and_snow_9t.md
    fig, ax = plt.subplots(figsize=(13, 4.8))
    ax.axvspan(pd.Timestamp("2025-11-20"), pd.Timestamp("2026-04-15"), color=LBLUE, alpha=0.22, lw=0)
    ax.axvspan(pd.Timestamp("2026-01-21"), pd.Timestamp("2026-06-19"), ymin=0, ymax=1, facecolor="none", hatch="///", edgecolor=GRID, lw=0)
    ax.axvspan(pd.Timestamp("2026-04-01"), pd.Timestamp("2026-04-10"), color=INK, alpha=0.28, lw=0)
    rows = {26: 0, 90: 1, 162: 2}
    for _, r in idx.iterrows():
        y = rows[int(r.track)]
        isbad = (r.date.strftime("%Y-%m-%d"), int(r.track)) in bad
        if isbad:
            ax.plot(r.date, y, "x", color=INK, ms=9, mew=1.8, zorder=4)
        else:
            ax.plot(r.date, y, "o", ms=8, mfc=(PAPER if r.collection == "beta" else BLUE), mec=BLUE, mew=1.6, zorder=3)
    for d, t in clean:
        ax.plot(pd.Timestamp(d), rows[t], "o", ms=17, mfc="none", mec=ORANGE, mew=2.4, zorder=5)
    ax.set_yticks([0, 1, 2])
    ax.set_yticklabels(["Track 26\n(descending)", "Track 90\n(ascending)", "Track 162\n(ascending)"])
    ax.set_ylim(-0.7, 3.0)
    ax.set_xlim(pd.Timestamp("2025-10-15"), pd.Timestamp("2026-10-31"))
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.text(pd.Timestamp("2025-11-22"), 2.72, "Trees bare (about 20 Nov to 15 Apr)", fontsize=9.5, color=INK, va="center")
    ax.text(pd.Timestamp("2026-03-12"), -0.45, "No processed NISAR scenes, 20 Jan to 20 Jun 2026", fontsize=9.5, color=INK, ha="center", va="center",
            bbox=dict(fc=PAPER, ec=GRID, boxstyle="round,pad=0.25"))
    ax.annotate("Early April:\ntrees bare,\nno NISAR scene", (pd.Timestamp("2026-04-05"), 1.0), xytext=(pd.Timestamp("2026-04-05"), 1.75), ha="center", fontsize=9.2,
                arrowprops=dict(arrowstyle="-", color=INK, lw=0.8))
    ax.plot([], [], "o", ms=8, mfc=PAPER, mec=BLUE, mew=1.6, label="Beta product (Oct 2025 to Jan 2026)")
    ax.plot([], [], "o", ms=8, mfc=BLUE, mec=BLUE, mew=1.6, label="Provisional product (Jun to Oct 2026)")
    ax.plot([], [], "o", ms=14, mfc="none", mec=ORANGE, mew=2.4, label="Bare trees and no snow (3 dates)")
    ax.plot([], [], "x", color=INK, ms=8, mew=1.8, label="Dropped, bad granule")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=4, frameon=False, fontsize=9)
    ax.set_title("Every NISAR scene we have over the study tile: 37 dates, none from February to May")
    save(fig, "nisar_scene_calendar_9t.png")


# ---------------------------------------------------------------- 5. placement
def fig_placement():
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6), gridspec_kw={"width_ratios": [1, 1.15]})
    ax = axes[0]
    tr = ["Track 26", "Track 90", "Track 162"]
    before = [9.6, 11.9, 9.1]  # docs/analysis_log.md 2026-10-09 Stage 0
    after = [1.2, 1.0, 1.1]    # docs/analysis_log.md 2026-10-13, canopy-modelled check, median
    x = np.arange(3)
    ax.bar(x - 0.19, before, 0.36, color=GREY, label="As delivered by NASA")
    ax.bar(x + 0.19, after, 0.36, color=BLUE, label="After our re-placement")
    for xi, v in zip(x - 0.19, before):
        ax.text(xi, v + 0.2, f"{v:.1f}", ha="center", fontsize=9.5)
    for xi, v in zip(x + 0.19, after):
        ax.text(xi, v + 0.2, f"{v:.1f}", ha="center", fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(tr)
    ax.set_ylabel("Typical error, metres")
    ax.set_ylim(0, 14)
    ax.legend(frameon=False, loc="upper right", fontsize=9)
    ax.set_title("Radar to lidar error")
    ax = axes[1]
    labs = ["NASA as\ndelivered", "Our first\nre-placement", "Final\nre-placement"]
    in25 = [0, 27, 40]  # blocks within 2.5 m, of 48, bare-earth check, docs/analysis_log.md 2026-10-13
    in5 = [0, 42, 48]
    x = np.arange(3)
    ax.bar(x - 0.19, in25, 0.36, color=BLUE, label="within 2.5 m")
    ax.bar(x + 0.19, in5, 0.36, color=LBLUE, label="within 5 m")
    for xi, v in zip(x - 0.19, in25):
        ax.text(xi, v + 0.8, str(v), ha="center", fontsize=9.5)
    for xi, v in zip(x + 0.19, in5):
        ax.text(xi, v + 0.8, str(v), ha="center", fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labs)
    ax.set_ylim(0, 56)
    ax.set_ylabel("Blocks of 1.1 km, out of 48")
    ax.legend(frameon=False, loc="upper left", fontsize=9)
    ax.set_title("Blocks that line up with the lidar")
    ax.text(2.45, 3, "With the forest-echo model\nthe final stack reaches\n46 of 48 within 2.5 m.", fontsize=8.8, ha="right", va="bottom")
    fig.suptitle("NASA's placement sat about 10 m from the lidar. Our re-placement brought it to about 1 m.", x=0.01, ha="left", fontsize=12.5, fontweight="bold", y=1.02)
    fig.subplots_adjust(left=0.07, right=0.99)
    save(fig, "nisar_placement_fix_9t.png")


# ---------------------------------------------------------------- 6. what AUC means
def fig_auc():
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
    xs = np.linspace(-4.5, 6.5, 400)
    for ax, auc, txt in zip(axes, [0.50, 0.64, 0.90], ["Chance: the two groups look the same", "Weak: a little separation", "Strong: the groups barely overlap"]):
        d = np.sqrt(2) * norm.ppf(auc)
        ax.fill_between(xs, norm.pdf(xs, 0, 1), color=GREY, alpha=0.5, lw=0)
        ax.fill_between(xs, norm.pdf(xs, d, 1), color=BLUE, alpha=0.5, lw=0)
        ax.plot(xs, norm.pdf(xs, 0, 1), color=GREY, lw=1.6)
        ax.plot(xs, norm.pdf(xs, d, 1), color=BLUE, lw=1.6)
        ax.set_title(f"AUC {auc:.2f}", fontsize=12)
        ax.text(0.5, -0.2, txt, transform=ax.transAxes, ha="center", fontsize=9.5)
        ax.set_yticks([])
        ax.set_xticks([])
        ax.text(-1.9, 0.30, "decoys", color=INK, fontsize=9.5, ha="center")
        ax.text(d + 1.9, 0.30, "pads", color=BLUE, fontsize=9.5, ha="center", fontweight="bold")
    fig.subplots_adjust(left=0.02, right=0.99, wspace=0.08)
    fig.suptitle("AUC is the chance that a real pad scores higher than a random look-alike spot", x=0.02, ha="left", fontsize=12.5, fontweight="bold", y=1.04)
    save(fig, "nisar_auc_explained.png")


# ---------------------------------------------------------------- 7. pad scores and place effect
def fig_staircase():
    fig, axes = plt.subplots(1, 2, figsize=(14, 5.2), gridspec_kw={"width_ratios": [1.25, 1]})
    ax = axes[0]
    rows = [  # (AUC, label, kind) docs/analysis_log.md 2026-10-26 entries
        (0.877, "First pass: decoys beside roads", "r"),
        (0.775, "Same design, labels shuffled in 500 m blocks", "c"),
        (0.713, "Decoys within 1.5 km of their pad", "r"),
        (0.635, "After audit fixes: decoys anywhere on the tile", "r"),
        (0.476, "After audit fixes: decoys within 1.5 km", "r"),
        (0.504, "Fake pads moved 150 to 300 m (placebo)", "c"),
    ]
    y = np.arange(len(rows))[::-1]
    for yi, (v, lab, kind) in zip(y, rows):
        ax.barh(yi, v, color=BLUE if kind == "r" else GREY, height=0.5)
        ax.text(v + 0.012, yi, f"{v:.2f}", va="center", fontsize=10, fontweight="bold")
        ax.text(0.01, yi + 0.30, lab, va="bottom", fontsize=9.3)
    ax.axvline(0.5, color=INK, lw=1.0, ls=(0, (4, 3)))
    ax.text(0.5, len(rows) - 0.05, "chance", ha="center", fontsize=9)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(-0.6, len(rows) + 0.25)
    ax.set_yticks([])
    ax.set_xlabel("AUC of NISAR for pads")
    ax.plot([], [], "s", color=BLUE, label="Real pads against decoys")
    ax.plot([], [], "s", color=GREY, label="Control that should score at chance")
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2, fontsize=9)
    ax.set_title("Pad score fell as we removed shortcuts")
    ax = axes[1]
    # docs/analysis_log.md 2026-10-27: AUC against decoys 100 to 500 m away, then over 3.5 km away
    series = [("NISAR", 0.44, 0.71, BLUE, "o"), ("Sentinel-2 optical", 0.56, 0.91, LBLUE, "s"), ("Map x/y only", 0.38, 0.96, GREY, "^")]
    for i, (nm, a, b, col, m) in enumerate(series):
        yy = 2 - i
        ax.plot([a, b], [yy, yy], color=col, lw=2.2, zorder=1)
        ax.plot([a], [yy], m, color=col, mec=INK, ms=10, zorder=3)
        ax.plot([b], [yy], m, color=col, mec=INK, ms=10, zorder=3, mfc=PAPER, mew=2)
        ax.text(0.34, yy + 0.2, nm, fontsize=10, fontweight="bold", color=INK)
        ax.text(a, yy - 0.3, f"{a:.2f}", ha="center", fontsize=9)
        ax.text(b, yy - 0.3, f"{b:.2f}", ha="center", fontsize=9)
    ax.axvline(0.5, color=INK, lw=1.0, ls=(0, (4, 3)))
    ax.set_xlim(0.3, 1.0)
    ax.set_ylim(-1.1, 2.7)
    ax.set_yticks([])
    ax.set_xlabel("AUC")
    ax.set_title("Every score rises when decoys are far away")
    ax.text(0.31, -0.55, "Filled marker: decoys 100 to 500 m away.\nHollow marker: decoys over 3.5 km away.", fontsize=8.8, color=INK, va="top")
    fig.suptitle("Most of the early radar score was location, not the pad", x=0.01, ha="left", fontsize=13, fontweight="bold", y=1.03)
    fig.subplots_adjust(left=0.03, right=0.99, wspace=0.12)
    save(fig, "nisar_pad_score_vs_place_9t.png")


# ---------------------------------------------------------------- 8. steel
def fig_steel():
    fig, ax = plt.subplots(figsize=(9.5, 4.6))
    tests = [  # docs/analysis_log.md: 2026-10-08 (9t), 2026-10-23 (Warren), 2026-10-21 (snapped)
        ("9t, first pass\n331 bright targets", 4.9, 3.8, "wells", "random spots"),
        ("Warren\n684 wells, 20,000 random pixels", 3.9, 5.2, "wells", "random spots"),
        ("9t, wells moved to nearest\nlidar feature (419 wells)", 0.7, 0.9, "wells", "other lidar features"),
    ]
    x = np.arange(len(tests))
    for xi, (nm, a, b, la, lb) in zip(x, tests):
        ax.bar(xi - 0.19, a, 0.36, color=BLUE)
        ax.bar(xi + 0.19, b, 0.36, color=GREY)
        ax.text(xi - 0.19, a + 0.12, f"{a:.1f}%", ha="center", fontsize=10, fontweight="bold")
        ax.text(xi + 0.19, b + 0.12, f"{b:.1f}%", ha="center", fontsize=10, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels([t[0] for t in tests], fontsize=9.5)
    ax.set_ylabel("Share with a steady bright target within 15 m")
    ax.set_ylim(0, 6.6)
    ax.plot([], [], "s", color=BLUE, label="Known wells")
    ax.plot([], [], "s", color=GREY, label="Comparison spots")
    ax.legend(frameon=False, fontsize=9.5, loc="upper right")
    ax.set_title("Wells are no more likely to have a bright steady spot than the ground around them")
    ax.text(0.0, -0.20, "Compare the two bars inside each pair only. The third pair uses a stricter rule, so every rate is lower.", transform=ax.transAxes, fontsize=8.8, color=GREY)
    save(fig, "nisar_steel_hit_rates.png")


# ---------------------------------------------------------------- 9. gain over lidar
def fig_gain():
    rows = [  # NISAR_FINDINGS.md sections 3 and 5: (label, gain, lo, hi)
        ("Pads the U-Net missed (47)", 0.001, -0.014, 0.026),
        ("Pads under canopy (277)", 0.000, -0.007, 0.006),
        ("Pads where lidar is weakest, tile-wide design (159)", 0.015, 0.003, 0.036),
        ("Pads where lidar is weakest, local design", 0.003, -0.026, 0.029),
        ("Pits, frozen model on a second tile (36)", -0.017, -0.055, 0.020),
        ("Radar added to Sentinel-2, against decoys (633)", -0.006, -0.020, 0.020),
        ("Radar added to Sentinel-2, against clearings (60)", 0.029, -0.046, 0.118),
        ("Precision at 70% recall, after the U-Net score", 0.034, -0.008, 0.061),
    ]
    fig, ax = plt.subplots(figsize=(11, 5.2))
    y = np.arange(len(rows))[::-1]
    for yi, (lab, g, lo, hi) in zip(y, rows):
        ax.plot([lo, hi], [yi, yi], color=BLUE, lw=2.4)
        ax.plot([g], [yi], "o", color=BLUE, mec=INK, ms=9, zorder=3)
        ax.text(-0.075, yi, lab, ha="right", va="center", fontsize=9.6)
        ax.text(max(hi, 0.0) + 0.006, yi, f"{g:+.3f}", va="center", fontsize=9.3)
    ax.axvline(0, color=INK, lw=1.0)
    ax.axvline(0.05, color=ORANGE, lw=2.0, ls=(0, (5, 3)))
    ax.text(0.052, len(rows) - 0.35, "pre-set bar:\n+0.05", color=INK, fontsize=9.5, ha="left", va="bottom", fontweight="bold")
    ax.text(0.0, len(rows) - 0.35, "no gain", fontsize=9.5, ha="center", va="bottom")
    ax.set_xlim(-0.075, 0.13)
    ax.set_ylim(-0.7, len(rows) + 0.6)
    ax.set_yticks([])
    ax.set_xlabel("Gain from adding the radar (AUC points; the last row is precision points)")
    for s in ("left",):
        ax.spines[s].set_visible(False)
    ax.set_title("No estimate reached the +0.05 bar we set in advance")
    ax.text(0.0, -0.20, "Dot: best estimate.  Line: 95% interval.  Long lines mean few samples, so a gain up to about 0.06 to 0.12 is not ruled out\nin the two smallest tests.", transform=ax.transAxes, fontsize=8.8, color=GREY, va="top")
    save(fig, "nisar_gain_over_lidar_9t.png")


# ---------------------------------------------------------------- 10. what the radar sees
def fig_r2():
    fig, ax = plt.subplots(figsize=(10, 4.8))
    groups = ["Whole tile", "Closed canopy\n(cover above 0.8)", "Open ground\n(cover below 0.25)"]
    opt = [0.52, 0.22, 0.82]  # docs/analysis_log.md 2026-10-27
    lid = [0.04, 0.17, 0.26]
    both = [0.54, 0.33, None]
    x = np.arange(3)
    w = 0.26
    ax.bar(x - w, opt, w, color=BLUE, label="Sentinel-2 optical (vegetation)")
    ax.bar(x, lid, w, color=ORANGE, label="Lidar (canopy height, cover, slope, elevation)")
    for i, b in enumerate(both):
        if b is not None:
            ax.bar(x[i] + w, b, w, color=GREY, label="Both" if i == 0 else None)
            ax.text(x[i] + w, b + 0.015, f"{b:.2f}", ha="center", fontsize=9.5)
        else:
            ax.text(x[i] + w, 0.02, "not\nreported", ha="center", fontsize=8.5, color=GREY)
    for xi, v in zip(x - w, opt):
        ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", fontsize=9.5)
    for xi, v in zip(x, lid):
        ax.text(xi, v + 0.015, f"{v:.2f}", ha="center", fontsize=9.5)
    ax.set_xticks(x)
    ax.set_xticklabels(groups)
    ax.set_ylabel("Share of HV radar variation explained (R²)")
    ax.set_ylim(0, 0.95)
    ax.set_xlim(-0.6, 2.75)
    ax.legend(frameon=False, fontsize=9.3, loc="upper left")
    ax.set_title("Over the tile, radar brightness follows vegetation type more than canopy structure")
    save(fig, "nisar_what_radar_follows_9t.png")


# ---------------------------------------------------------------- 11. wet vs dry
def fig_wet_dry():
    d = pd.read_csv(ROOT / "data/9t/results/nisar/nisar_pit_wet_dry_db_9t.csv")
    w = pd.read_csv(ROOT / "data/9t/results/pit/pit_inside_wet_intensity_9t.csv").set_index("pit_inside_id")
    g = d.groupby(["label", "pit"]).db.agg(["mean", "std", "count"]).reset_index()
    g["se"] = g["std"] / np.sqrt(g["count"])
    g["lidar"] = g.pit.map(w.int_ratio)
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.2))
    rng = np.random.default_rng(3)
    for ax, col, ylab, title in [(axes[0], "mean", "Radar: pit centre minus ring, dB (average of 36 dates)", "NISAR radar cannot tell them apart"),
                                  (axes[1], "lidar", "Lidar: laser return strength inside pit / around it", "Lidar laser strength separates them")]:
        for k, lab in enumerate(["wet", "dry"]):
            s = g[g.label == lab]
            s = s.sort_values(col).reset_index(drop=True)
            xj = k + np.array([-0.2, 0.0, 0.2])[np.arange(len(s)) % 3]
            col_ = BLUE if lab == "wet" else ORANGE
            mk = "o" if lab == "wet" else "s"
            if col == "mean":
                ax.errorbar(xj, s["mean"], yerr=s.se, fmt="none", ecolor=col_, lw=1.3, capsize=0, zorder=2)
            ax.plot(xj, s[col], mk, color=col_, mec=INK, ms=9, zorder=3)
            for xx, yy, pid in zip(xj, s[col], s.pit):
                ax.text(xx + 0.07, yy, str(pid), fontsize=7.8, color=INK, va="center")
            m = s[col].mean()
            ax.hlines(m, k - 0.32, k + 0.32, color=INK, lw=2)
        ax.set_xticks([0, 1])
        ax.set_xticklabels(["Wet pits (8)", "Dry pits (5)"], fontsize=10.5)
        ax.set_xlim(-0.6, 1.6)
        ax.set_ylabel(ylab, fontsize=9.5)
        ax.set_title(title, fontsize=11.5)
    axes[1].axhline(1.0, color=GREY, lw=1.0, ls=(0, (4, 3)))
    axes[1].text(1.55, 1.03, "equal to surroundings", ha="right", fontsize=8.8, color=GREY)
    axes[0].text(-0.55, axes[0].get_ylim()[1] * 0.97, "Whiskers: standard error over 36 dates.\nBlack bar: group mean.", fontsize=8.5, color=GREY, va="top")
    fig.suptitle("Wet and dry pits, labelled by eye: lidar laser strength separates them, NISAR does not", x=0.01, ha="left", fontsize=12.5, fontweight="bold", y=1.0)
    fig.subplots_adjust(left=0.07, right=0.99, wspace=0.22)
    save(fig, "nisar_wet_vs_dry_pits_9t.png")
    print(g.groupby("label")["mean"].mean().round(2).to_dict())


# ---------------------------------------------------------------- 12. timeline of the work
def fig_timeline():
    rows = [  # date, headline, outcome (n none, w weak, f fixed or confirmed)
        ("26 Sep", "Pads against their forest ring (GCOV, one date)", "w", "Pads about 0.3 dB darker. It is the clearing, not the pad."),
        ("30 Sep", "31-date stack at 5 m, pads and pits against decoys", "n", "Result flips with a few metres of shift. Seasonal change adds nothing."),
        ("5 Oct", "Interferograms at 506 pits", "n", "Coherence +0.0001. Motion noise 7.5 mm for pits and decoys alike."),
        ("7 Oct", "Steel, pad change, slope motion", "n", "Wells 0.1 dB brighter than decoys. No well flagged as moving."),
        ("9 to 13 Oct", "Radar placed 10 m off the lidar. Traced and fixed.", "f", "Error 10 m down to about 1 m. 46 of 48 blocks within 2.5 m."),
        ("13 to 14 Oct", "All tests re-run on the corrected stack", "w", "Pad darkening gone. Pit leads (+0.2 dB) remain but are small."),
        ("19 to 21 Oct", "Review fixes, 40-decoy swap test, wells snapped to lidar", "n", "Pit leads of +0.2 dB held. Wells 0.7% against 0.9% for controls."),
        ("21 Oct", "Bright steady targets across tracks", "f", "Stable objects repeat 6 to 8 times chance. Chips on 28 Oct: buildings and bridges, not wells."),
        ("23 Oct", "Warren swath, 684 wells", "n", "Wells 3.9% against 5.2% for random pixels."),
        ("26 Oct", "303 radar features, then an outside audit", "n", "Early 0.71 to 0.88 was mostly place. Corrected: 0.48 to 0.64."),
        ("27 Oct", "Follow-ups: where lidar is weak, against Sentinel-2", "n", "No gain over lidar or Sentinel-2. Radar tracks vegetation type."),
        ("28 Oct", "Leaf-off and snow dates", "f", "Only 3 NISAR dates are bare and snow-free. None in Feb to May."),
        ("29 Oct to 1 Nov", "Sentinel-1 early April, wet pits, the box", "n", "No bright steady return. Wet and dry pits overlap."),
    ]
    fig, ax = plt.subplots(figsize=(11.5, 8.0))
    n = len(rows)
    y = np.arange(n)[::-1]
    ax.plot([0.0] * 2, [-0.6, n - 0.4], color=GRID, lw=3, zorder=0)
    mk = {"n": ("X", ORANGE), "w": ("D", LBLUE), "f": ("o", BLUE)}
    for yi, (dt, head, out, note) in zip(y, rows):
        m, c = mk[out]
        ax.plot([0.0], [yi], m, color=c, mec=INK, mew=0.9, ms=12 if m != "o" else 12, zorder=3)
        ax.text(-0.06, yi, dt, ha="right", va="center", fontsize=9.8, fontweight="bold")
        ax.text(0.06, yi + 0.13, head, va="center", fontsize=10.3, fontweight="bold")
        ax.text(0.06, yi - 0.22, note, va="center", fontsize=9.4)
    ax.set_xlim(-0.55, 1.55)
    ax.set_ylim(-0.9, n - 0.1)
    ax.axis("off")
    ax.plot([], [], "X", color=ORANGE, mec=INK, ms=10, label="No usable signal")
    ax.plot([], [], "D", color=LBLUE, mec=INK, ms=9, label="Weak or depends on set-up")
    ax.plot([], [], "o", color=BLUE, mec=INK, ms=10, label="Method fixed or fact confirmed")
    ax.legend(frameon=False, loc="lower right", fontsize=9.8)
    ax.set_title("What we did, in order, and how each step came out  (2026)", fontsize=13, pad=10)
    save(fig, "nisar_work_timeline_9t.png")


if __name__ == "__main__":
    fig_ideas()
    fig_scale()
    fig_views()
    fig_calendar()
    fig_placement()
    fig_auc()
    fig_staircase()
    fig_steel()
    fig_gain()
    fig_r2()
    fig_wet_dry()
    fig_timeline()
