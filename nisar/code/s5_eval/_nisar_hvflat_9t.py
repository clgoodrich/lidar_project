"""Does terrain-flattened HV change the pad and pit scores? (outside-review follow-up 4, 2026-10-27, 9t)

The NISAR set already holds terrain-flattened HH (geometry:flat_db, HH minus the simulated facet gain) and the gain itself
(geometry:sim_db) for each track, and INC_MATCH decoys are matched on that gain. HV was not flattened. Here three layers are
added, HV date-mean minus sim_db for each track (raw_mean_hv from the radiometric-normalisation product), and the scores
are repeated with and without them.

  [TARGET=pit] [SHAPE=1 INC_MATCH=1] [REPEATS=5] NISAR_STACK=slc python _nisar_hvflat_9t.py
"""
import os

os.environ.setdefault("OMP_NUM_THREADS", "4")

import numpy as np
import pandas as pd
import rasterio
from joblib import Parallel, delayed
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C
import _nisar_feat_repeat_9t as R
import _nisar_optical_feats_9t as OF

TARGET = os.environ.get("TARGET", "pad")
SUFFIX = C.suffix(TARGET)
REPEATS, SEED = int(os.environ.get("REPEATS", 5)), 20261027


def main():
    S = C.load_samples(TARGET, SUFFIX)
    X, y, grp, xy, prod = S["X"], S["y"], S["grp"], S["xy"], S["prod"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    with rasterio.open(C.FEAT_DIR / f"nisar_check_radnorm_{C.A.TAG}_5m.tif") as r:
        names, arr = list(r.descriptions), r.read()
    with rasterio.open(C.FEAT_DIR / f"nisar_feat_geometry_{C.A.TAG}_5m.tif") as r:
        gn = list(r.descriptions)
        sim = {t: r.read(gn.index(f"sim_db_t{t:03d}") + 1) for t in (26, 90, 162)}
    flat = {f"hv_flat_t{t:03d}": arr[names.index(f"raw_mean_hv_t{t:03d}")] - sim[t] for t in (26, 90, 162)}
    Xf, _ = OF.on_rows(S, flat)
    sets = {"rich lidar": X[:, ctl | lt], "all NISAR": X[:, sar], "all NISAR + HV flat": np.hstack([X[:, sar], Xf]),
            "HV flat alone": Xf, "NISAR + rich lidar": X[:, sar | ctl | lt], "NISAR + HV flat + rich lidar": np.hstack([X[:, sar | ctl | lt], Xf])}
    runs = Parallel(n_jobs=4)(delayed(R.one_repeat)(sets, y, grp, xy, r) for r in range(REPEATS))
    pm = {k: np.nanmean([rr[k] for rr in runs], 0) for k in sets}
    rows = []
    for k in sets:
        a = np.array([roc_auc_score(y, rr[k]) for rr in runs])
        rows.append(dict(feature_set=k, auc_mean=a.mean(), auc_min=a.min(), auc_max=a.max(), note=""))
    rng = np.random.default_rng(SEED)
    for a_k, b_k in (("all NISAR + HV flat", "all NISAR"), ("NISAR + HV flat + rich lidar", "rich lidar"), ("NISAR + HV flat + rich lidar", "NISAR + rich lidar")):
        d = np.array([roc_auc_score(y, rr[a_k]) - roc_auc_score(y, rr[b_k]) for rr in runs])
        lo, hi = R.block_boot_auc_diff(y, grp, pm[a_k], pm[b_k], rng)
        rows.append(dict(feature_set=f"difference: {a_k} minus {b_k}", auc_mean=d.mean(), auc_min=d.min(), auc_max=d.max(), note=f"block-bootstrap 95% {lo:+.3f} to {hi:+.3f}"))
    res = pd.DataFrame(rows).round(3)
    pd.set_option("display.width", 250)
    print(f"{TARGET}{SUFFIX}: {int(y.sum())} targets, {int((1 - y).sum())} decoys")
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_{TARGET}_hvflat_auc_{C.A.TAG}{SUFFIX}.csv", index=False)


if __name__ == "__main__":
    main()
