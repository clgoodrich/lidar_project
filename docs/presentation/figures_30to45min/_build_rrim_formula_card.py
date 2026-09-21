"""How RRIM is built -- one card, with the real inputs and the real constants.

Everything here is read out of `notebooks/wellsight_v2/s1_build/_make_rrim.py`,
not out of the paper, so the card describes what this project actually computes.
The thumbnails come from the same 300 m Venango window as the annotation series,
so the card and the maps agree.

THE INPUT THUMBNAILS ARE DRAWN THE WAY QGIS DRAWS THEM
------------------------------------------------------
Openness and slope used to be shown here on invented green and orange ramps.
Two problems with that. They are not what those layers look like when opened,
which is the same defect `_build_derivative_panel.py` was fixed for; and a
green ramp beside an orange-red ramp, each carrying a different meaning, is
precisely the pair the colourblind rule in CLAUDE.md forbids. All three inputs
are now greyscale, read from `qgis/wellsight.qgz` through that module's
`qgis_styles`, so this card and the derivative panels agree with the screen and
with each other.

The RRIM panel is likewise raw bytes now. `rrim_openness_9t_05` is
multibandcolor with NoEnhancement in the project, and this card was applying a
2-98 percentile stretch of its own on top.

COLOUR THAT STAYS, AND WHY
--------------------------
The two ramp swatches keep the real RRIM constants, because they ARE the
algorithm -- teal/grey/yellow diverging about zero, white to red for slope.
The dataviz validator scores teal against grey at dE 4.2 deutan, but it is
scoring them as a categorical palette and they are not one: they are adjacent
stops of a diverging ramp, where being close together at the midpoint is the
ramp working. Neither ramp is read by colour alone -- both carry numeric ticks.
There is no green anywhere on the card, so there is no red/green pair.

Reference (already in literature/CITATIONS.md, PDFs in literature/papers/):
    Chiba, T., Kaneta, S., Suzuki, Y. (2008). "Red Relief Image Map: New
    Visualization Method for Three-Dimensional Data." Int. Archives of
    Photogrammetry, Remote Sensing and Spatial Information Sciences 37(B2):
    1071-1076.
    Openness itself is Yokoyama, Shirasawa & Pike (2002), PE&RS 68(3): 257-265.

Run:
    python docs/presentation/figures_30to45min/_build_rrim_formula_card.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _build_derivative_panel import qgis_styles, style_for   # noqa: E402

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D05 = ROOT / "data" / "9t" / "derived" / "05"
#: terrain layers moved to the 1 m stack; D05 still holds the 0.5 m split
#: bookkeeping and model inputs, which have no 1 m twin
D05_1M = ROOT / "data" / "9t" / "derived" / "1m"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "2_terrain_derivatives"

LAT, LON = 41.49264, -79.546127
SIDE_M = 300.0
EPSG = 6346

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"
#: The step numbers take the card's own subject colour, RRIM's slope red,
#: rather than the orange of the invented ramp that used to sit above them.
ACCENT = "#b62700"

# The exact constants from _make_rrim.py -- if that file changes, change these.
TEAL = np.array([0, 158, 162], float)
GRAY = np.array([138, 138, 138], float)
YELLOW = np.array([254, 255, 172], float)
WHITE = np.array([255, 255, 255], float)
RED = np.array([182, 39, 0], float)
SLOPE_HI = 40.0
DO_PCT = 98.0
BASE_BRIGHTNESS = 18.0


def target_xy():
    from pyproj import Transformer
    return Transformer.from_crs(4326, EPSG, always_xy=True).transform(LON, LAT)


def bounds():
    x, y = target_xy()
    h = SIDE_M / 2
    return (x - h, y - h, x + h, y + h)


def read(name, bb):
    with rasterio.open((D05_1M if name.endswith('_1m.tif') else D05)
                       / name) as r:
        w = from_bounds(*bb, transform=r.transform)
        a = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
    return a[0] if a.ndim == 3 else a


def thumb(ax, arr, title, cmap=None, sym=False, st=None):
    """One input, either QGIS-styled greyscale (st) or an explicit ramp."""
    if st is not None:
        cmap = "gray" if st["gradient"] == "BlackToWhite" else "gray_r"
        vmin, vmax = st["vmin"], st["vmax"]
    else:
        v = arr[np.isfinite(arr)]
        if sym:
            m = np.percentile(np.abs(v), 98)
            vmin, vmax = -m, m
        else:
            vmin, vmax = np.percentile(v, 2), np.percentile(v, 98)
    ax.imshow(arr, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.set_title(title, fontsize=11, fontweight="bold", loc="left", pad=5,
                 color=INK)


def ramp(ax, stops, label, ticks):
    """A horizontal colour bar built from the same stops the code uses."""
    grad = np.linspace(0, 1, 512)[None, :]
    cm = LinearSegmentedColormap.from_list("r", [c / 255 for c in stops])
    ax.imshow(grad, aspect="auto", cmap=cm, extent=[0, 1, 0, 1])
    ax.set_yticks([])
    ax.set_xticks([t[0] for t in ticks])
    ax.set_xticklabels([t[1] for t in ticks], fontsize=9, color=INK2)
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.set_title(label, fontsize=10.5, fontweight="bold", loc="left", pad=4,
                 color=INK)


def main() -> int:
    bb = bounds()
    op = read("openness_pos_9t_1m.tif", bb)
    on = read("openness_neg_9t_1m.tif", bb)
    slope = read("slope_9t_1m.tif", bb)
    do = (op - on) / 2.0
    dlim = float(np.nanpercentile(np.abs(do[np.isfinite(do)]), DO_PCT))

    with rasterio.open(D05_1M / "rrim_openness_9t_1m.tif") as r:
        w = from_bounds(*bb, transform=r.transform)
        rr = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")[:3]
    # NoEnhancement in the QGIS project: the stored bytes go straight to screen.
    rrim = np.clip(np.moveaxis(rr / 255.0, 0, -1), 0, 1)

    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })
    fig = plt.figure(figsize=(12.6, 7.2))
    gs = fig.add_gridspec(2, 4, height_ratios=[1.0, 1.15],
                          width_ratios=[1, 1, 1, 1.25],
                          hspace=0.26, wspace=0.22,
                          left=0.045, right=0.965, top=0.845, bottom=0.175)

    CM_D = LinearSegmentedColormap.from_list(
        "d", [TEAL / 255, GRAY / 255, YELLOW / 255])

    # The three real rasters are drawn the way the QGIS project draws them.
    # D is an intermediate that exists only inside _make_rrim.py, so it has no
    # project style; it wears the base ramp it feeds, which is the point of it.
    styles = qgis_styles()
    for ax_, arr, stem, title in (
            (fig.add_subplot(gs[0, 0]), op, "openness_pos_9t_05",
             "\u03a6  positive openness"),
            (fig.add_subplot(gs[0, 1]), on, "openness_neg_9t_05",
             "\u03a8  negative openness"),
            (fig.add_subplot(gs[0, 2]), slope, "slope_9t_05", "S  slope")):
        st = style_for(stem, styles, D05_1M / f"{stem}.tif")
        print(f"  {stem:22s} gray {st['gradient']} "
              f"{st['vmin']:.4g} to {st['vmax']:.4g}  ({st['source']})")
        thumb(ax_, arr, title, st=st)
    thumb(fig.add_subplot(gs[0, 3]), do, "D  differential openness", CM_D, sym=True)

    # --- the maths, as it is actually coded -----------------------------------
    ax = fig.add_subplot(gs[1, 0:2])
    ax.axis("off")
    lines = [
        ("1", "Differential openness", r"$D = (\Phi - \Psi)\,/\,2$"),
        ("2", f"Normalise, clipped at the {DO_PCT:.0f}th percentile of |D|",
         r"$t = \mathrm{clip}(D / d_{lim},\ -1,\ +1)$"),
        ("3", "Base colour, diverging about zero",
         r"$B = \mathrm{ramp}(t)\ +\ 18$"),
        ("4", f"Slope ramp, saturating at {SLOPE_HI:.0f}$\\degree$",
         r"$u = \mathrm{clip}(S / 40,\ 0,\ 1)$"),
        ("5", "Red overlay", r"$R = W + (R_{max} - W)\,u$"),
        ("6", "Multiply blend", r"$\mathbf{RRIM} = B \times R \,/\, 255$"),
    ]
    y = 0.97
    for num, words, formula in lines:
        ax.text(0.0, y, num, fontsize=11, fontweight="bold", color=ACCENT,
                va="top")
        ax.text(0.045, y, words, fontsize=10.5, color=INK2, va="top")
        ax.text(0.045, y - 0.075, formula, fontsize=13, color=INK, va="top")
        y -= 0.168
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)

    # --- the two ramps --------------------------------------------------------
    ramp(fig.add_subplot(gs[1, 2].subgridspec(2, 1, hspace=0.95)[0]),
         [TEAL, GRAY, YELLOW], "Base: concave \u2192 flat \u2192 convex",
         [(0.0, f"\u2212{dlim:.1f}\u00b0"), (0.5, "0"), (1.0, f"+{dlim:.1f}\u00b0")])
    ramp(fig.add_subplot(gs[1, 2].subgridspec(2, 1, hspace=0.95)[1]),
         [WHITE, RED], "Overlay: slope",
         [(0.0, "0\u00b0"), (1.0, f"{SLOPE_HI:.0f}\u00b0+")])

    ax = fig.add_subplot(gs[1, 3])
    ax.imshow(rrim)
    ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)
    ax.set_title("=  RRIM", fontsize=12, fontweight="bold", loc="left", pad=5)

    fig.text(0.045, 0.965, "How Red Relief Image Map is built",
             fontsize=18, fontweight="bold", va="top", color=INK)
    fig.text(0.045, 0.905,
             "Concave and convex read at once, with no lighting direction to hide "
             "behind \u2014 which is why a pit is visible from any aspect.",
             fontsize=11.5, color=INK2, va="top")
    fig.text(0.045, 0.125,
             "Chiba, T., Kaneta, S. & Suzuki, Y. (2008). Red Relief Image Map: New "
             "Visualization Method for Three-Dimensional Data.\n"
             "International Archives of Photogrammetry, Remote Sensing and Spatial "
             "Information Sciences 37(B2): 1071\u20131076.",
             fontsize=9.5, color=INK2, va="top")

    out = OUT / "rrim_formula_card.png"
    fig.savefig(out, dpi=200)
    plt.close(fig)
    print(f"d_lim = {dlim:.2f} deg")
    print(f"wrote {out}  ({out.stat().st_size/1e3:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
