"""Architecture comparison across all four 9t targets, on ONE 1 m grid.

WHY THIS SCRIPT EXISTS
----------------------
The leaderboard compares models that were trained on different splits, at
different resolutions, and scored with different metrics. That is fine for
tracking progress and useless for answering "which architecture is better".

This runs every architecture against every target with **one thing varying**:

    same grid        features_pit_9t_1m.tif, 4500 x 4500 @ 1 m
    same channels    CHANNELS_1M (roughness_5, not the DEFAULT_CHANNELS
                     roughness_11 mislabel -- see BACKLOG B5)
    same split       the unified block split, so a patch centred on a pad in a
                     "train" block can never overlap a pit "test" block
    same sampler     CenteredPatchSampler, patch 256, jitter 30 m, D4 aug
    same loss        FocalCE, gamma 2.0, per-target alpha held fixed across arms
    same schedule    epochs / lr / weight decay identical across arms
    same scoring     train_loop checkpoints on the target's positive-class IoU

Only ``--arch`` changes. Everything else is pinned.

WHY CROSS-VALIDATION IS NOT OPTIONAL HERE
-----------------------------------------
The ann712 pit CV5 run spans **0.810-0.911 recall across folds, sd 0.045**. The
July road sweep separated seven architecture variants by roughly 0.02-0.09. The
fold-to-fold noise is the same size as the effect being measured, so a
single-split table would rank architectures by which fold they drew. Every
number here is pooled over folds for that reason.

THE ARMS
--------
An ablation ladder, not a grab bag. Each arm differs from the one above it by
exactly one thing, so a difference is attributable:

    unet                    the incumbent. Custom 4-level U-Net, base=32, ~8 M
                            params. The control.
    r34_scratch             smp U-Net with a ResNet34 encoder, randomly
                            initialised. Isolates ARCHITECTURE.
    r34_imagenet            the same network with ImageNet encoder weights.
                            Against r34_scratch this isolates PRETRAINING.
    unetpp_r34_imagenet     U-Net++ with the same pretrained encoder. Against
                            r34_imagenet this isolates DENSE SKIP CONNECTIONS.

ImageNet weights expect 3 channels; smp adapts the first convolution to 7 by
repeating and rescaling. That is a real caveat for a DEM stack whose channels
are nothing like RGB, and it is exactly why r34_scratch is in the table.

TARGETS
-------
Three training runs, five reported classes. Pit interior/exterior come from one
3-class model; road/drainage come from one 3-class model. Training them
separately would measure the split, not the architecture.

    pit         labels_pit_9t_1m.tif    0 bg / 1 floor / 2 wall
    pad         labels_pad_9t_1m.tif    0 bg / 1 pad
    roaddrain   labels_road_9t_1m.tif   0 bg / 1 road / 2 drainage

Outputs
    data/9t/models/_arch_compare/1m/<target>/<arch>/fold<k>/
        best.pt, train_log.csv, fold_metrics.json
    data/9t/models/_arch_compare/1m/<target>/<arch>/pooled_metrics.json

Run
    python ..._arch_compare_9t_1m.py --target pit --arch unet --time-one-epoch
    python ..._arch_compare_9t_1m.py --target pit --arch unet --folds 5
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
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, normalize_ids, path_for  # noqa: E402
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet,  # noqa: E402
                 load_stats, train_loop)

FEATURES = DERIV_9T / "features_pit_9t_1m.tif"
STATS = DERIV_9T / "feature_stats_1m.json"
BLOCKS = DERIV_9T / "blocks_unified_9t.gpkg"
OUTROOT = path_for("models") / "_arch_compare" / "1m"

CHANNELS_1M = ("lrm_25", "lrm_5", "slope", "tpi_05",
               "openness_pos", "openness_neg", "roughness_5")

PATCH = 256
JITTER_M = 30.0
FOCAL_GAMMA = 2.0
WEIGHT_DECAY = 2e-4
CV_SEED = 42

#: Per-target configuration. ``alpha`` is copied from each target's existing
#: production trainer so the comparison inherits a tuned operating point rather
#: than inventing one; it is held identical across every arm.
TARGETS = {
    "pit": dict(
        labels="labels_pit_9t_1m.tif",
        manifest="pit_dataset_manifest_unified.csv",
        n_classes=3,
        alpha=(0.10, 0.72, 0.25),      # bg, floor(+), wall
        score_cls=1,
        iou_names=("bg", "floor", "wall"),
        xy=("centroid_x", "centroid_y"),
        kind_col=None,
    ),
    "pad": dict(
        labels="labels_pad_9t_1m.tif",
        manifest="pad_dataset_manifest_unified.csv",
        n_classes=2,
        alpha=(0.25, 0.75),            # bg, pad(+)
        score_cls=1,
        iou_names=("bg", "pad"),
        xy=("centroid_x", "centroid_y"),
        kind_col=None,
    ),
    "roaddrain": dict(
        labels="labels_road_9t_1m.tif",
        manifest="road_dataset_manifest_unified.csv",
        n_classes=3,
        alpha=(0.10, 0.72, 0.25),      # bg, road(+), drainage
        score_cls=1,
        iou_names=("bg", "road", "drainage"),
        xy=("mid_x", "mid_y"),
        kind_col="kind",
    ),
}


def build_model(arch: str, n_classes: int) -> torch.nn.Module:
    """One factory so every arm is constructed the same way."""
    if arch == "unet":
        return UNet(in_ch=len(CHANNELS_1M), n_classes=n_classes, base=32)

    import segmentation_models_pytorch as smp
    common = dict(encoder_name="resnet34", in_channels=len(CHANNELS_1M),
                  classes=n_classes)
    if arch == "r34_scratch":
        return smp.Unet(encoder_weights=None, **common)
    if arch == "r34_imagenet":
        return smp.Unet(encoder_weights="imagenet", **common)
    if arch == "unetpp_r34_imagenet":
        return smp.UnetPlusPlus(encoder_weights="imagenet", **common)
    raise SystemExit(f"unknown --arch {arch!r}")


ARCHS = ("unet", "r34_scratch", "r34_imagenet", "unetpp_r34_imagenet")


def assign_folds(block_ids: np.ndarray, counts: np.ndarray, k: int,
                 seed: int) -> dict:
    """Greedy-deficit fold assignment balanced on FEATURE count, not block count.

    Features cluster on pads, so balancing blocks would hand one fold twice the
    data. Same rule the production CV5 trainers use, so folds are comparable.
    """
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(block_ids))
    target = counts.sum() / k
    running = np.zeros(k)
    fold_of = {}
    for i in order:
        f = int(np.argmax(target - running))
        fold_of[block_ids[i]] = f
        running[f] += counts[i]
    return fold_of


def build_dataset(cfg, rows, blocks_sub, transform, mu, sd, *, augment, seed):
    xcol, ycol = cfg["xy"]
    if cfg["kind_col"]:
        # Positive class anchors sampling; the other kinds ride along as hard
        # negatives, matching the production road/drainage trainers.
        policies = []
        for kind in ("road", "drainage", "not_road"):
            pts = rows.loc[rows[cfg["kind_col"]] == kind, [xcol, ycol]].to_numpy()
            if len(pts):
                policies.append((kind, pts, JITTER_M))
        if not policies:
            return None
    else:
        pts = rows[[xcol, ycol]].to_numpy()
        if not len(pts):
            return None
        policies = [("pos", pts, JITTER_M)]
    bounds = np.array([g.bounds for g in blocks_sub.geometry])
    if not len(bounds):
        return None
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=DERIV_9T / cfg["labels"], policies=policies,
        block_bounds=bounds, transform=transform, mu=mu, sd=sd,
        patch=PATCH, augment=augment, seed=seed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, choices=sorted(TARGETS))
    ap.add_argument("--arch", required=True, choices=ARCHS)
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--only-folds", type=str, default="")
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--time-one-epoch", action="store_true",
                    help="train fold 0 for one epoch, report seconds, write nothing")
    args = ap.parse_args(argv)

    cfg = TARGETS[args.target]
    lbl_path = DERIV_9T / cfg["labels"]
    for p in (FEATURES, STATS, BLOCKS, lbl_path,
              DERIV_9T / cfg["manifest"]):
        if not p.exists():
            raise SystemExit(f"missing input: {p}")

    man = normalize_ids(pd.read_csv(DERIV_9T / cfg["manifest"]))
    man = man[man.block_id.notna()].copy()
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, CHANNELS_1M)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    n_per = man.groupby("block_id").size()
    bid = n_per.index.to_numpy()
    fold_of = assign_folds(bid, n_per.to_numpy(), args.folds, CV_SEED)
    man["fold"] = man.block_id.map(fold_of)
    blocks["fold"] = blocks.block_id.map(fold_of)

    print(f"== {args.target} / {args.arch} : {args.folds}-fold on the unified split ==")
    print(f"   {len(man):,} features across {len(bid)} blocks, 1 m grid")
    for f in range(args.folds):
        print(f"     fold {f}: {int((man.fold == f).sum()):5d} features")

    model0 = build_model(args.arch, cfg["n_classes"])
    n_par = sum(p.numel() for p in model0.parameters())
    print(f"   {args.arch}: {n_par/1e6:.1f} M parameters")
    del model0

    want = ({int(x) for x in args.only_folds.split(",") if x.strip()}
            if args.only_folds else set(range(args.folds)))

    out_arch = OUTROOT / args.target / args.arch
    results = []
    for k in range(args.folds):
        if k not in want:
            continue
        print(f"\n{'=' * 60}\nFOLD {k}\n{'=' * 60}")
        held = man.fold == k
        rest = man.loc[~held]
        # inner val = one of the remaining folds, so the held-out fold never
        # influences its own threshold or its own best epoch.
        inner = (k + 1) % args.folds
        tr_rows = rest.loc[rest.fold != inner]
        va_rows = rest.loc[rest.fold == inner]
        tr_blocks = blocks[(blocks.fold.notna()) & (blocks.fold != k)
                           & (blocks.fold != inner)]
        va_blocks = blocks[blocks.fold == inner]
        print(f"  train {len(tr_rows):,} / {len(tr_blocks)} blocks   "
              f"inner-val {len(va_rows):,} / {len(va_blocks)}   "
              f"HELD-OUT {int(held.sum()):,}")

        tr = build_dataset(cfg, tr_rows, tr_blocks, tf, mu, sd, augment=True, seed=42)
        va = build_dataset(cfg, va_rows, va_blocks, tf, mu, sd, augment=False, seed=43)
        if tr is None or va is None:
            print("  empty split, skipping fold")
            continue

        model = build_model(args.arch, cfg["n_classes"])
        tl = DataLoader(tr, batch_size=args.batch, shuffle=True,
                        num_workers=0, pin_memory=True)
        vl = DataLoader(va, batch_size=args.batch, shuffle=False,
                        num_workers=0, pin_memory=True)

        epochs = 1 if args.time_one_epoch else args.epochs
        fold_dir = out_arch / f"fold{k}"
        fold_dir.mkdir(parents=True, exist_ok=True)
        t0 = time.time()
        train_loop(
            model=model, train_loader=tl, val_loader=vl,
            loss_fn=FocalCE(alpha=cfg["alpha"], gamma=FOCAL_GAMMA),
            epochs=epochs, lr=args.lr, n_classes=cfg["n_classes"],
            out_dir=fold_dir, weight_decay=WEIGHT_DECAY,
            checkpoint_extra={"mu": mu, "sd": sd, "arch": args.arch,
                              "channels": list(CHANNELS_1M), "patch": PATCH,
                              "target": args.target, "fold": k},
            score=lambda iou: float(iou[cfg["score_cls"]]),
            extra_iou_names=cfg["iou_names"])
        dt = time.time() - t0

        if args.time_one_epoch:
            print(f"\nONE EPOCH: {dt:.1f}s  "
                  f"-> {args.epochs} epochs = {dt * args.epochs / 60:.0f} min/fold"
                  f"  -> {args.folds} folds = {dt * args.epochs * args.folds / 3600:.1f} h")
            return 0

        ck = torch.load(fold_dir / "best.pt", map_location="cpu", weights_only=False)
        results.append({"fold": k, "best_epoch": int(ck["epoch"]),
                        "val_score": float(ck["score"]), "minutes": dt / 60})
        print(f"  fold {k} done in {dt/60:.1f} min, best val "
              f"{cfg['iou_names'][cfg['score_cls']]} IoU {ck['score']:.3f}")

    if results:
        out_arch.mkdir(parents=True, exist_ok=True)
        scores = [r["val_score"] for r in results]
        pooled = {"target": args.target, "arch": args.arch,
                  "n_params": int(n_par), "folds": results,
                  "val_score_mean": float(np.mean(scores)),
                  "val_score_sd": float(np.std(scores)),
                  "channels": list(CHANNELS_1M), "patch": PATCH,
                  "alpha": list(cfg["alpha"]), "epochs": args.epochs,
                  "batch": args.batch, "lr": args.lr}
        (out_arch / "pooled_metrics.json").write_text(json.dumps(pooled, indent=2))
        print(f"\nPOOLED  val {cfg['iou_names'][cfg['score_cls']]} IoU "
              f"{np.mean(scores):.3f} (sd {np.std(scores):.3f})")
        print(f"wrote {out_arch / 'pooled_metrics.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
