"""Which NISAR aspect carries the signal? Leave-one-group-out, polarisation and track ablations on the scored samples.

Same samples, CV (5-fold by 500 m block, 250 m train-test buffer, fold-local preprocessing) and model as
_nisar_feat_model_9t.py. Sets: all SAR bands; without each product group; HH bands only, HV bands only, bands with
no polarisation in the name; descending track 026 only, ascending tracks 090 + 162 only. For pads, the all-SAR
out-of-fold AUC is also split by pad-area tercile.

  [TARGET=pit] [CORE_SHRINK_M=15] [ROAD_NEAR=1] [MATCH_ROUGH=1] [LOCAL_M=1500] python _nisar_feat_ablate_9t.py
"""
import os
import re

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
BASE = 0 if TARGET == "pit" else 5
CORE = float(os.environ.get("CORE_SHRINK_M", BASE))
SUFFIX = C.suffix(TARGET)


def main():
    S = C.load_samples(TARGET, SUFFIX)
    names, X, y, grp, prod = S["names"], S["X"], S["y"], S["grp"], S["prod"]
    band = np.array([n.split(":")[1] for n in names])
    ctl, lt, ctx, sar = C.feature_groups(prod)
    has = lambda tok: np.array([re.search(rf"(^|_){tok}(_|$)", b) is not None for b in band])  # noqa: E731
    trk = np.array([(re.search(r"_t(\d{3})$", b) or [None, ""])[1] for b in band])
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
        p, folds = C.oof_probs(X[:, m], y, grp)
        if k == "all NISAR":
            p_all = p
        fa = [roc_auc_score(y[te], p[te]) for te in folds if len(set(y[te])) == 2]
        rows.append(dict(feature_set=k, n_bands=int(m.sum()), auc=round(roc_auc_score(y, p), 3), fold_mean=round(np.mean(fa), 3)))
        print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    ref = float(res.loc[res.feature_set == "all NISAR", "auc"].iloc[0])
    res["change_vs_all"] = (res.auc - ref).round(3)
    z = S["z"]
    if "pad_area" in z.files and TARGET == "pad":
        area = np.r_[z["pad_area"][S["pads"]], z["pad_area"][z["dec_pad"][S["sel"]]]]
        edges = np.quantile(z["pad_area"][S["pads"]], [0, 1 / 3, 2 / 3, 1])
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
