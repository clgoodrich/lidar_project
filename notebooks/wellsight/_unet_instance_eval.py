"""Apples-to-apples: score the semantic UNet outputs with the SAME per-instance
metric used for Mask R-CNN / YOLO.

The instance models are scored by `_instance_common.per_instance_metrics`
(polygon IoU of best-matching predicted instance vs each test GT polygon). UNet
only emits a per-pixel probability raster, so to compare fairly we:

  1. threshold the UNet prob raster,
  2. label connected components -> one polygon per blob (the "instances"),
  3. attach a score = mean prob inside the blob,
  4. run the IDENTICAL per_instance_metrics on the resulting GeoDataFrame.

We sweep a few thresholds and keep the best recall@0.3 row, so UNet is judged
at its most favourable operating point (fair, not cherry-picked against it).

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


def sweep(name: str, prob, tf, crs, gt: ic.InstanceSet) -> tuple[dict, pd.DataFrame]:
    best = None
    best_df = None
    rows = []
    for th in THRESHOLDS:
        pred = polygonize_prob(prob, tf, crs, th)
        df, metrics = ic.per_instance_metrics(pred if len(pred) else None, gt, "test")
        metrics["threshold"] = th
        metrics["n_pred_instances"] = int(len(pred))
        rows.append(metrics)
        print(f"  {name} thr={th}: n_pred={len(pred):5d}  "
              f"R@0.3={metrics['recall_at_iou_0.3']:.2f}  "
              f"R@0.5={metrics['recall_at_iou_0.5']:.2f}  "
              f"meanIoU={metrics['mean_best_iou']:.3f}")
        key = (metrics["recall_at_iou_0.3"], metrics["mean_best_iou"])
        if best is None or key > (best["recall_at_iou_0.3"], best["mean_best_iou"]):
            best = metrics
            best_df = df
    return best, best_df, pd.DataFrame(rows)


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

    md = [
        "# UNet scored with the instance-model metric (apples-to-apples)\n",
        "Semantic UNet prob rasters thresholded -> connected components -> "
        "polygons -> identical `per_instance_metrics`. Best-of-sweep threshold "
        "shown (UNet judged at its most favourable operating point).\n",
        "## Pits (20 test instances)\n",
        "| Threshold | # pred instances | R@0.3 | R@0.5 | Mean IoU |",
        "|---|---|---|---|---|",
    ]
    for _, r in pit_sweep.iterrows():
        star = " **(best)**" if r["threshold"] == pit_best["threshold"] else ""
        md.append(f"| {r['threshold']}{star} | {int(r['n_pred_instances'])} | "
                  f"{r['recall_at_iou_0.3']:.2f} | {r['recall_at_iou_0.5']:.2f} | "
                  f"{r['mean_best_iou']:.3f} |")
    md += ["\n## Plats (9 test instances)\n",
           "| Threshold | # pred instances | R@0.3 | R@0.5 | Mean IoU |",
           "|---|---|---|---|---|"]
    for _, r in plat_sweep.iterrows():
        star = " **(best)**" if r["threshold"] == plat_best["threshold"] else ""
        md.append(f"| {r['threshold']}{star} | {int(r['n_pred_instances'])} | "
                  f"{r['recall_at_iou_0.3']:.2f} | {r['recall_at_iou_0.5']:.2f} | "
                  f"{r['mean_best_iou']:.3f} |")
    (OUTDIR / "SUMMARY.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nWrote {OUTDIR / 'SUMMARY.md'}")
    print(f"PIT  best: thr={pit_best['threshold']} R@0.3={pit_best['recall_at_iou_0.3']:.2f} "
          f"meanIoU={pit_best['mean_best_iou']:.3f}")
    print(f"PLAT best: thr={plat_best['threshold']} R@0.3={plat_best['recall_at_iou_0.3']:.2f} "
          f"meanIoU={plat_best['mean_best_iou']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
