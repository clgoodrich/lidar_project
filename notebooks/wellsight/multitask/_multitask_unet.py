"""Multi-task U-Net for pit / road / plat joint segmentation at 0.5 m.

Combines everything the per-task trainers learn separately:

  * pit head   (3 classes: bg / floor / wall)  -- from labels_pit_9t_05.tif
  * road head  (2 classes: bg / road)          -- from labels_road_9t_05.tif
  * plat head  (2 classes: bg / plat)          -- from labels_plat_9t_05.tif

Sampling policies (cycled per __getitem__, +1 random-background slot):
    pit centroid (jitter 30 m)        -- centers on a pit
    plat centroid (jitter 40 m)       -- centers on a well pad
    road midpoint (jitter 30 m)       -- centers on a road line
    not_road midpoint (jitter 30 m)   -- HARD NEGATIVE for the road head
    random block-interior background

A single shared encoder + bottleneck feeds three parallel decoder/output
heads. Each head's FocalCE loss is weighted, summed, and backpropped.

Outputs under ``data/derivatives/tiles/9t/multitask_unet/``:
    best.pt              best-val checkpoint (state_dict + cfg + norm stats)
    train_log.csv        per-epoch metrics with one IoU column per head class
    pit_prob.tif, pit_argmax.tif, road_prob.tif, road_argmax.tif,
    plat_prob.tif, plat_argmax.tif    full-tile inference outputs

Run:
    python notebooks/wellsight/multitask/_multitask_unet.py --epochs 40 --batch 8
    python notebooks/wellsight/multitask/_multitask_unet.py --smoke
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import torch
import torch.nn as nn
import torch.nn.functional as F
from rasterio.windows import Window
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, make_profile, write_tif
from _dl import (DEFAULT_CHANNELS, DEVICE, FocalCE, load_stats, normalize,
                 _cbr)  # type: ignore[attr-defined]

OUTDIR = DERIV_9T / "multitask_unet"
FEATURES = DERIV_9T / "features_pit_9t_05.tif"
LBL_PIT = DERIV_9T / "labels_pit_9t_05.tif"
LBL_ROAD = DERIV_9T / "labels_road_9t_05.tif"
LBL_PLAT = DERIV_9T / "labels_plat_9t_05.tif"
STATS = DERIV_9T / "feature_stats.json"
BLOCKS = DERIV_9T / "pit_blocks_9t.gpkg"
MAN_PIT = DERIV_9T / "pit_dataset_manifest.csv"
MAN_ROAD = DERIV_9T / "road_dataset_manifest.csv"
MAN_PLAT = DERIV_9T / "plat_dataset_manifest.csv"

# 384 px = 192 m at 0.5 m/px. Multiple of 16 (4-level encoder), and matches the
# plat trainer's window so well pads fit with context. Pits/roads centered in
# it still have plenty of background.
PATCH = 384
OVERLAP = 96

# Per-head class counts.
NC_PIT, NC_ROAD, NC_PLAT = 3, 2, 2

# Focal-loss class weights (mirrors the per-task trainers).
FOCAL_PIT = (0.05, 0.475, 0.475)
FOCAL_ROAD = (0.10, 0.90)
FOCAL_PLAT = (0.15, 0.85)
FOCAL_GAMMA = 2.0

# Per-task loss weighting. Pit gets the most weight because it's the
# downstream detection target; road/plat are auxiliary context.
LOSS_WEIGHTS = {"pit": 1.0, "road": 0.6, "plat": 0.6}


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

class MultiHeadUNet(nn.Module):
    """Shared 4-level encoder + bottleneck, with one decoder head per task.

    Each decoder is a standard U-Net upsampling path with skip connections
    back to the shared encoder. Heads are independent (their own params) so a
    bad gradient on one task doesn't fight the others' decoder features.
    """

    def __init__(self, in_ch: int = 7, base: int = 32,
                 head_classes: tuple[int, ...] = (NC_PIT, NC_ROAD, NC_PLAT)):
        super().__init__()
        self.d1 = _cbr(in_ch,    base)
        self.d2 = _cbr(base,     base * 2)
        self.d3 = _cbr(base * 2, base * 4)
        self.d4 = _cbr(base * 4, base * 8)
        self.bot = _cbr(base * 8, base * 16)
        self.pool = nn.MaxPool2d(2)
        self.heads = nn.ModuleList([_Head(base, nc) for nc in head_classes])

    def encode(self, x: torch.Tensor):
        d1 = self.d1(x)
        d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2))
        d4 = self.d4(self.pool(d3))
        b = self.bot(self.pool(d4))
        return d1, d2, d3, d4, b

    def forward(self, x: torch.Tensor) -> list[torch.Tensor]:
        skips = self.encode(x)
        return [h(skips) for h in self.heads]


class _Head(nn.Module):
    """Independent decoder + 1x1 output for one task."""

    def __init__(self, base: int, n_classes: int):
        super().__init__()
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, 2)
        self.u4 = _cbr(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, 2)
        self.u3 = _cbr(base * 8, base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, 2)
        self.u2 = _cbr(base * 4, base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2, base, 2, 2)
        self.u1 = _cbr(base * 2, base)
        self.out = nn.Conv2d(base, n_classes, 1)

    def forward(self, skips) -> torch.Tensor:
        d1, d2, d3, d4, b = skips
        u4 = self.u4(torch.cat([self.up4(b),  d4], 1))
        u3 = self.u3(torch.cat([self.up3(u4), d3], 1))
        u2 = self.u2(torch.cat([self.up2(u3), d2], 1))
        u1 = self.u1(torch.cat([self.up1(u2), d1], 1))
        return self.out(u1)


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------

class MultiLabelPatchSampler(Dataset):
    """Sample patches from the shared features raster + three label rasters.

    ``policies`` are ``(name, xy_array, jitter_m)``. Each __getitem__ cycles
    through them (plus one random-background slot) and returns
    ``(feat, lbl_pit, lbl_road, lbl_plat)`` -- all three label tiles for the
    same window, so every patch contributes to every head's loss.
    """

    def __init__(self, policies, block_bounds, transform, mu, sd,
                 *, patch: int = PATCH, augment: bool = True, seed: int = 0):
        self.policies = policies
        self.block_bounds = block_bounds
        self.transform = transform
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        self.patch = patch
        self.augment = augment
        self.seed = seed
        self.stride = len(policies) + 1
        max_pts = max((len(arr) for _, arr, _ in policies), default=0)
        self._epoch_len = max(max_pts, 1) * self.stride
        self._feat: Optional[rasterio.io.DatasetReader] = None
        self._lp: Optional[rasterio.io.DatasetReader] = None
        self._lr: Optional[rasterio.io.DatasetReader] = None
        self._la: Optional[rasterio.io.DatasetReader] = None
        self._rng: Optional[np.random.Generator] = None

    def __len__(self) -> int:
        return self._epoch_len

    def _open(self) -> None:
        if self._feat is None:
            self._feat = rasterio.open(FEATURES)
            self._lp = rasterio.open(LBL_PIT)
            self._lr = rasterio.open(LBL_ROAD)
            self._la = rasterio.open(LBL_PLAT)
        if self._rng is None:
            wi = torch.utils.data.get_worker_info()
            wid = wi.id if wi is not None else 0
            self._rng = np.random.default_rng(self.seed + wid)

    def _pick_center(self, idx: int) -> tuple[float, float]:
        slot = idx % self.stride
        rng = self._rng
        if slot < len(self.policies):
            _, pts, jitter = self.policies[slot]
            if len(pts):
                cx, cy = pts[rng.integers(0, len(pts))]
                cx += rng.uniform(-jitter, jitter)
                cy += rng.uniform(-jitter, jitter)
                return float(cx), float(cy)
        bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
        return rng.uniform(bb[0], bb[2]), rng.uniform(bb[1], bb[3])

    def __getitem__(self, idx: int):
        self._open()
        cx, cy = self._pick_center(idx)
        tf = self.transform
        col = int(round((cx - tf.c) / tf.a))
        row = int(round((cy - tf.f) / tf.e))
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(row - self.patch // 2, 0, H - self.patch))
        c0 = int(np.clip(col - self.patch // 2, 0, W - self.patch))
        win = Window(c0, r0, self.patch, self.patch)
        feat = self._feat.read(window=win).astype(np.float32)
        lp = self._lp.read(1, window=win).astype(np.int64)
        lr = self._lr.read(1, window=win).astype(np.int64)
        la = self._la.read(1, window=win).astype(np.int64)
        feat = normalize(feat, self.mu, self.sd)
        if self.augment:
            # Apply the same D4 transform to feat + all 3 label tiles so they
            # stay aligned.
            k = int(self._rng.integers(0, 4))
            if k:
                feat = np.rot90(feat, k, axes=(1, 2)).copy()
                lp = np.rot90(lp, k).copy()
                lr = np.rot90(lr, k).copy()
                la = np.rot90(la, k).copy()
            if self._rng.random() < 0.5:
                feat = feat[:, :, ::-1].copy()
                lp = lp[:, ::-1].copy()
                lr = lr[:, ::-1].copy()
                la = la[:, ::-1].copy()
        return (torch.from_numpy(feat),
                torch.from_numpy(lp),
                torch.from_numpy(lr),
                torch.from_numpy(la))


def build_dataset(split: str, blocks: gpd.GeoDataFrame, transform, mu, sd,
                  *, augment: bool, seed: int) -> MultiLabelPatchSampler:
    pit = pd.read_csv(MAN_PIT)
    road = pd.read_csv(MAN_ROAD)
    plat = pd.read_csv(MAN_PLAT)
    pit_pts = pit.loc[pit.split == split, ["centroid_x", "centroid_y"]].to_numpy()
    plat_pts = plat.loc[plat.split == split, ["centroid_x", "centroid_y"]].to_numpy()
    r = road[road.split == split]
    road_pts = r.loc[r.kind == "road", ["mid_x", "mid_y"]].to_numpy()
    not_road_pts = r.loc[r.kind == "not_road", ["mid_x", "mid_y"]].to_numpy()
    bounds = np.array([g.bounds for g in blocks.loc[blocks.split == split].geometry])
    policies = [
        ("pit",      pit_pts,      30.0),
        ("plat",     plat_pts,     40.0),
        ("road",     road_pts,     30.0),
        ("not_road", not_road_pts, 30.0),
    ]
    return MultiLabelPatchSampler(policies, bounds, transform, mu, sd,
                                  patch=PATCH, augment=augment, seed=seed)


# ---------------------------------------------------------------------------
# Training
# ---------------------------------------------------------------------------

def _iou_accum(pred: torch.Tensor, tgt: torch.Tensor, nc: int,
               inter: np.ndarray, union: np.ndarray, ignore: int = 255) -> None:
    valid = tgt != ignore
    for c in range(nc):
        pm = (pred == c) & valid
        tm = (tgt == c) & valid
        inter[c] += int((pm & tm).sum())
        union[c] += int((pm | tm).sum())


def _run_epoch(model, loader, opt, losses, scaler, *, train: bool):
    model.train(mode=train)
    use_amp = DEVICE.type == "cuda"
    totals = {"all": 0.0, "pit": 0.0, "road": 0.0, "plat": 0.0}
    n = 0
    inter = {"pit": np.zeros(NC_PIT), "road": np.zeros(NC_ROAD), "plat": np.zeros(NC_PLAT)}
    union = {"pit": np.zeros(NC_PIT), "road": np.zeros(NC_ROAD), "plat": np.zeros(NC_PLAT)}
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, yp, yr, ya in loader:
            x = x.to(DEVICE, non_blocking=True)
            yp = yp.to(DEVICE, non_blocking=True)
            yr = yr.to(DEVICE, non_blocking=True)
            ya = ya.to(DEVICE, non_blocking=True)
            if train:
                opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=use_amp):
                logit_p, logit_r, logit_a = model(x)
                l_pit = losses["pit"](logit_p, yp)
                l_road = losses["road"](logit_r, yr)
                l_plat = losses["plat"](logit_a, ya)
                loss = (LOSS_WEIGHTS["pit"] * l_pit
                        + LOSS_WEIGHTS["road"] * l_road
                        + LOSS_WEIGHTS["plat"] * l_plat)
            if train:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            totals["all"] += float(loss); totals["pit"] += float(l_pit)
            totals["road"] += float(l_road); totals["plat"] += float(l_plat)
            n += 1
            _iou_accum(logit_p.argmax(1), yp, NC_PIT, inter["pit"], union["pit"])
            _iou_accum(logit_r.argmax(1), yr, NC_ROAD, inter["road"], union["road"])
            _iou_accum(logit_a.argmax(1), ya, NC_PLAT, inter["plat"], union["plat"])
    iou = {k: [(inter[k][c] / union[k][c]) if union[k][c] else float("nan")
               for c in range(len(inter[k]))] for k in inter}
    means = {k: v / max(n, 1) for k, v in totals.items()}
    return means, iou


def write_full_tile(model, mu, sd, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    step = PATCH - OVERLAP
    with rasterio.open(FEATURES) as r:
        H, W = r.height, r.width
        tf, crs = r.transform, r.crs

    def grid(extent: int) -> list[int]:
        xs = list(range(0, max(extent - PATCH + 1, 1), step))
        if not xs or xs[-1] != extent - PATCH:
            xs.append(extent - PATCH)
        return sorted(set(max(x, 0) for x in xs))

    rs, cs = grid(H), grid(W)
    print(f"Inference: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches")
    probs = {"pit": np.zeros((NC_PIT, H, W), dtype=np.float32),
             "road": np.zeros((NC_ROAD, H, W), dtype=np.float32),
             "plat": np.zeros((NC_PLAT, H, W), dtype=np.float32)}
    cnt = np.zeros((H, W), dtype=np.float32)
    model.eval()
    use_amp = DEVICE.type == "cuda"
    buf_x, buf_pos = [], []

    def flush() -> None:
        if not buf_x:
            return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad(), torch.amp.autocast(device_type="cuda", enabled=use_amp):
            outs = model(x)
            p_pit = torch.softmax(outs[0], 1).cpu().numpy()
            p_road = torch.softmax(outs[1], 1).cpu().numpy()
            p_plat = torch.softmax(outs[2], 1).cpu().numpy()
        for i, (r0, c0) in enumerate(buf_pos):
            probs["pit"][:, r0:r0+PATCH, c0:c0+PATCH] += p_pit[i]
            probs["road"][:, r0:r0+PATCH, c0:c0+PATCH] += p_road[i]
            probs["plat"][:, r0:r0+PATCH, c0:c0+PATCH] += p_plat[i]
            cnt[r0:r0+PATCH, c0:c0+PATCH] += 1
        buf_x.clear(); buf_pos.clear()

    t0 = time.time()
    with rasterio.open(FEATURES) as src:
        for r0 in rs:
            for c0 in cs:
                f = src.read(window=Window(c0, r0, PATCH, PATCH)).astype(np.float32)
                buf_x.append(normalize(f, mu, sd))
                buf_pos.append((r0, c0))
                if len(buf_x) >= 16:
                    flush()
        flush()
    print(f"  inference done in {time.time()-t0:.1f}s")

    np.maximum(cnt, 1, out=cnt)
    for k in probs:
        probs[k] /= cnt
    for name, prob in probs.items():
        am = prob.argmax(0).astype(np.uint8)
        # Save foreground probability: 1 - bg for pit (3 classes), class-1 for
        # the binary heads. Pit's full per-class probs are recoverable from
        # the argmax if needed.
        fg = (1.0 - prob[0]) if name == "pit" else prob[1]
        write_tif(out_dir / f"{name}_prob.tif", fg,
                  transform=tf, crs=crs, dtype="float32", nodata=-1.0, bigtiff=True)
        pf = make_profile(width=W, height=H, transform=tf, crs=crs,
                          dtype="uint8", nodata=255)
        with rasterio.open(out_dir / f"{name}_argmax.tif", "w", **pf) as dst:
            dst.write(am, 1)
        print(f"  wrote {name}_prob.tif + {name}_argmax.tif")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=40)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--smoke", action="store_true",
                    help="single short epoch for sanity check")
    ap.add_argument("--no-infer", action="store_true",
                    help="skip full-tile inference at the end")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 1

    blocks = gpd.read_file(BLOCKS, layer="blocks")
    mu, sd = load_stats(STATS, DEFAULT_CHANNELS)
    with rasterio.open(FEATURES) as r:
        tf = r.transform

    train_ds = build_dataset("train", blocks, tf, mu, sd, augment=True,  seed=42)
    val_ds   = build_dataset("val",   blocks, tf, mu, sd, augment=False, seed=43)
    print(f"train: pit={len(train_ds.policies[0][1])} plat={len(train_ds.policies[1][1])} "
          f"road={len(train_ds.policies[2][1])} not_road={len(train_ds.policies[3][1])} "
          f"tiles/ep={len(train_ds)}")
    print(f"val:   pit={len(val_ds.policies[0][1])} plat={len(val_ds.policies[1][1])} "
          f"road={len(val_ds.policies[2][1])} not_road={len(val_ds.policies[3][1])} "
          f"tiles/ep={len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.workers, pin_memory=True)

    model = MultiHeadUNet(in_ch=len(DEFAULT_CHANNELS), base=32).to(DEVICE)
    losses = {"pit":  FocalCE(FOCAL_PIT,  FOCAL_GAMMA).to(DEVICE),
              "road": FocalCE(FOCAL_ROAD, FOCAL_GAMMA).to(DEVICE),
              "plat": FocalCE(FOCAL_PLAT, FOCAL_GAMMA).to(DEVICE)}
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")
    print(f"MultiHeadUNet params: {sum(p.numel() for p in model.parameters())/1e6:.2f} M")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    log_rows: list[dict] = []
    best_score = -float("inf")
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr, _ = _run_epoch(model, train_loader, opt, losses, scaler, train=True)
        va, va_iou = _run_epoch(model, val_loader, None, losses, None, train=False)
        sched.step()
        # Composite score: pit floor+wall + road class + plat class, all
        # equally weighted -- this is what we actually care about downstream.
        pit_score = np.nanmean(va_iou["pit"][1:])
        score = float(np.nanmean([pit_score, va_iou["road"][1], va_iou["plat"][1]]))
        dt = time.time() - t0
        print(f"ep {ep:3d}/{args.epochs}  "
              f"tr={tr['all']:.3f} (p={tr['pit']:.3f} r={tr['road']:.3f} a={tr['plat']:.3f})  "
              f"va={va['all']:.3f}  "
              f"iou pit[fl={va_iou['pit'][1]:.2f},wl={va_iou['pit'][2]:.2f}] "
              f"road={va_iou['road'][1]:.2f} plat={va_iou['plat'][1]:.2f}  "
              f"score={score:.3f}  {dt:.1f}s")
        log_rows.append({
            "epoch": ep, "tr_loss": tr["all"], "va_loss": va["all"],
            "tr_loss_pit": tr["pit"], "tr_loss_road": tr["road"], "tr_loss_plat": tr["plat"],
            "iou_pit_bg": va_iou["pit"][0], "iou_pit_floor": va_iou["pit"][1],
            "iou_pit_wall": va_iou["pit"][2],
            "iou_road_bg": va_iou["road"][0], "iou_road": va_iou["road"][1],
            "iou_plat_bg": va_iou["plat"][0], "iou_plat": va_iou["plat"][1],
            "score": score, "sec": dt,
        })
        if score > best_score:
            best_score = score
            torch.save({"state_dict": model.state_dict(), "epoch": ep,
                        "score": score, "mu": mu, "sd": sd,
                        "channels": list(DEFAULT_CHANNELS),
                        "patch": PATCH,
                        "head_classes": (NC_PIT, NC_ROAD, NC_PLAT),
                        "loss_weights": LOSS_WEIGHTS},
                       OUTDIR / "best.pt")
            print(f"    -> new best (score={score:.3f}), saved")
    pd.DataFrame(log_rows).to_csv(OUTDIR / "train_log.csv", index=False)
    print(f"\nBest score: {best_score:.3f}")

    if not args.no_infer:
        ck = torch.load(OUTDIR / "best.pt", map_location=DEVICE, weights_only=False)
        model.load_state_dict(ck["state_dict"])
        print(f"Loaded best (ep {ck['epoch']}). Running full-tile inference...")
        write_full_tile(model, mu, sd, OUTDIR)
    print(f"Outputs in {OUTDIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
