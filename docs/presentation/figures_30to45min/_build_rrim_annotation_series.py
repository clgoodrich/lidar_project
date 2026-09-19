"""Each annotation layer on RRIM, at a place where that layer is worth seeing.

Twelve images: one PAIR per class, the same frame without the shapefile and
with it, so the question "is that thing really there in the terrain, or did
somebody draw it" can be answered by flicking between two pictures. Pits get
four -- terrain, floors, rims, and both -- because the floor and the rim are
separate layers and the floor is the one the model trains on.

They all land in one flat folder, numbered in talk order. An earlier version
filed them in five subfolders named by latitude and longitude; the coordinates
are exact and unreadable, so they moved to README.md and the filenames now say
the class and the variant instead.

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
#:
#: The name is the class, the frame width and the variant, and nothing else:
#: annotation_roads_2km_no_lines_9t.png. The precise centre of each site lives
#: in README.md, because a lat/lon blob in every filename made the folder
#: unreadable.
BARE = ("no_lines", "terrain only, nothing drawn on it", [])
SERIES = [
    ("roads", "Roads",
     [BARE, ("lines", "with the hand-drawn roads", ["roads"])],
     41.499080, -79.541300, 2000.0),
    ("drainage", "Drainage",
     [BARE, ("lines", "with the hand-drawn drainage", ["drainage"])],
     41.502510, -79.533711, 2000.0),
    ("pads", "Pads",
     [BARE, ("lines", "with the hand-drawn pads", ["pad"])],
     41.507320, -79.541360, 2000.0),
    # Pits are drawn as two separate things and the floor is what the model is
    # trained on, so the rim, the floor and the pair all get their own picture.
    ("pits", "Pits",
     [BARE,
      ("floors", "pit floors only — this is what the model learns",
       ["pit_inside"]),
      ("rims", "outer rims only", ["pit_outside"]),
      ("floors_and_rims", "rims and floors together",
       ["pit_outside", "pit_inside"])],
     41.494906, -79.537175, 1000.0),
    ("all", "All four annotation layers",
     [BARE, ("lines", "with all four layers drawn",
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


BEGIN = "<!-- annotation-series: generated, do not edit by hand -->"
END = "<!-- /annotation-series -->"


def write_readme(index):
    """The coordinates the filenames dropped, kept next to the images.

    The Descriptive-filename rule wants the location in the name. One site per
    class makes the class slug enough to tell the twelve apart, and a lat/lon
    blob in every name made the folder unreadable, so the precise centre is
    recorded here instead of in the name.

    The stage README also describes figures this script does not build, so only
    the block between the two markers is replaced.
    """
    rows = [BEGIN,
            "",
            "## The per-class before/after series",
            "",
            "Twelve images. Each class is a pair on the same",
            "frame: the terrain alone, then the same terrain with the",
            "hand-drawn layer over it. Flicking between the two answers \"is",
            "that really in the terrain, or did somebody draw it\". Pits get",
            "four, because the floor and the rim are separate layers and the",
            "floor is the one the model trains on.",
            "",
            "| file | shows | centre (WGS84) | width |",
            "|---|---|---|---|"]
    for name, title, subtitle, site, side_m in index:
        rows.append(f"| `{name}` | {title} — {subtitle} | {site} "
                    f"| {side_m/1000:g} km |")
    rows += ["",
             "Rebuild with:",
             "",
             "```bash",
             "python docs/presentation/figures_30to45min/"
             "_build_rrim_annotation_series.py",
             "```",
             "",
             END]
    block = "\n".join(rows)

    p = OUT / "README.md"
    old = p.read_text(encoding="utf-8") if p.exists() else ""
    if BEGIN in old and END in old:
        head, _, tail = old.partition(BEGIN)
        _, _, tail = tail.partition(END)
        new = head + block + tail
    else:
        new = (old.rstrip() + "\n\n" + block + "\n") if old else block + "\n"
    p.write_text(new, encoding="utf-8")
    print(f"  index    {p}")


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
    index = []

    for slug, title, variants, lat, lon, side_m in SERIES:
        bounds = window_bounds(lat, lon, side_m)
        x, y = target_xy(lat, lon)
        clip = box(*bounds)
        site = ("dead centre of 9t" if lat is None else
                f"{lat:.6f} N, {abs(lon):.6f} W")
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
            ax.text(x0 + bar / 2, y0 + (t - b) * 0.017, lab, ha="center",
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

            # The class is the headline and the variant is the line under it.
            # Running both into one title gave "Pits — pit floors only — this
            # is what the model learns", which is three clauses and one dash
            # too many to read from the back of a room.
            ax.set_title(title, fontsize=18, fontweight="bold", loc="left",
                         pad=26)
            ax.text(0, 1.008, f"{subtitle}  ·  {side_m/1000:g} km across",
                    transform=ax.transAxes, fontsize=12, color=INK2,
                    va="bottom")
            fig.text(0.021, 0.014,
                     "Red Relief Image Map · Chiba et al. 2008",
                     fontsize=9, color=MUTED)
            fig.subplots_adjust(left=0.02, right=0.98, top=0.905, bottom=0.045)

            wide = (f"{side_m/1000:g}km").replace(".", "p")
            name = f"annotation_{slug}_{wide}_{tag}_9t.png"
            fig.savefig(OUT / name, dpi=200)
            plt.close(fig)
            written += 1
            n = {l: len(cache[(l, slug)]) for l in layers}
            print(f"  {(OUT / name).stat().st_size/1e3:7.0f} KB  {name}"
                  + (f"   {n}" if n else ""))
            index.append((name, title, subtitle, site, side_m))

    write_readme(index)
    print(f"\nwrote {written} images under {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
