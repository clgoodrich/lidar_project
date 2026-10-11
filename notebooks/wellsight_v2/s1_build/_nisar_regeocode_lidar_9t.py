"""Stage 3 of docs/iterations/nisar_regeocode_plan_9t.md: place RSLC samples on the 9t 5 m grid.

Heights:
  --heights nisar_dem   NASA's own DEM (NISAR DEM v1.2, ellipsoid heights). Check V1: the result
                        must reproduce NASA's GSLC before anything else is trusted.
  --heights lidar       the 1 m lidar bare earth, converted NAVD88 -> ellipsoid (production).

For each output pixel: map x, y -> lon, lat -> height -> ECEF -> zero-Doppler time and slant range
from the orbit -> timing corrections -> fractional RSLC row and column -> 8-tap sinc interpolation
with the azimuth Doppler carrier removed and restored -> range phase flattening.

Conventions were settled by the V1 sweep and live in CONV; the numbers are in the plan doc.

Run (check V1, NASA's DEM, one pair per track plus one beta pair):
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --v1       20260917_t162A:20260929_t162A 20260924_t090A:20261006_t090A       20260920_t026D:20261002_t026D 20251109_t162A:20251121_t162A
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _nisar_geometry as geo  # noqa: E402
import _fetch_nisar_gslc_window_9t as gfetch  # noqa: E402

D9 = gfetch.path_for("data") / "9t"
RS = D9 / "derived" / "nisar_rslc_window"
GS = D9 / "derived" / "nisar_gslc_5m"
NDEM = D9 / "derived" / "nisar_dem" / "DEM_N41_00_W080_00_C01.tif"
OUTD = D9 / "derived" / "nisar_slc_lidar_5m"
RES = D9 / "results" / "nisar"
TIMING = "science/LSAR/GSLC/metadata/processingInformation/timingCorrections/frequencyA"


def gslc_timing(rs_path, gslc_granule):
    """Timing-correction tables from the matching GSLC, cached inside the RSLC window file."""
    with h5py.File(rs_path, "a") as o:
        if "gslcTimingCorrections" not in o:
            import fsspec
            q = gfetch.query().set_index("granule")
            for attempt in range(4):        # the Earthdata login server times out now and then
                try:
                    f = fsspec.filesystem("http").open(gfetch.signed_url(q.loc[gslc_granule, "url"]),
                                                       block_size=2 * 2**20, cache_type="blockcache")
                    with h5py.File(f, "r") as h:
                        h.copy(h[TIMING], o, name="gslcTimingCorrections")
                    break
                except Exception as e:  # noqa: BLE001
                    print("timing fetch retry", attempt + 1, repr(e)[:120], flush=True)
                    time.sleep(20)
            else:
                raise RuntimeError(f"could not read timing tables for {gslc_granule}")
        g = o["gslcTimingCorrections"]
        return {k: g[k][()] for k in g}


def load_rslc(path):
    with h5py.File(path, "r") as o:
        d = dict(HH=o["HH"][:], HV=o["HV"][:], zt=o["zeroDopplerTime"][:], sr=o["slantRange"][:],
                 t_units=o["zeroDopplerTime"].attrs["units"],
                 orbit=geo.Orbit(o["orbit/time"][:], o["orbit/position"][:], o["orbit/velocity"][:]),
                 orbit_units=o["orbit/time"].attrs["units"],
                 fdc=(o["parameters/frequencyA/zeroDopplerTime"][:], o["parameters/frequencyA/slantRange"][:],
                      o["parameters/frequencyA/dopplerCentroid"][:]),
                 gg={k: o["geolocationGrid"][k][()] for k in o["geolocationGrid"]})
    if d["t_units"] != d["orbit_units"]:
        raise RuntimeError(f"time epochs differ: {d['t_units']} vs {d['orbit_units']}")
    return d


def output_grid(row):
    x = row.x_first_centre + row.spacing_m * np.arange(row.ncols)
    y = row.y_first_centre - row.spacing_m * np.arange(row.nrows)
    X, Y = np.meshgrid(x, y)
    return X.ravel(), Y.ravel(), (int(row.nrows), int(row.ncols))


def lidar_heights(lon, lat, X, Y):
    """Placeholder until V1 passes; production heights are wired in after it."""
    raise NotImplementedError("lidar heights are enabled only after check V1 passes")


def geometry(rs, X, Y, heights):
    lon, lat = geo.utm_to_lonlat(X, Y)
    h = geo.dem_heights(NDEM, lon, lat) if heights == "nisar_dem" else lidar_heights(lon, lat, X, Y)
    P = geo.lonlat_to_ecef(lon, lat, h)
    t_gg, r_gg = geo.geogrid_to_radar(rs["gg"], X, Y, h)
    t, r = geo.zero_doppler(rs["orbit"], P, t_gg)
    return dict(lon=lon, lat=lat, h=h, t=t, r=r, t_gg=t_gg, r_gg=r_gg)


def incidence_from_grid(gg, r, h):
    """Incidence angle per point from the geolocation grid (mean over time, linear in range)."""
    k = int(np.argmin(np.abs(gg["heightAboveEllipsoid"] - np.median(h))))
    inc = gg["incidenceAngle"][k].mean(axis=0)
    return np.interp(r, gg["slantRange"], inc)


def corrections(rs, tim, g, which):
    """Slant-range and azimuth-time corrections. 'which' is a set of names to apply."""
    t, r = g["t"], g["r"]
    dr = np.zeros_like(r)
    dt = np.zeros_like(t)
    lut = lambda name: geo.lut2d(tim["zeroDopplerTime"], tim["slantRange"], tim[name], t, r)  # noqa: E731
    if "set" in which:
        dr += lut("slantRangeSolidEarthTides")
    if "iono" in which:
        dr += lut("slantRangeIonosphere")
        dt += lut("azimuthIonosphere")
    if "tropo" in which:
        dr += geo.dry_tropo_slant_delay(g["h"], g["lat"], incidence_from_grid(rs["gg"], r, g["h"]))
    return dt, dr


def resample(rs, t, r, pol, carrier=True, beta=(1.0, 1.0)):
    """Sinc-interpolate one polarization at times t and ranges r. With carrier=True the azimuth
    Doppler carrier exp(j 2 pi fdc (t - tref)) is removed from the window first and restored at
    each output point, so the output keeps it."""
    zt, sr = rs["zt"], rs["sr"]
    row = (t - zt[0]) / (zt[1] - zt[0])
    col = (r - sr[0]) / (sr[1] - sr[0])
    slc = rs[pol]
    if not carrier:
        return geo.sinc_interp(slc, row, col, *beta)
    ft, fr, fd = rs["fdc"]
    tref = zt[len(zt) // 2]
    T, R = np.meshgrid(zt, sr, indexing="ij")
    ph = 2 * np.pi * geo.lut2d(ft, fr, fd, T.ravel(), R.ravel()).reshape(T.shape) * (T - tref)
    out = geo.sinc_interp(slc * np.exp(-1j * ph).astype(np.complex64), row, col, *beta)
    return out * np.exp(1j * 2 * np.pi * geo.lut2d(ft, fr, fd, t, r) * (t - tref))


def compare(ours, nasa, shape):
    """V1 numbers: amplitude offset (pixels), 5 x 5 complex coherence, high-passed phase spread."""
    from scipy.ndimage import uniform_filter
    from skimage.registration import phase_cross_correlation
    a, b = ours.reshape(shape), nasa.reshape(shape)
    m = np.isfinite(a) & np.isfinite(b) & (np.abs(b) > 0)
    sl = np.s_[20:-20, 20:-20]
    A, B = np.where(m, np.abs(a), 0)[sl], np.where(m, np.abs(b), 0)[sl]
    shift, _, _ = phase_cross_correlation(B, A, upsample_factor=50, normalization=None)
    amp_r = float(np.corrcoef(A[m[sl]], B[m[sl]])[0, 1])
    p = np.where(m, a * np.conj(b), 0)
    num = np.abs(uniform_filter(p.real, 5) + 1j * uniform_filter(p.imag, 5))
    den = np.sqrt(uniform_filter(np.where(m, np.abs(a) ** 2, 0), 5) * uniform_filter(np.where(m, np.abs(b) ** 2, 0), 5))
    coh = (num / np.maximum(den, 1e-12))[sl][m[sl]]
    # phase difference minus its own 50 m smooth (removes slow ramps from tides/ionosphere)
    sm = uniform_filter(p.real, 11) + 1j * uniform_filter(p.imag, 11)
    hp = np.angle(p * np.conj(sm))[sl][m[sl]]
    return dict(amp_offset_row_px=round(float(shift[0]), 3), amp_offset_col_px=round(float(shift[1]), 3),
                amp_corr=round(amp_r, 3), coh5_median=round(float(np.median(coh)), 3),
                phase_hp_std_rad=round(float(np.std(hp)), 3),
                phase_mean_rad=round(float(np.angle(p[sl][m[sl]].sum())), 3))


# Conventions fixed by the V1 sweep on 2026-09-29 track 162 (plan doc, "Check V1 result"):
CONV = dict(corr=("iono",), carrier=True, sign=+1, dem="isce_spline", dem_half_pixel=0.5)


def heights_for(lon, lat, X, Y, heights):
    if heights == "nisar_dem":
        return geo.dem_heights_isce(NDEM, lon, lat, CONV["dem_half_pixel"])
    return lidar_heights(lon, lat, X, Y)


def make_slc(date_key, heights="nisar_dem", pols=("HH",)):
    """One date on its GSLC 5 m grid. Returns dict of complex arrays (shape of the grid) and info."""
    ri = pd.read_csv(RS / "nisar_rslc_window_index_9t.csv")
    gi = pd.read_csv(GS / "nisar_gslc_window_index_9t_5m.csv")
    rrow = ri[ri.file == f"nisar_rslc_window_{date_key}_9t.h5"].iloc[0]
    grow = gi[(gi.date == rrow.date) & (gi.track == rrow.track)].iloc[0]
    rs = load_rslc(RS / rrow.file)
    tim = gslc_timing(RS / rrow.file, grow.granule)
    X, Y, shape = output_grid(grow)
    lon, lat = geo.utm_to_lonlat(X, Y)
    h = heights_for(lon, lat, X, Y, heights)
    P = geo.lonlat_to_ecef(lon, lat, h)
    t_gg, r_gg = geo.geogrid_to_radar(rs["gg"], X, Y, h)
    t, r = geo.zero_doppler(rs["orbit"], P, t_gg)
    g = dict(t=t, r=r, h=h, lat=lat)
    dt, dr = corrections(rs, tim, g, set(CONV["corr"]))
    lam = geo.C / grow.centre_frequency_hz
    out = {}
    for pol in pols:
        v = resample(rs, t + dt, r + dr, pol, carrier=CONV["carrier"])
        out[pol] = geo.flatten(v, r, lam, CONV["sign"]).reshape(shape)
    info = dict(grow=grow, rrow=rrow, shape=shape, h=h.reshape(shape),
                c0_time_max_abs_s=float(np.max(np.abs(t - t_gg))),
                c0_range_max_abs_m=float(np.max(np.abs(r - r_gg))))
    return out, info


def nasa_slc(grow, band=1):
    with rasterio.open(GS / grow.file) as s:
        return s.read(band)


def compare_ifg(o1, o2, n1, n2):
    """Our interferogram against NASA's for the same pair. The flattening height cancels here."""
    from scipy.ndimage import uniform_filter
    io, inn = o1 * np.conj(o2), n1 * np.conj(n2)
    m = np.isfinite(io) & np.isfinite(inn) & (np.abs(inn) > 0)
    q = np.where(m, io * np.conj(inn), 0)
    sm = lambda a: uniform_filter(a, 5)  # noqa: E731
    num = np.abs(sm(q.real) + 1j * sm(q.imag))
    den = np.sqrt(sm(np.where(m, np.abs(io) ** 2, 0)) * sm(np.where(m, np.abs(inn) ** 2, 0)))
    sl = np.s_[20:-20, 20:-20]
    coh = (num / np.maximum(den, 1e-12))[sl][m[sl]]
    look = np.angle(sm(q.real) + 1j * sm(q.imag))[sl][m[sl]]
    # natural coherence of NASA's own pair, for context
    nat = np.abs(sm(inn.real) + 1j * sm(inn.imag)) / np.sqrt(sm(np.abs(n1) ** 2) * sm(np.abs(n2) ** 2))
    return dict(ifg_match_coh5_median=round(float(np.median(coh)), 3),
                ifg_match_phase5_std_rad=round(float(np.std(look)), 3),
                ifg_match_phase_mean_rad=round(float(np.angle(q[sl][m[sl]].sum())), 3),
                nasa_pair_coherence5_median=round(float(np.nanmedian(nat[sl])), 3))


