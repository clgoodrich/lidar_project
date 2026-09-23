"""Record every pit/pad CV5 detection at a fine threshold grid, per block and per object.

WHY
---
Phase 1 and 2 of the operating-point plan
(`docs/iterations/operating_point_policy_plan.md`) need two things the CV5 runs
never saved:

  * held-out counts PER BLOCK at each threshold, so the precision-recall curve
    can be bootstrapped by resampling blocks (the unit the folds were split on)
  * one row PER PREDICTED OBJECT with its score and whether it matched, on both
    the inner-val and held-out splits, so scores can be calibrated on inner val
    and checked on held-out

NOTE (2026-09-23): the inner-val rows are recorded but no longer used. The
inner-val split cannot be reproduced (NaN block ids make `sorted(set(...))`
process-dependent), so all fitting downstream is leave-one-fold-out on the
held-out rows. See `_cv5_pr_calibration_pit_pad_9t.py`.

This script only records. `_cv5_pr_calibration_pit_pad_9t.py` does the analysis.
No training and no GPU. It reads the five fold probability rasters that
`_pit_unet_cv5.py` / `_pad_unet_cv5.py` already wrote, rebuilds each fold's
inner-val and held-out blocks with the same seeds, and re-polygonizes.

WHAT IS FIXED, AND WHY
----------------------
Everything that defines an object is inherited from the CV5 scripts unchanged:
`polygonize` (connected blobs, mean-probability score), the MIN_AREA_M2 floor
(pit 4 m2, pad 100 m2), greedy 1:1 IoU matching by score, and the
centroid-in-footprint rule for which predictions count. Only the threshold grid
is finer: 0.05 to 0.95 in steps of 0.025, against 0.10 to 0.85 in 0.05. A finer
grid is not a new choice. It just traces the same curve at more points.

MODELS
------
  pit       data/9t/models/pit/unet_cv5         vendor ground, ann712
  pit_smrf  data/9t/models/pit/unet_cv5_smrf    SMRF ground, same folds, same labels
  pad       data/9t/models/pad/unet_cv5         vendor ground, ann712

Run:
  python notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py
  python notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py --models pit
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize as _rasterize

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s3_train"))
from _common import normalize_ids, path_for, read_layer  # noqa: E402
import _pad_unet_cv5 as padcv  # noqa: E402
import _pit_unet_cv5 as pitcv  # noqa: E402

OUT = path_for("results_9t") / "operating_point"
GRID = np.round(np.arange(0.05, 0.951, 0.025), 3)
TAUS = (0.3, 0.5)
K = 5

MODELS = {
    "pit": dict(cv=pitcv, dir=path_for("models") / "pit" / "unet_cv5",
                prob="pit_prob_floor_cvfold{k}_9t_05.tif", gt_layer="pit_inside",
                id_col="pit_inside_id"),
    "pit_smrf": dict(cv=pitcv, dir=path_for("models") / "pit" / "unet_cv5_smrf",
                     prob="pit_prob_floor_cvfold{k}_9t_05.tif", gt_layer="pit_inside",
                     id_col="pit_inside_id"),
    "pad": dict(cv=padcv, dir=path_for("models") / "pad" / "unet_cv5",
                prob="pad_prob_cvfold{k}_9t_05.tif", gt_layer="pad",
                id_col="pad_id"),
}


def match_objects(gt: gpd.GeoDataFrame, pred: gpd.GeoDataFrame, tau: float):
    """Greedy 1:1 IoU matching by score, identical to `match_scores` in the CV5
    scripts, but returning WHICH rows matched instead of only the counts.

    Returns (gt_hit, pred_hit), two boolean arrays.
    """
    gt_hit = np.zeros(len(gt), bool)
    pred_hit = np.zeros(len(pred), bool)
    if not len(gt) or not len(pred):
        return gt_hit, pred_hit
    sidx = pred.sindex
    sc = pred["score"].to_numpy()
    pairs = []
    for gi, g in enumerate(gt.geometry):
        for pj in sidx.intersection(g.bounds):
            p = pred.geometry.iloc[pj]
            inter = g.intersection(p).area
            if inter <= 0:
                continue
            u = g.area + p.area - inter
            if u > 0 and inter / u >= tau:
                pairs.append((gi, int(pj), float(sc[pj])))
    for gi, pj, _ in sorted(pairs, key=lambda p: -p[2]):
        if gt_hit[gi] or pred_hit[pj]:
            continue
        gt_hit[gi] = pred_hit[pj] = True
    return gt_hit, pred_hit


def run_model(name: str, spec: dict) -> None:
    cv = spec["cv"]
    mdir = spec["dir"]
    man = normalize_ids(pd.read_csv(cv.MANIFEST))
    blocks = gpd.read_file(cv.BLOCKS, layer="blocks").to_crs(cv.CRS)

    # Use the fold assignment the CV run itself wrote. Recomputing it would
    # agree today, but the saved file is the record of what was actually held
    # out, so it is the one to trust.
    assign = normalize_ids(pd.read_csv(mdir / f"{name.split('_')[0]}_cv5_fold_assignment_9t.csv"))
    id_col = spec["id_col"]
    fold_of_block = assign.drop_duplicates("block_id").set_index("block_id")["fold"].to_dict()
    man["fold"] = man.block_id.map(fold_of_block)

    gt = read_layer(cv.ANN_GPKG, spec["gt_layer"]).to_crs(cv.CRS)
    gt = gt[[id_col, "geometry"]].dissolve(by=id_col).reset_index()
    gt = gt.merge(man[[id_col, "block_id", "fold"]], on=id_col, how="inner")

    block_rows, obj_rows = [], []
    t0 = time.time()
    for k in range(K):
        prob_tif = mdir / f"fold{k}" / spec["prob"].format(k=k)
        with rasterio.open(prob_tif) as r:
            prob = r.read(1).astype(np.float32)
            tf, rcrs = r.transform, r.crs

        # Same inner-val draw as the CV script: per-fold seed, same permutation.
        held_blocks = sorted(man.loc[man.fold == k, "block_id"].unique())
        rest = sorted(set(man.block_id.unique()) - set(held_blocks))
        rng = np.random.default_rng(cv.CV_SEED + 1000 * k)
        rest_shuf = list(rng.permutation(rest))
        n_val = max(1, int(round(cv.INNER_VAL_FRAC * len(rest_shuf))))
        val_blocks = sorted(rest_shuf[:n_val])

        splits = {"val": val_blocks, "heldout": held_blocks}
        bgeo = {s: blocks[blocks.block_id.isin(b)][["block_id", "geometry"]]
                .reset_index(drop=True) for s, b in splits.items()}
        foot = {s: g.geometry.union_all() for s, g in bgeo.items()}
        keep = _rasterize([(foot[s].buffer(cv.SCORE_BUF_M), 1) for s in splits],
                          out_shape=prob.shape, transform=tf, fill=0,
                          dtype="uint8").astype(bool)
        prob = np.where(keep, prob, 0.0).astype(np.float32)
        gts = {s: gt[gt.block_id.isin(b)].reset_index(drop=True)
               for s, b in splits.items()}

        for thr in GRID:
            allp = cv.polygonize(prob, tf, rcrs, float(thr))
            for s in splits:
                if len(allp):
                    # Which block holds each prediction's centroid. The union of
                    # blocks is the footprint, so "in a block" == "in footprint".
                    cen = gpd.GeoDataFrame(geometry=allp.geometry.centroid, crs=allp.crs)
                    j = gpd.sjoin(cen, bgeo[s], how="inner", predicate="within")
                    j = j[~j.index.duplicated()]
                    pred = allp.loc[j.index].reset_index(drop=True)
                    pred_block = j["block_id"].to_numpy()
                else:
                    pred = allp
                    pred_block = np.array([], dtype=int)
                g = gts[s]
                gb = g["block_id"].to_numpy()
                for tau in TAUS:
                    gh, ph = match_objects(g, pred, tau)
                    if s == "heldout":
                        for b in bgeo[s].block_id:
                            block_rows.append(dict(
                                model=name, fold=k, block_id=int(b), thr=float(thr),
                                tau=tau, n_gt=int((gb == b).sum()),
                                tp_gt=int(gh[gb == b].sum()),
                                n_pred=int((pred_block == b).sum()),
                                tp_pred=int(ph[pred_block == b].sum())))
                    for i in range(len(pred)):
                        obj_rows.append(dict(
                            model=name, fold=k, split=s, thr=float(thr), tau=tau,
                            block_id=int(pred_block[i]),
                            score=float(pred["score"].iloc[i]),
                            area_m2=float(pred.geometry.iloc[i].area),
                            is_tp=bool(ph[i])))
                    if s == "val":
                        # Inner-val recall is needed per threshold to choose the
                        # proposal threshold in Phase 2 without touching held-out.
                        block_rows.append(dict(
                            model=name, fold=k, block_id=-1, thr=float(thr), tau=tau,
                            n_gt=len(g), tp_gt=int(gh.sum()), n_pred=len(pred),
                            tp_pred=int(ph.sum()), split="val"))
        print(f"  {name} fold {k} done ({(time.time()-t0)/60:.1f} min)", flush=True)
        del prob

    bdf = pd.DataFrame(block_rows)
    bdf["split"] = bdf.get("split").fillna("heldout")
    bdf.to_csv(OUT / f"cv5_sweep_counts_per_block_{name}_thr0p05to0p95_9t.csv", index=False)
    pd.DataFrame(obj_rows).to_csv(
        OUT / f"cv5_sweep_objects_{name}_thr0p05to0p95_9t.csv.gz", index=False)
    print(f"  wrote {OUT / f'cv5_sweep_counts_per_block_{name}_thr0p05to0p95_9t.csv'}")
    print(f"  wrote {OUT / f'cv5_sweep_objects_{name}_thr0p05to0p95_9t.csv.gz'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default=",".join(MODELS))
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.models.split(","):
        print(f"== {name} ==")
        run_model(name, MODELS[name])
    return 0


if __name__ == "__main__":
    sys.exit(main())
