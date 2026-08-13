"""Centroid-matched precision to pair with the CV5 containment/locate recall.

The 5-fold runs report recall two ways but precision only one way:

    recall   containment (pits) / locate (pads) -- centroid-inside-polygon
    recall   recall_iou30                       -- 30% outline overlap
    precision precision_iou30                   -- 30% outline overlap ONLY

So quoting "locates 90% of pits at precision 0.62" mixes two different
definitions of a hit in one sentence. This script computes the missing half so
both numbers can share a rule.

Why centroid matching at all: Fiorucci et al. 2022 (Remote Sensing 14(7):1694)
argue IoU is the wrong criterion for small discrete archaeological objects,
because boundary disagreement on a feature a few metres across swamps the
overlap. Lidberg et al. 2024 (J. Field Archaeology 49(6):395-405) adopt their
centroid-based approach for hunting pits and report recall/precision/F1 from it.
Our `containment` column is already that criterion under another name.

Two precision variants are computed, because the recall side is deliberately
lenient (a rim holding three predictions counts once):

    lenient  TP = predictions whose centroid falls inside ANY annotated feature.
             Pairs with containment recall as published, but a model that
             shatters one pit into five blobs is rewarded five times.
    greedy   TP = 1:1 assignment, highest-scoring prediction first, each
             prediction and each annotation used at most once. Extra blobs on an
             already-matched feature become false positives. This is the
             defensible pair and what Fiorucci/Lidberg-style TP/FP/FN counting
             implies.

Both are reported. Recall is recomputed under each rule rather than copied, so
the numbers in a row are internally consistent.

No retraining and no re-inference. Reuses the per-fold probability rasters and
the exact polygonize/threshold settings of the CV runs, so results are directly
comparable to `pit_cv5_per_fold_9t.csv` / `pad_cv5_per_fold_9t.csv`.

Outputs (data/05_results/9t/pit/centroid_matching/):
    centroid_matching_cv5_pit_pad_9t.csv   per fold, per target, per objective
    _centroid_matching_cv5_9t.json         pooled summary

Reproduce:
  python notebooks/wellsight_v2/s5_eval/_cv5_centroid_precision_pit_pad_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize as _rasterize

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s3_train"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight_v2" / "s5_eval"))

from _common import DERIV_9T, path_for  # noqa: E402
from _pit_unet_cv5 import assign_folds, polygonize              # noqa: E402

ANN_GPKG = path_for("truth") / "annotations_proj.gpkg"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
OUT = path_for("results") / "9t" / "pit" / "centroid_matching"

CRS = "EPSG:6346"
CV_SEED = 20260727          # must match both CV runs
K = 5

# Per-target settings, lifted verbatim from the two CV scripts.
TARGETS = {
    "pit": dict(
        outdir=path_for("models") / "pit" / "unet_cv5",
        per_fold="pit_cv5_per_fold_9t.csv",
        blocks=DERIV_9T / "pit_blocks_9t.gpkg",
        manifest=DERIV_9T / "pit_dataset_manifest.csv",
        id_col="pit_id", n_col="n_pits",
        gt_layer="pit_outside",     # rims: containment is centroid-inside-RIM
        prob_name="pit_prob_floor_cvfold{k}_9t_05.tif",
        min_area=4.0, score_buf=40.0,
    ),
    "pad": dict(
        outdir=path_for("models") / "pad" / "unet_cv5",
        per_fold="pad_cv5_per_fold_9t.csv",
        blocks=DERIV_9T / "plat_blocks_9t.gpkg",
        manifest=DERIV_9T / "plat_dataset_manifest.csv",
        id_col="plat_id", n_col="n_pads",
        gt_layer="plat",
        prob_name="pad_prob_cvfold{k}_9t_05.tif",
        min_area=100.0, score_buf=80.0,
    ),
}


def centroid_match(gt: gpd.GeoDataFrame, pred: gpd.GeoDataFrame):
    """Centroid-inside-polygon matching, lenient and greedy 1:1.

    Returns (lenient, greedy) dicts with tp/recall/precision/f1.
    """
    n_gt, n_pred = len(gt), len(pred)
    empty = dict(tp=0, n_gt=n_gt, n_pred=n_pred, recall=0.0, precision=0.0, f1=0.0)
    if not n_gt or not n_pred:
        return dict(empty), dict(empty)

    cents = pred.geometry.centroid
    scores = pred["score"].to_numpy()
    sidx = pred.sindex

    pairs = []                       # (gi, pj, score) centroid of pj inside gt gi
    for gi, r in enumerate(gt.itertuples()):
        for pj in sidx.intersection(r.geometry.bounds):
            if r.geometry.contains(cents.iloc[int(pj)]):
                pairs.append((gi, int(pj), float(scores[int(pj)])))

    def _pack(tp):
        rec = tp / n_gt
        pre = tp / n_pred
        return dict(tp=int(tp), n_gt=n_gt, n_pred=n_pred, recall=rec,
                    precision=pre,
                    f1=2 * pre * rec / (pre + rec) if (pre + rec) else 0.0)

    # lenient: recall counts gt hit at least once, precision counts any
    # prediction landing inside something. Denominators differ, as published.
    hit_gt = len({gi for gi, _, _ in pairs})
    hit_pred = len({pj for _, pj, _ in pairs})
    lenient = dict(tp=int(hit_gt), n_gt=n_gt, n_pred=n_pred,
                   recall=hit_gt / n_gt, precision=hit_pred / n_pred,
                   tp_pred=int(hit_pred))
    p, r_ = lenient["precision"], lenient["recall"]
    lenient["f1"] = 2 * p * r_ / (p + r_) if (p + r_) else 0.0

    # greedy 1:1, highest-scoring prediction first
    ug, up, tp = set(), set(), 0
    for gi, pj, _ in sorted(pairs, key=lambda t: -t[2]):
        if gi in ug or pj in up:
            continue
        ug.add(gi); up.add(pj); tp += 1
    return lenient, _pack(tp)


def run_target(name: str, cfg: dict, tf, rcrs) -> list[dict]:
    man = pd.read_csv(cfg["manifest"])
    blocks = gpd.read_file(cfg["blocks"], layer="blocks").to_crs(CRS)
    n_per = man.groupby("block_id").size().rename(cfg["n_col"]).reset_index()
    fold_of = assign_folds(n_per[["block_id", cfg["n_col"]]], K, CV_SEED)
    man["fold"] = man.block_id.map(fold_of)
    blocks["fold"] = blocks.block_id.map(fold_of)

    gt_all = gpd.read_file(ANN_GPKG, layer=cfg["gt_layer"]).to_crs(CRS)
    gt_all = gt_all[[cfg["id_col"], "geometry"]].dissolve(
        by=cfg["id_col"]).reset_index()
    gt_all = gt_all.merge(man[[cfg["id_col"], "fold"]], on=cfg["id_col"],
                          how="inner")

    sel = pd.read_csv(cfg["outdir"] / cfg["per_fold"])
    rows = []
    for k in range(K):
        prob_tif = cfg["outdir"] / f"fold{k}" / cfg["prob_name"].format(k=k)
        if not prob_tif.exists():
            print(f"  [{name} fold {k}] MISSING {prob_tif} -- skipped")
            continue
        with rasterio.open(prob_tif) as r:
            prob = r.read(1).astype(np.float32)

        held_blocks = sorted(man.loc[man.fold == k, "block_id"].unique())
        foot_held = blocks.loc[
            blocks.block_id.isin(held_blocks)].geometry.union_all()
        keep = _rasterize([(foot_held.buffer(cfg["score_buf"]), 1)],
                          out_shape=prob.shape, transform=tf, fill=0,
                          dtype="uint8").astype(bool)
        prob_scored = np.where(keep, prob, 0.0).astype(np.float32)
        gt_held = gt_all[gt_all.fold == k].reset_index(drop=True)

        for obj in ("f1", "f2"):
            r_sel = sel[(sel.fold == k) & (sel.objective == obj)]
            if not len(r_sel):
                continue
            thr = float(r_sel.prob_threshold.iloc[0])
            allp = polygonize(prob_scored, tf, rcrs, thr,
                              min_area=cfg["min_area"])
            if len(allp):
                cen = allp.geometry.centroid
                hp = allp[cen.within(foot_held)].reset_index(drop=True)
            else:
                hp = allp
            len_m, greedy = centroid_match(gt_held, hp)
            pub = float(r_sel.get("containment",
                                  r_sel.get("locate")).iloc[0])
            rows.append(dict(
                target=name, fold=k, objective=obj, prob_threshold=thr,
                n_gt=len(gt_held), n_pred=len(hp),
                published_recall_centroid=pub,
                lenient_recall=len_m["recall"],
                lenient_precision=len_m["precision"], lenient_f1=len_m["f1"],
                lenient_tp_gt=len_m["tp"], lenient_tp_pred=len_m["tp_pred"],
                greedy_tp=greedy["tp"], greedy_recall=greedy["recall"],
                greedy_precision=greedy["precision"], greedy_f1=greedy["f1"],
                iou30_recall=float(r_sel.recall_iou30.iloc[0]),
                iou30_precision=float(r_sel.precision_iou30.iloc[0])))
            print(f"  [{name} fold {k} {obj}] thr {thr:.2f}  "
                  f"n_gt {len(gt_held):4d} n_pred {len(hp):4d} | "
                  f"lenient R {len_m['recall']:.3f} P {len_m['precision']:.3f} | "
                  f"greedy R {greedy['recall']:.3f} P {greedy['precision']:.3f} | "
                  f"published centroid R {pub:.3f}")
    return rows


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    with rasterio.open(FEATURES) as r:
        tf, rcrs = r.transform, r.crs

    rows = []
    for name, cfg in TARGETS.items():
        print(f"\n=== {name} ===")
        rows += run_target(name, cfg, tf, rcrs)

    df = pd.DataFrame(rows)
    csv = OUT / "centroid_matching_cv5_pit_pad_9t.csv"
    df.to_csv(csv, index=False)

    summary = {}
    print(f"\n{'='*74}\nPOOLED over folds (every object scored by a model that "
          f"never saw it)\n{'='*74}")
    for name in TARGETS:
        for obj in ("f1", "f2"):
            g = df[(df.target == name) & (df.objective == obj)]
            if not len(g):
                continue
            n_gt, n_pred = int(g.n_gt.sum()), int(g.n_pred.sum())
            key = f"{name}_{obj}"
            summary[key] = {
                "n_gt": n_gt, "n_pred": n_pred,
                "thresholds": sorted(g.prob_threshold.tolist()),
                "lenient": {
                    "recall": int(g.lenient_tp_gt.sum()) / n_gt,
                    "precision": int(g.lenient_tp_pred.sum()) / n_pred,
                    "tp_gt": int(g.lenient_tp_gt.sum()),
                    "tp_pred": int(g.lenient_tp_pred.sum())},
                "greedy": {
                    "recall": int(g.greedy_tp.sum()) / n_gt,
                    "precision": int(g.greedy_tp.sum()) / n_pred,
                    "tp": int(g.greedy_tp.sum())},
                "iou30": {
                    "recall": float((g.iou30_recall * g.n_gt).sum() / n_gt),
                    "precision": float(
                        (g.iou30_precision * g.n_pred).sum() / n_pred)},
                "published_recall_centroid": float(
                    (g.published_recall_centroid * g.n_gt).sum() / n_gt),
            }
            s = summary[key]
            s["lenient"]["f1"] = (
                2 * s["lenient"]["precision"] * s["lenient"]["recall"]
                / max(s["lenient"]["precision"] + s["lenient"]["recall"], 1e-9))
            s["greedy"]["f1"] = (
                2 * s["greedy"]["precision"] * s["greedy"]["recall"]
                / max(s["greedy"]["precision"] + s["greedy"]["recall"], 1e-9))
            print(f"\n{name.upper()}  thr selected by {obj}   "
                  f"n_gt={n_gt}  n_pred={n_pred}")
            print(f"  centroid lenient  R {s['lenient']['recall']:.3f}  "
                  f"P {s['lenient']['precision']:.3f}  "
                  f"F1 {s['lenient']['f1']:.3f}")
            print(f"  centroid greedy   R {s['greedy']['recall']:.3f}  "
                  f"P {s['greedy']['precision']:.3f}  "
                  f"F1 {s['greedy']['f1']:.3f}   (tp {s['greedy']['tp']})")
            print(f"  IoU 0.3           R {s['iou30']['recall']:.3f}  "
                  f"P {s['iou30']['precision']:.3f}")
            print(f"  published centroid recall {s['published_recall_centroid']:.3f}"
                  f"  <- must match lenient R")

    (OUT / "_centroid_matching_cv5_9t.json").write_text(
        json.dumps(summary, indent=2, default=float))
    print(f"\nwrote {csv}")
    print(f"wrote {OUT / '_centroid_matching_cv5_9t.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
