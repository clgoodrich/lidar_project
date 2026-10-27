"""Does the NISAR (or lidar) pad score depend on the DEP status of the well on the pad? (backlog item, review 2026-10-26)

Each scored pad is given the DEP status of the wells within STATUS_M (50 m) of its polygon, taken from the Venango DEP
export (WELL_STATU). A pad with several wells takes the first status in this order: orphan, abandoned, active, plugged,
other. A pad with no well within STATUS_M is "no well recorded". DEP positions are unreliable, so this is a coarse
split, and a missing well is not evidence of no well.

For each feature set the pooled out-of-fold probabilities come from the same CV as the model script (C.oof_probs).
The AUC is then computed within each status group: the pads of that group against the decoys drawn for those pads.
A block bootstrap (BOOT resamples of 500 m blocks inside the group) gives a 95% interval.

  [LOCAL_M=1500] [SHAPE=1] ... python _nisar_feat_status_9t.py
"""
import os

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C

TARGET = "pad"
SUFFIX = C.suffix(TARGET)
STATUS_M, BOOT, SEED = 50.0, 300, 20261027
ORDER = [("orphan", ["DEP Orphan List"]),
         ("abandoned", ["DEP Abandoned List", "Abandoned"]),
         ("active", ["Active"]),
         ("plugged", ["Plugged OG Well", "DEP Plugged", "Plugged Unverified"]),
         ("other", ["Operator Reported Not Drilled", "Proposed But Never Materialized", "Cannot Be Located"])]


def status_of_pads(pad_xy):
    pads = C.ifg.read_layer(C.ifg.ANN, "plat").to_crs(C.CRS)
    cen = np.array([[g.centroid.x, g.centroid.y] for g in pads.geometry])
    _, ix = cKDTree(cen).query(pad_xy)
    geoms = pads.geometry.values[ix]
    wells = gpd.read_file(C.A.WELLS).to_crs(C.CRS)
    sidx = wells.sindex
    out = []
    for g in geoms:
        near = wells.iloc[sidx.query(g.buffer(STATUS_M), predicate="intersects")]
        near = near[near.geometry.distance(g) <= STATUS_M]
        st = "no well recorded"
        for name, labels in ORDER:
            if near.WELL_STATU.isin(labels).any():
                st = name
                break
        out.append(st)
    return np.array(out)


def main():
    S = C.load_samples(TARGET, SUFFIX)
    X, y, grp, xy, prod, z = S["X"], S["y"], S["grp"], S["xy"], S["prod"], S["z"]
    ctl, lt, ctx, sar = C.feature_groups(prod)
    pads, sel = S["pads"], S["sel"]
    st_pad = status_of_pads(z["pad_xy"][pads])
    row_status = np.r_[st_pad, st_pad[np.searchsorted(pads, z["dec_pad"][sel])]]
    print(pd.Series(st_pad).value_counts().to_string(), flush=True)
    sets = {"all NISAR": X[:, sar], "rich lidar baseline": X[:, ctl | lt], "NISAR + rich baseline": X[:, sar | ctl | lt],
            "map x/y only": xy}
    P = {k: C.oof_probs(M, y, grp)[0] for k, M in sets.items()}
    rng = np.random.default_rng(SEED)
    rows = []
    for g in ["all"] + sorted(set(st_pad)):
        m = np.ones(len(y), bool) if g == "all" else row_status == g
        npad = int(y[m].sum())
        for k, p in P.items():
            if npad < 10:
                continue
            a = roc_auc_score(y[m], p[m])
            ug = np.unique(grp[m])
            where = {b: np.flatnonzero(m & (grp == b)) for b in ug}
            bs = []
            for _ in range(BOOT):
                idx = np.concatenate([where[b] for b in rng.choice(ug, len(ug))])
                if len(set(y[idx])) == 2:
                    bs.append(roc_auc_score(y[idx], p[idx]))
            rows.append(dict(status=g, n_pads=npad, n_decoys=int((1 - y[m]).sum()), feature_set=k, auc=round(a, 3),
                             ci_lo=round(np.percentile(bs, 2.5), 3), ci_hi=round(np.percentile(bs, 97.5), 3)))
    res = pd.DataFrame(rows)
    print(res.to_string(index=False))
    res.to_csv(C.OUT / f"nisar_pad_status_auc_{C.A.TAG}{SUFFIX}.csv", index=False)


if __name__ == "__main__":
    main()
