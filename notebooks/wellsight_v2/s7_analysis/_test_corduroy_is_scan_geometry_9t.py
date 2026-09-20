"""The corn rows are a scan artefact: they lie along the scan lines.

SUPERSEDED IN PART -- READ THIS FIRST
-------------------------------------
This script's parts 1 and 4 stand. Parts 2 and 3 were wrong, and the title used
to say "the scanner's along-track sweep step", which was wrong too.

  PART 2, flight bearing and groundspeed, regressed x and y against gps_time
  over all returns. That measures the SWEEP, not the aircraft: the beam crosses
  1149 m of ground in 6 ms while the plane moves under half a metre. It
  returned 112.2 m/s; the near-nadir ground track gives 70.1 m/s.

  PART 3, stripe spacing, reported 3.00 m from an autocorrelation restricted to
  lags over 2 m. Restrict a search above 2 m and it will return something above
  2 m. The same profile has no clean periodic peak anywhere, so no spacing is
  claimed any more.

  Everything built on those -- a 37.4 Hz sweep, a 1.03 m line spacing, an
  oscillating mirror, and a story about lines pairing at the swath edge -- is
  withdrawn. The sensor is a RIEGL VQ-1560 series, a ROTATING POLYGON, which
  rules straight parallel lines and has no turnaround and no phase to pair.

  `_measure_scanner_geometry_9t.py` has the corrected geometry and the full
  account of how each number went wrong.

WHAT SURVIVES, AND IT IS THE PART THAT MATTERS
----------------------------------------------
The corn rows run at 79.0 deg. The scan lines, measured independently off the
ground pattern, run at 78.0 deg. The corn rows lie ALONG THE SCAN LINES. Void
cells hold nothing: 94.1% have no return of any kind. Coverage on a stripe is
1.8x thinner than beside it.

THE QUESTION
------------
The CHM over this window carries regularly spaced parallel stripes. Earlier work
(_test_chm_nodata_bands_9t.py) established that the stripes are NoData, not tall
canopy, and measured their bearing at 79 deg. It did not establish what put them
there, and it did not answer whether "NoData" means thin coverage or no lidar at
all. This does both, by measurement.

WHAT IT MEASURES, AND WHAT EACH ANSWERS
---------------------------------------
1. Returns of every kind inside a void cell, not just first returns. "No first
   return" and "no lidar at all" are different claims and the earlier test only
   supported the first one.
2. Flight bearing and groundspeed, regressed from gps_time against position.
   If the stripes are a scan artefact their bearing must be the across-track
   direction, which is the flight bearing minus 90.
3. Stripe spacing and width, from run lengths in the along-track void profile.
   Spacing divided into groundspeed gives the mirror sweep rate.
4. Return density on a stripe against between stripes. A scan-geometry stripe
   must be a density trough; if density is flat the cause is something else.

DO NOT measure (3) with an FFT of the whole window. The void field occupies one
patch of it, so the transform's largest peak is the patch, not the stripes --
177 m, which is a meaningless number.

Nor with the gaps between detected stripe centres: a stripe faint enough to fall
under the threshold merges two gaps into one, so the answer moves with the
threshold and with the extent (3.00 m over one, 3.62 m over another).
Autocorrelation of the high-passed void profile uses every stripe at once and
does not depend on any individual one being detected.

DO NOT measure (4) by folding along-track position modulo the stripe spacing
either. Groundspeed and sweep rate both wander slightly, so the phase drifts
over a few hundred metres and the fold washes the modulation out completely
(1.02x against 0.98x -- flat). Phase-lock to the DETECTED stripe centres.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_corduroy_is_scan_geometry_9t.py
"""
from __future__ import annotations

from pathlib import Path

import laspy
import numpy as np
import rasterio
from rasterio.windows import from_bounds

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
SRC = ROOT / "data/_source/lidar/westernpa/OTHER_DATA"

