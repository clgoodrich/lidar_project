"""Frozen held-out test: train on all 9t pit samples, score the 613590 pit samples (pre-registration:
docs/iterations/nisar_heldout_613590_prereg.md, committed before this ran).

Only bands present on both tiles are used. No 613590 row influences training. The gate is the one of the model
script: NISAR + rich lidar baseline must beat the rich baseline by 0.05, and here also the lower end of a block
bootstrap of the difference must be above 0.

  python _nisar_feat_heldout_9t.py          (run from the 9t default environment; reads both samples files)
"""
import json

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

BOOT, SEED, GATE = 1000, 20261027, 0.05


def main():
    tr = C.load_samples("pit", "", tag="9t_slc")
    te = C.load_samples("pit", "", tag="613590_slc")
    common = [n for n in tr["names"] if n in set(te["names"])]
    missing = [n for n in tr["names"] if n not in set(te["names"])]
    print(f"{len(common)} bands on both tiles; {len(missing)} 9t bands missing on 613590: {sorted({m.split(':')[0] for m in missing})}", flush=True)
    it = [tr["names"].index(n) for n in common]
    ie = [te["names"].index(n) for n in common]
    Xtr, Xte = tr["X"][:, it], te["X"][:, ie]
    ytr, yte, gte = tr["y"], te["y"], te["grp"]
    prod = np.array([n.split(":")[0] for n in common])
    ctl, lt, ctx, sar = C.feature_groups(prod)
    sets = {"simple lidar baseline": ctl, "rich lidar baseline": ctl | lt, "all NISAR": sar,
            "NISAR + rich baseline": sar | ctl | lt, "NISAR + simple baseline": sar | ctl}
    print(f"train {int(ytr.sum())} pits / {int((1 - ytr).sum())} decoys; test {int(yte.sum())} pits / {int((1 - yte).sum())} decoys "
          f"in {len(np.unique(gte))} blocks", flush=True)
    P, rows = {}, []
    for k, m in sets.items():
        P[k] = C.fit_predict(Xtr[:, m], ytr, Xte[:, m])
        rows.append(dict(feature_set=k, n_bands=int(m.sum()), auc=round(roc_auc_score(yte, P[k]), 3)))
        print(rows[-1], flush=True)
    rng = np.random.default_rng(SEED)
    ug = np.unique(gte)
    where = {g: np.flatnonzero(gte == g) for g in ug}
    boot = {k: [] for k in P}
    diff = []
    for _ in range(BOOT):
        idx = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(yte[idx])) < 2:
            continue
        a = {k: roc_auc_score(yte[idx], P[k][idx]) for k in P}
        for k in P:
            boot[k].append(a[k])
        diff.append(a["NISAR + rich baseline"] - a["rich lidar baseline"])
    for r in rows:
        r["ci_lo"], r["ci_hi"] = (round(float(v), 3) for v in np.percentile(boot[r["feature_set"]], [2.5, 97.5]))
    d_obs = roc_auc_score(yte, P["NISAR + rich baseline"]) - roc_auc_score(yte, P["rich lidar baseline"])
    lo, hi = np.percentile(diff, [2.5, 97.5])
    passed = bool(d_obs >= GATE and lo > 0)
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    print(f"gain NISAR + rich over rich: {d_obs:+.3f} (block bootstrap 95% {lo:+.3f} to {hi:+.3f}); gate passed: {passed}")
    out = C.A.path_for("data") / "613590" / "results" / "nisar"
    res.to_csv(out / "nisar_pit_heldout_auc_613590_slc.csv", index=False)
    json.dump(dict(n_pits=int(yte.sum()), n_decoys=int((1 - yte).sum()), n_blocks=int(len(ug)), n_bands=len(common),
                   missing_bands=missing, gain_nisar_plus_rich_over_rich=d_obs, boot_lo=float(lo), boot_hi=float(hi),
                   gate=GATE, passes_gate=passed), open(out / "nisar_pit_heldout_summary_613590_slc.json", "w"), indent=2)


if __name__ == "__main__":
    main()
