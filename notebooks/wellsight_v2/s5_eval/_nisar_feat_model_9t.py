"""Product 10: do the NISAR bands, together, separate pads from matched decoys beyond cover + slope + roughness?

Reads the samples dumped by _nisar_feat_score_9t.py (pad core medians, matched decoy disc medians; decoys
share cover within 0.05 and slope within 1 degree with their pad). Gradient boosting, 5-fold CV grouped by
500 m block so neighbours never sit in both train and test. Out-of-fold AUC per feature set, pooled over
folds, with a block-bootstrap CI. Gate: NISAR must beat the lidar baseline by at least GATE AUC.

Feature sets: baseline (lidar cover, slope, roughness), all NISAR bands, NISAR + baseline, and each product
group alone. Also the open-ground pads (pad cover < 0.25) on their own.

  [CORE_SHRINK_M=15] python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import GroupKFold

import _nisar_feat_common as C

TARGET = os.environ.get("TARGET", "pad")
CORE = float(os.environ.get("CORE_SHRINK_M", 0 if TARGET == "pit" else 5))
SUFFIX = ("" if CORE == (0 if TARGET == "pit" else 5) else f"_core{CORE:.0f}m") + ("_roadnear" if os.environ.get("ROAD_NEAR") == "1" else "")
GATE, SEED, NB = 0.05, 20261026, 200


def oof_auc(X, y, grp, open_mask):
    p = np.full(len(y), np.nan)
    for tr, te in GroupKFold(5).split(X, y, grp):
        m = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06, max_iter=200, l2_regularization=1.0,
                                           min_samples_leaf=40, class_weight="balanced", random_state=SEED)
        m.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    rng = np.random.default_rng(SEED)
    ug = np.unique(grp)
    bs = []
    for _ in range(NB):
        pick = rng.choice(ug, len(ug))
        idx = np.concatenate([np.flatnonzero(grp == g) for g in pick])
        if len(set(y[idx])) == 2:
            bs.append(roc_auc_score(y[idx], p[idx]))
    ok = open_mask
    return roc_auc_score(y, p), *np.percentile(bs, [2.5, 97.5]), roc_auc_score(y[ok], p[ok])


def main():
    z = np.load(C.FEAT_DIR / f"nisar_{TARGET}_samples_{C.A.TAG}{SUFFIX}.npz", allow_pickle=True)
    names = [str(n) for n in z["names"]]
    pad, dec, dec_pad = z["pad"], z["dec"], z["dec_pad"]
    keep = np.isin(np.arange(pad.shape[1]), np.unique(dec_pad)) & np.isfinite(pad[names.index("control:cover")])
    pads = np.flatnonzero(keep)
    sel = np.flatnonzero(np.isin(dec_pad, pads))
    X_all = np.vstack([pad[:, pads].T, dec[:, sel].T])
    y = np.r_[np.ones(len(pads)), np.zeros(len(sel))].astype(int)
    grp = np.r_[z["pad_block"][pads], z["dec_block"][sel]]
    cov = np.r_[z["pad_cover"][pads], z["pad_cover"][dec_pad[sel]]]
    open_mask = cov < 0.25
    # missingness must not carry the label: drop bands that are >20% NaN in either class, median-impute the rest
    nanrate = np.stack([np.isnan(X_all[y == 1]).mean(0), np.isnan(X_all[y == 0]).mean(0)])
    good = nanrate.max(0) <= 0.20
    print(f"dropped {int((~good).sum())} bands for missingness", flush=True)
    names = [n for n, g in zip(names, good) if g]
    X_all = X_all[:, good]
    X_all = np.where(np.isnan(X_all), np.nanmedian(X_all, 0), X_all)
    prod = np.array([n.split(":")[0] for n in names])
    ctl = prod == "control"
    ctx = prod == "context"          # road annotations: circular for pads, never counted as NISAR
    sar = ~ctl & ~ctx
    sets = {"baseline (cover, slope, rough)": ctl, "all NISAR": sar, "NISAR + baseline": sar | ctl,
            "NISAR without geometry (SAR only)": sar & (prod != "geometry")}
    if ctx.any():
        sets.update({"road context only": ctx, "NISAR + road context": sar | ctx})
    for g in sorted(set(prod) - {"control", "context"}):
        sets[f"only {g}"] = prod == g
    rows = []
    for k, m in sets.items():
        auc, lo, hi, auc_open = oof_auc(X_all[:, m], y, grp, open_mask)
        rows.append(dict(feature_set=k, n_bands=int(m.sum()), auc=round(auc, 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                         auc_open=round(auc_open, 3)))
        print(rows[-1], flush=True)
    # placebo: the first decoy of each pad plays "pad" against the other decoys (same matching), AUC must be near 0.5
    first = np.array([np.flatnonzero(dec_pad[sel] == p)[0] for p in pads])
    yp = np.zeros(len(sel), int)
    yp[first] = 1
    nn = sar
    auc, lo, hi, auc_open = oof_auc(X_all[len(pads):][:, nn], yp, grp[len(pads):], open_mask[len(pads):])
    rows.append(dict(feature_set="placebo: decoy vs decoy, all NISAR", n_bands=int(nn.sum()), auc=round(auc, 3),
                     ci_lo=round(lo, 3), ci_hi=round(hi, 3), auc_open=round(auc_open, 3)))
    print(rows[-1], flush=True)
    res = pd.DataFrame(rows)
    base = float(res.loc[0, "auc"])
    res["gain_over_baseline"] = (res.auc - base).round(3)
    path = C.OUT / f"nisar_{TARGET}_model_auc_by_set_{C.A.TAG}{SUFFIX}.csv"
    res.to_csv(path, index=False)
    json.dump(dict(n_pads=int(len(pads)), n_decoys=int(len(sel)), gate=GATE, core_shrink_m=CORE, baseline_auc=base,
                   passes_gate=bool(res.loc[res.feature_set == "all NISAR", "gain_over_baseline"].iloc[0] >= GATE)),
              open(C.OUT / f"nisar_{TARGET}_model_summary_{C.A.TAG}{SUFFIX}.json", "w"), indent=2)
    print(res.to_string(index=False))


if __name__ == "__main__":
    main()
