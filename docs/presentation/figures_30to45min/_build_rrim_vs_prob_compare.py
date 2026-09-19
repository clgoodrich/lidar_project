"""RRIM beside the probability surface, on ground the model actually committed to.

Side-by-side panels: what the terrain looks like, and what the model made of it.
Windows are chosen by probability density, not by eye -- for each task, the
window holding the most high-probability pixels.

Runs on both tiles:
    9t       the tile the models trained on
    613590   a tile they never saw

WHY PICK THE WINDOW BY DENSITY
------------------------------
Choosing a window because it looks good is how a figure stops being evidence.
The search below bins pixels above the operating threshold and takes the
densest box, so the crop is reproducible and the same rule applies to both
tiles. It is still a best case -- say so on the slide -- but it is a best case
found by a rule rather than by taste.

Run:
    python docs/presentation/figures_30to45min/_build_rrim_vs_prob_compare.py
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

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _figure_style import CM_PROB, read_rrim   # noqa: E402

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OUT = ROOT / "docs" / "presentation" / "figures_30to45min" / "5_probability_surfaces"

SIDE_M = 400.0
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#8a887e"
RULE = "#d8d7cf"

#: The probability ramp, and how RRIM is drawn, are shared with every other
#: figure now -- see _figure_style.py for why both were wrong here.
CM = CM_PROB

#: Where the feature stack has no data the network still emits a probability --
#: around 0.5, which is above every operating threshold. Those pixels are not
#: detections and a density search walks straight into them, so every window is
#: required to be almost entirely valid ground.
#: The validity raster is per resolution as well as per tile: the 0.5 m models
#: and the 1 m models sit on different grids.
VALID = {
    ("9t", 0.5): ROOT / "data/9t/derived/05/features_pit_9t_05.tif",
    ("9t", 1.0): ROOT / "data/9t/derived/05/features_pit_9t_1m.tif",
    ("613590", 0.5): ROOT / "data/613590/derived/inference_05/features_613590_05.tif",
    ("613590", 1.0): ROOT / "data/westernpa_d20/613590/derived/1m/features_613590_1m.tif",
}

RRIM = {
    "9t": ROOT / "data/9t/derived/05/rrim_openness_9t_05.tif",
    "613590": ROOT / "data/613590/derived/05/rrim_openness_613590_05.tif",
}

#: (tile, task, probability raster, operating threshold, grid resolution)
#:
#: Road uses unet_1m_recall on BOTH tiles on purpose. unet_1m_corrected scores
#: better on 613590 and was fine-tuned on 613590 corrections, so quoting it as
#: out-of-domain would be false. recall never saw the tile.
CASES = [
    ("9t", "pit",
     ROOT / "data/9t/models/pit/unet_v2/pit_prob_floor.tif", 0.20, 0.5),
    ("9t", "pad",
     ROOT / "data/9t/models/pad/unet/pad_prob.tif", 0.45, 0.5),
    ("9t", "road",
     ROOT / "data/9t/models/road/unet_1m_recall/road_prob.tif", 0.20, 1.0),
    ("9t", "drainage",
     ROOT / "data/9t/models/drainage/unet_1m/drainage_prob.tif", 0.50, 1.0),
    ("613590", "pit",
     ROOT / "data/613590/derived/inference_05/pit_prob_floor_613590_05.tif",
     0.20, 0.5),
    ("613590", "pad",
     ROOT / "data/613590/derived/inference_05/pad_prob_613590_05.tif", 0.45, 0.5),
    ("613590", "road",
     ROOT / "data/9t/models/road/unet_1m_recall/road_prob_613590_1m.tif",
     0.20, 1.0),
    ("613590", "drainage",
     ROOT / "data/9t/models/drainage/unet_1m/drainage_prob_613590_1m.tif",
     0.50, 1.0),
]


def valid_mask(feat_path, shape):
    """Coarse finite-data mask from band 1 of the feature stack."""
    with rasterio.open(feat_path) as r:
        a = r.read(1, out_shape=shape).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    return np.isfinite(a)


def densest_window(prob_path, thr, side, feat_path=None, bin_m=25.0,
                   max_px=3000):
    """Box holding the most above-threshold pixels, via a summed-area table.

    Windows that are not at least 99% valid ground are excluded: the network
    emits ~0.5 over nodata, which outscores any real cluster.
    """
    with rasterio.open(prob_path) as r:
        b = r.bounds
        f = max(1, int(max(r.width, r.height) / max_px))
        a = r.read(1, out_shape=(r.height // f, r.width // f)).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
        res = r.res[0] * f
    if np.isfinite(a).any() and np.nanmax(a) > 1.5:
        a = a / 255.0
    ok = valid_mask(feat_path, a.shape) if feat_path else np.isfinite(a)
    hot = (np.nan_to_num(a, nan=0.0) >= thr) & ok
    step = max(1, int(bin_m / res))
    # coarsen to bin_m cells, then slide a `side`-wide box over the sums
    ny, nx = hot.shape[0] // step, hot.shape[1] // step
    H = hot[:ny * step, :nx * step].reshape(ny, step, nx, step).sum(axis=(1, 3))
    V = ok[:ny * step, :nx * step].reshape(ny, step, nx, step).sum(axis=(1, 3))
    k = max(1, int(side / bin_m))
    if k >= min(H.shape):
        return (b.left, b.bottom, b.left + side, b.bottom + side), 0
    S = np.pad(H.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    win = S[k:, k:] - S[:-k, k:] - S[k:, :-k] + S[:-k, :-k]
    SV = np.pad(V.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    vwin = SV[k:, k:] - SV[:-k, k:] - SV[k:, :-k] + SV[:-k, :-k]
    win = np.where(vwin >= 0.99 * (k * step) ** 2, win, -1)
    i, j = np.unravel_index(int(np.argmax(win)), win.shape)
    x0 = b.left + j * bin_m
    y0 = b.top - (i + k) * bin_m
    return (x0, y0, x0 + side, y0 + side), int(win[i, j])


def read(path, bb, rgb=False):
    with rasterio.open(path) as r:
        w = from_bounds(*bb, transform=r.transform)
        a = r.read(window=w, boundless=True, fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    if rgb:
        # NoEnhancement in the QGIS project: no stretch of our own.
        return np.clip(np.moveaxis(a[:3] / 255.0, 0, -1), 0, 1)
    a = a[0] if a.ndim == 3 else a
    if np.isfinite(a).any() and np.nanmax(a) > 1.5:
        a = a / 255.0
    return np.clip(a, 0, 1)


def furniture(ax, bb, bar_m=100):
    l, b, r_, t = bb
    side = r_ - l
    x0, y0 = l + side * 0.06, b + side * 0.06
    ax.plot([x0, x0 + bar_m], [y0, y0], color="white", linewidth=5.5,
            solid_capstyle="butt", zorder=12)
    ax.plot([x0, x0 + bar_m], [y0, y0], color=INK, linewidth=2.4,
            solid_capstyle="butt", zorder=13)
    ax.text(x0 + bar_m / 2, y0 + side * 0.028, f"{bar_m:.0f} m", ha="center",
            fontsize=9.5, color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.15", fc="#ffffffdd", ec="none"))
    nx, ny = r_ - side * 0.07, t - side * 0.19
    ax.annotate("", xy=(nx, ny + side * 0.10), xytext=(nx, ny),
                arrowprops=dict(arrowstyle="-|>", color=INK, linewidth=2.4,
                                mutation_scale=18), zorder=13)
    ax.text(nx, ny + side * 0.115, "N", ha="center", va="bottom", fontsize=12,
            fontweight="bold", color=INK, zorder=13,
            bbox=dict(boxstyle="round,pad=0.12", fc="#ffffffdd", ec="none"))


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "font.family": "DejaVu Sans",
        "text.color": INK,
    })

    for tile, task, prob_p, thr, res in CASES:
        rrim_p = RRIM[tile]
        if not rrim_p.exists() or not prob_p.exists():
            print(f"  SKIP {tile}/{task}: "
                  f"{'rrim' if not rrim_p.exists() else 'prob'} missing")
            continue
        bb, n = densest_window(prob_p, thr, SIDE_M,
                               feat_path=VALID.get((tile, res)))
        print(f"  {tile}/{task}: window at {bb[0]:.0f},{bb[1]:.0f} "
              f"holding {n} above-{thr} cells")
        rr = read_rrim(rrim_p, bb)
        pr = read(prob_p, bb)
        ext = [bb[0], bb[2], bb[1], bb[3]]

        fig, axes = plt.subplots(1, 2, figsize=(13.2, 7.2))
        axes[0].imshow(rr, extent=ext, origin="upper")
        axes[0].set_title("RRIM \u2014 the terrain", fontsize=15,
                          fontweight="bold", loc="left", pad=24)
        # Below 0.05 is background. Drawn, it is a flat wash over the whole
        # frame that hides the handful of cells the model actually committed
        # to; masked, the panel shows what was found.
        shown = np.ma.masked_where(~np.isfinite(pr) | (pr < 0.05), pr)
        im = axes[1].imshow(shown, extent=ext, origin="upper", cmap=CM,
                            vmin=0.0, vmax=1.0)
        axes[1].set_title(f"{task} probability \u2014 what the model made of it",
                          fontsize=15, fontweight="bold", loc="left", pad=24)
        for ax in axes:
            ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
            ax.set_aspect("equal")
            ax.set_xticks([]); ax.set_yticks([])
            for sp in ax.spines.values():
                sp.set_color(RULE)
            furniture(ax, bb)

        cb = fig.colorbar(im, ax=axes[1], fraction=0.040, pad=0.015)
        cb.set_label("probability", fontsize=10, color=INK2)
        cb.outline.set_edgecolor(RULE)

        trained = "trained here" if tile == "9t" else "never trained here"
        # This caveat is load-bearing: the crop is a best case by construction,
        # and a reader who does not know that will over-read the figure. It goes
        # at the top, where it cannot be cropped off a slide.
        # These sit on their own line under each bold title. As right-aligned
        # titles they overprinted the titles themselves on every figure.
        axes[1].text(0, 1.006,
                     f"window chosen by density of pixels above {thr:.2f}, "
                     f"not by eye  \u00b7  below 0.05 left blank",
                     transform=axes[1].transAxes, fontsize=10, color=MUTED,
                     va="bottom", ha="left")
        axes[0].text(0, 1.006, f"{tile}  \u00b7  {trained}",
                     transform=axes[0].transAxes, fontsize=10, color=MUTED,
                     va="bottom", ha="left")
        fig.text(0.012, 0.014,
                 "Red Relief Image Map \u00b7 Chiba et al. 2008",
                 fontsize=9, color=MUTED)
        fig.subplots_adjust(left=0.012, right=0.955, top=0.885, bottom=0.048,
                            wspace=0.06)

        name = f"rrim_vs_prob_{task}_{SIDE_M:.0f}m_{tile}.png"
        fig.savefig(OUT / name, dpi=200)
        plt.close(fig)
        print(f"    {(OUT / name).stat().st_size/1e3:7.0f} KB  {name}")

    print(f"\nwrote to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
