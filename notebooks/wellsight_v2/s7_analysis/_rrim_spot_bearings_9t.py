"""The RRIM at one spot, with candidate bearings drawn over it.

WHY DRAW INSTEAD OF MEASURE AGAIN
---------------------------------
Two readings of the same picture disagree. By eye the streaks run "the same way
as the corn rows, ENE or WNW". A 1 degree bearing sweep at 41.496597,
-79.516534 puts the RRIM's grain at 117 degrees with essentially nothing at 78:

    RRIM  0.5 m   peak 117 deg  x5.23    at 78 deg  x0.99
    slope 0.5 m   peak 117 deg  x6.02    at 78 deg  x0.53
    op_neg 0.5 m  peak 113 deg  x4.83    at 78 deg  x1.06

117 degrees IS west-north-west to east-south-east, so "WNW" and the sweep agree
about the direction. What they disagree about is whether it is the SAME family
as the corn rows, which lie at 78 -- 39 degrees away.

Another sweep will not settle that. Reference lines drawn on the image at each
candidate will, because the reader can lay them against the streaks.

WHAT IS DRAWN
-------------
  78 deg    the corn rows, from the NoData mask
  117 deg   what the sweep finds here
  176 deg   the flight lines
Each as a family of parallel guides across the whole crop, at both resolutions.

AND A CONTROL. The bottom row is the DSM over the same ground with the same
guides. Its corn rows are known to be at 78, so if the 78 guide does not line up
with the DSM's stripes the guides themselves are wrong and nothing above them
means anything.

Run:
    python notebooks/wellsight_v2/s7_analysis/_rrim_spot_bearings_9t.py
    ... --lat 41.496597 --lon -79.516534 --side 150
Writes:
    docs/presentation/figures_30to45min/v6/rrim_spot_bearings_9t.png
"""
from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

#: Guides. Grey for across-track because it is context, not a candidate; the
#: two real candidates get the validated lost/found pair, dE 21.1 deutan.
GUIDES = [
    (78.0, "#D97706", "78°  corn rows, from the NoData mask"),
    (117.0, "#1F5FA8", "117°  what the sweep finds here"),
    (176.0, "#8E959B", "176°  the flight lines"),
]
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"

PANELS = [
    ("RRIM, 0.5 m", "data/9t/derived/05/rrim_openness_9t_05.tif", True),
    ("RRIM, 1 m", "data/9t/derived/1m/rrim_openness_9t_1m.tif", True),
    ("DSM, 0.5 m — control, its stripes ARE the corn rows",
     "data/9t/derived/05/dsm_9t_05.tif", False),
]


