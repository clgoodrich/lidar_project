"""Azimuth sub-look coherence per pixel, multi-date, 9t. Set 2026-11-27 (secondary analysis, Track 2C).

Why
  A point scatterer (steel, a dihedral) reflects the same way across the whole synthetic aperture,
  so two images made from the two halves of the azimuth spectrum agree. Distributed ground and
  forest give independent speckle in each half, so the two disagree. The measure works on single
  pixels, needs no long stack, and a calibration gain or a season change hits both halves alike.

Method (per usable date, HH)
  1. Native RSLC window; remove the Doppler-centroid carrier (as the geocoder does), so the
     azimuth spectrum sits at baseband.
  2. FFT along azimuth. The occupied band is where the mean power spectrum is above 25% of its
     peak. Split it at its power-weighted centre into two non-overlapping halves; zero the rest.
  3. IFFT each half, restore the carrier, and place both on the 5 m lidar grid with the same
     geocoder, heights and per-date plus per-track offsets as the production stack.
  4. Per track and pixel: gamma_sub = |sum_d L1 L2*| / sqrt(sum_d |L1|^2 sum_d |L2|^2).

Outputs (git-ignored rasters; scored by _nisar_steel_pads_v2_9t.py, which picks them up if present)
  nisar/derived/9t/v2/nisar_sublook_coherence_t026_9t.tif  (and t090, t162)
  nisar/results/9t/v2/nisar_sublook_summary_9t.json

Run
  python nisar/code/s5_eval/_nisar_sublook_9t.py
"""
import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "nisar" / "code" / "s1_build"))
sys.argv = [sys.argv[0]]  # the geocoder must keep its plain area tag ("9t"), so no --slc
rg = importlib.import_module("_nisar_regeocode_lidar_9t")
geo = rg.geo
A = rg.gfetch.A
OUTD = A.NISAR_DERIVED / "v2"
RES = A.NISAR_ROOT / "results" / "9t" / "v2"
BAND_FRAC = 0.25


def split_looks(rs):
    """Two azimuth sub-look copies of rs['HH'] (carrier removed, split, carrier restored)."""
    zt, sr = rs["zt"], rs["sr"]
    ft, fr, fd = rs["fdc"]
    tref = zt[len(zt) // 2]
    T, R = np.meshgrid(zt, sr, indexing="ij")
    ph = 2 * np.pi * geo.lut2d(ft, fr, fd, T.ravel(), R.ravel()).reshape(T.shape) * (T - tref)
    car = np.exp(1j * ph).astype(np.complex64)
    x = np.nan_to_num(rs["HH"]) * np.conj(car)
    X = np.fft.fft(x, axis=0)
    f = np.fft.fftfreq(x.shape[0])
    p = (np.abs(X) ** 2).mean(1)
    o = np.argsort(f)
    fs, ps = f[o], p[o]
    occ = ps > BAND_FRAC * ps.max()
    lo, hi = fs[occ].min(), fs[occ].max()
    c = float((fs[occ] * ps[occ]).sum() / ps[occ].sum())
    looks = []
    for a, b in ((lo, c), (c, hi)):
        m = ((f >= a) & (f < b)).astype(np.float32)[:, None]
        looks.append((np.fft.ifft(X * m, axis=0) * car).astype(np.complex64))
    return looks, dict(band_lo=round(float(lo), 4), band_hi=round(float(hi), 4), centre=round(c, 4))


def main():
    OUTD.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    idx = A.usable_stack(pd.read_csv(rg.OUTD / f"nisar_slc_lidar_index_{rg.TAG}.csv"))
    load0 = rg.load_rslc
    acc, info = {}, {}
    for r in idx.itertuples():
        key = r.rslc.replace("nisar_rslc_window_", "").replace(f"_{rg.TAG}.h5", "")
        rs = load0(rg.RS / r.rslc)
        looks, bi = split_looks(rs)
        out = []
        for L in looks:
            rg.load_rslc = lambda path, L=L, rs=rs: dict(rs, HH=L)  # same window, HH replaced by one look
            o, inf = rg.make_slc(key, heights="lidar", pols=("HH",),
                                 coreg=(r.coreg_slant_m + r.track_slant_m, r.coreg_az_s + r.track_az_s))
            out.append(np.nan_to_num(o["HH"]))
        rg.load_rslc = load0
        t = int(r.track)
        a = acc.setdefault(t, dict(cross=0, p1=0, p2=0, n=0, grid=r))
        a["cross"] = a["cross"] + out[0] * np.conj(out[1])
        a["p1"] = a["p1"] + np.abs(out[0]) ** 2
        a["p2"] = a["p2"] + np.abs(out[1]) ** 2
        a["n"] += 1
        info[key] = bi
        print(key, bi, flush=True)
    summ = {}
    for t, a in acc.items():
        g = np.abs(a["cross"]) / np.sqrt(a["p1"] * a["p2"])
        g = np.where(a["p1"] * a["p2"] > 0, g, np.nan).astype(np.float32)
        m = a["grid"]
        tf = from_origin(m.x_first_centre - m.spacing_m / 2, m.y_first_centre + m.spacing_m / 2, m.spacing_m, m.spacing_m)
        p = OUTD / f"nisar_sublook_coherence_t{t:03d}_9t.tif"
        with rasterio.open(p, "w", driver="GTiff", width=g.shape[1], height=g.shape[0], count=1, dtype="float32",
                           crs="EPSG:32617", transform=tf, compress="deflate", nodata=np.nan) as d:
            d.write(g, 1)
        v = g[np.isfinite(g)]
        summ[t] = dict(n_dates=a["n"], median=round(float(np.median(v)), 3), p99=round(float(np.percentile(v, 99)), 3),
                       share_gt_0p8=round(float((v > 0.8).mean()), 4), file=str(p))
        print(t, summ[t])
    (RES / "nisar_sublook_summary_9t.json").write_text(json.dumps(dict(band_frac=BAND_FRAC, per_date=info, per_track=summ), indent=1))


if __name__ == "__main__":
    main()
