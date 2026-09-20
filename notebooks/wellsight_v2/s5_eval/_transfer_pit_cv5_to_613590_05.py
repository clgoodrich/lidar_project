"""Does the 9t pit model work on a tile it has never seen? Score it on 613590.

THE QUESTION
------------
Every published pit number is 9t. Cross-validation proves those numbers are
STABLE across folds; it says nothing about whether they TRANSFER, because all
five folds are the same landscape, the same survey and the same annotator. The
BACKLOG calls this "the single largest unquantified optimism in every pit and
pad number we publish".

613590 answers it. It is a genuinely disjoint tile:

    9t        x 619,500 - 624,000    y 4,593,000 - 4,597,500
    613590    x 613,500 - 618,000    y 4,590,000 - 4,594,500

No overlap in x at all, so nothing in 613590 can have leaked into training.

WHAT IS SCOREABLE HERE, AND WHAT IS NOT
---------------------------------------
**613590 IS NOT FULLY ANNOTATED.** 153 pit floors and 36 rims are drawn inside
it. That is not a complete inventory of the tile, it is whatever has been drawn
so far. Two consequences, and they are not symmetric:

  RECALL IS VALID.      Of the 153 floors that ARE drawn, how many did the model
                        find? A drawn pit the model missed is a real miss.

  PRECISION IS INVALID. An unmatched prediction may be a false positive OR a
                        real pit nobody has drawn yet, and nothing here can tell
                        those apart. **This script does not compute precision,
                        and the count of unmatched predictions must never be
                        reported as one.** It is emitted as
                        `n_unmatched_pred_NOT_FALSE_POSITIVES` so the name
                        refuses the misreading.

  Recall also carries a softer caveat: the drawn set may be biased toward
  obvious pits, which would flatter recall. Stated, not corrected.

DESIGN
------
Five checkpoints, not one. `data/9t/models/pit/unet_cv5/fold{0..4}/best.pt` each
saw 80% of 9t. Running all five on 613590 gives a transfer number WITH a
fold-to-fold spread, directly comparable to the held-out 9t spread in
`pit_cv5_per_fold_9t.csv`. One checkpoint would give a point estimate with no
way to tell a real drop from fold noise.

THRESHOLDS ARE FROZEN FROM 9t. Each fold carries the threshold that fold's own
9t validation chose, read from `pit_cv5_per_fold_9t.csv`, under both the F1 and
the F2 objective. Nothing is tuned on 613590 -- tuning on the test tile is the
exact defect the 2026-07-01 methodology audit found and fixed.

mu and sd come OUT OF THE CHECKPOINT. Recomputing them on this tile shifts every
input by a couple of percent, nothing errors, and the numbers quietly get worse.

Matching is the project's greedy 1:1 IoU rule at tau 0.3 and 0.5, plus rim
containment, copied from `_pit_unet_cv5.py` so the 9t and 613590 numbers are the
same measurement.

OUTPUTS -- all under data/_comparisons/pit_heldout_and_transfer_2026-09-20/
613590_transfer_from_9t_cv5_05/
    pit_transfer_recall_per_fold_613590_05.csv
    pit_transfer_recall_summary_613590_05.json
    pit_transfer_found_vs_missed_fold{k}_{obj}_thr{t}_613590_05.gpkg
    pit_prob_floor_cv5fold{k}_613590_05.tif      (only with --keep-prob)

Run:
    python notebooks/wellsight_v2/s5_eval/_transfer_pit_cv5_to_613590_05.py
    ... --folds 0 --keep-prob        # one fold, keep the raster
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import scipy.ndimage as ndi
import torch
from rasterio.features import shapes
from shapely.geometry import box, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _dl import DEVICE, UNet, predict_full_tile  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FEATURES = ROOT / "data/613590/derived/inference_05/features_613590_05.tif"
CKPT_DIR = ROOT / "data/9t/models/pit/unet_cv5"
PER_FOLD = CKPT_DIR / "pit_cv5_per_fold_9t.csv"
ANN = ROOT / "qgis/annotations/annotations_proj.gpkg"
OUT = (ROOT / "data/_comparisons/pit_heldout_and_transfer_2026-09-20"
       / "613590_transfer_from_9t_cv5_05")

#: 613590 tile footprint, EPSG:6346. Read off dem_613590_05.tif.
TILE = (613500.0, 4590000.0, 618000.0, 4594500.0)

N_CLASSES = 3
FLOOR_CLASS = 1
PATCH, OVERLAP = 256, 64
MIN_AREA_M2 = 4.0
REPORT_TAUS = (0.3, 0.5)


def polygonize(prob, transform, crs, thr, min_area=MIN_AREA_M2):
    """Probability raster -> scored polygons. Copied from _pit_unet_cv5."""
    mask = prob >= thr
    if not mask.any():
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    lbl, n = ndi.label(mask)
    means = ndi.mean(prob, labels=lbl, index=np.arange(1, n + 1))
    rows = []
    for geom, val in shapes(lbl.astype(np.int32), mask=mask, transform=transform):
        i = int(val)
        if i < 1:
            continue
        g = shape(geom)
        if g.area < min_area:
            continue
        rows.append({"score": float(means[i - 1]), "geometry": g})
    return (gpd.GeoDataFrame(rows, crs=crs) if rows
            else gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs))


def match_scores(gt, pred, taus=REPORT_TAUS):
    """Greedy 1:1 IoU matching. Copied from _pit_unet_cv5.

    Returns recall and the raw counts. **Precision is deliberately NOT returned**
    -- see the module docstring. The annotation on this tile is incomplete, so
    the precision denominator is not a denominator.
    """
    n_gt, n_pred = len(gt), len(pred)
    pairs = []
    if n_gt and n_pred:
        sidx = pred.sindex
        sc = pred["score"].to_numpy()
        for gi, r in enumerate(gt.itertuples()):
            g = r.geometry
            for pj in sidx.intersection(g.bounds):
                p = pred.geometry.iloc[pj]
                inter = g.intersection(p).area
                if inter <= 0:
                    continue
                u = g.area + p.area - inter
                if u > 0:
                    pairs.append((gi, int(pj), inter / u, float(sc[pj])))
    res = {}
    for t in taus:
        ug, up, tp = set(), set(), 0
        for gi, pj, iou, s in sorted((p for p in pairs if p[2] >= t),
                                     key=lambda p: -p[3]):
            if gi in ug or pj in up:
                continue
            ug.add(gi); up.add(pj); tp += 1
        res[t] = dict(tp=tp, n_gt=n_gt, n_pred=n_pred,
                      recall=tp / n_gt if n_gt else 0.0,
                      n_unmatched_pred_NOT_FALSE_POSITIVES=n_pred - tp,
                      matched_gt_idx=sorted(ug))
    return res


def containment(rims, pred):
    """Fraction of rims holding at least one prediction centroid."""
    if not len(rims) or not len(pred):
        return 0.0, 0
    hits = 0
    sidx = pred.sindex
    cents = pred.geometry.centroid
    for r in rims.itertuples():
        for pj in sidx.intersection(r.geometry.bounds):
            if r.geometry.contains(cents.iloc[pj]):
                hits += 1
                break
    return hits / len(rims), hits


def load_truth():
    foot = box(*TILE)
    floors = gpd.read_file(ANN, layer="pit_inside", engine="pyogrio")
    rims = gpd.read_file(ANN, layer="pit_outside", engine="pyogrio")
    floors = floors[floors.geometry.notna() & floors.geometry.intersects(foot)]
    rims = rims[rims.geometry.notna() & rims.geometry.intersects(foot)]
    return floors.reset_index(drop=True), rims.reset_index(drop=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, nargs="*", default=[0, 1, 2, 3, 4])
    ap.add_argument("--keep-prob", action="store_true",
                    help="also write each fold's floor probability raster "
                         "(~230 MB each, gitignored)")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    floors, rims = load_truth()
    print(f"613590 truth: {len(floors)} pit floors, {len(rims)} rims")
    print("  ANNOTATION IS INCOMPLETE -- recall is valid, precision is NOT\n")

    thr_tab = pd.read_csv(PER_FOLD)
    with rasterio.open(FEATURES) as r:
        tf, crs = r.transform, r.crs
    print(f"features {FEATURES.name}  crs {crs}\n")

    rows = []
    for k in a.folds:
        ck_path = CKPT_DIR / f"fold{k}" / "best.pt"
        ck = torch.load(ck_path, map_location="cpu", weights_only=False)
        mu, sd = np.asarray(ck["mu"]), np.asarray(ck["sd"])
        model = UNet(in_ch=len(ck["channels"]), n_classes=N_CLASSES, base=32)
        model.load_state_dict(ck["state_dict"])
        print(f"=== fold {k}  (9t epoch {ck['epoch']}, "
              f"9t val score {ck['score']:.3f}) ===")

        prob, _, prof = predict_full_tile(
            model, FEATURES, mu, sd, patch=PATCH, overlap=OVERLAP,
            n_classes=N_CLASSES)
        floor_prob = prob[FLOOR_CLASS]
        del prob
        if a.keep_prob:
            p = OUT / f"pit_prob_floor_cv5fold{k}_613590_05.tif"
            pr = prof.copy()
            pr.update(count=1, dtype="float32", nodata=-1.0,
                      compress="deflate", predictor=2)
            with rasterio.open(p, "w", **pr) as d:
                d.write(floor_prob, 1)
            print(f"    wrote {p}")

        for obj in ("f1", "f2"):
            sel = thr_tab[(thr_tab.fold == k) & (thr_tab.objective == obj)]
            thr = float(sel.prob_threshold.iloc[0])
            ref_recall = float(sel.recall_iou30.iloc[0])
            pred = polygonize(floor_prob, tf, crs, thr)
            m = match_scores(floors, pred)
            cont, hits = containment(rims, pred)
            tag = f"thr{str(thr).replace('.', 'p')}"
            print(f"  {obj.upper()}-selected thr {thr:.2f}   "
                  f"9t held-out R@0.3 {ref_recall:.3f}  ->  "
                  f"613590 R@0.3 {m[0.3]['recall']:.3f}  "
                  f"R@0.5 {m[0.5]['recall']:.3f}  "
                  f"containment {cont:.3f}  "
                  f"({m[0.3]['n_pred']} predictions, "
                  f"{m[0.3]['n_unmatched_pred_NOT_FALSE_POSITIVES']} unmatched "
                  f"-- NOT scored as FPs)")

            gt = floors.copy()
            gt["found_iou30"] = [i in set(m[0.3]["matched_gt_idx"])
                                 for i in range(len(gt))]
            gt["fold"] = k
            gt["objective"] = obj
            gt["prob_threshold"] = thr
            gt["NOTE"] = "annotation incomplete; recall valid, precision not"
            gp = (OUT / f"pit_transfer_found_vs_missed_fold{k}_{obj}_"
                        f"{tag}_613590_05.gpkg")
            gt.to_file(gp, driver="GPKG", layer="pit_floors_scored")
            pred.assign(fold=k, objective=obj, prob_threshold=thr).to_file(
                gp, driver="GPKG", layer="predictions_unmatched_not_FPs")

            rows.append(dict(
                fold=k, objective=obj, prob_threshold=thr,
                ckpt_epoch=int(ck["epoch"]),
                n_gt_floors_613590=len(floors), n_rims_613590=len(rims),
                n_pred=m[0.3]["n_pred"],
                n_unmatched_pred_NOT_FALSE_POSITIVES=(
                    m[0.3]["n_unmatched_pred_NOT_FALSE_POSITIVES"]),
                recall_iou30_613590=m[0.3]["recall"],
                recall_iou50_613590=m[0.5]["recall"],
                containment_613590=cont, containment_hits=hits,
                recall_iou30_9t_heldout=ref_recall,
                delta_recall_iou30=m[0.3]["recall"] - ref_recall))
        del floor_prob

    df = pd.DataFrame(rows)
    csv = OUT / "pit_transfer_recall_per_fold_613590_05.csv"
    df.to_csv(csv, index=False)

    summary = {"tile": "613590", "tile_bounds_epsg6346": list(TILE),
               "source_model": "data/9t/models/pit/unet_cv5 (5 folds)",
               "annotation_complete": False,
               "precision_reported": False,
               "why_no_precision": (
                   "613590 is not fully annotated. An unmatched prediction may "
                   "be a false positive or an undrawn real pit; nothing here "
                   "separates them."),
               "n_gt_floors": len(floors), "n_rims": len(rims), "by_objective": {}}
    for obj in ("f1", "f2"):
        d = df[df.objective == obj]
        if not len(d):
            continue
        summary["by_objective"][obj] = {
            "recall_iou30_613590_mean": float(d.recall_iou30_613590.mean()),
            "recall_iou30_613590_sd": float(d.recall_iou30_613590.std(ddof=0)),
            "recall_iou30_9t_heldout_mean": float(d.recall_iou30_9t_heldout.mean()),
            "recall_iou30_9t_heldout_sd": float(d.recall_iou30_9t_heldout.std(ddof=0)),
            "delta_mean": float(d.delta_recall_iou30.mean()),
            "containment_613590_mean": float(d.containment_613590.mean())}
    js = OUT / "pit_transfer_recall_summary_613590_05.json"
    js.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(f"\n{'=' * 70}\nTRANSFER 9t -> 613590, pit floors, recall only")
    for obj, s in summary["by_objective"].items():
        print(f"  {obj.upper()}: 9t held-out {s['recall_iou30_9t_heldout_mean']:.3f} "
              f"(sd {s['recall_iou30_9t_heldout_sd']:.3f})  ->  "
              f"613590 {s['recall_iou30_613590_mean']:.3f} "
              f"(sd {s['recall_iou30_613590_sd']:.3f})   "
              f"delta {s['delta_mean']:+.3f}")
    print(f"\n  {csv}\n  {js}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
