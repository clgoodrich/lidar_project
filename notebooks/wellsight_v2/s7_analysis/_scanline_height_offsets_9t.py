"""Does each scan line really sit a little high or low? The direct test.

THE CLAIM
---------
The RRIM's stripes were explained as a washboard: every sweep of the mirror
lays a line of ground points, and each line sits a centimetre or two off the
one before it, so the surface ends up corrugated at the scan-line spacing.
Slope and openness measure shape, so a ripple invisible in elevation becomes a
stripe in them.

Everything supporting that was indirect -- the direction of the stripes, which
layers carry them, how they respond to cell size and to the gridding algorithm.
Nobody had measured the thing itself: the height of one scan line against its
neighbour.

HOW
---
Ground returns only, in one window.

  1  Remove the terrain. For every point, subtract the mean ground height
     within roughly 15 m. Hillsides, valleys and the pit itself all go; what is
     left is the fine residual, in centimetres.
  2  Label every point with the sweep that produced it, by binning gps_time at
     the measured half-sweep period of 9.348 ms.
  3  Take the median residual of each sweep. One number per scan line.
  4  Look at the sequence of those numbers.

WHAT WOULD CONFIRM IT, AND WHAT WOULD KILL IT
---------------------------------------------
Confirm: the per-sweep medians have a real spread -- centimetres, not
millimetres -- AND the striped window shows more of it than the clean one.

Kill: the spread is the same in both windows, or it is at the level of the
noise in a single sweep. Then the lines do not disagree and the washboard story
is wrong, whatever the direction measurements say.

THE CONTROL IS THE POINT. A striped window on its own proves nothing, because
some spread is expected everywhere. 623822 E 4594949 N scores x9.03 on the DEM
and x3.70 on the RRIM; the corn-row panel 300 m west scores x1.0 on both. If
the washboard is the cause, the first must be worse than the second.

Run:
    python notebooks/wellsight_v2/s7_analysis/_scanline_height_offsets_9t.py
Writes:
    data/9t/results/nonground_classification/scanline_height_offsets_9t.json
    docs/presentation/figures_30to45min/v6/scanline_height_offsets_9t.png
"""
from __future__ import annotations

import json
from pathlib import Path

import laspy
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
OUT = (ROOT / "data/9t/results/nonground_classification"
       / "scanline_height_offsets_9t.json")
FIG = ROOT / "docs/presentation/figures_30to45min/v6"

#: Half-sweep period, from the nadir crossings of scan_angle in
#: _measure_scanner_geometry_9t.py. One bin of this length is one scan line.
HALF_SWEEP_S = 0.009348
#: Grid used to take the terrain out, and the smoothing radius on it.
TREND_CELL, TREND_SMOOTH_M = 2.0, 15.0
#: A sweep needs this many ground points in the window before its median means
#: anything.
MIN_PTS = 25

WINDOWS = {
    "striped  (DEM x9.0, RRIM x3.7)": (623822.4, 4594948.6, 400.0),
    "clean    (DEM x1.0, RRIM x1.0)": (621359.6, 4594467.4, 400.0),
}
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"
HOT, COOL = "#D97706", "#1F5FA8"


def laz_files():
    seen, out = set(), []
    for d in ("data/_source/lidar/westernpa",
              "data/_source/lidar/westernpa/OTHER_DATA"):
        for f in sorted((ROOT / d).glob("*.laz")):
            if ".copc." in f.name or f.name in seen:
                continue
            seen.add(f.name)
            out.append(f)
    return out


def load_ground(b):
    X, Y, Z, T = [], [], [], []
    for f in laz_files():
        with laspy.open(f) as rd:
            lo, hi = rd.header.mins, rd.header.maxs
        if lo[0] > b[2] or hi[0] < b[0] or lo[1] > b[3] or hi[1] < b[1]:
            continue
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = ((x >= b[0]) & (x < b[2]) & (y >= b[1]) & (y < b[3])
             & (np.asarray(las.classification) == 2))
        if not m.any():
            continue
        X.append(x[m]); Y.append(y[m])
        Z.append(np.asarray(las.z)[m])
        T.append(np.asarray(las.gps_time)[m])
    if not X:
        return None
    return (np.concatenate(X), np.concatenate(Y),
            np.concatenate(Z), np.concatenate(T))


def detrend(x, y, z, b):
    """Subtract the local mean ground height, so only the fine residual is left."""
    from scipy import ndimage
    nx = int(np.ceil((b[2] - b[0]) / TREND_CELL))
    ny = int(np.ceil((b[3] - b[1]) / TREND_CELL))
    c = np.clip(((x - b[0]) / TREND_CELL).astype(int), 0, nx - 1)
    r = np.clip(((b[3] - y) / TREND_CELL).astype(int), 0, ny - 1)
    i = r * nx + c
    s = np.bincount(i, weights=z, minlength=nx * ny).reshape(ny, nx)
    n = np.bincount(i, minlength=nx * ny).reshape(ny, nx).astype("float64")
    # smooth sum and count separately, then divide: dividing first would let
    # empty cells vote as zero and drag the trend down wherever coverage is thin
    k = max(3, int(round(TREND_SMOOTH_M / TREND_CELL)) | 1)
    ss = ndimage.uniform_filter(s, k, mode="nearest")
    nn = ndimage.uniform_filter(n, k, mode="nearest")
    trend = np.where(nn > 0, ss / np.maximum(nn, 1e-9), np.nan)
    return z - trend[r, c]


