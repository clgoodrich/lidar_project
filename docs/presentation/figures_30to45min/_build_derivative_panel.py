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

STYLING COMES FROM THE QGIS PROJECT, NOT FROM ME
------------------------------------------------
These panels used to carry invented blue / orange / green ramps, which is not
what any of these layers looks like when you open it. Every single-band layer in
`qgis/wellsight.qgz` is rendered **singleband gray**, stretched to the whole
raster's min and max, and the only layer with colour in it is RRIM, which is a
3-band composite shown as raw RGB with NoEnhancement.

So the styling is now READ OUT OF THE PROJECT FILE at build time. For a layer the
project styles, the panel uses that layer's exact gradient and min/max, so the
picture matches what is on screen. For a layer the project does not contain, the
same convention is applied -- gray, black to white, whole-raster min/max.

The gradients are not uniform and that matters: `openness_pos` is WhiteToBlack
while `openness_neg`, `slope`, `lrm` and `hillshade` are BlackToWhite. Rendering
them all the same way silently inverts one of them.

A side effect worth stating: greyscale everywhere plus one RGB composite contains
no red/green pair, so this panel satisfies the colourblind rule in CLAUDE.md by
construction.

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

QGZ = ROOT / "qgis" / "wellsight.qgz"

#: (source raster, slug for the filename, plain title). How each one is drawn
#: is read from the QGIS project, not decided here.
PANELS = [
    ("__optical__",             "aerial",        "Aerial imagery"),
    ("hillshade_9t_05.tif",     "hillshade",     "Hillshade"),
    ("dem_9t_05.tif",           "dem",           "Bare-earth elevation"),
    ("slope_9t_05.tif",         "slope",         "Slope"),
    ("lrm_5_9t_05.tif",         "lrm_5",         "Local relief, 5 m"),
    ("lrm_25_9t_05.tif",        "lrm_25",        "Local relief, 25 m"),
    ("tpi_05_9t_05.tif",        "tpi_05",        "Topographic position"),
    ("openness_pos_9t_05.tif",  "openness_pos",  "Openness, positive"),
    ("openness_neg_9t_05.tif",  "openness_neg",  "Openness, negative"),
    ("roughness_11_9t_05.tif",  "roughness_11",  "Roughness"),
    ("rrim_openness_9t_05.tif", "rrim",          "RRIM"),
    ("chm_9t_05.tif",           "chm",           "Canopy height"),
]

#: Layers the project does not hold, mapped to one it styles the same way.
#: Empty on purpose. `lrm_5` used to borrow `lrm_25`, on the reasoning that
#: it is the same product at a different radius. It is not the same RANGE:
#: local relief at 5 m has much the smaller amplitude, so lrm_25's stretch
#: flattened it to a grey square with nothing in it. An unstyled layer in
#: QGIS gets the project-wide convention anyway -- gray, black to white,
#: whole-raster min/max -- which is what `style_for` falls back to.
STYLE_ALIAS = {}


def qgis_styles(qgz=None):
    """Read every raster layer's renderer out of the QGIS project.

    Returns {layer stem: style dict}. A .qgz is a zip holding one .qgs, which is
    plain XML, so this needs nothing installed.
    """
    import zipfile
    import xml.etree.ElementTree as ET
    qgz = qgz or QGZ
    if not qgz.exists():
        print(f"  no QGIS project at {qgz}; falling back to gray min/max")
        return {}
    with zipfile.ZipFile(qgz) as z:
        name = [n for n in z.namelist() if n.endswith(".qgs")][0]
        xml = z.read(name).decode("utf-8", "replace")
    out = {}
    for ml in ET.fromstring(xml).iter("maplayer"):
        if ml.get("type") != "raster":
            continue
        stem = (ml.findtext("layername") or "").strip()
        r = ml.find(".//rasterrenderer")
        if r is None or stem in out:
            continue
        kind = r.get("type")
        if kind == "singlebandgray":
            ce = r.find("contrastEnhancement")
            try:
                lo = float(ce.findtext("minValue"))
                hi = float(ce.findtext("maxValue"))
            except (AttributeError, TypeError, ValueError):
                lo = hi = None
            out[stem] = dict(kind="gray", gradient=r.get("gradient",
                                                         "BlackToWhite"),
                             vmin=lo, vmax=hi)
        elif kind == "multibandcolor":
            bands = {}
            for c, tag in (("r", "redContrastEnhancement"),
                           ("g", "greenContrastEnhancement"),
                           ("b", "blueContrastEnhancement")):
                ce = r.find(tag)
                if ce is None:
                    continue
                bands[c] = (ce.findtext("algorithm"),
                            float(ce.findtext("minValue") or 0),
                            float(ce.findtext("maxValue") or 255))
            out[stem] = dict(kind="rgb", bands=bands)
    return out


