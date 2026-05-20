"""Plat iter 02 — SMP U-Net + ImageNet-pretrained ResNet34, 7-ch input.

Same data, loss, schedule as plat iter 01. Only the architecture changes:
  smp.Unet(encoder_name='resnet34', encoder_weights='imagenet',
           in_channels=7, classes=2)

Reuses PlatTiles (PATCH = 384, BG_PER_POS = 1) and the focal loss from _plat_unet.
"""
import argparse, json, time, sys
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window, from_bounds
from rasterio.features import rasterize
import geopandas as gpd
import torch
from torch.utils.data import DataLoader
import segmentation_models_pytorch as smp

sys.path.insert(0, str(Path(__file__).parent.parent))
from _plat_unet import (
    FocalCE, PlatTiles, run_epoch,
    D, ANN, FEATURES, LABELS_PLAT, STATS, BLOCKS, MANIFEST,
    DEVICE, PATCH, N_CLASSES, N_CH,
)

OUTDIR = D / "iterations" / "plat_02_smp_pretrained"; OUTDIR.mkdir(parents=True, exist_ok=True)
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


def infer_full(model, mu, sd):
    OV = 96
    with rasterio.open(FEATURES) as r:
        H, W = r.height, r.width
    step = PATCH - OV
    prob = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    rs = sorted(set(list(range(0, H - PATCH + 1, step)) + [H - PATCH]))
    cs = sorted(set(list(range(0, W - PATCH + 1, step)) + [W - PATCH]))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x)")
    src = rasterio.open(FEATURES); model.eval()
    BATCH = 4; buf_x, buf_pos = [], []
    def flush():
        if not buf_x: return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad():
            p = tta_predict_batch(model, x).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+PATCH, c0:c0+PATCH] += arr
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x.clear(); buf_pos.clear()
    t0 = time.time()
    for r0 in rs:
        for c0 in cs:
            f = src.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
            f = np.where(np.isfinite(f), f, 0.0)
            f = (f - mu[:, None, None]) / sd[:, None, None]
            buf_x.append(f); buf_pos.append((r0, c0))
            if len(buf_x) >= BATCH: flush()
    flush(); src.close()
    print(f"  TTA inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1); prob = prob / cnt
    argmax = prob.argmax(0).astype(np.uint8)
    with rasterio.open(LABELS_PLAT) as r:
        profile = r.profile.copy()
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(OUTDIR / "plat_prob.tif", "w", **p1) as d:
        d.write(prob[1], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "plat_argmax.tif", "w", **p2) as d:
        d.write(argmax, 1)
    return prob, argmax


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
        rows.append({"plat_id": pid, "recall": recall, "local_iou": loc_iou,
                     "area_m2": float(row.area_m2)})
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
    return df, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    print(f"Device: {DEVICE}")
    manifest = pd.read_csv(MANIFEST)
    blocks_gdf = gpd.read_file(BLOCKS, layer="blocks")
    stats = json.loads(Path(STATS).read_text())
    ch_order = ["lrm_25", "lrm_5", "slope", "tpi_05", "openness_pos", "openness_neg", "roughness_11"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)
    with rasterio.open(FEATURES) as r: tf = r.transform

    train_ds = PlatTiles("train", manifest, blocks_gdf, tf, mu, sd, augment=True)
    val_ds = PlatTiles("val", manifest, blocks_gdf, tf, mu, sd, augment=False)
    print(f"train plats={len(train_ds.plats)} tiles_per_epoch={len(train_ds)}")
    print(f"val   plats={len(val_ds.plats)} tiles_per_epoch={len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    print(f"Building SMP U-Net (encoder={ENCODER_NAME}, ImageNet, in_ch={N_CH}, classes={N_CLASSES})")
    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights="imagenet",
                     in_channels=N_CH, classes=N_CLASSES).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"SMP UNet params: {n_params/1e6:.2f} M")
    loss_fn = FocalCE(alpha=(0.15, 0.85), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    log = []; best_iou = -1.0
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, _ = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False)
        sched.step(); dt = time.time() - t0
        iou_plat = va_iou[1]
        print(f"ep {ep:3d}/{args.epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
              f"va_iou bg={va_iou[0]:.3f} plat={va_iou[1]:.3f}  {dt:.1f}s")
        log.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                    "iou_bg": va_iou[0], "iou_plat": va_iou[1], "sec": dt})
        if iou_plat > best_iou:
            best_iou = iou_plat
            torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                        "channels": ch_order, "patch": PATCH, "epoch": ep,
                        "iou_plat": iou_plat, "encoder": ENCODER_NAME},
                       OUTDIR / "best.pt")
            print("    -> new best, saved")
    pd.DataFrame(log).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"\nBest val plat IoU: {best_iou:.3f}")

    model = smp.Unet(encoder_name=ENCODER_NAME, encoder_weights=None,
                     in_channels=N_CH, classes=N_CLASSES).to(DEVICE)
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    print(f"\nLoaded best ep {ck['epoch']} (plat IoU={ck['iou_plat']:.3f}). TTA inference...")
    prob, argmax = infer_full(model, mu, sd)
    test_eval(argmax)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
