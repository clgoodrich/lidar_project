"""Why roads are cut into ~40 m chunks before training.

Two images:

    1  a window, chunk by chunk, alternating colour so the cuts are visible
    2  the same chunks coloured by train / val / test

THE PROBLEM CHUNKING SOLVES
---------------------------
Roads vary enormously in length. If each road is one training example, a 1 km
road and a 30 m stub count the same: the long road is barely learned and barely
scored, and a handful of long roads dominate whatever split they land in.
Cutting every line into ~40 m pieces makes each stretch its own sampling centre
and its own evaluation unit. On 9t that took evaluation from 27 lopsided lines
to 168 comparable chunks, and line AP from 0.963 to 0.992.

THE COST, WHICH BELONGS ON THE SLIDE
------------------------------------
Chunks inherit their parent road's geometry, so two chunks of the same road can
land in different splits. 485 of 1,220 held-out chunks (39.8%) share a parent
with a training chunk. `recall_clean` -- the 735 chunks whose entire parent road
was held out -- is the comparable number, and it costs about 1.5 points.

Source: data/9t/derived/05/road_chunks_9t.gpkg  (17,591 chunks)

Run:
    python docs/presentation/figures_30to45min/_build_road_chunking.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from rasterio.windows import from_bounds
from shapely.geometry import box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "4_model_building"
CHUNKS = D05 / "road_chunks_9t.gpkg"
HILL = D05 / "hillshade_9t_05.tif"
EPSG = 6346

SIDE_M = 700.0          # wide enough to hold several whole roads

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

SPLIT_COLOR = {"train": "#2a78d6", "val": "#eb6834",
               "test": "#1baf7a", "unused": "#c9c8bf"}
ALT = ["#ffb300", "#7b2ff7"]        # alternating, to expose the cut points


def hillshade(bb):
    with rasterio.open(HILL) as r:
        w = from_bounds(*bb, transform=r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float32")
    return a


def densest_window(g, side, bin_m=50.0):
    """Pick the window by road density rather than by eye.

    A brute-force scan over every candidate origin is O(windows x features) and
    takes minutes on 15,000 chunks. Binning the midpoints and summing over a
    sliding box is the same answer in milliseconds.
    """
    mids = g.geometry.interpolate(0.5, normalized=True)
    xs, ys = np.asarray(mids.x), np.asarray(mids.y)
    l, b, r_, t = g.total_bounds
    nx = max(1, int((r_ - l) / bin_m))
    ny = max(1, int((t - b) / bin_m))
    H, xe, ye = np.histogram2d(xs, ys, bins=[nx, ny],
                               range=[[l, l + nx * bin_m], [b, b + ny * bin_m]])
    k = max(1, int(side / bin_m))
    # summed-area table, so every window total is four lookups
    S = H.cumsum(0).cumsum(1)
    S = np.pad(S, ((1, 0), (1, 0)))
    win = (S[k:, k:] - S[:-k, k:] - S[k:, :-k] + S[:-k, :-k])
    i, j = np.unravel_index(int(np.argmax(win)), win.shape)
    x0, y0 = xe[i], ye[j]
    return (x0, y0, x0 + side, y0 + side), int(win[i, j])


def decorate(ax, bb, title, subtitle, handles, note, bar_m=100):
    ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3])
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    l, b, r_, t = bb
    x0, y0 = l + (r_ - l) * 0.06, b + (t - b) * 0.07
    ax.plot([x0, x0 + bar_m], [y0, y0], color="white", linewidth=5.5,
            solid_capstyle="butt", zorder=12)
    ax.plot([x0, x0 + bar_m], [y0, y0], color=INK, linewidth=2.4,
            solid_capstyle="butt", zorder=13)
    ax.text(x0 + bar_m / 2, y0 + (t - b) * 0.028, f"{bar_m} m", ha="center",
            fontsize=9.5, color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))
    nx, ny = r_ - (r_ - l) * 0.07, t - (t - b) * 0.19
    ax.annotate("", xy=(nx, ny + (t - b) * 0.10), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.4,
                                mutation_scale=18), zorder=13)
    ax.text(nx, ny + (t - b) * 0.115, "N", ha="center", va="bottom",
            fontsize=12, fontweight="bold", color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc", ec="none"))
    if handles:
        leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                        facecolor="#ffffff", edgecolor=RULE, fontsize=10.5,
                        framealpha=1.0)
        leg.set_zorder(20)
    ax.set_title(title, fontsize=17, fontweight="bold", loc="left", pad=10)
    fig = ax.get_figure()
    fig.subplots_adjust(left=0.02, right=0.98, top=0.925, bottom=0.030)


def main() -> int:
    g = gpd.read_file(CHUNKS, layer="chunks")
    if g.crs is None or g.crs.to_epsg() != EPSG:
        g = g.set_crs(EPSG, allow_override=True)
    roads = g[g.kind == "road"].copy()
    # roads.shp runs from Oil Creek to McKean, far outside 9t, so the density
    # search has to be clipped to the tile or it picks a window with no
    # hillshade under it and the basemap comes out black.
    with rasterio.open(HILL) as r:
        tile = box(*r.bounds)
    roads = roads[roads.intersects(tile)].copy()
    print(f"{len(g):,} chunks total, {len(roads):,} road chunks inside 9t")
    print(f"  median chunk {roads.length.median():.1f} m, "
          f"mean {roads.length.mean():.1f} m")

    bb, n = densest_window(roads, SIDE_M)
    print(f"  densest {SIDE_M:.0f} m window holds {n} road chunks")
    inw = roads[roads.intersects(box(*bb))].copy()
    hs = hillshade(bb)
    ext = [bb[0], bb[2], bb[1], bb[3]]

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })

    # --- 1. the cuts themselves ---------------------------------------------
    fig, ax = plt.subplots(figsize=(8.4, 9.0))
    ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
              vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
              zorder=1)
    # alternate the colour along each parent road so every cut is visible
    inw = inw.sort_values(["parent_id", "seg_idx"]) if "parent_id" in inw.columns \
        else inw.sort_values("line_id")
    for i, (_, row) in enumerate(inw.iterrows()):
        gpd.GeoSeries([row.geometry], crs=EPSG).plot(
            ax=ax, color=ALT[i % 2], linewidth=3.0, zorder=5)
    # mark the cut points
    ends = [g_.interpolate(0.0) for g_ in inw.geometry]
    ax.scatter([p.x for p in ends], [p.y for p in ends], s=16, c="#ffffff",
               edgecolors="#000000", linewidths=0.7, zorder=8)
    decorate(ax, bb, "Roads cut into ~40 m chunks",
             f"{len(inw)} chunks in this {SIDE_M:.0f} m window  \u00b7  "
             f"median {inw.length.median():.1f} m  \u00b7  white dots are the cuts",
             [Line2D([], [], color=ALT[0], linewidth=3, label="chunk"),
              Line2D([], [], color=ALT[1], linewidth=3, label="next chunk"),
              Line2D([], [], marker="o", linestyle="none", markersize=7,
                     markerfacecolor="#ffffff", markeredgecolor="#000000",
                     label="cut point")],
             "road_chunks_9t.gpkg  \u00b7  colours alternate along each parent "
             "road so the segmentation is visible; they carry no meaning")
    p = OUT / f"road_chunking_40m_cuts_9t_{SIDE_M:.0f}m.png"
    fig.savefig(p, dpi=200); plt.close(fig)
    print(f"  {p.stat().st_size/1e3:7.0f} KB  {p.name}")

    # --- 2. the same chunks by split ----------------------------------------
    fig, ax = plt.subplots(figsize=(8.4, 9.0))
    ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
              vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
              zorder=1)
    handles = []
    for split in ["unused", "train", "val", "test"]:
        sub = inw[inw.split == split]
        if not len(sub):
            continue
        sub.plot(ax=ax, color=SPLIT_COLOR[split], linewidth=3.0,
                 zorder=4 if split == "unused" else 6)
        handles.append(Line2D([], [], color=SPLIT_COLOR[split], linewidth=3,
                              label=f"{split}  ({len(sub)})"))
    whole = g[g.kind == "road"]
    counts = whole.split.value_counts().to_dict()
    decorate(ax, bb, "The same chunks, by split",
             "  \u00b7  ".join(f"{k} {v:,}" for k, v in sorted(counts.items()))
             + "   (whole tile)",
             handles,
             "Chunks inherit their parent road, so two pieces of one road can "
             "land in different splits. 485 of 1,220 held-out chunks share a "
             "parent with a training chunk \u2014 recall_clean is the "
             "comparable number.")
    p = OUT / f"road_chunking_40m_by_split_9t_{SIDE_M:.0f}m.png"
    fig.savefig(p, dpi=200); plt.close(fig)
    print(f"  {p.stat().st_size/1e3:7.0f} KB  {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
