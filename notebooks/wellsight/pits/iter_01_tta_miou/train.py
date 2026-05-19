"""Iter 01 — TTA + miou_pit checkpoint criterion.

Same architecture and data as data/derivatives/9t/pit_unet_v2 baseline, with two changes:
  1) Save checkpoint by miou(pit) (mean of floor+wall IoU on val) instead of val_loss.
  2) Inference uses 8-fold test-time augmentation (4 rotations x 2 flips, averaged).

Outputs:
    data/derivatives/9t/iterations/01_tta_miou/best.pt
    data/derivatives/9t/iterations/01_tta_miou/train_log.csv
    data/derivatives/9t/iterations/01_tta_miou/pit_prob_floor.tif
    data/derivatives/9t/iterations/01_tta_miou/pit_prob_wall.tif
    data/derivatives/9t/iterations/01_tta_miou/pit_argmax.tif
    data/derivatives/9t/iterations/01_tta_miou/test_metrics.json
    data/derivatives/9t/iterations/01_tta_miou/test_per_pit.csv
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

sys.path.insert(0, str(Path(__file__).parent.parent))
from _pit_unet_v2 import UNet, FocalCE, PitTiles

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "iterations" / "01_tta_miou"; OUTDIR.mkdir(parents=True, exist_ok=True)

FEATURES = D / "features_pit_9t_05.tif"
LABELS = D / "labels_pit_9t_05.tif"
STATS = D / "feature_stats.json"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 256
N_CLASSES = 3
N_CH = 7


def run_epoch(model, loader, opt, loss_fn, scaler, train=True):
    model.train() if train else model.eval()
    total_loss = 0.0; n = 0
    inter = np.zeros(N_CLASSES); union = np.zeros(N_CLASSES)
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True); y = y.to(DEVICE, non_blocking=True)
            if train: opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type == "cuda"):
                logits = model(x); loss = loss_fn(logits, y)
            if train:
                scaler.scale(loss).backward(); scaler.step(opt); scaler.update()
            total_loss += loss.item(); n += 1
            pred = logits.argmax(1)
            for c in range(N_CLASSES):
                pm = pred == c; tm = y == c
                inter[c] += (pm & tm).sum().item()
                union[c] += (pm | tm).sum().item()
    iou = [(inter[c]/union[c]) if union[c] else float("nan") for c in range(N_CLASSES)]
    return total_loss / max(n, 1), iou


def tta_predict_batch(model, x):
    """Run 8-fold TTA on a batch of feature patches; return averaged softmax probs."""
    outs = []
    for k in range(4):
        for flip in (False, True):
            x_aug = x
            if k:
                x_aug = torch.rot90(x_aug, k=k, dims=(2, 3))
            if flip:
                x_aug = torch.flip(x_aug, dims=(3,))
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type == "cuda"):
                logits = model(x_aug)
            p = torch.softmax(logits, dim=1)
            # invert augs
            if flip:
                p = torch.flip(p, dims=(3,))
            if k:
                p = torch.rot90(p, k=-k, dims=(2, 3))
            outs.append(p.float())
    return torch.stack(outs, dim=0).mean(dim=0)


def infer_full(model, mu, sd):
    PATCH_I = PATCH; OV = 64
    with rasterio.open(FEATURES) as r:
        H, W = r.height, r.width; profile = r.profile.copy()
    step = PATCH_I - OV
    prob = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    rs = sorted(set(list(range(0, H - PATCH_I + 1, step)) + [H - PATCH_I]))
    cs = sorted(set(list(range(0, W - PATCH_I + 1, step)) + [W - PATCH_I]))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x)")
    src = rasterio.open(FEATURES); model.eval()
    BATCH = 8; buf_x, buf_pos = [], []
    def flush():
        if not buf_x: return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad():
            p = tta_predict_batch(model, x).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+PATCH_I, c0:c0+PATCH_I] += arr
            cnt[r0:r0+PATCH_I, c0:c0+PATCH_I] += 1
        buf_x.clear(); buf_pos.clear()
    t0 = time.time()
    for r0 in rs:
        for c0 in cs:
            f = src.read(window=Window(c0, r0, PATCH_I, PATCH_I)).astype(np.float32)
            f = np.where(np.isfinite(f), f, 0.0)
            f = (f - mu[:, None, None]) / sd[:, None, None]
            buf_x.append(f); buf_pos.append((r0, c0))
            if len(buf_x) >= BATCH: flush()
    flush(); src.close()
    print(f"  TTA inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1); prob = prob / cnt
    argmax = prob.argmax(0).astype(np.uint8)
    p1 = profile.copy()
    p1.update(dtype="float32", count=1, compress="deflate", predictor=3,
              tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    for cls, name in [(1, "pit_prob_floor.tif"), (2, "pit_prob_wall.tif")]:
        with rasterio.open(OUTDIR / name, "w", **p1) as d: d.write(prob[cls], 1)
    p2 = profile.copy()
    p2.update(dtype="uint8", count=1, compress="deflate", predictor=2,
              tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(OUTDIR / "pit_argmax.tif", "w", **p2) as d: d.write(argmax, 1)
    return prob, argmax


def test_eval(argmax):
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
    pit_wall_g = gpd.read_file(ANN, layer="pit_wall")
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
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2, default=float))
    df.to_csv(OUTDIR / "test_per_pit.csv", index=False)
    print(f"\nTEST pixel IoU: bg={pix_iou['bg']:.3f}  floor={pix_iou['floor']:.3f}  wall={pix_iou['wall']:.3f}")
    print(f"Per-pit ({len(df)} pits):")
    print(f"  mean local IoU:   {metrics['mean_pit_iou_local']:.3f}")
    print(f"  median local IoU: {metrics['median_pit_iou_local']:.3f}")
    print(f"  detected (>=10%): {metrics['n_detected_any']}/{len(df)}")
    print(f"  local IoU > 0.3:  {metrics['n_solid_iou_gt_0.3']}/{len(df)}")
    return df, metrics


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    args = ap.parse_args()
    print(f"Device: {DEVICE}")
    manifest = pd.read_csv(MANIFEST)
    blocks_gdf = gpd.read_file(BLOCKS, layer="blocks")
    stats = json.loads(Path(STATS).read_text())
    ch_order = ["lrm_25","lrm_5","slope","tpi_05","openness_pos","openness_neg","roughness_11"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)
    with rasterio.open(FEATURES) as r: tf = r.transform

    train_ds = PitTiles("train", manifest, blocks_gdf, tf, mu, sd, augment=True)
    val_ds = PitTiles("val", manifest, blocks_gdf, tf, mu, sd, augment=False)
    print(f"train pits={len(train_ds.pits)} tiles_per_epoch={len(train_ds)}")
    print(f"val   pits={len(val_ds.pits)} tiles_per_epoch={len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    model = UNet(in_ch=N_CH, n_classes=N_CLASSES, base=32).to(DEVICE)
    loss_fn = FocalCE(alpha=(0.05, 0.475, 0.475), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    log = []; best_miou = -1.0
    for ep in range(1, args.epochs+1):
        t0 = time.time()
        tr_loss, tr_iou = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False)
        sched.step(); dt = time.time()-t0
        miou = float(np.nanmean(va_iou[1:]))  # CHANGED: pit-classes only (excludes bg)
        msg = (f"ep {ep:3d}/{args.epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
               f"va_iou bg={va_iou[0]:.3f} floor={va_iou[1]:.3f} wall={va_iou[2]:.3f}  "
               f"miou(pit)={miou:.3f}  {dt:.1f}s")
        print(msg)
        log.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                    "iou_bg": va_iou[0], "iou_floor": va_iou[1], "iou_wall": va_iou[2],
                    "miou_pit": miou, "sec": dt})
        if miou > best_miou:  # CHANGED: save by miou_pit not va_loss
            best_miou = miou
            torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                        "channels": ch_order, "patch": PATCH, "epoch": ep,
                        "miou_pit": miou},
                       OUTDIR / "best.pt")
            print(f"    -> new best miou(pit)={miou:.3f}, saved")
    pd.DataFrame(log).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"\nBest val miou(pit): {best_miou:.3f}")

    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    print(f"\nLoaded best from ep {ck['epoch']} (miou={ck['miou_pit']:.3f}). Running TTA inference...")
    prob, argmax = infer_full(model, mu, sd)
    test_eval(argmax)
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
