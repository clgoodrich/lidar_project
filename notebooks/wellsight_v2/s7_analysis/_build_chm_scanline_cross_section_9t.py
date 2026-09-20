"""Cross-section cut across the bright scan-line streaks in the CHM.

The streaks are established as an instrument artifact by
`_test_chm_scanline_streaks_9t.py`: the returns under them are 21% single-return
against 70% elsewhere, at the same scan angle as their surroundings, and they
fall into 20 discrete GPS-time bands. This draws the profile.

ORIENTATION IS MEASURED, NOT EYEBALLED -- AND NOT VIA scipy.rotate
------------------------------------------------------------------
The first attempt used a Radon transform built on `scipy.ndimage.rotate` and
returned a bearing that did not match the panel. The rotation convention was
ambiguous and the peak finder split single streaks, giving 129 deg and 2.0 m,
both wrong. This projects in MAP coordinates instead, with no rotation:

    along the line   u = ( sin t, cos t )      t = bearing from north
    across the line  v = ( cos t, -sin t )

Every bright pixel is projected onto `v`. When `u` is parallel to the streaks
they pile into a few bins and the histogram variance peaks. Spacing is then the
median gap between histogram peaks, in metres, along `v`. Both quantities come
out of the same projection, so they cannot disagree with each other.

THE PROFILE
-----------
Cut along `v`, so it crosses the streaks at right angles. DSM, DEM and CHM are
sampled on one line, which is the point: it shows the spikes living in the
first-return surface while the bare earth underneath stays smooth.

RENDERING
---------
The CHM map is drawn black-to-white on the raster min/max, the way the QGIS
project styles it and the way `chm_300m_9t.png` ships. A percentile stretch
hides these streaks -- that is how the first pass missed them -- so a percentile
stretch is not used anywhere in this figure.

COLOUR
------
The map is greyscale. The profile needs three lines that must be told apart:
dataviz reference categorical slots 1/2/7, validated
    node scripts/validate_palette.js "#2a78d6,#eb6834,#4a3aa7" \
         --mode light --pairs all      -> ALL CHECKS PASS
    CVD worst  #4a3aa7 <-> #2a78d6  dE 10.4 deutan
    normal     #4a3aa7 <-> #2a78d6  dE 16.3
No red and no green, so no red/green pair. Each line is also directly labelled
and the surfaces sit at different heights, so colour is never the only cue.

Run:
    python notebooks/wellsight_v2/s7_analysis/_build_chm_scanline_cross_section_9t.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
OUT = ROOT / "data/9t/results/chm_striping"
FIG = ROOT / "docs/presentation/figures_30to45min/2_terrain_derivatives"

PAPER, INK, INK2, MUTED, RULE = "#f7f8f6", "#141a1f", "#545c63", "#8a887e", "#c9ccc6"
C_DSM, C_DEM, C_CHM = "#2a78d6", "#eb6834", "#4a3aa7"


def bounds_of(lat, lon, side):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    x, y = tr.transform(lon, lat)
    h = side / 2.0
    return (x - h, y - h, x + h, y + h), (x, y)


def read_window(path, b):
    with rasterio.open(path) as r:
        w = from_bounds(*b, transform=r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    return a


def streak_mask(chm, q=99.5, size=9):
    """Isolate the thin bright ridges, by local contrast rather than by height.

    Two earlier detectors both failed, for the same underlying reason.

    A high CHM percentile keeps only the TALLEST pixels, which over this window
    are tree crowns; in the open ground where the streaks are most obvious they
    are not tall in absolute terms at all, just bright against near-zero canopy.
    Restricting that mask to the open quadrant returned zero pixels, which is
    what exposed the mistake.

    A 3x3 binary opening on the same mask removes blobs and keeps thin things,
    but it is still working on a set that barely contains the streaks.

    A white top-hat is the right instrument: it keeps whatever is brighter than
    its own surroundings within `size` pixels and discards everything smoothly
    varying, so it finds a 2 m ridge on bare ground and a 2 m ridge under
    canopy alike. The bearing it yields is stable across thresholds (121 deg at
    q99.0 and q99.5) where the percentile mask was not.
    """
    from scipy.ndimage import white_tophat
    th = white_tophat(np.nan_to_num(chm, nan=0.0), size=size)
    return th >= np.percentile(th, q)


def orientation(bright, res, bin_m=0.5):
    """Bearing of the streaks and their spacing, from one map-space projection."""
    rows, cols = np.where(bright)
    if len(rows) < 50:
        raise SystemExit("too few bright pixels to orient")
    ex = (cols + 0.5) * res          # metres east within the window
    ny = bright.shape[0]
    nn = (ny - rows - 0.5) * res     # metres north within the window

    best = (None, -1.0, None)
    scan = {}
    for t in np.arange(0.0, 180.0, 0.25):
        th = np.radians(t)
        p = ex * np.cos(th) - nn * np.sin(th)        # across-line coordinate
        h, _ = np.histogram(p, bins=np.arange(p.min(), p.max() + bin_m, bin_m))
        v = float(np.var(h))
        scan[float(t)] = v
        if v > best[1]:
            best = (float(t), v, (p, h))
    t, _, (p, h) = best

    # spacing: peaks must be at least 1 m apart so one streak is not split in
    # two, which is exactly what the first attempt did.
    pk, _ = find_peaks(h, height=0.30 * h.max(), distance=int(round(1.0 / bin_m)))
    sp = float(np.median(np.diff(pk) * bin_m)) if len(pk) >= 3 else None
    return t, sp, len(pk), scan


def sample(a, bounds, res, x0, y0, dx, dy, half_m):
    """Bilinear sample of a raster along a map-space line."""
    ny, nx = a.shape
    s = np.arange(-half_m, half_m, res)
    X = x0 + s * dx
    Y = y0 + s * dy
    c = (X - bounds[0]) / res - 0.5
    r = (bounds[3] - Y) / res - 0.5
    ok = (c >= 0) & (c < nx - 1) & (r >= 0) & (r < ny - 1)
    s, c, r = s[ok], c[ok], r[ok]
    c0, r0 = c.astype(int), r.astype(int)
    fc, fr = c - c0, r - r0
    v = (a[r0, c0] * (1 - fc) * (1 - fr) + a[r0, c0 + 1] * fc * (1 - fr)
         + a[r0 + 1, c0] * (1 - fc) * fr + a[r0 + 1, c0 + 1] * fc * fr)
    return s, v, X, Y


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float,
                    default=[41.49264, -79.546127])
    ap.add_argument("--side", type=float, default=300.0)
    ap.add_argument("--res", type=float, default=0.5)
    ap.add_argument("--hi", type=float, default=99.3)
    ap.add_argument("--profile-m", type=float, default=60.0,
                    help="half-length of the cross-section, metres")
    a = ap.parse_args()

    b, (cx, cy) = bounds_of(a.centre[0], a.centre[1], a.side)
    chm = read_window(D05 / "chm_9t_05.tif", b)
    dsm = read_window(D05 / "dsm_9t_05.tif", b)
    dem = read_window(D05 / "dem_9t_05.tif", b)

    thr = float(np.nanpercentile(chm, a.hi))
    bright = np.isfinite(chm) & (chm >= thr)
    streak = streak_mask(chm)
    print(f"  top-hat streak mask: {streak.sum():,} px "
          f"({100*streak.mean():.2f}% of the window)")
    t, sp, npk, _ = orientation(streak, a.res)
    th = np.radians(t)
    ux, uy = np.sin(th), np.cos(th)          # along the streaks
    vx, vy = np.cos(th), -np.sin(th)         # across them
    print(f"streaks bear {t:.1f} deg, spacing "
          f"{'n/a' if sp is None else f'{sp:.2f} m'} from {npk} peaks "
          f"(threshold CHM >= {thr:.2f} m, {bright.sum():,} px)")

    # put the cut where the streaks actually are: the bright centroid
    rows, cols = np.where(streak)
    px = b[0] + (cols.mean() + 0.5) * a.res
    py = b[3] - (rows.mean() + 0.5) * a.res

    s_dsm, v_dsm, X, Y = sample(dsm, b, a.res, px, py, vx, vy, a.profile_m)
    s_dem, v_dem, _, _ = sample(dem, b, a.res, px, py, vx, vy, a.profile_m)
    s_chm, v_chm, _, _ = sample(chm, b, a.res, px, py, vx, vy, a.profile_m)

    # how many spikes the cut crosses, and how tall they are
    pk, _ = find_peaks(np.nan_to_num(v_chm), height=max(5.0, 0.35 * np.nanmax(v_chm)),
                       distance=int(round(1.5 / a.res)))
    gaps = np.diff(s_chm[pk]) if len(pk) >= 3 else np.array([])
    print(f"  cut crosses {len(pk)} spikes; median gap "
          f"{np.median(gaps):.2f} m" if len(gaps) else
          f"  cut crosses {len(pk)} spikes")
    print(f"  DEM along the cut: range {np.nanmax(v_dem)-np.nanmin(v_dem):.2f} m, "
          f"sd {np.nanstd(v_dem):.3f} m")
    print(f"  DSM along the cut: range {np.nanmax(v_dsm)-np.nanmin(v_dsm):.2f} m, "
          f"sd {np.nanstd(v_dsm):.3f} m")

    plt.rcParams.update({"figure.facecolor": PAPER, "axes.facecolor": PAPER,
                         "savefig.facecolor": PAPER,
                         "font.family": "DejaVu Sans", "text.color": INK})
    fig = plt.figure(figsize=(18.6, 10.2))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.42], left=0.028,
                          right=0.975, top=0.815, bottom=0.085, wspace=0.11)

    ax = fig.add_subplot(gs[0, 0])
    lo, hi = float(np.nanmin(chm)), float(np.nanmax(chm))
    ax.imshow(chm, extent=[b[0], b[2], b[1], b[3]], origin="upper", cmap="gray",
              vmin=lo, vmax=hi, interpolation="nearest")
    ax.plot(X, Y, color="#ffd400", linewidth=2.6, zorder=5)
    ax.scatter([px], [py], s=48, facecolor="#ffd400", edgecolor=INK,
               zorder=6, linewidth=1.2)
    ax.set_title(f"Canopy height, black to white on {lo:.0f}–{hi:.0f} m "
                 f"(the shipped styling)", fontsize=12.5, fontweight="bold",
                 loc="left", color=INK, pad=7)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.text(0.5, -0.035, f"the cut runs {(t+90)%180:.0f}°, across streaks "
            f"bearing {t:.0f}°", transform=ax.transAxes, ha="center",
            va="top", fontsize=11.5, color=INK2)

    axp = fig.add_subplot(gs[0, 1])
    axp.plot(s_dsm, v_dsm, color=C_DSM, linewidth=1.9, zorder=4)
    axp.plot(s_dem, v_dem, color=C_DEM, linewidth=2.2, zorder=5)
    axp.fill_between(s_dsm, v_dem, v_dsm, where=np.isfinite(v_dsm),
                     color=C_DSM, alpha=0.10, zorder=2)
    axp.scatter(s_chm[pk], v_dsm[pk], s=34, facecolor="white",
                edgecolor=C_CHM, linewidth=1.6, zorder=7)
    axp.set_xlabel("distance across the streaks, metres", fontsize=12.5)
    axp.set_ylabel("elevation, m", fontsize=12.5)
    axp.grid(color=RULE, linewidth=0.8)
    axp.set_axisbelow(True)
    for s_ in ("top", "right"):
        axp.spines[s_].set_visible(False)
    xr = s_dsm[-1] if len(s_dsm) else 1
    axp.text(xr, np.nanmean(v_dsm[-40:]) if len(v_dsm) > 40 else np.nanmean(v_dsm),
             "  DSM (first returns)", color=C_DSM, fontsize=12,
             fontweight="bold", va="center")
    axp.text(xr, np.nanmean(v_dem[-40:]) if len(v_dem) > 40 else np.nanmean(v_dem),
             "  DEM (bare earth)", color=C_DEM, fontsize=12,
             fontweight="bold", va="center")
    axp.set_xlim(s_dsm.min(), s_dsm.max() + 0.42 * (s_dsm.max() - s_dsm.min()))
    axp.text(0.012, 0.965,
             f"{len(pk)} spikes crossed" +
             (f", median spacing {np.median(gaps):.1f} m" if len(gaps) else "") +
             f"\nDSM varies {np.nanmax(v_dsm)-np.nanmin(v_dsm):.1f} m along this "
             f"cut; the DEM under it varies "
             f"{np.nanmax(v_dem)-np.nanmin(v_dem):.1f} m",
             transform=axp.transAxes, fontsize=12, color=INK, va="top",
             linespacing=1.5,
             bbox=dict(boxstyle="round,pad=0.5", facecolor="white",
                       edgecolor=RULE))
    axp.set_title("The spikes are in the first-return surface only",
                  fontsize=13.5, fontweight="bold", loc="left", color=INK, pad=8)

    fig.text(0.028, 0.972,
             "The bright lines in the canopy model are scanner sweeps, "
             "not vegetation",
             fontsize=25, fontweight="bold", color=INK, va="top")
    fig.text(0.028, 0.905,
             f"Same {a.side:.0f} m window as every derivative panel, centred "
             f"{cx:.0f} E {cy:.0f} N (EPSG:6346), one flight line (637). The "
             f"returns on these lines are 21% single-return against 70% off "
             f"them, sit at the same\nscan angle as their surroundings "
             f"(3.8° vs 3.6°, so this is not the 18° wide-angle cut), and fall "
             f"into 20 discrete GPS-time bands. CHM is not one of the seven "
             f"model channels, so nothing downstream uses it.",
             fontsize=12.5, color=INK2, va="top", linespacing=1.55)

    FIG.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    p = FIG / f"chm_scanline_cross_section_{a.side:.0f}m_9t.png"
    fig.savefig(p, dpi=150)
    plt.close(fig)
    jp = OUT / f"chm_scanline_cross_section_{a.side:.0f}m_9t.json"
    jp.write_text(json.dumps(dict(
        bearing_deg=t, cut_bearing_deg=(t + 90) % 180, spacing_m=sp,
        n_hist_peaks=npk, threshold_m=thr, spikes_on_cut=int(len(pk)),
        median_spike_gap_m=float(np.median(gaps)) if len(gaps) else None,
        dsm_range_m=float(np.nanmax(v_dsm) - np.nanmin(v_dsm)),
        dem_range_m=float(np.nanmax(v_dem) - np.nanmin(v_dem)),
        dem_sd_m=float(np.nanstd(v_dem))), indent=2), encoding="utf-8")
    print(f"\n  {p}\n  {jp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
