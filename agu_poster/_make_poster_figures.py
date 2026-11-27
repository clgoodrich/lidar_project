"""Poster figures for the AGU poster, tile 9t. Every model output shown is held-out (out-of-fold).

Writes agu_poster/figures/:
  poster_hero_heldout_9t.png        held-out pit and pad predictions on hillshade, with a hit, a miss and a false alarm
  poster_channels_one_pit_9t.png    the seven input channels around one pit
  poster_signs_gallery_9t.png       three pits, three pads, three road segments on hillshade, hand outlines
  poster_cv_folds_pit_9t.png        the five held-out block sets of the pit split
  poster_pipeline_diagram.png       processing steps
  poster_pr_curves_heldout_9t.png   precision-recall, ranked candidates, IoU 0.3, held-out
  poster_optical_vs_lidar_9t.png    optical and RRIM pair, from the user's RemoteSensing_option2.pptx

Inputs (read only)
  data/9t/derived/05/hillshade_9t_05.tif, features_pit_9t_05.tif, pit_blocks_9t.gpkg, pad_blocks_9t.gpkg
  data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif  (uint8, p = v / 254, 255 = no fold)
  data/9t/models/pad/unet_cv5/fold{k}/pad_prob_cvfold{k}_9t_05.tif + pad_cv5_fold_assignment_9t.csv (block -> fold)
  data/9t/models/{pit,pad}/unet_cv5/*_per_fold_9t.csv  (F2 threshold per fold)
  data/9t/results/operating_point/pr_froc_curve_points_ranked_candidates_heldout_cv5_pit_pitsmrf_pad_9t.csv
  qgis/annotations/annotations_proj.gpkg (pit_inside, pit_outside, plat, roads)

Palette (dataviz validate_palette.js, light, --pairs all, 2026-11-09): pit #eb6834, pad #2a78d6, road #1baf7a.
Pit is orange so the small pits stand out on the translucent blue pads (swapped 2026-11-09 at the user request).
Worst CVD pair road/pad dE 9.2 deutan, tritan 9.6; normal floor 24.0; road 2.74:1 contrast (WARN), so every
class is also named by a direct label. No red carries meaning.

Run
    python agu_poster/_make_poster_figures.py
"""
from __future__ import annotations

import io
import zipfile
from pathlib import Path

import geopandas as gpd
import matplotlib
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from scipy import ndimage as ndi

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "figures"
D05 = ROOT / "data/9t/derived/05"
MOD = ROOT / "data/9t/models"
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
PR = ROOT / "data/9t/results/operating_point/pr_froc_curve_points_ranked_candidates_heldout_cv5_pit_pitsmrf_pad_9t.csv"
DECK = ROOT / "RemoteSensing_option2.pptx"

PIT, PAD, ROAD = "#eb6834", "#2a78d6", "#1baf7a"
# Map overlays sit on the red-tinted RRIM, so they use blue, yellow and white, which separate from the teal and brown RRIM.
MPIT, MPAD, MROAD = "#1A3CFF", "#FFE000", "#FFFFFF"
INK, MUTED, HELD, OTHER = "#2B2F36", "#6B6B6B", "#2a78d6", "#D9D9D9"
DPI = 200
plt.rcParams.update({"font.family": "Georgia", "font.size": 32, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK})
HALO = [pe.withStroke(linewidth=6, foreground="white")]


def read(path, bounds, band=1):
    with rasterio.open(path) as r:
        w = from_bounds(*bounds, r.transform)
        return r.read(band, window=w, boundless=True, fill_value=r.nodata if r.nodata is not None else 0)


def grid(bounds, res=0.5):
    x0, y0, x1, y1 = bounds
    return rasterio.transform.from_origin(x0, y1, res, res), (int(round((y1 - y0) / res)), int(round((x1 - x0) / res)))


def f2_thresholds(name):
    t = pd.read_csv(MOD / name / "unet_cv5" / f"{name}_cv5_per_fold_9t.csv")
    return t[t.objective == "f2"].set_index("fold").prob_threshold.to_dict()


def block_fold(name):
    a = pd.read_csv(MOD / name / "unet_cv5" / f"{name}_cv5_fold_assignment_9t.csv").dropna()
    a = a.drop_duplicates("block_id")
    b = gpd.read_file(D05 / f"{name}_blocks_9t.gpkg", layer="blocks")
    return b.merge(a[["block_id", "fold"]], on="block_id")


def oof(bounds):
    """Held-out probability and threshold maps for pits and pads over bounds."""
    tr, shape = grid(bounds)
    v = read(MOD / "pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif", bounds)
    pit_p = np.where(v == 255, np.nan, v / 254.0)
    pf = block_fold("pit")
    pit_fold = rasterize(((g, int(f)) for g, f in zip(pf.geometry, pf.fold)), shape, transform=tr, fill=-1)
    th = f2_thresholds("pit")
    pit_t = np.vectorize(lambda f: th.get(f, np.nan))(pit_fold)
    df = block_fold("pad")
    pad_fold = rasterize(((g, int(f)) for g, f in zip(df.geometry, df.fold)), shape, transform=tr, fill=-1)
    pad_p = np.full(shape, np.nan)
    for k in range(5):
        m = pad_fold == k
        if m.any():
            pad_p[m] = read(MOD / f"pad/unet_cv5/fold{k}/pad_prob_cvfold{k}_9t_05.tif", bounds)[m]
    th = f2_thresholds("pad")
    pad_t = np.vectorize(lambda f: th.get(f, np.nan))(pad_fold)
    return pit_p >= pit_t, pad_p >= pad_t, (pit_fold >= 0) & (pad_fold >= 0)


