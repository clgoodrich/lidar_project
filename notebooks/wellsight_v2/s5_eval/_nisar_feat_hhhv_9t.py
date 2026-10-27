"""HH against HV on identical band recipes, and a shuffled-label null.

Every band whose name carries an `hh` token has an `hv` twin built by the same recipe (same product, same
window, same track) except the sub-aperture product, which is HH only. This script keeps only complete
twins, so the two sides hold the same number of bands of the same kinds.
  pairs   per-band AUC of each twin, strength = |AUC - 0.5|; paired signed-rank test of HH against HV
          (the bands are correlated, so that p is optimistic)
  models  gradient boosting on HH twins, HV twins, both, and each + lidar baseline (C.oof_probs)
  null    the "both" model refitted with labels shuffled among rows of the same 500 m block, NPERM times

  [TARGET=pit] [CORE_SHRINK_M=15] [ROAD_NEAR=1] [LOCAL_M=1500] python _nisar_feat_hhhv_9t.py
"""
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
from _nisar_feat_ablate_9t import SUFFIX, TARGET

NPERM = int(os.environ.get("NPERM", 20))


def auc_of(a, b):
    r = rankdata(np.r_[a, b])
    return (r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))


def twin(name, to):
    return re.sub(r"(^|_)hh(_|$)", rf"\1{to}\2", name.split(":", 1)[1]) if re.search(r"(^|_)hh(_|$)", name) else None


def main():
    S = C.load_samples(TARGET, SUFFIX)
    names, X, y, grp = S["names"], S["X"], S["y"], S["grp"]
    col = {n: i for i, n in enumerate(names)}

    def band_auc(i):
        v = X[:, i]
        ok = np.isfinite(v)
        return auc_of(v[ok & (y == 1)], v[ok & (y == 0)])

    rows = []
    for n in names:
        t = twin(n, "hv")
        if t is None or n.split(":")[0] in ("control", "context", "lidartex"):
            continue
        m = f"{n.split(':')[0]}:{t}"
        if m in col:
            rows.append(dict(product=n.split(":")[0], hh=n, hv=m, auc_hh=band_auc(col[n]), auc_hv=band_auc(col[m])))
    pr = pd.DataFrame(rows)
    pr["strength_hh"], pr["strength_hv"] = (pr.auc_hh - 0.5).abs(), (pr.auc_hv - 0.5).abs()
    pr["hh_stronger"] = pr.strength_hh > pr.strength_hv
    pr = pr.round(3)
    pr.to_csv(C.OUT / f"nisar_{TARGET}_hhhv_pairs_{C.A.TAG}{SUFFIX}.csv", index=False)
    by = pr.groupby("product").agg(n=("hh", "size"), hh=("strength_hh", "mean"), hv=("strength_hv", "mean"),
                                   hh_wins=("hh_stronger", "sum")).round(3)
    p = wilcoxon(pr.strength_hh, pr.strength_hv).pvalue
    print(f"{len(pr)} twin pairs; mean strength HH {pr.strength_hh.mean():.3f} HV {pr.strength_hv.mean():.3f}; "
          f"HH stronger in {int(pr.hh_stronger.sum())}; signed-rank p {p:.2g}")
    print(by.to_string())
    hh_i = np.array([col[n] for n in pr.hh]), np.array([col[n] for n in pr.hv])
    ctl = np.array([i for i, n in enumerate(names) if n.startswith("control:")])
    sets = {"HH twins": hh_i[0], "HV twins": hh_i[1], "HH + HV twins": np.r_[hh_i[0], hh_i[1]],
            "lidar baseline": ctl, "HH twins + baseline": np.r_[hh_i[0], ctl], "HV twins + baseline": np.r_[hh_i[1], ctl],
            "HH + HV twins + baseline": np.r_[hh_i[0], hh_i[1], ctl]}
    res = []
    for k, m in sets.items():
        pp, _ = C.oof_probs(X[:, m], y, grp)
        res.append(dict(feature_set=k, n_bands=len(m), auc=round(roc_auc_score(y, pp), 3)))
        print(res[-1], flush=True)
    rng = np.random.default_rng(20261026)
    both = sets["HH + HV twins"]
    null = []
    for _ in range(NPERM):
        ys = y.copy()
        for g in np.unique(grp):
            ix = np.flatnonzero(grp == g)
            ys[ix] = rng.permutation(y[ix])
        pp, _ = C.oof_probs(X[:, both], ys, grp)
        null.append(roc_auc_score(ys, pp))
    real = [r["auc"] for r in res if r["feature_set"] == "HH + HV twins"][0]
    res.append(dict(feature_set=f"shuffled labels within block, HH + HV twins ({NPERM} runs): mean", n_bands=len(both),
                    auc=round(float(np.mean(null)), 3)))
    res.append(dict(feature_set="shuffled labels: max", n_bands=len(both), auc=round(float(np.max(null)), 3)))
    print(f"real {real} against shuffled mean {np.mean(null):.3f} sd {np.std(null):.3f} max {np.max(null):.3f}")
    out = pd.DataFrame(res)
    path = C.OUT / f"nisar_{TARGET}_hhhv_models_{C.A.TAG}{SUFFIX}.csv"
    out.to_csv(path, index=False)
    print(out.to_string(index=False))
    print(path)


if __name__ == "__main__":
    main()
