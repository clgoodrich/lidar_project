"""Drainage-focused 9t road/drainage U-Net (1 m, 3-class bg/road/drainage).

The symmetric twin of `_road_unet_1m_recall.py`: SAME clean 9t data, channels, and
3-class label raster (0=bg 1=road 2=drainage), but the focal weights are flipped so
DRAINAGE is the positive of interest and road is demoted to a confuser/negative.
Where the road model bumped road-alpha to chase road recall, this bumps drainage:

  * focal-alpha (bg, road, drainage) = (0.10, 0.25, 0.72)   [road model was (0.10, 0.72, 0.25)]
  * keeping road as its own class (not folded into bg) so the net explicitly learns
    "this linear feature is a ROAD, not drainage" -- the in-model fix for the
    road/drainage confusion, rather than a post-hoc filter.

The 3-class label raster already encodes drainage (2): 179,928 px in 9t, with
1067/136/249 train/val/test drainage chunks in road_chunks_9t.gpkg.

After training it evals on the held-out 9t test blocks (drainage IoU + drainage-vs-road
AP) AND predicts 613590 drainage_prob so we can compare against the road model's
incidental drainage channel.

CLI:  python notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py --epochs 40
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
import torch
from rasterio.features import rasterize
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, DERIV_9T, make_profile, write_tif, path_for
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

OUTDIR = path_for("models") / "drainage" / "unet_1m"
FEATURES = DERIV_9T / "features_pit_9t_1m.tif"
LABELS = DERIV_9T / "labels_road_9t_1m.tif"
STATS = DERIV_9T / "feature_stats_1m.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "road_dataset_manifest.csv"
CHUNKS = DERIV_9T / "road_chunks_9t.gpkg"

CHANNELS_1M = ("lrm_25", "lrm_5", "slope", "tpi_05",
               "openness_pos", "openness_neg", "roughness_5")

PATCH = 256
OVERLAP = 64
N_CLASSES = 3
JITTER_M = 30.0
FOCAL_ALPHA = (0.10, 0.25, 0.72)   # bg, road(-, confuser), DRAINAGE(+)
FOCAL_GAMMA = 2.0
WEIGHT_DECAY = 2e-4
DRAIN_CLS = 2

PREDICT_BLOCK = path_for("data_3x3") / "westernpa_d20" / "613590"


def build_dataset(split, manifest, blocks, transform, mu, sd, *, augment, seed):
    m = manifest[manifest.split == split]
    drainage = m.loc[m.kind == "drainage", ["mid_x", "mid_y"]].to_numpy()
    roads = m.loc[m.kind == "road", ["mid_x", "mid_y"]].to_numpy()
    not_roads = m.loc[m.kind == "not_road", ["mid_x", "mid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks.loc[blocks.split == split].geometry])
    # drainage first so it anchors sampling; road/not_road provide hard negatives
    policies = [("drainage", drainage, JITTER_M), ("road", roads, JITTER_M)]
    if len(not_roads):
        policies.append(("not_road", not_roads, JITTER_M))
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS, policies=policies,
        block_bounds=bounds, transform=transform, mu=mu, sd=sd,
        patch=PATCH, augment=augment, seed=seed)


def write_outputs(prob, argmax, profile):
    tf, crs = profile["transform"], profile["crs"]
    write_tif(OUTDIR / "drainage_prob.tif", prob[DRAIN_CLS], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0], transform=tf,
                     crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "drainage_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)


def evaluate_test(argmax, prob):
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_geom = blocks.loc[blocks.split == "test", "geometry"]
    test_mask = rasterize([(g, 1) for g in test_geom], out_shape=(H, W),
                          transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == DRAIN_CLS; t = labels == DRAIN_CLS
    inter = int((p & t & test_mask).sum()); union = int(((p | t) & test_mask).sum())
    pix_iou = inter / union if union else None

    chunks = gpd.read_file(CHUNKS, layer="chunks")
    ct = chunks[chunks.split == "test"]

    def line_prob(line, cls=DRAIN_CLS):
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length)); vals = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e)); c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[cls, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    rows = [{"kind": r.kind, "p_drain": line_prob(r.geometry)} for _, r in ct.iterrows()]
    df = pd.DataFrame(rows)

    def ap_vs(neg):
        sub = df[df.kind.isin(["drainage", neg])]
        if not len(sub) or sub.kind.nunique() < 2:
            return None
        y = (sub.kind == "drainage").astype(int).to_numpy()
        order = np.argsort(-sub.p_drain.to_numpy()); ys = y[order]
        tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
        prec = tp / np.maximum(tp + fp, 1); rec = tp / max(int(y.sum()), 1)
        return float(np.trapezoid(prec, rec))

    metrics = {
        "pixel_iou_drainage_test": pix_iou,
        "ap_drainage_vs_road": ap_vs("road"),
        "ap_drainage_vs_not_road": ap_vs("not_road"),
        "mean_Pdrain_on_drainage_test": float(df[df.kind == "drainage"].p_drain.mean()) if (df.kind == "drainage").any() else None,
        "mean_Pdrain_on_road_test": float(df[df.kind == "road"].p_drain.mean()) if (df.kind == "road").any() else None,
        "focal_alpha": list(FOCAL_ALPHA), "n_classes": N_CLASSES, "channels": list(CHANNELS_1M),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    print("\n=== 9t held-out test (drainage) ===")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:30s} {v:.4f}")


def predict_613590(mu, sd, model):
    feat = PREDICT_BLOCK / "features_613590_1m.tif"
    if not feat.exists():
        print(f"  (skip 613590 predict: {feat} missing)"); return
    prob, argmax, prof = predict_full_tile(
        model, feat, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf, crs = prof["transform"], prof["crs"]
    write_tif(OUTDIR / "drainage_prob_613590_1m.tif", prob[DRAIN_CLS], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUTDIR / "road_prob_613590_1m.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    print(f"\n=== 613590 predict ===  drainage>=0.5 px = {int((prob[DRAIN_CLS] >= 0.5).sum())}  "
          f"mean P(drain) where>=0.3 = {float(prob[DRAIN_CLS][prob[DRAIN_CLS] >= 0.3].mean()):.3f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, CHANNELS_1M)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    model = UNet(in_ch=len(CHANNELS_1M), n_classes=N_CLASSES, base=32)

    if not args.eval_only:
        train_ds = build_dataset("train", manifest, blocks, tf, mu, sd, augment=True, seed=42)
        val_ds = build_dataset("val", manifest, blocks, tf, mu, sd, augment=False, seed=43)
        print(f"alpha={FOCAL_ALPHA}  wd={WEIGHT_DECAY}")
        print(f"train drainage={len(train_ds.policies[0][1])} tiles/ep={len(train_ds)}  "
              f"val drainage={len(val_ds.policies[0][1])} tiles/ep={len(val_ds)}")
        train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                                  num_workers=0, pin_memory=True)
        val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                                num_workers=0, pin_memory=True)
        train_loop(
            model=model, train_loader=train_loader, val_loader=val_loader,
            loss_fn=FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA),
            epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES, out_dir=OUTDIR,
            weight_decay=WEIGHT_DECAY,
            checkpoint_extra={"mu": mu, "sd": sd, "channels": list(CHANNELS_1M), "patch": PATCH},
            score=lambda iou: float(iou[DRAIN_CLS]),
            extra_iou_names=("bg", "road", "drainage"))

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}, val drainage IoU {ck['score']:.3f}).")
    prob, argmax, profile = predict_full_tile(
        model, FEATURES, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    write_outputs(prob, argmax, profile)
    evaluate_test(argmax, prob)
    predict_613590(mu, sd, model)
    print(f"\nDONE. Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
