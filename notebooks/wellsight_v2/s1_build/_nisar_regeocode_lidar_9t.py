"""Stage 3 of docs/iterations/nisar_regeocode_plan_9t.md: place RSLC samples on the 9t 5 m grid.

Heights:
  --heights nisar_dem   NASA's own DEM (NISAR DEM v1.2, ellipsoid heights). Check V1: the result
                        must reproduce NASA's GSLC before anything else is trusted.
  --heights lidar       the 1 m lidar bare earth, converted NAVD88 -> ellipsoid (production).

For each output pixel: map x, y -> lon, lat -> height -> ECEF -> zero-Doppler time and slant range
from the orbit -> timing corrections -> fractional RSLC row and column -> 8-tap sinc interpolation
with the azimuth Doppler carrier removed and restored -> range phase flattening.

Conventions were settled by the V1 sweep and live in CONV; the numbers are in the plan doc.

Run (production, lidar heights, every date, HH and HV):
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write
Then line the dates of each track up (2026-10-13; beta dates sit 3.2 m off in slant range and
dusk track 026 dates jump metres along track):
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --estimate-offsets
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write --coreg
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --estimate-offsets   # check: change near 0
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --coherence          # before and after
Then put each track on the lidar (check V3 with forest echo at 10% of stand height):
  python notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar --kappa 0.1
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --track-offsets _coreg_k010
  python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py --heights lidar --write --coreg --absolute

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


LIDAR_DEM = D9 / "derived" / "1m" / "dem_9t_1m.tif"      # NAD83(2011) / UTM 17N, NAVD88 (Geoid12B)
GEOID12B = "https://cdn.proj.org/us_noaa_g2012bu0.tif"
_LIDAR5 = {}


def _lidar_5m():
    """The 1 m bare earth averaged over 5 x 5 cells (one output pixel), cached."""
    if not _LIDAR5:
        from scipy.ndimage import uniform_filter
        with rasterio.open(LIDAR_DEM) as s:
            z = s.read(1, masked=True).filled(np.nan).astype(np.float64)
            tf = s.transform
        ok = np.isfinite(z)
        num = uniform_filter(np.where(ok, z, 0.0), 5, mode="constant")
        den = uniform_filter(ok.astype(np.float64), 5, mode="constant")
        _LIDAR5.update(z=np.where(den > 0.6, num / np.maximum(den, 1e-9), np.nan), tf=tf)
    return _LIDAR5


def lidar_heights(lon, lat, X, Y):
    """WGS84 ellipsoid height of the lidar bare earth under each output pixel.

    The output grid is WGS84 / UTM 17N and NASA's heights are WGS84 ellipsoid heights. ISCE3
    treats WGS84 as ITRF. The lidar is NAD83(2011) with NAVD88 heights. Steps:
      1. ITRF2014 lon, lat -> NAD83(2011) lon, lat (about 1.1 m horizontally at 9t).
      2. Sample the 5 m mean lidar DEM there (bilinear) -> NAVD88 height.
      3. + Geoid12B N (about -33 m) -> NAD83(2011) ellipsoid height.
      4. NAD83(2011) -> ITRF2014 in 3-D (about -1.19 m vertically at 9t).
    PROJ's own NAD83(2011) -> "WGS 84" route is a null transform, so ITRF2014 (EPSG:7912)
    stands in for WGS84. Pixels with no lidar take NASA's DEM and are counted in LAST_FILL.
    """
    from pyproj import Transformer
    from scipy.ndimage import map_coordinates
    to83 = Transformer.from_crs("EPSG:7912", "EPSG:6319", always_xy=True)
    lon83, lat83, _ = to83.transform(lon, lat, np.zeros_like(lon))
    x83, y83 = Transformer.from_crs("EPSG:6318", "EPSG:6346", always_xy=True).transform(lon83, lat83)
    L = _lidar_5m()
    col = (x83 - L["tf"].c) / L["tf"].a - 0.5
    row = (y83 - L["tf"].f) / L["tf"].e - 0.5
    navd = map_coordinates(L["z"], [row, col], order=1, mode="constant", cval=np.nan)
    n = geo.geoid_offset(GEOID12B, lon83, lat83)
    _, _, h = Transformer.from_crs("EPSG:6319", "EPSG:7912", always_xy=True).transform(lon83, lat83, navd + n)
    h = np.asarray(h, dtype=np.float64)
    fill = ~np.isfinite(h)
    if fill.any():
        h[fill] = geo.dem_heights_isce(NDEM, lon[fill], lat[fill], CONV["dem_half_pixel"])
    LAST_FILL["share"] = float(fill.mean())
    return h


LAST_FILL = {}


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


def make_slc(date_key, heights="nisar_dem", pols=("HH",), coreg=(0.0, 0.0)):
    """One date on its GSLC 5 m grid. Returns dict of complex arrays (shape of the grid) and info.

    coreg: (slant range m, azimuth time s) added on top of NASA's timing corrections, from
    the per-date offsets table (estimate_offsets). (0, 0) places the date exactly as NASA does."""
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
    dr, dt = dr + coreg[0], dt + coreg[1]
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


OFFSETS = RES / "nisar_slc_date_offsets_9t.csv"
TRACK_OFFSETS = RES / "nisar_slc_track_offsets_9t.csv"
CORE = np.s_[41:941, 41:941]     # the lidar-covered 900 x 900 cells of the 981 x 981 window


def write_stack(heights, coreg=False, absolute=False):
    """Every RSLC date re-placed with the given heights, HH and HV, on its GSLC 5 m grid.
    With coreg, each date also takes its offsets from OFFSETS (see estimate_offsets). With
    absolute, each track also takes its offset against the lidar from TRACK_OFFSETS."""
    OUTD.mkdir(parents=True, exist_ok=True)
    ri = pd.read_csv(RS / "nisar_rslc_window_index_9t.csv")
    gi = pd.read_csv(GS / "nisar_gslc_window_index_9t_5m.csv")
    tag = "lidar" if heights == "lidar" else "nisardem"
    off = pd.read_csv(OFFSETS).set_index("file") if coreg else None
    trk = pd.read_csv(TRACK_OFFSETS).set_index("track") if absolute else None
    rows = []
    for rrow in ri.itertuples():
        key = rrow.file.replace("nisar_rslc_window_", "").replace("_9t.h5", "")
        name = f"nisar_slc_{tag}_{key}_9t.tif"
        grow = gi[(gi.date == rrow.date) & (gi.track == rrow.track)].iloc[0]
        bad = (str(rrow.date), int(rrow.track)) in gfetch.A.BAD_DATES
        cs = (float(off.loc[name, "slant_m"]), float(off.loc[name, "az_s"])) if coreg and name in off.index else (0.0, 0.0)
        ts = (float(trk.loc[rrow.track, "slant_m"]), float(trk.loc[rrow.track, "az_s"])) if absolute else (0.0, 0.0)
        t0 = time.time()
        o, info = make_slc(key, heights=heights, pols=("HH", "HV"), coreg=(cs[0] + ts[0], cs[1] + ts[1]))
        m = grow
        tf = from_origin(m.x_first_centre - m.spacing_m / 2, m.y_first_centre + m.spacing_m / 2,
                         m.spacing_m, m.spacing_m)
        with rasterio.open(OUTD / name, "w", driver="GTiff", width=info["shape"][1], height=info["shape"][0],
                           count=2, dtype="complex64", crs="EPSG:32617", transform=tf, compress="deflate") as d:
            d.write(o["HH"].astype(np.complex64), 1)
            d.write(o["HV"].astype(np.complex64), 2)
            d.set_band_description(1, "HH")
            d.set_band_description(2, "HV")
        h_nasa = geo.dem_heights_isce(NDEM, *geo.utm_to_lonlat(*output_grid(grow)[:2]), CONV["dem_half_pixel"])
        dh = h_nasa - info["h"].ravel()
        r = grow.to_dict()
        r.update(file=name, rslc=rrow.file, heights=heights,
                 lidar_fill_share=LAST_FILL.get("share", 0.0) if heights == "lidar" else 1.0,
                 nasa_minus_used_height_median_m=round(float(np.nanmedian(dh)), 2),
                 coreg=bool(coreg), coreg_slant_m=cs[0], coreg_az_s=cs[1],
                 absolute=bool(absolute), track_slant_m=ts[0], track_az_s=ts[1], bad_granule=bad,
                 seconds=round(time.time() - t0, 1))
        r.pop("Index", None)
        rows.append(r)
        pd.DataFrame(rows).to_csv(OUTD / f"nisar_slc_{tag}_index_9t.csv", index=False)
        print(name, {k: r[k] for k in ("lidar_fill_share", "nasa_minus_used_height_median_m",
                                       "coreg_slant_m", "coreg_az_s", "seconds")}, flush=True)
    return rows


def radar_offsets(e, n, l, vg):
    """Map shift (east, north m) of a date's content -> slant range (m) and azimuth time (s)
    offsets, plus the shift away from the satellite and forward along track (m).
    Content that sits a m away from the satellite was recorded a sin(incidence) m further in
    slant range. Content f m forward along track was recorded f / vg s later."""
    away = -np.array([l["east"], l["north"]]) / np.hypot(l["east"], l["north"])
    fwd = np.array([l["along_east"], l["along_north"]]) / np.hypot(l["along_east"], l["along_north"])
    a, f = np.linalg.solve(np.c_[away, fwd], [e, n])
    return a * np.sin(np.radians(l["incidence_deg"])), f / vg, a, f


def estimate_offsets():
    """Per-date offset of the lidar-height stack against its own track, from every date pair.

    Reference: the mean of each track's provisional dates. The offsets found are added to
    those the stack already had applied, so OFFSETS always holds the total correction. Run
    it again after --write --coreg: the change it reports should be near zero.
    """
    idx = gfetch.A.usable(pd.read_csv(OUTD / "nisar_slc_lidar_index_9t.csv"))
    los = json.load(open(RES / "nisar_los_by_track_9t.json"))
    rows = []
    for t, g in idx.groupby("track"):
        l = los[str(int(t))]
        imgs = {}
        for r in g.itertuples():
            with rasterio.open(OUTD / r.file) as s:
                imgs[r.file] = np.abs(s.read(1))[CORE].astype(np.float64)
        off, rms = geo.network_offsets(imgs, list(g[g.collection == "provisional"].file))
        for r in g.itertuples():
            with h5py.File(RS / r.rslc, "r") as h:
                vg = float(np.median(h["geolocationGrid/groundTrackVelocity"][:]))
            drow, dcol = off[r.file]
            ds, da, a, f = radar_offsets(5 * dcol, -5 * drow, l, vg)
            s0 = float(getattr(r, "coreg_slant_m", 0.0) or 0.0)
            a0 = float(getattr(r, "coreg_az_s", 0.0) or 0.0)
            rows.append(dict(file=r.file, date=r.date, track=int(t), collection=r.collection,
                             away_m=round(a, 2), forward_m=round(f, 2),
                             slant_m=round(s0 + ds, 3), az_s=a0 + da, az_m=round((a0 + da) * vg, 2),
                             applied_slant_m=s0, applied_az_s=a0,
                             track_misclosure_rms_m=round(5 * rms, 2)))
    df = pd.DataFrame(rows)
    df.to_csv(OFFSETS, index=False)
    print(df.to_string(index=False))
    print("wrote", OFFSETS)
    return df


def track_offsets(check="_coreg_k010"):
    """Per-track offset of the co-registered stack against the lidar, from check V3.

    Reads the block shifts of `_nisar_lidar_sim_match_9t.py --stack lidar --kappa 0.1` (the
    lidar simulation with forest echo at 10% of stand height, the best fit on 2026-10-13), takes
    the median over blocks and turns it into slant range and azimuth time. The offsets found
    are added to those the stack already had applied. Split-half check: the median of each
    checkerboard half of the blocks, and how the other half fares after that correction.
    """
    sh = pd.read_csv(RES / f"nisar_lidar_sim_match_shifts{check}_9t.csv")
    sh = sh[sh.block != "tile"].copy()
    sh["half"] = (sh.block.str[1].astype(int) + sh.block.str[2].astype(int)) % 2
    los = json.load(open(RES / "nisar_los_by_track_9t.json"))
    idx = gfetch.A.usable(pd.read_csv(OUTD / "nisar_slc_lidar_index_9t.csv"))
    rows = []
    for t, g in sh.groupby("track"):
        l = los[str(int(t))]
        away = -np.array([l["east"], l["north"]]) / np.hypot(l["east"], l["north"])
        back = np.array([-away[1], away[0]])          # the check's along_m axis
        a, b = float(g.away_m.median()), float(g.along_m.median())
        e, n = a * away + b * back
        rr = idx[idx.track == t].iloc[0]
        with h5py.File(RS / rr.rslc, "r") as h:
            vg = float(np.median(h["geolocationGrid/groundTrackVelocity"][:]))
        ds, da, _, f = radar_offsets(e, n, l, vg)
        s0 = float(rr.get("track_slant_m", 0.0) or 0.0) if "track_slant_m" in idx else 0.0
        a0 = float(rr.get("track_az_s", 0.0) or 0.0) if "track_az_s" in idx else 0.0
        halves = []
        for k in (0, 1):
            fit, test = g[g.half == k], g[g.half != k]
            ca, cb = fit.away_m.median(), fit.along_m.median()
            halves.append(int((np.hypot(test.away_m - ca, test.along_m - cb) <= 2.5).sum()))
        rows.append(dict(track=int(t), check=check, away_m=round(a, 2), back_m=round(b, 2),
                         slant_m=round(s0 + ds, 3), az_s=a0 + da, az_m=round((a0 + da) * vg, 2),
                         applied_slant_m=s0, applied_az_s=a0,
                         split_half_test_blocks_within_2p5m=f"{halves[0]}/{len(g) - len(g[g.half == 0])}, "
                                                            f"{halves[1]}/{len(g) - len(g[g.half == 1])}"))
    df = pd.DataFrame(rows)
    df.to_csv(TRACK_OFFSETS, index=False)
    print(df.to_string(index=False))
    print("wrote", TRACK_OFFSETS)
    return df


def pair_coherence(max_days=36):
    """Median 5 x 5 coherence of every same-track pair up to max_days apart, on the stack as it
    is now. Dates that sit metres apart lose coherence; lining them up should bring it back."""
    from scipy.ndimage import uniform_filter
    idx = gfetch.A.usable(pd.read_csv(OUTD / "nisar_slc_lidar_index_9t.csv"))
    state = "co-registered" if "coreg" in idx and idx.coreg.any() else "as placed"
    rows = []
    for t, g in idx.sort_values("date").groupby("track"):
        S = {}
        for r in g.itertuples():
            with rasterio.open(OUTD / r.file) as s:
                S[r.date] = s.read(1)[CORE]
        dates = list(S)
        for i, d1 in enumerate(dates):
            for d2 in dates[i + 1:]:
                days = (pd.Timestamp(d2) - pd.Timestamp(d1)).days
                if days > max_days:
                    continue
                a, b = S[d1], S[d2]
                p = a * np.conj(b)
                num = np.abs(uniform_filter(p.real, 5) + 1j * uniform_filter(p.imag, 5))
                den = np.sqrt(uniform_filter(np.abs(a) ** 2, 5) * uniform_filter(np.abs(b) ** 2, 5))
                rows.append(dict(stack=state, track=int(t), date1=d1, date2=d2, days=days,
                                 coh5_median=round(float(np.median(num / np.maximum(den, 1e-12))), 3)))
    new = pd.DataFrame(rows)
    path = RES / "nisar_slc_pair_coherence_9t.csv"
    if path.exists():
        old = pd.read_csv(path)
        new = pd.concat([old[old["stack"] != state], new], ignore_index=True)
    new.to_csv(path, index=False)
    print(new[new["stack"] == state].to_string(index=False))
    print("wrote", path)
    return new


def run_v2(block=30):
    """Check V2: is the shift between NASA's placement and ours the one the heights predict?

    Both stacks place the same RSLC samples, so registering them block by block is sharp.
    Predicted shift of NASA's content away from the satellite: (NASA DEM height - lidar height)
    / tan(incidence), averaged over the block. Pass (plan): slope of measured on predicted
    0.9-1.1. Runs on the stack as placed (no co-registration offsets), usable dates only.
    """
    from skimage.registration import phase_cross_correlation
    li = gfetch.A.usable(pd.read_csv(OUTD / "nisar_slc_lidar_index_9t.csv"))
    if "coreg" in li and li.coreg.any():
        raise SystemExit("V2 needs the stack as placed: rewrite it without --coreg first")
    gi = pd.read_csv(GS / "nisar_gslc_window_index_9t_5m.csv")
    los = json.load(open(RES / "nisar_los_by_track_9t.json"))
    X, Y, shape = output_grid(gi.iloc[0])
    lon, lat = geo.utm_to_lonlat(X, Y)
    dh = (geo.dem_heights_isce(NDEM, lon, lat, CONV["dem_half_pixel"])
          - lidar_heights(lon, lat, X, Y)).reshape(shape)[CORE]
    nb = 900 // block
    rows = []
    for t, g in li.groupby("track"):
        l = los[str(int(t))]
        away = -np.array([l["east"], l["north"]]) / np.hypot(l["east"], l["north"])
        tan_i = np.tan(np.radians(l["incidence_deg"]))
        ours = nasa = 0.0
        for r in g.itertuples():
            with rasterio.open(OUTD / r.file) as s:
                ours = ours + np.abs(s.read(1))[CORE].astype(np.float64) ** 2
            gf = gi[(gi.date == r.date) & (gi.track == r.track)].iloc[0].file
            with rasterio.open(GS / gf) as s:
                nasa = nasa + np.abs(s.read(1))[CORE].astype(np.float64) ** 2
        ours, nasa = np.sqrt(ours), np.sqrt(nasa)
        for i in range(nb):
            for j in range(nb):
                sl = np.s_[i * block:(i + 1) * block, j * block:(j + 1) * block]
                s, _, _ = phase_cross_correlation(ours[sl], nasa[sl], upsample_factor=20)
                e, n = -5 * s[1], 5 * s[0]          # where NASA puts the content, against ours
                rows.append(dict(track=int(t), block_row=i, block_col=j,
                                 measured_away_m=round(e * away[0] + n * away[1], 2),
                                 measured_across_m=round(-e * away[1] + n * away[0], 2),
                                 nasa_minus_lidar_height_m=round(float(np.mean(dh[sl])), 2),
                                 predicted_away_m=round(float(np.mean(dh[sl])) / tan_i, 2)))
    df = pd.DataFrame(rows)
    df.to_csv(RES / "nisar_regeocode_v2_blocks_9t.csv", index=False)
    out = []
    for t, g in df.groupby("track"):
        slope, icpt = np.polyfit(g.predicted_away_m, g.measured_away_m, 1)
        out.append(dict(check="V2 shift against height difference", track=int(t), blocks=len(g),
                        block_m=5 * block, slope=round(float(slope), 3), intercept_m=round(float(icpt), 2),
                        r=round(float(np.corrcoef(g.predicted_away_m, g.measured_away_m)[0, 1]), 3),
                        median_measured_m=round(float(g.measured_away_m.median()), 2),
                        median_predicted_m=round(float(g.predicted_away_m.median()), 2),
                        median_across_m=round(float(g.measured_across_m.median()), 2),
                        passed=bool(0.9 <= slope <= 1.1)))
    out = pd.DataFrame(out)
    out.to_csv(RES / "nisar_regeocode_v2_checks_9t.csv", index=False)
    print(out.to_string(index=False))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--heights", default="nisar_dem", choices=["nisar_dem", "lidar"])
    ap.add_argument("--v2", action="store_true", help="check V2 on the stack as placed")
    ap.add_argument("--v1", nargs="+", help="date pairs as d1:d2, e.g. 20260917_t162A:20260929_t162A")
    ap.add_argument("--write", action="store_true", help="re-place every date (HH and HV) and write the stack")
    ap.add_argument("--coreg", action="store_true", help="with --write: apply the per-date offsets table")
    ap.add_argument("--absolute", action="store_true", help="with --write --coreg: apply the per-track offsets too")
    ap.add_argument("--track-offsets", metavar="CHECK", help="per-track offsets from a V3 run, e.g. _coreg_k010")
    ap.add_argument("--estimate-offsets", action="store_true", help="per-date offsets of the stack on disk")
    ap.add_argument("--coherence", action="store_true", help="pair coherence of the stack on disk")
    a = ap.parse_args()
    if a.write:
        write_stack(a.heights, coreg=a.coreg, absolute=a.absolute)
        return
    if a.track_offsets:
        track_offsets(a.track_offsets)
        return
    if a.estimate_offsets:
        estimate_offsets()
        return
    if a.coherence:
        pair_coherence()
        return
    if a.v2:
        run_v2()
        return
    if a.heights != "nisar_dem":
        raise SystemExit("--v1 compares against NASA and runs on NASA's DEM only")
    rows = run_v1([tuple(p.split(":")) for p in a.v1])
    RES.mkdir(exist_ok=True)
    p = RES / "nisar_regeocode_v1_checks_9t.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    print("wrote", p)


if __name__ == "__main__":
    main()
