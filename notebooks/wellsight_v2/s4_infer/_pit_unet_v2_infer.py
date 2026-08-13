"""Full-tile inference + test-set eval for pit_unet_v2.

Writes pit_prob_floor.tif, pit_prob_wall.tif, pit_argmax.tif, test_metrics.json,
test_per_pit.csv, test_preds.png under data/derivatives/tiles/9t/pit_unet_v2/.
"""
from __future__ import annotations

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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, make_profile, path_for, write_tif
from _dl import DEVICE, UNet, predict_full_tile

OUTDIR = path_for("models") / "pit" / "unet_v2"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LABELS = DERIV_9T / "labels_pit_9t_05.tif"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MANIFEST = DERIV_9T / "pit_dataset_manifest.csv"
CKPT = OUTDIR / "best.pt"
ANN = path_for("truth") / "annotations_proj.gpkg"

PATCH = 256
OVERLAP = 64
N_CLASSES = 3


def write_outputs(prob: np.ndarray, argmax: np.ndarray, profile: dict) -> None:
    """Write float prob bands + uint8 argmax with project-standard compression."""
    tf, crs = profile["transform"], profile["crs"]
    # Probability rasters (floor + wall).
    for cls, name in [(1, "pit_prob_floor.tif"), (2, "pit_prob_wall.tif")]:
        write_tif(OUTDIR / name, prob[cls], transform=tf, crs=crs,
                  dtype="float32", nodata=-1.0, bigtiff=True)
        print(f"  wrote {name}")
    # Argmax raster.
    p = make_profile(
        width=argmax.shape[1], height=argmax.shape[0],
        transform=tf, crs=crs, dtype="uint8", nodata=255,
    )
    with rasterio.open(OUTDIR / "pit_argmax.tif", "w", **p) as dst:
        dst.write(argmax, 1)
    print("  wrote pit_argmax.tif")


def evaluate_test(argmax: np.ndarray) -> tuple[pd.DataFrame, dict]:
    """Pixel- and per-pit metrics restricted to TEST blocks."""
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    test_geom = blocks.loc[blocks.split == "test", "geometry"]
    test_mask = rasterize([(g, 1) for g in test_geom], out_shape=(H, W),
                          transform=tf, fill=0, dtype="uint8").astype(bool)

    pix_iou: dict[str, float | None] = {}
    for cls, name in [(0, "bg"), (1, "floor"), (2, "wall")]:
        p = (argmax == cls) & test_mask
        t = (labels == cls) & test_mask
        inter = int((p & t).sum()); union = int((p | t).sum())
        pix_iou[name] = inter / union if union else None
    print(f"\nTEST pixel IoU: bg={pix_iou['bg']:.3f}  "
          f"floor={pix_iou['floor']:.3f}  wall={pix_iou['wall']:.3f}")

    # Per-pit recall + local IoU.
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    test_pits = pd.read_csv(MANIFEST).query("split == 'test'")
    rows: list[dict] = []
    for _, mrow in test_pits.iterrows():
        pid = int(mrow.pit_id)
        ginner = pit_in.loc[pit_in.pit_id == pid].geometry.iloc[0]
        win = from_bounds(*[ginner.bounds[i] + (-6 if i < 2 else 6) for i in range(4)], tf)
        r0, c0 = max(int(win.row_off), 0), max(int(win.col_off), 0)
        wh, ww = min(int(win.height), H - r0), min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0:
            continue
        sub_lbl = labels[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]
        floor_t = sub_lbl == 1; wall_t = sub_lbl == 2
        pit_t = floor_t | wall_t
        pit_p = (sub_pred == 1) | (sub_pred == 2)
        inter = int((pit_t & pit_p).sum()); union = int((pit_t | pit_p).sum())
        rows.append({
            "pit_id": pid,
            "recall_floor":   float((floor_t & (sub_pred == 1)).sum() / max(floor_t.sum(), 1)),
            "recall_wall":    float((wall_t  & (sub_pred == 2)).sum() / max(wall_t.sum(),  1)),
            "recall_any_pit": float((pit_t & pit_p).sum() / max(pit_t.sum(), 1)),
            "pit_iou_local":  inter / union if union else None,
        })
    df = pd.DataFrame(rows)
    print(f"\nPer-pit recall on TEST ({len(df)} pits):")
    print(df.describe()[["recall_floor", "recall_wall", "recall_any_pit", "pit_iou_local"]]
          .round(3).to_string())

    n_any = int((df.recall_any_pit > 0.1).sum())
    n_solid = int((df.pit_iou_local.fillna(0) > 0.3).sum())
    print(f"\nPits with any pit pixels predicted (>=10% recall): {n_any}/{len(df)}")
    print(f"Pits with local IoU > 0.3:                          {n_solid}/{len(df)}")
    metrics = {
        "pixel_iou": pix_iou,
        "n_test_pits": len(df),
        "n_detected_any": n_any,
        "n_solid_iou_gt_0.3": n_solid,
        "mean_pit_iou_local": float(df.pit_iou_local.mean()),
        "mean_recall_any_pit": float(df.recall_any_pit.mean()),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2))
    df.to_csv(OUTDIR / "test_per_pit.csv", index=False)
    return df, metrics


