"""Binary road segmentation U-Net at 0.5 m.

Trains on roads buffered 1.5 m -> rasterized to labels_road_9t_05.tif.
Uses ``not_roads`` as a hard-negative sampling pool so the network sees them
at train time with label = 0.

Pipeline:
    train -> save best.pt -> full-tile inference -> test eval.
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
from _dl import (DEFAULT_CHANNELS, DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

OUTDIR = DERIV_9T / "road_unet"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_road_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "road_dataset_manifest.csv"
ANN = DERIV_9T.parent / "annotations" / "annotations_proj.gpkg"

PATCH = 256
OVERLAP = 64
N_CLASSES = 2
JITTER_M = 30.0
FOCAL_ALPHA = (0.10, 0.90)
FOCAL_GAMMA = 2.0


def build_dataset(split: str, manifest: pd.DataFrame, blocks: gpd.GeoDataFrame,
                  transform, mu, sd, *, augment: bool, seed: int):
    m = manifest[manifest.split == split]
    roads = m.loc[m.kind == "road", ["mid_x", "mid_y"]].to_numpy()
    not_roads = m.loc[m.kind == "not_road", ["mid_x", "mid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks.loc[blocks.split == split].geometry])
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS,
        policies=[("road", roads, JITTER_M), ("not_road", not_roads, JITTER_M)],
        block_bounds=bounds, transform=transform,
        mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed,
    )


def write_outputs(prob: np.ndarray, argmax: np.ndarray, profile: dict) -> None:
    tf, crs = profile["transform"], profile["crs"]
    write_tif(OUTDIR / "road_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                     transform=tf, crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "road_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)
    print("  wrote road_prob.tif + road_argmax.tif")


def evaluate_test(argmax: np.ndarray, prob: np.ndarray) -> pd.DataFrame:
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_geom = blocks.loc[blocks.split == "test", "geometry"]
    test_mask = rasterize([(g, 1) for g in test_geom], out_shape=(H, W),
                          transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & test_mask).sum()); union = int(((p | t) & test_mask).sum())
    pix_iou = inter / union if union else None

    # Per-line mean probability for road / not_road TEST lines.
    man = pd.read_csv(MANIFEST)
    roads_t = gpd.read_file(ANN, layer="roads")
    not_roads_t = gpd.read_file(ANN, layer="not_roads")

    def line_prob(line) -> float:
        n = max(2, int(line.length))
        vals: list[float] = []
        for i in range(n + 1):
            pt = line.interpolate(min(i, line.length))
            r0 = int(round((pt.y - tf.f) / tf.e))
            c0 = int(round((pt.x - tf.c) / tf.a))
            if 0 <= r0 < H and 0 <= c0 < W:
                vals.append(float(prob[1, r0, c0]))
        return float(np.mean(vals)) if vals else 0.0

    rows: list[dict] = []
    for kind, gdf in (("road", roads_t), ("not_road", not_roads_t)):
        for i, row in gdf.reset_index(drop=True).iterrows():
            lid = f"{kind}_{i}"
            mrow = man[man.line_id == lid]
            if mrow.empty or mrow.iloc[0]["split"] != "test":
                continue
            rows.append({"line_id": lid, "kind": kind,
                         "split": "test", "mean_prob": line_prob(row.geometry)})
    line_df = pd.DataFrame(rows)

    ap: float | None = None
    if len(line_df) and line_df.kind.nunique() == 2:
        y = (line_df.kind == "road").astype(int).to_numpy()
        order = np.argsort(-line_df.mean_prob.to_numpy())
        y_sorted = y[order]
        tp = np.cumsum(y_sorted); fp = np.cumsum(1 - y_sorted)
        prec = tp / np.maximum(tp + fp, 1)
        rec = tp / max(int(y.sum()), 1)
        ap = float(np.trapezoid(prec, rec))

    metrics = {"pixel_iou_road_test": pix_iou,
               "line_average_precision_test": ap,
               "n_test_lines_evaluated": int(len(line_df))}
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    line_df.to_csv(OUTDIR / "test_per_line.csv", index=False)

    print(f"\nTEST pixel IoU (road): {pix_iou:.3f}" if pix_iou is not None else "\nNo pixel IoU")
    print(f"Per-line AP on test: {ap}")
    if len(line_df):
        print(line_df.groupby("kind").mean_prob.describe()[["mean", "50%"]].round(3))
    return line_df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()

    manifest = pd.read_csv(MANIFEST)
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
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

    model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
    loss_fn = FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA)

    # Score = IoU on the road class (class 1).
    train_loop(
        model=model, train_loader=train_loader, val_loader=val_loader,
        loss_fn=loss_fn, epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES,
        out_dir=OUTDIR,
        checkpoint_extra={"mu": mu, "sd": sd,
                          "channels": list(DEFAULT_CHANNELS), "patch": PATCH},
        score=lambda iou: float(iou[1]),
        extra_iou_names=("bg", "road"),
    )

    # Reload best, infer, evaluate on the test split.
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