def run_v1(pairs):
    rows = []
    cache = {}
    for d1, d2 in pairs:
        for d in (d1, d2):
            if d not in cache:
                t0 = time.time()
                o, info = make_slc(d)
                n = nasa_slc(info["grow"])
                single = compare(o["HH"].ravel(), n.ravel(), info["shape"])
                cache[d] = (o["HH"], n, info)
                rows.append(dict(check="V1 single date", date=d, collection=info["rrow"].collection,
                                 **single, c0_time_max_abs_s=info["c0_time_max_abs_s"],
                                 c0_range_max_abs_m=info["c0_range_max_abs_m"],
                                 seconds=round(time.time() - t0, 1)))
                print(rows[-1], flush=True)
        r = compare_ifg(cache[d1][0], cache[d2][0], cache[d1][1], cache[d2][1])
        rows.append(dict(check="V1 interferogram", date=f"{d1}-{d2}", **r))
        print(rows[-1], flush=True)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heights", default="nisar_dem", choices=["nisar_dem", "lidar"])
    ap.add_argument("--v1", nargs="+", help="date pairs as d1:d2, e.g. 20260917_t162A:20260929_t162A")
    a = ap.parse_args()
    if a.heights != "nisar_dem":
        raise SystemExit("lidar heights are enabled only after V1 passes")
    rows = run_v1([tuple(p.split(":")) for p in a.v1])
    RES.mkdir(exist_ok=True)
    p = RES / "nisar_regeocode_v1_checks_9t.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    print("wrote", p)


if __name__ == "__main__":
    main()
