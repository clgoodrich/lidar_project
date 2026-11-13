"""Does NISAR help where lidar is weak? (outside-review follow-up 1, 2026-10-27, 9t)

The tests so far average over every pad, and most pads are easy for lidar (AUC near 0.99), so a gain cannot show. Here the
pads are split by how well lidar does on them, and the radar is scored on the hard ones.

Subsets of the pad targets (each target is scored against its own matched decoys):
  all                      every target (reference)
  U-Net missed             no out-of-fold U-Net candidate (probability >= TAU) overlaps the pad at IoU >= 0.3
  U-Net found              the rest
  lidar-weak quartile      the 25% of targets with the lowest out-of-fold probability from the rich lidar model
  covered by canopy        pad cover > 0.5 (grown over)
  weak and covered         intersection of the last two
Models (repeated shuffled grouped CV, fold-local preprocessing, 250 m buffer, probabilities averaged over repeats):
  rich lidar, all NISAR, NISAR + rich lidar, and a control "permuted NISAR + rich lidar" in which the NISAR rows are shuffled
  across all samples (same width, no information about the target). The control exists because a subset chosen for low lidar
  score makes any added model look better by regression to the mean. The gain that counts is the combined gain minus the
  permuted-control gain.
Per subset: AUC of each model, paired gains with a block-bootstrap interval (500 m blocks resampled inside the subset).

  [LOCAL_M=1500] [REPEATS=5] [TAU=0.3] NISAR_STACK=slc python _nisar_weak_lidar_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import geopandas as gpd
import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
import _nisar_feat_repeat_9t as R
import _nisar_pad_fp_screen_9t as F

SUFFIX = C.suffix("pad")
REPEATS, SEED, BOOT = int(os.environ.get("REPEATS", 5)), 20261027, 500
CACHE = C.OUT / f"nisar_pad_unet_found_per_pad_9t_slc_{F.TAGU}.csv"


def unet_found_per_pad():
    """Best IoU of any out-of-fold U-Net candidate with every annotated pad (cached)."""
    if CACHE.exists():
        return pd.read_csv(CACHE)
    cand = F.candidates()
    pads = F.U.read_layer(F.U.ANN_GPKG, "pad").to_crs(F.U.CRS)[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
    sidx = cand.sindex
    best = []
    for g in pads.geometry:
        b = 0.0
        for j in sidx.query(g, predicate="intersects"):
            c = cand.geometry.iloc[j]
            i = g.intersection(c).area
            if i > 0:
                b = max(b, i / (g.area + c.area - i))
        best.append(b)
    out = pd.DataFrame(dict(pad_id=pads.pad_id, x=pads.geometry.centroid.x, y=pads.geometry.centroid.y, best_iou=best))
    out.to_csv(CACHE, index=False)
    return out


def sub_auc(y, p, m):
    return roc_auc_score(y[m], p[m]) if len(set(y[m])) == 2 else np.nan


def main():
    S = C.load_samples("pad", SUFFIX)
    names, X, y, grp, xy, prod = S["names"], S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    z, pads, sel = S["z"], S["pads"], S["sel"]
    pid = np.r_[pads, z["dec_pad"][sel]]                   # pad index of every row
    n_t = len(pads)
    ann = unet_found_per_pad()
    d = np.hypot(z["pad_xy"][pads][:, None, 0] - ann.x.values[None], z["pad_xy"][pads][:, None, 1] - ann.y.values[None])
    j = d.argmin(1)
    print(f"targets {n_t}; matched to an annotated pad within {np.median(d.min(1)):.1f} m (median), max {d.min(1).max():.1f} m", flush=True)
    iou = ann.best_iou.values[j]
    missed = iou < 0.3
    rng = np.random.default_rng(SEED)
    perm = rng.permutation(len(y))
    sets = {"rich lidar": X[:, ctl | lt], "all NISAR": X[:, sar], "NISAR + rich lidar": X[:, sar | ctl | lt],
            "permuted NISAR + rich lidar": np.hstack([X[:, sar][perm], X[:, ctl | lt]])}
    runs = Parallel(n_jobs=4)(delayed(R.one_repeat)(sets, y, grp, xy, r) for r in range(REPEATS))
    pm = {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}
    lidar_t = pm["rich lidar"][:n_t]
    weak = lidar_t <= np.nanpercentile(lidar_t, 25)
    cov = z["pad_cover"][pads] > 0.5
    subsets = {"all": np.ones(n_t, bool), "U-Net missed": missed, "U-Net found": ~missed, "lidar-weak quartile": weak,
               "covered by canopy (cover > 0.5)": cov, "weak and covered": weak & cov}
    rows = []
    for nm, tm in subsets.items():
        ids = pads[tm]
        m = np.isin(pid, ids)
        row = dict(subset=nm, n_targets=int(tm.sum()), n_decoys=int((m & (y == 0)).sum()), n_blocks=len(np.unique(grp[m])))
        for k in sets:
            row[f"auc_{k}"] = sub_auc(y, pm[k], m)
        for k in ("NISAR + rich lidar", "permuted NISAR + rich lidar"):
            row[f"gain_{k}"] = row[f"auc_{k}"] - row["auc_rich lidar"]
        row["gain_net_of_permuted"] = row["gain_NISAR + rich lidar"] - row["gain_permuted NISAR + rich lidar"]
        ug = np.unique(grp[m])
        where = {g: np.flatnonzero((grp == g) & m) for g in ug}
        b_raw, b_net = [], []
        for _ in range(BOOT):
            ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
            if len(set(y[ix])) < 2:
                continue
            a = roc_auc_score(y[ix], pm["NISAR + rich lidar"][ix])
            p_ = roc_auc_score(y[ix], pm["permuted NISAR + rich lidar"][ix])
            l_ = roc_auc_score(y[ix], pm["rich lidar"][ix])
            b_raw.append(a - l_)
            b_net.append((a - l_) - (p_ - l_))
        if len(b_net) > 50:
            row["gain_ci"] = f"{np.percentile(b_raw, 2.5):+.3f} to {np.percentile(b_raw, 97.5):+.3f}"
            row["net_gain_ci"] = f"{np.percentile(b_net, 2.5):+.3f} to {np.percentile(b_net, 97.5):+.3f}"
        rows.append(row)
        print(row, flush=True)
    res = pd.DataFrame(rows).round(3)
    pd.set_option("display.width", 300)
    print(res.T.to_string(header=False))
    res.to_csv(C.OUT / f"nisar_pad_weak_lidar_auc_{C.A.TAG}{SUFFIX}_{F.TAGU}.csv", index=False)
    print(f"U-Net missed {int(missed.sum())} of {n_t} ({missed.mean():.1%}) at tau {F.TAU}")


if __name__ == "__main__":
    main()
