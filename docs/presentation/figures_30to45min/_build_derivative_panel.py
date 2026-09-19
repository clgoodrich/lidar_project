"""One place in Venango, seen every way we can see it.

One PNG per view, each standalone with its own scale bar and north arrow.

Optical aerial imagery plus every terrain derivative we build, over the same
300 m square, with a scale bar and a north arrow.

Centre: 41.492640 N, -79.546127 W  ->  621359.6 E, 4594467.4 N (EPSG:6346)
Tile:   9t, 0.5 m

WHY OPTICAL COMES FROM A WEB SERVICE
------------------------------------
There is no aerial photography in the repository. `rgb3_9t_05.tif` looks like it
might be, and is not -- it is a 3-band float32 composite of derivatives built to
feed YOLO, which expects three channels. So the optical panel is fetched from
ESRI World Imagery and reprojected to the tile's CRS. It is basemap imagery for
visual context, not a measured product, and it is not used in any analysis.

North is up: EPSG:6346 is a UTM projection and grid north is within a fraction of
a degree of true north here, so the arrow is drawn straight up without apology.

Run:
    python docs/presentation/figures_30to45min/_build_derivative_panel.py
"""
from __future__ import annotations

import io
import json
import urllib.request
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "2_terrain_derivatives"

LAT, LON = 41.49264, -79.546127
SIDE_M = 300.0
EPSG = 6346

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"

# Single-hue ramps, light to dark. No rainbow -- a rainbow ramp invents
# boundaries in continuous terrain that are not in the data.
CM_BLUE = LinearSegmentedColormap.from_list("b", ["#d6e6f9", "#2a78d6", "#10365f"])
CM_ORANGE = LinearSegmentedColormap.from_list("o", ["#fde3d1", "#eb6834", "#8c2f0c"])
CM_GREEN = LinearSegmentedColormap.from_list("g", ["#d8f0e4", "#1baf7a", "#0a5238"])

#: (filename, panel title, colormap, stretch). Stretch "pct" is a 2-98 percentile
#: clip, which keeps one bad pixel from flattening the whole panel.
#: (source raster, slug for the filename, plain title, colormap, stretch)
PANELS = [
    ("__optical__",             "aerial",         "Aerial imagery",       None,      None),
    ("hillshade_9t_05.tif",     "hillshade",      "Hillshade",            "gray",    "pct"),
    ("dem_9t_05.tif",           "dem",            "Bare-earth elevation", CM_BLUE,   "pct"),
    ("slope_9t_05.tif",         "slope",          "Slope",                CM_ORANGE, "pct"),
    ("lrm_5_9t_05.tif",         "lrm_5",          "Local relief, 5 m",    CM_ORANGE, "sym"),
    ("lrm_25_9t_05.tif",        "lrm_25",         "Local relief, 25 m",   CM_ORANGE, "sym"),
    ("tpi_05_9t_05.tif",        "tpi_05",         "Topographic position", CM_ORANGE, "sym"),
    ("openness_pos_9t_05.tif",  "openness_pos",   "Openness, positive",   CM_GREEN,  "pct"),
    ("openness_neg_9t_05.tif",  "openness_neg",   "Openness, negative",   CM_GREEN,  "pct"),
    ("roughness_11_9t_05.tif",  "roughness_11",   "Roughness",            CM_GREEN,  "pct"),
    ("rrim_openness_9t_05.tif", "rrim",           "RRIM",                 None,      "rgb"),
    ("chm_9t_05.tif",           "chm",            "Canopy height",        CM_GREEN,  "pct"),
]


def target_xy():
    from pyproj import Transformer
    tr = Transformer.from_crs(4326, EPSG, always_xy=True)
    return tr.transform(LON, LAT)


def window_bounds():
    x, y = target_xy()
    h = SIDE_M / 2
    return (x - h, y - h, x + h, y + h)


def read_window(path: Path, bounds):
    with rasterio.open(path) as r:
        w = from_bounds(*bounds, transform=r.transform)
        arr = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            arr[arr == r.nodata] = np.nan
    return arr


def fetch_optical(bounds, px=900):
    """ESRI World Imagery, exported straight into the tile CRS."""
    l, b, r_, t = bounds
    url = ("https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery"
           f"/MapServer/export?bbox={l},{b},{r_},{t}&bboxSR={EPSG}&imageSR={EPSG}"
           f"&size={px},{px}&format=png&f=json")
    with urllib.request.urlopen(url, timeout=60) as resp:
        href = json.load(resp)["href"]
    with urllib.request.urlopen(href, timeout=60) as resp:
        raw = resp.read()
    import matplotlib.image as mpimg
    return mpimg.imread(io.BytesIO(raw))


