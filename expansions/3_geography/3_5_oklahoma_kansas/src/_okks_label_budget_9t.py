"""S2 (3.5). Label-budget curve on 9t. Recall at K for the lidar recipe trained on 25, 50, 100 % of blocks.

Purpose
    Sets the minimum labelled training features for Q1 before any OK/KS label is drawn. Uses only the
    valid historical held-out lists (protocol section 3). For each fold the training pool is every
    other block with a block id. An inner validation set is drawn once with a child seed and saved
    (a split file, not a seed, is the source of truth). Subsets are nested (25 within 50 within 100).
    --plan (default) writes the split file and feature counts only (CPU, seconds).
    --execute trains each fraction with the isolated sampler (GPU), predicts the held-out fold,
    and scores recall at K = 40 per km2 with the shared scorer.
Inputs (held)
    data/9t/results/splits/cv_split_blocks_pit_9t.csv      (held_out rows only)
    data/9t/derived/05/blocks_unified_9t.gpkg, features_pit_9t_05.tif, labels_pit_9t_05.tif
    qgis/annotations/annotations_proj.gpkg layer pit_inside (feature counts per block)
Outputs
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_label_budget_splits_9t.json
    expansions/3_geography/3_5_oklahoma_kansas/results/tables/okks_label_budget_curve_9t.csv  (--execute)
    expansions/3_geography/3_5_oklahoma_kansas/models/label_budget_9t/f<frac>_fold<k>/best.pt  (--execute)
Run
    python expansions/3_geography/3_5_oklahoma_kansas/src/_okks_label_budget_9t.py --plan
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "3_4_gulf_texas" / "src"))
import _geo_transfer_core as gt  # noqa: E402

ek = gt.ek
EXP = "3.5"
LIDAR_CHANNELS = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]


def nested_subsets(pool: list, fracs: list[float], seed: int) -> dict:
    rng = np.random.default_rng(seed)
    order = [int(x) for x in rng.permutation(sorted(pool))]
    return {f"{f:.2f}": sorted(order[:max(1, int(round(f * len(order))))]) for f in sorted(fracs)}


def make_plan(split: pd.DataFrame, fracs: list[float], master: int, val_frac: float = 0.15) -> dict:
    held = split[split["role"] == "held_out"].dropna(subset=["block_id"])
    allb = sorted(int(x) for x in held["block_id"].astype(int).unique())
    plan = {}
    for fold, g in held.groupby("fold"):
        test = sorted(int(x) for x in g["block_id"].astype(int).unique())
        pool = [b for b in allb if b not in test]
        rng = np.random.default_rng(ek.child_seed(master, int(fold), 0))
        val = sorted(int(x) for x in rng.choice(pool, max(1, int(round(val_frac * len(pool)))), replace=False))
        train_pool = [b for b in pool if b not in val]
        subs = nested_subsets(train_pool, fracs, ek.child_seed(master, int(fold), 1))
        ek.assert_disjoint(test, val, f"fold {fold} test/val")
        for s in subs.values():
            ek.assert_disjoint(s, test + val, f"fold {fold} train/test+val")
        plan[str(int(fold))] = {"test": test, "val": val, "train": subs}
    return plan


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--plan", action="store_true")
    ap.add_argument("--execute", action="store_true", help="GPU training of every fraction and fold")
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--n-train", type=int, default=2000)
    a = ap.parse_args(argv)
    cfg = gt.load_config(EXP)
    pr = cfg["prereg"]
    import geopandas as gpd
    try:
        split = pd.read_csv(gt.require_input(ek.path_for("results_9t") / "splits" / "cv_split_blocks_pit_9t.csv",
                                             "9t pit CV split"))
        blocks = gpd.read_file(gt.require_input(ek.path_for("nine_t") / "blocks_unified_9t.gpkg", "9t blocks"))
        pits = gpd.read_file(ek.path_for("truth") / "annotations_proj.gpkg", layer="pit_inside")
    except gt.MissingInputError as e:
        print(str(e), file=sys.stderr)
        return 2
    plan = make_plan(split, pr["label_budget_fracs"], int(pr["master_seed"]))
    cent = gpd.GeoDataFrame(geometry=pits.geometry.centroid, crs=pits.crs)
    per_block = gpd.sjoin(cent, blocks[["block_id", "geometry"]], predicate="within")["block_id"].value_counts()
    summary = {f: {fr: int(per_block.reindex(b).fillna(0).sum()) for fr, b in v["train"].items()}
               for f, v in plan.items()}
    tables = ek.sub(EXP, "results/tables")
    sp = tables / "okks_label_budget_splits_9t.json"
    sp.write_text(json.dumps({"plan": plan, "train_pit_features": summary,
                              "note": "held-out lists are the valid historical ones. val drawn here and saved"},
                             indent=2), encoding="utf-8")
    print(pd.DataFrame(summary).T.to_string())
    print(f"wrote {sp}")
    if not a.execute:
        return 0
    feats = ek.path_for("nine_t") / "features_pit_9t_05.tif"
    labs = ek.path_for("nine_t") / "labels_pit_9t_05.tif"
    rows = []
    for fold, v in plan.items():
        forb = blocks[blocks["block_id"].isin(v["test"] + v["val"])].geometry.union_all()
        for fr, tb in v["train"].items():
            seed = ek.child_seed(int(pr["master_seed"]), int(fold), int(float(fr) * 100))
            w_tr = gt.sample_windows(blocks[blocks["block_id"].isin(tb)], forb, 128.0, a.n_train, seed)
            w_va = gt.sample_windows(blocks[blocks["block_id"].isin(v["val"])],
                                     blocks[~blocks["block_id"].isin(v["val"])].geometry.union_all(), 128.0, 300, seed + 1)
            mu, sd = gt.fit_norm_stats(feats, w_tr)
            od = ek.sub(EXP, f"models/label_budget_9t/f{fr}_fold{fold}")
            gt.train_unet([(feats, labs, w_tr)], [(feats, labs, w_va)], mu, sd, od, n_classes=3, patch_px=256,
                          epochs=a.epochs, lr=3e-4, alpha=[0.25, 0.5, 0.25], seed=seed,
                          channels=LIDAR_CHANNELS)
            prob = gt.frozen_infer(feats, od / "best.pt", "pit", od, f"lb_f{fr}_fold{fold}")
            hb = blocks[blocks["block_id"].isin(v["test"])].assign(eligible=True, area_km2=lambda d: d.area / 1e6)
            hb["block_id"] = hb["block_id"].astype(str)
            tr = pits.assign(truth_id=range(1, len(pits) + 1))
            tabs, _ = gt.score_raster(prob, tr, hb)
            rows.append({"fold": fold, "frac": fr, "recall_k40": gt.pooled_recall_at_k(tabs, list(tabs)),
                         "train_features": summary[fold][fr]})
    cp = tables / "okks_label_budget_curve_9t.csv"
    pd.DataFrame(rows).to_csv(cp, index=False)
    print(f"wrote {cp}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