def ann(layer):
    return gpd.read_file(ANN, layer=layer).to_crs("EPSG:6346")


def hs(bounds):
    return read(D05 / "hillshade_9t_05.tif", bounds).astype(float)


def show_hs(ax, bounds):
    """Red Relief Image Map (RGB) as the base image."""
    with rasterio.open(D05 / "rrim_openness_9t_05.tif") as r:
        w = from_bounds(*bounds, r.transform)
        a = np.moveaxis(r.read(window=w, boundless=True, fill_value=0), 0, -1)
    ax.imshow(a, extent=(bounds[0], bounds[2], bounds[1], bounds[3]), interpolation="bilinear")


def sci_scalebar(ax, x, y, length, fs=22, nseg=2):
    """Standard map scale bar: alternating black and white blocks with ticks 0 and full length beneath, on a tight white box.
    (x, y) is the lower-left corner of the bar in data units."""
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    fig = ax.figure
    w_in = ax.get_position().width * fig.get_figwidth()
    h_in = ax.get_position().height * fig.get_figheight()
    ux, uy = (x1 - x0) / w_in / 72, (y1 - y0) / h_in / 72      # data units per point
    bar_h = 7 * fs / 22 * uy * 2.2
    lab = f"{length:g} m"
    half_lab = 0.5 * len(lab) * fs * 0.55 * ux
    pad = 4 * ux
    top = y + bar_h + 3 * uy
    bot = y - 3 * uy - fs * 1.15 * uy - 3 * uy
    left, right = x - 0.5 * fs * 0.55 * ux - pad, x + length + half_lab + pad
    ax.add_patch(Rectangle((left, bot), right - left, top - bot, fc="white", ec="none", alpha=0.88, zorder=5))
    seg = length / nseg
    for i in range(nseg):
        ax.add_patch(Rectangle((x + i * seg, y), seg, bar_h, fc="black" if i % 2 == 0 else "white", ec="black", lw=1.5, zorder=6))
    ax.text(x, y - 3 * uy, "0", ha="center", va="top", fontsize=fs, color="black", zorder=7)
    ax.text(x + length, y - 3 * uy, lab, ha="center", va="top", fontsize=fs, color="black", zorder=7)


def overlay(ax, mask, bounds, color, alpha=0.55):
    rgba = np.zeros(mask.shape + (4,))
    rgba[mask] = matplotlib.colors.to_rgba(color, alpha)
    ax.imshow(rgba, extent=(bounds[0], bounds[2], bounds[1], bounds[3]), interpolation="nearest")


def outline(ax, gdf, bounds, color, lw=3, ls="-"):
    x0, y0, x1, y1 = bounds
    g = gdf.cx[x0:x1, y0:y1]
    if len(g):
        g.boundary.plot(ax=ax, color="white", linewidth=lw + 3)
        g.boundary.plot(ax=ax, color=color, linewidth=lw, linestyle=ls)


def bare(ax, bounds):
    ax.set_xlim(bounds[0], bounds[2]); ax.set_ylim(bounds[1], bounds[3])
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)


def scalebar(ax, bounds, length, label):
    x0, y0, x1, y1 = bounds
    w, h = x1 - x0, y1 - y0
    bx, by = x0 + 0.04 * w, y0 + 0.06 * h
    ax.add_patch(Rectangle((bx - 0.01 * w, by - 0.03 * h), length + 0.02 * w, 0.13 * h, color="white", alpha=0.85))
    ax.plot([bx, bx + length], [by, by], color=INK, lw=6, solid_capstyle="butt")
    ax.text(bx + length / 2, by + 0.015 * h, label, ha="center", va="bottom", fontsize=26, color=INK)


# ---------------------------------------------------------------------------
def pick_window():
    """375 m tall, 750 m wide window on the pit block grid with full held-out coverage and the most features."""
    pb = block_fold("pit").set_index(["ix", "iy"])
    db = block_fold("pad")
    pits, pads = ann("pit_outside"), ann("plat")
    cands = []
    for (ix, iy), r in pb.iterrows():
        if (ix + 1, iy) not in pb.index:
            continue
        x0, y0, _, y1 = r.geometry.bounds
        b = (x0, y0, x0 + 750, y1)
        from shapely.geometry import box
        bb = box(*b)
        if db.geometry.intersection(bb).area.sum() < 0.999 * bb.area:
            continue
        n = len(pits.cx[b[0]:b[2], b[1]:b[3]]) + len(pads.cx[b[0]:b[2], b[1]:b[3]])
        cands.append((n, b))
    return [b for n, b in sorted(cands, reverse=True)]


def classify(mask, truth, bounds):
    """Connected predicted objects -> hit / false alarm; truth polygons -> found / missed."""
    tr, shape = grid(bounds)
    lab, n = ndi.label(mask)
    tmask = rasterize(((g, 1) for g in truth.geometry), shape, transform=tr, fill=0).astype(bool)
    objs = ndi.find_objects(lab)
    fa = []
    for i, sl in enumerate(objs, 1):
        o = lab[sl] == i
        if o.sum() >= 16 and not (tmask[sl] & o).any():
            cy, cx = ndi.center_of_mass(o)
            fa.append((bounds[0] + (sl[1].start + cx) * 0.5, bounds[3] - (sl[0].start + cy) * 0.5, int(o.sum())))
    hits, miss = [], []
    for g in truth.geometry:
        m = rasterize([(g, 1)], shape, transform=tr, fill=0).astype(bool)
        if not m.any():
            continue
        (hits if (m & mask).any() else miss).append(g)
    return hits, miss, fa