def read(path, b, rgb):
    with rasterio.open(path) as r:
        a = r.read(window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
    if rgb:
        return np.moveaxis(np.nan_to_num(a[:3], nan=255).astype("uint8"), 0, -1)
    g = a[0]
    g[g < -1e6] = np.nan
    return g


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=41.496597)
    ap.add_argument("--lon", type=float, default=-79.516534)
    ap.add_argument("--side", type=float, default=150.0)
    a = ap.parse_args()

    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    cx, cy = tr.transform(a.lon, a.lat)
    h = a.side / 2.0
    b = (cx - h, cy - h, cx + h, cy + h)
    print(f"{a.lat}, {a.lon}  ->  {cx:.1f} E {cy:.1f} N   {a.side:.0f} m window")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from importlib.machinery import SourceFileLoader
    mm = SourceFileLoader("mm", str(Path(__file__).resolve().parent
                                    / "_rrim_grain_bearing_9t.py")).load_module()

    fig, axes = plt.subplots(2, len(PANELS),
                             figsize=(4.9 * len(PANELS), 9.6),
                             gridspec_kw=dict(height_ratios=[1.45, 1.0]))
    fig.patch.set_facecolor(PAPER)
    brgs = np.arange(0.0, 180.0, 1.0)

    for col, (name, rel, rgb) in enumerate(PANELS):
        img = read(ROOT / rel, b, rgb)
        with rasterio.open(ROOT / rel) as r:
            res = abs(r.transform.a)

        # ---- the crop, clean. Guides over the picture hid the thing they
        # were meant to point at, so the answer moved to the curve below.
        ax = axes[0][col]
        if rgb:
            ax.imshow(img, interpolation="nearest")
        else:
            cmap = matplotlib.colormaps["gray"].with_extremes(bad="#D97706")
            ax.imshow(np.ma.masked_invalid(img), cmap=cmap,
                      vmin=np.nanpercentile(img, 2),
                      vmax=np.nanpercentile(img, 98),
                      interpolation="nearest")
        n = img.shape[0]
        # one short guide per candidate, in the corner, out of the way
        for k, (brg, colr, _) in enumerate(GUIDES):
            t = np.radians(brg)
            dx, dy = np.sin(t), -np.cos(t)
            x0, y0 = n * 0.14, n * (0.80 + 0.055 * k)
            L = n * 0.11
            ax.plot([x0 - dx * L, x0 + dx * L], [y0 - dy * L, y0 + dy * L],
                    color=colr, lw=3.0, solid_capstyle="round", zorder=6)
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_edgecolor("#c8c8c0")
        ax.set_title(name, loc="left", fontsize=13, fontweight="bold",
                     color=INK)

        # ---- power against bearing: the part that is not a judgement call
        g = img
        if rgb:
            g = (0.299 * img[..., 0] + 0.587 * img[..., 1]
                 + 0.114 * img[..., 2]).astype("float32")
        sc = np.array([mm.power(g, bg, res) for bg in brgs])
        med = np.nanmedian(sc)
        rel_sc = sc / med
        ax = axes[1][col]
        ax.plot(brgs, rel_sc, color=INK, lw=2.0, zorder=4)
        ax.axhline(1.0, color="#c8c8c0", lw=1.2, zorder=1)
        for brg, colr, _ in GUIDES:
            ax.axvline(brg, color=colr, lw=2.2, alpha=0.9, zorder=2)
            ax.text(brg, ax.get_ylim()[1], f" {brg:.0f}°", color=colr,
                    fontsize=11, fontweight="bold", va="top", rotation=90)
        pk = int(np.nanargmax(rel_sc))
        ax.plot([brgs[pk]], [rel_sc[pk]], "o", color="#A31515", ms=8, zorder=5)
        ax.annotate(f"peak {brgs[pk]:.0f}°  ×{rel_sc[pk]:.1f}",
                    xy=(brgs[pk], rel_sc[pk]),
                    xytext=(8, -4), textcoords="offset points",
                    fontsize=12, fontweight="bold", color="#A31515")
        ax.set_xlim(0, 180)
        ax.set_xticks([0, 45, 90, 135, 180])
        ax.set_xlabel("bearing the lines would run, degrees",
                      fontsize=11, color=MUTED)
        if col == 0:
            ax.set_ylabel("power, relative to\nthe median bearing",
                          fontsize=11, color=MUTED)
        ax.grid(axis="y", color="#e6e6de", lw=0.9)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_edgecolor("#c8c8c0")

    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([], [], color=c, lw=2.8, label=l)
                        for _, c, l in GUIDES],
               loc="lower center", ncol=3, frameon=False, fontsize=12)
    fig.suptitle("Which way does the grain run here?",
                 x=0.012, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    fig.text(0.012, 0.945,
             f"{a.lat:.6f}, {a.lon:.6f}  ·  {cx:.0f} E {cy:.0f} N  "
             f"·  {a.side:.0f} m across  ·  "
             "the DSM is the control — its stripes ARE the corn rows, "
             "so its curve must peak at 78°",
             fontsize=12, color=MUTED)
    fig.tight_layout(rect=(0, 0.045, 1, 0.925))
    FIG.mkdir(parents=True, exist_ok=True)
    out = FIG / "rrim_spot_bearings_9t.png"
    fig.savefig(out, dpi=155, facecolor=PAPER)
    plt.close(fig)
    print(f"  {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
