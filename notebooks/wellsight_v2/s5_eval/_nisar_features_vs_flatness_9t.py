"""Do NISAR-derived features track lidar flatness on open ground? (9t; --area picks another area)

Hypothesis behind pad detection: a pad is unnaturally flat, so radar measures tied to flatness
(brightness, its spread over time, HV/HH, coherence, brightness differences between tracks)
should change with lidar slope and roughness. Test that on all open ground first, before any
pad test. If a feature cannot follow lidar flatness there, it cannot see a flat pad.

Features (5 m grid, per track unless noted; HH = band 1, HV = band 2 of the complex windows):
  hh_mean_db, hv_mean_db, hv_minus_hh_db   mean power in dB
  hh_std_db, hh_p90_p10_db                 spread of the dB value over dates
  hh_da                                    amplitude dispersion std/mean
  coh_short, coh_mid, coh_long, coh_decay  HH coherence (3x3) for pair gaps <=12, 13-36, >36 days,
                                           decay = coh_short - coh_long
  diff_tAAA_tBBB_db                        mean-dB difference between the two ascending tracks
                                           (different incidence angle)
  diff_tDDD_asc_db                         descending track minus the mean of the ascending tracks
Lidar (1 m -> 5 m mean): slope, roughness_5, canopy cover (share of 1 m CHM cells above 2 m).
Open ground = cover < 0.30 (also reported: < 0.10). Closed = cover > 0.90 as a control.
Statistic: Spearman rho against slope and roughness; AUC steep (slope > 8 deg) vs flat (< 2 deg).

  python notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py [--area warren]
"""
from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import rasterio
from rasterio.warp import Resampling, reproject
from scipy.stats import mannwhitneyu, spearmanr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
ifg = importlib.import_module("_nisar_gslc_interferogram_pits_9t")
st, A = ifg.st, ifg.A
OUT, CRS = ifg.OUT, ifg.CRS
STACK_DIR = A.DATA / "derived" / "nisar_features_5m"
SEED, N_MAX = 20261026, 60000
BINS = {"coh_short": (0, 12), "coh_mid": (13, 36), "coh_long": (37, 999)}


def to_grid(path, tf, shape):
    """Average a 1 m lidar raster onto the 5 m radar grid."""
    with rasterio.open(path) as r:
        src = r.read(1, masked=True)
        src = np.where(src.mask, np.nan, src.filled(0)).astype(np.float32)
        dst = np.full(shape, np.nan, np.float32)
        reproject(src, dst, src_transform=r.transform, src_crs=r.crs, src_nodata=np.nan,
                  dst_transform=tf, dst_crs=CRS, dst_nodata=np.nan, resampling=Resampling.average)
    return dst


def track_features(g, stack):
    """Amplitude features for one track (rows of the index), HH and HV."""
    hh = np.stack([np.abs(stack[f][0]) for f in g.file]).astype(np.float32)
    hv = np.stack([np.abs(stack[f][1]) for f in g.file]).astype(np.float32)
    ok = np.all(np.isfinite(hh) & (hh > 0) & np.isfinite(hv) & (hv > 0), axis=0)
    hhd = 10 * np.log10(np.where(hh > 0, hh ** 2, np.nan))
    m = hh.mean(0)
    f = {}
    f["hh_mean_db"] = 10 * np.log10(np.where(ok, (hh ** 2).mean(0), np.nan))
    f["hv_mean_db"] = 10 * np.log10(np.where(ok, (hv ** 2).mean(0), np.nan))
    f["hv_minus_hh_db"] = f["hv_mean_db"] - f["hh_mean_db"]
    f["hh_std_db"] = np.where(ok, np.nanstd(hhd, 0), np.nan)
    f["hh_p90_p10_db"] = np.where(ok, np.nanpercentile(hhd, 90, 0) - np.nanpercentile(hhd, 10, 0), np.nan)
    f["hh_da"] = np.where(ok, hh.std(0) / np.where(m > 0, m, np.nan), np.nan)
    return f


def coherence_bins(g, stack):
    """Mean HH coherence over all date pairs of one track, by temporal gap."""
    g = g.sort_values("date").reset_index(drop=True)
    d = pd.to_datetime(g.date).values
    acc = {k: [] for k in BINS}
    for i in range(len(g)):
        for j in range(i + 1, len(g)):
            dt = int((d[j] - d[i]) / np.timedelta64(1, "D"))
            for k, (lo, hi) in BINS.items():
                if lo <= dt <= hi:
                    coh, _ = ifg.interferogram(stack[g.file[i]][0], stack[g.file[j]][0])
                    acc[k].append(coh)
    return ({k: (np.nanmean(np.stack(v), 0) if v else None) for k, v in acc.items()},
            {k: len(v) for k, v in acc.items()})


