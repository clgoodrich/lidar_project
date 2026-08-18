"""Pit semantic segmentation v2: 3-class (bg / floor / wall) at 0.5 m.

Inputs:
    data/derivatives/tiles/9t/features_pit_9t_05.tif    (7 bands, float32, NaN nodata)
    data/derivatives/tiles/9t/labels_pit_9t_05.tif      (uint8: 0=bg, 1=floor, 2=wall)
    data/derivatives/tiles/9t/feature_stats.json
    data/derivatives/tiles/9t/pit_blocks_9t.gpkg
    data/derivatives/tiles/9t/pit_dataset_manifest.csv

Outputs under data/derivatives/tiles/9t/pit_unet_v2/:
    best.pt              best-val checkpoint (state_dict + cfg + norm stats)
    train_log.csv        per-epoch metrics

Run:
    python notebooks/wellsight/pits/_pit_unet_v2.py --epochs 40 --batch 16
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from torch.utils.data import DataLoader

# Sibling-import the project's shared modules.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, normalize_ids
from _dl import (DEFAULT_CHANNELS, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, train_loop)

OUTDIR = path_for("models") / "pit" / "unet_v2"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_pit_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "pit_dataset_manifest.csv"

PATCH = 256        # 128 m at 0.5 m/px
N_CLASSES = 3
JITTER_M = 30.0
FOCAL_ALPHA = (0.05, 0.475, 0.475)
FOCAL_GAMMA = 2.0


def build_dataset(split: str, manifest: pd.DataFrame, blocks_gdf: gpd.GeoDataFrame,
                  transform, mu: np.ndarray, sd: np.ndarray, *, augment: bool, seed: int):
    pits = manifest.loc[manifest.split == split, ["centroid_x", "centroid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks_gdf.loc[blocks_gdf.split == split].geometry])
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS,
        policies=[("pit", pits, JITTER_M)],
        block_bounds=bounds, transform=transform,
        mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--smoke", action="store_true", help="single short epoch for sanity")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 1

    manifest = normalize_ids(pd.read_csv(MANIFEST))
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    train_ds = build_dataset("train", manifest, blocks, tf, mu, sd, augment=True,  seed=42)
    val_ds   = build_dataset("val",   manifest, blocks, tf, mu, sd, augment=False, seed=43)
    print(f"train pits={len(train_ds.policies[0][1])} tiles_per_epoch={len(train_ds)}")
    print(f"val   pits={len(val_ds.policies[0][1])} tiles_per_epoch={len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, pin_memory=True)
    val_loader   = DataLoader(val_ds,   batch_size=args.batch, shuffle=False,
                              num_workers=args.workers, pin_memory=True)

    model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
    loss_fn = FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA)
    print(f"UNet params: {sum(p.numel() for p in model.parameters())/1e6:.2f} M")

    # Score = mean IoU of pit classes (exclude background).
    def score(iou: list[float]) -> float:
        return float(np.nanmean(iou[1:]))

    train_loop(
        model=model, train_loader=train_loader, val_loader=val_loader,
        loss_fn=loss_fn, epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES,
        out_dir=OUTDIR,
        checkpoint_extra={"mu": mu, "sd": sd,
                          "channels": list(DEFAULT_CHANNELS), "patch": PATCH},
        score=score,
        extra_iou_names=("bg", "floor", "wall"),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
