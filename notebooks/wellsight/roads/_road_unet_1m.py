"""Binary road segmentation U-Net at 1 m (matches the 1 m data_3x3 blocks).

Identical architecture/recipe to _road_unet.py but trained on the 1 m 9t stack
(features_pit_9t_1m.tif, roughness_5 instead of roughness_11) so the model can be
applied to the 1 m data_3x3 blocks at matched resolution. See
docs/iterations/road_unet_1m.md.

Pipeline: train -> save best.pt -> full-tile inference -> test eval.
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
from _common import DERIV_9T, make_profile, write_tif
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

OUTDIR = DERIV_9T / "road_unet_1m"
FEATURES = DERIV_9T / "features_pit_9t_1m.tif"
LABELS = DERIV_9T / "labels_road_9t_1m.tif"
STATS = DERIV_9T / "feature_stats_1m.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "road_dataset_manifest.csv"
CHUNKS = DERIV_9T / "road_chunks_9t.gpkg"  # per-chunk geometries for eval
ANN = DERIV_9T.parent / "annotations" / "annotations_proj.gpkg"

# 1 m channel order: roughness_5 replaces roughness_11.
CHANNELS_1M = ("lrm_25", "lrm_5", "slope", "tpi_05",
               "openness_pos", "openness_neg", "roughness_5")

PATCH = 256
OVERLAP = 64
N_CLASSES = 3  # 0=bg, 1=road, 2=drainage (drainage learned as explicit negative)
JITTER_M = 30.0
# bg down-weighted; road is the priority class (kept high, like the 2-class
# model's 0.90), drainage weighted enough to be learned as the suppressor that
# stops channels being called road. Road sampling is now balanced via chunking.
FOCAL_ALPHA = (0.10, 0.60, 0.30)
FOCAL_GAMMA = 2.0


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
        feat_path=FEATURES, lbl_path=LABELS,
        policies=policies,
        block_bounds=bounds, transform=transform,
        mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed,
    )


def write_outputs(prob, argmax, profile):
    tf, crs = profile["transform"], profile["crs"]
    write_tif(OUTDIR / "road_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                     transform=tf, crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "road_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)
    print("  wrote road_prob.tif + road_argmax.tif")


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

    # Per-CHUNK eval: comparable-length units (roads/not_roads chunked ~40 m,
    # drainage native chunks), read from road_chunks_9t.gpkg.
    chunks = gpd.read_file(CHUNKS, layer="chunks")
    chunks_test = chunks[chunks.split == "test"]

    def line_prob(line, cls=1) -> float:
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length))
        vals = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e))
            c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[cls, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    rows = []
    for _, row in chunks_test.iterrows():
        rows.append({"line_id": row.line_id, "kind": row.kind, "split": "test",
                     "mean_prob": line_prob(row.geometry, cls=1),       # P(road)
                     "mean_prob_drain": line_prob(row.geometry, cls=2)})  # P(drain)
    line_df = pd.DataFrame(rows)

    # Road-vs-not_road AP (unchanged headline, comparable to the 2-class model).
    def ap_road_vs(neg_kind):
        sub = line_df[line_df.kind.isin(["road", neg_kind])]
        if not len(sub) or sub.kind.nunique() < 2:
            return None
        y = (sub.kind == "road").astype(int).to_numpy()
        order = np.argsort(-sub.mean_prob.to_numpy())
        ys = y[order]
        tp = np.cumsum(ys); fp = np.cumsum(1 - ys)
        prec = tp / np.maximum(tp + fp, 1)
        rec = tp / max(int(y.sum()), 1)
        return float(np.trapezoid(prec, rec))

    ap = ap_road_vs("not_road")
    ap_vs_drain = ap_road_vs("drainage")
    drain_lines = line_df[line_df.kind == "drainage"]
    road_lines = line_df[line_df.kind == "road"]
    metrics = {"pixel_iou_road_test": pix_iou,
               "line_average_precision_test": ap,
               "line_ap_road_vs_drainage_test": ap_vs_drain,
               "mean_Proad_on_road_test": float(road_lines.mean_prob.mean()) if len(road_lines) else None,
               "mean_Proad_on_drainage_test": float(drain_lines.mean_prob.mean()) if len(drain_lines) else None,
               "n_test_lines_evaluated": int(len(line_df)),
               "n_classes": N_CLASSES,
               "resolution_m": 1.0, "channels": list(CHANNELS_1M)}
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    line_df.to_csv(OUTDIR / "test_per_line.csv", index=False)
    print(f"\nTEST pixel IoU (road): {pix_iou:.3f}" if pix_iou is not None else "\nNo pixel IoU")
    print(f"Per-line AP road-vs-not_road: {ap}   road-vs-drainage: {ap_vs_drain}")
    if len(line_df):
        print("mean P(road) by kind:")
        print(line_df.groupby("kind").mean_prob.agg(["mean", "median", "count"]).round(3))
    return line_df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, CHANNELS_1M)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    train_ds = build_dataset("train", manifest, blocks, tf, mu, sd, augment=True,  seed=42)
    val_ds   = build_dataset("val",   manifest, blocks, tf, mu, sd, augment=False, seed=43)
    print(f"train roads={len(train_ds.policies[0][1])} not_roads={len(train_ds.policies[1][1])} "
          f"tiles/ep={len(train_ds)}")
    print(f"val   roads={len(val_ds.policies[0][1])} not_roads={len(val_ds.policies[1][1])} "
          f"tiles/ep={len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=0, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch, shuffle=False,
                              num_workers=0, pin_memory=True)

    model = UNet(in_ch=len(CHANNELS_1M), n_classes=N_CLASSES, base=32)
    loss_fn = FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA)
    train_loop(
        model=model, train_loader=train_loader, val_loader=val_loader,
        loss_fn=loss_fn, epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES,
        out_dir=OUTDIR,
        checkpoint_extra={"mu": mu, "sd": sd,
                          "channels": list(CHANNELS_1M), "patch": PATCH},
        score=lambda iou: float(iou[1]),  # still select on road IoU
        extra_iou_names=("bg", "road", "drainage"),
    )

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}). Inference + test eval...")
    prob, argmax, profile = predict_full_tile(
        model, FEATURES, mu, sd,
        patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES,
    )
    write_outputs(prob, argmax, profile)
    evaluate_test(argmax, prob)
    print(f"Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
