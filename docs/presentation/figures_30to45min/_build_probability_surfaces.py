"""What the model actually outputs: a probability surface, per feature class.

Four images over the same Venango window -- pit floor, pad, road, drainage --
each showing the raw probability the network assigns to every pixel, with the
hand-drawn annotation outlined on top so you can see what it got and what it
invented.

A probability raster is not a detection. Turning it into one needs a threshold,
and that is the next slide. These are the surface the threshold is applied to.

SOURCES
-------
    pit       data/9t/models/pit/unet_v2/pit_prob_floor.tif
    pad       data/9t/models/pad/unet/pad_prob.tif
    road      data/9t/models/road/sweep_202607/cldice/road_prob.tif   (1 m)
    drainage  data/9t/models/drainage/unet_1m/drainage_prob.tif       (1 m)

Pit and pad are 0.5 m; road and drainage are 1 m. Same ground either way -- the
window is defined in metres, not pixels.

Run:
    python docs/presentation/figures_30to45min/_build_probability_surfaces.py
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
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds
from shapely.geometry import box

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
MODELS = ROOT / "data" / "9t" / "models"
ANN = ROOT / "qgis" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "5_probability_surfaces"

LAT, LON = 41.492640, -79.546127
SIDE_M = 300.0
EPSG = 6346

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

#: Probability is a magnitude, so it gets a single-hue ramp. Low probability is
#: transparent rather than pale, so the hillshade shows through and you can see
#: WHERE the model is confident, not just how much.
CM_PROB = LinearSegmentedColormap.from_list(
    "p", ["#ffffcc", "#fd8d3c", "#bd0026"])

C_ANN = "#00e5ff"
HALO = [pe.Stroke(linewidth=3.0, foreground="#000000"), pe.Normal()]

#: Argmax is the class the network actually picks per pixel -- the probability
#: surface after the decision, not before it. Road and drainage come from
#: 3-class models, so their argmax rasters carry both classes; the pit argmax
#: carries floor AND wall. That is worth showing rather than hiding.
#: (slug, title, raster, class values -> (label, colour))
ARGMAX = [
    ("pit", "Pit argmax — what the model commits to",
     MODELS / "pit" / "unet_v2" / "pit_argmax.tif",
     {1: ("pit floor", "#ccff00"), 2: ("pit wall", "#00e5ff")}),
    ("pad", "Pad argmax — what the model commits to",
     MODELS / "pad" / "unet" / "pad_argmax.tif",
     {1: ("pad", "#e040fb")}),
    ("road", "Road argmax — what the model commits to",
     MODELS / "road" / "unet_1m_recall" / "road_argmax.tif",
     {1: ("road", "#ffb300"), 2: ("drainage", "#2979ff")}),
    ("drainage", "Drainage argmax — drainage-positive model",
     MODELS / "drainage" / "unet_1m" / "drainage_argmax.tif",
     {1: ("road", "#ffb300"), 2: ("drainage", "#2979ff")}),
]

#: (slug, title, raster, annotation layer, how the annotation is drawn)
SETS = [
    ("pit", "Pit floor probability",
     MODELS / "pit" / "unet_v2" / "pit_prob_floor.tif", "pit_inside", "poly"),
    ("pad", "Pad probability",
     MODELS / "pad" / "unet" / "pad_prob.tif", "pad", "poly"),
    ("road", "Road probability",
     MODELS / "road" / "sweep_202607" / "cldice" / "road_prob.tif", "roads", "line"),
    ("drainage", "Drainage probability",
     MODELS / "drainage" / "unet_1m" / "drainage_prob.tif", "drainage", "line"),
]


def target_xy():
    from pyproj import Transformer
    return Transformer.from_crs(4326, EPSG, always_xy=True).transform(LON, LAT)


def bounds():
    x, y = target_xy()
    h = SIDE_M / 2
    return (x - h, y - h, x + h, y + h)


def read(path, bb, band=1):
    with rasterio.open(path) as r:
        w = from_bounds(*bb, transform=r.transform)
        a = r.read(band, window=w, boundless=True,
                   fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    return a


def read_hillshade(bb):
    return read(D05 / "hillshade_9t_05.tif", bb)


def read_layer(layer, clip):
    import pyogrio
    names = {n for n, _ in pyogrio.list_layers(str(ANN))}
    if layer not in names:
        layer = {"pad": "plat"}.get(layer, layer)
        if layer not in names:
            return gpd.GeoDataFrame(geometry=[])
    g = gpd.read_file(ANN, layer=layer)
    if g.crs is None or g.crs.to_epsg() != EPSG:
        g = g.set_crs(EPSG, allow_override=True)
    g = g[g.geometry.notna() & ~g.geometry.is_empty]
    return g[g.intersects(clip)]


def main() -> int:
    bb = bounds()
    x, y = target_xy()
    ext = [bb[0], bb[2], bb[1], bb[3]]
    clip = box(*bb)
    site = (f"{LAT:.6f}".replace(".", "p") + "N_"
            + f"{abs(LON):.6f}".replace(".", "p") + "W")
    outdir = OUT / f"venango_site_{site}"
    outdir.mkdir(parents=True, exist_ok=True)

    hs = read_hillshade(bb)
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })

    for slug, title, raster, layer, how in SETS:
        if not raster.exists():
            print(f"  MISSING {raster}")
            continue
        prob = read(raster, bb)
        # A probability raster can be stored 0-1 or 0-255 depending on the
        # writer; normalise so the colour bar means the same thing every time.
        finite = prob[np.isfinite(prob)]
        if finite.size and np.nanmax(finite) > 1.5:
            prob = prob / 255.0
        prob = np.clip(prob, 0, 1)

        fig, ax = plt.subplots(figsize=(7.4, 8.0))
        ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
                  vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
                  zorder=1)
        # below 0.05 is background noise; showing it as a wash of pale colour
        # makes the model look far less certain than it is
        masked = np.ma.masked_where(~np.isfinite(prob) | (prob < 0.05), prob)
        im = ax.imshow(masked, extent=ext, origin="upper", cmap=CM_PROB,
                       vmin=0.0, vmax=1.0, alpha=0.78, zorder=3)

        g = read_layer(layer, clip)
        if len(g):
            if how == "poly":
                g.boundary.plot(ax=ax, color=C_ANN, linewidth=2.0, zorder=6,
                                path_effects=HALO)
            else:
                g.plot(ax=ax, color=C_ANN, linewidth=1.8, zorder=6,
                       path_effects=HALO)

        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_color(RULE)

        l, b, r_, t = bb
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

        cb = fig.colorbar(im, ax=ax, fraction=0.038, pad=0.015)
        cb.set_label("probability", fontsize=10, color=INK2)
        cb.outline.set_edgecolor(RULE)

        ax.set_title(title, fontsize=17, fontweight="bold", loc="left", pad=10)
        with rasterio.open(raster) as r:
            res = r.res[0]
        fig.subplots_adjust(left=0.02, right=0.90, top=0.93, bottom=0.030)

        name = f"venango_{site}_{SIDE_M:.0f}m_prob_{slug}_9t.png"
        fig.savefig(outdir / name, dpi=200)
        plt.close(fig)
        hi = float(np.nanmax(prob)) if np.isfinite(prob).any() else float("nan")
        print(f"  {(outdir / name).stat().st_size/1e3:7.0f} KB  {name}"
              f"   max p = {hi:.2f}, annotation = {len(g)}")

    # ------------------------------------------------------------ argmax
    # The class the network commits to per pixel: the probability surface AFTER
    # the decision. Road and drainage come from 3-class models, so both classes
    # appear in each; the pit argmax carries floor and wall together.
    from matplotlib.colors import ListedColormap
    from matplotlib.patches import Patch
    for slug, title, raster, classes in ARGMAX:
        if not raster.exists():
            print(f"  MISSING {raster}")
            continue
        arr = read(raster, bb)
        fig, ax = plt.subplots(figsize=(7.4, 8.0))
        ax.imshow(hs, extent=ext, origin="upper", cmap="gray",
                  vmin=np.nanpercentile(hs, 2), vmax=np.nanpercentile(hs, 98),
                  zorder=1)
        handles, counts = [], {}
        for val, (label, colour) in sorted(classes.items()):
            m = np.ma.masked_where(~np.isfinite(arr) | (arr != val), arr)
            ax.imshow(m, extent=ext, origin="upper",
                      cmap=ListedColormap([colour]), vmin=val - 0.5,
                      vmax=val + 0.5, alpha=0.85, zorder=3 + val)
            n = int(np.nansum(arr == val))
            counts[label] = n
            handles.append(Patch(facecolor=colour, edgecolor="none",
                                 label=f"{label}  ({n:,} px)"))
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_color(RULE)

        l, b, r_, t = bb
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
        leg = ax.legend(handles=handles, loc="lower right", frameon=True,
                        facecolor="#ffffff", edgecolor=RULE, fontsize=10.5,
                        framealpha=1.0)
        leg.set_zorder(20)

        ax.set_title(title, fontsize=16, fontweight="bold", loc="left", pad=10)
        with rasterio.open(raster) as r:
            res = r.res[0]
        fig.subplots_adjust(left=0.02, right=0.99, top=0.93, bottom=0.030)
        name = f"venango_{site}_{SIDE_M:.0f}m_argmax_{slug}_9t.png"
        fig.savefig(outdir / name, dpi=200)
        plt.close(fig)
        print(f"  {(outdir / name).stat().st_size/1e3:7.0f} KB  {name}   {counts}")

    print(f"\nwrote to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
