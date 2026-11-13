"""Is the gap between the tile-wide pad design (NISAR AUC about 0.64) and the local-decoy design (about 0.48) a subset effect?

The local design (decoys 100 to 1,500 m from the pad) keeps only the pads that have at least 10 matched decoys in that
ring (297 of 645). This script takes the out-of-fold probabilities of the tile-wide design and reports the AUC for the
pads that are in the local design and for the pads that are not, each against their own tile-wide decoys.
If NISAR scores near 0.64 in both, the gap is not a subset effect.

  NISAR_STACK=slc python _nisar_feat_subset_9t.py
"""
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from sklearn.metrics import roc_auc_score

import _nisar_feat_common as C


def main():
    A = C.load_samples("pad", "")
    B = C.load_samples("pad", "_local1500", tag=C.A.TAG)
    pa, pb = A["z"]["pad_xy"][A["pads"]], B["z"]["pad_xy"][B["pads"]]
    d, _ = cKDTree(pb).query(pa)
    in_local_pad = d < 1.0
    sel = A["sel"]
    row_in = np.r_[in_local_pad, in_local_pad[np.searchsorted(A["pads"], A["z"]["dec_pad"][sel])]]
    ctl, lt, ctx, sar = C.feature_groups(A["prod"])
    sets = {"all NISAR": A["X"][:, sar], "rich lidar baseline": A["X"][:, ctl | lt], "map x/y only": A["xy"]}
    rows = []
    for k, M in sets.items():
        p, _ = C.oof_probs(M, A["y"], A["grp"])
        for label, m in (("pads in the local design", row_in), ("pads not in the local design", ~row_in), ("all", np.ones(len(row_in), bool))):
            rows.append(dict(feature_set=k, subset=label, n_pads=int(A["y"][m].sum()), auc=round(roc_auc_score(A["y"][m], p[m]), 3)))
            print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(C.OUT / f"nisar_pad_subset_effect_auc_{C.A.TAG}.csv", index=False)


if __name__ == "__main__":
    main()
