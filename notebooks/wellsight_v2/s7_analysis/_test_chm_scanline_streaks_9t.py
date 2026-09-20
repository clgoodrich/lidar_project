"""SUPERSEDED 2026-09-19 -- WRONG MASK. Do not quote any number from this file.

Use `_test_chm_nodata_bands_9t.py` instead.

The bands are NoData, not canopy: matplotlib paints NaN as the figure
background, which on a black-to-white greyscale ramp is brighter than the
maximum value. The mask below is `chm >= percentile(chm, 99.3)`, which by
construction keeps only cells that HAVE a value -- the exact complement of the
bands it was written to measure. Everything it reports is canopy versus ground.

Retracted from this script: the 21%-vs-70% single-return split, the 20 GPS-time
bands, the 3.8-vs-3.6 deg scan angle, and flight line 637. Its bearing is wrong
a second time over: `(90 - ang)` does not belong, the projection angle IS the
map bearing. Correct answer, on the NoData mask, is 79.0 deg.

Kept unmodified as the record of how the mistake was made.

--- original docstring follows ---

What are the bright parallel streaks in the CHM?

The canopy panel `chm_300m_9t.png` carries thin, bright, regularly spaced lines
running roughly ENE across the whole window, indifferent to terrain and canopy.
An earlier attempt at this missed them twice over, and both mistakes are worth
recording so they are not repeated:

  1. It re-rendered the CHM with a 2-98 percentile stretch. These streaks are
     one to two pixels wide and near the top of the range, so the stretch
     flattened them out of the image being examined. The shipped panel uses the
     QGIS black-to-white min/max styling, which is why they are obvious there.
  2. It looked for them with a 2D FFT. The spectrum over this window is
     dominated by tree-crown structure; sparse single-pixel ridges carry very
     little total power, so the peak came back at 73 m in the wrong direction
     and a prominence test fired on it. Periodicity was the wrong instrument.

This takes the direct route instead. Find the bright pixels, confirm they are
collinear and evenly spaced, then go back to the POINT CLOUD and ask what the
returns under them have in common. If they share a scan angle, a return number,
a classification or a narrow GPS-time slice, that identifies the mechanism
outright and no inference about spectra is needed.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_chm_scanline_streaks_9t.py
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"
OUT = ROOT / "data/9t/results/chm_striping"

LAT, LON, SIDE, RES = 41.49264, -79.546127, 300.0, 0.5


def bounds_of(lat, lon, side):
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:4326", "EPSG:6346", always_xy=True)
    x, y = tr.transform(lon, lat)
    h = side / 2.0
    return (x - h, y - h, x + h, y + h)


def read_window(path, b):
    with rasterio.open(path) as r:
        w = from_bounds(*b, transform=r.transform)
        a = r.read(1, window=w, boundless=True, fill_value=np.nan).astype("float32")
        if r.nodata is not None and np.isfinite(r.nodata):
            a[a == r.nodata] = np.nan
    return a


def radon_orientation(mask):
    """Bearing that maximises the variance of the projected bright mask.

    Rotating a binary image and summing down columns: collinear bright pixels
    pile into a few columns at the right angle and spread out at every other,
    so projection variance peaks on the line direction. This works on sparse
    thin structures where a power spectrum does not.
    """
    from scipy.ndimage import rotate
    best = (None, -1.0)
    prof = {}
    for ang in np.arange(0.0, 180.0, 0.5):
        r = rotate(mask.astype(np.float32), ang, reshape=False, order=0,
                   mode="constant", cval=0.0)
        p = r.sum(axis=0)
        v = float(np.var(p))
        prof[float(ang)] = v
        if v > best[1]:
            best = (float(ang), v)
    return best[0], prof


def spacing_from_projection(mask, ang):
    """Peak-to-peak spacing of the streaks, measured across them."""
    from scipy.ndimage import rotate
    from scipy.signal import find_peaks
    r = rotate(mask.astype(np.float32), ang, reshape=False, order=0,
               mode="constant", cval=0.0)
    p = r.sum(axis=0)
    if p.max() <= 0:
        return None, 0, p
    pk, _ = find_peaks(p, height=0.35 * p.max(), distance=2)
    if len(pk) < 3:
        return None, len(pk), p
    d = np.diff(pk) * RES
    return float(np.median(d)), len(pk), p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float, default=[LAT, LON])
    ap.add_argument("--side", type=float, default=SIDE)
    ap.add_argument("--hi", type=float, default=99.3,
                    help="percentile above which a CHM pixel counts as a streak")
    a = ap.parse_args()

    b = bounds_of(a.centre[0], a.centre[1], a.side)
    chm = read_window(D05 / "chm_9t_05.tif", b)
    dsm = read_window(D05 / "dsm_9t_05.tif", b)
    dem = read_window(D05 / "dem_9t_05.tif", b)
    print(f"window {b[0]:.1f},{b[1]:.1f} - {b[2]:.1f},{b[3]:.1f}   CHM {chm.shape}")

    thr = float(np.nanpercentile(chm, a.hi))
    bright = np.isfinite(chm) & (chm >= thr)
    print(f"  streak threshold: CHM >= {thr:.2f} m  ({bright.sum():,} px, "
          f"{100*bright.mean():.2f}% of the window)")

    ang, _ = radon_orientation(bright)
    # rotate() turns the image; a projection peak at rotation `ang` means the
    # lines run at bearing (90 - ang) in map terms, x east / y north.
    bearing = (90.0 - ang) % 180.0
    sp, npk, _ = spacing_from_projection(bright, ang)
    print(f"  streaks run at bearing {bearing:.1f} deg "
          f"(projection angle {ang:.1f})")
    print(f"  spacing {sp if sp is None else round(sp, 2)} m "
          f"from {npk} projected peaks")

    # ---- the decisive part: what are the POINTS under the streaks?
    import laspy
    l, bb, r_, t = b
    rows, cols = np.where(bright)
    bx = l + (cols + 0.5) * RES
    by = t - (rows + 0.5) * RES
    keys = set(zip((bx // RES).astype(np.int64), (by // RES).astype(np.int64)))

    stats = {}
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= l) & (x < r_) & (y >= bb) & (y < t)
        if not m.any():
            continue
        x, y = x[m], y[m]
        z = np.asarray(las.z)[m]
        cls = np.asarray(las.classification)[m].astype(np.int16)
        rn = np.asarray(las.return_number)[m].astype(np.int16)
        nr = np.asarray(las.number_of_returns)[m].astype(np.int16)
        ang6 = np.asarray(las.scan_angle)[m].astype(np.float32) * 0.006
        gt = np.asarray(las.gps_time)[m]
        try:
            edge = np.asarray(las.edge_of_flight_line)[m].astype(np.int16)
        except Exception:
            edge = np.zeros(len(x), np.int16)
        try:
            sd = np.asarray(las.scan_direction_flag)[m].astype(np.int16)
        except Exception:
            sd = np.zeros(len(x), np.int16)

        kk = np.array([(int(px // RES), int(py // RES)) for px, py in zip(x, y)],
                      dtype=np.int64) if False else None
        on = np.fromiter(
            ((int(px // RES), int(py // RES)) in keys for px, py in zip(x, y)),
            dtype=bool, count=len(x))
        off = ~on
        if on.sum() < 50:
            continue
        print(f"\n  {f.name}: {on.sum():,} points on the streaks, "
              f"{off.sum():,} off")

        def describe(mask, label):
            d = dict(
                n=int(mask.sum()),
                mean_z=float(z[mask].mean()),
                scan_angle_mean=float(ang6[mask].mean()),
                scan_angle_absmean=float(np.abs(ang6[mask]).mean()),
                scan_angle_p05=float(np.percentile(ang6[mask], 5)),
                scan_angle_p95=float(np.percentile(ang6[mask], 95)),
                first_return_pct=float(100 * (rn[mask] == 1).mean()),
                single_return_pct=float(100 * (nr[mask] == 1).mean()),
                edge_of_flight_pct=float(100 * (edge[mask] == 1).mean()),
                scan_dir_1_pct=float(100 * (sd[mask] == 1).mean()),
                class_hist={int(c): int(n) for c, n in
                            zip(*np.unique(cls[mask], return_counts=True))},
            )
            print(f"    {label:10s} n={d['n']:>8,}  |scan angle| "
                  f"{d['scan_angle_absmean']:5.2f} deg "
                  f"[{d['scan_angle_p05']:+.1f},{d['scan_angle_p95']:+.1f}]  "
                  f"first {d['first_return_pct']:5.1f}%  single "
                  f"{d['single_return_pct']:5.1f}%  edge "
                  f"{d['edge_of_flight_pct']:5.2f}%  scandir1 "
                  f"{d['scan_dir_1_pct']:5.1f}%")
            print(f"               classes {d['class_hist']}")
            return d

        stats[f.name] = dict(on=describe(on, "ON streak"),
                             off=describe(off, "OFF streak"))

        # GPS time is the sharpest instrument: one scanner sweep is one narrow
        # time slice. If the streak points cluster into regularly spaced time
        # bands while the rest do not, these ARE sweeps.
        gon = np.sort(gt[on])
        if len(gon) > 200:
            gaps = np.diff(gon)
            big = gaps[gaps > np.percentile(gaps, 99)]
            stats[f.name]["gps"] = dict(
                span_s=float(gon[-1] - gon[0]),
                median_gap_s=float(np.median(gaps)),
                p99_gap_s=float(np.percentile(gaps, 99)),
                n_big_gaps=int(len(big)))
            print(f"    gps time: span {gon[-1]-gon[0]:.3f} s, median gap "
                  f"{np.median(gaps):.2e} s, p99 gap "
                  f"{np.percentile(gaps,99):.2e} s, {len(big)} big gaps")

    # is the streak in the DSM or the DEM?
    for name, arr in (("chm", chm), ("dsm", dsm), ("dem", dem)):
        on_v = arr[bright]
        off_v = arr[np.isfinite(arr) & ~bright]
        print(f"\n  {name:4s} on-streak mean {np.nanmean(on_v):8.3f}   "
              f"off-streak mean {np.nanmean(off_v):8.3f}   "
              f"difference {np.nanmean(on_v)-np.nanmean(off_v):+.3f}")

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "chm_scanline_streaks_300m_9t.json"
    p.write_text(json.dumps(dict(
        bounds=list(b), threshold_m=thr, bright_px=int(bright.sum()),
        bearing_deg=bearing, spacing_m=sp, n_peaks=npk, points=stats),
        indent=2), encoding="utf-8")
    print(f"\n  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
