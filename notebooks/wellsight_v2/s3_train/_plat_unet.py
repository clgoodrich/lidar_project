"""Binary plat segmentation U-Net (plat / background) at 0.5 m.

Outputs (under data/derivatives/tiles/9t/plat_unet/):
    best.pt              best-val checkpoint
    train_log.csv        per-epoch metrics
    plat_prob.tif        full-tile probability
    plat_argmax.tif      uint8 argmax
    test_metrics.json    pixel + per-plat IoU on the test split
    test_preds.png       worst-IoU plats side-by-side
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import rasterio
import torch
from matplotlib.colors import ListedColormap
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, make_profile, path_for, write_tif
from _dl import (DEFAULT_CHANNELS, DEVICE, CenteredPatchSampler, FocalCE, UNet,
                 load_stats, predict_full_tile, train_loop)

OUTDIR = path_for("models") / "plat" / "unet"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_plat_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "plat_blocks_9t.gpkg"  # pad-aware split (all in-tile pads; see _build_plat_split.py)
MANIFEST = DERIV_9T / "plat_dataset_manifest.csv"
ANN = path_for("truth") / "annotations_proj.gpkg"

PATCH = 384  # plats are bigger than pits -> larger context window
OVERLAP = 96
N_CLASSES = 2
JITTER_M = 40.0
FOCAL_ALPHA = (0.15, 0.85)
FOCAL_GAMMA = 2.0


def build_dataset(split: str, manifest: pd.DataFrame, blocks: gpd.GeoDataFrame,
                  transform, mu, sd, *, augment: bool, seed: int):
    plats = manifest.loc[manifest.split == split, ["centroid_x", "centroid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks.loc[blocks.split == split].geometry])
    return CenteredPatchSampler(
        feat_path=FEATURES, lbl_path=LABELS,
        policies=[("plat", plats, JITTER_M)],
        block_bounds=bounds, transform=transform,
        mu=mu, sd=sd, patch=PATCH, augment=augment, seed=seed,
    )


def write_outputs(prob: np.ndarray, argmax: np.ndarray, profile: dict) -> None:
    tf, crs = profile["transform"], profile["crs"]
    write_tif(OUTDIR / "plat_prob.tif", prob[1], transform=tf, crs=crs,
              dtype="float32", nodata=-1.0, bigtiff=True)
    p = make_profile(width=argmax.shape[1], height=argmax.shape[0],
                     transform=tf, crs=crs, dtype="uint8", nodata=255)
    with rasterio.open(OUTDIR / "plat_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)
    print("  wrote plat_prob.tif + plat_argmax.tif")


def _per_plat_window(geom, tf, H: int, W: int, pad: float = 15.0):
    minx, miny, maxx, maxy = geom.bounds
    win = from_bounds(minx - pad, miny - pad, maxx + pad, maxy + pad, tf)
    r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
    wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
    return r0, c0, wh, ww


def evaluate_test(argmax: np.ndarray) -> tuple[pd.DataFrame, dict]:
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_geom = blocks.loc[blocks.split == "test", "geometry"]
    test_mask = rasterize([(g, 1) for g in test_geom], out_shape=(H, W),
                          transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & test_mask).sum()); union = int(((p | t) & test_mask).sum())
    pix_iou = inter / union if union else None

    plat = gpd.read_file(ANN, layer="plat")
    tp = pd.read_csv(MANIFEST).query("split == 'test'")
    rows: list[dict] = []
    for _, row in tp.iterrows():
        pid = int(row.plat_id)
        g = plat.loc[plat.plat_id == pid].geometry.iloc[0]
        r0, c0, wh, ww = _per_plat_window(g, tf, H, W)
        if wh <= 0 or ww <= 0:
            continue
        sl = labels[r0:r0+wh, c0:c0+ww] == 1
        sp = argmax[r0:r0+wh, c0:c0+ww] == 1
        inter2 = int((sl & sp).sum()); union2 = int((sl | sp).sum())
        rows.append({
            "plat_id": pid,
            "recall":     float((sl & sp).sum() / max(sl.sum(), 1)),
            "local_iou":  inter2 / union2 if union2 else None,
            "area_m2":    float(g.area),
        })
    df = pd.DataFrame(rows)
    metrics = {
        "pixel_iou_test": pix_iou,
        "n_test_plats": len(df),
        "n_detected_any_10pct": int((df.recall > 0.1).sum()),
        "n_iou_gt_0.3": int((df.local_iou.fillna(0) > 0.3).sum()),
        "mean_local_iou": float(df.local_iou.mean()),
        "mean_recall": float(df.recall.mean()),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2))
    df.to_csv(OUTDIR / "test_per_plat.csv", index=False)
    print(f"\nTEST pixel IoU: {pix_iou:.3f}" if pix_iou is not None else "\nNo pixel IoU")
    print(f"Per-plat ({len(df)}): mean_recall={df.recall.mean():.3f}  "
          f"mean_local_iou={df.local_iou.mean():.3f}")
    print(f"  detected (>=10% recall): {metrics['n_detected_any_10pct']}/{len(df)}")
    print(f"  local IoU > 0.3:         {metrics['n_iou_gt_0.3']}/{len(df)}")
    return df, metrics


def render_grid(df: pd.DataFrame, argmax: np.ndarray, *, n: int = 6) -> None:
    if df.empty:
        return
    df = df.sort_values("local_iou").head(n).reset_index(drop=True)
    plat = gpd.read_file(ANN, layer="plat")
    with rasterio.open(DERIV_9T / "hillshade_9t_05.tif") as r:
        tf, H, W = r.transform, r.height, r.width
        hs_full = r.read(1)
    with rasterio.open(LABELS) as r:
        lbl_full = r.read(1)
    cmap_lbl = ListedColormap(["#00000000", "#ff3333aa"])
    cmap_pred = ListedColormap(["#00000000", "#00ddffcc"])

    fig, axes = plt.subplots(len(df), 2, figsize=(7, 3.5 * len(df)))
    if len(df) == 1:
        axes = np.array([axes])
    for i, row in df.iterrows():
        pid = int(row.plat_id)
        g = plat.loc[plat.plat_id == pid].geometry.iloc[0]
        r0, c0, wh, ww = _per_plat_window(g, tf, H, W)
        hs = hs_full[r0:r0+wh, c0:c0+ww]
        sl = lbl_full[r0:r0+wh, c0:c0+ww]
        sp = argmax[r0:r0+wh, c0:c0+ww]
        for ax in axes[i]:
            ax.set_xticks([]); ax.set_yticks([])
        axes[i, 0].imshow(hs, cmap="gray")
        axes[i, 0].imshow(sl, cmap=cmap_lbl, vmin=0, vmax=1)
        axes[i, 0].set_title(f"plat {pid}  LABEL  IoU={row.local_iou:.2f}", fontsize=8)
        axes[i, 1].imshow(hs, cmap="gray")
        axes[i, 1].imshow(sp, cmap=cmap_pred, vmin=0, vmax=1)
        axes[i, 1].set_title(f"plat {pid}  PRED  recall={row.recall:.2f}", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUTDIR / "test_preds.png", dpi=110, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--eval-only", action="store_true",
                    help="skip training; load existing best.pt and re-run inference + test eval")
    args = ap.parse_args()

    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    if not args.eval_only:
        manifest = pd.read_csv(MANIFEST)
        blocks = gpd.read_file(BLOCKS, layer="blocks")
        train_ds = build_dataset("train", manifest, blocks, tf, mu, sd, augment=True,  seed=42)
        val_ds   = build_dataset("val",   manifest, blocks, tf, mu, sd, augment=False, seed=43)
        print(f"train plats={len(train_ds.policies[0][1])} tiles/ep={len(train_ds)}")
        print(f"val   plats={len(val_ds.policies[0][1])} tiles/ep={len(val_ds)}")

        train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                                  num_workers=0, pin_memory=True)
        val_loader   = DataLoader(val_ds,   batch_size=args.batch, shuffle=False,
                                  num_workers=0, pin_memory=True)

        model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
        loss_fn = FocalCE(alpha=FOCAL_ALPHA, gamma=FOCAL_GAMMA)

        train_loop(
            model=model, train_loader=train_loader, val_loader=val_loader,
            loss_fn=loss_fn, epochs=args.epochs, lr=args.lr, n_classes=N_CLASSES,
            out_dir=OUTDIR,
            checkpoint_extra={"mu": mu, "sd": sd,
                              "channels": list(DEFAULT_CHANNELS), "patch": PATCH},
            score=lambda iou: float(iou[1]),
            extra_iou_names=("bg", "plat"),
        )

    model = UNet(in_ch=len(DEFAULT_CHANNELS), n_classes=N_CLASSES, base=32)
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.to(DEVICE).load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}). Inference + test eval...")
    prob, argmax, profile = predict_full_tile(
        model, FEATURES, mu, sd,
        patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES,
    )
    write_outputs(prob, argmax, profile)
    df, _ = evaluate_test(argmax)
    render_grid(df, argmax, n=min(6, len(df)))
    print(f"Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
