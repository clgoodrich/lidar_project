"""Pit semantic segmentation v2: 3-class (bg / floor / wall) on 0.5 m polygon labels.

Inputs:
    data/derivatives/9t/features_pit_9t_05.tif    (7 bands, float32, NaN nodata)
    data/derivatives/9t/labels_pit_9t_05.tif      (uint8: 0=bg, 1=floor, 2=wall)
    data/derivatives/9t/feature_stats.json        (per-band mean/std from TRAIN blocks)
    data/derivatives/9t/pit_blocks_9t.gpkg        (12x12 spatial-block grid + split)
    data/derivatives/9t/pit_dataset_manifest.csv  (per-pit centroid + split)

Outputs (under data/derivatives/9t/pit_unet_v2/):
    best.pt              best-val checkpoint (state_dict + cfg + norm stats)
    train_log.csv        per-epoch metrics
    sample_preds.png     qualitative predictions on a few val pits

Run:
    python notebooks/wellsight/pits/_pit_unet_v2.py --epochs 40 --batch 16
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import pandas as pd
import rasterio
from rasterio.windows import Window
import geopandas as gpd
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

import sys
sys.path.insert(0, str(Path(__file__).parent))
# Import shared UNet from this folder (the small one with 7-channel input would clash
# with v1's signature; we declare a local UNet below to keep this script standalone).

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
D = ROOT / "data" / "derivatives" / "9t"
OUTDIR = D / "pit_unet_v2"
OUTDIR.mkdir(exist_ok=True)

FEATURES = D / "features_pit_9t_05.tif"
LABELS = D / "labels_pit_9t_05.tif"
STATS = D / "feature_stats.json"
BLOCKS = D / "pit_blocks_9t.gpkg"
MANIFEST = D / "pit_dataset_manifest.csv"

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
PATCH = 256          # 256 px = 128 m at 0.5 m/px
N_CLASSES = 3        # bg / floor / wall
N_CH = 7
BG_PER_POS = 1       # background samples per pit-centered sample per epoch


# ===================== model =====================
def cbr(ic, oc):
    return nn.Sequential(
        nn.Conv2d(ic, oc, 3, padding=1, bias=False),
        nn.BatchNorm2d(oc), nn.ReLU(inplace=True),
        nn.Conv2d(oc, oc, 3, padding=1, bias=False),
        nn.BatchNorm2d(oc), nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    def __init__(self, in_ch=7, n_classes=3, base=32):
        super().__init__()
        self.d1 = cbr(in_ch, base);     self.d2 = cbr(base, base*2)
        self.d3 = cbr(base*2, base*4);  self.d4 = cbr(base*4, base*8)
        self.bot = cbr(base*8, base*16)
        self.up4 = nn.ConvTranspose2d(base*16, base*8, 2, 2); self.u4 = cbr(base*16, base*8)
        self.up3 = nn.ConvTranspose2d(base*8, base*4, 2, 2);  self.u3 = cbr(base*8, base*4)
        self.up2 = nn.ConvTranspose2d(base*4, base*2, 2, 2);  self.u2 = cbr(base*4, base*2)
        self.up1 = nn.ConvTranspose2d(base*2, base, 2, 2);    self.u1 = cbr(base*2, base)
        self.out = nn.Conv2d(base, n_classes, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x):
        d1 = self.d1(x); d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2)); d4 = self.d4(self.pool(d3))
        b = self.bot(self.pool(d4))
        u4 = self.u4(torch.cat([self.up4(b), d4], 1))
        u3 = self.u3(torch.cat([self.up3(u4), d3], 1))
        u2 = self.u2(torch.cat([self.up2(u3), d2], 1))
        u1 = self.u1(torch.cat([self.up1(u2), d1], 1))
        return self.out(u1)


# ===================== focal loss =====================
class FocalCE(nn.Module):
    def __init__(self, alpha=(0.05, 0.475, 0.475), gamma=2.0, ignore=255):
        super().__init__()
        self.gamma = gamma
        self.ignore = ignore
        self.register_buffer("alpha", torch.tensor(alpha, dtype=torch.float32))

    def forward(self, logits, target):
        log_p = torch.log_softmax(logits, 1)
        p = log_p.exp()
        valid = (target != self.ignore)
        t = target.clone(); t[~valid] = 0
        oh = torch.nn.functional.one_hot(t, logits.shape[1]).permute(0, 3, 1, 2).float()
        focal = (1 - p) ** self.gamma
        a = self.alpha.view(1, -1, 1, 1)
        loss = -(oh * a * focal * log_p).sum(1)
        return loss[valid].mean()


def per_class_iou(pred, target, n=3, ignore=255):
    out = []
    valid = target != ignore
    for c in range(n):
        p = (pred == c) & valid
        t = (target == c) & valid
        inter = (p & t).sum().item()
        union = (p | t).sum().item()
        out.append(float("nan") if union == 0 else inter / union)
    return out


# ===================== dataset =====================
class PitTiles(Dataset):
    """Samples 256x256 windows from the 9t tile.

    Two modes per epoch:
      - 'pit-centered' windows: one per pit in this split, with random jitter.
      - 'background' windows: BG_PER_POS per pit, random within split's blocks.
    """
    def __init__(self, split, manifest, blocks_gdf, transform, mu, sd, augment=True):
        self.split = split
        self.augment = augment
        self.transform = transform  # affine from rasterio
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        # Pit centroids in this split
        m = manifest[manifest.split == split].copy()
        self.pits = m[["centroid_x", "centroid_y"]].values  # (N, 2)
        # Block geometries for this split (for bg sampling)
        bs = blocks_gdf[blocks_gdf.split == split]
        self.block_bounds = np.array([g.bounds for g in bs.geometry])  # (B, 4)
        # Open rasters lazily per-worker via __getitem__
        self._feat = None
        self._lbl = None

    def _open(self):
        if self._feat is None:
            self._feat = rasterio.open(FEATURES)
            self._lbl = rasterio.open(LABELS)

    def __len__(self):
        return len(self.pits) * (1 + BG_PER_POS)

    def _world_to_window(self, cx, cy):
        # Affine: x = a*col + b*row + c;  y = d*col + e*row + f
        a, b, c, d, e, f = (self.transform.a, self.transform.b, self.transform.c,
                            self.transform.d, self.transform.e, self.transform.f)
        col = (cx - c) / a
        row = (cy - f) / e
        return row, col

    def __getitem__(self, idx):
        self._open()
        rng = np.random.default_rng()
        is_pit = idx < len(self.pits)
        if is_pit:
            cx, cy = self.pits[idx]
            jitter_m = (rng.uniform(-30, 30), rng.uniform(-30, 30))
            cx += jitter_m[0]; cy += jitter_m[1]
        else:
            bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
            cx = rng.uniform(bb[0], bb[2])
            cy = rng.uniform(bb[1], bb[3])

        row, col = self._world_to_window(cx, cy)
        r0 = int(round(row)) - PATCH // 2
        c0 = int(round(col)) - PATCH // 2

        # Clamp to raster bounds (9000 x 9000)
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(r0, 0, H - PATCH))
        c0 = int(np.clip(c0, 0, W - PATCH))

        win = Window(c0, r0, PATCH, PATCH)
        feat = self._feat.read(window=win).astype(np.float32)  # (C, H, W)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        # NaN -> 0, then normalize
        feat = np.where(np.isfinite(feat), feat, 0.0)
        feat = (feat - self.mu[:, None, None]) / self.sd[:, None, None]
        # Light augmentation
        if self.augment:
            k = rng.integers(0, 4)
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lbl = np.rot90(lbl, k).copy()
            if rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lbl = lbl[:, ::-1].copy()
        return torch.from_numpy(feat), torch.from_numpy(lbl)


# ===================== train / eval =====================
def run_epoch(model, loader, opt, loss_fn, scaler, train=True):
    model.train() if train else model.eval()
    total_loss = 0.0
    inter = np.zeros(N_CLASSES); union = np.zeros(N_CLASSES)
    n_batches = 0
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            if train:
                opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=DEVICE.type == "cuda"):
                logits = model(x)
                loss = loss_fn(logits, y)
            if train:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            total_loss += loss.item()
            n_batches += 1
            pred = logits.argmax(1)
            for c in range(N_CLASSES):
                pm = pred == c; tm = y == c
                inter[c] += (pm & tm).sum().item()
                union[c] += (pm | tm).sum().item()
    iou = [(inter[c] / union[c]) if union[c] else float("nan") for c in range(N_CLASSES)]
    return total_loss / max(n_batches, 1), iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--smoke", action="store_true", help="single short epoch, tiny subset")
    args = ap.parse_args()

    print(f"Device: {DEVICE}")
    print(f"Reading manifest, blocks, stats…")
    manifest = pd.read_csv(MANIFEST)
    blocks_gdf = gpd.read_file(BLOCKS, layer="blocks")
    stats = json.loads(Path(STATS).read_text())
    # Channel order must match _stack_features.py
    ch_order = ["lrm_25", "lrm_5", "slope", "tpi_05",
                "openness_pos", "openness_neg", "roughness_11"]
    mu = np.array([stats[c]["mean"] for c in ch_order], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], 1e-6) for c in ch_order], dtype=np.float32)

    with rasterio.open(FEATURES) as r:
        tf = r.transform
    train_ds = PitTiles("train", manifest, blocks_gdf, tf, mu, sd, augment=True)
    val_ds = PitTiles("val", manifest, blocks_gdf, tf, mu, sd, augment=False)
    print(f"train pits={len(train_ds.pits)} tiles_per_epoch={len(train_ds)}")
    print(f"val   pits={len(val_ds.pits)} tiles_per_epoch={len(val_ds)}")

    if args.smoke:
        args.epochs = 1

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.workers, pin_memory=True)

    model = UNet(in_ch=N_CH, n_classes=N_CLASSES, base=32).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"UNet params: {n_params/1e6:.2f} M")

    loss_fn = FocalCE(alpha=(0.05, 0.475, 0.475), gamma=2.0).to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    log_rows = []
    best_val = float("inf")
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, tr_iou = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False)
        sched.step()
        dt = time.time() - t0
        miou = np.nanmean(va_iou[1:])  # exclude bg
        msg = (f"ep {ep:3d}/{args.epochs}  "
               f"tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
               f"va_iou bg={va_iou[0]:.3f} floor={va_iou[1]:.3f} wall={va_iou[2]:.3f}  "
               f"miou(pit)={miou:.3f}  {dt:.1f}s")
        print(msg)
        log_rows.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                         "iou_bg": va_iou[0], "iou_floor": va_iou[1], "iou_wall": va_iou[2],
                         "miou_pit": miou, "sec": dt})
        if va_loss < best_val:
            best_val = va_loss
            torch.save({"state_dict": model.state_dict(),
                        "mu": mu, "sd": sd, "channels": ch_order,
                        "patch": PATCH, "epoch": ep},
                       OUTDIR / "best.pt")
            print("    -> new best, saved")

    pd.DataFrame(log_rows).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"Done. Best val_loss={best_val:.4f}. Outputs in {OUTDIR}")


if __name__ == "__main__":
    main()
