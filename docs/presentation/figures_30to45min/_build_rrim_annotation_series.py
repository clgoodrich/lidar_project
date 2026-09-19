"""Each annotation layer on RRIM, at a place where that layer is worth seeing.

Ten images: one PAIR per class, the same frame without the shapefile and with
it, so the question "is that thing really there in the terrain, or did somebody
draw it" can be answered by flicking between two pictures.

    class      centre                        width
    roads      41.499080 N, 79.541300 W      2 km
    drainage   41.502510 N, 79.533711 W      2 km
    pads       41.507320 N, 79.541360 W      2 km
    pits       41.494906 N, 79.537175 W      1 km
    all four   dead centre of 9t             3 km

Earlier versions put every class on one 300 m square, which flattered some
layers and starved others -- 300 m holds a couple of pits and almost no road.
Each class now gets a frame chosen for it, and the all-four frame is the middle
of the 9t training area so it is not cherry-picked.

WHY RRIM AS THE BASE
--------------------
Red Relief Image Map combines positive and negative openness with slope, so
concave and convex features read at once without a lighting direction. A
hillshade hides whatever faces away from its light; RRIM does not, which makes
it the honest backdrop for showing where a hand-drawn polygon actually sits.

COLOUR CHOICE
-------------
RRIM is already red-brown and cyan, so the annotation colours deliberately avoid
both: amber, magenta, yellow-green and strong blue, each with a dark halo so it
survives over the bright and dark parts of the base. No red/green pair, per the
colourblind rule in CLAUDE.md.

THE BASE IS DRAWN THE WAY QGIS DRAWS IT
---------------------------------------
`rrim_openness_9t_05` is multibandcolor with NoEnhancement in
`qgis/wellsight.qgz`, which means the stored bytes go to screen untouched. This
used to apply a 2-98 percentile stretch of its own, so the base did not match
what is on the screen. It does now.

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

EPSG = 6346
#: 9t training area, and its dead centre -- the frame for the all-four image.
BBOX_9T = (619500.0, 4593000.0, 624000.0, 4597500.0)
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
#: The outer rim sits in the same picture as the floor, so it has to separate
#: from C_PIT. White against yellow-green is a large lightness step, and the two
#: also differ by FORM -- the rim is an outline, the floor is filled.
C_PIT_OUT = "#ffffff"

HALO = [pe.Stroke(linewidth=3.2, foreground="#000000"), pe.Normal()]

#: (slug, title, variants, latitude, longitude, window width in metres).
#: Each variant is (filename tag, panel subtitle, layers to draw). The first is
#: always the bare terrain, so every site gives a before/after pair at minimum.
#: `None` for the centre means the dead centre of 9t.
BARE = ("terrain_only", "terrain only", [])
SERIES = [
    ("roads", "Roads",
     [BARE, ("with_annotation", "with the annotation", ["roads"])],
     41.499080, -79.541300, 2000.0),
    ("drainage", "Drainage",
     [BARE, ("with_annotation", "with the annotation", ["drainage"])],
     41.502510, -79.533711, 2000.0),
    ("pads", "Pads",
     [BARE, ("with_annotation", "with the annotation", ["pad"])],
     41.507320, -79.541360, 2000.0),
    # Pits are drawn as two separate things and the floor is what the model is
    # trained on, so the rim, the floor and the pair all get their own picture.
    ("pits", "Pits",
     [BARE,
      ("with_pit_inside", "floors only", ["pit_inside"]),
      ("with_pit_outside", "outer rims only", ["pit_outside"]),
      ("with_both", "rims and floors together", ["pit_outside", "pit_inside"])],
     41.494906, -79.537175, 1000.0),
    ("all", "All four annotation layers",
     [BARE, ("with_annotation", "with the annotation",
             ["pad", "drainage", "roads", "pit_inside"])],
     None, None, 3000.0),
]


def target_xy(lat, lon):
    if lat is None:
        return (BBOX_9T[0] + BBOX_9T[2]) / 2, (BBOX_9T[1] + BBOX_9T[3]) / 2
    from pyproj import Transformer
    return Transformer.from_crs(4326, EPSG, always_xy=True).transform(lon, lat)


def window_bounds(lat, lon, side_m):
    x, y = target_xy(lat, lon)
    h = side_m / 2
    return (x - h, y - h, x + h, y + h)


def bar_length(side_m):
    """A scale bar that is a sensible fraction of the frame, and a round number."""
    for n in (1000, 500, 200, 100, 50, 20):
        if n <= side_m / 4:
            return n
    return 10


def read_rrim(bounds):
    with rasterio.open(RRIM) as r:
        w = from_bounds(*bounds, transform=r.transform)
        a = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
    # NoEnhancement in the QGIS project: the stored bytes go straight to screen.
    a = a[:3] / 255.0
    return np.clip(np.moveaxis(a, 0, -1), 0, 1)


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
    if layer == "pit_outside":
        gdf.boundary.plot(ax=ax, color=C_PIT_OUT, linewidth=2.2, zorder=7,
                          path_effects=HALO)
        # a white patch on a white legend is invisible, so the swatch is a
        # haloed line -- same dark outline the map uses
        return Line2D([], [], color=C_PIT_OUT, linewidth=2.6,
                      path_effects=HALO, label=f"pit rims  ({len(gdf)})")
    if layer in ("pad", "plat"):
        gdf.boundary.plot(ax=ax, color=C_PAD, linewidth=2.6, zorder=5,
                          path_effects=HALO)
        return Patch(facecolor="none", edgecolor=C_PAD, linewidth=2.6,
                     label=f"pads  ({len(gdf)})")
    return None


def main() -> int:
    if not RRIM.exists():
        raise SystemExit(f"missing RRIM base: {RRIM}")
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })
    cache = {}
    written = 0

    for slug, title, variants, lat, lon, side_m in SERIES:
        bounds = window_bounds(lat, lon, side_m)
        x, y = target_xy(lat, lon)
        clip = box(*bounds)
        site = ("9t_centre" if lat is None else
                f"{lat:.6f}".replace(".", "p") + "N_"
                + f"{abs(lon):.6f}".replace(".", "p") + "W")
        outdir = OUT / f"venango_{slug}_{site}"
        outdir.mkdir(parents=True, exist_ok=True)
        base = read_rrim(bounds)
        ext = [bounds[0], bounds[2], bounds[1], bounds[3]]
        print(f"\n{slug}: centre {x:.1f} E, {y:.1f} N, {side_m:.0f} m window")

        for tag, subtitle, layers in variants:
            fig, ax = plt.subplots(figsize=(7.6, 8.1))
            ax.imshow(base, extent=ext, origin="upper", zorder=1)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_aspect("equal")
            for sp in ax.spines.values():
                sp.set_color("#e5e4dd")

            handles = []
            for layer in layers:
                key = (layer, slug)
                if key not in cache:
                    cache[key] = read_layer_clip(layer, clip)
                h = draw(ax, layer, cache[key])
                if h is not None:
                    handles.append(h)

            ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])

            # scale bar + north arrow, on every image because each stands alone
            l, b, r_, t = bounds
            bar = bar_length(side_m)
            x0, y0 = l + (r_ - l) * 0.06, b + (t - b) * 0.07
            ax.plot([x0, x0 + bar], [y0, y0], color="white", linewidth=5.5,
                    solid_capstyle="butt", zorder=12)
            ax.plot([x0, x0 + bar], [y0, y0], color=INK, linewidth=2.4,
                    solid_capstyle="butt", zorder=13)
            lab = f"{bar/1000:g} km" if bar >= 1000 else f"{bar:g} m"
            ax.text(x0 + bar / 2, y0 + (t - b) * 0.03, lab, ha="center",
                    fontsize=9.5, color=INK, zorder=13,
                    bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc",
                              ec="none"))
            nx, ny = r_ - (r_ - l) * 0.075, t - (t - b) * 0.21
            ax.annotate("", xy=(nx, ny + (t - b) * 0.115), xytext=(nx, ny),
                        arrowprops=dict(arrowstyle="-|>", color=INK,
                                        linewidth=2.4, mutation_scale=18),
                        zorder=13)
            ax.text(nx, ny + (t - b) * 0.13, "N", ha="center", va="bottom",
                    fontsize=12, fontweight="bold", color=INK, zorder=13,
                    bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc",
                              ec="none"))

            if handles:
                leg = ax.legend(handles=handles, loc="lower right",
                                frameon=True, facecolor="#ffffff",
                                edgecolor="#c9c8bf", fontsize=10.5,
                                framealpha=1.0)
                leg.set_zorder(20)      # opaque: lines were reading through it

            ax.set_title(f"{title} — {subtitle}", fontsize=17,
                         fontweight="bold", loc="left", pad=30)
            ax.text(0, 1.008, f"{side_m/1000:g} km across", transform=ax.transAxes,
                    fontsize=11, color=INK2, va="bottom")
            fig.text(0.021, 0.014,
                     "Red Relief Image Map · Chiba et al. 2008",
                     fontsize=9, color=MUTED)
            fig.subplots_adjust(left=0.02, right=0.98, top=0.925, bottom=0.045)

            name = f"annotations_{slug}_{site}_{side_m:.0f}m_{tag}_9t_05.png"
            fig.savefig(outdir / name, dpi=200)
            plt.close(fig)
            written += 1
            n = {l: len(cache[(l, slug)]) for l in layers}
            print(f"  {(outdir / name).stat().st_size/1e3:7.0f} KB  {name}"
                  + (f"   {n}" if n else ""))

    print(f"\nwrote {written} images under {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
