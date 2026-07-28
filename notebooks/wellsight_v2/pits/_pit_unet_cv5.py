"""5-fold cross-validation of the pit U-Net on 9t.

WHY
---
Every pit number we quote rests on 65 test pits from ONE split. That is small
enough that a 3-point difference is noise, and it invites the fair objection
that the split was lucky. This trains five models, each holding out a different
fifth of the tile, so:

  * ALL 426 hand-drawn pits get scored, each by a model that never saw it
  * the spread across folds says whether a number is stable or noise

No new annotation. No change to the architecture, loss, channels or schedule.

DESIGN
------
Split by BLOCK, never by well. Training patches are 128 m with 30 m jitter, so a
patch centred on a training pit can physically overlap a neighbouring held-out
pit. The 12x12 grid of 375 m blocks (111 of which contain pits) is the unit.

Folds are balanced on PIT COUNT, not block count, because pits cluster on pads.
Same greedy-deficit assignment as `_build_pit_dataset.py`, different seed.

Per fold k:
  held-out  = fold k blocks                          (~20% of pits)
  inner val = 20% of the remaining blocks            (~16% of pits)
  train     = the rest                               (~64% of pits)
The held-out fold NEVER influences its own threshold or its own best epoch.
That is what makes the number defensible.

THRESHOLD SELECTION -- BOTH OBJECTIVES, DECLARED UP FRONT
---------------------------------------------------------
The probability threshold is selected on the inner val split, twice:
  F1  weights recall and precision equally
  F2  weights recall 4x precision -- a missed well costs more than a false alarm
Both are frozen and scored once on the held-out fold. Reporting both, chosen
before seeing any held-out data, is the opposite of cherry-picking. Picking
whichever looks better afterwards would not be.

Also reported, threshold-free, so no cutoff has to be defended at all:
  the FULL recovery curve over probability thresholds, per fold.

SCORING
-------
  recall@IoU     predicted floor vs annotated floor (`pit_inside`), greedy 1:1
  containment    predicted floor centroid inside the annotated rim
                 (`pit_outside`) -- LOCATING a pit, not delineating it
  precision      predictions restricted to the held-out fold's block footprint,
                 the extent-matching fix from `_reeval_instance_precision_9t.py`

KNOWN LIMITATION, STATED NOT HIDDEN
------------------------------------
Channel normalisation stats (`feature_stats.json`, 7 means + 7 sds) were
computed once over the original train blocks and are reused for every fold. They
are not recomputed per fold. This leaks 14 global numbers into each fold. The
effect is negligible but it is not zero, and it is cheaper to disclose than to
re-derive.

Every fold is still 9t -- one landscape, one survey, one canopy condition. This
measures whether our number is STABLE. It does not measure whether it TRANSFERS.

Run:
  python notebooks/wellsight_v2/pits/_pit_unet_cv5.py --folds 5 --epochs 40
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import torch
from rasterio.features import rasterize as _rasterize, shapes
from scipy import ndimage as ndi
from shapely.geometry import shape
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T
from _dl import (DEFAULT_CHANNELS, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

ROOT = Path(__file__).resolve().parents[3]
ANN_GPKG = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_pit_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "pit_dataset_manifest.csv"
OUTDIR = DERIV_9T / "pit_unet_cv5"
OUTDIR.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
PATCH = 256
OVERLAP = 64
N_CLASSES = 3
JITTER_M = 30.0
FOCAL_ALPHA = (0.05, 0.475, 0.475)
FOCAL_GAMMA = 2.0
MIN_AREA_M2 = 4.0
INNER_VAL_FRAC = 0.20
CV_SEED = 20260727
PROB_GRID = np.round(np.arange(0.10, 0.86, 0.05), 2)
REPORT_TAUS = (0.3, 0.5)
SEL_TAU = 0.3                      # IoU at which thresholds are selected
SCORE_BUF_M = 40.0                 # buffer on the scored footprint, >> a pit


# ---------------------------------------------------------------------------
# folds
# ---------------------------------------------------------------------------
def assign_folds(blocks_n: pd.DataFrame, k: int, seed: int) -> dict[int, int]:
    """Greedy-deficit assignment of blocks to k folds, balanced on pit count."""
    shuffled = blocks_n.sample(frac=1, random_state=seed).values
    total = int(shuffled[:, 1].sum())
    quota = [total / k] * k
    got = [0] * k
    out = {}
    for bid, n in shuffled:
        f = int(np.argmax([quota[i] - got[i] for i in range(k)]))
        out[int(bid)] = f
        got[f] += int(n)
    return out


# ---------------------------------------------------------------------------
# scoring
# ---------------------------------------------------------------------------
def polygonize(prob, transform, crs, thr, min_area=MIN_AREA_M2):
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
    """Greedy 1:1 IoU matching. Returns {tau: dict(tp, recall, precision, f1)}."""
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
        rec = tp / n_gt if n_gt else 0.0
        pre = tp / n_pred if n_pred else 0.0
        res[t] = dict(tp=tp, n_gt=n_gt, n_pred=n_pred, recall=rec,
                      precision=pre,
                      f1=2 * pre * rec / (pre + rec) if (pre + rec) else 0.0,
                      f2=5 * pre * rec / (4 * pre + rec) if (4 * pre + rec) else 0.0)
    return res


def containment(rims, pred):
    """Fraction of rims holding at least one prediction centroid."""
    if not len(rims):
        return 0.0, 0
    if not len(pred):
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--only-folds", type=str, default="",
                    help="comma list, e.g. '4'. Default: all folds.")
    args = ap.parse_args()
    K = args.folds
    want = ({int(x) for x in args.only_folds.split(",") if x.strip() != ""}
            if args.only_folds else set(range(K)))

    print(f"== pit U-Net {K}-fold cross-validation on 9t ==\n")

    man = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks").to_crs(CRS)
    n_per = man.groupby("block_id").size().rename("n_pits").reset_index()
    fold_of = assign_folds(n_per[["block_id", "n_pits"]], K, CV_SEED)
    man["fold"] = man.block_id.map(fold_of)
    blocks["fold"] = blocks.block_id.map(fold_of)

    print(f"  {len(man)} pits across {man.block_id.nunique()} pit-bearing blocks")
    for f in range(K):
        sub = man[man.fold == f]
        print(f"    fold {f}: {sub.block_id.nunique():3d} blocks  {len(sub):4d} pits")
    print()

    # ground truth geometry
    floors = gpd.read_file(ANN_GPKG, layer="pit_inside").to_crs(CRS)
    floors = floors[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
    floors = floors.merge(man[["pit_id", "fold"]], on="pit_id", how="inner")
    rims = gpd.read_file(ANN_GPKG, layer="pit_outside").to_crs(CRS)
    rims = rims[["pit_id", "geometry"]].dissolve(by="pit_id").reset_index()
    rims = rims.merge(man[["pit_id", "fold"]], on="pit_id", how="inner")

    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    with rasterio.open(FEATURES) as r:
        tf = r.transform
        rcrs = r.crs

    t_start = time.time()

    # Carry forward rows for folds we are NOT re-running, so a resumed partial
    # run still writes complete CSVs instead of clobbering earlier folds.
    fold_csv = OUTDIR / "pit_cv5_per_fold_9t.csv"
    curve_csv = OUTDIR / "pit_cv5_recovery_curve_9t.csv"

    def _carry(path):
        if not path.exists():
            return []
        old = pd.read_csv(path)
        return old[~old.fold.isin(want)].to_dict("records")

    fold_rows, curve_rows = _carry(fold_csv), _carry(curve_csv)
    if fold_rows or curve_rows:
        print(f"  carried forward {len(fold_rows)} fold rows / "
              f"{len(curve_rows)} curve rows from previous run\n")

    def flush():
        pd.DataFrame(fold_rows).sort_values(["fold", "objective"]).to_csv(
            fold_csv, index=False)
        pd.DataFrame(curve_rows).sort_values(["fold", "prob_threshold"]).to_csv(
            curve_csv, index=False)

    for k in range(K):
        if k not in want:
            continue
        print(f"{'='*70}\nFOLD {k}\n{'='*70}")
        fd = OUTDIR / f"fold{k}"
        fd.mkdir(parents=True, exist_ok=True)
        prob_tif = fd / f"pit_prob_floor_cvfold{k}_9t_05.tif"

        held_blocks = sorted(man.loc[man.fold == k, "block_id"].unique())
        rest = sorted(set(man.block_id.unique()) - set(held_blocks))
        # Seed per fold, not once before the loop. A single shared RNG makes the
        # inner-val draw depend on how many folds ran before it in the process,
        # so --only-folds silently gives a different split than a full run.
        rng = np.random.default_rng(CV_SEED + 1000 * k)
        rest_shuf = list(rng.permutation(rest))
        n_val = max(1, int(round(INNER_VAL_FRAC * len(rest_shuf))))
        val_blocks = sorted(rest_shuf[:n_val])
        tr_blocks = sorted(rest_shuf[n_val:])

        def pits_in(bids):
            return man.loc[man.block_id.isin(bids),
                           ["centroid_x", "centroid_y"]].to_numpy()

        def bounds_of(bids):
            return np.array([g.bounds for g in
                             blocks.loc[blocks.block_id.isin(bids)].geometry])

        tr_pits, va_pits = pits_in(tr_blocks), pits_in(val_blocks)
        print(f"  train {len(tr_pits)} pits / {len(tr_blocks)} blocks   "
              f"inner-val {len(va_pits)} / {len(val_blocks)}   "
              f"HELD-OUT {int((man.fold == k).sum())} / {len(held_blocks)}")

        tr_ds = CenteredPatchSampler(
            feat_path=FEATURES, lbl_path=LABELS,
            policies=[("pit", tr_pits, JITTER_M)], block_bounds=bounds_of(tr_blocks),
            transform=tf, mu=mu, sd=sd, patch=PATCH, augment=True, seed=100 + k)
        va_ds = CenteredPatchSampler(
            feat_path=FEATURES, lbl_path=LABELS,
            policies=[("pit", va_pits, JITTER_M)], block_bounds=bounds_of(val_blocks),
            transform=tf, mu=mu, sd=sd, patch=PATCH, augment=False, seed=200 + k)

        # Resumable: a finished checkpoint or prob raster is reused as-is. Both
        # are deterministic products of a fold that already ran, so re-deriving
        # them would change nothing and costs ~9 min of GPU each.
        model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
        tlog = fd / "train_log.csv"
        n_done = len(pd.read_csv(tlog)) if tlog.exists() else 0
        if (fd / "best.pt").exists() and n_done >= args.epochs:
            print(f"  reusing existing checkpoint {fd / 'best.pt'} "
                  f"({n_done} epochs)")
        else:
            if (fd / "best.pt").exists():
                print(f"  DISCARDING partial checkpoint in {fd.name}: "
                      f"{n_done}/{args.epochs} epochs -- retraining from scratch")
            train_loop(
                model=model,
                train_loader=DataLoader(tr_ds, batch_size=args.batch, shuffle=True,
                                        num_workers=args.workers, pin_memory=True),
                val_loader=DataLoader(va_ds, batch_size=args.batch, shuffle=False,
                                      num_workers=args.workers, pin_memory=True),
                loss_fn=FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA),
                epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES, out_dir=fd,
                checkpoint_extra={"mu": mu, "sd": sd, "fold": k,
                                  "channels": list(DEFAULT_CHANNELS), "patch": PATCH,
                                  "held_out_blocks": held_blocks},
                score=lambda iou: float(np.nanmean(iou[1:])),
                extra_iou_names=("bg", "floor", "wall"))

        if prob_tif.exists():
            print(f"  reusing existing probability raster {prob_tif}")
            with rasterio.open(prob_tif) as r:
                floor = r.read(1).astype(np.float32)
        else:
            ck = torch.load(fd / "best.pt", map_location="cpu", weights_only=False)
            model.load_state_dict(ck["model"] if "model" in ck else ck["state_dict"])
            prob, _, prof = predict_full_tile(model, FEATURES, mu, sd, patch=PATCH,
                                              overlap=OVERLAP, n_classes=N_CLASSES,
                                              batch=args.batch)
            floor = prob[1].astype(np.float32)
            del prob
            with rasterio.open(prob_tif, "w",
                               driver="GTiff", height=floor.shape[0],
                               width=floor.shape[1], count=1, dtype="float32",
                               crs=prof["crs"], transform=prof["transform"],
                               nodata=-1.0, compress="deflate", predictor=2,
                               tiled=True, BIGTIFF="YES") as d:
                d.write(floor, 1)

        gt_val = floors[floors.pit_id.isin(man.loc[man.block_id.isin(val_blocks),
                                                   "pit_id"])]
        gt_held = floors[floors.fold == k]
        rim_held = rims[rims.fold == k]
        foot_val = blocks.loc[blocks.block_id.isin(val_blocks)].geometry.union_all()
        foot_held = blocks.loc[blocks.block_id.isin(held_blocks)].geometry.union_all()

        # Only predictions whose centroid falls in the val or held-out footprint
        # are ever scored, so zero the rest before polygonizing. Buffered by
        # SCORE_BUF_M (>> a pit) so no scored blob is clipped mid-object. This is
        # a large speedup and changes no scored number.
        keep = _rasterize(
            [(g, 1) for g in
             [foot_val.buffer(SCORE_BUF_M), foot_held.buffer(SCORE_BUF_M)]],
            out_shape=floor.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        floor_scored = np.where(keep, floor, 0.0).astype(np.float32)
        print(f"  scoring mask covers {100*keep.mean():.1f}% of tile")

        # ---- sweep once, reuse for selection AND for the reported curve ----
        val_by_thr, held_by_thr = {}, {}
        for pt in PROB_GRID:
            t0 = time.time()
            allp = polygonize(floor_scored, tf, rcrs, float(pt))
            if len(allp):
                cen = allp.geometry.centroid
                val_by_thr[float(pt)] = match_scores(
                    gt_val, allp[cen.within(foot_val)].reset_index(drop=True))
                hp = allp[cen.within(foot_held)].reset_index(drop=True)
            else:
                val_by_thr[float(pt)] = match_scores(gt_val, allp)
                hp = allp
            held_by_thr[float(pt)] = (match_scores(gt_held, hp),
                                      containment(rim_held, hp), len(hp))
            m, c, npred = held_by_thr[float(pt)]
            print(f"    thr {pt:.2f}: {len(allp):5d} poly in mask, "
                  f"{npred:4d} in held-out, recall@0.3 {m[0.3]['recall']:.3f} "
                  f"({time.time()-t0:.0f}s)")
            curve_rows.append(dict(
                fold=k, prob_threshold=float(pt), n_pred_heldout=npred,
                n_heldout=len(gt_held),
                recall_iou30=m[0.3]["recall"], precision_iou30=m[0.3]["precision"],
                f1_iou30=m[0.3]["f1"], recall_iou50=m[0.5]["recall"],
                containment=c[0], containment_hits=c[1], n_rims=len(rim_held)))

        for obj in ("f1", "f2"):
            best_pt = max(val_by_thr, key=lambda t: val_by_thr[t][SEL_TAU][obj])
            m, c, npred = held_by_thr[best_pt]
            fold_rows.append(dict(
                fold=k, objective=obj, prob_threshold=best_pt,
                val_score=val_by_thr[best_pt][SEL_TAU][obj],
                n_heldout=len(gt_held), n_pred_heldout=npred,
                recall_iou30=m[0.3]["recall"], precision_iou30=m[0.3]["precision"],
                f1_iou30=m[0.3]["f1"], recall_iou50=m[0.5]["recall"],
                containment=c[0], containment_hits=c[1], n_rims=len(rim_held)))
            print(f"  [{obj.upper()}-selected thr {best_pt:.2f}]  held-out "
                  f"recall@0.3 {m[0.3]['recall']:.3f}  P {m[0.3]['precision']:.3f}"
                  f"  recall@0.5 {m[0.5]['recall']:.3f}  containment "
                  f"{c[0]:.3f} ({c[1]}/{len(rim_held)})")

        # Write after EVERY fold. The first run of this script lost four folds of
        # completed work when fold 4 died, because the CSVs were only written
        # after the loop.
        flush()
        print(f"  flushed results through fold {k} -> {fold_csv.name}")

        del model, floor, floor_scored, keep
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"  fold {k} done, {(time.time()-t_start)/60:.1f} min elapsed\n")

    fdf = pd.DataFrame(fold_rows)
    cdf = pd.DataFrame(curve_rows)
    flush()
    man[["pit_id", "block_id", "fold"]].to_csv(
        OUTDIR / "pit_cv5_fold_assignment_9t.csv", index=False)

    print(f"\n{'='*70}\nPOOLED RESULT ({K} folds, all {len(man)} pits scored once "
          f"by a model that never saw them)\n{'='*70}")
    for obj in ("f1", "f2"):
        g = fdf[fdf.objective == obj]
        tot_gt = g.n_heldout.sum()
        pooled_r = (g.recall_iou30 * g.n_heldout).sum() / tot_gt
        pooled_c = (g.containment * g.n_rims).sum() / g.n_rims.sum()
        pooled_p = (g.precision_iou30 * g.n_pred_heldout).sum() / g.n_pred_heldout.sum()
        print(f"\n  threshold selected on inner val by {obj.upper()}:")
        print(f"    prob thresholds chosen: {sorted(g.prob_threshold.tolist())}")
        print(f"    recall @ IoU 0.3   {pooled_r:.3f}   "
              f"per-fold {g.recall_iou30.min():.3f}-{g.recall_iou30.max():.3f}  "
              f"(sd {g.recall_iou30.std():.3f})")
        print(f"    precision @ IoU 0.3 {pooled_p:.3f}   "
              f"per-fold {g.precision_iou30.min():.3f}-{g.precision_iou30.max():.3f}")
        print(f"    recall @ IoU 0.5   {(g.recall_iou50*g.n_heldout).sum()/tot_gt:.3f}   "
              f"per-fold {g.recall_iou50.min():.3f}-{g.recall_iou50.max():.3f}")
        print(f"    containment        {pooled_c:.3f}   "
              f"per-fold {g.containment.min():.3f}-{g.containment.max():.3f}  "
              f"({int(g.containment_hits.sum())}/{int(g.n_rims.sum())} rims)")

    print(f"\n  wrote {OUTDIR / 'pit_cv5_per_fold_9t.csv'}")
    print(f"  wrote {OUTDIR / 'pit_cv5_recovery_curve_9t.csv'}")
    print(f"  wrote {OUTDIR / 'pit_cv5_fold_assignment_9t.csv'}")
    print(f"  total {(time.time()-t_start)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
