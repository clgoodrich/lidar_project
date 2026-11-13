"""Repeated cross-validation with a spread, and block-clustered single-band tests (backlog item, outside review 2026-10-26).

1. Repeated CV. The model script uses one deterministic GroupKFold, so its AUC has no spread over fold assignments. Here
   the same model (C.oof_probs, 250 m buffer, fold-local preprocessing) is run REPEATS times with a shuffled
   StratifiedGroupKFold (grouped by 500 m block, stratified on the label), each repeat with a different seed.
   Reported per feature set: mean, sd, min and max of the pooled out-of-fold AUC over repeats. For the gate (NISAR +
   rich lidar baseline against the rich baseline) the paired difference is reported per repeat, and a block bootstrap
   of the difference on the repeat-averaged out-of-fold probabilities gives a confidence interval.

2. Cluster-aware band tests. The Mann-Whitney p of the scorer treats every decoy as independent, but decoys of one
   pad share a block and a target and neighbouring blocks share terrain. Here whole 500 m blocks are resampled
   (BOOT times), the AUC of every band is recomputed, and the p-value is the two-sided bootstrap tail of AUC about 0.5.
   Benjamini-Hochberg q is taken over bands. The naive q is kept beside it.

  [TARGET=pit] [LOCAL_M=1500] [SHAPE=1] [INC_MATCH=1] ... [REPEATS=10] [BOOT=400] python _nisar_feat_repeat_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from scipy.stats import mannwhitneyu, rankdata
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
SUFFIX = C.suffix(TARGET)
REPEATS, BOOT, SEED = int(os.environ.get("REPEATS", 10)), int(os.environ.get("BOOT", 400)), 20261027


def one_repeat(sets, y, grp, xy, r):
    out = {}
    for k, M in sets.items():
        p, _ = C.oof_probs(M, y, grp, xy=xy, seed=SEED + r)
        out[k] = p
    return out


def block_boot_auc_diff(y, grp, pa, pb, rng, n=500):
    ug = np.unique(grp)
    where = {g: np.flatnonzero(grp == g) for g in ug}
    d = []
    for _ in range(n):
        idx = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(y[idx])) == 2:
            d.append(roc_auc_score(y[idx], pa[idx]) - roc_auc_score(y[idx], pb[idx]))
    return np.percentile(d, [2.5, 97.5])


def bh(p):
    p = np.asarray(p, float)
    o = np.argsort(p)
    q = np.empty_like(p)
    q[o] = np.minimum.accumulate((p[o] * len(p) / np.arange(1, len(p) + 1))[::-1])[::-1]
    return np.minimum(q, 1)


def band_aucs(X, y):
    """AUC of every column, NaNs omitted (rank sums over the finite entries of each column)."""
    R = rankdata(X, axis=0, nan_policy="omit")
    pos = y == 1
    n1, n0 = np.isfinite(X[pos]).sum(0), np.isfinite(X[~pos]).sum(0)
    r1 = np.nansum(np.where(np.isfinite(X), R, 0)[pos], 0)
    with np.errstate(all="ignore"):
        return (r1 - n1 * (n1 + 1) / 2) / (n1 * n0)


def main():
    S = C.load_samples(TARGET, SUFFIX)
    names, X, y, grp, xy, prod = S["names"], S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    sets = {"rich lidar baseline": X[:, ctl | lt],
            "map x/y only": xy,
            "all NISAR": X[:, sar],
            "NISAR + rich baseline": X[:, sar | ctl | lt],
            "rich baseline + map x/y": np.hstack([X[:, ctl | lt], xy]),
            "NISAR + rich baseline + map x/y": np.hstack([X[:, sar | ctl | lt], xy])}
    runs = Parallel(n_jobs=4)(delayed(one_repeat)(sets, y, grp, xy, r) for r in range(REPEATS))
    rows = []
    for k in sets:
        a = np.array([roc_auc_score(y, rr[k]) for rr in runs])
        rows.append(dict(feature_set=k, repeats=REPEATS, auc_mean=a.mean(), auc_sd=a.std(ddof=1), auc_min=a.min(), auc_max=a.max()))
    rng = np.random.default_rng(SEED)
    pmean = {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}
    for a_k, b_k, label in (("NISAR + rich baseline", "rich lidar baseline", "gain: NISAR + rich baseline over rich baseline"),
                            ("NISAR + rich baseline + map x/y", "rich baseline + map x/y", "gain: NISAR + rich + x/y over rich + x/y"),
                            ("all NISAR", "map x/y only", "all NISAR minus map x/y only")):
        d = np.array([roc_auc_score(y, rr[a_k]) - roc_auc_score(y, rr[b_k]) for rr in runs])
        lo, hi = block_boot_auc_diff(y, grp, pmean[a_k], pmean[b_k], rng)
        rows.append(dict(feature_set=label, repeats=REPEATS, auc_mean=d.mean(), auc_sd=d.std(ddof=1), auc_min=d.min(), auc_max=d.max(),
                         boot_lo=lo, boot_hi=hi, share_ge_0p05=float((d >= 0.05).mean())))
    res = pd.DataFrame(rows).round(4)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_{TARGET}_repeatcv_auc_{C.A.TAG}{SUFFIX}.csv", index=False)

    # cluster-aware single-band tests
    auc = band_aucs(X, y)
    ug = np.unique(grp)
    where = {g: np.flatnonzero(grp == g) for g in ug}
    bs = np.full((BOOT, X.shape[1]), np.nan)
    for b in range(BOOT):
        idx = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(y[idx])) == 2:
            bs[b] = band_aucs(X[idx], y[idx])
    with np.errstate(all="ignore"):
        lo_t, hi_t = np.nanmean(bs <= 0.5, 0), np.nanmean(bs >= 0.5, 0)
    p_cl = np.clip(2 * np.minimum(lo_t, hi_t), 1.0 / BOOT, 1)
    p_naive = np.array([mannwhitneyu(X[(y == 1) & np.isfinite(X[:, i]), i], X[(y == 0) & np.isfinite(X[:, i]), i]).pvalue
                        if np.isfinite(X[:, i]).sum() > 50 else np.nan for i in range(X.shape[1])])
    ok = np.isfinite(auc) & np.isfinite(p_naive)
    df = pd.DataFrame(dict(band=np.array(names)[ok], auc=auc[ok], ci_lo=np.nanpercentile(bs, 2.5, 0)[ok], ci_hi=np.nanpercentile(bs, 97.5, 0)[ok],
                           p_cluster=p_cl[ok], p_naive=p_naive[ok]))
    df["q_cluster"], df["q_naive"] = bh(df.p_cluster.values), bh(df.p_naive.values)
    df["dev"] = (df.auc - 0.5).abs()
    df = df.sort_values("dev", ascending=False).drop(columns="dev")
    sarb = df.band.map(lambda n: n.split(":")[0] not in ("control", "lidartex", "context"))
    print(f"bands {len(df)}; q<0.05 naive {int((df.q_naive < 0.05).sum())}, block-clustered {int((df.q_cluster < 0.05).sum())}; "
          f"SAR bands only: naive {int((df.q_naive[sarb] < 0.05).sum())}, clustered {int((df.q_cluster[sarb] < 0.05).sum())} of {int(sarb.sum())}")
    print(df.head(12).round(3).to_string(index=False))
    df.round(4).to_csv(C.OUT / f"nisar_{TARGET}_band_cluster_tests_{C.A.TAG}{SUFFIX}.csv", index=False)


if __name__ == "__main__":
    main()
