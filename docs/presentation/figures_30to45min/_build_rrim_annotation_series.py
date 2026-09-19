"""The same Venango site on RRIM, with each annotation layer in turn.

Five images, all the same 300 m square, all on the same RRIM base:

    drainage        roads        pits        pads        all four

WHY RRIM AS THE BASE
--------------------
Red Relief Image Map combines positive and negative openness with slope, so
concave and convex features read at once without a lighting direction. A
hillshade hides whatever faces away from its light; RRIM does not, which makes
it the honest backdrop for showing where a hand-drawn polygon actually sits.

COLOUR CHOICE
-------------
RRIM is already red-brown and cyan, so the annotation colours deliberately avoid
both: amber, magenta, yellow-green and strong blue, each with a white halo so it
survives over the bright and dark parts of the base.

Centre: 41.492640 N, -79.546127 W  ->  621359.6 E, 4594467.4 N (EPSG:6346)

Run:
    python docs/presentation/figures_30to45min/_build_rrim_annotation_series.py
"""
from __future__ import annotations

from pathlib import Path

import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from rasterio.windows import from_bounds
from shapely.geometry import box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "3_annotations"

LAT, LON = 41.49264, -79.546127
SIDE_M = 300.0
EPSG = 6346
RRIM = D05 / "rrim_openness_9t_05.tif"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"

#: Chosen against RRIM's own red/cyan, not from the light-background palette.
C_DRAIN = "#2979ff"
C_ROAD = "#ffb300"
C_PIT = "#ccff00"
C_PAD = "#e040fb"

HALO = [pe.Stroke(linewidth=3.2, foreground="#000000"), pe.Normal()]

#: (slug, title, layers to draw)
SERIES = [
    ("drainage", "Drainage", ["drainage"]),
    ("roads",    "Roads",    ["roads"]),
    ("pits",     "Pits",     ["pit_inside"]),
    ("pads",     "Pads",     ["pad"]),
    ("all",      "All four annotation layers",
     ["pad", "drainage", "roads", "pit_inside"]),
]


def target_xy():
    from pyproj import Transformer
    return Transformer.from_crs(4326, EPSG, always_xy=True).transform(LON, LAT)


def window_bounds():
    x, y = target_xy()
    h = SIDE_M / 2
    return (x - h, y - h, x + h, y + h)


def read_rrim(bounds):
    with rasterio.open(RRIM) as r:
        w = from_bounds(*bounds, transform=r.transform)
        a = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
    a = a[:3]
    out = []
    for b in a:
        lo, hi = np.nanpercentile(b, 2), np.nanpercentile(b, 98)
        out.append((b - lo) / max(hi - lo, 1e-9))
    return np.clip(np.moveaxis(np.stack(out), 0, -1), 0, 1)


def read_layer_clip(layer, clip_geom):
    """Read one annotation layer and keep only what touches the window."""
    import pyogrio
    names = {n for n, _ in pyogrio.list_layers(str(ANN))}
    if layer not in names:
        alias = {"pad": "plat", "pit_full": "pit_outside"}.get(layer)
        if alias in names:
            layer = alias
        else:
            print(f"    layer {layer!r} absent; present: {sorted(names)}")
            return gpd.GeoDataFrame(geometry=[])
    g = gpd.read_file(ANN, layer=layer)
    if g.crs is None or g.crs.to_epsg() != EPSG:
        g = g.set_crs(EPSG, allow_override=True)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g[g.intersects(clip_geom)]


