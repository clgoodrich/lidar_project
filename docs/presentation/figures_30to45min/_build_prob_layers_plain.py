"""The probability layers, plain.

One image per layer, showing the raster and nothing else: no hillshade beneath,
no annotation on top, no masking. Colour bar, scale bar, north arrow.

Extent is a centred square at half the tile's width -- 2,250 m of the 4,500 m
9t tile -- which is large enough to read as "this is the whole output" while
still resolving individual features.

Sources
-------
    pit       data/9t/models/pit/unet_v2/pit_prob_floor.tif        0.5 m
    pad       data/9t/models/pad/unet/pad_prob.tif                 0.5 m
    road      data/9t/models/road/sweep_202607/cldice/road_prob.tif  1 m
    drainage  data/9t/models/drainage/unet_1m/drainage_prob.tif      1 m

Run:
    python docs/presentation/figures_30to45min/_build_prob_layers_plain.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from matplotlib.colors import LinearSegmentedColormap
from rasterio.windows import from_bounds

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
MODELS = ROOT / "data" / "9t" / "models"
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "5_probability_surfaces"

FRACTION = 0.5          # of the tile's width, centred
MAX_PX = 2600           # cap the read so a 0.5 m layer does not blow memory

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

#: Single hue, light to dark. Probability is a magnitude, so it gets a
#: sequential ramp -- never a rainbow, which would invent thresholds that are
#: not in the data.
CM = LinearSegmentedColormap.from_list("p", ["#fff7ec", "#fdbb84", "#e34a33",
                                            "#7f0000"])

LAYERS = [
    ("pit", "Pit floor probability",
     MODELS / "pit" / "unet_v2" / "pit_prob_floor.tif"),
    ("pad", "Pad probability",
     MODELS / "pad" / "unet" / "pad_prob.tif"),
    ("road", "Road probability",
     MODELS / "road" / "sweep_202607" / "cldice" / "road_prob.tif"),
    ("drainage", "Drainage probability",
     MODELS / "drainage" / "unet_1m" / "drainage_prob.tif"),
]


def centred_window(path, fraction):
    with rasterio.open(path) as r:
        b = r.bounds
    cx, cy = (b.left + b.right) / 2, (b.bottom + b.top) / 2
    half = min(b.right - b.left, b.top - b.bottom) * fraction / 2
    return (cx - half, cy - half, cx + half, cy + half)


def read(path, bb):
    with rasterio.open(path) as r:
        w = from_bounds(*bb, transform=r.transform)
        h, wd = int(w.height), int(w.width)
        f = max(1, int(max(h, wd) / MAX_PX))
        a = r.read(1, window=w, boundless=True, fill_value=np.nan,
                   out_shape=(max(1, h // f), max(1, wd // f))).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
        res = r.res[0]
    if np.isfinite(a).any() and np.nanmax(a) > 1.5:
        a = a / 255.0          # some writers store 0-255
    return np.clip(a, 0, 1), res, f


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })

    for slug, title, path in LAYERS:
        if not path.exists():
            print(f"  MISSING {path}")
            continue
        bb = centred_window(path, FRACTION)
        arr, res, f = read(path, bb)
        ext = [bb[0], bb[2], bb[1], bb[3]]
        side = bb[2] - bb[0]

        fig, ax = plt.subplots(figsize=(8.6, 8.9))
        im = ax.imshow(arr, extent=ext, origin="upper", cmap=CM,
                       vmin=0.0, vmax=1.0, interpolation="nearest")
        ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
        ax.set_aspect("equal")
        ax.set_xticks([]); ax.set_yticks([])
        for sp in ax.spines.values():
            sp.set_color(RULE)

        # scale bar -- 500 m reads well against a ~2.2 km frame
        l, b, r_, t = bb
        bar = 500.0
        x0, y0 = l + side * 0.05, b + side * 0.05
        ax.plot([x0, x0 + bar], [y0, y0], color="white", linewidth=6,
                solid_capstyle="butt", zorder=12)
        ax.plot([x0, x0 + bar], [y0, y0], color=INK, linewidth=2.6,
                solid_capstyle="butt", zorder=13)
        ax.text(x0 + bar / 2, y0 + side * 0.019, f"{bar:.0f} m", ha="center",
                fontsize=10.5, color=INK, zorder=13,
                bbox=dict(boxstyle="round,pad=0.16", fc="#ffffffdd", ec="none"))

        nx, ny = r_ - side * 0.055, t - side * 0.155
        ax.annotate("", xy=(nx, ny + side * 0.085), xytext=(nx, ny),
                    arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.6,
                                    mutation_scale=19), zorder=13)
        ax.text(nx, ny + side * 0.095, "N", ha="center", va="bottom",
                fontsize=13, fontweight="bold", color=INK, zorder=13,
                bbox=dict(boxstyle="round,pad=0.13", fc="#ffffffdd", ec="none"))

        cb = fig.colorbar(im, ax=ax, fraction=0.040, pad=0.018)
        cb.set_label("probability", fontsize=11, color=INK2)
        cb.set_ticks([0, 0.2, 0.4, 0.6, 0.8, 1.0])
        cb.outline.set_edgecolor(RULE)

        ax.set_title(title, fontsize=18, fontweight="bold", loc="left", pad=11)
        fig.subplots_adjust(left=0.02, right=0.90, top=0.93, bottom=0.030)

        name = f"prob_{slug}_9t.png"
        fig.savefig(OUT / name, dpi=200)
        plt.close(fig)
        print(f"  {(OUT / name).stat().st_size/1e3:7.0f} KB  {name}"
              f"   {arr.shape[1]}x{arr.shape[0]} px shown, max p {np.nanmax(arr):.2f}")

    print(f"\nwrote to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
