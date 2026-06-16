"""Recall-focused 9t-only road U-Net (1 m, 3-class bg/road/drainage).

Same clean 9t data as _road_unet_1m.py (roads + drainage CLIPPED TO 9t, nothing
outside) and the same roughness_5 channel-7 (which matches the data_3x3 blocks'
band-7 data). The only changes target ROAD RECALL on out-of-domain blocks:

  * road focal-alpha 0.60 -> 0.72 (push P(road) on real roads above threshold;
    we have headroom — held-out road-vs-drainage AP was 0.997)
  * drainage 0.30 -> 0.25, bg 0.10 (unchanged)
  * weight_decay 1e-4 -> 2e-4 (curb the late overfit)

After training it evals on the held-out 9t test blocks AND predicts 613590
(road_prob + drainage_prob) so we can compare gap-closing vs the deployed model.

CLI:  python notebooks/wellsight/roads/_road_unet_1m_recall.py --epochs 40
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
from _common import DERIV, DERIV_9T, make_profile, write_tif
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

OUTDIR = DERIV_9T / "road_unet_1m_recall"
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
FOCAL_ALPHA = (0.10, 0.72, 0.25)   # bg, ROAD(+), drainage(-)
FOCAL_GAMMA = 2.0
WEIGHT_DECAY = 2e-4

PREDICT_BLOCK = DERIV / "tiles" / "data_3x3" / "westernpa_d20" / "613590"


def build_dataset(split, manifest, blocks, transform, mu, sd, *, augment, seed):
    m = manifest[manifest.split == split]
    roads = m.loc[m.kind == "road", ["mid_x", "mid_y"]].to_numpy()
    not_roads = m.loc[m.kind == "not_road", ["mid_x", "mid_y"]].to_numpy()
    drainage = m.loc[m.kind == "drainage", ["mid_x", "mid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks.loc[blocks.split == split].geometry])
    policies = [("road", roads, JITTER_M), ("not_road", not_roads, JITTER_M)]
    if len(drainage):
        policies.append(("drainage", drainage, JITTER_M))
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS, policies=policies,
        block_bounds=bounds, transform=transform, mu=mu, sd=sd,
        patch=PATCH, augment=augment, seed=seed)


def write_outputs(prob, argmax, profile):
    tf, crs = profile["transform"], profile["crs"]
    write_tif(OUTDIR / "road_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0], transform=tf,
                     crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "road_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)


def evaluate_test(argmax, prob):
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_geom = blocks.loc[blocks.split == "test", "geometry"]
    test_mask = rasterize([(g, 1) for g in test_geom], out_shape=(H, W),
                          transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & test_mask).sum()); union = int(((p | t) & test_mask).sum())
    pix_iou = inter / union if union else None

    chunks = gpd.read_file(CHUNKS, layer="chunks")
    ct = chunks[chunks.split == "test"]

    def line_prob(line, cls=1):
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length)); vals = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e)); c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[cls, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    rows = [{"kind": r.kind, "p_road": line_prob(r.geometry, 1)} for _, r in ct.iterrows()]
    df = pd.DataFrame(rows)

    def ap_vs(neg):
        sub = df[df.kind.isin(["road", neg])]
        if not len(sub) or sub.kind.nunique() < 2:
            return None
        y = (sub.kind == "road").astype(int).to_numpy()
        order = np.argsort(-sub.p_road.to_numpy()); ys = y[order]
        tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
        prec = tp / np.maximum(tp + fp, 1); rec = tp / max(int(y.sum()), 1)
        return float(np.trapezoid(prec, rec))

    metrics = {
        "pixel_iou_road_test": pix_iou,
        "ap_road_vs_not_road": ap_vs("not_road"),
        "ap_road_vs_drainage": ap_vs("drainage"),
        "mean_Proad_on_road_test": float(df[df.kind == "road"].p_road.mean()) if (df.kind == "road").any() else None,
        "mean_Proad_on_drainage_test": float(df[df.kind == "drainage"].p_road.mean()) if (df.kind == "drainage").any() else None,
        "focal_alpha": list(FOCAL_ALPHA), "n_classes": N_CLASSES, "channels": list(CHANNELS_1M),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    print("\n=== 9t held-out test ===")
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:28s} {v:.4f}")


def predict_613590(mu, sd, model):
    feat = PREDICT_BLOCK / "features_613590_1m.tif"
    if not feat.exists():
        print(f"  (skip 613590 predict: {feat} missing)"); return
    prob, argmax, prof = predict_full_tile(
        model, feat, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf, crs = prof["transform"], prof["crs"]
    write_tif(OUTDIR / "road_prob_613590_1m.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUTDIR / "drainage_prob_613590_1m.tif", prob[2], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    print(f"\n=== 613590 predict ===  road>=0.5 px = {int((prob[1] >= 0.5).sum())}  "
          f"mean P(road) where>=0.3 = {float(prob[1][prob[1] >= 0.3].mean()):.3f}")


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
        print(f"train roads={len(train_ds.policies[0][1])} tiles/ep={len(train_ds)}  "
              f"val roads={len(val_ds.policies[0][1])} tiles/ep={len(val_ds)}")
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
            score=lambda iou: float(iou[1]),
            extra_iou_names=("bg", "road", "drainage"))

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}, val road IoU {ck['score']:.3f}).")
    prob, argmax, profile = predict_full_tile(
        model, FEATURES, mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    write_outputs(prob, argmax, profile)
    evaluate_test(argmax, prob)
    predict_613590(mu, sd, model)
    print(f"\nDONE. Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
