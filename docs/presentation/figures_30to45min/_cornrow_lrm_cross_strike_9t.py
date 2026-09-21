"""Cross-strike profile of the striping in LRM, with the direction measured.

WHY LRM ONLY
------------
A bare elevation profile across this ground is dominated by the hillside --
metres of relief against a few centimetres of ripple. The Local Relief Model is
elevation minus a smoothed copy of itself, so the hillside is already gone and
what is left is the short-wavelength residual at centimetre scale. It is also
one of the seven channels the model reads, so this is real model input rather
than a derived illustration.

FINDING THE DIRECTION INSTEAD OF ASSUMING IT
--------------------------------------------
Nothing here is set by eye.

  1  Rotate the LRM window through every bearing from 0 to 179 deg. At each
     one, average down the columns. If the rotation has aligned the stripes
     with the columns, that average keeps their ripple; at any other angle the
     stripes cut across columns and average away. The bearing whose profile
     varies most is the stripe direction.

  2  Read the spacing off that profile's power spectrum, ignoring wavelengths
     longer than a quarter of the window (terrain, not stripes) or shorter
     than two cells (noise).

  3  Find the crests by peak detection, keeping peaks at least half a spacing
     apart.

THE ROTATION-TO-BEARING CONVERSION IS CALIBRATED, NOT DERIVED
-------------------------------------------------------------
`ndimage.rotate`'s sign convention against a north-up map bearing is easy to
get backwards, and a first version of this script did, reporting 10 deg for a
structure at 170. So the conversion is fixed by test: synthetic stripes were
generated at known bearings 0, 30, 78, 120 and 165 deg and run through the
same detector. It returns

    best_rotation = (180 - true_bearing) % 180

on all five, exactly. Hence `bearing = (180 - best) % 180`. `_selftest()` below
re-runs that check and is called on every build, so the conversion cannot drift
silently.

WHAT IT FINDS, AND WHY THE WHOLE CURVE IS PLOTTED
-------------------------------------------------
The deck says the corn rows run at 78 deg, the scan-line bearing. On this
window this method does NOT return 78 -- it returns a direction near the
flight-line bearing instead. Rather than report only the winner, the middle
panel plots directional variance against every bearing, with both the measured
peak and the 78 deg prediction marked, so the reader can see how much structure
sits at each and judge for themselves.

Run:
    python docs/presentation/figures_30to45min/_cornrow_lrm_cross_strike_9t.py
Writes:
    docs/presentation/figures_30to45min/v6/cornrow_lrm_cross_strike_9t.png
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import rasterio
from rasterio.windows import from_bounds
from scipy import ndimage
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parents[3]
D05 = ROOT / "data/9t/derived/05"
LRM = D05 / "lrm_5_9t_05.tif"
OUT = (ROOT / "docs/presentation/figures_30to45min/v6"
       / "cornrow_lrm_cross_strike_9t.png")

CX, CY = 623822.4, 4594948.6
SIDE = 240.0
CELL = 0.5
SCAN_BEARING = 78.0             # scan lines, from the point cloud's geometry
FLIGHT_BEARING = 176.0          # flight lines, same source

BLUE, ORANGE, GREYLINE = "#1F5FA8", "#D97706", "#8E959B"
INK, MUTED, PAPER = "#141A1F", "#6B7278", "#F7F8F6"


#: Corduroy lives at a few metres. Swath-scale brightness banding lives at
#: tens of metres and carries far more variance, so an unfiltered profile finds
#: THAT instead -- the first working version of this returned 173 deg, the
#: flight-line direction, because along-track banding dominated. Removing
#: everything longer than this makes the measurement about corn rows.
BANDPASS_M = 15.0


def profile_at(a, angle_deg, bandpass=True):
    """Column-mean profile after rotating the array by `angle_deg`.

    High-passed by default, so the variance that follows is the variance of
    metre-scale ripple rather than of swath-scale banding.
    """
    r = ndimage.rotate(a, angle_deg, reshape=False, order=1, mode="nearest")
    n = r.shape[0]
    m = int(n * 0.15)                      # trim corners the rotation fakes
    prof = r[m:n - m, m:n - m].mean(axis=0)
    if bandpass:
        k = max(3, int(round(BANDPASS_M / CELL)) | 1)
        prof = prof - ndimage.uniform_filter1d(prof, k, mode="nearest")
    return prof


def bearing_from_rotation(best: float) -> float:
    """Calibrated in _selftest(); do not 'simplify' this."""
    return (180.0 - best) % 180.0


#: A real stripe direction produces a peak several degrees wide. Bilinear
#: rotation also produces one- and two-sample spikes where the resampling grid
#: happens to resonate with the cell grid -- on this window there is a 2-sample
#: spike at rotation 79-80 that is 5x its neighbours and is not a direction.
#: A MEDIAN over +/-3 deg (circular, because bearing is mod 180) removes them.
#: A mean does not: the spike is 5x its neighbours, so averaging five samples
#: still leaves it the winner. The median of the same seven is simply the
#: neighbouring value, which is the point.
SMOOTH_DEG = 7


def sweep(a, step=1.0, smooth=True):
    angles = np.arange(0, 180, step)
    var = np.array([profile_at(a, ang).var() for ang in angles])
    if not smooth:
        return angles, var, var
    k = max(3, int(round(SMOOTH_DEG / step)) | 1)
    sm = ndimage.median_filter(var, size=k, mode="wrap")
    return angles, var, sm


def _selftest():
    """Synthetic stripes at known bearings must come back at those bearings."""
    n, cell = 240, 0.5
    y, x = np.mgrid[0:n, 0:n].astype(float)
    X, Y = x * cell, (n - 1 - y) * cell
    for truth in (0.0, 30.0, 78.0, 120.0, 165.0):
        b = np.radians(truth)
        s = X * np.cos(b) + Y * np.sin(b)
        img = np.sin(2 * np.pi * s / 3.0).astype("float32")
        ang, _, sm = sweep(img, step=1.0)
        got = bearing_from_rotation(float(ang[int(np.argmax(sm))]))
        off = abs(((got - truth + 90) % 180) - 90)
        if off > 2.0:
            raise SystemExit(
                f"bearing calibration broken: synthetic {truth} deg "
                f"came back as {got} deg")


def read_window():
    h = SIDE / 2
    b = (CX - h, CY - h, CX + h, CY + h)
    with rasterio.open(LRM) as s:
        a = s.read(1, window=from_bounds(*b, transform=s.transform)).astype("float32")
        nd = s.nodata
    if nd is not None:
        a[a == nd] = np.nan
    return np.nan_to_num(a, nan=float(np.nanmean(a)))


def spacing_of(prof):
    p = prof - prof.mean()
    power = np.abs(np.fft.rfft(p * np.hanning(p.size))) ** 2
    freq = np.fft.rfftfreq(p.size, d=CELL)
    lam = np.divide(1.0, freq, out=np.full_like(freq, np.inf), where=freq > 0)
    ok = (lam <= p.size * CELL / 4) & (lam >= 2 * CELL)
    return float(lam[ok][int(np.argmax(power[ok]))])


def main() -> int:
    if not LRM.exists():
        raise SystemExit(f"missing: {LRM}")
    _selftest()
    a = read_window()

    angles, var_raw, var = sweep(a)
    best = float(angles[int(np.argmax(var))])
    bearing = bearing_from_rotation(best)

    prof = profile_at(a, best) * 100.0
    x = np.arange(prof.size) * CELL
    spacing = spacing_of(prof)
    pk, _ = find_peaks(prof, distance=max(2, int(0.5 * spacing / CELL)))
    rows = x[pk]

    # variance at the two bearings the geometry predicts, for comparison
    def var_at(bear):
        rot = (180.0 - bear) % 180.0
        i = int(round(rot)) % len(var)
        return float(var[i])
    v_scan, v_flight, v_best = (var_at(SCAN_BEARING),
                                var_at(FLIGHT_BEARING), float(var.max()))

    fig, axes = plt.subplots(1, 3, figsize=(16.6, 6.0))
    fig.patch.set_facecolor(PAPER)

    ax = axes[0]
    lo, hi = np.nanpercentile(a, (2, 98))
    ax.imshow(a, cmap="gray", vmin=lo, vmax=hi, extent=(0, SIDE, 0, SIDE))
    br = np.radians(bearing)
    L = SIDE
    for r in rows[::3]:
        d = r - x.mean()
        px, py = SIDE / 2 + d * np.cos(br), SIDE / 2 - d * np.sin(br)
        ax.plot([px - L * np.sin(br), px + L * np.sin(br)],
                [py - L * np.cos(br), py + L * np.cos(br)],
                color=ORANGE, lw=0.9, alpha=0.7)
    ax.set_xlim(0, SIDE); ax.set_ylim(0, SIDE)
    ax.set_title("Local relief, 0.5 m", loc="left", fontsize=15,
                 fontweight="bold", color=INK, pad=9)
    ax.set_xticks([]); ax.set_yticks([])

    ax = axes[1]
    bx = bearing_from_rotation(angles)
    o = np.argsort(bx)                     # else the polyline wraps 0<->179
    ax.plot(bx[o], var_raw[o], color=GREYLINE, lw=0.9, alpha=0.8,
            label="raw")
    ax.plot(bx[o], var[o], color=BLUE, lw=2.0, label="median, 7°")
    ax.axvline(bearing, color=ORANGE, lw=2.0,
               label=f"peak {bearing:.0f}°")
    ax.axvline(SCAN_BEARING, color=GREYLINE, lw=1.6, ls=(0, (5, 3)),
               label=f"scan lines {SCAN_BEARING:.0f}°")
    ax.axvline(FLIGHT_BEARING, color=GREYLINE, lw=1.6, ls=(0, (1, 2)),
               label=f"flight lines {FLIGHT_BEARING:.0f}°")
    ax.set_title("How much stripe sits at each direction", loc="left",
                 fontsize=15, fontweight="bold", color=INK, pad=9)
    ax.set_xlabel("bearing of the stripes, degrees", fontsize=11.5,
                  color=MUTED)
    ax.set_ylabel("variance of the cross-strike profile", fontsize=11.5,
                  color=MUTED)
    ax.set_xlim(0, 180)
    ax.legend(fontsize=10, framealpha=0.9)

    ax = axes[2]
    ax.plot(x, prof, color=BLUE, lw=1.5)
    for r in rows:
        ax.axvline(r, color=ORANGE, lw=0.8, alpha=0.5)
    ax.axhline(0, color="#c8c8c0", lw=1)
    ax.set_title(f"Cross-strike profile at {bearing:.0f}°", loc="left",
                 fontsize=15, fontweight="bold", color=INK, pad=9)
    ax.set_xlabel("distance across the stripes, metres", fontsize=11.5,
                  color=MUTED)
    ax.set_ylabel("local relief, centimetres", fontsize=11.5, color=MUTED)
    ax.set_xlim(0, x.max())

    for ax in axes[1:]:
        ax.grid(axis="y", color="#e9e9e1", lw=0.9)
        ax.set_axisbelow(True)
        ax.tick_params(colors=MUTED, labelsize=10)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"):
            ax.spines[sp].set_edgecolor("#c8c8c0")
    for sp in axes[0].spines.values():
        sp.set_edgecolor("#c8c8c0")

    fig.suptitle("Where the stripes are, measured rather than eyeballed",
                 x=0.006, y=0.985, ha="left", va="top", fontsize=20,
                 fontweight="bold", color=INK)
    fig.tight_layout(rect=(0, 0.015, 1, 0.935))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=155, facecolor=PAPER)
    plt.close(fig)

    amp = float(np.percentile(prof, 95) - np.percentile(prof, 5))
    print(f"  measured bearing   {bearing:6.1f} deg")
    print(f"  scan-line bearing  {SCAN_BEARING:6.1f} deg   "
          f"variance {v_scan/v_best*100:5.1f}% of peak")
    print(f"  flight-line bearing{FLIGHT_BEARING:6.1f} deg   "
          f"variance {v_flight/v_best*100:5.1f}% of peak")
    print(f"  spacing            {spacing:6.2f} m")
    print(f"  crests             {len(rows)}")
    print(f"  amplitude          {amp:6.2f} cm (5-95%)")
    print(f"  {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
