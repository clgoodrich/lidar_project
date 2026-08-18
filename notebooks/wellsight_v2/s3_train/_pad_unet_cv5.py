"""5-fold cross-validation of the pad (plat) U-Net on 9t.

WHY
---
Direct companion to `pits/_pit_unet_cv5.py`. Every pad number we quote rests on
93 test pads from ONE split. That is small enough that a 3-point difference is
noise, and it invites the fair objection that the split was lucky. This trains
five models, each holding out a different fifth of the tile, so:

  * ALL 650 in-tile hand-drawn pads get scored, each by a model that never saw it
  * the spread across folds says whether a number is stable or noise

No new annotation. No change to the architecture, loss, channels or schedule.
Parameters are copied verbatim from `_plat_unet.py` (patch 384, jitter 40 m,
2 classes, focal alpha 0.15/0.85) so this measures the split, not a new model.

DESIGN
------
Split by BLOCK, never by pad. Training patches are 384 px (192 m) with 40 m
jitter, so a patch centred on a training pad can physically overlap a
neighbouring held-out pad. The block is the unit.

Folds are balanced on PAD COUNT, not block count. Same greedy-deficit assignment
and same seed as the pit CV, so the two runs are argued the same way.

Per fold k:
  held-out  = fold k blocks                          (~20% of pads)
  inner val = 20% of the remaining blocks            (~16% of pads)
  train     = the rest                               (~64% of pads)
The held-out fold NEVER influences its own threshold or its own best epoch.

THRESHOLD SELECTION -- BOTH OBJECTIVES, DECLARED UP FRONT
---------------------------------------------------------
Selected on the inner val split, twice:
  F1  weights recall and precision equally
  F2  weights recall 4x precision -- a missed pad costs more than a false alarm
Both are frozen and scored once on the held-out fold. Reporting both, chosen
before seeing any held-out data, is the opposite of cherry-picking.

Also reported, threshold-free: the FULL recovery curve over probability
thresholds, per fold.

SCORING
-------
  recall@IoU     predicted pad vs annotated pad (`plat` layer), greedy 1:1
  locate         annotated pad containing >=1 predicted centroid -- LOCATING a
                 pad, not delineating it. This is the pad analogue of the pit
                 rim-containment metric. Pads have no inside/outside pair, so
                 the pad polygon itself is the target.
  precision      predictions restricted to the held-out fold's block footprint

Ground truth is hand-drawn annotation only. No state well coordinate is used.

KNOWN LIMITATION, STATED NOT HIDDEN
------------------------------------
Channel normalisation stats (`feature_stats.json`) are computed once over the
original train blocks and reused for every fold, leaking 14 global numbers into
each. Same disclosure as the pit CV.

Every fold is still 9t -- one landscape, one survey, one canopy condition. This
measures whether our number is STABLE. It does not measure whether it TRANSFERS.

Run:
  python notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py --folds 5 --epochs 40
  python notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py --only-folds 3,4
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
import torch
from rasterio.features import rasterize as _rasterize, shapes
from scipy import ndimage as ndi
from shapely.geometry import shape
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, path_for, read_layer, normalize_ids
from _dl import (DEFAULT_CHANNELS, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

ROOT = Path(__file__).resolve().parents[3]
ANN_GPKG = path_for("truth") / "annotations_proj.gpkg"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_plat_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "plat_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "plat_dataset_manifest.csv"
OUTDIR = path_for("models") / "pad" / "unet_cv5"
OUTDIR.mkdir(parents=True, exist_ok=True)

CRS = "EPSG:6346"
PATCH = 384                        # plats are bigger than pits -> more context
OVERLAP = 96
N_CLASSES = 2                      # bg, plat
JITTER_M = 40.0
FOCAL_ALPHA = (0.15, 0.85)
FOCAL_GAMMA = 2.0
MIN_AREA_M2 = 100.0                # smallest annotated pad is 260 m2
INNER_VAL_FRAC = 0.20
CV_SEED = 20260727                 # same seed as the pit CV
PROB_GRID = np.round(np.arange(0.10, 0.86, 0.05), 2)
REPORT_TAUS = (0.3, 0.5)
SEL_TAU = 0.3                      # IoU at which thresholds are selected
SCORE_BUF_M = 80.0                 # buffer on the scored footprint, >> a pad


def assign_folds(blocks_n: pd.DataFrame, k: int, seed: int) -> dict[int, int]:
    """Greedy-deficit assignment of blocks to k folds, balanced on pad count."""
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


def locate_rate(gt, pred):
    """Fraction of annotated pads holding at least one prediction centroid."""
    if not len(gt) or not len(pred):
        return 0.0, 0
    hits = 0
    sidx = pred.sindex
    cents = pred.geometry.centroid
    for r in gt.itertuples():
        for pj in sidx.intersection(r.geometry.bounds):
            if r.geometry.contains(cents.iloc[pj]):
                hits += 1
                break
    return hits / len(gt), hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)   # patch 384 -> smaller batch
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--only-folds", type=str, default="",
                    help="comma list, e.g. '4'. Default: all folds.")
    args = ap.parse_args()
    K = args.folds
    want = ({int(x) for x in args.only_folds.split(",") if x.strip() != ""}
            if args.only_folds else set(range(K)))

    print(f"== pad U-Net {K}-fold cross-validation on 9t ==\n")

    man = normalize_ids(pd.read_csv(MANIFEST))
    blocks = gpd.read_file(BLOCKS, layer="blocks").to_crs(CRS)
    n_per = man.groupby("block_id").size().rename("n_pads").reset_index()
    fold_of = assign_folds(n_per[["block_id", "n_pads"]], K, CV_SEED)
    man["fold"] = man.block_id.map(fold_of)
    blocks["fold"] = blocks.block_id.map(fold_of)

    print(f"  {len(man)} pads across {man.block_id.nunique()} pad-bearing blocks")
    for f in range(K):
        sub = man[man.fold == f]
        print(f"    fold {f}: {sub.block_id.nunique():3d} blocks  {len(sub):4d} pads")
    print()

    pads = read_layer(ANN_GPKG, "plat").to_crs(CRS)
    pads = pads[["pad_id", "geometry"]].dissolve(by="pad_id").reset_index()
    pads = pads.merge(man[["pad_id", "fold"]], on="pad_id", how="inner")
    print(f"  {len(pads)} annotated pad polygons matched to the manifest\n")

    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    with rasterio.open(FEATURES) as r:
        tf = r.transform
        rcrs = r.crs

    t_start = time.time()

    fold_csv = OUTDIR / "pad_cv5_per_fold_9t.csv"
    curve_csv = OUTDIR / "pad_cv5_recovery_curve_9t.csv"

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
        if fold_rows:
            pd.DataFrame(fold_rows).sort_values(["fold", "objective"]).to_csv(
                fold_csv, index=False)
        if curve_rows:
            pd.DataFrame(curve_rows).sort_values(["fold", "prob_threshold"]).to_csv(
                curve_csv, index=False)

    for k in range(K):
        if k not in want:
            continue
        print(f"{'='*70}\nFOLD {k}\n{'='*70}")
        fd = OUTDIR / f"fold{k}"
        fd.mkdir(parents=True, exist_ok=True)
        prob_tif = fd / f"pad_prob_cvfold{k}_9t_05.tif"

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

        def pads_in(bids):
            return man.loc[man.block_id.isin(bids),
                           ["centroid_x", "centroid_y"]].to_numpy()

        def bounds_of(bids):
            return np.array([g.bounds for g in
                             blocks.loc[blocks.block_id.isin(bids)].geometry])

        tr_pads, va_pads = pads_in(tr_blocks), pads_in(val_blocks)
        print(f"  train {len(tr_pads)} pads / {len(tr_blocks)} blocks   "
              f"inner-val {len(va_pads)} / {len(val_blocks)}   "
              f"HELD-OUT {int((man.fold == k).sum())} / {len(held_blocks)}")

        tr_ds = CenteredPatchSampler(
            feat_path=FEATURES, lbl_path=LABELS,
            policies=[("plat", tr_pads, JITTER_M)], block_bounds=bounds_of(tr_blocks),
            transform=tf, mu=mu, sd=sd, patch=PATCH, augment=True, seed=100 + k)
        va_ds = CenteredPatchSampler(
            feat_path=FEATURES, lbl_path=LABELS,
            policies=[("plat", va_pads, JITTER_M)], block_bounds=bounds_of(val_blocks),
            transform=tf, mu=mu, sd=sd, patch=PATCH, augment=False, seed=200 + k)

        # Resumable, but ONLY from a checkpoint whose fold ran the full schedule.
        # A run killed mid-fold leaves a best.pt from a partial schedule. Reusing
        # it would silently give this fold fewer epochs than its siblings, which
        # breaks the one thing cross-validation is for -- folds that differ only
        # in which blocks are held out. train_log.csv is the completion record.
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
                score=lambda iou: float(iou[1]),
                extra_iou_names=("bg", "plat"))

        if prob_tif.exists():
            print(f"  reusing existing probability raster {prob_tif}")
            with rasterio.open(prob_tif) as r:
                pad_prob = r.read(1).astype(np.float32)
        else:
            ck = torch.load(fd / "best.pt", map_location="cpu", weights_only=False)
            model.load_state_dict(ck["model"] if "model" in ck else ck["state_dict"])
            prob, _, prof = predict_full_tile(model, FEATURES, mu, sd, patch=PATCH,
                                              overlap=OVERLAP, n_classes=N_CLASSES,
                                              batch=args.batch)
            pad_prob = prob[1].astype(np.float32)
            del prob
            with rasterio.open(prob_tif, "w",
                               driver="GTiff", height=pad_prob.shape[0],
                               width=pad_prob.shape[1], count=1, dtype="float32",
                               crs=prof["crs"], transform=prof["transform"],
                               nodata=-1.0, compress="deflate", predictor=2,
                               tiled=True, BIGTIFF="YES") as d:
                d.write(pad_prob, 1)

        gt_val = pads[pads.pad_id.isin(man.loc[man.block_id.isin(val_blocks),
                                                "pad_id"])]
        gt_held = pads[pads.fold == k]
        foot_val = blocks.loc[blocks.block_id.isin(val_blocks)].geometry.union_all()
        foot_held = blocks.loc[blocks.block_id.isin(held_blocks)].geometry.union_all()

        keep = _rasterize(
            [(g, 1) for g in
             [foot_val.buffer(SCORE_BUF_M), foot_held.buffer(SCORE_BUF_M)]],
            out_shape=pad_prob.shape, transform=tf, fill=0, dtype="uint8").astype(bool)
        pad_scored = np.where(keep, pad_prob, 0.0).astype(np.float32)
        print(f"  scoring mask covers {100*keep.mean():.1f}% of tile")

        val_by_thr, held_by_thr = {}, {}
        for pt in PROB_GRID:
            t0 = time.time()
            allp = polygonize(pad_scored, tf, rcrs, float(pt))
            if len(allp):
                cen = allp.geometry.centroid
                val_by_thr[float(pt)] = match_scores(
                    gt_val, allp[cen.within(foot_val)].reset_index(drop=True))
                hp = allp[cen.within(foot_held)].reset_index(drop=True)
            else:
                val_by_thr[float(pt)] = match_scores(gt_val, allp)
                hp = allp
            held_by_thr[float(pt)] = (match_scores(gt_held, hp),
                                      locate_rate(gt_held, hp), len(hp))
            m, c, npred = held_by_thr[float(pt)]
            print(f"    thr {pt:.2f}: {len(allp):5d} poly in mask, "
                  f"{npred:4d} in held-out, recall@0.3 {m[0.3]['recall']:.3f} "
                  f"({time.time()-t0:.0f}s)")
            curve_rows.append(dict(
                fold=k, prob_threshold=float(pt), n_pred_heldout=npred,
                n_heldout=len(gt_held),
                recall_iou30=m[0.3]["recall"], precision_iou30=m[0.3]["precision"],
                f1_iou30=m[0.3]["f1"], recall_iou50=m[0.5]["recall"],
                locate=c[0], locate_hits=c[1]))

        for obj in ("f1", "f2"):
            best_pt = max(val_by_thr, key=lambda t: val_by_thr[t][SEL_TAU][obj])
            m, c, npred = held_by_thr[best_pt]
            fold_rows.append(dict(
                fold=k, objective=obj, prob_threshold=best_pt,
                val_score=val_by_thr[best_pt][SEL_TAU][obj],
                n_heldout=len(gt_held), n_pred_heldout=npred,
                recall_iou30=m[0.3]["recall"], precision_iou30=m[0.3]["precision"],
                f1_iou30=m[0.3]["f1"], recall_iou50=m[0.5]["recall"],
                locate=c[0], locate_hits=c[1]))
            print(f"  [{obj.upper()}-selected thr {best_pt:.2f}]  held-out "
                  f"recall@0.3 {m[0.3]['recall']:.3f}  P {m[0.3]['precision']:.3f}"
                  f"  recall@0.5 {m[0.5]['recall']:.3f}  locate "
                  f"{c[0]:.3f} ({c[1]}/{len(gt_held)})")

        flush()
        print(f"  flushed results through fold {k} -> {fold_csv.name}")

        del model, pad_prob, pad_scored, keep
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print(f"  fold {k} done, {(time.time()-t_start)/60:.1f} min elapsed\n")

    fdf = pd.DataFrame(fold_rows)
    flush()
    man[["pad_id", "block_id", "fold"]].to_csv(
        OUTDIR / "pad_cv5_fold_assignment_9t.csv", index=False)

    if fdf.empty:
        print("\n  no fold rows -- nothing to pool (dry check?)")
        return 0

    print(f"\n{'='*70}\nPOOLED RESULT ({K} folds, all {len(man)} pads scored once "
          f"by a model that never saw them)\n{'='*70}")
    for obj in ("f1", "f2"):
        g = fdf[fdf.objective == obj]
        tot_gt = g.n_heldout.sum()
        pooled_r = (g.recall_iou30 * g.n_heldout).sum() / tot_gt
        pooled_l = (g.locate * g.n_heldout).sum() / tot_gt
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
        print(f"    locate             {pooled_l:.3f}   "
              f"per-fold {g.locate.min():.3f}-{g.locate.max():.3f}  "
              f"({int(g.locate_hits.sum())}/{int(tot_gt)} pads)")

    print(f"\n  wrote {fold_csv}")
    print(f"  wrote {curve_csv}")
    print(f"  wrote {OUTDIR / 'pad_cv5_fold_assignment_9t.csv'}")
    print(f"  total {(time.time()-t_start)/60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
