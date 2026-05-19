"""Iter 04 — inference-only ensemble of iter 01 + iter 03.

Loads:
  iter 01 checkpoint (custom 8M-param UNet, 7-channel features)
  iter 03 checkpoint (SMP UNet + ResNet34/ImageNet, 11-channel features)

For each patch position on the 9t tile:
  1. Read 7-ch crop, normalize via iter 01's stats, run iter 01 with 8-fold TTA -> softmax_A
  2. Read 11-ch crop, normalize via iter 03's stats, run iter 03 with 8-fold TTA -> softmax_B
  3. Combine into TWO ensemble outputs:
       MEAN ensemble:   per-pixel mean of (softmax_A, softmax_B)
       MAX-PIT ensemble: per-pixel max for pit classes (1, 2), min for bg (0), re-normalized

Evaluate BOTH against the 20 held-out test pits.

Outputs land in data/derivatives/9t/iterations/04_ensemble_01_03/:
  ensemble_mean_prob_floor.tif
  ensemble_mean_prob_wall.tif
  ensemble_mean_argmax.tif
  ensemble_maxpit_prob_floor.tif
  ensemble_maxpit_prob_wall.tif
  ensemble_maxpit_argmax.tif
  test_metrics.json   (both schemes side by side)
  test_per_pit_mean.csv / test_per_pit_maxpit.csv
"""
import json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.features import rasterize
import geopandas as gpd
import torch
import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent.parent))
from _pit_unet_v2 import UNet  # custom 8M-param UNet used by iter 01

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "iterations" / "04_ensemble_01_03"; OUTDIR.mkdir(parents=True, exist_ok=True)

# Iter 01 inputs
FEATURES_01 = D / "features_pit_9t_05.tif"
CKPT_01 = D / "iterations" / "01_tta_miou" / "best.pt"

# Iter 03 inputs
FEATURES_03 = D / "iterations" / "03_multiscale_feats" / "features_pit_v2_9t_05.tif"
CKPT_03 = D / "iterations" / "03_multiscale_feats" / "best.pt"

LABELS = D / "labels_pit_9t_05.tif"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 256
OV = 64
N_CLASSES = 3
ENCODER_NAME = "resnet34"


def tta_predict_batch(model, x):
    outs = []
    for k in range(4):
        for flip in (False, True):
            x_aug = x
            if k: x_aug = torch.rot90(x_aug, k=k, dims=(2, 3))
            if flip: x_aug = torch.flip(x_aug, dims=(3,))
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type == "cuda"):
                logits = model(x_aug)
            p = torch.softmax(logits, dim=1)
            if flip: p = torch.flip(p, dims=(3,))
            if k: p = torch.rot90(p, k=-k, dims=(2, 3))
            outs.append(p.float())
    return torch.stack(outs, dim=0).mean(dim=0)


def load_model_01():
    ck = torch.load(CKPT_01, map_location=DEVICE, weights_only=False)
    n_ch = len(ck["channels"])
    model = UNet(in_ch=n_ch, n_classes=N_CLASSES, base=32).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"[iter 01] loaded ep {ck['epoch']} miou={ck['miou_pit']:.3f} channels={n_ch}")
    return model, mu, sd, n_ch


def load_model_03():
    ck = torch.load(CKPT_03, map_location=DEVICE, weights_only=False)
    n_ch = len(ck["channels"])
    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights=None,
                     in_channels=n_ch, classes=N_CLASSES).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)
    print(f"[iter 03] loaded ep {ck['epoch']} miou={ck['miou_pit']:.3f} channels={n_ch}")
    return model, mu, sd, n_ch