def auc(a, b):
    return mannwhitneyu(a, b).statistic / (len(a) * len(b))


def main():
    idx, stack, tf, shape = ifg.load_complex()
    feats, npairs = {}, {}
    for t, g in idx.groupby("track"):
        t = int(t)
        f = track_features(g, stack)
        c, npairs[t] = coherence_bins(g, stack)
        for k, v in f.items():
            feats[f"{k}_t{t:03d}"] = v
        for k, v in c.items():
            if v is not None:
                feats[f"{k}_t{t:03d}"] = v.astype(np.float32)
        if c["coh_short"] is not None and c["coh_long"] is not None:
            feats[f"coh_decay_t{t:03d}"] = (c["coh_short"] - c["coh_long"]).astype(np.float32)
        print(f"track {t}: {len(g)} dates, pairs {npairs[t]}", flush=True)
    tracks = sorted(int(t) for t in idx.track.unique())
    asc = [t for t in tracks if idx[idx.track == t].direction.iloc[0].upper().startswith("A")]
    des = [t for t in tracks if t not in asc]
    if len(asc) >= 2:
        feats[f"diff_t{asc[0]:03d}_t{asc[1]:03d}_db"] = (feats[f"hh_mean_db_t{asc[0]:03d}"]
                                                         - feats[f"hh_mean_db_t{asc[1]:03d}"])
    for t in des:
        feats[f"diff_t{t:03d}_asc_db"] = feats[f"hh_mean_db_t{t:03d}"] - np.nanmean(
            [feats[f"hh_mean_db_t{a:03d}"] for a in asc], 0)

    slope = to_grid(A.lidar("slope"), tf, shape)
    rough = to_grid(A.lidar("roughness_5"), tf, shape)
    cover = st.canopy_cover(tf, shape)

    STACK_DIR.mkdir(parents=True, exist_ok=True)
    names = list(feats) + ["lidar_slope", "lidar_roughness5", "lidar_cover"]
    arrs = [feats[n] for n in feats] + [slope, rough, cover]
    path = STACK_DIR / f"nisar_feature_stack_{A.TAG}_5m.tif"
    with rasterio.open(path, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(arrs),
                       dtype="float32", crs=CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
        for i, (n, a) in enumerate(zip(names, arrs), 1):
            dst.write(a.astype(np.float32), i)
            dst.set_band_description(i, n)
    print("wrote", path)

    rng = np.random.default_rng(SEED)
    base = np.isfinite(slope) & np.isfinite(rough) & np.isfinite(cover)
    rows = []
    for setting, mask in (("open_lt0p30", cover < 0.30), ("open_lt0p10", cover < 0.10),
                          ("closed_gt0p90", cover > 0.90)):
        sel0 = base & mask
        for n, a in feats.items():
            sel = sel0 & np.isfinite(a)
            if sel.sum() < 500:
                continue
            ii = np.flatnonzero(sel.ravel())
            if len(ii) > N_MAX:
                ii = rng.choice(ii, N_MAX, replace=False)
            x, s, r = a.ravel()[ii], slope.ravel()[ii], rough.ravel()[ii]
            flat, steep = x[s < 2], x[s > 8]
            rows.append(dict(setting=setting, feature=n, n_px=int(sel.sum()),
                             rho_slope=round(float(spearmanr(x, s)[0]), 3),
                             rho_rough=round(float(spearmanr(x, r)[0]), 3),
                             n_flat=len(flat), n_steep=len(steep),
                             auc_steep_gt_flat=round(float(auc(steep, flat)), 3)
                             if min(len(flat), len(steep)) >= 50 else np.nan))
    res = pd.DataFrame(rows)
    res.to_csv(OUT / f"nisar_features_vs_flatness_per_feature_{A.TAG}.csv", index=False)
    json.dump(dict(tracks=tracks, pairs_per_track=npairs, n_features=len(feats),
                   open_px=int((base & (cover < 0.30)).sum()), closed_px=int((base & (cover > 0.90)).sum()),
                   stack=str(path)),
              open(OUT / f"nisar_features_vs_flatness_summary_{A.TAG}.json", "w"), indent=2)
    pd.set_option("display.width", 200)
    print(res[res.setting == "open_lt0p30"].sort_values("rho_slope", key=abs, ascending=False).to_string(index=False))


if __name__ == "__main__":
    main()