def stretch(arr, mode):
    v = arr[np.isfinite(arr)]
    if not v.size:
        return None, None
    if mode == "sym":                       # signed: centre the ramp on zero
        m = np.percentile(np.abs(v), 98)
        return -m, m
    return np.percentile(v, 2), np.percentile(v, 98)


def scale_bar(ax, bounds, length_m=50):
    l, b, r_, t = bounds
    x0 = l + (r_ - l) * 0.06
    y0 = b + (t - b) * 0.08
    ax.plot([x0, x0 + length_m], [y0, y0], color="white", linewidth=5,
            solid_capstyle="butt", zorder=9)
    ax.plot([x0, x0 + length_m], [y0, y0], color=INK, linewidth=2.2,
            solid_capstyle="butt", zorder=10)
    ax.text(x0 + length_m / 2, y0 + (t - b) * 0.035, f"{length_m} m",
            ha="center", fontsize=9, color=INK, zorder=10,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffcc", ec="none"))


def north_arrow(ax, bounds):
    l, b, r_, t = bounds
    x = r_ - (r_ - l) * 0.08
    y0 = t - (t - b) * 0.22
    ax.annotate("", xy=(x, y0 + (t - b) * 0.12), xytext=(x, y0),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.2,
                                mutation_scale=18), zorder=10)
    ax.text(x, y0 + (t - b) * 0.135, "N", ha="center", va="bottom",
            fontsize=12, fontweight="bold", color=INK, zorder=10,
            bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffcc", ec="none"))


def main() -> int:
    bounds = window_bounds()
    x, y = target_xy()
    site = f"{LAT:.6f}".replace(".", "p") + "N_" + f"{abs(LON):.6f}".replace(".", "p") + "W"
    outdir = OUT / f"venango_site_{site}"
    outdir.mkdir(parents=True, exist_ok=True)
    print(f"centre {x:.1f} E, {y:.1f} N   window {SIDE_M:.0f} m")
    print(f"writing to {outdir}\n")

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK, "axes.titlecolor": INK,
    })
    ext = [bounds[0], bounds[2], bounds[1], bounds[3]]
    written = []

    for fname, slug, title, cmap, mode in PANELS:
        fig, ax = plt.subplots(figsize=(7.2, 7.6))
        ax.set_xticks([]); ax.set_yticks([])
        ax.set_aspect("equal")
        for sp in ax.spines.values():
            sp.set_color("#e5e4dd")

        ok = True
        if fname == "__optical__":
            try:
                ax.imshow(fetch_optical(bounds), extent=ext, origin="upper")
            except Exception as e:
                print(f"  optical failed: {type(e).__name__}: {e}")
                ok = False
        else:
            src = D05 / fname
            if not src.exists():
                print(f"  MISSING {fname}")
                ok = False
            else:
                arr = read_window(src, bounds)
                if mode == "rgb" and arr.ndim == 3 and arr.shape[0] >= 3:
                    a = arr[:3]
                    a = np.stack([(b_ - np.nanpercentile(b_, 2)) /
                                  max(np.nanpercentile(b_, 98)
                                      - np.nanpercentile(b_, 2), 1e-9)
                                  for b_ in a])
                    ax.imshow(np.clip(np.moveaxis(a, 0, -1), 0, 1),
                              extent=ext, origin="upper")
                else:
                    a = arr[0] if arr.ndim == 3 else arr
                    vmin, vmax = stretch(a, mode)
                    ax.imshow(a, extent=ext, origin="upper", cmap=cmap,
                              vmin=vmin, vmax=vmax)
        if not ok:
            plt.close(fig)
            continue

        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        # Standalone images, so every one carries its own bar and arrow.
        scale_bar(ax, bounds)
        north_arrow(ax, bounds)

        ax.set_title(title, fontsize=17, fontweight="bold", loc="left", pad=10)
        # Nothing along the bottom except a method citation, and only where the
        # rendering itself comes from a paper.
        cite = ""
        if "rrim" in slug:
            cite = "Red Relief Image Map · Chiba et al. 2008"
        elif "openness" in slug:
            cite = "Openness · Yokoyama et al. 2002"
        elif fname == "__optical__":
            cite = "ESRI World Imagery · visual context only"
        bot = 0.052 if cite else 0.020
        if cite:
            fig.text(0.021, 0.018, cite, fontsize=9, color=MUTED)
        fig.subplots_adjust(left=0.02, right=0.98, top=0.93, bottom=bot)

        name = f"venango_{site}_{SIDE_M:.0f}m_{slug}_9t_05.png"
        fig.savefig(outdir / name, dpi=200)
        plt.close(fig)
        kb = (outdir / name).stat().st_size / 1e3
        written.append(name)
        print(f"  {kb:7.0f} KB  {name}")

    print(f"\n{len(written)} images in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
