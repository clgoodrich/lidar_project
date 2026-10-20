"""Can NISAR backscatter tell the pit detector's true positives from its false positives? (9t)

Detections: data/9t/results/instance_precision/scored_pit_unet_v2.gpkg, layer "detections"
(104 rows, verdict TP or FP against the annotated pits). For each detection the same eight
seasonal backscatter metrics as _nisar_gslc_stack_pad_pit_seasonal_9t.py are measured
(HH and HV, leaf-off fall, winter, leaf-on, leaf-on minus fall; detection minus its 10-30 m ring,
dB, mean over tracks), on the lidar-placed stack, no registration shift.

Tests, all against the verdict:
  * AUC of each metric (TP vs FP) with a label-permutation p, 5,000 shuffles, two-sided.
  * AUC of the detector's own score, for scale.
  * Repeated stratified 5-fold CV of a logistic regression: score alone vs score + NISAR metrics.
    The statistic is the mean CV AUC gain. A label permutation (200 shuffles of the whole CV) gives
    its null.
NISAR is not an input to the detector, so there is no leakage from training.

  python notebooks/wellsight_v2/s5_eval/_nisar_pit_fp_screen_9t.py --slc
"""
import importlib
import json
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
seas = importlib.import_module("_nisar_gslc_stack_pad_pit_seasonal_9t")
A = seas.A
OUT = seas.OUT
DET = A.DATA / "results" / "instance_precision" / "scored_pit_unet_v2.gpkg"
N_PERM, N_CV_PERM, SEED = 5000, 200, 20261020
rng = np.random.default_rng(SEED)


def build_layers(idx, inten, tracks):
    means = {}
    for (track, season), g in idx.groupby(["track", "season"]):
        for p, pi in (("hh", 0), ("hv", 1)):
            s = np.stack([inten[f][pi] for f in g.file])
            n_ok = np.isfinite(s).sum(0)
            need = max(1, int(np.ceil(0.5 * len(g))))
            with np.errstate(all="ignore"):
                m = np.nanmean(s, axis=0)
            means[(track, season, p)] = np.where(n_ok >= need, m, np.nan).ravel()
    return {t: {f"{p}_{s}": means[(t, s, p)] for s in seas.SEASONS for p in ("hh", "hv") if (t, s, p) in means}
            for t in tracks}


def cv_auc(X, y, seed, n_rep=20):
    cv = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    pr = np.zeros((n_rep, len(y)))
    for k, (tr, te) in enumerate(cv.split(X, y)):
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=1000)).fit(X[tr], y[tr])
        pr[k // 5, te] = m.predict_proba(X[te])[:, 1]
    return float(np.mean([roc_auc_score(y, p) for p in pr]))


def main():
    warnings.filterwarnings("ignore")
    idx, inten, tf, shape = seas.load_stack()
    idx["season"] = idx.date.map(seas.season_of)
    tracks = sorted(idx.track.unique())
    layers = build_layers(idx, inten, tracks)
    cover = seas.canopy_cover(tf, shape)
    ok_flat = np.isfinite(cover).ravel()

    det = gpd.read_file(DET, layer="detections").to_crs(seas.CRS).reset_index(drop=True)
    y = (det.verdict == "TP").to_numpy().astype(int)
    pits = seas.read_layer(seas.ANN, "pit_outside").to_crs(seas.CRS)
    roads = seas.read_layer(seas.ANN, "roads").to_crs(seas.CRS)
    import pandas as _pd
    excl = _pd.concat([pits.buffer(seas.PIT_EXCL), roads.buffer(seas.PIT_EXCL)]).union_all()

    metrics = {}
    for p in ("hh", "hv"):
        for s in seas.SEASONS:
            metrics[f"{p}_{s}"] = (f"{p}_{s}", None)
        metrics[f"{p}_change_leafon_vs_fall"] = (f"{p}_leafon", f"{p}_leafoff_fall")

    rows = []
    for i, g in enumerate(det.geometry):
        core, rg = seas.pixel_sets(g, 0.0, seas.PIT_RING, excl.difference(g.buffer(1)), tf, shape, ok_flat)
        row = dict(det_id=i, verdict=det.verdict[i], score=float(det.score[i]), n_core=len(core), n_ring=len(rg))
        for m, (num, den) in metrics.items():
            if len(core) == 0 or len(rg) < 10:
                row[m] = np.nan
                continue
            v = [seas.set_value(core, rg, layers[t], num, den) for t in tracks]
            row[m] = float(np.nanmean(v)) if np.isfinite(v).any() else np.nan
        rows.append(row)
    df = pd.DataFrame(rows)
    use = df[list(metrics)].notna().all(axis=1) & (df.n_ring >= 10)
    print(f"{len(df)} detections, {int(use.sum())} with complete NISAR metrics "
          f"(TP {int(y[use].sum())}, FP {int((1 - y[use]).sum())})")
    d, yy = df[use].reset_index(drop=True), y[use.to_numpy()]

    res = []
    for m in ["score"] + list(metrics):
        x = d[m].to_numpy()
        a = roc_auc_score(yy, x)
        null = np.array([roc_auc_score(rng.permutation(yy), x) for _ in range(N_PERM)])
        p = float((1 + (np.abs(null - 0.5) >= abs(a - 0.5)).sum()) / (1 + N_PERM))
        res.append(dict(metric=m, auc_tp_gt_fp=round(a, 3), p_perm=round(p, 4),
                        median_tp=round(float(np.median(x[yy == 1])), 3), median_fp=round(float(np.median(x[yy == 0])), 3)))
    res = pd.DataFrame(res)
    print(res.to_string(index=False))

    Xs, Xn = d[["score"]].to_numpy(), d[["score"] + list(metrics)].to_numpy()
    base, full = cv_auc(Xs, yy, SEED), cv_auc(Xn, yy, SEED)
    gain = full - base
    null_gain = np.array([cv_auc(Xn, (pm := rng.permutation(yy)), SEED + k, 4) - cv_auc(Xs, pm, SEED + k, 4)
                          for k in range(N_CV_PERM)])
    p_gain = float((1 + (null_gain >= gain).sum()) / (1 + N_CV_PERM))
    print(f"CV AUC score alone {base:.3f}, score + NISAR {full:.3f}, gain {gain:+.3f}, "
          f"permutation p {p_gain:.3f} (null gain 95th pct {np.percentile(null_gain, 95):+.3f})")

    stem = "nisar_pit_fp_screen"
    df.to_csv(OUT / f"{stem}_per_detection_{A.TAG}.csv", index=False)
    res.to_csv(OUT / f"{stem}_auc_{A.TAG}.csv", index=False)
    json.dump(dict(detections=len(df), used=int(use.sum()), tp=int(yy.sum()), fp=int((1 - yy).sum()),
                   cv_auc_score_alone=base, cv_auc_score_plus_nisar=full, gain=gain, p_gain=p_gain,
                   null_gain_p95=float(np.percentile(null_gain, 95)), n_perm=N_PERM, n_cv_perm=N_CV_PERM),
              open(OUT / f"{stem}_summary_{A.TAG}.json", "w"), indent=2)
    print("wrote", OUT / f"{stem}_*_{A.TAG}.*")


if __name__ == "__main__":
    main()
