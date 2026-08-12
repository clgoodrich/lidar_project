"""Apples-to-apples: score the semantic UNet outputs with the SAME per-instance
metric used for Mask R-CNN / YOLO.

The instance models are scored by `_instance_common.per_instance_metrics`
(polygon IoU of best-matching predicted instance vs each test GT polygon). UNet
only emits a per-pixel probability raster, so to compare fairly we:

  1. threshold the UNet prob raster,
  2. label connected components -> one polygon per blob (the "instances"),
  3. attach a score = mean prob inside the blob,
  4. run the IDENTICAL per_instance_metrics on the resulting GeoDataFrame.

The threshold is selected on the VAL split (best F1@0.3), then the frozen
threshold is scored ONCE on test — the reported test numbers are never used
for selection. (Pre-2026-07 runs selected the threshold on test itself, which
optimistically biased the reported recall.)

Pit prob = max(floor_prob, wall_prob)  (pit_unet_v2 emits two class bands).
Plat prob = plat_prob.tif single band.

Writes data/derivatives/tiles/9t/iterations/unet_instance_eval/SUMMARY.md + CSVs.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import shapes
from scipy import ndimage
from shapely.geometry import shape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV_9T, DST_CRS  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "unet_instance_eval"
THRESHOLDS = [0.3, 0.5, 0.7]
MIN_AREA_M2 = 4.0  # same floor as detections_to_gpkg


def polygonize_prob(prob: np.ndarray, transform, crs, thresh: float,
                    min_area_m2: float = MIN_AREA_M2) -> gpd.GeoDataFrame:
    """Threshold -> connected components -> one scored polygon per blob."""
    mask = prob >= thresh
    if not mask.any():
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    labels, n = ndimage.label(mask)
    # Mean prob per label = instance score.
    means = ndimage.mean(prob, labels=labels, index=np.arange(1, n + 1))
    rows = []
    for geom, val in shapes(labels.astype(np.int32), mask=mask, transform=transform):
        lbl = int(val)
        if lbl == 0:
            continue
        g = shape(geom)
        if g.area < min_area_m2:
            continue
        rows.append({"score": float(means[lbl - 1]), "geometry": g})
    if not rows:
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    return gpd.GeoDataFrame(rows, crs=crs)


def read_pit_prob() -> tuple[np.ndarray, object, object]:
    floor = DERIV_9T / "pit_unet_v2" / "pit_prob_floor.tif"
    wall = DERIV_9T / "pit_unet_v2" / "pit_prob_wall.tif"
    with rasterio.open(floor) as r:
        f = r.read(1); tf = r.transform; crs = r.crs; nd = r.nodata
    with rasterio.open(wall) as r:
        w = r.read(1)
    if nd is not None:
        f = np.where(f == nd, 0.0, f)
        w = np.where(w == nd, 0.0, w)
    return np.maximum(f, w), tf, crs


def read_plat_prob() -> tuple[np.ndarray, object, object]:
    p = DERIV_9T / "plat_unet" / "plat_prob.tif"
    with rasterio.open(p) as r:
        arr = r.read(1); tf = r.transform; crs = r.crs; nd = r.nodata
    if nd is not None:
        arr = np.where(arr == nd, 0.0, arr)
    return arr, tf, crs


def sweep(name: str, prob, tf, crs, gt: ic.InstanceSet) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Select threshold on VAL (F1@0.3, mean-IoU tiebreak); score it once on test."""
    best_th, best_key = None, None
    val_rows = []
    preds = {}
    for th in THRESHOLDS:
        pred = polygonize_prob(prob, tf, crs, th)
        preds[th] = pred
        _, vm = ic.per_instance_metrics(pred if len(pred) else None, gt, "val")
        vm["threshold"] = th
        vm["n_pred_instances"] = int(len(pred))
        val_rows.append(vm)
        print(f"  {name} thr={th} [val]: n_pred={len(pred):5d}  "
              f"F1@0.3={vm['f1_at_iou_0.3']:.3f}  R@0.3={vm['recall_at_iou_0.3']:.2f}  "
              f"P@0.3={vm['precision_at_iou_0.3']:.3f}")
        key = (vm["f1_at_iou_0.3"], vm["mean_best_iou"])
        if best_key is None or key > best_key:
            best_key, best_th = key, th
    df, metrics = ic.per_instance_metrics(
        preds[best_th] if len(preds[best_th]) else None, gt, "test")
    metrics["threshold"] = best_th
    metrics["n_pred_instances"] = int(len(preds[best_th]))
    print(f"  {name} FROZEN thr={best_th} [test]: "
          f"R@0.3={metrics['recall_at_iou_0.3']:.2f}  "
          f"P@0.3={metrics['precision_at_iou_0.3']:.3f}  "
          f"F1@0.3={metrics['f1_at_iou_0.3']:.3f}  "
          f"meanIoU={metrics['mean_best_iou']:.3f}")
    return metrics, df, pd.DataFrame(val_rows)


