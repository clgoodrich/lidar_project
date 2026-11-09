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
INK, MUTED, HELD, OTHER = "#2B2F36", "#6B6B6B", "#2a78d6", "#D9D9D9"
DPI = 200
plt.rcParams.update({"font.family": "Calibri", "font.size": 32, "axes.edgecolor": MUTED,
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
    a = hs(bounds)
    lo, hi = np.nanpercentile(a, [1, 99])
    ax.imshow(a, cmap="gray", vmin=lo, vmax=hi, extent=(bounds[0], bounds[2], bounds[1], bounds[3]),
              interpolation="bilinear")


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
    pits_rim, pads = ann("pit_outside"), ann("plat")
    # the most feature-rich window that holds at least one found pit, one missed pit and one false alarm
    for b in pick_window()[:25]:
        pit_m, pad_m, cover = oof(b)
        x0, y0, x1, y1 = b
        m = 30  # keep the insets off the edge
        hits, miss, fa = classify(pit_m, pits_rim.cx[x0 + m:x1 - m, y0 + m:y1 - m], b)
        fa = [f for f in fa if x0 + m < f[0] < x1 - m and y0 + m < f[1] < y1 - m]
        if hits and miss and fa:
            break
    fig = plt.figure(figsize=(27.6, 9.4), dpi=DPI)
    ax = fig.add_axes([0.0, 0.10, 0.62, 0.90])
    show_hs(ax, b)
    overlay(ax, pad_m & cover, b, PAD, 0.30)
    overlay(ax, pit_m & cover, b, PIT, 0.95)
    outline(ax, pads, b, PAD, 3, "--")
    outline(ax, pits_rim, b, PIT, 3)
    bare(ax, b)
    scalebar(ax, b, 100, "100 m")
    picks = []
    g = max(hits, key=lambda g: g.area)
    picks.append(("Found", "The model's pit (solid) sits inside|the hand-drawn rim.", g.centroid.x, g.centroid.y))
    g = miss[0]
    picks.append(("Missed", "A hand-drawn pit with no|model pit inside it.", g.centroid.x, g.centroid.y))
    f = max(fa, key=lambda t: t[2])
    picks.append(("Not in our labels", "The model marked a pit we never|drew. It may be one we overlooked.",
                  f[0], f[1]))
    half = 25
    for i, (lab, expl, cx, cy) in enumerate(picks):
        ib = (cx - half, cy - half, cx + half, cy + half)
        ax.add_patch(Rectangle((ib[0], ib[1]), 2 * half, 2 * half, fill=False, ec="white", lw=7))
        ax.add_patch(Rectangle((ib[0], ib[1]), 2 * half, 2 * half, fill=False, ec=INK, lw=3.5))
        ax.text(ib[0], ib[3] + 4, str(i + 1), fontsize=36, fontweight="bold", color=INK, path_effects=HALO)
        y0 = 1 - (i + 1) * 0.333 + 0.02
        ia = fig.add_axes([0.632, y0, 0.115, 0.30])
        pm, _, _ = oof(ib)
        show_hs(ia, ib)
        overlay(ia, pm, ib, PIT, 0.95)          # insets are about pits, so pads are outline only
        outline(ia, pads, ib, PAD, 3, "--")
        outline(ia, pits_rim, ib, PIT, 5)
        bare(ia, ib)
        fig.text(0.758, y0 + 0.22, f"{i + 1}  {lab}", fontsize=34, fontweight="bold", color=INK, va="center")
        fig.text(0.758, y0 + 0.10, expl.replace("|", chr(10)), fontsize=28, color=INK, va="center", linespacing=1.15)
    # legend, direct and in words
    lx = 0.0
    for txt, col, kind in (("Pit found by model", PIT, "fill"), ("Pit drawn by hand", PIT, "line"),
                           ("Pad found by model", PAD, "fill"), ("Pad drawn by hand", PAD, "dash")):
        y = 0.045
        if kind == "fill":
            fig.patches.append(Rectangle((lx, y - 0.016), 0.014, 0.032, transform=fig.transFigure, color=col,
                                         alpha=0.95 if col == PIT else 0.45))
        else:
            fig.lines.append(plt.Line2D([lx, lx + 0.014], [y, y], transform=fig.transFigure, color=col, lw=5,
                                        ls="--" if kind == "dash" else "-"))
        fig.text(lx + 0.019, y, txt, fontsize=28, va="center", color=INK)
        lx += 0.158
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
    rows = (("Pit", pits, PIT, 30, "-"), ("Pad", pads, PAD, 90, "--"), ("Road", roads, ROAD, 90, "-"))
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
            ax.text(0.04, 0.95, lab, transform=ax.transAxes, va="top", fontsize=34, fontweight="bold", color=INK, path_effects=HALO)
            ax.text(0.04, 0.05, f"{2 * half} m", transform=ax.transAxes, fontsize=24, color=INK, path_effects=HALO)
    fig.savefig(OUT / "poster_signs_gallery_9t.png", dpi=DPI)
    plt.close(fig)


def fig_folds():
    pf = block_fold("pit")
    allb = gpd.read_file(D05 / "pit_blocks_9t.gpkg", layer="blocks")
    fig, axs = plt.subplots(1, 5, figsize=(13.47, 2.9), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=0.80, bottom=0, wspace=0.06)
    for k, ax in enumerate(axs):
        allb.plot(ax=ax, color="white", edgecolor=OTHER, lw=0.8)
        pf[pf.fold != k].plot(ax=ax, color=OTHER, edgecolor="white", lw=0.8)
        pf[pf.fold == k].plot(ax=ax, color=HELD, edgecolor="white", lw=0.8)
        ax.set_axis_off()
        ax.set_title(f"Test {k + 1}", fontsize=28, color=INK)
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
            ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15",
                                        fc="#DCE8F8" if hi else "#F2F2F2", ec="none"))
            ax.text(x + w / 2, y + h / 2, s, ha="center",
                    va="center", fontsize=32, color=INK, fontweight="bold" if hi else "normal", linespacing=1.0)
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
    for name, col, lab in (("pit", PIT, "Pits"), ("pad", PAD, "Pads")):
        s = d[d.model == name].sort_values("rank")
        ax.plot(s.recall, s.precision, color=col, lw=5)
        i = int(len(s) * (0.80 if name == "pit" else 0.62))
        ax.text(s.recall.iloc[i], s.precision.iloc[i] + (0.05 if name == "pit" else -0.11), lab, color=INK, fontsize=34,
                fontweight="bold", ha="center", path_effects=HALO)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.set_yticks([0, 0.5, 1]); ax.set_xticks([0, 0.25, 0.5, 0.75, 1])
    ax.set_xlabel("Found (share of hand-drawn features)"); ax.set_ylabel("Correct")
    ax.grid(color="#E6E6E6", lw=1.5); ax.spines[["top", "right"]].set_visible(False)
    fig.savefig(OUT / "poster_pr_curves_heldout_9t.png", dpi=DPI)
    plt.close(fig)


def fig_optical():
    with zipfile.ZipFile(DECK) as z:
        ims = [Image.open(io.BytesIO(z.read(f"ppt/media/image{i}.png"))).convert("RGB") for i in (2, 3)]
    fig, axs = plt.subplots(1, 2, figsize=(13.47, 3.25), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0.03)
    for ax, im, t in zip(axs, ims, ("Air photo", "Lidar, trees removed")):
        ax.imshow(im, aspect="auto"); ax.set_axis_off()
        ax.text(0.03, 0.94, t, transform=ax.transAxes, va="top", fontsize=30, fontweight="bold", color=INK, path_effects=HALO)
    fig.savefig(OUT / "poster_optical_vs_lidar_9t.png", dpi=DPI)
    plt.close(fig)


def main():
    OUT.mkdir(exist_ok=True)
    for f in (fig_channels, fig_gallery, fig_folds, fig_pipeline, fig_pr, fig_optical):
        f(); print(f.__name__)
    print("hero window, hits, misses, false alarms:", fig_hero())


if __name__ == "__main__":
    main()
