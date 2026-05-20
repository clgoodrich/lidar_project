"""Pit iter 06 — DEM-only single-channel input.

Apples-to-apples comparison with iter 01:
  iter 01: 7 engineered channels (LRMs, slope, TPI, openness, roughness)
  iter 06: 1 raw DEM channel

Same architecture (custom UNet, base=32), same dataset sampler, same focal
loss (3-class bg/floor/wall), same TTA inference, same 20-pit test set.

Hypothesis: if engineered features carry real signal the model can't reach
from raw elevation, iter 06 will regress hard. If the model can learn its
own LRM-equivalent features, iter 06 will come close to iter 01.

Uses the wsight package for the heavy lifting -- this is the first iteration
to demonstrate the consolidated library.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
import geopandas as gpd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # to find `wsight` package

from wsight.paths import (
    PIT_LABELS, BLOCKS_GPKG, PIT_MANIFEST, ANN_GPKG, ITERATIONS_DIR,
)
from wsight.models import UNet, load_segmentation_checkpoint
from wsight.losses import FocalCE
from wsight.datasets import SegmentationTiles
from wsight.training import train_segmentation
from wsight.inference import sliding_window_predict, write_prob_raster, write_argmax_raster
from wsight.evaluation import pit_test_eval

# Iter 06-specific paths
OUTDIR = ITERATIONS_DIR / "06_dem_only"; OUTDIR.mkdir(parents=True, exist_ok=True)
FEATURES = OUTDIR / "features_dem_9t_05.tif"
STATS = OUTDIR / "feature_stats_dem.json"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 256
N_CLASSES = 3
N_CH = 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    print(f"Device: {DEVICE}")

    manifest = pd.read_csv(PIT_MANIFEST)
    blocks_gdf = gpd.read_file(BLOCKS_GPKG, layer="blocks")
    stats = json.loads(Path(STATS).read_text())
    ch_order = ["dem"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)
    with rasterio.open(FEATURES) as r: tf = r.transform

    train_pits = manifest[manifest.split == "train"][["centroid_x", "centroid_y"]].values
    val_pits = manifest[manifest.split == "val"][["centroid_x", "centroid_y"]].values
    train_blocks = blocks_gdf[blocks_gdf.split == "train"]
    val_blocks = blocks_gdf[blocks_gdf.split == "val"]
    train_bb = np.array([g.bounds for g in train_blocks.geometry])
    val_bb = np.array([g.bounds for g in val_blocks.geometry])

    train_ds = SegmentationTiles(
        FEATURES, PIT_LABELS,
        centroids=train_pits, split_block_bounds=train_bb,
        transform=tf, mu=mu, sd=sd,
        patch=PATCH, jitter_m=30, bg_per_pos=1, augment=True,
    )
    val_ds = SegmentationTiles(
        FEATURES, PIT_LABELS,
        centroids=val_pits, split_block_bounds=val_bb,
        transform=tf, mu=mu, sd=sd,
        patch=PATCH, jitter_m=30, bg_per_pos=1, augment=False,
    )
    print(f"train pits={len(train_pits)} tiles_per_epoch={len(train_ds)}")
    print(f"val   pits={len(val_pits)} tiles_per_epoch={len(val_ds)}")
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    model = UNet(in_ch=N_CH, n_classes=N_CLASSES, base=32).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"UNet(in_ch=1, n_classes=3, base=32): {n_params/1e6:.2f} M params")
    loss_fn = FocalCE(alpha=(0.05, 0.475, 0.475), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    train_segmentation(
        model, train_loader, val_loader,
        loss_fn=loss_fn, opt=opt, scheduler=sched, scaler=scaler, device=DEVICE,
        n_classes=N_CLASSES, epochs=args.epochs, miou_classes=[1, 2],
        ckpt_path=OUTDIR / "best.pt",
        ckpt_extras={"mu": mu, "sd": sd, "channels": ch_order, "patch": PATCH},
        log_path=OUTDIR / "train_log.csv",
        label="iter 06 DEM-only",
    )

    # Reload best, infer with TTA, eval
    model, mu, sd, meta = load_segmentation_checkpoint(OUTDIR / "best.pt", device=DEVICE)
    print(f"\nLoaded best from ep {meta['epoch']}. Running TTA inference...")
    prob = sliding_window_predict(model, FEATURES, mu, sd,
                                  device=DEVICE, n_classes=N_CLASSES,
                                  patch=PATCH, overlap=64, batch=8, use_tta=True)
    argmax = prob.argmax(0).astype("uint8")
    write_prob_raster(prob[1], PIT_LABELS, OUTDIR / "pit_prob_floor.tif")
    write_prob_raster(prob[2], PIT_LABELS, OUTDIR / "pit_prob_wall.tif")
    write_argmax_raster(argmax, PIT_LABELS, OUTDIR / "pit_argmax.tif")

    metrics = pit_test_eval(
        argmax,
        labels_path=PIT_LABELS, blocks_path=BLOCKS_GPKG,
        manifest_path=PIT_MANIFEST, annotations_gpkg=ANN_GPKG,
        out_dir=OUTDIR,
    )
    print(f"\nTEST pixel IoU: bg={metrics['pixel_iou']['bg']:.3f}  "
          f"floor={metrics['pixel_iou']['floor']:.3f}  "
          f"wall={metrics['pixel_iou']['wall']:.3f}")
    print(f"Per-pit ({metrics['n_test_pits']} pits):")
    print(f"  mean local IoU:   {metrics['mean_pit_iou_local']:.3f}")
    print(f"  median local IoU: {metrics['median_pit_iou_local']:.3f}")
    print(f"  detected (>=10%): {metrics['n_detected_any']}/{metrics['n_test_pits']}")
    print(f"  local IoU > 0.3:  {metrics['n_solid_iou_gt_0.3']}/{metrics['n_test_pits']}")
    print(f"\nOutputs in {OUTDIR}")


if __name__ == "__main__":
    main()
