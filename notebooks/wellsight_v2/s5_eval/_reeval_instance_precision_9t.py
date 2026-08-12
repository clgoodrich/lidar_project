"""Honest 9t instance metrics: matched extent, matched class, val-frozen thresholds.

WHY THIS EXISTS
---------------
The leaderboard reports precision 0.029-0.070 for every pit/pad model, which is
irreconcilable with how the detections look in QGIS. Three separate deflations
were found, all in the measurement rather than the models:

1. EXTENT MISMATCH (`_instance_common.per_instance_metrics`):
       gt_split = gt.for_split(split)   # TEST GT only (93 of 650 pads)
       prec = tp / n_pred               # ...but ALL detections, whole tile
   The 9t split is block-wise over spatially INTERLEAVED blocks, and the test
   blocks are only ~12% of the tile. So ~86% of detections had no ground truth
   available to match against and were false positives by construction.

2. CLASS MISMATCH (pits): the pit models emit 'floor' AND 'wall' detections but
   the GT is pit_inside (floor) alone, so every wall detection was an automatic
   false positive. Same for the pit U-Net, whose prob raster is max(floor, wall).

3. UNTUNED SCORE THRESHOLD: the leaderboard notes the thresholds (0.3, YOLO pit
   0.05) were never tuned. Here the threshold is selected on VAL and then frozen
   and scored once on TEST, so test never informs selection.

NOTE ON THE BLOCK GEOMETRY. `blocks_unified_9t.gpkg` carries its own `split`
column which is a DIFFERENT assignment -- only 28 of the 93 pad-test instances
fall in its "test" blocks. Its block_id NUMBERING is shared, though (verified
650/650 pads and 426/426 pits land in the block matching their manifest row), so
each task's footprint is built from its own manifest's block_ids.

Outputs (data/derivatives/eval_9t_instance_precision/):
  metrics_9t.csv              as-is vs corrected, per model, per IoU
  val_threshold_sweep_9t.csv  the val selection that fixed each threshold
  scored_<model>.gpkg         detections labelled TP/FP  (layer 'detections')
                              + GT labelled matched/missed (layer 'gt')
  unet_instances_<kind>.gpkg  vectorized U-Net predictions (were raster-only)
  precision_reeval_9t.png     old vs corrected precision, and the sweeps
  detections_map_9t.png       TP / FP / FN on the ground, per model
  _reeval_9t.json             summary

Run:
  python notebooks/wellsight_v2/s5_eval/_reeval_instance_precision_9t.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from matplotlib.colors import LightSource
from matplotlib.patches import Patch
from rasterio.features import shapes
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[3]
NINE_T = ROOT / "data" / "derivatives" / "tiles" / "9t"
ITER = NINE_T / "iterations"
ANN_GPKG = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUT = ROOT / "data" / "derivatives" / "eval_9t_instance_precision"
OUT.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
# Full IoU sweep, so the whole precision/recall-vs-strictness curve is on record
# and no single tau has to be defended as "the" number. Widened 2026-07-27 from
# (0.1, 0.3, 0.5).
TAUS = (0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80, 0.90)
# The probability/score threshold is selected once at SEL_TAU and then held
# FIXED across every tau below. Re-selecting per tau would be exactly the
# cherry-picking this sweep exists to rule out.
SEL_TAU = 0.3                      # IoU at which the threshold is selected
MIN_AREA_M2 = 4.0                  # same blob floor as _unet_instance_eval
UNET_THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
SCORE_THRESHOLDS = np.round(np.arange(0.05, 0.96, 0.05), 2)

INSTANCE_MODELS = {
    "pit_07_maskrcnn": ("pit", ITER / "pit_07_maskrcnn" / "instances.gpkg"),
    "pit_08_yolo":     ("pit", ITER / "pit_08_yolo" / "instances.gpkg"),
    "pad_05_maskrcnn": ("pad", ITER / "pad_05_maskrcnn" / "instances.gpkg"),
    "pad_06_yolo":     ("pad", ITER / "pad_06_yolo" / "instances.gpkg"),
}
UNET_PROB = {
    # pits: floor prob ONLY. _unet_instance_eval used max(floor, wall), which
    # cannot be matched against floor-only GT without inflating false positives.
    "pit_unet_v2": ("pit", NINE_T / "pit_unet_v2" / "pit_prob_floor.tif"),
    "plat_unet":   ("pad", NINE_T / "plat_unet" / "plat_prob.tif"),
}


# --------------------------------------------------------------------------
# matching
# --------------------------------------------------------------------------
def iou_pairs(gt, pred):
    if pred is None or len(pred) == 0 or len(gt) == 0:
        return []
    sidx = pred.sindex
    scores = (pred["score"].astype(float).values if "score" in pred.columns
              else np.zeros(len(pred)))
    out = []
    for gi, r in enumerate(gt.itertuples()):
        g = r.geometry
        for pj in sidx.intersection(g.bounds):
            p = pred.geometry.iloc[pj]
            inter = g.intersection(p).area
            if inter <= 0:
                continue
            u = g.union(p).area
            if u > 0:
                out.append((gi, int(pj), inter / u, float(scores[pj])))
    return out


def match(pairs, tau):
    """Greedy 1:1. Returns {gt_i: pred_j} for matches at IoU >= tau."""
    used_gt, used_pred, m = set(), set(), {}
    for gi, pj, iou, s in sorted((p for p in pairs if p[2] >= tau),
                                 key=lambda p: -p[3]):
        if gi in used_gt or pj in used_pred:
            continue
        used_gt.add(gi); used_pred.add(pj); m[gi] = pj
    return m


def score(gt, pred, taus=TAUS):
    pairs = iou_pairs(gt, pred)
    n_gt = len(gt)
    n_pred = 0 if pred is None else len(pred)
    res = {}
    for t in taus:
        m = match(pairs, t)
        tp = len(m)
        rec = tp / n_gt if n_gt else 0.0
        prec = tp / n_pred if n_pred else 0.0
        res[t] = dict(tp=tp, n_gt=n_gt, n_pred=n_pred, recall=rec,
                      precision=prec,
                      f1=2 * prec * rec / (prec + rec) if (prec + rec) else 0.0,
                      matches=m)
    return res


def polygonize(prob, transform, crs, thresh, min_area=MIN_AREA_M2):
    """Threshold -> connected components -> one scored polygon per blob."""
    from shapely.geometry import shape
    mask = prob >= thresh
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
    if not rows:
        return gpd.GeoDataFrame({"score": []}, geometry=[], crs=crs)
    return gpd.GeoDataFrame(rows, crs=crs)


def main() -> int:
    print("== 9t instance metrics: matched extent + class, val-frozen thresholds ==")

    blocks = gpd.read_file(NINE_T / "blocks_unified_9t.gpkg").to_crs(CRS)
    blocks = blocks.set_index("block_id")
    tile_area = blocks.geometry.union_all().area

    def footprint(manifest, split):
        ids = sorted(manifest.loc[manifest.split == split, "block_id"].unique())
        sel = blocks.loc[blocks.index.intersection(ids)]
        return sel.geometry.union_all()

    # ---- ground truth ----
    gts, foot = {}, {}
    pits = gpd.read_file(ANN_GPKG, layer="pit_inside").to_crs(CRS)
    pits = pits.rename(columns={"pit_id": "inst_id"})[["inst_id", "geometry"]]
    pm = pd.read_csv(NINE_T / "pit_dataset_manifest.csv")
    gts["pit"] = pits.merge(pm[["pit_id", "split"]].rename(
        columns={"pit_id": "inst_id"}), on="inst_id", how="inner")
    foot["pit"] = {s: footprint(pm, s) for s in ("val", "test")}

    pads = gpd.read_file(ANN_GPKG, layer="plat").to_crs(CRS)
    pads = pads.rename(columns={"plat_id": "inst_id"})[["inst_id", "geometry"]]
    am = pd.read_csv(NINE_T / "plat_dataset_manifest.csv")
    gts["pad"] = pads.merge(am[["plat_id", "split"]].rename(
        columns={"plat_id": "inst_id"}), on="inst_id", how="inner")
    foot["pad"] = {s: footprint(am, s) for s in ("val", "test")}

    for k in ("pit", "pad"):
        g = gts[k]
        for s in ("val", "test"):
            gs = g[g.split == s]
            inb = int(gs.geometry.centroid.within(foot[k][s]).sum())
            print(f"  GT {k} {s}: {len(gs)} instances, "
                  f"{100 * foot[k][s].area / tile_area:.1f}% of tile, "
                  f"{inb}/{len(gs)} inside footprint")

    # ---- assemble every model's predictions ----
    preds = {}
    for name, (kind, path) in INSTANCE_MODELS.items():
        if not path.exists():
            print(f"  !! {name} missing"); continue
        p = gpd.read_file(path).to_crs(CRS)
        preds[name] = (kind, "score", p)
    for name, (kind, path) in UNET_PROB.items():
        if not path.exists():
            print(f"  !! {name} missing"); continue
        with rasterio.open(path) as r:
            prob = r.read(1).astype(np.float32)
            if r.nodata is not None:
                prob = np.where(prob == r.nodata, 0.0, prob)
            tf, crs = r.transform, r.crs
        preds[name] = (kind, "prob", (prob, tf, crs))

    rows, sweep_rows, summary = [], [], {}
    for name, (kind, mode, payload) in preds.items():
        gt_all = gts[kind]
        gt_val = gt_all[gt_all.split == "val"]
        gt_test = gt_all[gt_all.split == "test"]

        def restrict(p, split):
            """Detections inside this task's split footprint, matching class."""
            if p is None or len(p) == 0:
                return p
            q = p[p.geometry.centroid.within(foot[kind][split])]
            if kind == "pit" and "cls" in q.columns:
                q = q[q["cls"] == "floor"]
            return q

        # ---- select the threshold on VAL ----
        best = None
        for th in (SCORE_THRESHOLDS if mode == "score" else UNET_THRESHOLDS):
            if mode == "score":
                cand = payload[payload["score"].astype(float) >= th]
            else:
                prob, tf, pcrs = payload
                cand = polygonize(prob, tf, pcrs, th)
            v = score(gt_val, restrict(cand, "val"), taus=(SEL_TAU,))[SEL_TAU]
            sweep_rows.append(dict(model=name, kind=kind, threshold=float(th),
                                   n_det_val=v["n_pred"], tp=v["tp"],
                                   recall=v["recall"], precision=v["precision"],
                                   f1=v["f1"]))
            if best is None or v["f1"] > best[1]:
                best = (float(th), v["f1"], cand)
        th, val_f1, cand = best
        print(f"\n  {name} ({kind}, {mode}): val-selected threshold {th:.2f} "
              f"(val F1@{SEL_TAU} {val_f1:.3f})")

        # ---- freeze, score once on TEST ----
        full = payload if mode == "score" else polygonize(*payload, 0.5)
        as_is = score(gt_test, full)                      # leaderboard protocol
        kept = restrict(cand, "test")
        fixed = score(gt_test, kept)
        print(f"    detections: {len(full)} raw -> {len(kept)} scored "
              f"(test footprint + class + thr)")
        for t in TAUS:
            a, f = as_is[t], fixed[t]
            print(f"    IoU {t:.2f}  R {a['recall']:.3f}->{f['recall']:.3f}   "
                  f"P {a['precision']:.3f}->{f['precision']:.3f}   "
                  f"F1 {a['f1']:.3f}->{f['f1']:.3f}")
            rows.append(dict(model=name, kind=kind, mode=mode, iou=t,
                             threshold=th, n_gt_test=len(gt_test),
                             n_det_raw=len(full), n_det_scored=len(kept),
                             tp=f["tp"],
                             recall_as_is=a["recall"], recall=f["recall"],
                             precision_as_is=a["precision"],
                             precision=f["precision"],
                             f1_as_is=a["f1"], f1=f["f1"]))

        # ---- label TP/FP/FN and export for QGIS ----
        m = fixed[SEL_TAU]["matches"]
        if len(kept):
            k2 = kept.reset_index(drop=True).copy()
            k2["verdict"] = "FP"
            k2.loc[list(m.values()), "verdict"] = "TP"
            k2["model"] = name
            k2.to_file(OUT / f"scored_{name}.gpkg", layer="detections",
                       driver="GPKG")
        g2 = gt_test.reset_index(drop=True).copy()
        g2["verdict"] = "missed"
        g2.loc[list(m.keys()), "verdict"] = "matched"
        g2["model"] = name
        g2.to_file(OUT / f"scored_{name}.gpkg", layer="gt", driver="GPKG")
        summary[name] = dict(kind=kind, threshold=th, val_f1=val_f1,
                             test=dict(precision=fixed[SEL_TAU]["precision"],
                                       recall=fixed[SEL_TAU]["recall"],
                                       f1=fixed[SEL_TAU]["f1"]))
        if mode == "prob":
            cand.to_file(OUT / f"unet_instances_{kind}.gpkg",
                         layer="instances", driver="GPKG")

    df = pd.DataFrame(rows); df.to_csv(OUT / "metrics_9t.csv", index=False)
    sw = pd.DataFrame(sweep_rows)
    sw.to_csv(OUT / "val_threshold_sweep_9t.csv", index=False)
    print(f"\n  wrote {OUT / 'metrics_9t.csv'}")
    print(f"  wrote {OUT / 'val_threshold_sweep_9t.csv'}")

    # ---- figure 1: precision before/after + val sweeps ----
    d3 = df[df.iou == SEL_TAU].sort_values("kind")
    fig, ax = plt.subplots(1, 2, figsize=(16, 5.6))
    x = np.arange(len(d3))
    ax[0].bar(x - 0.2, d3.precision_as_is, 0.4, color="#bbbbbb",
              label="as reported (whole-tile denominator)")
    ax[0].bar(x + 0.2, d3.precision, 0.4, color="#d7191c",
              label="matched extent + class + val threshold")
    for i, (a, b) in enumerate(zip(d3.precision_as_is, d3.precision)):
        ax[0].text(i - 0.2, a, f"{a:.3f}", ha="center", va="bottom", fontsize=8)
        ax[0].text(i + 0.2, b, f"{b:.3f}", ha="center", va="bottom", fontsize=8)
    ax[0].set_xticks(x); ax[0].set_xticklabels(d3.model, rotation=20, ha="right")
    ax[0].set_ylabel(f"precision @ IoU {SEL_TAU}"); ax[0].legend(fontsize=8)
    ax[0].set_title("Precision was a measurement artifact")
    for m_, g in sw.groupby("model"):
        ax[1].plot(g.threshold, g.f1, marker="o", ms=3, label=m_)
    ax[1].set_xlabel("threshold"); ax[1].set_ylabel(f"VAL F1 @ IoU {SEL_TAU}")
    ax[1].legend(fontsize=8); ax[1].grid(alpha=0.3)
    ax[1].set_title("Threshold selected on val, then frozen")
    fig.tight_layout()
    fig.savefig(OUT / "precision_reeval_9t.png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'precision_reeval_9t.png'}")

    # ---- figure 2: TP/FP/FN on the ground ----
    with rasterio.open(NINE_T / "hillshade_9t_05.tif") as r:
        hs = r.read(1); hs_ext = (r.bounds.left, r.bounds.right,
                                  r.bounds.bottom, r.bounds.top)
    names = list(preds.keys())
    fig, axs = plt.subplots(2, 3, figsize=(19, 13))
    for a, name in zip(axs.ravel(), names):
        kind = preds[name][0]
        gt_test = gts[kind][gts[kind].split == "test"]
        # densest test block for this task
        blk = blocks.loc[blocks.index.intersection(
            sorted((pm if kind == "pit" else am)
                   .loc[lambda d: d.split == "test", "block_id"].unique()))]
        cnt = [(gt_test.geometry.centroid.within(gm).sum(), gm)
               for gm in blk.geometry]
        gm = max(cnt, key=lambda c: c[0])[1]
        x0, y0, x1, y1 = gm.bounds
        a.imshow(hs, cmap="gray", extent=hs_ext, alpha=0.9)
        try:
            d = gpd.read_file(OUT / f"scored_{name}.gpkg", layer="detections")
            d[d.verdict == "FP"].plot(ax=a, facecolor="none",
                                      edgecolor="#d7191c", linewidth=1.1)
            d[d.verdict == "TP"].plot(ax=a, facecolor="none",
                                      edgecolor="#1a9641", linewidth=1.6)
        except Exception:
            pass
        g = gpd.read_file(OUT / f"scored_{name}.gpkg", layer="gt")
        g[g.verdict == "missed"].plot(ax=a, facecolor="none",
                                      edgecolor="#fdae61", linewidth=2.2,
                                      linestyle="--")
        r_ = summary[name]["test"]
        a.set_xlim(x0, x1); a.set_ylim(y0, y1); a.set_aspect("equal")
        a.set_xticks([]); a.set_yticks([])
        a.set_title(f"{name}  thr={summary[name]['threshold']:.2f}\n"
                    f"P {r_['precision']:.2f}  R {r_['recall']:.2f}  "
                    f"F1 {r_['f1']:.2f}", fontsize=10)
    for a in axs.ravel()[len(names):]:
        a.axis("off")
    axs.ravel()[0].legend(handles=[
        Patch(facecolor="none", edgecolor="#1a9641", label="TP detection"),
        Patch(facecolor="none", edgecolor="#d7191c", label="FP detection"),
        Patch(facecolor="none", edgecolor="#fdae61", label="missed GT (FN)")],
        loc="upper left", fontsize=8, framealpha=0.9)
    fig.suptitle("9t densest test block: detections after extent + class "
                 "matching and val-frozen thresholds", fontsize=13)
    fig.tight_layout()
    fig.savefig(OUT / "detections_map_9t.png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"  wrote {OUT / 'detections_map_9t.png'}")

    (OUT / "_reeval_9t.json").write_text(json.dumps(summary, indent=2))
    print(f"  wrote {OUT / '_reeval_9t.json'}")
    print("\n  final (IoU 0.3, val-frozen threshold, matched extent + class):")
    for _, r in d3.iterrows():
        print(f"    {r.model:18s} thr {r.threshold:.2f}  "
              f"P {r.precision:.3f}  R {r.recall:.3f}  F1 {r.f1:.3f}   "
              f"(was P {r.precision_as_is:.3f} F1 {r.f1_as_is:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
