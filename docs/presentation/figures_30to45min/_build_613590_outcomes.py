"""What the models produced on 613590 -- a tile no model ever trained on.

Four images:

    1  the generated road network, whole tile
    2  generated against TIGER, the public road layer
    3  road found vs missed at threshold 0.50, scored on hand-drawn truth
    4  pit and pad candidates over the tile

WHY 613590 MATTERS
------------------
Cross-validation shows a number is stable. It does not show it travels: every
fold is still the same tile, the same survey, the same terrain. 613590 is a
different tile with its own hand-drawn ground truth, so it is the only place in
the project where "does this generalise" has an answer.

A CAUTION THAT BELONGS ON THE SLIDE
-----------------------------------
The 613590 road truth splits by `src`. `613590_review_r2` is a previous model's
own output that a human vetted, and every model scores 0.96-1.00 on it -- that
subset cannot rank anything. `613590_added_r2` was drawn from scratch on roads
the model MISSED, so it is the only informative half and it is adversarially
hard by construction. Quote the `added` column.

SOURCES
-------
    roads_studio/exports/faithful_613590_deployed_t030.gpkg      3,693 feats, 231.4 km
    data/westernpa_d20/613590/derived/1m/tiger_roads_613590.gpkg    39 feats,  40.0 km
    data/613590/results/road/thresholds/road_found_vs_missed_thr0p50_613590_1m.gpkg
    data/613590/derived/inference_05/pit_candidates_613590_05.gpkg
    data/613590/derived/inference_05/pad_candidates_613590_05.gpkg

Run:
    python docs/presentation/figures_30to45min/_build_613590_outcomes.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import pyogrio
import rasterio
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from rasterio.windows import from_bounds

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "5_probability_surfaces"
EPSG = 6346

FAITHFUL = ROOT / "roads_studio" / "exports" / "faithful_613590_deployed_t030.gpkg"
TIGER = ROOT / "data/westernpa_d20/613590/derived/1m/tiger_roads_613590.gpkg"
FOUND_MISSED = (ROOT / "data/613590/results/road/thresholds"
                / "road_found_vs_missed_thr0p50_613590_1m.gpkg")
PIT_CAND = ROOT / "data/613590/derived/inference_05/pit_candidates_613590_05.gpkg"
PAD_CAND = ROOT / "data/613590/derived/inference_05/pad_candidates_613590_05.gpkg"
HILL = ROOT / "data/613590/derived/05/hillshade_613590_05.tif"
DEM = ROOT / "data/613590/derived/05/dem_613590_05.tif"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

C_GEN = "#ffb300"
C_TIGER = "#2979ff"
C_FOUND = "#1baf7a"
C_MISSED = "#e5194b"
C_PIT = "#ccff00"
C_PAD = "#e040fb"
HALO = [pe.Stroke(linewidth=2.6, foreground="#000000"), pe.Normal()]


def tile_bounds():
    src = HILL if HILL.exists() else DEM
    with rasterio.open(src) as r:
        return tuple(r.bounds), src


def basemap(ax, bb, src):
    """Hillshade if we still have one, otherwise a flat ground."""
    if src is None or not src.exists():
        ax.set_facecolor("#efeee8")
        return
    with rasterio.open(src) as r:
        # whole tile at ~2000 px is plenty for a slide
        f = max(1, int(max(r.width, r.height) / 2000))
        a = r.read(1, out_shape=(r.height // f, r.width // f)).astype("float32")
        if r.nodata is not None:
            a[a == r.nodata] = np.nan
    ax.imshow(a, extent=[bb[0], bb[2], bb[1], bb[3]], origin="upper",
              cmap="gray", vmin=np.nanpercentile(a, 2),
              vmax=np.nanpercentile(a, 98), zorder=1)


def frame(ax, bb, title, subtitle, handles, note):
    ax.set_xlim(bb[0], bb[2]); ax.set_ylim(bb[1], bb[3])
    ax.set_aspect("equal")
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    l, b, r_, t = bb
    x0, y0 = l + (r_ - l) * 0.05, b + (t - b) * 0.055
    ax.plot([x0, x0 + 1000], [y0, y0], color="white", linewidth=6,
            solid_capstyle="butt", zorder=12)
    ax.plot([x0, x0 + 1000], [y0, y0], color=INK, linewidth=2.6,
            solid_capstyle="butt", zorder=13)
    ax.text(x0 + 500, y0 + (t - b) * 0.022, "1 km", ha="center", fontsize=10,
            color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))
    nx, ny = r_ - (r_ - l) * 0.06, t - (t - b) * 0.17
    ax.annotate("", xy=(nx, ny + (t - b) * 0.09), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.6,
                                mutation_scale=18), zorder=13)
    ax.text(nx, ny + (t - b) * 0.10, "N", ha="center", va="bottom", fontsize=13,
            fontweight="bold", color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc", ec="none"))
    if handles:
        leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                        facecolor="#ffffff", edgecolor=RULE, fontsize=11,
                        framealpha=1.0)
        leg.set_zorder(20)
    # The caveat belongs where the claim is, not in a footer that gets cropped
    # off a slide. Anything that changes how the figure should be READ goes
    # above the map; plain provenance is dropped entirely.
    head = title
    if subtitle:
        head += "\n" + subtitle
    ax.set_title(head, fontsize=17, fontweight="bold", loc="left", pad=10)
    if note:
        ax.set_title(note, fontsize=9.5, fontweight="normal", loc="right",
                     color=MUTED, pad=10)
    fig = ax.get_figure()
    fig.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.020)


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    fig.savefig(p, dpi=190)
    plt.close(fig)
    print(f"  {p.stat().st_size/1e3:7.0f} KB  {name}")


def read_any(path, layer=None):
    if not path.exists():
        print(f"  MISSING {path}")
        return gpd.GeoDataFrame(geometry=[])
    if layer is None:
        layers = [n for n, _ in pyogrio.list_layers(str(path))]
        layer = layers[0]
    g = gpd.read_file(path, layer=layer)
    if g.crs is None or g.crs.to_epsg() != EPSG:
        g = g.set_crs(EPSG, allow_override=True)
    return g[g.geometry.notna() & ~g.geometry.is_empty]


def main() -> int:
    bb, hsrc = tile_bounds()
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })
    print(f"613590 tile: {bb[0]:.0f}-{bb[2]:.0f} E, {bb[1]:.0f}-{bb[3]:.0f} N"
          f"  basemap={hsrc.name if hsrc else 'none'}")

    # --- 1. the generated network -------------------------------------------
    gen = read_any(FAITHFUL, "roads")
    km = gen.length.sum() / 1000
    fig, ax = plt.subplots(figsize=(9.6, 9.6))
    basemap(ax, bb, hsrc)
    gen.plot(ax=ax, color=C_GEN, linewidth=0.9, zorder=5)
    frame(ax, bb, "Generated road network, 613590",
          f"{len(gen):,} segments  \u00b7  {km:.1f} km  \u00b7  a tile no road "
          f"model ever trained on",
          [Line2D([], [], color=C_GEN, linewidth=2.4,
                  label=f"model output  ({km:.0f} km)")],
          "faithful_613590_deployed_t030.gpkg  \u00b7  threshold 0.30, "
          "faithful vectorisation \u2014 strip and trace, nothing invented")
    save(fig, "roads_generated_thr0p30_613590.png")

    # --- 2. against TIGER ----------------------------------------------------
    tig = read_any(TIGER)
    tkm = tig.length.sum() / 1000
    fig, ax = plt.subplots(figsize=(9.6, 9.6))
    basemap(ax, bb, hsrc)
    gen.plot(ax=ax, color=C_GEN, linewidth=0.9, zorder=4)
    tig.plot(ax=ax, color=C_TIGER, linewidth=2.2, zorder=6, path_effects=HALO)
    frame(ax, bb, "What the public road layer knows about",
          f"model {km:.1f} km against TIGER {tkm:.1f} km \u2014 "
          f"{km / max(tkm, 1e-9):.1f}x more road",
          [Line2D([], [], color=C_GEN, linewidth=2.4,
                  label=f"model output  ({km:.0f} km)"),
           Line2D([], [], color=C_TIGER, linewidth=2.4,
                  label=f"TIGER  ({tkm:.0f} km)")],
          "US Census TIGER/Line roads. These are the roads a public dataset "
          "carries; the rest are logging and access traces under canopy.")
    save(fig, "roads_vs_tiger_613590.png")

    # --- 3. found vs missed --------------------------------------------------
    # The `chunks` layer carries found=True/False and src. The vetted subset
    # (613590_review_r2) is a previous model's own output, so every model scores
    # 0.96+ on it; only 613590_added_r2 can rank anything. Split the figure by
    # src rather than lumping them, or the number flatters.
    if FOUND_MISSED.exists():
        ch = read_any(FOUND_MISSED, "chunks")
        added = ch[ch.src == "613590_added_r2"]
        fig, ax = plt.subplots(figsize=(9.6, 9.6))
        basemap(ax, bb, hsrc)
        hit = added[added.found]
        miss = added[~added.found]
        if len(hit):
            hit.plot(ax=ax, color=C_FOUND, linewidth=1.6, zorder=5)
        if len(miss):
            miss.plot(ax=ax, color=C_MISSED, linewidth=2.0, zorder=7)
        rate = len(hit) / max(len(added), 1)
        handles = [
            Line2D([], [], color=C_FOUND, linewidth=2.4,
                   label=f"found  ({len(hit):,}, {hit.length.sum()/1000:.1f} km)"),
            Line2D([], [], color=C_MISSED, linewidth=2.4,
                   label=f"missed  ({len(miss):,}, {miss.length.sum()/1000:.1f} km)"),
        ]
        frame(ax, bb, "Road detection on the hard half of the truth",
              f"613590_added_r2 only  ·  threshold 0.50  ·  "
              f"{len(hit):,} of {len(added):,} chunks found  =  {rate:.3f}",
              handles,
              "The other 4,004 chunks are 613590_review_r2 — a previous "
              "model's output that a human vetted. Every model scores 0.96+ on "
              "those, so they rank nothing and are excluded here.")
        save(fig, "roads_found_vs_missed_thr0p50_613590.png")

    # --- 4. pit and pad candidates ------------------------------------------
    pit = read_any(PIT_CAND)
    pad = read_any(PAD_CAND)
    fig, ax = plt.subplots(figsize=(9.6, 9.6))
    basemap(ax, bb, hsrc)
    handles = []
    if len(pad):
        pad.plot(ax=ax, facecolor="none", edgecolor=C_PAD, linewidth=1.0,
                 zorder=5)
        handles.append(Patch(facecolor="none", edgecolor=C_PAD, linewidth=2.0,
                             label=f"pad candidates  ({len(pad):,})"))
    if len(pit):
        c = pit.geometry.centroid
        ax.scatter(c.x, c.y, s=9, c=C_PIT, edgecolors="#000000",
                   linewidths=0.35, zorder=7)
        handles.append(Line2D([], [], marker="o", linestyle="none",
                              markerfacecolor=C_PIT, markeredgecolor="#000000",
                              markersize=7,
                              label=f"pit candidates  ({len(pit):,})"))
    frame(ax, bb, "Pit and pad candidates, 613590",
          f"{len(pit):,} pit candidates  \u00b7  {len(pad):,} pad candidates  "
          f"\u00b7  transferred with no retraining",
          handles,
          "pit_candidates_613590_05.gpkg, pad_candidates_613590_05.gpkg  "
          "\u00b7  candidates, not confirmed wells")
    save(fig, "pit_pad_candidates_613590.png")

    print(f"\nwrote to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
