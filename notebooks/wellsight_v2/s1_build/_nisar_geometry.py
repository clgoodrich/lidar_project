"""Stage 2 of docs/iterations/nisar_regeocode_plan_9t.md: NISAR radar geometry in plain numpy/scipy.

No ISCE3 (it does not run on Windows). Every function works on flat arrays of points.

Conventions (all checked against NASA's own GSLC in check V1, see the plan doc):
  * Times are seconds since midnight of the acquisition date, as in the RSLC file.
  * Orbit positions and velocities are WGS84 ECEF metres.
  * The RSLC is focused to zero Doppler. A ground point is imaged at the time t where
    (P - S(t)) . V(t) = 0, at slant range |P - S(t)|.
  * Heights are metres above the WGS84 ellipsoid.
"""
from __future__ import annotations

import numpy as np
from pyproj import Transformer
from scipy.interpolate import CubicHermiteSpline, RectBivariateSpline, RegularGridInterpolator

C = 299_792_458.0
WGS84_A = 6_378_137.0
WGS84_E2 = 6.69437999014e-3
SINC_TAPS = 8


# ---------- coordinates ----------

def utm_to_lonlat(x, y, epsg=32617):
    tf = Transformer.from_crs(f"EPSG:{epsg}", "EPSG:4326", always_xy=True)
    return tf.transform(x, y)


def lonlat_to_ecef(lon, lat, h):
    lo, la = np.radians(lon), np.radians(lat)
    n = WGS84_A / np.sqrt(1 - WGS84_E2 * np.sin(la) ** 2)
    return np.stack([(n + h) * np.cos(la) * np.cos(lo),
                     (n + h) * np.cos(la) * np.sin(lo),
                     (n * (1 - WGS84_E2) + h) * np.sin(la)], axis=-1)


# ---------- heights ----------

def dem_heights(path, lon, lat, order=5):
    """Sample a point-registered EPSG:4326 DEM with a spline of the given order (5 = quintic,
    closest to the biquintic interpolation NASA's GSLC metadata names)."""
    import rasterio
    with rasterio.open(path) as s:
        t = s.transform
        c0 = int(np.floor((lon.min() - t.c) / t.a)) - 8
        c1 = int(np.ceil((lon.max() - t.c) / t.a)) + 8
        r0 = int(np.floor((lat.max() - t.f) / t.e)) - 8
        r1 = int(np.ceil((lat.min() - t.f) / t.e)) + 8
        z = s.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
    # AREA_OR_POINT=Point: the transform origin is half a pixel off the first sample
    lon_ax = t.c + (np.arange(c0, c1) + 0.5) * t.a
    lat_ax = t.f + (np.arange(r0, r1) + 0.5) * t.e
    spl = RectBivariateSpline(lat_ax[::-1], lon_ax, z[::-1], kx=order, ky=order)
    return spl.ev(lat, lon)


def _local_spline_weights(frac):
    """Weights of a natural cubic spline through 6 unit-spaced samples, evaluated at 2 + frac."""
    from scipy.interpolate import CubicSpline
    return CubicSpline(np.arange(6), np.eye(6), bc_type="natural")(2 + frac)   # (N, 6)


def dem_heights_isce(path, lon, lat, half_pixel=0.0):
    """ISCE-style "biquintic": a natural cubic spline through the 6 x 6 neighbouring DEM samples,
    first along each row, then down the column. half_pixel shifts the sample origin (in pixels)
    to test the pixel-is-point convention."""
    import rasterio
    with rasterio.open(path) as s:
        t = s.transform
        fx = (lon - t.c) / t.a - half_pixel
        fy = (lat - t.f) / t.e - half_pixel
        c0, r0 = int(np.floor(fx.min())) - 4, int(np.floor(fy.min())) - 4
        c1, r1 = int(np.ceil(fx.max())) + 5, int(np.ceil(fy.max())) + 5
        z = s.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
    fx, fy = fx - c0, fy - r0
    ix, iy = np.floor(fx).astype(int), np.floor(fy).astype(int)
    wx = _local_spline_weights(fx - ix)
    wy = _local_spline_weights(fy - iy)
    k = np.arange(-2, 4)
    blk = z[(iy[:, None] + k)[:, :, None], (ix[:, None] + k)[:, None, :]]   # (N, 6 rows, 6 cols)
    return np.einsum("ni,nij,nj->n", wy, blk, wx)


