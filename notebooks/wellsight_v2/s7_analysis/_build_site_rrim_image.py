"""A plain RRIM image of any coordinate, with a scale bar and a north arrow.

Point it at a latitude and longitude, say how wide you want the square, and it
finds whichever RRIM raster covers that spot, crops it, and writes a figure plus
a georeferenced GeoTIFF of the same extent.

No overlays, no annotation, no model output -- just the terrain, a scale bar, a
north arrow, and a footer saying where it is and what it came from.

Pixels are drawn with nearest-neighbour interpolation on purpose. The crop is
displayed larger than its native pixel count, and smoothing it would invent
detail the lidar never recorded.

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_site_rrim_image.py
    ... --lat 41.484384 --lon -79.518911 --side 200
    ... --lat 41.484384 --lon -79.518911 --side 400 --bar 100
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from pyproj import Transformer
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
OUTROOT = ROOT / "docs" / "presentation" / "figures_30to45min"

SURFACE, INK, INK2, MUTED, RULE = "#fcfcfb", "#0b0b0b", "#52514e", "#8a887e", "#d8d7cf"

#: every RRIM in the repo, finest resolution first so a 0.5 m product wins
#: over a 1 m one covering the same ground
RRIM_GLOB = "data/**/rrim*.tif"


def covering_rasters(x, y):
    hits = []
    for p in sorted(ROOT.glob(RRIM_GLOB)):
        try:
            with rasterio.open(p) as r:
                b = r.bounds
                if b.left <= x <= b.right and b.bottom <= y <= b.top:
                    hits.append((r.res[0], p))
        except rasterio.RasterioIOError:
            continue
    return sorted(hits)


def nice_bar(side):
    """A round scale-bar length that is roughly a quarter of the frame."""
    for v in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000):
        if v >= side / 4:
            return float(v)
    return float(side / 4)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--side", type=float, default=200.0, help="square width, m")
    ap.add_argument("--bar", type=float, default=0.0, help="scale bar, m; 0 = auto")
    ap.add_argument("--src", help="force a particular RRIM raster")
    ap.add_argument("--epsg", default="EPSG:6346")
    args = ap.parse_args()

    x, y = Transformer.from_crs("EPSG:4326", args.epsg, always_xy=True).transform(
        args.lon, args.lat)
    print(f"{args.lat}, {args.lon}  ->  {x:.1f} E, {y:.1f} N  ({args.epsg})")

    if args.src:
        src, res = Path(args.src), None
    else:
        hits = covering_rasters(x, y)
        if not hits:
            raise SystemExit(f"no RRIM raster covers {x:.1f}, {y:.1f}")
        for r_, p in hits:
            print(f"  candidate  {r_:g} m  {p.relative_to(ROOT)}")
        res, src = hits[0]
        print(f"  using      {src.relative_to(ROOT)}")

    half = args.side / 2
    bb = (x - half, y - half, x + half, y + half)
    with rasterio.open(src) as r:
        w = from_bounds(*bb, transform=r.transform)
        a = r.read([1, 2, 3], window=w, boundless=True, fill_value=255)
        res = r.res[0]
        prof = dict(r.profile)
        prof.update(height=a.shape[1], width=a.shape[2], count=3, dtype="uint8",
                    transform=r.window_transform(w), compress="deflate")
    a = np.clip(a, 0, 255).astype("uint8")
    img = np.moveaxis(a, 0, -1)
    print(f"  {a.shape[2]} x {a.shape[1]} px at {res:g} m native")

    lat_s = f"{abs(args.lat):.6f}".replace(".", "p") + ("N" if args.lat >= 0 else "S")
    lon_s = f"{abs(args.lon):.6f}".replace(".", "p") + ("W" if args.lon < 0 else "E")
    out = OUTROOT / f"venango_site_{lat_s}_{lon_s}"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"rrim_{args.side:.0f}m_{lat_s}_{lon_s}_{src.stem.split('_')[-2]}_" \
           f"{str(res).replace('.', 'p').rstrip('p0') or '0p5'}"
    stem = f"rrim_{args.side:.0f}m_{lat_s}_{lon_s}"

    tif = out / f"{stem}.tif"
    with rasterio.open(tif, "w", **prof) as ds:
        ds.write(a)

    # ---- the figure ------------------------------------------------------
    plt.rcParams.update({"figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig, ax = plt.subplots(figsize=(8.6, 9.05))
    ext = [bb[0], bb[2], bb[1], bb[3]]
    ax.imshow(img, extent=ext, origin="upper", interpolation="nearest")
    ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    ax.set_aspect("equal"); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values():
        sp.set_color(RULE)

    bar = args.bar or nice_bar(args.side)
    bx, by = bb[0] + args.side * 0.06, bb[1] + args.side * 0.06
    ax.plot([bx, bx + bar], [by, by], color="white", linewidth=6.5,
            solid_capstyle="butt", zorder=12)
    ax.plot([bx, bx + bar], [by, by], color=INK, linewidth=2.8,
            solid_capstyle="butt", zorder=13)
    for xv in (bx, bx + bar):
        ax.plot([xv, xv], [by - args.side * 0.009, by + args.side * 0.009],
                color=INK, linewidth=2.8, zorder=13)
    ax.text(bx + bar / 2, by + args.side * 0.022, f"{bar:.0f} m", ha="center",
            fontsize=11, color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.16", fc="#ffffffdd", ec="none"))

    nx, ny = bb[2] - args.side * 0.075, bb[3] - args.side * 0.20
    ax.annotate("", xy=(nx, ny + args.side * 0.105), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.8,
                                mutation_scale=20), zorder=13)
    ax.text(nx, ny + args.side * 0.118, "N", ha="center", va="bottom",
            fontsize=14, fontweight="bold", color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.13", fc="#ffffffdd", ec="none"))

    fig.text(0.021, 0.016, "Red Relief Image Map · Chiba et al. 2008",
             fontsize=9, color=MUTED)
    fig.subplots_adjust(left=0.021, right=0.979, top=0.986, bottom=0.048)

    png = out / f"{stem}_scaled.png"
    fig.savefig(png, dpi=200)
    plt.close(fig)

    print(f"\n{png}")
    print(tif)
    return 0


if __name__ == "__main__":
    sys.exit(main())