def fig_hero():
    """Classic multi-panel map. (a) one held-out block with coordinate axes, (b-d) 50 m details, framed legend."""
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    pits_rim, pads = ann("pit_outside"), ann("plat")
    for b in pick_window()[:25]:
        b = (b[0], b[1] + 31, b[2], b[3] - 32)      # 750 x 312 m, aspect 2.4, fills the wide panel
        pit_m, pad_m, cover = oof(b)
        x0, y0, x1, y1 = b
        m = 30
        hits, miss, fa = classify(pit_m, pits_rim.cx[x0 + m:x1 - m, y0 + m:y1 - m], b)
        fa = [f for f in fa if x0 + m < f[0] < x1 - m and y0 + m < f[1] < y1 - m]
        if hits and miss and fa:
            break
    fig = plt.figure(figsize=(27.6, 8.2), dpi=DPI)
    ax = fig.add_axes([0.075, 0.15, 0.62, 0.83])
    show_hs(ax, b)
    overlay(ax, pad_m & cover, b, MPAD, 0.28)
    overlay(ax, pit_m & cover, b, MPIT, 0.75)
    for g, col, ls in ((pads, MPAD, "--"), (pits_rim, MPIT, "-")):
        gg = g.cx[x0:x1, y0:y1]
        if len(gg):
            gg.boundary.plot(ax=ax, color=col, linewidth=2.2, linestyle=ls)
    ax.set_xlim(x0, x1); ax.set_ylim(y0, y1)
    ax.set_xticks(np.arange(np.ceil(x0 / 250) * 250, x1 + 1, 250))
    ax.set_yticks(np.arange(np.ceil(y0 / 100) * 100 + 100, y1 + 1, 100))
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.tick_params(labelsize=28, length=8, width=1.5)
    ax.set_xlabel("Easting (m), EPSG:6346", fontsize=30)
    ax.set_ylabel("Northing (m)", fontsize=30)
    for s in ax.spines.values():
        s.set_linewidth(1.5); s.set_color(INK)
    # standard scale bar and north arrow, drawn on the map
    sci_scalebar(ax, x0 + 255, y1 - 78, 100, fs=26, nseg=2)
    ax.annotate("", xy=(x1 - 30, y1 - 40), xytext=(x1 - 30, y1 - 78),
                arrowprops=dict(arrowstyle="-|>", color="white", lw=3, mutation_scale=28))
    ax.text(x1 - 30, y1 - 6, "N", ha="center", va="top", fontsize=28, color="white", path_effects=[pe.withStroke(linewidth=5, foreground="black")])
    ax.text(0.012, 0.97, "(a)", transform=ax.transAxes, va="top", fontsize=34, color="black", path_effects=HALO)
    # detail windows
    picks = []
    g = max(hits, key=lambda g: g.area); picks.append(("b", g.centroid.x, g.centroid.y))
    g = miss[0]; picks.append(("c", g.centroid.x, g.centroid.y))
    f = max(fa, key=lambda t_: t_[2]); picks.append(("d", f[0], f[1]))
    half = 25
    for i, (lab, cx, cy) in enumerate(picks):
        ib = (cx - half, cy - half, cx + half, cy + half)
        ax.add_patch(Rectangle((ib[0], ib[1]), 2 * half, 2 * half, fill=False, ec="black", lw=2.5))
        ax.text(ib[2] + 6, ib[3], lab, fontsize=32, color="black", va="top", path_effects=HALO)
        side = 0.30
        ia = fig.add_axes([0.715, 0.68 - i * 0.325 + 0.02, side * 8.2 / 27.6, side])
        pm, _, _ = oof(ib)
        show_hs(ia, ib)
        overlay(ia, pm, ib, MPIT, 0.75)
        for gdf, col, ls in ((pads, MPAD, "--"), (pits_rim, MPIT, "-")):
            gg = gdf.cx[ib[0]:ib[2], ib[1]:ib[3]]
            if len(gg):
                gg.boundary.plot(ax=ia, color=col, linewidth=2.5, linestyle=ls)
        ia.set_xlim(ib[0], ib[2]); ia.set_ylim(ib[1], ib[3]); ia.set_xticks([]); ia.set_yticks([])
        for s in ia.spines.values():
            s.set_linewidth(1.5); s.set_color("black")
        ia.text(0.04, 0.96, f"({lab})", transform=ia.transAxes, va="top", fontsize=30, color="black", path_effects=HALO)
        sci_scalebar(ia, ib[0] + 5, ib[1] + 9, 10, fs=18, nseg=2)
    handles = [Patch(fc=MPIT, ec="none", alpha=0.75, label="Pit, model output"),
               Line2D([0], [0], color=MPIT, lw=3, label="Pit, hand-drawn"),
               Patch(fc=MPAD, ec="none", alpha=0.28, label="Pad, model output"),
               Line2D([0], [0], color=MPAD, lw=3, ls="--", label="Pad, hand-drawn")]
    lg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.815, 0.98), fontsize=26, frameon=True,
                    fancybox=False, edgecolor="black", framealpha=1.0, borderpad=0.8, labelspacing=0.9,
                    handlelength=2.2)
    lg.get_frame().set_linewidth(1.5)
    fig.savefig(OUT / "poster_hero_heldout_9t.png", dpi=DPI)
    plt.close(fig)
    return b, len(hits), len(miss), len(fa)


