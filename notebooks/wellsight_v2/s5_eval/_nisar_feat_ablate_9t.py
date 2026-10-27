"""Which NISAR aspect carries the signal? Leave-one-group-out, polarisation and track ablations on the scored samples.

Reads the samples dumped by _nisar_feat_score_9t.py (same file the model script reads) and fits the same
gradient-boosting model, 5-fold CV grouped by 500 m block. Sets:
  all NISAR                   reference
  without <group>             all NISAR minus one product group (a big drop means the group is needed)
  HH bands only / HV bands only / bands with no polarisation in the name
  descending track 026 only / ascending tracks 090 + 162 only
For pads with pad_area in the file, the all-NISAR out-of-fold AUC is also split by pad-area tercile.

  [TARGET=pit] [CORE_SHRINK_M=15] [ROAD_NEAR=1] [MATCH_ROUGH=1] python notebooks/wellsight_v2/s5_eval/_nisar_feat_ablate_9t.py
"""
import os
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
BASE = 0 if TARGET == "pit" else 5
CORE = float(os.environ.get("CORE_SHRINK_M", BASE))
SUFFIX = (("" if CORE == BASE else f"_core{CORE:.0f}m") + ("_roadnear" if os.environ.get("ROAD_NEAR") == "1" else "")
          + ("_roughmatch" if os.environ.get("MATCH_ROUGH") == "1" else "") + (f"_local{float(os.environ['LOCAL_M']):.0f}" if float(os.environ.get("LOCAL_M", 0)) else ""))
SEED = 20261026


def oof(X, y, grp):
    p = np.full(len(y), np.nan)
    for tr, te in GroupKFold(5).split(X, y, grp):
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, l2_regularization=1.0,
                                           min_samples_leaf=40, class_weight="balanced", random_state=SEED)
        m.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


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
    X = np.where(np.isnan(X), np.nanmedian(X, 0), X)
    prod = np.array([n.split(":")[0] for n in names])
    band = np.array([n.split(":")[1] for n in names])
    sar = ~np.isin(prod, ["control", "context"])
    has = lambda tok: np.array([re.search(rf"(^|_){tok}(_|$)", b) is not None for b in band])  # noqa: E731
    trk = np.array([re.search(r"_t(\d{3})$", b).group(1) if re.search(r"_t(\d{3})$", b) else "" for b in band])
    sets = {"all NISAR": sar}
    for g in sorted(set(prod[sar])):
        sets[f"without {g}"] = sar & (prod != g)
    sets["HH bands only"] = sar & has("hh")
    sets["HV bands only"] = sar & has("hv")
    sets["no polarisation in name"] = sar & ~has("hh") & ~has("hv")
    sets["descending t026 only"] = sar & (trk == "026")
    sets["ascending t090 + t162 only"] = sar & np.isin(trk, ["090", "162"])
    rows, p_all = [], None
    for k, m in sets.items():
        if m.sum() < 3:
            continue
        p = oof(X[:, m], y, grp)
        if k == "all NISAR":
            p_all = p
        rows.append(dict(feature_set=k, n_bands=int(m.sum()), auc=round(roc_auc_score(y, p), 3)))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    ref = float(res.loc[res.feature_set == "all NISAR", "auc"].iloc[0])
    res["change_vs_all"] = (res.auc - ref).round(3)
    if "pad_area" in z.files and TARGET == "pad":
        area = np.r_[z["pad_area"][pads], z["pad_area"][dec_pad[sel]]]
        edges = np.quantile(z["pad_area"][pads], [0, 1 / 3, 2 / 3, 1])
        for i in range(3):
            lo, hi = edges[i], edges[i + 1] + (1e-9 if i == 2 else 0)
            m = (area >= lo) & (area < hi)
            row = dict(feature_set=f"pad area {lo:.0f}-{edges[i + 1]:.0f} m2 (tercile {i + 1}), all NISAR",
                       n_bands=int(sar.sum()), auc=round(roc_auc_score(y[m], p_all[m]), 3))
            res = pd.concat([res, pd.DataFrame([row])], ignore_index=True)
            print(row, flush=True)
    path = C.OUT / f"nisar_{TARGET}_ablation_auc_{C.A.TAG}{SUFFIX}.csv"
    res.to_csv(path, index=False)
    print(res.to_string(index=False))
    print(path)


if __name__ == "__main__":
    main()
