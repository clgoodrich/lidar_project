"""Binary plat segmentation U-Net (plat / background) at 0.5 m.

Reuses the v2 UNet architecture from pits. 7 input channels, 2 output classes.

Outputs:
    data/derivatives/9t/plat_unet/best.pt
    data/derivatives/9t/plat_unet/train_log.csv
    data/derivatives/9t/plat_unet/plat_prob.tif       (full-tile probability)
    data/derivatives/9t/plat_unet/plat_argmax.tif
    data/derivatives/9t/plat_unet/test_metrics.json
    data/derivatives/9t/plat_unet/test_preds.png
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
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap

sys.path.insert(0, str(Path(__file__).parent.parent / "pits"))
from _pit_unet_v2 import UNet, FocalCE  # reuse

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
ANN = ROOT / "data" / "derivatives" / "annotations" / "annotations_proj.gpkg"
OUTDIR = D / "plat_unet"; OUTDIR.mkdir(exist_ok=True)

FEATURES = D / "features_pit_9t_05.tif"
LABELS_PLAT = D / "labels_plat_9t_05.tif"
STATS = D / "feature_stats.json"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "plat_dataset_manifest.csv"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 384  # plats are bigger than pits -> larger context window
N_CLASSES = 2
N_CH = 7
BG_PER_POS = 1


class PlatTiles(Dataset):
    def __init__(self, split, manifest, blocks_gdf, transform, mu, sd, augment=True):
        self.augment = augment
        self.transform = transform
        self.mu = mu.astype(np.float32); self.sd = sd.astype(np.float32)
        m = manifest[manifest.split == split]
        self.plats = m[["centroid_x", "centroid_y"]].values
        bs = blocks_gdf[blocks_gdf.split == split]
        self.block_bounds = np.array([g.bounds for g in bs.geometry])
        self._feat = None; self._lbl = None

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(FEATURES)
            self._lbl = rasterio.open(LABELS_PLAT)

    def __len__(self):
        return len(self.plats) * (1 + BG_PER_POS)

    def _w2p(self, x, y):
        tf = self.transform
        col = (x - tf.c) / tf.a
        row = (y - tf.f) / tf.e
        return row, col

    def __getitem__(self, idx):
        self._open()
        rng = np.random.default_rng()
        if idx < len(self.plats):
            cx, cy = self.plats[idx]
            cx += rng.uniform(-40, 40); cy += rng.uniform(-40, 40)
        else:
            bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
            cx = rng.uniform(bb[0], bb[2]); cy = rng.uniform(bb[1], bb[3])
        row, col = self._w2p(cx, cy)
        r0 = int(round(row)) - PATCH // 2
        c0 = int(round(col)) - PATCH // 2
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(r0, 0, H - PATCH)); c0 = int(np.clip(c0, 0, W - PATCH))
        win = Window(c0, r0, PATCH, PATCH)
        feat = self._feat.read(window=win).astype(np.float32)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        if self.augment:
            k = rng.integers(0, 4)
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lbl = np.rot90(lbl, k).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lbl = lbl[:, ::-1].copy()
        return torch.from_numpy(feat), torch.from_numpy(lbl)


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
                logits = model(x)
                loss = loss_fn(logits, y)
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


def infer_full(model, mu, sd):
    PATCH_I = PATCH; OV = 96
    with rasterio.open(FEATURES) as r:
        H, W = r.height, r.width; profile = r.profile.copy()
    step = PATCH_I - OV
    prob = np.zeros((N_CLASSES, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    rs = list(range(0, H - PATCH_I + 1, step)) + [H - PATCH_I]
    cs = list(range(0, W - PATCH_I + 1, step)) + [W - PATCH_I]
    rs = sorted(set(rs)); cs = sorted(set(cs))
    print(f"Inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches")
    src = rasterio.open(FEATURES); model.eval()
    buf_x, buf_pos = [], []
    BATCH = 8
    def flush():
        if not buf_x: return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad(), torch.amp.autocast(device_type="cuda", enabled=DEVICE.type=="cuda"):
            p = torch.softmax(model(x), 1).cpu().numpy()
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
    print(f"  inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1); prob = prob / cnt
    argmax = prob.argmax(0).astype(np.uint8)
    # Write
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
    tbm = rasterize([(g,1) for g in blocks[blocks.split=="test"].geometry],
                    out_shape=(H,W), transform=tf, fill=0, dtype="uint8").astype(bool)
    p = argmax == 1; t = labels == 1
    inter = int((p & t & tbm).sum()); union = int(((p | t) & tbm).sum())
    pix_iou = inter/union if union else None
    # Per-plat recall
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
        r0, c0 = max(int(win.row_off), 0), max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        if wh <= 0 or ww <= 0: continue
        sl = labels[r0:r0+wh, c0:c0+ww] == 1
        sp = argmax[r0:r0+wh, c0:c0+ww] == 1
        recall = float((sl & sp).sum() / max(sl.sum(), 1))
        inter2 = int((sl & sp).sum()); union2 = int((sl | sp).sum())
        loc_iou = inter2/union2 if union2 else None
        rows.append({"plat_id": pid, "recall": recall, "local_iou": loc_iou,
                     "area_m2": float(row.area_m2)})
    df = pd.DataFrame(rows)
    metrics = {"pixel_iou_test": pix_iou, "n_test_plats": len(df),
               "n_detected_any_10pct": int((df.recall > 0.1).sum()),
               "n_iou_gt_0.3": int((df.local_iou.fillna(0) > 0.3).sum()),
               "mean_local_iou": float(df.local_iou.mean()),
               "mean_recall": float(df.recall.mean())}
    (OUTDIR / "test_metrics.json").write_text(json.dumps(metrics, indent=2))
    df.to_csv(OUTDIR / "test_per_plat.csv", index=False)
    print(f"\nTEST pixel IoU: {pix_iou:.3f}")
    print(f"Per-plat ({len(df)} plats): mean_recall={df.recall.mean():.3f}  "
          f"mean_local_iou={df.local_iou.mean():.3f}")
    print(f"  detected (>=10% recall): {metrics['n_detected_any_10pct']}/{len(df)}")
    print(f"  local IoU > 0.3:         {metrics['n_iou_gt_0.3']}/{len(df)}")
    return df, metrics


def render_test_grid(df, argmax, n=6):
    if len(df) == 0: return
    df_sorted = df.sort_values("local_iou").head(n).reset_index(drop=True)
    plat = gpd.read_file(ANN, layer="plat")
    with rasterio.open(D / "hillshade_9t_05.tif") as r:
        tf = r.transform; H, W = r.height, r.width; hs_full = r.read(1)
    with rasterio.open(LABELS_PLAT) as r:
        lbl_full = r.read(1)
    cmap_lbl = ListedColormap(["#00000000", "#ff3333aa"])
    cmap_pred = ListedColormap(["#00000000", "#00ddffcc"])
    fig, axes = plt.subplots(n, 2, figsize=(7, 3.5*n))
    if n == 1: axes = axes[None, :]
    for i, row in df_sorted.iterrows():
        pid = int(row.plat_id)
        g = plat[plat.plat_id == pid].geometry.iloc[0]
        minx, miny, maxx, maxy = g.bounds
        pad = 15.0
        win = from_bounds(minx-pad, miny-pad, maxx+pad, maxy+pad, tf)
        r0, c0 = max(int(win.row_off), 0), max(int(win.col_off), 0)
        wh = min(int(win.height), H - r0); ww = min(int(win.width), W - c0)
        hs = hs_full[r0:r0+wh, c0:c0+ww]
        sl = lbl_full[r0:r0+wh, c0:c0+ww]
        sp = argmax[r0:r0+wh, c0:c0+ww]
        for ax in axes[i]: ax.set_xticks([]); ax.set_yticks([])
        axes[i,0].imshow(hs, cmap="gray"); axes[i,0].imshow(sl, cmap=cmap_lbl, vmin=0, vmax=1)
        axes[i,0].set_title(f"plat {pid}  LABEL  IoU={row.local_iou:.2f}", fontsize=8)
        axes[i,1].imshow(hs, cmap="gray"); axes[i,1].imshow(sp, cmap=cmap_pred, vmin=0, vmax=1)
        axes[i,1].set_title(f"plat {pid}  PRED  recall={row.recall:.2f}", fontsize=8)
    plt.tight_layout()
    plt.savefig(OUTDIR / "test_preds.png", dpi=110, bbox_inches="tight")
    plt.close()


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
    ch_order = ["lrm_25","lrm_5","slope","tpi_05","openness_pos","openness_neg","roughness_11"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)
    with rasterio.open(FEATURES) as r: tf = r.transform
    train_ds = PlatTiles("train", manifest, blocks_gdf, tf, mu, sd, augment=True)
    val_ds = PlatTiles("val", manifest, blocks_gdf, tf, mu, sd, augment=False)
    print(f"train plats={len(train_ds.plats)} tiles_per_epoch={len(train_ds)}")
    print(f"val   plats={len(val_ds.plats)} tiles_per_epoch={len(val_ds)}")
    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False, num_workers=0, pin_memory=True)

    model = UNet(in_ch=N_CH, n_classes=N_CLASSES, base=32).to(DEVICE)
    loss_fn = FocalCE(alpha=(0.15, 0.85), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type=="cuda")

    log = []; best_miou = -1.0
    for ep in range(1, args.epochs+1):
        t0 = time.time()
        tr_loss, _ = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False)
        sched.step(); dt = time.time()-t0
        miou_plat = va_iou[1]
        msg = (f"ep {ep:3d}/{args.epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
               f"va_iou bg={va_iou[0]:.3f} plat={va_iou[1]:.3f}  {dt:.1f}s")
        print(msg)
        log.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                    "iou_bg": va_iou[0], "iou_plat": va_iou[1], "sec": dt})
        if miou_plat > best_miou:
            best_miou = miou_plat
            torch.save({"state_dict": model.state_dict(), "mu": mu, "sd": sd,
                        "channels": ch_order, "patch": PATCH, "epoch": ep,
                        "iou_plat": miou_plat}, OUTDIR / "best.pt")
            print(f"    -> new best (plat IoU), saved")
    pd.DataFrame(log).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"\nBest plat IoU on val: {best_miou:.3f}")

    # Load best, infer, eval
    ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
    model.load_state_dict(ck["state_dict"])
    print(f"\nLoaded best (ep {ck['epoch']}). Running full-tile inference...")
    prob, argmax = infer_full(model, mu, sd)
    df, _ = test_eval(argmax)
    render_test_grid(df, argmax, n=min(6, len(df)))
    print(f"Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
