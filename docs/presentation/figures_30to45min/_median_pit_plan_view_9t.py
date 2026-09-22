# -*- coding: utf-8 -*-
"""An overhead view of the average orphaned well pit, drawn from a real one.

WHY A REAL PIT AND NOT A DIAGRAM
--------------------------------
A drawn circle would say what we think a pit looks like. This shows one, and
picks it by measurement rather than by eye: of the 501 pits inside 9t that have
both an outline and a floor, it selects the one whose floor area and outline
area are jointly closest to the medians of the whole population. The result is
a pit that is average in both dimensions at once, not one that is average in
area while being an odd shape.

    median floor    26.2 m2      the selected pit   26.6 m2
    median outline 183.1 m2      the selected pit  181.0 m2

Everything on this figure is measured on 9t only, per the rule that the
annotation and morphology slides talk about 9t and nothing else.

THREE PANELS, LEFT TO RIGHT
---------------------------
    hillshade   what a person would see on a shaded relief map. Pits are hard
                to see here, which is the point of the next panel.
    local relief with the hillside subtracted, the dish is obvious. This is
                the layer a reader should associate with pit detection.
    dimensions  the same two outlines with nothing behind them, carrying the
                numbers: across, floor across, depth, and the areas.

The first two panels prove the third is not an idealisation.

DEPTH IS MEASURED, NOT QUOTED
-----------------------------
The deck said "about 0.7 m deep". Here depth is computed for every paired pit
in 9t as the difference between the median elevation around the outline and the
median elevation inside the floor, and the figure reports the population median
alongside this pit's own value. If the two disagree the caption says so rather
than smoothing it over.

COLOUR
------
The validated pair from CLAUDE.md, outline #1F5FA8 and floor #D97706 (worst
pair dE 21.1 deutan, 22.6 normal). No green anywhere, so no red/green pair.
The two rings are also distinguishable by position alone -- one encloses the
other -- so the figure does not depend on colour at all.

Run:
    python docs/presentation/figures_30to45min/_median_pit_plan_view_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/median_pit_plan_view_9t_05.png
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from shapely.geometry import box

ROOT = Path(__file__).resolve().parents[3]
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
DER = ROOT / "data/9t/derived/05"
HS = DER / "hillshade_9t_05.tif"
LRM = DER / "local_relief_10_9t_05.tif"
DEM = DER / "dem_9t_05.tif"
OUT = ROOT / "docs/presentation/figures_30to45min/v6"

BB = box(619500, 4593000, 624000, 4597500)
CRS = 6346
HALF = 15.0                      # half-width of the map window, metres

PAPER = "#f7f8f6"
INK = "#141a1f"
INK2 = "#545c63"
MUTED = "#8a887e"
OUTLINE = "#1F5FA8"              # validated "delivered" blue
FLOOR = "#D97706"                # validated "recovered" orange


def read(path, b):
    with rasterio.open(path) as s:
        a = s.read(1, window=from_bounds(*b, transform=s.transform)).astype("float32")
        if s.nodata is not None:
            a[a == s.nodata] = np.nan
    return a


def zonal_median(path, geom):
    """Median raster value inside a polygon, read from its own tight window."""
    b = geom.bounds
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(1, window=w).astype("float32")
        if s.nodata is not None:
            a[a == s.nodata] = np.nan
        tr = s.window_transform(w)
    if a.size == 0:
        return np.nan
    from rasterio.features import geometry_mask
    m = geometry_mask([geom], out_shape=a.shape, transform=tr, invert=True)
    v = a[m & np.isfinite(a)]
    return float(np.median(v)) if v.size else np.nan


def ring_median(path, rim, floor):
    """Median elevation of the wall: inside the outline, outside the floor."""
    b = rim.bounds
    with rasterio.open(path) as s:
        w = from_bounds(*b, transform=s.transform)
        a = s.read(1, window=w).astype("float32")
        if s.nodata is not None:
            a[a == s.nodata] = np.nan
        tr = s.window_transform(w)
    from rasterio.features import geometry_mask
    inr = geometry_mask([rim], out_shape=a.shape, transform=tr, invert=True)
    inf = geometry_mask([floor], out_shape=a.shape, transform=tr, invert=True)
    v = a[inr & ~inf & np.isfinite(a)]
    return float(np.median(v)) if v.size else np.nan


def draw_poly(ax, geom, colour, lw, label=None, fill=None):
    """A few annotations were digitised as MultiPolygon, so handle both."""
    parts = list(geom.geoms) if geom.geom_type == "MultiPolygon" else [geom]
    for g in parts:
        xs, ys = g.exterior.xy
        if fill:
            ax.fill(xs, ys, color=colour, alpha=fill, zorder=3, linewidth=0)
        ax.plot(xs, ys, color=colour, linewidth=lw, zorder=4, label=label,
                solid_joinstyle="round")
        label = None


def main() -> int:
    for p in (ANN, HS, LRM, DEM):
        if not p.exists():
            raise SystemExit(f"missing: {p}")

    fl = gpd.read_file(ANN, layer="pit_inside").to_crs(CRS)
    rm = gpd.read_file(ANN, layer="pit_outside").to_crs(CRS)
    fl = fl[fl.geometry.centroid.within(BB)].copy()
    rm = rm[rm.geometry.centroid.within(BB)].copy()
    fl["a"] = fl.area
    rm["ar"] = rm.area

    pair = gpd.sjoin(fl[["a", "geometry"]], rm[["ar", "geometry"]],
                     predicate="within", how="inner")
    tf, tr = fl["a"].median(), rm["ar"].median()
    pair["score"] = (((pair["a"] - tf) / tf).abs()
                     + ((pair["ar"] - tr) / tr).abs())
    pick = pair.loc[pair["score"].idxmin()]
    floor_g = pick.geometry
    rim_g = rm.loc[pick["index_right"]].geometry

    # ---- depth, for this pit and for the population ----------------------
    depths = []
    for i, row in pair.iterrows():
        rg = rm.loc[row["index_right"]].geometry
        w = ring_median(DEM, rg, row.geometry)
        f = zonal_median(DEM, row.geometry)
        if np.isfinite(w) and np.isfinite(f):
            depths.append(w - f)
    depths = np.asarray(depths)
    d_med = float(np.median(depths))
    d_this = ring_median(DEM, rim_g, floor_g) - zonal_median(DEM, floor_g)

    dia = lambda a: 2 * np.sqrt(a / np.pi)
    print(f"  {len(pair)} paired pits in 9t")
    print(f"  floor   median {tf:6.1f} m2   this pit {pick['a']:6.1f} m2")
    print(f"  outline median {tr:6.1f} m2   this pit {pick['ar']:6.1f} m2")
    print(f"  equivalent diameter: outline {dia(tr):.1f} m, floor {dia(tf):.1f} m")
    print(f"  depth   median {d_med:5.2f} m   this pit {d_this:5.2f} m "
          f"(10-90%: {np.percentile(depths,10):.2f}-"
          f"{np.percentile(depths,90):.2f})")

    c = rim_g.centroid
    b = (c.x - HALF, c.y - HALF, c.x + HALF, c.y + HALF)
    ext = [b[0], b[2], b[1], b[3]]

    plt.rcParams.update({"figure.facecolor": PAPER, "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, axes = plt.subplots(1, 3, figsize=(15.2, 5.6))

    hs = read(HS, b)
    lo, hi = np.nanpercentile(hs, (2, 98))
    axes[0].imshow(hs, cmap="gray", vmin=lo, vmax=hi, extent=ext)
    axes[0].set_title("Shaded relief\nwhat the eye gets", loc="left",
                      fontsize=14, fontweight="bold", color=INK, pad=8)

    lr = read(LRM, b)
    # A 98th-percentile symmetric stretch washed the dish out: one strong
    # cell at the window edge set the range and everything else went white.
    # Stretch on the window's own 3-97 percentile instead.
    v0, v1 = np.nanpercentile(lr, (3, 97))
    axes[1].imshow(lr, cmap="Greys_r", vmin=v0, vmax=v1, extent=ext)
    axes[1].set_title("Local relief\nthe hillside subtracted", loc="left",
                      fontsize=14, fontweight="bold", color=INK, pad=8)

    for ax in axes[:2]:
        draw_poly(ax, rim_g, OUTLINE, 2.4)
        draw_poly(ax, floor_g, FLOOR, 2.4)
        ax.set_xlim(b[0], b[2])
        ax.set_ylim(b[1], b[3])
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_color("#c9ccc6")

    # ---- panel 3: the same shapes, dimensioned ---------------------------
    ax = axes[2]
    ax.set_title("The same pit, measured\n9t medians in brackets", loc="left",
                 fontsize=14, fontweight="bold", color=INK, pad=8)
    draw_poly(ax, rim_g, OUTLINE, 3.0, fill=0.10)
    draw_poly(ax, floor_g, FLOOR, 3.0, fill=0.22)
    ax.set_xlim(b[0], b[2])
    ax.set_ylim(b[1], b[3])
    ax.set_aspect("equal")
    ax.axis("off")

    # a 5 m scale bar, bottom left, so the reader never guesses at size
    x0, y0 = b[0] + 2.0, b[1] + 2.0
    ax.plot([x0, x0 + 5], [y0, y0], color=INK, linewidth=3, zorder=6)
    ax.text(x0 + 2.5, y0 + 0.5, "5 m", fontsize=12, fontweight="bold",
            color=INK, ha="center", va="bottom", zorder=6)

    ax.text(b[0] + 1.2, b[3] - 1.4,
            f"outline  {pick['ar']:.0f} m²   [{tr:.0f}]\n"
            f"across   {dia(pick['ar']):.1f} m   [{dia(tr):.1f}]",
            fontsize=12.5, color=OUTLINE, fontweight="bold",
            va="top", ha="left", linespacing=1.5, zorder=6)
    ax.text(b[2] - 1.2, b[3] - 1.4,
            f"floor  {pick['a']:.0f} m²   [{tf:.0f}]\n"
            f"across {dia(pick['a']):.1f} m   [{dia(tf):.1f}]",
            fontsize=12.5, color=FLOOR, fontweight="bold",
            va="top", ha="right", linespacing=1.5, zorder=6)
    ax.text(b[0] + 1.2, b[1] + 5.4,
            f"depth  {d_this:.2f} m   [median {d_med:.2f}]",
            fontsize=12.5, color=INK, fontweight="bold",
            va="bottom", ha="left", zorder=6)

    for ax in axes:
        ax.set_aspect("equal")

    fig.subplots_adjust(left=0.012, right=0.988, top=0.86, bottom=0.03,
                        wspace=0.06)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "median_pit_plan_view_9t_05.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    from PIL import Image
    print(f"\n  {Image.open(p).size[0]}x{Image.open(p).size[1]} px")
    print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
