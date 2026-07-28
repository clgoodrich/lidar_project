"""Pit CV recall/precision as a function of IoU strictness, pooled over 5 folds.

The 5-fold run reported IoU 0.3 and 0.5 only. The AGU abstract quotes a range
that ends at IoU 0.6, so this fills in the scale without retraining anything.

CRITICAL, same rule as `_plot_iou_strictness_scale_9t.py`: each fold's
probability threshold is the one ALREADY selected on that fold's inner val
split, and it is held FIXED across every tau. Re-selecting per tau would
manufacture a flattering curve.

CPU only. Reads the five existing fold probability rasters.

Run:
  python notebooks/wellsight_v2/eval/_pit_cv5_tau_scale.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize as _rasterize

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "pits"))
from _pit_unet_cv5 import (ANN_GPKG, BLOCKS, CRS, FEATURES, OUTDIR, SCORE_BUF_M,
                           match_scores, polygonize)

TAUS = (0.3, 0.4, 0.5, 0.6, 0.7)
OBJECTIVES = ("f1", "f2")


def main() -> int:
    fold_df = pd.read_csv(OUTDIR / "pit_cv5_per_fold_9t.csv")
    assign = pd.read_csv(OUTDIR / "pit_cv5_fold_assignment_9t.csv")
    blocks = gpd.read_file(BLOCKS, layer="blocks").to_crs(CRS)
    blocks = blocks.merge(assign[["block_id", "fold"]].drop_duplicates(),
                          on="block_id", how="inner")

    floors = gpd.read_file(ANN_GPKG, layer="pit_inside").to_crs(CRS)
    floors = floors[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
    floors = floors.merge(assign[["pit_id", "fold"]], on="pit_id", how="inner")

    with rasterio.open(FEATURES) as r:
        tf, rcrs = r.transform, r.crs

    rows = []
    for obj in OBJECTIVES:
        for k in sorted(fold_df.fold.unique()):
            sel = fold_df[(fold_df.fold == k) & (fold_df.objective == obj)]
            thr = float(sel.prob_threshold.iloc[0])
            tif = OUTDIR / f"fold{k}" / f"pit_prob_floor_cvfold{k}_9t_05.tif"
            with rasterio.open(tif) as r:
                prob = r.read(1).astype(np.float32)

            held = blocks[blocks.fold == k]
            foot = held.geometry.union_all()
            keep = _rasterize([(foot.buffer(SCORE_BUF_M), 1)],
                              out_shape=prob.shape, transform=tf, fill=0,
                              dtype="uint8").astype(bool)
            allp = polygonize(np.where(keep, prob, 0.0).astype(np.float32),
                              tf, rcrs, thr)
            if len(allp):
                cen = allp.geometry.centroid
                allp = allp[cen.within(foot)].reset_index(drop=True)

            gt = floors[floors.fold == k]
            m = match_scores(gt, allp, taus=TAUS)
            for t in TAUS:
                rows.append(dict(objective=obj, fold=k, threshold=thr, iou=t,
                                 n_gt=len(gt), n_pred=len(allp),
                                 recall=m[t]["recall"], precision=m[t]["precision"],
                                 f1=m[t]["f1"]))
            print(f"  {obj} fold {k} thr {thr:.2f}: "
                  + "  ".join(f"R@{t}={m[t]['recall']:.3f}" for t in TAUS))
            del prob, keep

    df = pd.DataFrame(rows)
    out = OUTDIR / "pit_cv5_iou_strictness_scale_9t.csv"
    df.to_csv(out, index=False)

    print(f"\n{'='*66}\nPOOLED ACROSS 5 FOLDS (all 426 pits)\n{'='*66}")
    md = ["| IoU required | pit R (F1-sel) | pit P (F1-sel) | pit R (F2-sel) | pit P (F2-sel) |",
          "|---|---|---|---|---|"]
    for t in TAUS:
        cells = []
        for obj in OBJECTIVES:
            g = df[(df.objective == obj) & (df.iou == t)]
            r = (g.recall * g.n_gt).sum() / g.n_gt.sum()
            p = (g.precision * g.n_pred).sum() / g.n_pred.sum()
            cells += [f"{r:.3f}", f"{p:.3f}"]
            if obj == "f1":
                print(f"  IoU {t}: F1-sel R {r:.3f}  P {p:.3f}"
                      f"   (per-fold {g.recall.min():.3f}-{g.recall.max():.3f})")
        md.append(f"| {t:.2f} | " + " | ".join(cells) + " |")
    tbl = OUTDIR / "pit_cv5_iou_strictness_scale_9t.md"
    tbl.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\n  wrote {out}\n  wrote {tbl}")
    print("\n".join(md))
    return 0


if __name__ == "__main__":
    sys.exit(main())
