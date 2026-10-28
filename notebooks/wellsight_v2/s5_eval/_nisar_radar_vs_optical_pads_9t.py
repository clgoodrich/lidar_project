"""Radar alone against Sentinel-2 alone, no lidar features (outside-review follow-up 2, 2026-10-27, 9t).

If lidar is absent, is NISAR any better than free optical imagery at telling a pad from the ground around it? Feature sets,
none of which uses lidar bands (the decoys are still chosen with lidar cover and slope, so the design, not the model, uses lidar):
  NISAR all bands, NISAR basic (six date-mean HH/HV backscatter layers), Sentinel-2 (22 layers), NISAR + Sentinel-2,
  NISAR basic + Sentinel-2, and rich lidar as the reference. Map x/y is the location control.
Designs: tile-wide matched decoys (suffix "") and decoys only from other clearings (_confuser; 60 pads, so wide intervals).
Repeated shuffled grouped CV (REPEATS repeats); AUC mean and range, and a block-bootstrap interval of (A - B) for the pairs
that matter: NISAR against Sentinel-2, and NISAR + Sentinel-2 against Sentinel-2 alone.
Also the AUC of each Sentinel-2 layer and each basic radar layer on its own.

  [CONFUSER=1] [REPEATS=10] NISAR_STACK=slc python _nisar_radar_vs_optical_pads_9t.py
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

SUFFIX = C.suffix("pad")
REPEATS, SEED = int(os.environ.get("REPEATS", 10)), 20261027


def main():
    S = C.load_samples("pad", SUFFIX)
    names, X, y, grp, xy, prod = S["names"], S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    Xo, on = OF.on_rows(S, OF.optical_layers())
    Xb, bn = OF.on_rows(S, OF.radar_basic_layers())
    print(f"{int(y.sum())} targets, {int((1 - y).sum())} decoys; optical {Xo.shape[1]} layers, radar basic {Xb.shape[1]}; "
          f"optical finite {np.isfinite(Xo).mean():.2f}", flush=True)
    sets = {"NISAR all bands": X[:, sar], "NISAR basic (6 layers)": Xb, "Sentinel-2 (22 layers)": Xo,
            "NISAR + Sentinel-2": np.hstack([X[:, sar], Xo]), "NISAR basic + Sentinel-2": np.hstack([Xb, Xo]),
            "rich lidar (reference)": X[:, ctl | lt], "map x/y only": xy}
    runs = Parallel(n_jobs=4)(delayed(R.one_repeat)(sets, y, grp, xy, r) for r in range(REPEATS))
    pm = {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}
    rows = []
    for k in sets:
        a = np.array([roc_auc_score(y, rr[k]) for rr in runs])
        rows.append(dict(item=k, auc_mean=a.mean(), auc_min=a.min(), auc_max=a.max(), note=""))
    rng = np.random.default_rng(SEED)
    for a_k, b_k in (("NISAR all bands", "Sentinel-2 (22 layers)"), ("NISAR basic (6 layers)", "Sentinel-2 (22 layers)"),
                     ("NISAR + Sentinel-2", "Sentinel-2 (22 layers)"), ("NISAR basic + Sentinel-2", "Sentinel-2 (22 layers)"),
                     ("NISAR + Sentinel-2", "NISAR all bands")):
        d = np.array([roc_auc_score(y, rr[a_k]) - roc_auc_score(y, rr[b_k]) for rr in runs])
        lo, hi = R.block_boot_auc_diff(y, grp, pm[a_k], pm[b_k], rng)
        rows.append(dict(item=f"difference: {a_k} minus {b_k}", auc_mean=d.mean(), auc_min=d.min(), auc_max=d.max(),
                         note=f"block-bootstrap 95% {lo:+.3f} to {hi:+.3f}"))
    for j, n in enumerate(on):
        v = Xo[:, j]
        ok = np.isfinite(v)
        rows.append(dict(item=f"single layer, Sentinel-2: {n}", auc_mean=roc_auc_score(y[ok], v[ok]), note=f"{int(ok.sum())} rows"))
    for j, n in enumerate(bn):
        v = Xb[:, j]
        ok = np.isfinite(v)
        rows.append(dict(item=f"single layer, radar: {n}", auc_mean=roc_auc_score(y[ok], v[ok]), note=f"{int(ok.sum())} rows"))
    res = pd.DataFrame(rows).round(3)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_rows", 200)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_pad_radar_vs_optical_auc_{C.A.TAG}{SUFFIX}.csv", index=False)


if __name__ == "__main__":
    main()