def render_grid(df: pd.DataFrame, argmax: np.ndarray, *, n: int = 8) -> None:
    """Side-by-side hillshade + label / + prediction for worst-IoU pits."""
    if df.empty:
        return
    df = df.sort_values("pit_iou_local").head(n).reset_index(drop=True)
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    with rasterio.open(DERIV_9T / "hillshade_9t_05.tif") as r:
        tf, H, W = r.transform, r.height, r.width
        hs_full = r.read(1)
    with rasterio.open(LABELS) as r:
        lbl_full = r.read(1)
    cmap_lbl = ListedColormap(["#00000000", "#ff3333aa", "#3399ffaa"])
    cmap_pred = ListedColormap(["#00000000", "#ffaa00cc", "#00ddffcc"])

    fig, axes = plt.subplots(len(df), 2, figsize=(6, 3 * len(df)))
    if len(df) == 1:
        axes = np.array([axes])
    for i, row in df.iterrows():
        pid = int(row.pit_id)
        g = pit_in.loc[pit_in.pit_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        win = from_bounds(minx - 8, miny - 8, maxx + 8, maxy + 8, tf)
        r0, c0 = max(int(win.row_off), 0), max(int(win.col_off), 0)
        wh, ww = min(int(win.height), H - r0), min(int(win.width), W - c0)
        hs = hs_full[r0:r0+wh, c0:c0+ww]
        sub_lbl = lbl_full[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]
        for ax in axes[i]:
            ax.set_xticks([]); ax.set_yticks([])
        axes[i, 0].imshow(hs, cmap="gray")
        axes[i, 0].imshow(sub_lbl, cmap=cmap_lbl, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 0].set_title(f"pit {pid}  LABEL  IoU={row.pit_iou_local:.2f}", fontsize=8)
        axes[i, 1].imshow(hs, cmap="gray")
        axes[i, 1].imshow(sub_pred, cmap=cmap_pred, vmin=0, vmax=2, interpolation="nearest")
        axes[i, 1].set_title(f"pit {pid}  PRED  recall_any={row.recall_any_pit:.2f}", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUTDIR / "test_preds.png", dpi=110, bbox_inches="tight")
    plt.close(fig)
    print(f"Wrote test_preds.png ({len(df)} worst-IoU pits)")


def main() -> int:
    print(f"Device: {DEVICE}")
    ck = torch.load(CKPT, map_location=DEVICE, weights_only=False)
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"Loaded ep {ck['epoch']} -> channels: {ck['channels']}")

    model = UNet(in_ch=len(ck["channels"]), n_classes=N_CLASSES, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])

    prob, argmax, profile = predict_full_tile(
        model, FEATURES, mu, sd,
        patch=PATCH, overlap=OVERLAP, n_classes=N_CLASSES,
    )
    write_outputs(prob, argmax, profile)
    df, _ = evaluate_test(argmax)
    render_grid(df, argmax, n=min(8, len(df)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
