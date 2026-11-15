"""Held-out pit test with the NISAR bands replaced by their first k principal components.

Question (user, 2026-11-15). Does the number of NISAR bands change the lidar-plus-radar gain on the 613590 pits?
Same frozen design as _nisar_feat_heldout_9t.py. Train on 9t pit samples, score the 613590 pit samples.
For each k the PCA is fitted on the 9t training rows only (drop bands over 20% missing in either class,
median-impute, clip to 1st-99th percentile, z-score, SVD) and then applied to the 613590 rows.
Exploratory. It was run after the pre-registered test and is not part of it.

Reads   the pit sample files for 9t and 613590 (slc). Writes nisar/results/613590/nisar_pit_heldout_pca_sweep_613590_slc.{csv,json}
Run from the repo root: python nisar/code/s5_eval/_nisar_feat_pca_sweep_heldout_9t.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _nisar_feat_common as C  # noqa: E402

BOOT, SEED, KS = 1000, 20261027, [1, 2, 5, 10, 30, 60, 127]


def pca_fit(X, y):
    nr = np.stack([np.isnan(X[y == 1]).mean(0), np.isnan(X[y == 0]).mean(0)]).max(0)
    good = nr <= 0.20
    med = np.nanmedian(X[:, good], 0)
    Xg = np.where(np.isnan(X[:, good]), med, X[:, good])
    lo, hi = np.percentile(Xg, [1, 99], axis=0)
    Xc = np.clip(Xg, lo, hi)
    mu, sd = Xc.mean(0), Xc.std(0)
    keep = sd > 1e-9
    Z = (Xc[:, keep] - mu[keep]) / sd[keep]
    _, S, Vt = np.linalg.svd(Z, full_matrices=False)
    return dict(good=good, med=med, lo=lo, hi=hi, mu=mu, sd=sd, keep=keep, V=Vt.T)


def pca_apply(m, X, k):
    Xg = np.where(np.isnan(X[:, m["good"]]), m["med"], X[:, m["good"]])
    Xc = np.clip(Xg, m["lo"], m["hi"])
    Z = (Xc[:, m["keep"]] - m["mu"][m["keep"]]) / m["sd"][m["keep"]]
    return Z @ m["V"][:, :k]


def main():
    tr = C.load_samples("pit", "", tag="9t_slc")
    te = C.load_samples("pit", "", tag="613590_slc")
    common = [n for n in tr["names"] if n in set(te["names"])]
    it = [tr["names"].index(n) for n in common]
    ie = [te["names"].index(n) for n in common]
    Xtr, Xte = tr["X"][:, it], te["X"][:, ie]
    ytr, yte, gte = tr["y"], te["y"], te["grp"]
    prod = np.array([n.split(":")[0] for n in common])
    ctl, lt, ctx, sar = C.feature_groups(prod)
    base = ctl | lt
    print(f"{int(sar.sum())} NISAR bands, {int(base.sum())} lidar bands, train rows {len(ytr)}, test rows {len(yte)}", flush=True)

    P = {"rich lidar baseline": C.fit_predict(Xtr[:, base], ytr, Xte[:, base]),
         "all NISAR bands + rich": C.fit_predict(Xtr[:, sar | base], ytr, Xte[:, sar | base])}
    m = pca_fit(Xtr[:, sar], ytr)
    print("PCA fitted on", int(m["keep"].sum()), "bands", flush=True)
    for k in KS:
        a, b = pca_apply(m, Xtr[:, sar], k), pca_apply(m, Xte[:, sar], k)
        P[f"PC{k} alone"] = C.fit_predict(a, ytr, b)
        P[f"PC{k} + rich"] = C.fit_predict(np.hstack([a, Xtr[:, base]]), ytr, np.hstack([b, Xte[:, base]]))

    rng = np.random.default_rng(SEED)
    ug = np.unique(gte)
    where = {g: np.flatnonzero(gte == g) for g in ug}
    names = list(P)
    boot = {k: [] for k in names}
    for _ in range(BOOT):
        idx = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(yte[idx])) < 2:
            continue
        for k in names:
            boot[k].append(roc_auc_score(yte[idx], P[k][idx]))
    rich = np.array(boot["rich lidar baseline"])
    rows = []
    for k in names:
        auc = roc_auc_score(yte, P[k])
        row = dict(feature_set=k, auc=round(auc, 3))
        if k.endswith("+ rich"):
            d = np.array(boot[k]) - rich
            row["gain_over_rich"] = round(auc - roc_auc_score(yte, P["rich lidar baseline"]), 3)
            row["gain_lo"], row["gain_hi"] = (round(float(v), 3) for v in np.percentile(d, [2.5, 97.5]))
        rows.append(row)
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    out = C.A.NISAR_ROOT / "results" / "613590"
    res.to_csv(out / "nisar_pit_heldout_pca_sweep_613590_slc.csv", index=False)
    json.dump(dict(n_pits=int(yte.sum()), n_blocks=int(len(ug)), ks=KS, seed=SEED, boot=BOOT,
                   note="exploratory, after the pre-registered held-out test"),
              open(out / "nisar_pit_heldout_pca_sweep_613590_slc.json", "w"), indent=2)


if __name__ == "__main__":
    main()