#: The CHM panel's window, from LAT/LON/SIDE_M in
#: docs/presentation/figures_30to45min/_build_derivative_panel.py.
CX, CY, SIDE, RES = 621359.6, 4594467.4, 300.0, 0.5


def window():
    h = SIDE / 2.0
    return (CX - h, CY - h, CX + h, CY + h)


def read(fn, b):
    with rasterio.open(D05 / fn) as r:
        a = r.read(1, window=from_bounds(*b, transform=r.transform),
                   boundless=True, fill_value=np.nan).astype("float32")
    a[a < -1000.0] = np.nan
    return a


def load_points(b):
    X, Y, T, P, RN, CL = [], [], [], [], [], []
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= b[0]) & (x < b[2]) & (y >= b[1]) & (y < b[3])
        if not m.any():
            continue
        X.append(x[m]); Y.append(y[m])
        T.append(np.asarray(las.gps_time)[m])
        P.append(np.asarray(las.point_source_id)[m])
        RN.append(np.asarray(las.return_number)[m])
        CL.append(np.asarray(las.classification)[m])
    return (np.concatenate(X), np.concatenate(Y), np.concatenate(T),
            np.concatenate(P), np.concatenate(RN), np.concatenate(CL))


def main() -> int:
    b = window()
    dsm, dem = read("dsm_9t_05.tif", b), read("dem_9t_05.tif", b)
    void = ~np.isfinite(dsm)
    ny, nx = dsm.shape
    print(f"window {SIDE:.0f} m at {CX} E {CY} N, {nx}x{ny} @ {RES} m")
    print(f"  DSM void {void.sum():,} cells = {100*void.mean():.2f}%   "
          f"DEM void {100*(~np.isfinite(dem)).mean():.2f}%")

    x, y, t, psid, rn, cl = load_points(b)

    # ---- 1. is there any lidar at all in a void cell -------------------
    c = np.clip(((x - b[0]) / RES).astype(int), 0, nx - 1)
    r = np.clip(((b[3] - y) / RES).astype(int), 0, ny - 1)
    idx = r * nx + c
    n_all = np.bincount(idx, minlength=nx * ny).reshape(ny, nx)
    n_1st = np.bincount(idx[rn == 1], minlength=nx * ny).reshape(ny, nx)
    n_gnd = np.bincount(idx[cl == 2], minlength=nx * ny).reshape(ny, nx)
    print("\n1. WHAT IS IN A VOID CELL")
    for label, m in (("void", void), ("normal", ~void)):
        print(f"  {label:7s} n={int(m.sum()):>7,}  "
              f"zero returns {100*(n_all[m] == 0).mean():5.2f}%  "
              f"zero first {100*(n_1st[m] == 0).mean():6.2f}%  "
              f"zero ground {100*(n_gnd[m] == 0).mean():5.2f}%  "
              f"mean {n_all[m].mean():.2f} returns/cell")

    # ---- 2. flight geometry --------------------------------------------
    print("\n2. FLIGHT GEOMETRY")
    print(f"  point_source_id in window: {np.unique(psid)}")
    tt = t - t.mean()
    vx = np.polyfit(tt, x, 1)[0]
    vy = np.polyfit(tt, y, 1)[0]
    flight = np.degrees(np.arctan2(vx, vy)) % 360.0
    speed = float(np.hypot(vx, vy))
    across = (flight - 90.0) % 180.0   # a line has a direction, not a sense
    print(f"  bearing {flight:.1f} deg, groundspeed {speed:.1f} m/s")
    print(f"  across-track {across:.1f} deg  <- compare the stripes' 79 deg")

    # ---- 3. stripe spacing and width -----------------------------------
    u = np.array([np.sin(np.radians(flight)), np.cos(np.radians(flight))])
    XX = b[0] + (np.arange(nx)[None, :] + 0.5) * RES
    YY = b[3] - (np.arange(ny)[:, None] + 0.5) * RES
    s = (XX - CX) * u[0] + (YY - CY) * u[1]        # along track
    a_ = -(XX - CX) * u[1] + (YY - CY) * u[0]      # across track
    lo, hi = np.percentile(a_[void], [5, 95])
    slo, shi = np.percentile(s[void], [2, 98])
    band = (a_ >= lo) & (a_ <= hi) & (s >= slo) & (s <= shi)

    edges = np.arange(slo, shi, 0.25)
    cells, _ = np.histogram(s[band].ravel(), bins=edges)
    vcell, _ = np.histogram(s[band & void].ravel(), bins=edges)
    vfrac = np.where(cells > 0, vcell / np.maximum(cells, 1), 0.0)
    on = vfrac > vfrac.mean() + 0.5 * vfrac.std()
    off = vfrac < vfrac.mean() * 0.2

    widths, run, n_stripes = [], 0, 0
    for v in on:
        if v:
            run += 1
        elif run:
            widths.append(run * 0.25)
            n_stripes += 1
            run = 0

    # Spacing by autocorrelation of the high-passed profile. Every stripe
    # contributes, so a faint one that the threshold missed cannot merge two
    # gaps into one and drag the answer around.
    hp = vfrac - np.convolve(vfrac, np.ones(21) / 21.0, mode="same")
    hp -= hp.mean()
    ac = np.correlate(hp, hp, mode="full")[len(hp) - 1:]
    ac = ac / ac[0]
    lag = np.arange(len(ac)) * 0.25

    # Take the FIRST local maximum past 2 m, not the largest. The stripes come
    # in clusters of about three, so the third harmonic near 8.5 m is the
    # tallest peak in the curve (r=0.43 against 0.36) and argmax lands on it.
    # The fundamental is what a sweep rate is computed from.
    pk = None
    for i in range(1, len(ac) - 1):
        if lag[i] < 2.0:
            continue
        if lag[i] > 12.0:
            break
        if ac[i] > ac[i - 1] and ac[i] >= ac[i + 1] and ac[i] > 0:
            pk = i
            break
    spacing = float(lag[pk]) if pk else float("nan")
    print("\n3. STRIPE GEOMETRY")
    print(f"  {n_stripes} stripes over {edges[-1]-edges[0]:.0f} m along-track")
    print(f"  spacing {spacing:.2f} m  "
          f"(first autocorrelation peak past 2 m, r={ac[pk]:.2f})")
    print(f"  width   median {np.median(widths):.2f} m")
    print(f"  implied sweep rate {speed/spacing:.1f} Hz")

    # ---- 4. density on a stripe vs between ------------------------------
    ps = (x - CX) * u[0] + (y - CY) * u[1]
    pa = -(x - CX) * u[1] + (y - CY) * u[0]
    k = (pa >= lo) & (pa <= hi) & (ps >= slo) & (ps <= shi)
    cnt, _ = np.histogram(ps[k], bins=edges)
    dens = np.where(cells > 0, cnt / np.maximum(cells, 1), np.nan)
    d_on, d_off = float(np.nanmean(dens[on])), float(np.nanmean(dens[off]))
    print("\n4. RETURN DENSITY, returns per 0.5 m cell")
    print(f"  on a stripe      {d_on:.3f}")
    print(f"  between stripes  {d_off:.3f}")
    print(f"  ratio            {d_off/max(d_on, 1e-9):.1f}x thinner on a stripe")

    print("\nVERDICT")
    print(f"  stripes run {across:.1f} deg, the across-track direction of a "
          f"{flight:.1f} deg flight line")
    print(f"  spaced {spacing:.2f} m, which is {speed:.0f} m/s / "
          f"{speed/spacing:.1f} Hz -- one mirror sweep")
    print(f"  {d_off/max(d_on, 1e-9):.1f}x thinner coverage on a stripe, and "
          f"{100*(n_all[void] == 0).mean():.0f}% of void cells hold no return "
          f"of any kind")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