def fig_channels():
    pits = ann("pit_outside")
    g = pits.iloc[(pits.area - pits.area.median()).abs().argsort().iloc[0]].geometry
    c = g.centroid
    b = (c.x - 20, c.y - 20, c.x + 20, c.y + 20)
    names = ["Relief 25 m", "Relief 5 m", "Slope", "Position", "Openness +", "Openness −", "Roughness"]
    fig, axs = plt.subplots(1, 7, figsize=(13.47, 2.9), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=0.80, bottom=0.0, wspace=0.04)
    for i, (ax, nm) in enumerate(zip(axs, names)):
        a = read(D05 / "features_pit_9t_05.tif", b, band=i + 1).astype(float)
        lo, hi = np.nanpercentile(a, [2, 98])
        ax.imshow(a, cmap="gray", vmin=lo, vmax=hi)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_title(nm, fontsize=22, color=INK, pad=6)
    fig.savefig(OUT / "poster_channels_one_pit_9t.png", dpi=DPI)
    plt.close(fig)


def fig_gallery():
    rng = np.random.default_rng(20261109)
    with rasterio.open(D05 / "hillshade_9t_05.tif") as r:
        tb = r.bounds
    inner = lambda g: g.cx[tb.left + 100:tb.right - 100, tb.bottom + 100:tb.top - 100]  # noqa: E731
    pits, pads, roads = inner(ann("pit_outside")), inner(ann("plat")), inner(ann("roads"))
    fig, axs = plt.subplots(1, 3, figsize=(13.47, 4.4), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0.04)
    keep = {"Pit": 0, "Pad": 1, "Road": 1}   # one example per sign, from the same seeded draw as before
    rows = (("Pit", pits, MPIT, 30, "-"), ("Pad", pads, MPAD, 90, "--"), ("Road", roads, MROAD, 90, "-"))
    for r, (lab, gdf, col, half, ls) in enumerate(rows):
        big = gdf[gdf.length > 120] if lab == "Road" else gdf[gdf.area > gdf.area.quantile(0.4)]
        for c, idx in enumerate(rng.choice(len(big), 3, replace=False)):
            if c != keep[lab]:
                continue
            p = big.iloc[idx].geometry
            pt = p.interpolate(0.5, normalized=True) if lab == "Road" else p.centroid
            b = (pt.x - half, pt.y - half, pt.x + half, pt.y + half)
            ax = axs[r]
            show_hs(ax, b)
            if lab == "Road":
                gdf.cx[b[0]:b[2], b[1]:b[3]].plot(ax=ax, color="white", lw=8)
                gdf.cx[b[0]:b[2], b[1]:b[3]].plot(ax=ax, color=col, lw=4)
            else:
                outline(ax, gdf, b, col, 4, ls)
            bare(ax, b)
            L = 20 if lab == "Pit" else 50
            ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
            sci_scalebar(ax, b[0] + 0.08 * 2 * half, b[1] + 0.13 * 2 * half, L, fs=24)
    fig.savefig(OUT / "poster_signs_gallery_9t.png", dpi=DPI)
    plt.close(fig)


def fig_folds():
    pf = block_fold("pit")
    allb = gpd.read_file(D05 / "pit_blocks_9t.gpkg", layer="blocks")
    fig, axs = plt.subplots(1, 5, figsize=(13.47, 2.9), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=0.72, bottom=0, wspace=0.06)
    for k, ax in enumerate(axs):
        allb.plot(ax=ax, color="white", edgecolor=OTHER, lw=0.8)
        pf[pf.fold != k].plot(ax=ax, color=OTHER, edgecolor="white", lw=0.8)
        pf[pf.fold == k].plot(ax=ax, color=HELD, edgecolor="white", lw=0.8)
        ax.set_axis_off()
        ax.set_title(f"Test {k + 1}", fontsize=26, color=INK, pad=14)
    fig.savefig(OUT / "poster_cv_folds_pit_9t.png", dpi=DPI)
    plt.close(fig)


def fig_pipeline():
    nl = chr(10)
    rows = ([f"Lidar{nl}points", f"Ground{nl}filter", f"Bare earth{nl}0.5 m", f"7 terrain{nl}layers"],
            [f"U-Net{nl}per sign", "Cutoff", f"Candidate{nl}outlines"])
    W, H = 13.47, 3.6
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_axis_off()
    w, h, gap = 2.95, 1.3, 0.47
    prev = None
    for r, (row, y) in enumerate(zip(rows, (2.2, 0.1))):
        for i, s in enumerate(row):
            x = 0.05 + (i if r == 0 else 3 - i) * (w + gap)
            hi = s.startswith("U-Net")  # the model step is the one shaded box
            ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="square,pad=0.0",
                                        fc="white", ec=INK, lw=2.5))
            ax.text(x + w / 2, y + h / 2, s, ha="center",
                    va="center", fontsize=32, color=INK, fontweight="normal", linespacing=1.0)
            if prev is not None:
                px, py = prev
                if py == y and x > px:
                    a, bb = (px + w + 0.04, y + h / 2), (x - 0.04, y + h / 2)
                elif py == y:
                    a, bb = (px - 0.04, y + h / 2), (x + w + 0.04, y + h / 2)
                else:
                    a, bb = (px + w / 2, py - 0.04), (x + w / 2, y + h + 0.04)
                ax.add_patch(FancyArrowPatch(a, bb, arrowstyle="-|>", mutation_scale=30, color=MUTED, lw=3,
                                             connectionstyle="arc3,rad=0"))
            prev = (x, y)
    fig.savefig(OUT / "poster_pipeline_diagram.png", dpi=DPI)
    plt.close(fig)