def geoid_offset(grid_url, lon, lat):
    """Geoid height N (m above the ellipsoid) from a PROJ geoid grid, e.g.
    https://cdn.proj.org/us_noaa_g2012bu0.tif (Geoid12B). Ellipsoid height = orthometric + N."""
    import rasterio
    with rasterio.open(f"/vsicurl/{grid_url}") as s:
        t = s.transform
        lon_w = np.where(lon < 0, lon + 360, lon) if t.c > 0 else lon
        c0 = int(np.floor((lon_w.min() - t.c) / t.a)) - 2
        c1 = int(np.ceil((lon_w.max() - t.c) / t.a)) + 3
        r0 = int(np.floor((lat.max() - t.f) / t.e)) - 2
        r1 = int(np.ceil((lat.min() - t.f) / t.e)) + 3
        z = s.read(1, window=((r0, r1), (c0, c1))).astype(np.float64)
    lon_ax = t.c + (np.arange(c0, c1) + 0.5) * t.a
    lat_ax = t.f + (np.arange(r0, r1) + 0.5) * t.e
    f = RegularGridInterpolator((lat_ax[::-1], lon_ax), z[::-1], method="linear")
    return f(np.c_[lat, lon_w])


# ---------- orbit and zero-Doppler geometry ----------

class Orbit:
    """Cubic Hermite interpolation of the state vectors (positions with velocities as slopes)."""

    def __init__(self, t, pos, vel):
        self.t0 = float(t[0])
        tt = np.asarray(t, float) - self.t0
        self.p = CubicHermiteSpline(tt, pos, vel, axis=0)
        self.v = self.p.derivative()
        self.a = self.v.derivative()

    def __call__(self, t):
        tt = np.asarray(t) - self.t0
        return self.p(tt), self.v(tt), self.a(tt)


def zero_doppler(orbit, P, t_guess, iters=12, tol=1e-9):
    """Solve (P - S(t)) . V(t) = 0 by Newton. Returns time and slant range per point."""
    t = np.broadcast_to(np.asarray(t_guess, float), P.shape[:1]).copy()
    for _ in range(iters):
        S, V, A = orbit(t)
        d = P - S
        f = np.einsum("ij,ij->i", d, V)
        fp = -np.einsum("ij,ij->i", V, V) + np.einsum("ij,ij->i", d, A)
        dt = f / fp
        t -= dt
        if np.max(np.abs(dt)) < tol:
            break
    S, _, _ = orbit(t)
    return t, np.linalg.norm(P - S, axis=1)


def geogrid_to_radar(gg, x, y, h, epsg_out=32617):
    """Independent route for check C0: invert the RSLC geolocationGrid (height, time, range) -> map
    x, y. Per height layer, time and range are fitted as cubic polynomials in x, y over the cut
    grid, then interpolated linearly in height."""
    tf = Transformer.from_crs(f"EPSG:{int(gg['epsg'][()])}", f"EPSG:{epsg_out}", always_xy=True)
    gt, gr, gh = gg["zeroDopplerTime"][:], gg["slantRange"][:], gg["heightAboveEllipsoid"][:]
    T, R = np.meshgrid(gt, gr, indexing="ij")
    xc, yc = x.mean(), y.mean()

    def design(u, v):
        u, v = (u - xc) / 1e3, (v - yc) / 1e3
        return np.stack([u ** i * v ** j for i in range(4) for j in range(4 - i)], axis=-1)

    tl, rl = [], []
    for k in range(len(gh)):
        X, Y = tf.transform(gg["coordinateX"][k], gg["coordinateY"][k])
        A = design(X.ravel(), Y.ravel())
        ct, *_ = np.linalg.lstsq(A, T.ravel(), rcond=None)
        cr, *_ = np.linalg.lstsq(A, R.ravel(), rcond=None)
        D = design(x, y)
        tl.append(D @ ct)
        rl.append(D @ cr)
    tl, rl = np.array(tl), np.array(rl)
    k = np.clip(np.searchsorted(gh, h) - 1, 0, len(gh) - 2)
    w = (h - gh[k]) / (gh[k + 1] - gh[k])
    i = np.arange(len(x))
    return (1 - w) * tl[k, i] + w * tl[k + 1, i], (1 - w) * rl[k, i] + w * rl[k + 1, i]


# ---------- corrections ----------