def style_for(stem, styles, path):
    """The style QGIS would use, or the project's convention if it has none."""
    key = STYLE_ALIAS.get(stem, stem)
    st = styles.get(key)
    if st is not None:
        return dict(st, source=("project" if key == stem
                                else f"project, via {key}"))
    # Same convention every single-band layer in the project uses, with the
    # min/max taken over the WHOLE raster -- QGIS stretches on the full extent,
    # not on whatever window happens to be on screen.
    with rasterio.open(path) as ds:
        st_ = ds.statistics(1, approx=True)
        lo, hi = float(st_.min), float(st_.max)
    return dict(kind="gray", gradient="BlackToWhite", vmin=lo, vmax=hi,
                source="convention")


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


#: NoData paint. Without this, matplotlib leaves NaN as the axes facecolor
#: (SURFACE, near white), which on a BlackToWhite ramp is BRIGHTER THAN vmax --
#: a hole renders as the tallest thing in the panel. That is what made the
#: NoData bands in `chm_300m_9t.png` read as canopy. Any raster with holes was
#: affected, not just the CHM.
#:
#: A greyscale panel contains no green, so the red/green prohibition is not the
#: binding constraint; the binding constraint is that this colour must not read
#: as a grey LEVEL under any vision. Measured, not eyed, with
#: `tools/check_nodata_colour_vs_gray_ramp.py` against 11 ramp steps:
#:   #D97706  worst dE 27.8 (protan vs #808080); normal 32.7, deutan 29.7,
#:            tritan 33.2. Chosen for the margin -- the runner-up #A31515 sits
#:            at 16.6 protan, barely over the floor of 15.
#:   Rejected: #E5007D, the instinctive magenta, FAILS at dE 5.1 deutan against
#:            mid grey. #00C2D4 fails at 12.1 protan.
#: Second encoding: every panel with holes gets the legend patch below, so the
#: category is never carried by colour alone.
NODATA_RGB = "#D97706"


def draw_gray(ax, a, st, ext):
    """Singleband gray, exactly as QGIS draws it, with NoData painted."""
    import matplotlib as mpl
    base = "gray" if st["gradient"] == "BlackToWhite" else "gray_r"
    cmap = mpl.colormaps[base].with_extremes(bad=NODATA_RGB)
    ax.imshow(np.ma.masked_invalid(a), extent=ext, origin="upper", cmap=cmap,
              vmin=st["vmin"], vmax=st["vmax"], interpolation="nearest")


def nodata_legend(ax, a):
    """Label the holes, so NoData is never carried by colour alone."""
    frac = float(np.mean(~np.isfinite(a)))
    if frac <= 0.0:
        return 0.0
    from matplotlib.patches import Patch
    lg = ax.legend(
        handles=[Patch(facecolor=NODATA_RGB, edgecolor="none",
                       label=f"no data  {100*frac:.1f}%")],
        loc="lower right", frameon=True, fontsize=10, handlelength=1.2,
        borderpad=0.5)
    lg.get_frame().set_facecolor("#ffffff")
    lg.get_frame().set_edgecolor("#c8c8c0")
    lg.set_zorder(10)
    return frac


def draw_rgb(ax, arr, st, ext):
    """Multiband colour. RRIM is stored 0-255 and QGIS applies NoEnhancement,
    so the bytes go to screen untouched -- no percentile stretch of our own."""
    a = arr[:3].astype("float32")
    bands = st.get("bands") or {}
    for i, c in enumerate("rgb"):
        alg, lo, hi = bands.get(c, ("NoEnhancement", 0.0, 255.0))
        if alg == "NoEnhancement":
            lo, hi = 0.0, 255.0
        a[i] = (a[i] - lo) / max(hi - lo, 1e-9)
    ax.imshow(np.clip(np.moveaxis(a, 0, -1), 0, 1), extent=ext,
              origin="upper", interpolation="nearest")


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
    outdir = OUT
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

    styles = qgis_styles()
    print(f"read {len(styles)} styled raster layers from {QGZ.name}\n")

    for fname, slug, title in PANELS:
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
                st = style_for(src.stem, styles, src)
                if st["kind"] == "rgb" and arr.ndim == 3 and arr.shape[0] >= 3:
                    draw_rgb(ax, arr, st, ext)
                    print(f"  {slug:14s} RGB, no enhancement      "
                          f"({st['source']})")
                else:
                    a = arr[0] if arr.ndim == 3 else arr
                    if st.get("vmin") is None:
                        v = a[np.isfinite(a)]
                        st = dict(st, vmin=float(v.min()), vmax=float(v.max()))
                    nd = float(np.mean(~np.isfinite(a)))
                    print(f"  {slug:14s} gray {st['gradient']:12s} "
                          f"{st['vmin']:.3g} to {st['vmax']:.3g}  "
                          f"nodata {100*nd:5.2f}%  ({st['source']})")
                    draw_gray(ax, a, st, ext)
                    nodata_legend(ax, a)
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

        name = f"{slug}_{SIDE_M:.0f}m_9t.png"
        fig.savefig(outdir / name, dpi=200)
        plt.close(fig)
        kb = (outdir / name).stat().st_size / 1e3
        written.append(name)
        print(f"  {kb:7.0f} KB  {name}")

    print(f"\n{len(written)} images in {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
