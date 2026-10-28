"""Why does NISAR score 0.64 against tile-wide decoys and 0.48 against local ones? (outside-review follow-up 3, 2026-10-27, 9t)

Hypothesis: the radar separates a pad from ground far away because the far ground is a different place (stand type, aspect,
illumination), not because the pad looks different. If so, the AUC should rise with the distance of the decoys, and
Sentinel-2 (stand type) and map x/y should rise with it, and the radar should add nothing to them.

Decoys come from two matched-decoy files with the same protocol: tile-wide (10 per pad, mostly 1.3 to 4.4 km away) and local
(100 to 1,500 m). Their distance to their own pad is binned. In each bin the targets that have at least one decoy there are
scored against the decoys in the bin. Models (repeated shuffled grouped CV, REPEATS repeats): NISAR all bands, Sentinel-2,
map x/y, rich lidar, NISAR + Sentinel-2. Reported per bin: AUC of each, gain of NISAR + Sentinel-2 over Sentinel-2, and a
block-bootstrap interval of the NISAR AUC.

  [REPEATS=3] NISAR_STACK=slc python _nisar_pad_distance_bands_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import pandas as pd
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
import _nisar_feat_repeat_9t as R
import _nisar_optical_feats_9t as OF

REPEATS, SEED = int(os.environ.get("REPEATS", 3)), 20261027
BANDS = [(100, 500), (500, 1000), (1000, 1500), (1500, 2500), (2500, 3500), (3500, 6000)]


def main():
    L = OF.optical_layers()
    parts = []
    for suf in ("", "_local1500"):
        S = C.load_samples("pad", suf)
        Xo, _ = OF.on_rows(S, L)
        z, pads, sel = S["z"], S["pads"], S["sel"]
        n_t = len(pads)
        pid = np.r_[pads, z["dec_pad"][sel]]
        dist = np.r_[np.full(n_t, np.nan), np.hypot(*(S["xy"][n_t:] - z["pad_xy"][z["dec_pad"][sel]]).T)]
        parts.append(dict(S=S, Xo=Xo, pid=pid, dist=dist, n_t=n_t))
        print(f"'{suf}': {n_t} targets, {len(sel)} decoys", flush=True)
    P0 = parts[0]
    n_t = P0["n_t"]
    S0 = P0["S"]
    prod = S0["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    # pooled rows: targets of the tile-wide file, then decoys of both files
    tr = slice(0, n_t)
    X = np.vstack([S0["X"][tr]] + [p["S"]["X"][p["n_t"]:] for p in parts])
    Xo = np.vstack([P0["Xo"][tr]] + [p["Xo"][p["n_t"]:] for p in parts])
    xy = np.vstack([S0["xy"][tr]] + [p["S"]["xy"][p["n_t"]:] for p in parts])
    grp = np.concatenate([S0["grp"][tr]] + [p["S"]["grp"][p["n_t"]:] for p in parts])
    y = np.r_[np.ones(n_t), np.zeros(len(X) - n_t)].astype(int)
    pid = np.concatenate([P0["pid"][tr]] + [p["pid"][p["n_t"]:] for p in parts])
    dist = np.concatenate([np.full(n_t, np.nan)] + [p["dist"][p["n_t"]:] for p in parts])
    rows = []
    for lo, hi in BANDS:
        dm = (y == 0) & (dist >= lo) & (dist < hi)
        pads_in = np.unique(pid[dm])
        m = dm | ((y == 1) & np.isin(pid, pads_in))
        sets = {"NISAR all bands": X[m][:, sar], "Sentinel-2": Xo[m], "map x/y": xy[m], "rich lidar": X[m][:, ctl | lt],
                "NISAR + Sentinel-2": np.hstack([X[m][:, sar], Xo[m]])}
        yy, gg, xx = y[m], grp[m], xy[m]
        runs = Parallel(n_jobs=4)(delayed(R.one_repeat)(sets, yy, gg, xx, r) for r in range(REPEATS))
        pm = {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}
        row = dict(distance_m=f"{lo}-{hi}", n_targets=len(pads_in), n_decoys=int(dm.sum()))
        for k in sets:
            row[f"auc_{k}"] = roc_auc_score(yy, pm[k])
        row["gain_NISAR_over_Sentinel2"] = row["auc_NISAR + Sentinel-2"] - row["auc_Sentinel-2"]
        rng = np.random.default_rng(SEED)
        ug = np.unique(gg)
        where = {g: np.flatnonzero(gg == g) for g in ug}
        b, bg = [], []
        for _ in range(300):
            ix = np.concatenate([where[g] for g in rng.choice(ug, len(ug))])
            if len(set(yy[ix])) == 2:
                b.append(roc_auc_score(yy[ix], pm["NISAR all bands"][ix]))
                bg.append(roc_auc_score(yy[ix], pm["NISAR + Sentinel-2"][ix]) - roc_auc_score(yy[ix], pm["Sentinel-2"][ix]))
        row["nisar_auc_ci"] = f"{np.percentile(b, 2.5):.3f} to {np.percentile(b, 97.5):.3f}"
        row["gain_ci"] = f"{np.percentile(bg, 2.5):+.3f} to {np.percentile(bg, 97.5):+.3f}"
        rows.append(row)
        print(row, flush=True)
    res = pd.DataFrame(rows).round(3)
    pd.set_option("display.width", 300)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_pad_distance_bands_auc_{C.A.TAG}.csv", index=False)


if __name__ == "__main__":
    main()
