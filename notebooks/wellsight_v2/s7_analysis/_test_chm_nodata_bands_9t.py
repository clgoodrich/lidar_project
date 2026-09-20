"""What are the bright parallel bands in the CHM? They are NoData.

Supersedes `_test_chm_scanline_streaks_9t.py`, which asked the same question
with the wrong mask and therefore got a real-looking but meaningless answer.

THE MISTAKE THAT MADE THE OLD SCRIPT WRONG
------------------------------------------
matplotlib paints NaN as the FIGURE BACKGROUND. On the panel's black-to-white
greyscale ramp the background is brighter than the maximum value, so a missing
cell renders brighter than 27.9 m of canopy. The bands in `chm_300m_9t.png` are
not tall vegetation. They are holes.

The old script selected its mask with `chm >= percentile(chm, 99.3)`, which by
construction keeps only cells that HAVE a value -- the exact complement of the
bands it was trying to measure. Its headline number, 21% single-return on the
streaks against 70% off them, is therefore canopy-versus-ground and says
nothing about the bands. Do not quote it.

WHAT THIS ONE DOES
------------------
Mask = `~isfinite(chm)`. Then:
  1. Confirm the voids are collinear and evenly spaced (same estimator as
     before -- it validates exactly against synthetic lines; only the mask was
     ever wrong).
  2. Check whether the hole is in the DSM, the DEM, or both. CHM = DSM - DEM,
     so a CHM hole is inherited from whichever input is missing.
  3. Go to the point cloud and ask how many returns fall inside a void cell.
     A DSM cell is empty because no return landed in it, so the decisive
     measurement is RETURN DENSITY, not return attributes.

Run:
    python notebooks/wellsight_v2/s7_analysis/_test_chm_nodata_bands_9t.py
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
    a[a < -1000.0] = np.nan
    return a


def radon_orientation(mask):
    """Bearing that maximises the variance of the projected mask.

    The projection angle IS the map bearing, clockwise from north. The old
    script applied a `(90 - ang)` conversion, which is wrong: calibrated here
    against synthetic lines at 0/30/45/79/120/135 deg, the estimator returns
    each bearing unchanged. So the three bearings on record (121/135/139) were
    wrong twice over -- wrong mask and wrong conversion.
    """
    from scipy.ndimage import rotate
    best, prof = (None, -1.0), {}
    for ang in np.arange(0.0, 180.0, 0.5):
        r = rotate(mask.astype(np.float32), ang, reshape=False, order=0,
                   mode="constant", cval=0.0)
        v = float(np.var(r.sum(axis=0)))
        prof[float(ang)] = v
        if v > best[1]:
            best = (float(ang), v)
    return best[0], prof


def spacing_from_projection(mask, ang):
    from scipy.ndimage import rotate
    from scipy.signal import find_peaks
    r = rotate(mask.astype(np.float32), ang, reshape=False, order=0,
               mode="constant", cval=0.0)
    p = r.sum(axis=0)
    if p.max() <= 0:
        return None, 0
    pk, _ = find_peaks(p, height=0.35 * p.max(), distance=2)
    if len(pk) < 3:
        return None, len(pk)
    return float(np.median(np.diff(pk) * RES)), len(pk)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--centre", nargs=2, type=float, default=[LAT, LON])
    ap.add_argument("--side", type=float, default=SIDE)
    a = ap.parse_args()

    b = bounds_of(a.centre[0], a.centre[1], a.side)
    chm = read_window(D05 / "chm_9t_05.tif", b)
    dsm = read_window(D05 / "dsm_9t_05.tif", b)
    dem = read_window(D05 / "dem_9t_05.tif", b)
    print(f"window {b[0]:.1f},{b[1]:.1f} - {b[2]:.1f},{b[3]:.1f}   CHM {chm.shape}")

    void = ~np.isfinite(chm)
    print(f"\n  CHM NoData: {void.sum():,} cells "
          f"({100*void.mean():.2f}% of the window)")
    print(f"  DSM NoData: {int((~np.isfinite(dsm)).sum()):,} "
          f"({100*(~np.isfinite(dsm)).mean():.2f}%)")
    print(f"  DEM NoData: {int((~np.isfinite(dem)).sum()):,} "
          f"({100*(~np.isfinite(dem)).mean():.2f}%)")
    both = void & ~np.isfinite(dsm)
    print(f"  CHM holes that are also DSM holes: {int(both.sum()):,} "
          f"({100*both.sum()/max(void.sum(),1):.1f}% of them)")

    ang, _ = radon_orientation(void)
    bearing = ang % 180.0
    sp, npk = spacing_from_projection(void, ang)
    print(f"\n  voids run at bearing {bearing:.1f} deg "
          f"(projection angle {ang:.1f})")
    print(f"  spacing {sp if sp is None else round(sp, 2)} m from {npk} peaks")

    # ---- return density inside a void cell vs a valid cell
    import laspy
    l, bb, r_, t = b
    ny, nx = chm.shape
    n_void_pts = n_valid_pts = 0
    first_void = first_valid = 0
    for f in sorted(SRC.glob("*.laz")):
        las = laspy.read(f)
        x, y = np.asarray(las.x), np.asarray(las.y)
        m = (x >= l) & (x < r_) & (y >= bb) & (y < t)
        if not m.any():
            continue
        x, y = x[m], y[m]
        rn = np.asarray(las.return_number)[m].astype(np.int16)
        ci = np.clip(((x - l) / RES).astype(int), 0, nx - 1)
        ri = np.clip(((t - y) / RES).astype(int), 0, ny - 1)
        inv = void[ri, ci]
        n_void_pts += int(inv.sum())
        n_valid_pts += int((~inv).sum())
        first_void += int((rn[inv] == 1).sum())
        first_valid += int((rn[~inv] == 1).sum())
        print(f"  {f.name}: {int(m.sum()):,} returns in window, "
              f"{int(inv.sum()):,} land in a NoData cell")

    nv, nval = int(void.sum()), int((~void).sum())
    d_void = n_void_pts / max(nv, 1)
    d_valid = n_valid_pts / max(nval, 1)
    print(f"\n  RETURN DENSITY")
    print(f"    NoData cells : {nv:,} cells, {n_void_pts:,} returns "
          f"= {d_void:.2f} per cell   ({first_void:,} first-returns, "
          f"{first_void/max(nv,1):.2f} per cell)")
    print(f"    valid cells  : {nval:,} cells, {n_valid_pts:,} returns "
          f"= {d_valid:.2f} per cell   ({first_valid:,} first-returns, "
          f"{first_valid/max(nval,1):.2f} per cell)")
    print(f"    ratio        : {d_void/max(d_valid,1e-9):.3f}x")

    dens = dict(void_cells=nv, valid_cells=nval,
                void_returns=n_void_pts, valid_returns=n_valid_pts,
                void_first_returns=first_void, valid_first_returns=first_valid,
                void_per_cell=d_void, valid_per_cell=d_valid,
                void_first_per_cell=first_void / max(nv, 1),
                valid_first_per_cell=first_valid / max(nval, 1))

    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / "chm_nodata_bands_300m_9t.json"
    p.write_text(json.dumps(dict(
        bounds=list(b), chm_nodata_cells=nv,
        chm_nodata_pct=float(100 * void.mean()),
        dsm_nodata_pct=float(100 * (~np.isfinite(dsm)).mean()),
        dem_nodata_pct=float(100 * (~np.isfinite(dem)).mean()),
        bearing_deg=bearing, spacing_m=sp, n_peaks=npk,
        density=dens), indent=2), encoding="utf-8")
    print(f"\n  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