def fig_pr():
    d = pd.read_csv(PR)
    d = d[d.tau == 0.3]
    fig, ax = plt.subplots(figsize=(13.47, 4.0), dpi=DPI)
    fig.subplots_adjust(left=0.13, right=0.97, top=0.95, bottom=0.30)
    for name, col, lab in (("pit", PIT, "Pits, AP 0.82"), ("pad", PAD, "Pads, AP 0.75")):
        s = d[d.model == name].sort_values("rank")
        ax.plot(s.recall, s.precision, color=col, lw=5)
        i = int(len(s) * (0.80 if name == "pit" else 0.62))
        ax.text(s.recall.iloc[i], s.precision.iloc[i] + (0.05 if name == "pit" else -0.24), lab, color=INK, fontsize=34,
                fontweight="normal", ha="center", path_effects=HALO)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.set_yticks([0, 0.5, 1]); ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    ax.grid(color="#E6E6E6", lw=1.5); ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(axis="x", pad=14)
    fig.savefig(OUT / "poster_pr_curves_heldout_9t.png", dpi=DPI)
    plt.close(fig)


def fig_optical():
    with zipfile.ZipFile(DECK) as z:
        ims = [Image.open(io.BytesIO(z.read(f"ppt/media/image{i}.png"))).convert("RGB") for i in (2, 3)]
    fig, axs = plt.subplots(1, 2, figsize=(13.47, 3.25), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0.03)
    for ax, im in zip(axs, ims):
        ax.imshow(im, aspect="auto"); ax.set_axis_off()
    fig.savefig(OUT / "poster_optical_vs_lidar_9t.png", dpi=DPI)
    plt.close(fig)


D613 = ROOT / "data/613590/derived"


def show_rrim_613(ax, b):
    with rasterio.open(D613 / "05/rrim_openness_613590_05.tif") as r:
        w = from_bounds(*b, r.transform)
        a = np.moveaxis(r.read(window=w, boundless=True, fill_value=0), 0, -1)
    ax.imshow(a, extent=(b[0], b[2], b[1], b[3]), interpolation="bilinear")


def fig_transfer():
    """Tile 613590: the 9t-trained pit and pad models run on a tile they never saw. Predictions with hand outlines where drawn."""
    inf = D613 / "inference_05"
    full = (613500, 4590000, 618000, 4594500)
    pit_h, pad_h = ann("pit_inside"), ann("plat")
    W, H = 660, 420
    best = None
    for x0 in range(613500, 618000 - W, 60):
        for y0 in range(4590000, 4594500 - H, 60):
            b = (x0, y0, x0 + W, y0 + H)
            n = len(pit_h.cx[b[0]:b[2], b[1]:b[3]]) + len(pad_h.cx[b[0]:b[2], b[1]:b[3]])
            if best is None or n > best[0]:
                best = (n, b)
    b = best[1]
    pit_m = read(inf / "pit_argmax_613590_05.tif", b) == 1
    pad_m = read(inf / "pad_argmax_613590_05.tif", b) == 1
    hits, miss, fa = classify(pit_m, pit_h.cx[b[0]:b[2], b[1]:b[3]], b)
    fa = [f for f in fa if b[0] + 40 < f[0] < b[2] - 40 and b[1] + 40 < f[1] < b[3] - 40]
    fig = plt.figure(figsize=(13.47, 5.0), dpi=DPI)
    ax = fig.add_axes([0.105, 0.16, 0.50, 0.82])
    show_rrim_613(ax, b)
    overlay(ax, pad_m, b, MPAD, 0.30)
    overlay(ax, pit_m, b, MPIT, 0.80)
    for g, col, ls in ((pad_h, MPAD, "--"), (pit_h, MPIT, "-")):
        gg = g.cx[b[0]:b[2], b[1]:b[3]]
        if len(gg):
            gg.boundary.plot(ax=ax, color=col, linewidth=1.6, linestyle=ls)
    ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
    ax.set_xticks(np.arange(np.ceil(b[0] / 200) * 200, b[2] + 1, 200))
    ax.set_yticks(np.arange(np.ceil(b[1] / 200) * 200, b[3] + 1, 200))
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.tick_params(labelsize=17, length=6, width=1.2)
    ax.set_xlabel("Easting (m), EPSG:6346", fontsize=19)
    ax.set_ylabel("Northing (m)", fontsize=19)
    ax.text(0.015, 0.975, "(a)", transform=ax.transAxes, va="top", fontsize=24, color="black", path_effects=HALO)
    sci_scalebar(ax, b[2] - 190, b[1] + 60, 100, fs=16, nseg=2)
    picks = []
    if hits: picks.append(("b", max(hits, key=lambda g: g.area).centroid))
    if fa:
        f = max(fa, key=lambda t_: t_[2]); picks.append(("c", type("P", (), {"x": f[0], "y": f[1]})))
    half = 40
    for i, (lab, c) in enumerate(picks):
        ib = (c.x - half, c.y - half, c.x + half, c.y + half)
        ax.add_patch(Rectangle((ib[0], ib[1]), 2 * half, 2 * half, fill=False, ec="black", lw=2))
        ax.text(ib[2] + 6, ib[3], lab, fontsize=22, color="black", va="top", path_effects=HALO)
        side = 0.34
        ia = fig.add_axes([0.635 + i * 0.185, 0.50, 0.175, 0.175 * 13.47 / 5.0])
        show_rrim_613(ia, ib)
        pm = read(inf / "pit_argmax_613590_05.tif", ib) == 1
        pd_ = read(inf / "pad_argmax_613590_05.tif", ib) == 1
        overlay(ia, pd_, ib, MPAD, 0.30); overlay(ia, pm, ib, MPIT, 0.80)
        for gdf, col, ls in ((pad_h, MPAD, "--"), (pit_h, MPIT, "-")):
            gg = gdf.cx[ib[0]:ib[2], ib[1]:ib[3]]
            if len(gg):
                gg.boundary.plot(ax=ia, color=col, linewidth=2, linestyle=ls)
        ia.set_xlim(ib[0], ib[2]); ia.set_ylim(ib[1], ib[3]); ia.set_xticks([]); ia.set_yticks([])
        for s in ia.spines.values():
            s.set_linewidth(1.2); s.set_color("black")
        ia.text(0.05, 0.95, f"({lab})", transform=ia.transAxes, va="top", fontsize=20, color="black", path_effects=HALO)
        sci_scalebar(ia, ib[0] + 6, ib[1] + 14, 20, fs=11, nseg=2)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    handles = [Patch(fc=MPIT, ec="none", alpha=0.8, label="Pit, model output"),
               Line2D([0], [0], color=MPIT, lw=2.5, label="Pit, hand-drawn"),
               Patch(fc=MPAD, ec="none", alpha=0.3, label="Pad, model output"),
               Line2D([0], [0], color=MPAD, lw=2.5, ls="--", label="Pad, hand-drawn")]
    lg = fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.635, 0.44), fontsize=17, frameon=True,
                    fancybox=False, edgecolor="black", framealpha=1.0, borderpad=0.7, labelspacing=0.7)
    lg.get_frame().set_linewidth(1.2)
    fig.savefig(OUT / "poster_transfer_613590.png", dpi=DPI)
    plt.close(fig)
    return b, len(hits), len(miss), len(fa)


