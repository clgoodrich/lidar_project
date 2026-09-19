"""Generate the new presentation figures named in the 30-45 min worklist.

Every figure is built from data on disk. Nothing is synthesized or hand-entered
except the pipeline diagram, which is a schematic by definition.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import ListedColormap
from rasterio.windows import from_bounds

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OUT = ROOT / "docs" / "presentation" / "figures_30to45min"
OUT.mkdir(parents=True, exist_ok=True)

# --- palette (dataviz reference instance, light mode; validated all-pairs) ----
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
S1 = "#2a78d6"   # blue
S2 = "#eb6834"   # orange
S3 = "#1baf7a"   # aqua
NEUTRAL = "#c9c8bf"
GRID = "#e5e4dd"

SPLIT_COLOR = {"train": S1, "val": S2, "test": S3, "unused": NEUTRAL}
PAD_COLOR = {"train": S1, "val": S2, "test": S3,
             "unassigned": "#a8a69b", "outside": NEUTRAL}

from matplotlib.colors import LinearSegmentedColormap
# Sequential ramps are one hue, light to dark (never a rainbow).
CMAP_ORANGE = LinearSegmentedColormap.from_list("wsO", ["#fde3d1", S2, "#8c2f0c"])
CMAP_BLUE = LinearSegmentedColormap.from_list("wsB", ["#d6e6f9", S1, "#10365f"])

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
    "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": GRID,
    "xtick.color": INK2, "ytick.color": INK2, "axes.titlecolor": INK,
    "axes.grid": False, "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 10,
})

written: list[tuple[str, str]] = []


def save(fig, name, note):
    p = OUT / name
    fig.savefig(p, dpi=200, bbox_inches="tight")
    plt.close(fig)
    written.append((name, note))
    print(f"  wrote {p}  ({p.stat().st_size/1e3:.0f} KB)")


def title(ax, t, sub=None):
    """Title above subtitle, both in axes fraction, so they never collide."""
    if sub is None:
        ax.set_title(t, fontsize=12, fontweight="bold", loc="left", pad=8)
        return
    ax.text(0, 1.085, t, transform=ax.transAxes, fontsize=12, fontweight="bold",
            color=INK, va="bottom")
    ax.text(0, 1.022, sub, transform=ax.transAxes, fontsize=9, color=INK2,
            va="bottom")


# ============================================================ F1 locator map
AREAS = [
    ("9t",          6346, "data/9t/derived/05/_dem_9t_1m_link.tif",              "venango"),
    ("613590",      6346, "data/613590/derived/05/dem_613590_05.tif",            "venango"),
    ("616593",      6346, "data/616593/derived/1m/dem_616593_1m.tif",            "venango"),
    ("607594",      6346, "data/607594/derived/1m/dem_607594_1m.tif",            "venango"),
    ("610594",      6346, "data/610594/derived/1m/dem_610594_1m.tif",            "venango"),
    ("610605",      6346, "data/610605/derived/1m/dem_610605_1m.tif",            "venango"),
    ("mckean e1423n2238", 6346,
     "data/mckean/e1423n2238/derived/05/dem_mck_e1423n2238_05.tif",              "mckean"),
]
ROLE_COLOR = {"9t": S1, "613590": S2}


def _read_areas():
    rows = []
    for name, epsg, rel, group in AREAS:
        f = ROOT / rel
        if not f.exists():
            continue
        with rasterio.open(f) as r:
            rows.append(dict(name=name, epsg=epsg, group=group, bounds=tuple(r.bounds),
                             res=r.res[0], w=r.width, h=r.height))
    return rows


def _draw_boxes(ax, rows, unit_km=True):
    """Boxes plus labels stacked above the panel so they never overlap."""
    k = 1000.0 if unit_km else 1.0
    order = sorted(rows, key=lambda d: (-d["bounds"][3], d["bounds"][0]))
    for i, d in enumerate(order):
        l, b, r_, t_ = [v / k for v in d["bounds"]]
        col = ROLE_COLOR.get(d["name"], NEUTRAL)
        ax.add_patch(mpatches.Rectangle((l, b), r_ - l, t_ - b, facecolor=col,
                                        alpha=0.6, edgecolor=col, linewidth=1.5,
                                        zorder=3))
        ax.annotate(d["name"], xy=((l + r_) / 2, t_),
                    xytext=(0, 9 + 13 * (i % 2)), textcoords="offset points",
                    ha="center", va="bottom", fontsize=8.5, color=INK, zorder=5,
                    arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8,
                                    shrinkA=0, shrinkB=1))
    arr = np.array([d["bounds"] for d in rows]) / k
    mx = max((arr[:, 2] - arr[:, 0]).max(), (arr[:, 3] - arr[:, 1]).max())
    # Extra room on the right so a long label at the last box is not clipped.
    padx = max(0.22 * mx, 1.2)
    ax.set_xlim(arr[:, 0].min() - padx, arr[:, 2].max() + padx * 2.6)
    ax.set_ylim(arr[:, 1].min() - padx, arr[:, 3].max() + padx * 2.4)
    ax.set_aspect("equal")


def fig_locator():
    from pyproj import Transformer

    rows = _read_areas()
    ven = [d for d in rows if d["group"] == "venango"]
    mck = [d for d in rows if d["group"] == "mckean"]

    fig = plt.figure(figsize=(11.2, 7.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 0.85], hspace=0.38, wspace=0.3)

    ax = fig.add_subplot(gs[0, 0])
    _draw_boxes(ax, ven)
    ax.set_xlabel("UTM 17N easting (km)"); ax.set_ylabel("UTM 17N northing (km)")
    title(ax, "a  Venango County cluster", "EPSG:6346 \u00b7 9t and 613590 carry the models")

    ax = fig.add_subplot(gs[0, 1])
    _draw_boxes(ax, mck)
    ax.set_xlabel("UTM 17N easting (km)"); ax.set_ylabel("UTM 17N northing (km)")
    title(ax, "b  McKean County", "EPSG:6346 \u00b7 ~80 km northeast of the cluster")

    # (c) the table. A lon/lat scatter with no basemap says nothing; the extents do.
    ax = fig.add_subplot(gs[1, :])
    ax.axis("off")
    hdr = ["area", "group", "CRS", "res (m)", "grid (px)", "extent (km)",
           "centre lon, lat"]
    cw = [0.19, 0.09, 0.09, 0.08, 0.13, 0.15, 0.17]
    xs = np.cumsum([0] + cw[:-1])
    for x, h in zip(xs, hdr):
        ax.text(x, 0.95, h, fontsize=9, fontweight="bold", color=INK2, va="top")
    ax.plot([0, sum(cw)], [0.9, 0.9], color=GRID, linewidth=1.2)
    for i, d in enumerate(rows):
        y = 0.83 - i * 0.092
        l, b, r_, t_ = d["bounds"]
        tr = Transformer.from_crs(d["epsg"], 4326, always_xy=True)
        lon, lat = tr.transform((l + r_) / 2, (b + t_) / 2)
        col = ROLE_COLOR.get(d["name"], INK)
        cells = [d["name"], d["group"], f"EPSG:{d['epsg']}", f"{d['res']:.1f}",
                 f"{d['w']} x {d['h']}",
                 f"{(r_-l)/1000:.1f} x {(t_-b)/1000:.1f}",
                 f"{lon:.3f}, {lat:.3f}"]
        for x, c in zip(xs, cells):
            ax.text(x, y, c, fontsize=8.8, color=col if x == 0 else INK2, va="top",
                    fontweight="bold" if x == 0 else "normal")
    ax.set_xlim(-0.01, sum(cw)); ax.set_ylim(0, 1)
    title(ax, "c  Every area, as read from the DEM headers")

    save(fig, "locator_study_areas_pa.png",
         f"{len(ven)} Venango tiles and {len(mck)} McKean, plus an extent table")


# ====================================================== F2 pipeline diagram
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(13.2, 6.8))
    ax.set_xlim(-7, 101); ax.set_ylim(2, 64); ax.axis("off")

    W, H = 18.0, 9.5
    COLS = [0, 20.6, 41.2, 61.8, 82.4]          # 2.6 units of clear gap
    Y_BASE, Y_A, Y_B = 50.0, 28.0, 8.0
    BUS = 45.0
    SPINE = -4.0

    def box(col, y, text, fc, ec, weight="normal"):
        x = COLS[col]
        ax.add_patch(mpatches.FancyBboxPatch(
            (x, y), W, H, boxstyle="round,pad=0,rounding_size=1.1",
            facecolor=fc, edgecolor=ec, linewidth=1.3))
        ax.text(x + W / 2, y + H / 2, text, ha="center", va="center",
                fontsize=9, color=INK, fontweight=weight, linespacing=1.45)

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color=MUTED, linewidth=1.4,
                                    shrinkA=0, shrinkB=0))

    def chain(cols, y):
        for c in cols[:-1]:
            arrow(COLS[c] + W, y + H / 2, COLS[c + 1], y + H / 2)

    # --- shared base -------------------------------------------------------
    ax.text(0, Y_BASE + H + 2.2, "Shared base", fontsize=10.5,
            fontweight="bold", color=INK2)
    for c, t in enumerate(["USGS 3DEP\nQL2 point cloud",
                           "ground-classified\npoints (PDAL)",
                           "DEM\n0.5 m / 1 m",
                           "terrain derivatives\nslope, roughness, TPI,\nLRM, openness"]):
        box(c, Y_BASE, t, "#f2f1ea", MUTED)
    chain([0, 1, 2, 3], Y_BASE)
    box(4, Y_BASE, "hand annotation\nin QGIS on hillshade", "#f2f1ea", MUTED)

    # --- bus: derivatives and annotation both feed both branches -----------
    dx = COLS[3] + W / 2
    ax_x = COLS[4] + W / 2
    ax.plot([dx, dx], [Y_BASE, BUS], color=MUTED, linewidth=1.4)
    ax.plot([ax_x, ax_x], [Y_BASE, BUS], color=MUTED, linewidth=1.4)
    ax.plot([SPINE, ax_x], [BUS, BUS], color=MUTED, linewidth=1.4)
    ax.plot([SPINE, SPINE], [Y_B + H / 2, BUS], color=MUTED, linewidth=1.4)
    arrow(SPINE, Y_A + H / 2, COLS[0], Y_A + H / 2)
    arrow(SPINE, Y_B + H / 2, COLS[0], Y_B + H / 2)
    ax.text(SPINE + 1.2, BUS + 1.2, "derivatives and annotation feed both branches",
            fontsize=8.5, color=MUTED)

    # --- branch A ----------------------------------------------------------
    ax.text(0, Y_A + H + 2.2, "Branch A  ·  classical", fontsize=10.5,
            fontweight="bold", color=S2)
    for c, t in enumerate(["mean pit template\n17x17 m, 5 channels",
                           "NCC scan\n~628k candidates",
                           "48 features\nper candidate",
                           "XGBoost + LightGBM +\nHistGB, spatial CV,\nisotonic calibration"]):
        box(c, Y_A, t, "#fdece4", S2)
    box(4, Y_A, "ROC-AUC 0.905\nPR-AUC 0.212", "#fdece4", S2, weight="bold")
    chain([0, 1, 2, 3, 4], Y_A)

    # --- branch B ----------------------------------------------------------
    ax.text(0, Y_B + H + 2.2, "Branch B  ·  deep learning", fontsize=10.5,
            fontweight="bold", color=S1)
    for c, t in enumerate(["7-channel stack\nnormalized on train",
                           "spatial-block split\n12x12 grid, greedy fill",
                           "U-Net\npit / pad / road",
                           "5-fold CV +\nheld-out threshold\nsweep, 9 thresholds"]):
        box(c, Y_B, t, "#e3eefb", S1)
    box(4, Y_B, "probability rasters\n→ candidate polygons", "#e3eefb", S1,
        weight="bold")
    chain([0, 1, 2, 3, 4], Y_B)

    ax.text(101, 3.4, "both branches score against the same hand annotation",
            ha="right", fontsize=8.5, color=MUTED)
    ax.set_title("WellSight detection pipeline, two branches off one base",
                 fontsize=13.5, fontweight="bold", loc="left", pad=14)
    save(fig, "pipeline_diagram_classical_and_unet_branches.png",
         "schematic; replaces the four-step pipeline slide")


# ================================================== F3 annotation growth
def fig_annotation_growth():
    srcs = [("ann426\n2026-06-10",
             "qgis/annotations/_history/_backup_pit_ann426_2026-06-10/pit_dataset_manifest.csv"),
            ("ann527\n2026-09-04",
             "qgis/annotations/_history/_backup_pit_ann527_2026-09-04/pit_dataset_manifest.csv"),
            ("ann712\ncurrent",
             "data/9t/derived/05/pit_dataset_manifest.csv")]
    rows = []
    for lbl, p in srcs:
        d = pd.read_csv(ROOT / p)
        vc = d["split"].value_counts().to_dict()
        rows.append({"label": lbl, "total": len(d),
                     **{k: int(vc.get(k, 0)) for k in ["train", "val", "test", "unused"]}})
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(8.6, 5.4))
    x = np.arange(len(df))
    bottom = np.zeros(len(df))
    for split in ["train", "val", "test", "unused"]:
        v = df[split].to_numpy()
        ax.bar(x, v, 0.56, bottom=bottom, color=SPLIT_COLOR[split],
               edgecolor=SURFACE, linewidth=2,
               label="outside 9t (no block)" if split == "unused" else split)
        for xi, (vi, bi) in enumerate(zip(v, bottom)):
            if vi > 22:
                ax.text(xi, bi + vi / 2, f"{vi}", ha="center", va="center",
                        fontsize=9.5, color="white" if split != "unused" else INK2,
                        fontweight="bold")
        bottom += v
    for xi, row in df.iterrows():
        inside = row["train"] + row["val"] + row["test"]
        ax.text(xi, row["total"] + 12, f"{row['total']} annotated",
                ha="center", fontsize=10, fontweight="bold", color=INK)
        ax.text(xi, row["total"] + 42, f"{inside} inside 9t", ha="center",
                fontsize=9, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(df["label"], fontsize=10)
    ax.set_ylabel("pit floors in the 9t manifest")
    ax.set_ylim(0, df["total"].max() * 1.22)
    ax.legend(frameon=False, fontsize=9, ncol=4, loc="upper left",
              bbox_to_anchor=(0, -0.09))
    title(ax, "The 9t annotation is a moving target",
          "each expansion reassigns the spatial-block split, so no earlier "
          "checkpoint stays held-out")
    fig.text(0.01, -0.13,
             "The manifest is project-wide. Rows with no block_id are pit floors "
             "outside the 9t tile, so they can never be trained or scored on here.\n"
             "Verified: all 209 of the current 'unused' rows fall outside "
             "619500-624000 E, 4593000-4597500 N. ann426 had none.",
             fontsize=8.5, color=MUTED)
    save(fig, "annotation_growth_pit_splits_426_527_712.png",
         f"split composition across ann426/527/712; "
         f"{int(df.iloc[-1][['train','val','test']].sum())} of "
         f"{int(df.iloc[-1]['total'])} current pits are inside 9t")


# ================================================ F4 spatial block split grid
def fig_block_grid():
    b = gpd.read_file(ROOT / "data/9t/derived/05/pit_blocks_9t.gpkg", layer="blocks")
    fig, axes = plt.subplots(1, 2, figsize=(13, 6.1),
                             gridspec_kw={"width_ratios": [1.12, 1]})

    ax = axes[0]
    for _, r in b.iterrows():
        x0, y0, x1, y1 = r.geometry.bounds
        ax.add_patch(mpatches.Rectangle((x0 / 1000, y0 / 1000), (x1 - x0) / 1000,
                                        (y1 - y0) / 1000,
                                        facecolor=SPLIT_COLOR[r["split"]], alpha=0.85,
                                        edgecolor=SURFACE, linewidth=1.6))
        if r["n_pits"] > 0:
            ax.text((x0 + x1) / 2000, (y0 + y1) / 2000, int(r["n_pits"]),
                    ha="center", va="center", fontsize=7.5,
                    color="white" if r["split"] != "unused" else INK2,
                    fontweight="bold")
    bl, bb, br, bt = b.total_bounds
    ax.set_xlim(bl / 1000, br / 1000); ax.set_ylim(bb / 1000, bt / 1000)
    ax.set_aspect("equal")
    ax.set_xlabel("UTM 17N easting (km)"); ax.set_ylabel("UTM 17N northing (km)")
    h = [mpatches.Patch(facecolor=SPLIT_COLOR[s], label=s) for s in
         ["train", "val", "test", "unused"]]
    ax.legend(handles=h, frameon=False, fontsize=9, ncol=4, loc="upper left",
              bbox_to_anchor=(0, -0.1))
    title(ax, "a  The 12x12 spatial-block split on 9t",
          "numbers are pit floors per block; blank blocks hold none")

    ax = axes[1]
    agg = (b.groupby("split").agg(blocks=("block_id", "size"),
                                  pits=("n_pits", "sum")).reindex(
        ["train", "val", "test", "unused"]))
    y = np.arange(len(agg))[::-1]
    tot_b, tot_p = agg["blocks"].sum(), agg["pits"].sum()
    ax.barh(y + 0.19, agg["blocks"] / tot_b * 100, 0.34, color=NEUTRAL,
            edgecolor=SURFACE, linewidth=1.5, label="share of blocks")
    ax.barh(y - 0.19, agg["pits"] / tot_p * 100, 0.34,
            color=[SPLIT_COLOR[s] for s in agg.index], edgecolor=SURFACE,
            linewidth=1.5, label="share of pit floors")
    for yi, (s, row) in zip(y, agg.iterrows()):
        ax.text(row["blocks"] / tot_b * 100 + 1.2, yi + 0.19,
                f"{row['blocks']} blocks", va="center", fontsize=9, color=INK2)
        ax.text(row["pits"] / tot_p * 100 + 1.2, yi - 0.19,
                f"{int(row['pits'])} pits", va="center", fontsize=9,
                fontweight="bold", color=INK)
    ax.set_yticks(y); ax.set_yticklabels(agg.index, fontsize=10)
    ax.set_xlabel("share of the tile (%)")
    ax.set_xlim(0, 72)
    ax.legend(frameon=False, fontsize=9, loc="lower right")
    title(ax, "b  Why the fill balances on count",
          "blocks and pits do not track each other; pits cluster")
    fig.subplots_adjust(wspace=0.26)
    save(fig, "spatial_block_split_grid_12x12_9t_ann712.png",
         f"144 blocks by split, {int(tot_p)} pit floors inside the tile; "
         f"count vs block share")


# ============================================ F5 classical vs U-Net, one scene
def fig_classical_vs_unet():
    cand = gpd.read_file(ROOT / "data/_results/candidates/candidates_pits.gpkg")
    if cand.crs is None or cand.crs.to_epsg() != 6346:
        cand = cand.set_crs(6346, allow_override=True)
    # A 1.6 km window renders a 13 m pit at a handful of pixels. Zoom to the
    # densest 400 m box inside the candidate extent instead, chosen by a coarse
    # search over annotated floor centroids so the box is not hand-picked.
    l, b, r_, t_ = cand.total_bounds
    _ann = gpd.read_file(ROOT / "qgis/annotations/annotations_proj.gpkg",
                         layer="pit_inside").to_crs(6346)
    _c = _ann.geometry.centroid
    _in = _c[(_c.x >= l) & (_c.x <= r_) & (_c.y >= b) & (_c.y <= t_)]
    SIDE = 400.0
    best, best_n = None, -1
    for x0 in np.arange(l, r_ - SIDE, 50.0):
        for y0 in np.arange(b, t_ - SIDE, 50.0):
            n = int(((_in.x >= x0) & (_in.x < x0 + SIDE) &
                     (_in.y >= y0) & (_in.y < y0 + SIDE)).sum())
            if n > best_n:
                best, best_n = (x0, y0), n
    win_b = (best[0], best[1], best[0] + SIDE, best[1] + SIDE)

    hs_p = ROOT / "data/9t/derived/05/hillshade_9t_05.tif"
    pr_p = ROOT / "data/9t/models/pit/unet_v2/pit_prob_floor.tif"
    with rasterio.open(hs_p) as h:
        w = from_bounds(*win_b, transform=h.transform)
        hs = h.read(1, window=w)
        ext = rasterio.windows.bounds(w, h.transform)
    with rasterio.open(pr_p) as p:
        wp = from_bounds(*win_b, transform=p.transform)
        prob = p.read(1, window=wp)

    ann = _ann[_ann.intersects(gpd.GeoSeries.from_wkt(
        [f"POLYGON(({win_b[0]} {win_b[1]},{win_b[2]} {win_b[1]},"
         f"{win_b[2]} {win_b[3]},{win_b[0]} {win_b[3]},{win_b[0]} {win_b[1]}))"],
        crs=6346).iloc[0])]

    e = [ext[0] / 1000, ext[2] / 1000, ext[1] / 1000, ext[3] / 1000]
    fig, axes = plt.subplots(1, 2, figsize=(13.4, 6.6), sharex=True, sharey=True)

    # The axes are in kilometres (extent e is metres/1000), so the annotation
    # geometry has to be scaled to match or it lands far off the panel.
    ann_km = ann.geometry.scale(xfact=1e-3, yfact=1e-3, origin=(0, 0))

    for ax in axes:
        ax.imshow(hs, cmap="gray", extent=e, origin="upper", vmin=0, vmax=255)
        ax.set_aspect("equal")
        ax.set_xlabel("UTM 17N easting (km)")

    ax = axes[0]
    cw = cand.cx[win_b[0]:win_b[2], win_b[1]:win_b[3]]
    cs = cw["confidence_score"].to_numpy()
    sc = ax.scatter(cw.geometry.x / 1000, cw.geometry.y / 1000,
                    s=26 + 150 * (cs - cs.min()) / max(np.ptp(cs), 1e-9),
                    c=cs, cmap=CMAP_ORANGE, edgecolor="none", alpha=0.9, zorder=3)
    cb = fig.colorbar(sc, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("ensemble confidence", fontsize=9, color=INK2)
    cb.outline.set_visible(False)
    ax.set_ylabel("UTM 17N northing (km)")
    title(ax, "a  Branch A, classical ensemble",
          f"{len(cw)} scored candidates in this window")

    ax = axes[1]
    # Masked at the 0.20 operating threshold. Below that the raster is mostly
    # faint response along drainage and roads, which buries the pits.
    m = np.ma.masked_less(prob, 0.20)
    im = ax.imshow(m, cmap=CMAP_BLUE, extent=e, origin="upper", vmin=0.2, vmax=1,
                   alpha=0.95, zorder=3)
    cb = fig.colorbar(im, ax=ax, fraction=0.043, pad=0.02)
    cb.set_label("U-Net pit-floor probability", fontsize=9, color=INK2)
    cb.outline.set_visible(False)
    title(ax, "b  Branch B, pit U-Net",
          "per-pixel floor probability at or above 0.20")

    import matplotlib.patheffects as pe
    from matplotlib.lines import Line2D
    for a in axes:
        ann_km.boundary.plot(ax=a, color=S3, linewidth=2.2, zorder=8,
                             path_effects=[pe.Stroke(linewidth=3.8,
                                                     foreground="#0b0b0b"),
                                           pe.Normal()])
    for a in axes:
        a.legend(handles=[Line2D([], [], color=S3, linewidth=2.0,
                                 label=f"hand-annotated pit floor (n={len(ann)})")],
                 frameon=True, facecolor="#ffffffcc", edgecolor="none",
                 fontsize=8.5, loc="lower left")
    fig.suptitle("Same scene, both branches", fontsize=13, fontweight="bold",
                 x=0.09, ha="left", y=1.0)
    save(fig, "classical_vs_unet_pit_detection_same_scene_9t.png",
         f"{len(cw)} classical candidates vs U-Net floor probability in a "
         f"400 m window, {len(ann)} annotated floors")


# ==================================================== F7 NISAR GCOV clip
def fig_nisar():
    import h5py
    g5 = (ROOT / "data/_source/reference/nisar/9t/NISAR_L2_GCOV_BETA_V1/"
          "NISAR_L2_PR_GCOV_010_162_A_023_4005_DHDH_A_20260120T101554_"
          "20260120T101629_X05010_N_F_J_001.h5")
    bx, by = (619500, 624000), (4593000, 4597500)
    with h5py.File(g5, "r") as f:
        g = f["/science/LSAR/GCOV/grids/frequencyA"]
        x = g["xCoordinates"][:]
        y = g["yCoordinates"][:]
        ix = np.where((x >= bx[0]) & (x <= bx[1]))[0]
        iy = np.where((y >= by[0]) & (y <= by[1]))[0]
        sx, sy = slice(ix[0], ix[-1] + 1), slice(iy[0], iy[-1] + 1)
        hh = g["HHHH"][sy, sx].astype("float32")
        hv = g["HVHV"][sy, sx].astype("float32")
    with np.errstate(divide="ignore", invalid="ignore"):
        hh_db = 10 * np.log10(np.where(hh > 0, hh, np.nan))
        hv_db = 10 * np.log10(np.where(hv > 0, hv, np.nan))
    ratio = hh_db - hv_db
    ext = [bx[0] / 1000, bx[1] / 1000, by[0] / 1000, by[1] / 1000]

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 5.3), sharex=True, sharey=True)
    for ax, arr, lab, cm, vr in [
            (axes[0], hh_db, "HH gamma-0 (dB)", "gray", (-16, -2)),
            (axes[1], hv_db, "HV gamma-0 (dB)", "gray", (-24, -10)),
            (axes[2], ratio, "HH - HV (dB)", CMAP_ORANGE, (4, 12))]:
        im = ax.imshow(arr, cmap=cm, extent=ext, origin="upper",
                       vmin=vr[0], vmax=vr[1])
        cb = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.02)
        cb.set_label(lab, fontsize=9, color=INK2)
        cb.outline.set_visible(False)
        ax.set_aspect("equal")
        ax.set_xlabel("UTM 17N easting (km)")
        ax.text(0.02, 0.975, f"median {np.nanmedian(arr):.1f} dB",
                transform=ax.transAxes, fontsize=9, color="white", va="top",
                bbox=dict(boxstyle="round,pad=0.3", fc="#00000088", ec="none"))
    axes[0].set_ylabel("UTM 17N northing (km)")
    for ax, t in zip(axes, ["a  co-pol HH", "b  cross-pol HV",
                            "c  HH - HV, forest signature"]):
        title(ax, t)
    fig.suptitle("NISAR L-band GCOV over 9t, 2026-01-20 (beta product)",
                 fontsize=13, fontweight="bold", x=0.09, ha="left", y=1.02)
    fig.text(0.5, -0.02, f"{hh.shape[1]} x {hh.shape[0]} px at 10 m, clipped from a "
             f"36,216 x 35,784 px swath.  9t is 0.016% of the granule area.",
             ha="center", fontsize=8.5, color=MUTED)
    save(fig, "nisar_gcov_hh_hv_clip_9t_10m_20260120.png",
         f"{hh.shape[1]}x{hh.shape[0]} px HH/HV/ratio clip, median HH "
         f"{np.nanmedian(hh_db):.1f} dB, HV {np.nanmedian(hv_db):.1f} dB, "
         f"ratio {np.nanmedian(ratio):.1f} dB")


# ==================================================== F7 one pit, fully digitized
ANN = "qgis/annotations/annotations_proj.gpkg"
T9 = (619500.0, 4593000.0, 624000.0, 4597500.0)   # the 9t tile, metres


def _lyr(name):
    g = gpd.read_file(ROOT / ANN, layer=name)
    if g.crs is None or g.crs.to_epsg() != 6346:
        g = g.set_crs(6346, allow_override=True)
    return g


def _hs(win):
    with rasterio.open(ROOT / "data/9t/derived/05/hillshade_9t_05.tif") as h:
        w = from_bounds(*win, transform=h.transform)
        return h.read(1, window=w), rasterio.windows.bounds(w, h.transform)


def fig_pit_anatomy():
    """The schema on one pad, then on one pit. Nothing here is hand-picked:
    the pad is the one inside 9t carrying the most annotated floors, and the
    pit is the floor in it whose rim polygon has the largest area."""
    pad = _lyr("plat")
    pit = _lyr("pit_inside")
    wall = _lyr("pit_wall")
    full = _lyr("pit_outside")
    roads = _lyr("roads")

    box = gpd.GeoSeries.from_wkt(
        [f"POLYGON(({T9[0]} {T9[1]},{T9[2]} {T9[1]},{T9[2]} {T9[3]},"
         f"{T9[0]} {T9[3]},{T9[0]} {T9[1]}))"], crs=6346).iloc[0]
    pad_in = pad[pad.within(box)].copy()
    pad_in["n"] = pad_in.pad_id.map(pit.pad_id.value_counts()).fillna(0)
    # Pads hold one or two floors, never more, so ties on n are broken by area:
    # the largest such pad renders legibly at 0.5 m.
    pad_in["ha"] = pad_in.geometry.area / 10000
    sel = pad_in.sort_values(["n", "ha"], ascending=False).iloc[0]
    pid = sel.pad_id

    pits = pit[pit.pad_id == pid]
    fl = full[full.pad_id == pid].copy()
    fl["a"] = fl.geometry.area
    tgt = fl.sort_values("a", ascending=False).iloc[0]

    # panel a window: the pad plus a 60 m margin
    l, b, r_, t_ = sel.geometry.bounds
    m = 60.0
    wa = (l - m, b - m, r_ + m, t_ + m)
    # panel b window: the target depression plus 12 m
    l2, b2, r2, t2 = tgt.geometry.bounds
    m2 = 12.0
    side = max(r2 - l2, t2 - b2) / 2 + m2
    cx, cy = (l2 + r2) / 2, (b2 + t2) / 2
    wb = (cx - side, cy - side, cx + side, cy + side)

    fig, axes = plt.subplots(1, 2, figsize=(11.0, 5.8))
    fig.subplots_adjust(wspace=0.32)
    for ax, win, lab in zip(axes, [wa, wb], ["a", "b"]):
        hs, ext = _hs(win)
        ax.imshow(hs, cmap="gray", extent=[ext[0], ext[2], ext[1], ext[3]],
                  origin="upper", vmin=0, vmax=255, zorder=1)
        ax.set_xlim(win[0], win[2]); ax.set_ylim(win[1], win[3])
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_visible(True); sp.set_color(GRID)

    ax = axes[0]
    gpd.GeoSeries([sel.geometry], crs=6346).boundary.plot(
        ax=ax, color=S2, linewidth=2.4, zorder=4)
    rd = roads[roads.intersects(sel.geometry.buffer(50))]
    if len(rd):
        rd.plot(ax=ax, color=S3, linewidth=2.0, zorder=5)
    pits.plot(ax=ax, facecolor=S1, alpha=0.45, edgecolor=S1, linewidth=1.8,
              zorder=6)
    gpd.GeoSeries([tgt.geometry], crs=6346).boundary.plot(
        ax=ax, color=INK, linewidth=1.4, linestyle="--", zorder=7)
    import matplotlib.patheffects as pe
    halo = [pe.Stroke(linewidth=3, foreground="white"), pe.Normal()]
    pb = sel.geometry.bounds
    ax.text((pb[0] + pb[2]) / 2, pb[3] + 6, "pad", color=S2, fontsize=10.5,
            fontweight="bold", ha="center", va="bottom", zorder=9,
            path_effects=halo)
    if len(rd):
        g = rd.geometry.iloc[0]
        px, py = g.interpolate(0.5, normalized=True).coords[0]
        ax.text(px + 8, py, "road", color=S3, fontsize=10.5, fontweight="bold",
                ha="left", va="center", zorder=9, path_effects=halo)
    _scalebar(ax, wa, 50)
    title(ax, "a  One pad, its floors and its access road",
          f"pad {int(pid)}, {sel.ha:.2f} ha, {int(sel.n)} floors "
          f"· dashed outline is the depression in panel b")

    ax = axes[1]
    wl = wall[wall.intersects(tgt.geometry)]
    if len(wl):
        wl.plot(ax=ax, facecolor=S3, alpha=0.35, edgecolor=S3, linewidth=1.6,
                zorder=5)
    wbox = gpd.GeoSeries.from_wkt(
        [f"POLYGON(({wb[0]} {wb[1]},{wb[2]} {wb[1]},{wb[2]} {wb[3]},"
         f"{wb[0]} {wb[3]},{wb[0]} {wb[1]}))"], crs=6346).iloc[0]
    pin = pit[pit.intersects(wbox)]
    pin.plot(ax=ax, facecolor=S1, alpha=0.45, edgecolor=S1, linewidth=2.2,
             zorder=6)
    gpd.GeoSeries([tgt.geometry], crs=6346).boundary.plot(
        ax=ax, color=S2, linewidth=2.4, zorder=7)
    _scalebar(ax, wb, 10)
    title(ax, "b  The same pit, three layers",
          f"floor {pin[pin.intersects(tgt.geometry)].geometry.area.sum():.0f} m² "
          f"· whole depression {tgt.geometry.area:.0f} m²")

    handles = [mpatches.Patch(facecolor=S1, alpha=0.5, edgecolor=S1,
                              label="pit_inside — floor (712)"),
               mpatches.Patch(facecolor=S3, alpha=0.4, edgecolor=S3,
                              label="pit_wall — rim (586)"),
               mpatches.Patch(facecolor="none", edgecolor=S2, linewidth=2.2,
                              label="pit_full — whole depression (723)"),
               mpatches.Patch(facecolor="none", edgecolor=S2, linewidth=2.2,
                              label="pad — disturbed footprint (995)"),
               mpatches.Patch(facecolor="none", edgecolor=S3, linewidth=2.2,
                              label="roads — access traces (3,690)")]
    handles = [h for h in handles
               if "pit_" in h.get_label()]
    fig.legend(handles=handles, frameon=False, fontsize=9, ncol=5,
               loc="lower center", bbox_to_anchor=(0.5, -0.04))
    fig.text(0.01, -0.13,
             "Every polygon here was drawn by hand in QGIS over 0.5 m hillshade.\n"
             "A point detector can only be right or wrong about where this is. A "
             "polygon can be right in the wrong\nplace, the right place at the "
             "wrong size, or one object split in two — which is why rim "
             "containment\nand IoU had to be added to the metrics. Pads hold one "
             "or two floors: 995 pads carry 712 floors.",
             fontsize=8.5, color=MUTED)
    save(fig, "annotation_schema_one_pad_one_pit_9t_05.png",
         f"pad {int(pid)} with {int(sel.n)} floors, then floor/rim/full on one pit")


def _scalebar(ax, win, length_m):
    x0 = win[0] + (win[2] - win[0]) * 0.06
    y0 = win[1] + (win[3] - win[1]) * 0.06
    ax.plot([x0, x0 + length_m], [y0, y0], color="white", linewidth=5, zorder=9,
            solid_capstyle="butt")
    ax.plot([x0, x0 + length_m], [y0, y0], color=INK, linewidth=2.2, zorder=10,
            solid_capstyle="butt")
    ax.text(x0 + length_m / 2, y0 + (win[3] - win[1]) * 0.022, f"{length_m} m",
            ha="center", fontsize=9, color=INK, zorder=10,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))


# ============================== F8 threshold sweep: ground flagged vs found
TILE_HA = 2025.0


def fig_threshold_sweep():
    """The headline. Two questions asked of all three U-Nets at the same nine
    cutoffs: how much ground does it flag, and how much of the withheld hand
    annotation does it find."""
    pit = pd.read_csv(ROOT / "data/9t/results/pit/thresholds/"
                             "pit_threshold_found_vs_missed_summary_9t.csv")
    pad = pd.read_csv(ROOT / "data/9t/results/pad/thresholds/"
                             "pad_threshold_sweep_9t.csv")
    road = pd.read_csv(ROOT / "data/9t/results/road/thresholds/"
                              "road_threshold_sweep_9t.csv")

    pit = pit.assign(pct=pit.ha_claimed / TILE_HA * 100,
                     rec=pit.found / pit.n_heldout)
    pad = pad.assign(pct=pad.ha_claimed / TILE_HA * 100, rec=pad.recall_iou30)
    road = road.assign(pct=road.ha_claimed / TILE_HA * 100, rec=road.recall_clean)

    series = [("pit floors", pit, S1, 0.20),
              ("roads", road, S3, 0.20),
              ("pads", pad, S2, 0.45)]
    # per-series label offsets, so the two 0.20 operating points do not collide
    OFF_A = {"pit floors": (10, 8), "roads": (10, 10), "pads": (10, -18)}
    OFF_B = {"pit floors": (-4, 14), "roads": (-14, -22), "pads": (12, -6)}

    fig, axes = plt.subplots(1, 2, figsize=(13.2, 5.8))

    ax = axes[0]
    for name, d, col, op in series:
        ax.plot(d.threshold, d.pct, color=col, linewidth=2.2, zorder=3)
        r = d.iloc[(d.threshold - op).abs().argmin()]
        ax.plot([r.threshold], [r.pct], "o", color=col, markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate(f"{name}  {r.pct:.2f}%", xy=(r.threshold, r.pct),
                    xytext=OFF_A[name], textcoords="offset points",
                    fontsize=9.5, color=col, fontweight="bold")
    ax.set_yscale("log")
    ax.set_xlabel("probability threshold")
    ax.set_ylabel("share of the 2,025 ha tile flagged (%, log)")
    title(ax, "a  How much ground does it flag?",
          "the search burden a field crew inherits")

    ax = axes[1]
    for name, d, col, op in series:
        ax.plot(d.threshold, d.rec, color=col, linewidth=2.2, zorder=3)
        r = d.iloc[(d.threshold - op).abs().argmin()]
        ax.plot([r.threshold], [r.rec], "o", color=col, markersize=9,
                markeredgecolor=SURFACE, markeredgewidth=2, zorder=5)
        ax.annotate(f"{name}  {r.rec:.3f}", xy=(r.threshold, r.rec),
                    xytext=OFF_B[name], textcoords="offset points",
                    fontsize=9.5, color=col, fontweight="bold")
    ax.set_ylim(0, 1.16)
    ax.set_xlabel("probability threshold")
    ax.set_ylabel("recall on withheld hand annotation")
    title(ax, "b  How much of it does it find?",
          "pit 126/127 rims · road recall_clean · pad IoU ≥ 0.30")

    for ax in axes:
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)

    pr = pit.iloc[(pit.threshold - 0.20).abs().argmin()]
    fig.text(0.01, -0.09,
             f"Dots are the operating points: pit 0.20, road 0.20, pad 0.45. "
             f"At 0.20 the pit model flags {pr.ha_claimed:.2f} ha of 2,025 and "
             f"finds {int(pr.found)} of {int(pr.n_heldout)} withheld rims.\n"
             "The pit sweep was run at four cutoffs, 0.20-0.50; road and pad at "
             "nine, 0.05-0.90.\n"
             "The pad model is the weak one and flagged area is what shows it: "
             "55x the ground for fewer targets. Scored against hand-drawn "
             "annotation withheld from training — no DEP list, no TIGER.",
             fontsize=8.5, color=MUTED)
    save(fig, "threshold_sweep_flagged_area_vs_recall_pit_pad_road_9t.png",
         f"pit {pr.pct:.2f}% of tile at thr 0.20 for {int(pr.found)}/"
         f"{int(pr.n_heldout)} rims; road and pad on the same axes")


# ================================================= F9 pad annotation growth
def fig_pad_growth():
    srcs = [("plat650\n2026-08-06",
             "qgis/annotations/_history/_snapshot_plat_artifacts_2026-08-06/"
             "plat_dataset_manifest.csv"),
            ("pad995\n2026-09-04",
             "qgis/annotations/_history/_backup_pit_ann527_2026-09-04/"
             "pad_dataset_manifest.csv"),
            ("pad995\ncurrent",
             "data/9t/derived/05/pad_dataset_manifest.csv")]
    # "unused" is two different things and conflating them overstates how much
    # annotation lies outside the tile: a null block_id means outside 9t, while
    # an in-tile row can still be unused if the greedy fill left its block out.
    rows = []
    for lbl, p in srcs:
        d = pd.read_csv(ROOT / p)
        vc = d["split"].value_counts().to_dict()
        has_block = d["block_id"].notna() if "block_id" in d.columns else None
        outside = 0 if has_block is None else int((~has_block).sum())
        unassigned = int(vc.get("unused", 0)) - outside
        rows.append({"label": lbl, "total": len(d),
                     "train": int(vc.get("train", 0)),
                     "val": int(vc.get("val", 0)),
                     "test": int(vc.get("test", 0)),
                     "unassigned": unassigned, "outside": outside})
    df = pd.DataFrame(rows)

    fig, ax = plt.subplots(figsize=(9.2, 5.4))
    x = np.arange(len(df))
    bottom = np.zeros(len(df))
    for split in ["train", "val", "test", "unassigned", "outside"]:
        v = df[split].to_numpy()
        lab = {"unassigned": "in 9t, block unassigned",
               "outside": "outside 9t (no block)"}.get(split, split)
        ax.bar(x, v, 0.56, bottom=bottom, color=PAD_COLOR[split],
               edgecolor=SURFACE, linewidth=2, label=lab)
        for xi, (vi, bi) in enumerate(zip(v, bottom)):
            if vi > 30:
                ax.text(xi, bi + vi / 2, f"{vi}", ha="center", va="center",
                        fontsize=9.5,
                        color=INK2 if split in ("unassigned", "outside") else "white",
                        fontweight="bold")
        bottom += v
    for xi, row in df.iterrows():
        inside = row["train"] + row["val"] + row["test"] + row["unassigned"]
        ax.text(xi, row["total"] + 16, f"{row['total']} annotated", ha="center",
                fontsize=10, fontweight="bold", color=INK)
        ax.text(xi, row["total"] + 56, f"{inside} inside 9t", ha="center",
                fontsize=9, color=INK2)
    ax.set_xticks(x); ax.set_xticklabels(df["label"], fontsize=10)
    ax.set_ylabel("pads in the 9t manifest")
    ax.set_ylim(0, df["total"].max() * 1.22)
    ax.legend(frameon=False, fontsize=9, ncol=3, loc="upper left",
              bbox_to_anchor=(0, -0.09))
    title(ax, "Pads move the same way the pits do",
          "650 → 995 annotated, and the split is reassigned even when the "
          "count does not change")
    fig.text(0.01, -0.13,
             "The two 995 bars hold the same pads. Only the block split differs, "
             "so test went 87 → 114 and val 100 → 69 with no new "
             "annotation at all.\nThat is the same hazard as the pits: a "
             "checkpoint scored against the middle bar is not held out under the "
             "right one.\nUnlike the pits, not every unused pad is outside the "
             "tile. 66 sit in 9t blocks the greedy fill left unassigned,\nso 650 "
             "pads are in-tile, not 584.", fontsize=8.5, color=MUTED)
    save(fig, "annotation_growth_pad_splits_650_995_9t.png",
         f"pad split composition, "
         f"{int(df.iloc[-1][['train','val','test','unassigned']].sum())} of "
         f"{int(df.iloc[-1]['total'])} current pads inside 9t")


if __name__ == "__main__":
    os.chdir(ROOT)
    for fn in [fig_locator, fig_pipeline, fig_annotation_growth, fig_block_grid,
               fig_classical_vs_unet, fig_nisar,
               fig_pit_anatomy, fig_threshold_sweep, fig_pad_growth]:
        print(f"[{fn.__name__}]")
        try:
            fn()
        except Exception:
            print("  FAILED")
            traceback.print_exc()
    print("\n=== written ===")
    for n, note in written:
        print(f"{n}\n    {note}")
    (OUT / "_manifest.json").write_text(json.dumps(written, indent=2))