def per_sweep(resid, t):
    idx = ((t - t.min()) / HALF_SWEEP_S).astype(np.int64)
    order = np.argsort(idx)
    idx, resid = idx[order], resid[order]
    keep = np.isfinite(resid)
    idx, resid = idx[keep], resid[keep]
    uniq, start = np.unique(idx, return_index=True)
    meds, cnts = [], []
    bounds = np.append(start, len(idx))
    for a, bnd in zip(bounds[:-1], bounds[1:]):
        if bnd - a < MIN_PTS:
            continue
        meds.append(float(np.median(resid[a:bnd])))
        cnts.append(int(bnd - a))
    return np.asarray(meds), np.asarray(cnts)


def main() -> int:
    res = {"half_sweep_s": HALF_SWEEP_S, "min_pts": MIN_PTS, "windows": {}}
    series = {}
    for name, (cx, cy, side) in WINDOWS.items():
        h = side / 2.0
        b = (cx - h, cy - h, cx + h, cy + h)
        g = load_ground(b)
        if g is None:
            print(f"{name}: no ground returns")
            continue
        x, y, z, t = g
        resid = detrend(x, y, z, b)
        meds, cnts = per_sweep(resid, t)
        if len(meds) < 30:
            print(f"{name}: only {len(meds)} usable sweeps")
            continue
        # spread of the per-line offsets
        sd = float(np.std(meds))
        iqr = float(np.percentile(meds, 75) - np.percentile(meds, 25))
        # how much of a single sweep's own scatter could fake that
        within = float(np.median([np.std(resid[np.isfinite(resid)])]))
        # do neighbouring lines alternate? lag-1 autocorrelation of the series
        m0 = meds - meds.mean()
        lag1 = float(np.corrcoef(m0[:-1], m0[1:])[0, 1]) if len(m0) > 3 else np.nan
        series[name] = meds
        res["windows"][name] = dict(
            n_ground=int(len(x)), n_sweeps=int(len(meds)),
            median_pts_per_sweep=int(np.median(cnts)),
            sd_cm=sd * 100, iqr_cm=iqr * 100,
            within_sweep_sd_cm=within * 100, lag1_autocorr=lag1)
        print(f"\n{name}")
        print(f"  {len(x):,} ground returns, {len(meds):,} usable scan lines, "
              f"{int(np.median(cnts))} points each")
        print(f"  line-to-line height offset:  sd {sd*100:.2f} cm,  "
              f"IQR {iqr*100:.2f} cm")
        print(f"  scatter WITHIN one line:     sd {within*100:.2f} cm")
        print(f"  neighbouring lines, lag-1 correlation: {lag1:+.3f}")

    ks = list(res["windows"])
    if len(ks) == 2:
        a, c = res["windows"][ks[0]], res["windows"][ks[1]]
        ratio = a["sd_cm"] / max(c["sd_cm"], 1e-9)
        res["striped_over_clean"] = ratio
        print(f"\nVERDICT")
        print(f"  striped window line offsets {a['sd_cm']:.2f} cm")
        print(f"  clean   window line offsets {c['sd_cm']:.2f} cm")
        print(f"  ratio {ratio:.2f}x")
        if ratio > 1.4:
            print("  -> the lines DO disagree more where the stripes are. "
                  "The washboard story holds.")
        elif ratio < 1.15:
            print("  -> the lines disagree the SAME amount in both. The "
                  "washboard story does NOT explain the stripes; something "
                  "else does.")
        else:
            print("  -> inconclusive. The difference is too small to carry a "
                  "claim either way.")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=2), encoding="utf-8")
    if series:
        figure(series, res)
    print(f"\n  {OUT}")
    return 0


def figure(series, res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(14.0, 5.4))
    fig.patch.set_facecolor(PAPER)
    for ax, (name, meds), col in zip(axes, series.items(), (HOT, COOL)):
        n = min(160, len(meds))
        ax.plot(np.arange(n), meds[:n] * 100, "-o", color=col, lw=1.8, ms=3.5)
        ax.axhline(0, color="#c8c8c0", lw=1.2)
        d = res["windows"][name]
        ax.set_title(name.strip(), loc="left", fontsize=14,
                     fontweight="bold", color=INK)
        ax.set_xlabel(f"scan line, in the order they were flown  ·  "
                      f"sd {d['sd_cm']:.2f} cm", fontsize=12, color=MUTED)
        ax.set_ylabel("height of the line, cm above local ground",
                      fontsize=11.5, color=MUTED)
        ax.grid(axis="y", color="#e9e9e1", lw=0.9)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_edgecolor("#c8c8c0")
    lo = min(a.get_ylim()[0] for a in axes)
    hi = max(a.get_ylim()[1] for a in axes)
    for ax in axes:
        ax.set_ylim(lo, hi)      # same scale, or the comparison is theatre

    fig.suptitle("Does each scan line sit high or low?",
                 x=0.010, y=0.985, ha="left", va="top", fontsize=17,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    FIG.mkdir(parents=True, exist_ok=True)
    p = FIG / "scanline_height_offsets_9t.png"
    fig.savefig(p, dpi=155, facecolor=PAPER)
    plt.close(fig)
    print(f"  {p}")


if __name__ == "__main__":
    raise SystemExit(main())
