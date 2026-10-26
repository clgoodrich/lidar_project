"""Product 9: sub-aperture (squint) and sub-band signature of each pixel, from the RSLC windows (HH).

A smooth surface returns about the same power to every part of the synthetic aperture. A metal object
or a corner (pumpjack, tank, wellhead, fence) returns strongly to only part of it, and a dihedral also
changes with radar frequency. Per RSLC window the Doppler carrier is removed, the azimuth spectrum is
cut into three contiguous sub-looks (aft, mid, fore) and the range spectrum into two sub-bands. Each
sub-look intensity is placed on the 9t 5 m grid with the same geometry, lidar heights and offsets as the
SLC stack (_nisar_regeocode_lidar_9t.py), then averaged over the dates of a track.

Bands (suffix _tNNN, dB of the date-mean sub-look intensity, each normalised by its spectral share):
  az_fore_aft_db   fore minus aft sub-look (squint asymmetry)
  az_spread_db     max - min over the three azimuth sub-looks
  az_sd_db         std over the three azimuth sub-looks
  rg_diff_db       high minus low range sub-band
  az_spread_resid  az_spread_db minus its 51 x 51 pixel running median (local anomaly)

  python notebooks/wellsight_v2/s5_eval/_nisar_feat_subaperture_9t.py
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.ndimage import map_coordinates, median_filter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "s1_build"))
import _nisar_feat_common as C  # noqa: E402

rg = importlib.import_module("_nisar_regeocode_lidar_9t")
geo = rg.geo
N_AZ, N_RG, OCC = 3, 2, 0.2          # sub-looks, sub-bands, occupied-band threshold (share of peak spectrum power)


def occupied(power):
    """First and last index where the mean spectrum power exceeds OCC of its peak."""
    p = np.convolve(power, np.ones(9) / 9, mode="same")
    k = np.flatnonzero(p > OCC * p.max())
    return int(k[0]), int(k[-1]) + 1


def split(x, axis, n):
    """n sub-looks of complex x along axis. Returns intensities (n, ...) scaled to equal mean power."""
    F = np.fft.fftshift(np.fft.fft(x, axis=axis), axes=axis)   # DC in the middle so the occupied band is contiguous
    other = tuple(i for i in range(x.ndim) if i != axis)
    lo, hi = occupied((np.abs(F) ** 2).mean(axis=other))
    edges = np.linspace(lo, hi, n + 1).astype(int)
    out = []
    for a, b in zip(edges[:-1], edges[1:]):
        G = np.zeros_like(F)
        sl = [slice(None)] * x.ndim
        sl[axis] = slice(a, b)
        G[tuple(sl)] = F[tuple(sl)]
        out.append(np.abs(np.fft.ifft(np.fft.ifftshift(G, axes=axis), axis=axis)) ** 2 / ((b - a) / (hi - lo)))
    return np.stack(out)


def date_looks(rfile, off, trk, grow):
    """Sub-look intensities of one RSLC window on the 5 m grid: (N_AZ + N_RG, ny, nx)."""
    rs = rg.load_rslc(rg.RS / rfile)
    tim = rg.gslc_timing(rg.RS / rfile, grow.granule)
    X, Y, shape = rg.output_grid(grow)
    lon, lat = geo.utm_to_lonlat(X, Y)
    h = rg.heights_for(lon, lat, X, Y, "lidar")
    P = geo.lonlat_to_ecef(lon, lat, h)
    t_gg, r_gg = geo.geogrid_to_radar(rs["gg"], X, Y, h)
    t, r = geo.zero_doppler(rs["orbit"], P, t_gg)
    dt, dr = rg.corrections(rs, tim, dict(t=t, r=r, h=h, lat=lat), set(rg.CONV["corr"]))
    dr, dt = dr + off[0] + trk[0], dt + off[1] + trk[1]
    zt, sr = rs["zt"], rs["sr"]
    row = (t + dt - zt[0]) / (zt[1] - zt[0])
    col = (r + dr - sr[0]) / (sr[1] - sr[0])
    ft, fr, fd = rs["fdc"]
    tref = zt[len(zt) // 2]
    T, R = np.meshgrid(zt, sr, indexing="ij")
    ph = 2 * np.pi * geo.lut2d(ft, fr, fd, T.ravel(), R.ravel()).reshape(T.shape) * (T - tref)
    base = rs["HH"] * np.exp(-1j * ph).astype(np.complex64)
    base = np.nan_to_num(base)
    looks = np.concatenate([split(base, 0, N_AZ), split(base, 1, N_RG)])
    return np.stack([map_coordinates(L, [row, col], order=1, mode="constant", cval=np.nan).reshape(shape)
                     for L in looks])


def main():
    idx = pd.read_csv(rg.OUTD / "nisar_slc_lidar_index_9t.csv")
    gi = pd.read_csv(rg.GS / f"nisar_gslc_window_index_{rg.TAG}_5m.csv")
    _, _, tf, shape = C.load()
    sums, cnt = {}, {}
    for r in idx.itertuples():
        if r.bad_granule:
            continue
        grow = gi[(gi.date == r.date) & (gi.track == r.track)].iloc[0]
        L = date_looks(r.rslc, (r.coreg_slant_m, r.coreg_az_s), (r.track_slant_m, r.track_az_s), grow)
        ok = np.all(np.isfinite(L) & (L > 0), axis=0)
        t = int(r.track)
        sums[t] = sums.get(t, 0) + np.where(ok, L, 0)
        cnt[t] = cnt.get(t, 0) + ok
        print(r.date, t, f"valid {ok.mean():.1%}", flush=True)
    bands = {}
    for t in sums:
        n = cnt[t]
        good = n >= max(3, int(0.7 * n.max()))
        m = np.where(good[None], sums[t] / np.maximum(n, 1)[None], np.nan)
        d = C.db(m)
        tag = f"_t{t:03d}"
        az = d[:N_AZ]
        bands["az_fore_aft_db" + tag] = az[-1] - az[0]
        bands["az_spread_db" + tag] = az.max(0) - az.min(0)
        bands["az_sd_db" + tag] = az.std(0)
        bands["rg_diff_db" + tag] = d[N_AZ + 1] - d[N_AZ]
        s = bands["az_spread_db" + tag]
        bands["az_spread_resid" + tag] = s - median_filter(np.where(np.isfinite(s), s, np.nanmedian(s)), size=51)
    C.write_bands("subaperture", bands, tf, shape)


if __name__ == "__main__":
    main()
