"""Pit NISAR drop (0.829 to 0.568): decoy design or smaller sample? (outside-review follow-up 5, 2026-10-27, 9t)

The first pit design scored 495 pit targets with 10 decoys each. The design with the pit's own footprint and matched
incidence (shape_inc) keeps only the pits that still find decoys, so the two designs score different pits and different
decoys. Here both are scored on one fixed set of pits, the pits present in every design listed in DESIGNS.

Two ways to read each design on the fixed set:
  retrained   the models are trained and scored on the fixed pits and that design's decoys only (same pits everywhere)
  pooled      the models are trained on the full design, and the AUC is read on the fixed pits and their decoys
Models: rich lidar, all NISAR, NISAR + rich lidar (repeated shuffled grouped CV, REPEATS repeats, as the repeat script).

  DESIGNS=",_shape_inc" REPEATS=5 NISAR_STACK=slc python _nisar_pit_fixed_subset_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
import _nisar_feat_repeat_9t as R

DESIGNS = os.environ.get("DESIGNS", ",_shape_inc").split(",")
REPEATS, SEED = int(os.environ.get("REPEATS", 5)), 20261027


def load(suffix):
    S = C.load_samples("pit", suffix)
    z = S["z"]
    S["pid"] = np.r_[S["pads"], z["dec_pad"][S["sel"]]]
    return S


def models(S, rows_mask):
    names, X, y, grp, xy, prod = S["names"], S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    m = rows_mask
    sets = {"rich lidar": X[m][:, ctl | lt], "all NISAR": X[m][:, sar], "NISAR + rich lidar": X[m][:, sar | ctl | lt]}
    runs = Parallel(n_jobs=4)(delayed(R.one_repeat)(sets, y[m], grp[m], xy[m], r) for r in range(REPEATS))
    return {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}


def main():
    D = {d: load(d) for d in DESIGNS}
    fixed = set(D[DESIGNS[0]]["pads"])
    for d in DESIGNS[1:]:
        fixed &= set(D[d]["pads"])
    fixed = np.array(sorted(fixed))
    print(f"pits per design: { {d or 'first': len(S['pads']) for d, S in D.items()} }; fixed set {len(fixed)}", flush=True)
    rows = []
    for d, S in D.items():
        y, grp = S["y"], S["grp"]
        m = np.isin(S["pid"], fixed)
        for mode in ("retrained", "pooled"):
            if mode == "retrained":
                pm = models(S, m)
                yy, gg = y[m], grp[m]
                mm = np.ones(m.sum(), bool)
            else:
                pm = models(S, np.ones(len(y), bool))
                yy, gg, mm = y, grp, m
            row = dict(design=d or "first", mode=mode, n_pits=len(fixed) if mode == "retrained" else len(fixed), n_decoys=int((mm & (yy == 0)).sum()))
            for k, p in pm.items():
                row[f"auc_{k}"] = roc_auc_score(yy[mm], p[mm])
            row["gain_over_rich"] = row["auc_NISAR + rich lidar"] - row["auc_rich lidar"]
            ug = np.unique(gg[mm])
            where = {g: np.flatnonzero((gg == g) & mm) for g in ug}
            rng = np.random.default_rng(SEED)
            b = []
            for _ in range(500):
                ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
                if len(set(yy[ix])) == 2:
                    b.append(roc_auc_score(yy[ix], pm["NISAR + rich lidar"][ix]) - roc_auc_score(yy[ix], pm["rich lidar"][ix]))
            row["gain_ci"] = f"{np.percentile(b, 2.5):+.3f} to {np.percentile(b, 97.5):+.3f}"
            rows.append(row)
            print(row, flush=True)
    # the same, on each design's own full pit set (for the attrition column)
    for d, S in D.items():
        pm = models(S, np.ones(len(S["y"]), bool))
        rows.append(dict(design=d or "first", mode="own full set", n_pits=len(S["pads"]), n_decoys=int((S["y"] == 0).sum()),
                         **{f"auc_{k}": roc_auc_score(S["y"], p) for k, p in pm.items()}))
        rows[-1]["gain_over_rich"] = rows[-1]["auc_NISAR + rich lidar"] - rows[-1]["auc_rich lidar"]
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows).round(3)
    pd.set_option("display.width", 300)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_pit_fixed_subset_auc_{C.A.TAG}.csv", index=False)


if __name__ == "__main__":
    main()