def fig_probmaps():
    """Tile 613590, 400 m window: (a) relief image with hand outlines, (b) pit and (c) pad probability, grey scale 0 to 1."""
    inf = D613 / "inference_05"
    pit_h, pad_h = ann("pit_inside"), ann("plat")
    S = 400
    best = None
    for x0 in range(613500, 618000 - S, 50):
        for y0 in range(4590000, 4594500 - S, 50):
            b = (x0, y0, x0 + S, y0 + S)
            n = len(pit_h.cx[b[0]:b[2], b[1]:b[3]]) + len(pad_h.cx[b[0]:b[2], b[1]:b[3]])
            if best is None or n > best[0]:
                best = (n, b)
    b = best[1]
    f613 = inf / "features_613590_05.tif"
    pp = prob_ensemble("pit", b, f613)
    dp = prob_ensemble("pad", b, f613)
    fig, axs = plt.subplots(1, 3, figsize=(13.47, 4.9), dpi=DPI)
    fig.subplots_adjust(left=0.105, right=0.985, top=0.97, bottom=0.25, wspace=0.07)
    ext = (b[0], b[2], b[1], b[3])
    show_rrim_613(axs[0], b)
    for g, col, ls in ((pad_h, MPAD, "--"), (pit_h, MPIT, "-")):
        gg = g.cx[b[0]:b[2], b[1]:b[3]]
        if len(gg):
            gg.boundary.plot(ax=axs[0], color=col, linewidth=2.0, linestyle=ls)
    im = axs[1].imshow(pp, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
    axs[2].imshow(dp, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
    for i, (ax, lab) in enumerate(zip(axs, "abc")):
        ax.set_xlim(b[0], b[2]); ax.set_ylim(b[1], b[3])
        ax.set_xticks([b[0] + 100, b[0] + 300]); ax.set_yticks([])
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.tick_params(labelsize=15, length=5, width=1.2)
        for s in ax.spines.values():
            s.set_linewidth(1.2); s.set_color("black")
        ax.text(0.03, 0.97, f"({lab})", transform=ax.transAxes, va="top", fontsize=22, color="black", path_effects=HALO)
    axs[0].set_yticks([b[1] + 100, b[1] + 300]); axs[0].set_ylabel("Northing (m)", fontsize=16)
    axs[0].tick_params(axis="y", labelsize=15)
    axs[1].set_xlabel("Easting (m), EPSG:6346", fontsize=17)
    sci_scalebar(axs[0], b[0] + 20, b[1] + 55, 100, fs=13, nseg=2)
    cax = fig.add_axes([0.76, 0.135, 0.22, 0.03])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.tick_params(labelsize=14, length=4); cb.set_label("Probability", fontsize=15, labelpad=2)
    fig.savefig(OUT / "poster_prob_maps_613590.png", dpi=DPI)
    plt.close(fig)
    return b, float(pp.max()), float(dp.max())


# ---------------------------------------------------------------------------
# 2026-11-27: four-panel hero (aerial, RRIM, pad probability, pit probability), Hann-blended
import sys as _sys
_sys.path.insert(0, str(ROOT / "notebooks/wellsight_v2"))
import torch  # noqa: E402
from _dl import DEVICE, UNet, predict_array  # noqa: E402
import requests  # noqa: E402
from pyproj import Transformer  # noqa: E402

FEAT9 = D05 / "features_pit_9t_05.tif"
TASKS_CV = {"pit": ("pit/unet_cv5", 3, 256, 128), "pad": ("pad/unet_cv5", 2, 384, 192)}
_MODEL_CACHE = {}
PADM = 96.0


def _load_fold_model(task, k):
    key = (task, k)
    if key not in _MODEL_CACHE:
        sub, ncls, _, _ = TASKS_CV[task]
        ck = torch.load(MOD / sub / f"fold{k}" / "best.pt", map_location=DEVICE, weights_only=False)
        m = UNet(in_ch=len(ck["channels"]), n_classes=ncls, base=32).to(DEVICE)
        m.load_state_dict(ck["state_dict"])
        m.eval()
        _MODEL_CACHE[key] = (m, np.asarray(ck["mu"], np.float32), np.asarray(ck["sd"], np.float32))
    return _MODEL_CACHE[key]


def read_feats(path, bounds):
    """Seven-channel stack over bounds plus PADM metres of context each side, 0.5 m."""
    pb = (bounds[0] - PADM, bounds[1] - PADM, bounds[2] + PADM, bounds[3] + PADM)
    with rasterio.open(path) as r:
        w = from_bounds(*pb, r.transform)
        a = r.read(window=w, boundless=True, fill_value=np.nan).astype(np.float32)
    return a


def crop_ctx(arr):
    i = int(round(PADM / 0.5))
    return arr[..., i:-i, i:-i]


def prob_heldout(task, bounds):
    """Out-of-fold class-1 probability over bounds on 9t: each pixel from the model that never saw its block. Hann blended."""
    feats = read_feats(FEAT9, bounds)
    tr, shape = grid(bounds)
    bf = block_fold(task)
    fold = rasterize(((g, int(f)) for g, f in zip(bf.geometry, bf.fold)), shape, transform=tr, fill=-1)
    _, ncls, patch, ov = TASKS_CV[task]
    out = np.full(shape, np.nan, np.float32)
    for k in sorted(set(np.unique(fold)) - {-1}):
        m, mu, sd = _load_fold_model(task, k)
        p = crop_ctx(predict_array(m, feats, mu, sd, patch=patch, overlap=ov, n_classes=ncls, hann=True)[1])
        out[fold == k] = p[fold == k]
    return out


def prob_ensemble(task, bounds, feat_path):
    """Mean of the five fold models, Hann blended. For a tile none of them saw."""
    feats = read_feats(feat_path, bounds)
    _, ncls, patch, ov = TASKS_CV[task]
    acc = 0
    for k in range(5):
        m, mu, sd = _load_fold_model(task, k)
        acc = acc + predict_array(m, feats, mu, sd, patch=patch, overlap=ov, n_classes=ncls, hann=True)[1]
    return crop_ctx(acc / 5.0)


def naip(bounds, year="20220619"):
    """NAIP leaf-on aerial over bounds (EPSG:6346) from Planetary Computer, windowed read. Returns RGB uint8."""
    stac = "https://planetarycomputer.microsoft.com/api/stac/v1"
    cx, cy = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
    ll = gpd.GeoSeries(gpd.points_from_xy([cx], [cy]), crs=6346).to_crs(4326).iloc[0]
    items = requests.post(f"{stac}/search", json={"collections": ["naip"], "intersects": {"type": "Point", "coordinates": [ll.x, ll.y]}, "limit": 20}, timeout=60).json()["features"]
    by = {f["properties"]["datetime"][:10].replace("-", ""): f for f in items}
    f = by[year]
    href = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/sign?href=" + f["assets"]["image"]["href"], timeout=60).json()["href"]
    with rasterio.open(href) as s:
        t = Transformer.from_crs(6346, s.crs, always_xy=True)
        x0, y0 = t.transform(bounds[0], bounds[1])
        x1, y1 = t.transform(bounds[2], bounds[3])
        win = from_bounds(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1), transform=s.transform)
        a = s.read([1, 2, 3], window=win, boundless=True, fill_value=0)
    return np.moveaxis(a, 0, -1)


def pick_window4(S=400):
    """S x S window on a 50 m step with held-out coverage for both tasks everywhere, most annotated pits and pads."""
    from shapely.geometry import box
    pbk, dbk = block_fold("pit"), block_fold("pad")
    pits, pads = ann("pit_inside"), ann("plat")
    best = []
    for x0 in range(619500, 624000 - S + 1, 50):
        for y0 in range(4593000, 4597500 - S + 1, 50):
            bb = box(x0, y0, x0 + S, y0 + S)
            if pbk.geometry.intersection(bb).area.sum() < 0.999 * bb.area or dbk.geometry.intersection(bb).area.sum() < 0.999 * bb.area:
                continue
            npit = len(pits.cx[x0:x0 + S, y0:y0 + S])
            npad = len(pads.cx[x0:x0 + S, y0:y0 + S])
            if npit >= 6 and npad >= 3:
                best.append((npit + npad, (x0, y0, x0 + S, y0 + S)))
    best.sort(reverse=True)
    return [b for _, b in best]


def show_rrim_9(ax, b):
    with rasterio.open(D05 / "rrim_openness_9t_05.tif") as r:
        w = from_bounds(*b, r.transform)
        a = np.moveaxis(r.read(window=w, boundless=True, fill_value=0), 0, -1)
    ax.imshow(a, extent=(b[0], b[2], b[1], b[3]), interpolation="bilinear")


def fig_hero4(b=None):
    pit_h, pad_h = ann("pit_inside"), ann("plat")
    b = b or pick_window4()[0]
    x0, y0, x1, y1 = b
    pit_p = prob_heldout("pit", b)
    pad_p = prob_heldout("pad", b)
    air = naip(b)
    W, H = 27.6, 8.0
    fig = plt.figure(figsize=(W, H), dpi=DPI)
    side, gap, left, bottom = 6.05, 0.33, 1.95, 1.75
    axs = [fig.add_axes([(left + i * (side + gap)) / W, bottom / H, side / W, side / H]) for i in range(4)]
    ext = (x0, x1, y0, y1)
    axs[0].imshow(air, extent=ext, interpolation="bilinear")
    show_rrim_9(axs[1], b)
    im = axs[2].imshow(pad_p, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
    axs[3].imshow(pit_p, cmap="gray", vmin=0, vmax=1, extent=ext, interpolation="nearest")
    for g, ax, col, ls in ((pad_h, axs[2], MPAD, "--"), (pit_h, axs[3], MPIT, "-")):
        gg = g.cx[x0:x1, y0:y1]
        if len(gg):
            gg.boundary.plot(ax=ax, color=col, linewidth=2.0, linestyle=ls)
    for i, ax in enumerate(axs):
        ax.set_xlim(x0, x1)
        ax.set_ylim(y0, y1)
        ax.set_xticks([x0 + 100, x0 + 300])
        ax.set_yticks([y0 + 100, y0 + 300] if i == 0 else [])
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.tick_params(labelsize=22, length=7, width=1.5)
        for s in ax.spines.values():
            s.set_linewidth(1.5)
            s.set_color("black")
        ax.text(0.03, 0.97, "(" + "abcd"[i] + ")", transform=ax.transAxes, va="top", fontsize=34, color="black", path_effects=HALO)
    fig.text(0.40 / W, (bottom + side / 2) / H, "Northing (m)", rotation=90, va="center", ha="center", fontsize=24)
    fig.text((left + side + gap / 2) / W, 0.80 / H, "Easting (m), EPSG:6346", ha="center", fontsize=24)
    sci_scalebar(axs[1], x0 + 20, y0 + 52, 100, fs=20, nseg=2)
    axs[1].annotate("", xy=(x1 - 25, y1 - 22), xytext=(x1 - 25, y1 - 75), arrowprops=dict(arrowstyle="-|>", color="white", lw=3, mutation_scale=30))
    axs[1].text(x1 - 25, y1 - 82, "N", ha="center", va="top", fontsize=28, color="white", path_effects=[pe.withStroke(linewidth=5, foreground="black")])
    cax = fig.add_axes([(left + 2 * (side + gap) + 0.6) / W, 0.95 / H, (2 * side + gap - 1.2) / W, 0.22 / H])
    cb = fig.colorbar(im, cax=cax, orientation="horizontal", ticks=[0, 0.5, 1])
    cb.ax.tick_params(labelsize=22, length=6)
    cb.set_label("Probability", fontsize=24, labelpad=4)
    fig.savefig(OUT / "poster_hero4_9t.png", dpi=DPI)
    plt.close(fig)
    return b


def fig_errors():
    """Found pit, missed pit, model pit with no hand label: three 50 m windows from one held-out window, F2 cutoff."""
    pits_rim, pads = ann("pit_outside"), ann("plat")
    pit_h = ann("pit_inside")
    for bw in pick_window()[:25]:
        b = (bw[0], bw[1] + 31, bw[2], bw[3] - 32)
        pit_m, pad_m, cover = oof(b)
        x0, y0, x1, y1 = b
        m = 30
        hits, miss, fa = classify(pit_m, pits_rim.cx[x0 + m:x1 - m, y0 + m:y1 - m], b)
        fa = [f for f in fa if x0 + m < f[0] < x1 - m and y0 + m < f[1] < y1 - m]
        if hits and miss and fa:
            break
    f = max(fa, key=lambda t_: t_[2])
    picks = [max(hits, key=lambda g: g.area).centroid, miss[0].centroid, type("P", (), {"x": f[0], "y": f[1]})]
    fig, axs = plt.subplots(1, 3, figsize=(13.47, 4.7), dpi=DPI)
    fig.subplots_adjust(left=0.01, right=0.99, top=0.99, bottom=0.01, wspace=0.03)
    half = 25
    for i, (ax, c) in enumerate(zip(axs, picks)):
        ib = (c.x - half, c.y - half, c.x + half, c.y + half)
        show_hs(ax, ib)
        pm, _, _ = oof(ib)
        overlay(ax, pm, ib, MPIT, 0.75)
        for gdf, col, ls in ((pads, MPAD, "--"), (pit_h, MPIT, "-")):
            gg = gdf.cx[ib[0]:ib[2], ib[1]:ib[3]]
            if len(gg):
                gg.boundary.plot(ax=ax, color=col, linewidth=2.5, linestyle=ls)
        ax.set_xlim(ib[0], ib[2])
        ax.set_ylim(ib[1], ib[3])
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_linewidth(1.5)
            s.set_color("black")
        ax.text(0.04, 0.96, "(" + "abc"[i] + ")", transform=ax.transAxes, va="top", fontsize=30, color="black", path_effects=HALO)
        sci_scalebar(ax, ib[0] + 3, ib[1] + 7, 10, fs=17, nseg=2)
    fig.savefig(OUT / "poster_errors_9t.png", dpi=DPI)
    plt.close(fig)
    return b, len(hits), len(miss), len(fa)


def main():
    OUT.mkdir(exist_ok=True)
    for f in (fig_gallery, fig_folds, fig_optical):
        f(); print(f.__name__)
    print("hero4 window:", fig_hero4())
    print("errors window, hits, misses, unlabelled:", fig_errors())
    print("transfer 613590 window, max pit, max pad:", fig_probmaps())


if __name__ == "__main__":
    main()