def main() -> int:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    pit_set = ic.load_pit_set()
    plat_set = ic.load_plat_set()

    print("PIT UNet (pit_unet_v2):")
    pit_prob, pit_tf, pit_crs = read_pit_prob()
    pit_best, pit_df, pit_sweep = sweep("pit", pit_prob, pit_tf, pit_crs, pit_set)
    pit_sweep.to_csv(OUTDIR / "pit_unet_sweep.csv", index=False)
    pit_df.to_csv(OUTDIR / "pit_unet_best_per_inst.csv", index=False)

    print("\nPLAT UNet (plat_unet):")
    plat_prob, plat_tf, plat_crs = read_plat_prob()
    plat_best, plat_df, plat_sweep = sweep("plat", plat_prob, plat_tf, plat_crs, plat_set)
    plat_sweep.to_csv(OUTDIR / "plat_unet_sweep.csv", index=False)
    plat_df.to_csv(OUTDIR / "plat_unet_best_per_inst.csv", index=False)

    def block(title, val_sweep, best):
        out = [f"\n## {title} ({best['n_test_instances']} test instances)\n",
               "Threshold selected on VAL (F1@0.3); test scored once at the frozen threshold.\n",
               "| Threshold (val sweep) | # pred | val F1@0.3 | val R@0.3 | val P@0.3 |",
               "|---|---|---|---|---|"]
        for _, r in val_sweep.iterrows():
            star = " **(chosen)**" if r["threshold"] == best["threshold"] else ""
            out.append(f"| {r['threshold']}{star} | {int(r['n_pred_instances'])} | "
                       f"{r['f1_at_iou_0.3']:.3f} | {r['recall_at_iou_0.3']:.2f} | "
                       f"{r['precision_at_iou_0.3']:.3f} |")
        out += ["",
                f"**Test @ thr={best['threshold']}** (1:1 matching): "
                f"R@0.3 = {best['recall_at_iou_0.3']:.2f}, "
                f"P@0.3 = {best['precision_at_iou_0.3']:.3f}, "
                f"F1@0.3 = {best['f1_at_iou_0.3']:.3f}, "
                f"R@0.5 = {best['recall_at_iou_0.5']:.2f}, "
                f"mean best IoU = {best['mean_best_iou']:.3f}, "
                f"loose R@0.3 = {best['recall_loose_at_iou_0.3']:.2f} "
                f"(legacy definition), n_pred = {best['n_pred_instances']}."]
        return out

    md = [
        "# UNet scored with the instance-model metric (apples-to-apples)\n",
        "Semantic UNet prob rasters thresholded -> connected components -> "
        "polygons -> identical `per_instance_metrics` (greedy 1:1 matching + "
        "precision as of 2026-07-02).\n",
    ]
    md += block("Pits", pit_sweep, pit_best)
    md += block("Pads", plat_sweep, plat_best)
    (OUTDIR / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nWrote {OUTDIR / 'SUMMARY.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
