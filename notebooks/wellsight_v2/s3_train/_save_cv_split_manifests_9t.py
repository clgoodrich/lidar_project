"""Save the explicit 5-fold block splits used by the pit and pad CV trainers, and check spatial separation.

The trainers rebuild folds at run time from a seed. This script calls their own assign_folds with their own seed and manifest,
but it drops NaN block ids before shuffling and the trainers do not. Held-out lists are valid. Train and val roles do NOT match the trained models,
and the trainers' inner split is not reproducible across processes (NaN position in a sorted set). See expansions/0_prerequisites/p1_splits_manifests/docs/plan_prereq_splits_manifests.md. It trains nothing.

Outputs (data/9t/results/splits/):
  cv_split_blocks_pit_9t.csv, cv_split_blocks_pad_9t.csv   one row per block per fold role (held_out, val, train)
  cv_split_check_9t.json                                    adjacency and nearest-feature distances across held-out and train
Run: python notebooks/wellsight_v2/s3_train/_save_cv_split_manifests_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
import _pit_unet_cv5 as pit  # noqa: E402
import _pad_unet_cv5 as pad  # noqa: E402
from _common import normalize_ids  # noqa: E402

OUT = ROOT / "data/9t/results/splits"
OUT.mkdir(parents=True, exist_ok=True)
K = 5


def one(mod, count_col):
    man = normalize_ids(pd.read_csv(mod.MANIFEST))
    n_all = len(man)
    man = man[man.block_id.notna()].copy()  # features with no block are never scored by the trainers
    man["block_id"] = man.block_id.astype(int)
    n_per = man.groupby("block_id").size().rename(count_col).reset_index()
    fold_of = mod.assign_folds(n_per[["block_id", count_col]], K, mod.CV_SEED)
    man["fold"] = man.block_id.map(fold_of)
    rows, chk = [], {}
    blocks = gpd.read_file(pit.BLOCKS, layer="blocks").set_index("block_id")
    for k in range(K):
        held = sorted(man.loc[man.fold == k, "block_id"].unique())
        rest = sorted(set(man.block_id.unique()) - set(held))
        rng = np.random.default_rng(mod.CV_SEED + 1000 * k)
        shuf = list(rng.permutation(rest))
        nv = max(1, int(round(mod.INNER_VAL_FRAC * len(shuf))))
        val, tr = sorted(shuf[:nv]), sorted(shuf[nv:])
        for role, ids in (("held_out", held), ("val", val), ("train", tr)):
            rows += [dict(fold=k, role=role, block_id=int(b)) for b in ids]
        # spatial separation. Blocks are 375 m squares in a grid, so touching blocks share an edge.
        hb = blocks.loc[[int(b) for b in held]].geometry.union_all()
        tb = blocks.loc[[int(b) for b in tr + val]]
        touching = int(tb.geometry.touches(hb).sum() + tb.geometry.intersects(hb).sum() * 0)
        h = man[man.fold == k][["centroid_x", "centroid_y"]].to_numpy()
        t = man[(man.fold != k)][["centroid_x", "centroid_y"]].to_numpy()
        d, _ = cKDTree(t).query(h)
        chk[k] = dict(n_held_blocks=len(held), n_val_blocks=len(val), n_train_blocks=len(tr),
                      train_or_val_blocks_touching_held_out=touching,
                      min_dist_held_to_other_feature_m=round(float(d.min()), 1),
                      share_held_features_within_40m_of_other_fold=round(float((d <= 40).mean()), 4))
    chk["manifest_rows"] = n_all
    chk["rows_without_block_excluded_from_cv"] = n_all - len(man)
    return pd.DataFrame(rows), chk


def main():
    res = {}
    for name, mod, col in (("pit", pit, "n_pits"), ("pad", pad, "n_pads")):
        df, chk = one(mod, col)
        df.to_csv(OUT / f"cv_split_blocks_{name}_9t.csv", index=False)
        res[name] = dict(seed=mod.CV_SEED, folds=chk)
    res["note"] = ("Held-out and training blocks are adjacent in a grid, so the separation is 0 m between blocks. "
                   "Features inside the scored footprint buffer can sit within 40 m of another fold's feature. "
                   "Judge whether this is acceptable for the claim being made, and use a buffered split for a final test.")
    (OUT / "cv_split_check_9t.json").write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
