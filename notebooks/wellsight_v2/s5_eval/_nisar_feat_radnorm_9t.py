"""Per-date radiometric normalisation, and how close pads are to the HV floor (backlog item, review 2026-10-26).

Every product so far averages raw per-date power. If one date is brighter than the rest (soil moisture, a calibration or
processing-release step), the date-mean and the date-to-date spread inherit that offset. This script builds the same
simple per-track bands twice, raw and normalised, and tests whether normalising changes anything.

Normalisation: for each track, date and polarisation, the reference level is the median dB over closed-canopy flat
ground (cover > 0.85, slope < 10 degrees, finite on every date). Each date's power is divided by its reference offset
from the track mean of those references. Bands per track and polarisation: mean (dB), spread over dates (sd of dB);
plus the HV minus HH mean. Raw and normalised versions, 15 bands each.

Outputs:
  data/9t/derived/nisar_features_5m/nisar_check_radnorm_9t_slc_5m.tif   (not named nisar_feat_*, so the scorer's read_all ignores it)
  data/9t/results/nisar/nisar_radnorm_date_offsets_9t_slc.csv
  data/9t/results/nisar/nisar_radnorm_<target>_auc_9t_slc<suffix>.csv  (single-band and model AUC, raw against normalised)
  data/9t/results/nisar/nisar_radnorm_noise_margin_9t_slc.csv           (pad HV level against the darkest ground of the tile)

Scoring reads the saved footprints (C.sample_values) of each samples file, so raw and normalised bands are compared on
exactly the pixels of the main study. Run the scorer first (it saves the footprints).

  NISAR_STACK=slc python _nisar_feat_radnorm_9t.py build
  NISAR_STACK=slc [TARGET=pit] [LOCAL_M=1500] python _nisar_feat_radnorm_9t.py score
"""
import os
import sys

import numpy as np
import pandas as pd
import rasterio
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
SUFFIX = C.suffix(TARGET)
PATH = C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif"


def build():
    idx, stack, tf, shape = C.load()
    grids = C.lidar_grids(tf, shape)
    ref = (grids["cover"] > 0.85) & (grids["slope"] < 10)
    bands, off_rows = {}, []
    for t, g in C.by_track(idx):
        mean_db = {"raw": {}, "norm": {}}
        for pol, pi in (("hh", 0), ("hv", 1)):
            cube = np.abs(C.cube(g, stack, pi)) ** 2
            ok = np.all(np.isfinite(cube) & (cube > 0), axis=0)
            cube = np.where(ok[None], cube, np.nan)
            m = ref & ok
            ref_db = np.array([np.nanmedian(10 * np.log10(c[m])) for c in cube])
            off = ref_db - ref_db.mean()
            for d, f, r, o in zip(g.date, g.file, ref_db, off):
                off_rows.append(dict(track=t, pol=pol, date=d, collection=g.loc[g.file == f, "collection"].iloc[0] if "collection" in g else "",
                                     ref_db=round(float(r), 3), offset_db=round(float(o), 3), ref_pixels=int(m.sum())))
            ncube = cube / (10 ** (off / 10))[:, None, None]
            for kind, cb in (("raw", cube), ("norm", ncube)):
                db = 10 * np.log10(cb)
                mean_db[kind][pol] = C.db(np.nanmean(cb, 0))
                bands[f"{kind}_mean_{pol}_t{t:03d}"] = mean_db[kind][pol]
                bands[f"{kind}_sd_{pol}_t{t:03d}"] = np.nanstd(db, 0)
            print(f"track {t} {pol}: date offsets sd {off.std():.2f} dB, range {off.min():+.2f} to {off.max():+.2f}", flush=True)
        for kind in ("raw", "norm"):
            bands[f"{kind}_hvhh_t{t:03d}"] = mean_db[kind]["hv"] - mean_db[kind]["hh"]
    with rasterio.open(PATH, "w", driver="GTiff", height=shape[0], width=shape[1], count=len(bands), dtype="float32",
                       crs=C.CRS, transform=tf, nodata=np.nan, compress="deflate") as dst:
        for i, (n, a) in enumerate(bands.items(), 1):
            dst.write(np.asarray(a, np.float32), i)
            dst.set_band_description(i, n)
    print("wrote", PATH, len(bands), "bands")
    off = pd.DataFrame(off_rows)
    off.to_csv(C.OUT / f"nisar_radnorm_date_offsets_{C.A.TAG}.csv", index=False)
    print(off.groupby(["track", "pol"]).offset_db.agg(["std", "min", "max"]).round(2).to_string())