def lut2d(t_axis, r_axis, table, t, r):
    """Bilinear lookup in a (time, range) table, clamped at the edges."""
    f = RegularGridInterpolator((t_axis, r_axis), table, bounds_error=False, fill_value=None)
    return f(np.c_[np.clip(t, t_axis[0], t_axis[-1]), np.clip(r, r_axis[0], r_axis[-1])])


def dry_tropo_slant_delay(h, lat, incidence_deg):
    """Zenith hydrostatic delay (Saastamoinen, standard-atmosphere pressure) mapped by 1/cos(inc)."""
    p = 1013.25 * (1 - 2.2557e-5 * h) ** 5.2559
    zhd = 0.0022768 * p / (1 - 0.00266 * np.cos(2 * np.radians(lat)) - 0.00028e-3 * h)
    return zhd / np.cos(np.radians(incidence_deg))


# ---------- resampling ----------

def _kernel(frac, beta=1.0):
    """8-tap Hann-windowed sinc weights for fractional offsets frac (N,) -> (N, 8).
    beta < 1 low-passes to beta x the sample rate (the signal bandwidth over the sample rate)."""
    k = np.arange(-SINC_TAPS // 2 + 1, SINC_TAPS // 2 + 1)        # -3..4
    x = k[None, :] - frac[:, None]
    w = beta * np.sinc(beta * x) * (0.5 + 0.5 * np.cos(np.pi * x / (SINC_TAPS / 2 + 1)))
    return w / w.sum(axis=1, keepdims=True), k


def sinc_interp(slc, row, col, beta_row=1.0, beta_col=1.0, chunk=200_000):
    """Complex 2-D separable sinc interpolation at fractional (row, col). The caller removes any
    azimuth Doppler carrier first and restores it after (see _nisar_regeocode_lidar_9t.resample)."""
    out = np.full(row.shape, np.nan + 0j, np.complex64)
    n0, n1 = slc.shape
    for a in range(0, len(row), chunk):
        r, c = row[a:a + chunk], col[a:a + chunk]
        ri, ci = np.floor(r).astype(int), np.floor(c).astype(int)
        ok = (ri >= SINC_TAPS) & (ri < n0 - SINC_TAPS) & (ci >= SINC_TAPS) & (ci < n1 - SINC_TAPS)
        wr, k = _kernel(r[ok] - ri[ok], beta_row)
        wc, _ = _kernel(c[ok] - ci[ok], beta_col)
        rr = ri[ok][:, None] + k[None, :]            # (N, 8)
        cc = ci[ok][:, None] + k[None, :]
        block = slc[rr[:, :, None], cc[:, None, :]]  # (N, 8, 8)
        v = np.einsum("ni,nij,nj->n", wr, block, wc)
        tmp = out[a:a + chunk]
        tmp[ok] = v
        out[a:a + chunk] = tmp
    return out


def flatten(slc, slant_range, wavelength, sign=+1):
    """Remove the geometric range phase: multiply by exp(sign * j 4 pi r / lambda)."""
    return slc * np.exp(sign * 1j * 4 * np.pi * slant_range / wavelength)


# ---------- terrain correction and masks (Small 2011) ----------

def local_incidence(dem, res, los_enu):
    """cos of the local incidence angle per DEM cell, and the slope rising toward the satellite.
    los_enu: unit vector ground -> satellite (east, north, up). Rows run south."""
    gy, gx = np.gradient(dem, res)
    dzdx, dzdn = gx, -gy
    nz = 1 / np.sqrt(1 + dzdx ** 2 + dzdn ** 2)
    cos_loc = (-dzdx * los_enu[0] - dzdn * los_enu[1] + los_enu[2]) * nz
    lh = np.hypot(los_enu[0], los_enu[1])
    toward = (dzdx * los_enu[0] + dzdn * los_enu[1]) / lh
    return cos_loc, toward, nz


def layover_shadow(dem, res, los_enu, incidence_deg):
    """1 = layover (slope toward the satellite steeper than the incidence), 2 = shadow (facing away)."""
    cos_loc, toward, _ = local_incidence(dem, res, los_enu)
    m = np.zeros(dem.shape, np.uint8)
    m[toward > np.tan(np.radians(incidence_deg))] = 1
    m[cos_loc <= 0] = 2
    return m


def rtc_area_factor(dem, res, los_enu):
    """Illuminated area of each facet relative to flat ground: max(cos_loc, 0) / (nz cos(inc))."""
    cos_loc, _, nz = local_incidence(dem, res, los_enu)
    return np.clip(cos_loc, 0, None) / nz / los_enu[2]
