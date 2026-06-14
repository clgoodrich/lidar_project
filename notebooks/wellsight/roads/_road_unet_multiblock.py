"""Multi-block 3-class road U-Net (bg/road/drainage) at 1 m.

Trains across the 6 data_3x3 blocks that carry hand-drawn road (built by
_build_road_multiblock_dataset.py) instead of the 9t slice alone. Uses each
block's own roughness_11 feature stack (matching what we infer on) and
train-block normalization. Spatial-block split: train {618594,622591,613603,
613608}, val {618591}, test {622594}. 613590 stays a pure inference target.

Pipeline: train -> save best.pt -> eval on held-out 622594 -> predict 613590.

CLI:  python notebooks/wellsight/roads/_road_unet_multiblock.py --epochs 40
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
from torch.utils.data import ConcatDataset, DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV, make_profile, write_tif
from _dl import (DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

BLOCKDIR = DERIV / "tiles" / "data_3x3" / "westernpa_d20"
DSET = DERIV / "tiles" / "road_multiblock"
OUTDIR = DSET / "road_unet_mb"
STATS = DSET / "feature_stats_road_mb.json"
MANIFEST = DSET / "road_mb_manifest.csv"
CHUNKS = DSET / "road_mb_chunks.gpkg"

CHANNELS = ("lrm_25", "lrm_5", "slope", "tpi_05",
            "openness_pos", "openness_neg", "roughness_11")
TRAIN_BLOCKS = ["618594", "622591", "613603", "613608"]
VAL_BLOCKS = ["618591"]
TEST_BLOCK = "622594"
PREDICT_BLOCKS = ["613590"]

PATCH, OVERLAP, N_CLASSES, JITTER_M = 256, 64, 3, 30.0
FOCAL_ALPHA = (0.10, 0.60, 0.30)
FOCAL_GAMMA = 2.0


def feat_path(key): return BLOCKDIR / key / f"features_{key}_1m.tif"
def lbl_path(key): return DSET / f"labels_road_{key}_1m.tif"


def block_sampler(key, manifest, mu, sd, *, augment, seed):
    m = manifest[manifest.block == key]
    def pts(kind):
        s = m[m.kind == kind]
        return s[["mid_x", "mid_y"]].to_numpy() if len(s) else np.empty((0, 2))
    policies = [("road", pts("road"), JITTER_M),
                ("not_road", pts("not_road"), JITTER_M),
                ("drainage", pts("drainage"), JITTER_M)]
    with rasterio.open(feat_path(key)) as r:
        tf = r.transform
        b = r.bounds
    bounds = np.array([[b.left, b.bottom, b.right, b.top]])
    return CenteredPatchSampler(
        feat_path=feat_path(key), lbl_path=lbl_path(key),
        policies=policies, block_bounds=bounds, transform=tf,
        mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed)


def eval_block(key, mu, sd, model):
    """Pixel road-IoU + per-line P(road) by kind on a held-out block."""
    prob, argmax, prof = predict_full_tile(
        model, feat_path(key), mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf = prof["transform"]; H, W = argmax.shape
    with rasterio.open(lbl_path(key)) as r:
        lab = r.read(1)
    valid = lab != 255
    p = (argmax == 1) & valid; t = (lab == 1) & valid
    inter = int((p & t).sum()); union = int((p | t).sum())
    iou = inter / union if union else None

    chunks = gpd.read_file(CHUNKS, layer="chunks")
    ck = chunks[(chunks.block == key)]

    def line_prob(line, cls):
        if line is None or line.is_empty:
            return 0.0
        n = max(2, int(line.length)); vals = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e)); c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[cls, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    rows = [{"kind": row.kind, "p_road": line_prob(row.geometry, 1)} for _, row in ck.iterrows()]
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
        "test_block": key, "pixel_iou_road": iou,
        "ap_road_vs_drainage": ap_vs("drainage"),
        "ap_road_vs_not_road": ap_vs("not_road"),
        "mean_Proad_on_road": float(df[df.kind == "road"].p_road.mean()) if (df.kind == "road").any() else None,
        "mean_Proad_on_drainage": float(df[df.kind == "drainage"].p_road.mean()) if (df.kind == "drainage").any() else None,
        "n_lines": int(len(df)), "channels": list(CHANNELS), "resolution_m": 1.0,
    }
    # save test-block road prob for inspection
    write_tif(OUTDIR / f"road_prob_{key}_1m.tif", prob[1], transform=tf, crs=prof["crs"],
              dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUTDIR / f"drainage_prob_{key}_1m.tif", prob[2], transform=tf, crs=prof["crs"],
              dtype="float32", nodata=-1.0, bigtiff=True)
    return metrics


def predict_block(key, mu, sd, model):
    prob, argmax, prof = predict_full_tile(
        model, feat_path(key), mu, sd, patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES)
    tf = prof["transform"]
    write_tif(OUTDIR / f"road_prob_{key}_1m.tif", prob[1], transform=tf, crs=prof["crs"],
              dtype="float32", nodata=-1.0, bigtiff=True)
    write_tif(OUTDIR / f"drainage_prob_{key}_1m.tif", prob[2], transform=tf, crs=prof["crs"],
              dtype="float32", nodata=-1.0, bigtiff=True)
    am = make_profile(width=argmax.shape[1], height=argmax.shape[0], transform=tf,
                      crs=prof["crs"], dtype="uint8", nodata=255, bigtiff=True)
    with rasterio.open(OUTDIR / f"road_argmax_{key}_1m.tif", "w", **am) as d:
        d.write(argmax, 1)
    print(f"  predicted {key}: road>=0.5 px = {int((prob[1] >= 0.5).sum())}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--eval-only", action="store_true")
    args = ap.parse_args()

    OUTDIR.mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(MANIFEST, dtype={"block": str})
    mu, sd = load_stats(STATS, CHANNELS)

    model = UNet(in_ch=len(CHANNELS), n_classes=N_CLASSES, base=32)

    if not args.eval_only:
        train_ds = ConcatDataset([block_sampler(k, manifest, mu, sd, augment=True, seed=42 + i)
                                  for i, k in enumerate(TRAIN_BLOCKS)])
        val_ds = ConcatDataset([block_sampler(k, manifest, mu, sd, augment=False, seed=99 + i)
                                for i, k in enumerate(VAL_BLOCKS)])
        print(f"train blocks={TRAIN_BLOCKS} tiles/ep={len(train_ds)}  "
              f"val blocks={VAL_BLOCKS} tiles/ep={len(val_ds)}")
        train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                                  num_workers=0, pin_memory=True)
        val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                                num_workers=0, pin_memory=True)
        train_loop(
            model=model, train_loader=train_loader, val_loader=val_loader,
            loss_fn=FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA),
            epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES, out_dir=OUTDIR,
            checkpoint_extra={"mu": mu, "sd": sd, "channels": list(CHANNELS), "patch": PATCH},
            score=lambda iou: float(iou[1]),
            extra_iou_names=("bg", "road", "drainage"))

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}, val road IoU {ck['score']:.3f}).")

    print(f"\n=== eval on held-out {TEST_BLOCK} ===")
    metrics = eval_block(TEST_BLOCK, mu, sd, model)
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    for k, v in metrics.items():
        if isinstance(v, float):
            print(f"  {k:24s} {v:.4f}")
        elif not isinstance(v, list):
            print(f"  {k:24s} {v}")

    for key in PREDICT_BLOCKS:
        print(f"\n=== predict {key} ===")
        predict_block(key, mu, sd, model)
    print(f"\nDONE. Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