def draw(ax, layer, gdf):
    if not len(gdf):
        return None
    if layer == "drainage":
        gdf.plot(ax=ax, color=C_DRAIN, linewidth=2.0, zorder=6,
                 path_effects=HALO)
        return Line2D([], [], color=C_DRAIN, linewidth=2.6,
                      label=f"drainage  ({len(gdf)})")
    if layer == "roads":
        gdf.plot(ax=ax, color=C_ROAD, linewidth=2.2, zorder=7,
                 path_effects=HALO)
        return Line2D([], [], color=C_ROAD, linewidth=2.6,
                      label=f"roads  ({len(gdf)})")
    if layer == "pit_inside":
        gdf.plot(ax=ax, facecolor=C_PIT, edgecolor=C_PIT, alpha=0.55,
                 linewidth=1.8, zorder=8)
        gdf.boundary.plot(ax=ax, color=C_PIT, linewidth=1.8, zorder=9,
                          path_effects=HALO)
        return Patch(facecolor=C_PIT, edgecolor=C_PIT, alpha=0.75,
                     label=f"pit floors  ({len(gdf)})")
    if layer in ("pad", "plat"):
        gdf.boundary.plot(ax=ax, color=C_PAD, linewidth=2.6, zorder=5,
                          path_effects=HALO)
        return Patch(facecolor="none", edgecolor=C_PAD, linewidth=2.6,
                     label=f"pads  ({len(gdf)})")
    return None


def main() -> int:
    if not RRIM.exists():
        raise SystemExit(f"missing RRIM base: {RRIM}")

    bounds = window_bounds()
    x, y = target_xy()
    clip = box(*bounds)
    site = (f"{LAT:.6f}".replace(".", "p") + "N_"
            + f"{abs(LON):.6f}".replace(".", "p") + "W")
    outdir = OUT / f"venango_site_{site}"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"centre {x:.1f} E, {y:.1f} N   window {SIDE_M:.0f} m")

    base = read_rrim(bounds)
    ext = [bounds[0], bounds[2], bounds[1], bounds[3]]
    cache = {}

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })

    for slug, title, layers in SERIES:
        fig, ax = plt.subplots(figsize=(7.2, 7.8))
        ax.imshow(base, extent=ext, origin="upper", zorder=1)
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_color("#e5e4dd")

        handles = []
        for layer in layers:
            if layer not in cache:
                cache[layer] = read_layer_clip(layer, clip)
            h = draw(ax, layer, cache[layer])
            if h is not None:
                handles.append(h)

        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])

        # scale bar + north arrow, on every image because each stands alone
        l, b, r_, t = bounds
        x0, y0 = l + (r_ - l) * 0.06, b + (t - b) * 0.07
        ax.plot([x0, x0 + 50], [y0, y0], color="white", linewidth=5.5,
                solid_capstyle="butt", zorder=12)
        ax.plot([x0, x0 + 50], [y0, y0], color=INK, linewidth=2.4,
                solid_capstyle="butt", zorder=13)
        ax.text(x0 + 25, y0 + (t - b) * 0.03, "50 m", ha="center", fontsize=9.5,
                color=INK, zorder=13,
                bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))
        nx, ny = r_ - (r_ - l) * 0.075, t - (t - b) * 0.21
        ax.annotate("", xy=(nx, ny + (t - b) * 0.115), xytext=(nx, ny),
                    arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.4,
                                    mutation_scale=18), zorder=13)
        ax.text(nx, ny + (t - b) * 0.13, "N", ha="center", va="bottom",
                fontsize=12, fontweight="bold", color=INK, zorder=13,
                bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc", ec="none"))

        if handles:
            leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                            facecolor="#ffffff", edgecolor="#c9c8bf",
                            fontsize=10.5, framealpha=1.0)
            leg.set_zorder(20)          # opaque: lines were reading through it

        ax.set_title(title, fontsize=17, fontweight="bold", loc="left", pad=10)
        fig.text(0.021, 0.016,
                 "Red Relief Image Map \u00b7 Chiba et al. 2008",
                 fontsize=9, color=MUTED)
        fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=0.048)

        name = f"venango_{site}_{SIDE_M:.0f}m_rrim_{slug}_9t_05.png"
        fig.savefig(outdir / name, dpi=200)
        plt.close(fig)
        counts = {k: len(v) for k, v in cache.items() if k in layers}
        print(f"  {(outdir / name).stat().st_size/1e3:7.0f} KB  {name}   {counts}")

    print(f"\nwrote {len(SERIES)} images to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
