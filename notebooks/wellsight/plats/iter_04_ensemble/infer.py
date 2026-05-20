"""Plat iter 04 — inference-only ensemble of plat iter 01 + plat iter 02.

Mirror of pit iter 04. Loads both saved checkpoints (custom UNet on 7ch and
SMP-ResNet34 on 7ch), runs each with 8-fold TTA per patch, combines softmax
into a MEAN ensemble. Note: we skip the max-pit variant for plats because
plats don't have the same "I'd rather miss boundary than miss the pit"
asymmetry — plats have 100% detection on iter 01 already; the goal is to
preserve that while gaining iter 02's boundary quality.

Outputs under data/derivatives/9t/iterations/plat_04_ensemble/.
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
from _plat_unet import UNet, D, ANN, LABELS_PLAT, BLOCKS, MANIFEST, DEVICE

OUTDIR = D / "iterations" / "plat_04_ensemble"; OUTDIR.mkdir(parents=True, exist_ok=True)

FEATURES_7CH = D / "features_pit_9t_05.tif"
CKPT_01 = D / "iterations" / "plat_01_tta_miou" / "best.pt"
CKPT_02 = D / "iterations" / "plat_02_smp_pretrained" / "best.pt"

PATCH = 384
OV = 96
N_CLASSES = 2
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
    print(f"[plat 01] loaded ep {ck['epoch']} plat IoU={ck['iou_plat']:.3f}")
    return model, np.asarray(ck["mu"], dtype=np.float32), np.asarray(ck["sd"], dtype=np.float32)


def load_model_02():
    ck = torch.load(CKPT_02, map_location=DEVICE, weights_only=False)
    n_ch = len(ck["channels"])
    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights=None,
                     in_channels=n_ch, classes=N_CLASSES).to(DEVICE)
    model.load_state_dict(ck["state_dict"])
    model.eval()
    print(f"[plat 02] loaded ep {ck['epoch']} plat IoU={ck['iou_plat']:.3f}")
    return model, np.asarray(ck["mu"], dtype=np.float32), np.asarray(ck["sd"], dtype=np.float32)


def infer_ensemble():
    model_01, mu_01, sd_01 = load_model_01()
    model_02, mu_02, sd_02 = load_model_02()
    with rasterio.open(FEATURES_7CH) as r:
        H, W = r.height, r.width
    step = PATCH - OV
    rs = sorted(set(list(range(0, H - PATCH + 1, step)) + [H - PATCH]))
    cs = sorted(set(list(range(0, W - PATCH + 1, step)) + [W - PATCH]))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x, both models)")
    prob_mean = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    src = rasterio.open(FEATURES_7CH)
    BATCH = 4
    buf_x01, buf_x02, buf_pos = [], [], []
    def flush():
        if not buf_x01: return
        x01 = torch.from_numpy(np.stack(buf_x01)).to(DEVICE)
        x02 = torch.from_numpy(np.stack(buf_x02)).to(DEVICE)
        with torch.no_grad():
            p_a = tta_predict_batch(model_01, x01).cpu().numpy()
            p_b = tta_predict_batch(model_02, x02).cpu().numpy()
        p_mean = 0.5 * (p_a + p_b)
        for arr, (r0, c0) in zip(p_mean, buf_pos):
            prob_mean[:, r0:r0+PATCH, c0:c0+PATCH] += arr
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x01.clear(); buf_x02.clear(); buf_pos.clear()
    t0 = time.time()
    for r0 in rs:
        for c0 in cs:
            f = src.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
            f = np.where(np.isfinite(f), f, 0.0)
            f01 = (f - mu_01[:, None, None]) / sd_01[:, None, None]
            f02 = (f - mu_02[:, None, None]) / sd_02[:, None, None]
            buf_x01.append(f01); buf_x02.append(f02); buf_pos.append((r0, c0))
            if len(buf_x01) >= BATCH: flush()
    flush(); src.close()
    print(f"  ensemble inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1)
    prob_mean = prob_mean / cnt
    argmax_mean = prob_mean.argmax(0).astype(np.uint8)

    with rasterio.open(LABELS_PLAT) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(OUTDIR / "ensemble_mean_prob.tif", "w", **p1) as d:
        d.write(prob_mean[1], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "ensemble_mean_argmax.tif", "w", **p2) as d:
        d.write(argmax_mean, 1)
    return argmax_mean


def test_eval(argmax):
    with rasterio.open(LABELS_PLAT) as r:
        labels = r.read(1); H, W = r.height, r.width; tf = r.transform
    blocks = gpd.read_file(BLOCKS, layer="blocks")
    tbm = rasterize([(g, 1) for g in blocks[blocks.split == "test"].geometry],
                    out_shape=(H, W), transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & tbm).sum()); union = int(((p | t) & tbm).sum())
    pix_iou = inter / union if union else None
    man = pd.read_csv(MANIFEST)
    tp = man[man.split == "test"]
    plat = gpd.read_file(ANN, layer="plat")
    rows = []
    for _, row in tp.iterrows():
        pid = int(row.plat_id)
        g = plat[plat.plat_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        pad = 15.0
        win = from_bounds(minx-pad, miny-pad, maxx+pad, maxy+pad, tf)
        r0 = max(int(win.row_off), 0); c0 = max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0: continue
        sl = labels[r0:r0+wh, c0:c0+ww] == 1
        sp = argmax[r0:r0+wh, c0:c0+ww] == 1
        recall = float((sl & sp).sum() / max(sl.sum(), 1))
        inter2 = int((sl & sp).sum()); union2 = int((sl | sp).sum())
        loc_iou = inter2 / union2 if union2 else None
        rows.append({"plat_id": pid, "recall": recall, "local_iou": loc_iou})
    df = pd.DataFrame(rows)
    metrics = {
        "pixel_iou_test": pix_iou, "n_test_plats": len(df),
        "n_detected_any_10pct": int((df.recall > 0.1).sum()),
        "n_iou_gt_0.3": int((df.local_iou.fillna(0) > 0.3).sum()),
        "mean_local_iou": float(df.local_iou.mean()),
        "median_local_iou": float(df.local_iou.median()),
        "mean_recall": float(df.recall.mean()),
    }
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    df.to_csv(OUTDIR / "test_per_plat.csv", index=False)
    print(f"\nTEST pixel IoU: {pix_iou:.3f}")
    print(f"Per-plat ({len(df)} plats):")
    print(f"  mean local IoU:   {metrics['mean_local_iou']:.3f}")
    print(f"  median local IoU: {metrics['median_local_iou']:.3f}")
    print(f"  detected (>=10%): {metrics['n_detected_any_10pct']}/{len(df)}")
    print(f"  local IoU > 0.3:  {metrics['n_iou_gt_0.3']}/{len(df)}")
    return metrics


def main():
    print(f"Device: {DEVICE}")
    argmax = infer_ensemble()
    test_eval(argmax)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
