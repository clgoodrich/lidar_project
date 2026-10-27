"""HH against HV on identical band recipes, and a shuffled-label null.

Every band whose name carries an `hh` token has an `hv` twin built by the same recipe (same product, same
window, same track) except the sub-aperture product, which is HH only. This script keeps only complete
twins, so the two sides hold the same number of bands of the same kinds.
  pairs   per-band AUC of each twin, strength = |AUC - 0.5|; paired signed-rank test of HH against HV
  models  gradient boosting (as _nisar_feat_model_9t.py) on HH twins, HV twins, both, and each + lidar baseline
  null    the "both" model refitted with labels shuffled among rows of the same 500 m block, NPERM times;
          the real AUC is compared with that spread (it answers "could this be chance?")

  [TARGET=pit] [CORE_SHRINK_M=15] [ROAD_NEAR=1] python notebooks/wellsight_v2/s5_eval/_nisar_feat_hhhv_9t.py
"""
import os
import re

import numpy as np
import pandas as pd
from scipy.stats import rankdata, wilcoxon
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
from _nisar_feat_ablate_9t import SUFFIX, TARGET, oof

NPERM = int(os.environ.get("NPERM", 20))


def auc_of(a, b):
    r = rankdata(np.r_[a, b])
    return (r[:len(a)].sum() - len(a) * (len(a) + 1) / 2) / (len(a) * len(b))


def twin(name, to):
    return re.sub(r"(^|_)hh(_|$)", rf"\1{to}\2", name.split(":", 1)[1]) if re.search(r"(^|_)hh(_|$)", name) else None


def main():
    z = np.load(C.FEAT_DIR / f"nisar_{TARGET}_samples_{C.A.TAG}{SUFFIX}.npz", allow_pickle=True)
    names = [str(n) for n in z["names"]]
    pad, dec, dec_pad = z["pad"], z["dec"], z["dec_pad"]
    keep = np.isin(np.arange(pad.shape[1]), np.unique(dec_pad)) & np.isfinite(pad[names.index("control:cover")])
    pads = np.flatnonzero(keep)
    sel = np.flatnonzero(np.isin(dec_pad, pads))
    X = np.vstack([pad[:, pads].T, dec[:, sel].T])
    y = np.r_[np.ones(len(pads)), np.zeros(len(sel))].astype(int)
    grp = np.r_[z["pad_block"][pads], z["dec_block"][sel]]
    nan = np.stack([np.isnan(X[y == 1]).mean(0), np.isnan(X[y == 0]).mean(0)]).max(0)
    good = nan <= 0.20
    names = [n for n, g in zip(names, good) if g]
    X = X[:, good]
    Xi = np.where(np.isnan(X), np.nanmedian(X, 0), X)
    col = {n: i for i, n in enumerate(names)}
    rows = []
    for n in names:
        t = twin(n, "hv")
        if t is None or n.split(":")[0] in ("control", "context"):
            continue
        m = f"{n.split(':')[0]}:{t}"
        if m in col:
            a, b = col[n], col[m]
            rows.append(dict(product=n.split(":")[0], hh=n, hv=m,
                             auc_hh=auc_of(Xi[y == 1, a], Xi[y == 0, a]), auc_hv=auc_of(Xi[y == 1, b], Xi[y == 0, b])))
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
        a = roc_auc_score(y, oof(Xi[:, m], y, grp))
        res.append(dict(feature_set=k, n_bands=len(m), auc=round(a, 3)))
        print(res[-1], flush=True)
    rng = np.random.default_rng(20261026)
    both = sets["HH + HV twins"]
    null = []
    for i in range(NPERM):
        ys = y.copy()
        for g in np.unique(grp):
            ix = np.flatnonzero(grp == g)
            ys[ix] = rng.permutation(y[ix])
        null.append(roc_auc_score(ys, oof(Xi[:, both], ys, grp)))
    real = [r["auc"] for r in res if r["feature_set"] == "HH + HV twins"][0]
    res.append(dict(feature_set=f"shuffled labels, HH + HV twins ({NPERM} runs): mean / max", n_bands=len(both),
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