def infer_ensemble():
    """Slide windows across the tile, run both models with TTA per window, combine."""
    model_01, mu_01, sd_01, n01 = load_model_01()
    model_03, mu_03, sd_03, n03 = load_model_03()

    with rasterio.open(FEATURES_01) as r:
        H, W = r.height, r.width
    step = PATCH - OV
    rs = sorted(set(list(range(0, H - PATCH + 1, step)) + [H - PATCH]))
    cs = sorted(set(list(range(0, W - PATCH + 1, step)) + [W - PATCH]))
    print(f"Inference grid: {len(rs)} x {len(cs)} = {len(rs)*len(cs)} patches (TTA 8x each, both models)")

    prob_mean = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    prob_max  = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)

    src_01 = rasterio.open(FEATURES_01)
    src_03 = rasterio.open(FEATURES_03)
    BATCH = 8
    buf_x01, buf_x03, buf_pos = [], [], []
    t0 = time.time()

    def flush():
        if not buf_x01:
            return
        x01 = torch.from_numpy(np.stack(buf_x01)).to(DEVICE)
        x03 = torch.from_numpy(np.stack(buf_x03)).to(DEVICE)
        with torch.no_grad():
            p_a = tta_predict_batch(model_01, x01).cpu().numpy()
            p_b = tta_predict_batch(model_03, x03).cpu().numpy()
        p_mean = 0.5 * (p_a + p_b)
        # max-pit scheme: take max prob for pit classes, then renormalize so sum=1
        p_max = np.stack([
            np.minimum(p_a[:, 0], p_b[:, 0]),                # bg: be the more skeptical of the two
            np.maximum(p_a[:, 1], p_b[:, 1]),                # floor: be the more confident
            np.maximum(p_a[:, 2], p_b[:, 2]),                # wall: be the more confident
        ], axis=1)
        s = p_max.sum(axis=1, keepdims=True)
        p_max = p_max / np.clip(s, 1e-8, None)
        for arr_m, arr_mx, (r0, c0) in zip(p_mean, p_max, buf_pos):
            prob_mean[:, r0:r0+PATCH, c0:c0+PATCH] += arr_m
            prob_max [:, r0:r0+PATCH, c0:c0+PATCH] += arr_mx
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x01.clear(); buf_x03.clear(); buf_pos.clear()

    for r0 in rs:
        for c0 in cs:
            win = Window(c0, r0, PATCH, PATCH)
            f01 = src_01.read(window=win).astype(np.float32)
            f01 = np.where(np.isfinite(f01), f01, 0.0)
            f01 = (f01 - mu_01[:, None, None]) / sd_01[:, None, None]
            f03 = src_03.read(window=win).astype(np.float32)
            f03 = np.where(np.isfinite(f03), f03, 0.0)
            f03 = (f03 - mu_03[:, None, None]) / sd_03[:, None, None]
            buf_x01.append(f01); buf_x03.append(f03); buf_pos.append((r0, c0))
            if len(buf_x01) >= BATCH:
                flush()
    flush()
    src_01.close(); src_03.close()
    print(f"  ensemble inference done in {time.time()-t0:.1f}s")

    cnt = np.maximum(cnt, 1)
    prob_mean = prob_mean / cnt
    prob_max  = prob_max  / cnt
    # re-normalize prob_max after averaging across overlapping windows
    s = prob_max.sum(axis=0, keepdims=True)
    prob_max = prob_max / np.clip(s, 1e-8, None)
    argmax_mean = prob_mean.argmax(0).astype(np.uint8)
    argmax_max  = prob_max .argmax(0).astype(np.uint8)

    # Write rasters using the label TIF's profile (1-band reference grid)
    with rasterio.open(LABELS) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    for prob, prefix in [(prob_mean, "ensemble_mean"), (prob_max, "ensemble_maxpit")]:
        for cls, name in [(1, "prob_floor"), (2, "prob_wall")]:
            with rasterio.open(OUTDIR / f"{prefix}_{name}.tif", "w", **p1) as d:
                d.write(prob[cls], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "ensemble_mean_argmax.tif", "w", **p2) as d:
        d.write(argmax_mean, 1)
    with rasterio.open(OUTDIR / "ensemble_maxpit_argmax.tif", "w", **p2) as d:
        d.write(argmax_max, 1)
    print(f"  wrote 6 rasters to {OUTDIR}")

    return argmax_mean, argmax_max


