"""Does reusing decoy locations change the NISAR result? (outside review 2026-11-03)

The scorer draws 10 decoys per pit but several pits pick the same location. On the 9t pit design 4,890 decoy rows sit on 4,115 distinct
centres. Exact repeats share a block, so they never cross a CV fold, but they count more than once in the AUC and in the training set.
Here every repeat is dropped (key = centre pixel and footprint size) and the same model is scored again with the same folds rule.

Compares, for the full and the de-duplicated rows: rich lidar baseline, all NISAR, NISAR + rich baseline, and the gain. Block-bootstrap
interval of the gain on the de-duplicated rows.

  [TARGET=pit|pad] [LOCAL_M=1500] NISAR_STACK=slc python _nisar_feat_dedupe_9t.py
"""
import os

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pit")
SUFFIX = C.suffix(TARGET)
NB, SEED = 300, 20261103


def auc_sets(S, rows, sets):
    y, grp = S["y"][rows], S["grp"][rows]
    out, P = {}, {}
    old = C.CV_XY
    C.CV_XY = S["xy"][rows]
    for k, cols in sets.items():
        p, _ = C.oof_probs(S["X"][rows][:, cols], y, grp)
        P[k] = p
        out[k] = roc_auc_score(y, p)
    C.CV_XY = old
    return out, P, y, grp


def main():
    S = C.load_samples(TARGET, SUFFIX)
    z = S["z"]
    n0 = len(S["pads"])
    ctl, lt, ctx, sar = C.feature_groups(S["prod"])
    sets = {"rich lidar baseline": ctl | lt, "all NISAR": sar, "NISAR + rich baseline": sar | ctl | lt}
    key = np.array([f"{c}_{n}" for c, n in zip(z["dec_ctr"][S["sel"]] if len(z["dec_ctr"]) != len(S["sel"]) else z["dec_ctr"], z["dec_n"][S["sel"]] if len(z["dec_n"]) != len(S["sel"]) else z["dec_n"])])
    first = np.unique(key, return_index=True)[1]
    keep = np.r_[np.arange(n0), n0 + np.sort(first)]
    full = np.arange(len(S["y"]))
    print(f"{TARGET}{SUFFIX}: {n0} targets, {len(key)} decoys, {len(first)} distinct decoys", flush=True)
    rows = []
    res = {}
    for name, idx in (("all rows", full), ("repeats dropped", keep)):
        a, P, y, grp = auc_sets(S, idx, sets)
        res[name] = (a, P, y, grp)
        rows.append(dict(rows=name, n_targets=int(y.sum()), n_decoys=int((1 - y).sum()), **{k: round(v, 3) for k, v in a.items()},
                         gain=round(a["NISAR + rich baseline"] - a["rich lidar baseline"], 3)))
        print(rows[-1], flush=True)
    a, P, y, grp = res["repeats dropped"]
    rng = np.random.default_rng(SEED)
    ug = np.unique(grp)
    where = {g: np.flatnonzero(grp == g) for g in ug}
    diff = []
    for _ in range(NB):
        idx = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
        if len(set(y[idx])) == 2:
            diff.append(roc_auc_score(y[idx], P["NISAR + rich baseline"][idx]) - roc_auc_score(y[idx], P["rich lidar baseline"][idx]))
    lo, hi = np.percentile(diff, [2.5, 97.5])
    print(f"gain with repeats dropped {rows[-1]['gain']:+.3f}, block bootstrap 95% {lo:+.3f} to {hi:+.3f}")
    df = pd.DataFrame(rows)
    df["gain_ci_lo"] = [np.nan, round(float(lo), 3)]
    df["gain_ci_hi"] = [np.nan, round(float(hi), 3)]
    df.to_csv(C.OUT / f"nisar_{TARGET}_dedupe_auc_{C.A.TAG}{SUFFIX}.csv", index=False)
    print(C.OUT / f"nisar_{TARGET}_dedupe_auc_{C.A.TAG}{SUFFIX}.csv")


if __name__ == "__main__":
    main()