def score():
    S = C.load_samples(TARGET, SUFFIX)
    z = S["z"]
    if "pad_near" not in z.files:
        raise SystemExit("samples file has no footprints; re-run _nisar_feat_score_9t.py first")
    with rasterio.open(PATH) as r:
        names = list(r.descriptions)
        arr = r.read()
    pads, sel = S["pads"], S["sel"]
    cols = {}
    for i, n in enumerate(names):
        pv, dv = C.sample_values(arr[i].ravel(), z)
        cols[n] = np.r_[pv[pads], dv[sel]]
    y, grp = S["y"], S["grp"]
    ctl, lt, ctx, sar = C.feature_groups(S["prod"])
    rich = S["X"][:, ctl | lt]
    rows = []
    for n in names:
        v = cols[n]
        ok = np.isfinite(v)
        rows.append(dict(band=n, auc=round(roc_auc_score(y[ok], v[ok]), 3), n_finite=int(ok.sum())))
    single = pd.DataFrame(rows)
    single["kind"] = single.band.str.split("_").str[0]
    single["stat"] = single.band.str.replace(r"^(raw|norm)_", "", regex=True)
    pair = single.pivot(index="stat", columns="kind", values="auc")
    pair["strength_raw"], pair["strength_norm"] = (pair["raw"] - 0.5).abs(), (pair["norm"] - 0.5).abs()
    print(pair.round(3).to_string())
    sets = {"raw bands": [n for n in names if n.startswith("raw_")], "normalised bands": [n for n in names if n.startswith("norm_")]}
    out = []
    for k, ns in sets.items():
        Xk = np.column_stack([cols[n] for n in ns])
        for label, M in ((k, Xk), (k + " + rich lidar baseline", np.hstack([Xk, rich]))):
            p, _ = C.oof_probs(M, y, grp)
            out.append(dict(feature_set=label, n_bands=M.shape[1], auc=round(roc_auc_score(y, p), 3)))
            print(out[-1], flush=True)
    p, _ = C.oof_probs(rich, y, grp)
    out.append(dict(feature_set="rich lidar baseline", n_bands=rich.shape[1], auc=round(roc_auc_score(y, p), 3)))
    res = pd.DataFrame(out)
    res["mean_single_band_strength_raw"] = round(pair.strength_raw.mean(), 4)
    res["mean_single_band_strength_norm"] = round(pair.strength_norm.mean(), 4)
    print(res.to_string(index=False))
    pair.round(4).to_csv(C.OUT / f"nisar_radnorm_{TARGET}_bands_auc_{C.A.TAG}{SUFFIX}.csv")
    res.to_csv(C.OUT / f"nisar_radnorm_{TARGET}_auc_{C.A.TAG}{SUFFIX}.csv", index=False)
    if TARGET == "pad" and not SUFFIX:
        # how close are pad cores to the darkest ground of the tile, per track and polarisation (raw date-mean level)
        mrows = []
        for n in names:
            if not n.startswith("raw_mean_"):
                continue
            a = arr[names.index(n)]
            fin = a[np.isfinite(a)]
            pv, dv = C.sample_values(a.ravel(), z)
            p01, p05, p50 = np.percentile(fin, [1, 5, 50])
            mrows.append(dict(band=n, tile_p01=round(p01, 2), tile_p05=round(p05, 2), tile_p50=round(p50, 2),
                              pad_median=round(float(np.nanmedian(pv[pads])), 2), decoy_median=round(float(np.nanmedian(dv[sel])), 2),
                              pad_minus_p01=round(float(np.nanmedian(pv[pads])) - p01, 2),
                              pads_below_p05_share=round(float((pv[pads] < p05).mean()), 3)))
        mm = pd.DataFrame(mrows)
        print(mm.to_string(index=False))
        mm.to_csv(C.OUT / f"nisar_radnorm_noise_margin_{C.A.TAG}.csv", index=False)


if __name__ == "__main__":
    {"build": build, "score": score}[sys.argv[1]]()
