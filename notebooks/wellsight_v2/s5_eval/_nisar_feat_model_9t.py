"""Product 10: do the NISAR bands, together, separate targets from matched decoys beyond lidar and location?

Reads the samples dumped by _nisar_feat_score_9t.py. Gradient boosting, 5-fold CV grouped by 500 m block, with a
250 m buffer between train and test rows (C.oof_probs). Band filtering and imputation happen inside each training
fold. Reports the pooled out-of-fold AUC, the mean and spread of the five fold AUCs, and a block-bootstrap CI.

Feature sets: simple lidar baseline (cover, slope, roughness), rich lidar baseline (those plus the same texture
operators the SAR spatial product uses, run on lidar grids), map x/y only (location control), all SAR bands,
and combinations, plus each product group alone.

  [TARGET=pit] [CORE_SHRINK_M=15] [ROAD_NEAR=1] [MATCH_ROUGH=1] [LOCAL_M=1500] python _nisar_feat_model_9t.py
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
CORE = float(os.environ.get("CORE_SHRINK_M", 0 if TARGET == "pit" else 5))
SUFFIX = (("" if CORE == (0 if TARGET == "pit" else 5) else f"_core{CORE:.0f}m") + ("_roadnear" if os.environ.get("ROAD_NEAR") == "1" else "")
          + ("_roughmatch" if os.environ.get("MATCH_ROUGH") == "1" else "")
          + (f"_local{float(os.environ['LOCAL_M']):.0f}" if float(os.environ.get("LOCAL_M", 0)) else ""))
GATE, SEED, NB = 0.05, 20261026, 200


def score(X, y, grp, open_mask):
    p, folds = C.oof_probs(X, y, grp)
    fa = [roc_auc_score(y[te], p[te]) for te in folds if len(set(y[te])) == 2]
    rng = np.random.default_rng(SEED)
    ug = np.unique(grp)
    bs = []
    for _ in range(NB):
        idx = np.concatenate([np.flatnonzero(grp == g) for g in rng.choice(ug, len(ug))])
        if len(set(y[idx])) == 2:
            bs.append(roc_auc_score(y[idx], p[idx]))
    return dict(auc=roc_auc_score(y, p), ci_lo=np.percentile(bs, 2.5), ci_hi=np.percentile(bs, 97.5),
                auc_open=roc_auc_score(y[open_mask], p[open_mask]), fold_mean=np.mean(fa), fold_sd=np.std(fa), p=p)


def main():
    S = C.load_samples(TARGET, SUFFIX)
    names, X, y, grp, xy, prod = S["names"], S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    open_mask = S["cover"] < 0.25
    ctl, lt, ctx, sar = C.feature_groups(prod)
    geo = sar & (prod == "geometry")
    sets = {"baseline (cover, slope, rough)": X[:, ctl],
            "lidar rich baseline (+ texture)": X[:, ctl | lt],
            "map x/y only": xy,
            "rich baseline + map x/y": np.hstack([X[:, ctl | lt], xy]),
            "all NISAR": X[:, sar],
            "NISAR + baseline": X[:, sar | ctl],
            "NISAR + rich baseline": X[:, sar | ctl | lt],
            "NISAR + rich baseline + map x/y": np.hstack([X[:, sar | ctl | lt], xy]),
            "NISAR without geometry (SAR only)": X[:, sar & ~geo]}
    if ctx.any():
        sets.update({"road context only": X[:, ctx], "NISAR + road context": X[:, sar | ctx]})
    for g in sorted(set(prod[sar])):
        sets[f"only {g}"] = X[:, prod == g]
    rows = []
    for k, M in sets.items():
        r = score(M, y, grp, open_mask)
        rows.append(dict(feature_set=k, n_bands=int(M.shape[1]), auc=round(r["auc"], 3), ci_lo=round(r["ci_lo"], 3), ci_hi=round(r["ci_hi"], 3),
                         auc_open=round(r["auc_open"], 3), fold_mean=round(r["fold_mean"], 3), fold_sd=round(r["fold_sd"], 3)))
        print(rows[-1], flush=True)
    # placebo: the first decoy of each target plays "target" against the other decoys (same matching)
    dec_pad, pads, sel = S["z"]["dec_pad"], S["pads"], S["sel"]
    first = np.array([np.flatnonzero(dec_pad[sel] == p)[0] for p in pads])
    yp = np.zeros(len(sel), int)
    yp[first] = 1
    n0 = len(pads)
    C.CV_XY = xy[n0:]
    r = score(X[n0:][:, sar], yp, grp[n0:], open_mask[n0:])
    C.CV_XY = xy
    rows.append(dict(feature_set="placebo: decoy vs decoy, all NISAR", n_bands=int(sar.sum()), auc=round(r["auc"], 3), ci_lo=round(r["ci_lo"], 3),
                     ci_hi=round(r["ci_hi"], 3), auc_open=round(r["auc_open"], 3), fold_mean=round(r["fold_mean"], 3), fold_sd=round(r["fold_sd"], 3)))
    print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    get = lambda k: float(res.loc[res.feature_set == k, "auc"].iloc[0])  # noqa: E731
    res["gain_over_simple_baseline"] = (res.auc - get("baseline (cover, slope, rough)")).round(3)
    res["gain_over_rich_baseline"] = (res.auc - get("lidar rich baseline (+ texture)")).round(3)
    res.to_csv(C.OUT / f"nisar_{TARGET}_model_auc_by_set_{C.A.TAG}{SUFFIX}.csv", index=False)
    json.dump(dict(n_targets=int(len(pads)), n_decoys=int(len(sel)), gate=GATE, core_shrink_m=CORE, cv_buffer_m=C.CV_BUFFER_M,
                   simple_baseline_auc=get("baseline (cover, slope, rough)"), rich_baseline_auc=get("lidar rich baseline (+ texture)"),
                   xy_only_auc=get("map x/y only"), all_nisar_auc=get("all NISAR"),
                   passes_gate_over_rich_baseline=bool(get("NISAR + rich baseline") - get("lidar rich baseline (+ texture)") >= GATE),
                   passes_gate_over_rich_plus_xy=bool(get("NISAR + rich baseline + map x/y") - get("rich baseline + map x/y") >= GATE)),
              open(C.OUT / f"nisar_{TARGET}_model_summary_{C.A.TAG}{SUFFIX}.json", "w"), indent=2)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