def test_eval(argmax, scheme_name):
    with rasterio.open(LABELS) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tbm = rasterize([(g,1) for g in blocks[blocks.split=="test"].geometry],
                    out_shape=(H,W), transform=tf, fill=0, dtype="uint8").astype(bool)
    pix_iou = {}
    for cls, name in [(0,"bg"),(1,"floor"),(2,"wall")]:
        p = (argmax == cls) & tbm; t = (labels == cls) & tbm
        inter = int((p & t).sum()); union = int((p | t).sum())
        pix_iou[name] = inter/union if union else None
    man = pd.read_csv(MANIFEST)
    tp = man[man.split == "test"]
    pit_in = gpd.read_file(ANN, layer="pit_inside")
    rows = []
    for _, row in tp.iterrows():
        pid = int(row.pit_id)
        g = pit_in[pit_in.pit_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        pad = 6.0
        win = from_bounds(minx-pad, miny-pad, maxx+pad, maxy+pad, tf)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0: continue
        sub_lbl = labels[r0:r0+wh, c0:c0+ww]
        sub_pred = argmax[r0:r0+wh, c0:c0+ww]
        floor_t = sub_lbl == 1; wall_t = sub_lbl == 2
        pit_t = floor_t | wall_t
        pit_p = (sub_pred == 1) | (sub_pred == 2)
        recall_floor = float((floor_t & (sub_pred == 1)).sum() / max(floor_t.sum(), 1))
        recall_wall = float((wall_t & (sub_pred == 2)).sum() / max(wall_t.sum(), 1))
        recall_any = float((pit_t & pit_p).sum() / max(pit_t.sum(), 1))
        inter = int((pit_t & pit_p).sum()); union = int((pit_t | pit_p).sum())
        loc_iou = inter/union if union else None
        rows.append({"pit_id": pid, "recall_floor": recall_floor,
                     "recall_wall": recall_wall, "recall_any_pit": recall_any,
                     "pit_iou_local": loc_iou})
    df = pd.DataFrame(rows)
    metrics = {"pixel_iou": pix_iou, "n_test_pits": len(df),
               "n_detected_any": int((df.recall_any_pit > 0.1).sum()),
               "n_solid_iou_gt_0.3": int((df.pit_iou_local.fillna(0) > 0.3).sum()),
               "mean_pit_iou_local": float(df.pit_iou_local.mean()),
               "median_pit_iou_local": float(df.pit_iou_local.median()),
               "mean_recall_any_pit": float(df.recall_any_pit.mean())}
    df.to_csv(OUTDIR / f"test_per_pit_{scheme_name}.csv", index=False)
    print(f"\n[{scheme_name}] TEST pixel IoU: bg={pix_iou['bg']:.3f}  "
          f"floor={pix_iou['floor']:.3f}  wall={pix_iou['wall']:.3f}")
    print(f"[{scheme_name}] Per-pit ({len(df)} pits):")
    print(f"  mean local IoU:   {metrics['mean_pit_iou_local']:.3f}")
    print(f"  median local IoU: {metrics['median_pit_iou_local']:.3f}")
    print(f"  detected (>=10%): {metrics['n_detected_any']}/{len(df)}")
    print(f"  local IoU > 0.3:  {metrics['n_solid_iou_gt_0.3']}/{len(df)}")
    return metrics


def main():
    print(f"Device: {DEVICE}")
    argmax_mean, argmax_max = infer_ensemble()
    m_mean = test_eval(argmax_mean, "mean")
    m_max  = test_eval(argmax_max, "maxpit")
    (OUTDIR / "test_metrics.json").write_text(json.dumps(
        {"mean_ensemble": m_mean, "maxpit_ensemble": m_max}, indent=2, default=float))
    print(f"\nOutputs in {OUTDIR}")


if __name__ == "__main__":
    main()
