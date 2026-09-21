"""Two things that are hard to say and easy to show.

    1  held_out   the split: which pits the model was never allowed to see
    2  outcomes   what it then found, what it flagged with nothing under it,
                  and what it missed
    3  undecided  a zoom on the flagged-with-nothing-under-it cases

WHY THE SPLIT IMAGE MATTERS
---------------------------
Training windows are sampled around features and wobble about 30 m, so a window
centred on a training pit can physically overlap the pit next door. If that
neighbour is a test pit, the model has seen its ground and the test score is
inflated. Assigning whole 375 m blocks instead of individual pits puts a hard
spatial wall between the sets -- and the image shows the wall.

WHAT "UNDECIDED" MEANS
----------------------
A prediction with no annotation under it. It is NOT automatically a false
positive: it may be a real pit nobody has drawn yet. That is the whole reason
the layer exists -- it is a review queue, not an error list.

SOURCES
-------
    data/9t/derived/05/pit_blocks_9t.gpkg           layer "blocks"
    data/9t/derived/05/pit_dataset_manifest.csv     split per pit
    data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg
        undecided 207 / matched 481 / missed_pit 26   (2026-08-05, ann527 era)

Run:
    python docs/presentation/figures_30to45min/_build_split_and_undecided.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyogrio
import rasterio
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from rasterio.windows import from_bounds
from shapely.geometry import box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
#: terrain layers moved to the 1 m stack; D05 still holds the 0.5 m split
#: bookkeeping and model inputs, which have no 1 m twin
D05_1M = ROOT / "data" / "9t" / "derived" / "1m"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min"
UND = (ROOT / "data/9t/results/pit/centroid_matching"
       / "pit_candidates_undecided_thr0p50_9t.gpkg")
BLOCKS = D05 / "pit_blocks_9t.gpkg"
MANIFEST = D05 / "pit_dataset_manifest.csv"
HILL = D05_1M / "hillshade_9t_1m.tif"
RRIM = D05_1M / "rrim_openness_9t_1m.tif"
EPSG = 6346

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

#: Test is BLACK on request -- it is the category that matters most and it now
#: cannot be confused with anything. Validated with the dataviz validator,
#: --pairs all: CVD worst-pair dE 24.7 protan (#eb6834 vs #2a78d6),
#: normal-vision worst 33.6. Black sits outside the validator's lightness band
#: by design; that is what makes it unmistakable.
SPLIT_COLOR = {"train": "#2a78d6", "val": "#eb6834",
               "test": "#111111", "unused": "#c9c8bf"}
C_MATCH = "#1baf7a"
C_UNDEC = "#ffb300"
C_MISS = "#e5194b"



#: Which stage folder each figure belongs to. The talk runs in this order, and
#: the folders are numbered so a directory listing is the running order:
#:   1 data QA · 2 terrain derivatives · 3 annotations · 4 model building
#:   5 probability surfaces.  A name missing here lands at the top level, which
#:   is reserved for figures that belong to no single stage (the locator map).
STAGE = {
    "nisar_radar_10m_9t.png": "1_data_qa",
    "annotation_schema_pad_and_pit_9t.png": "3_annotations",
    "annotation_growth_pits_9t.png": "3_annotations",
    "annotation_growth_pads_9t.png": "3_annotations",
    "split_blocks_12x12_9t.png": "3_annotations",
    "split_held_out_pits_9t.png": "3_annotations",
    "pipeline_diagram_classical_and_unet_branches.png": "4_model_building",
    "classical_vs_unet_pits_9t.png": "4_model_building",
    "pit_outcomes_9t.png": "5_probability_surfaces",
    "pit_review_queue_9t.png": "5_probability_surfaces",
    "threshold_sweep_9t.png":
        "5_probability_surfaces",
}


def stage_path(name):
    """Full path for a figure, in its stage folder."""
    d = OUT / STAGE[name] if name in STAGE else OUT
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def hill(bb, src=None, px=2200):
    src = src or HILL
    with rasterio.open(src) as r:
        w = from_bounds(*bb, transform=r.transform)
        h = int(w.height); wd = int(w.width)
        f = max(1, int(max(h, wd) / px))
        a = r.read(1, window=w, boundless=True, fill_value=np.nan,
                   out_shape=(max(1, h // f), max(1, wd // f))).astype("float32")
    return a


def decorate(ax, bb, title, subtitle, handles, note, bar_m=1000):
    ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3])
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    l, b, r_, t = bb
    x0, y0 = l + (r_ - l) * 0.05, b + (t - b) * 0.05
    ax.plot([x0, x0 + bar_m], [y0, y0], color="white", linewidth=6,
            solid_capstyle="butt", zorder=12)
    ax.plot([x0, x0 + bar_m], [y0, y0], color=INK, linewidth=2.6,
            solid_capstyle="butt", zorder=13)
    lab = f"{bar_m/1000:g} km" if bar_m >= 1000 else f"{bar_m:g} m"
    ax.text(x0 + bar_m / 2, y0 + (t - b) * 0.021, lab, ha="center", fontsize=10,
            color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))
    nx, ny = r_ - (r_ - l) * 0.055, t - (t - b) * 0.15
    ax.annotate("", xy=(nx, ny + (t - b) * 0.085), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.6,
                                mutation_scale=18), zorder=13)
    ax.text(nx, ny + (t - b) * 0.095, "N", ha="center", va="bottom", fontsize=13,
            fontweight="bold", color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc", ec="none"))
    if handles:
        leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                        facecolor="#ffffff", edgecolor=RULE, fontsize=11,
                        framealpha=1.0)
        leg.set_zorder(20)
    ax.set_title(title, fontsize=17, fontweight="bold", loc="left", pad=10)
    fig = ax.get_figure()
    fig.text(0.021, 0.016,
             "Red Relief Image Map \u00b7 Chiba et al. 2008",
             fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.02, right=0.98, top=0.925, bottom=0.048)


def save(fig, name):
    p = stage_path(name)
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:7.0f} KB  {name}")


def main() -> int:
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    if blocks.crs is None or blocks.crs.to_epsg() != EPSG:
        blocks = blocks.set_crs(EPSG, allow_override=True)
    bb = tuple(blocks.total_bounds)
    ext = [bb[0], bb[2], bb[1], bb[3]]
    hs = hill(bb)

    man = pd.read_csv(MANIFEST)
    man = man[man.block_id.notna()]
    pits = gpd.GeoDataFrame(
        man.copy(),
        geometry=gpd.points_from_xy(man.centroid_x, man.centroid_y), crs=EPSG)

    # --- 1. the split --------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9.6, 9.8))
    ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
              vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
              zorder=1, alpha=0.55)
    for split in ["unused", "train", "val", "test"]:
        sub = blocks[blocks.split == split]
        if len(sub):
            sub.plot(ax=ax, facecolor=SPLIT_COLOR[split], alpha=0.30,
                     edgecolor=SPLIT_COLOR[split], linewidth=0.8, zorder=3)
    handles = []
    for split in ["train", "val", "test"]:
        sub = pits[pits.split == split]
        if not len(sub):
            continue
        ax.scatter(sub.geometry.x, sub.geometry.y, s=14,
                   c=SPLIT_COLOR[split], edgecolors="#000000", linewidths=0.35,
                   zorder=7)
        nb = int((blocks.split == split).sum())
        handles.append(Line2D([], [], marker="o", linestyle="none",
                              markerfacecolor=SPLIT_COLOR[split],
                              markeredgecolor="#000000", markersize=8,
                              label=f"{split}  {len(sub)} pits / {nb} blocks"))
    handles.append(Patch(facecolor=SPLIT_COLOR["unused"], alpha=0.5,
                         edgecolor="none",
                         label=f"no pits  ({int((blocks.split=='unused').sum())} blocks)"))
    held = int((pits.split != "train").sum())
    decorate(ax, bb, "Which pits the model was never allowed to see",
             f"{len(pits)} pits in 144 blocks of 375 m  \u00b7  {held} held out "
             f"of training  \u00b7  whole blocks move together, never individual pits",
             handles,
             "Training windows wobble 30 m, so a window on a train pit can cover "
             "the pit next door. Blocks put a wall between the sets. Balanced on "
             "pit count, not block count \u2014 pits cluster.")
    save(fig, "split_held_out_pits_9t.png")

    # --- 2. outcomes ---------------------------------------------------------
    layers = {n for n, _ in pyogrio.list_layers(str(UND))}
    matched = gpd.read_file(UND, layer="matched") if "matched" in layers else None
    undec = gpd.read_file(UND, layer="undecided") if "undecided" in layers else None
    missed = gpd.read_file(UND, layer="missed_pit") if "missed_pit" in layers else None
    for g in (matched, undec, missed):
        if g is not None and (g.crs is None or g.crs.to_epsg() != EPSG):
            g.set_crs(EPSG, allow_override=True, inplace=True)

    fig, ax = plt.subplots(figsize=(9.6, 9.8))
    ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
              vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
              zorder=1, alpha=0.75)
    handles = []
    for g, col, lab, z, sz in ((matched, C_MATCH, "matched a known pit", 5, 12),
                               (undec, C_UNDEC, "flagged, nothing drawn there", 7, 22),
                               (missed, C_MISS, "known pit, not found", 9, 40)):
        if g is None or not len(g):
            continue
        c = g.geometry.centroid
        ax.scatter(c.x, c.y, s=sz, c=col, edgecolors="#000000",
                   linewidths=0.4, zorder=z, marker="o")
        handles.append(Line2D([], [], marker="o", linestyle="none",
                              markerfacecolor=col, markeredgecolor="#000000",
                              markersize=8, label=f"{lab}  ({len(g)})"))
    decorate(ax, bb, "What the model found, flagged and missed",
             f"cross-validated over all five folds at threshold 0.50  \u00b7  "
             f"precision 0.699, recall 0.949",
             handles,
             "pit_candidates_undecided_thr0p50_9t.gpkg, 2026-08-05 (ann527-era "
             "model). 'Flagged, nothing drawn there' is a review queue, not an "
             "error list \u2014 some are real pits nobody had drawn yet.")
    save(fig, "pit_outcomes_9t.png")

    # --- 3. zoom on the undecided -------------------------------------------
    if undec is not None and len(undec):
        c = undec.geometry.centroid
        side = 400.0
        best, best_n = None, -1
        for x0 in np.arange(bb[0], bb[2] - side, 100.0):
            for y0 in np.arange(bb[1], bb[3] - side, 100.0):
                n = int(((c.x >= x0) & (c.x < x0 + side) &
                         (c.y >= y0) & (c.y < y0 + side)).sum())
                if n > best_n:
                    best, best_n = (x0, y0), n
        zbb = (best[0], best[1], best[0] + side, best[1] + side)
        zext = [zbb[0], zbb[2], zbb[1], zbb[3]]
        src = RRIM if RRIM.exists() else HILL
        with rasterio.open(src) as r:
            w = from_bounds(*zbb, transform=r.transform)
            a = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
        fig, ax = plt.subplots(figsize=(8.4, 9.0))
        if a.shape[0] >= 3:
            a3 = np.stack([(b_ - np.nanpercentile(b_, 2)) /
                           max(np.nanpercentile(b_, 98) - np.nanpercentile(b_, 2), 1e-9)
                           for b_ in a[:3]])
            ax.imshow(np.clip(np.moveaxis(a3, 0, -1), 0, 1), extent=zext,
                      origin="upper", zorder=1)
        else:
            ax.imshow(a[0], extent=zext, origin="upper", cmap="gray", zorder=1)
        zb = box(*zbb)
        ann = gpd.read_file(ROOT / "qgis/annotations/annotations_proj.gpkg",
                            layer="pit_inside")
        if ann.crs is None or ann.crs.to_epsg() != EPSG:
            ann = ann.set_crs(EPSG, allow_override=True)
        ann = ann[ann.intersects(zb)]
        if len(ann):
            ann.boundary.plot(ax=ax, color="#ccff00", linewidth=2.2, zorder=6)
        sub = undec[undec.intersects(zb)]
        if len(sub):
            sub.plot(ax=ax, facecolor="none", edgecolor=C_UNDEC, linewidth=2.4,
                     zorder=8)
        decorate(ax, zbb, "The review queue, up close",
                 f"{len(sub)} flagged with nothing drawn there  \u00b7  "
                 f"{len(ann)} annotated floors in the same {side:.0f} m window",
                 [Line2D([], [], color=C_UNDEC, linewidth=2.6,
                         label=f"flagged, undecided  ({len(sub)})"),
                  Line2D([], [], color="#ccff00", linewidth=2.6,
                         label=f"hand-drawn floor  ({len(ann)})")],
                 "RRIM base. Each orange outline is a decision a human still has "
                 "to make: real pit, or not?", bar_m=50)
        save(fig, "pit_review_queue_9t.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
