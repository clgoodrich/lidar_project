"""Shared deep-learning building blocks for pit / road / pad U-Net trainers.

What's here vs. what stays in the per-task scripts:

  * ``UNet``, ``FocalCE``                — model + loss (single definition)
  * ``DEFAULT_CHANNELS``, ``load_stats`` — channel order + normalisation stats
  * ``CenteredPatchSampler``             — common patch-sampling base class
  * ``random_d4``                        — D4 augmentation (rot90 × flip)
  * ``run_epoch``                        — one pass with optional grad / AMP
  * ``train_loop``                       — full per-epoch driver, writes log CSV + best ckpt
  * ``predict_full_tile``                — sliding-window full-tile inference

Per-task scripts (``pits/_pit_unet_v2.py``, ``roads/_road_unet.py``,
``s3_train/_pad_unet.py``) supply: task-specific sample policy, ``n_classes``,
focal-loss class weights, patch size, label raster path, and the test-eval
function — the rest is reused verbatim.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence

import numpy as np
import pandas as pd
import rasterio
import torch
import torch.nn as nn
import torch.nn.functional as F
from rasterio.windows import Window
from torch.utils.data import DataLoader, Dataset

__all__ = [
    "DEVICE", "DEFAULT_CHANNELS",
    "UNet", "FocalCE",
    "load_stats", "normalize",
    "CenteredPatchSampler", "random_d4",
    "run_epoch", "train_loop", "predict_full_tile",
]

DEVICE: torch.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Channel order frozen across pit / road / pad tasks. Must match the band
# order produced by ``pits/_stack_features.py``.
DEFAULT_CHANNELS: tuple[str, ...] = (
    "lrm_25", "lrm_5", "slope", "tpi_05",
    "openness_pos", "openness_neg", "roughness_11",
)


# ---------------------------------------------------------------------------
# Model + loss
# ---------------------------------------------------------------------------

def _cbr(in_ch: int, out_ch: int) -> nn.Sequential:
    """Conv-BN-ReLU twice — the standard U-Net block."""
    return nn.Sequential(
        nn.Conv2d(in_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
        nn.Conv2d(out_ch, out_ch, 3, padding=1, bias=False),
        nn.BatchNorm2d(out_ch), nn.ReLU(inplace=True),
    )


class UNet(nn.Module):
    """Custom 4-level U-Net, base=32 by default (~8 M params at in_ch=7)."""

    def __init__(self, in_ch: int = 7, n_classes: int = 3, base: int = 32):
        super().__init__()
        self.d1 = _cbr(in_ch,    base)
        self.d2 = _cbr(base,     base * 2)
        self.d3 = _cbr(base * 2, base * 4)
        self.d4 = _cbr(base * 4, base * 8)
        self.bot = _cbr(base * 8, base * 16)
        self.up4 = nn.ConvTranspose2d(base * 16, base * 8, 2, 2); self.u4 = _cbr(base * 16, base * 8)
        self.up3 = nn.ConvTranspose2d(base * 8,  base * 4, 2, 2); self.u3 = _cbr(base * 8,  base * 4)
        self.up2 = nn.ConvTranspose2d(base * 4,  base * 2, 2, 2); self.u2 = _cbr(base * 4,  base * 2)
        self.up1 = nn.ConvTranspose2d(base * 2,  base,     2, 2); self.u1 = _cbr(base * 2,  base)
        self.out = nn.Conv2d(base, n_classes, 1)
        self.pool = nn.MaxPool2d(2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        d1 = self.d1(x)
        d2 = self.d2(self.pool(d1))
        d3 = self.d3(self.pool(d2))
        d4 = self.d4(self.pool(d3))
        b = self.bot(self.pool(d4))
        u4 = self.u4(torch.cat([self.up4(b),  d4], 1))
        u3 = self.u3(torch.cat([self.up3(u4), d3], 1))
        u2 = self.u2(torch.cat([self.up2(u3), d2], 1))
        u1 = self.u1(torch.cat([self.up1(u2), d1], 1))
        return self.out(u1)


class FocalCE(nn.Module):
    """Focal cross-entropy with per-class alpha weights (Lin et al. 2017)."""

    def __init__(self, alpha: Sequence[float], gamma: float = 2.0, ignore: int = 255):
        super().__init__()
        self.gamma = gamma
        self.ignore = ignore
        self.register_buffer("alpha", torch.tensor(alpha, dtype=torch.float32))

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        log_p = F.log_softmax(logits, 1)
        p = log_p.exp()
        valid = target != self.ignore
        t = target.clone(); t[~valid] = 0
        oh = F.one_hot(t, logits.shape[1]).permute(0, 3, 1, 2).float()
        focal = (1 - p) ** self.gamma
        a = self.alpha.view(1, -1, 1, 1)
        loss = -(oh * a * focal * log_p).sum(1)
        if not bool(valid.any()):
            # All-ignore patch (possible with corridor-supervised blocks):
            # return a graph-connected zero instead of NaN from empty mean().
            return (logits * 0.0).sum()
        return loss[valid].mean()


# ---------------------------------------------------------------------------
# Stats + normalisation
# ---------------------------------------------------------------------------

def load_stats(
    stats_path: Path,
    channels: Sequence[str] = DEFAULT_CHANNELS,
    *,
    sd_floor: float = 1e-6,
) -> tuple[np.ndarray, np.ndarray]:
    """Read per-channel ``mean`` / ``std`` from a feature_stats.json."""
    stats = json.loads(stats_path.read_text())
    mu = np.array([stats[c]["mean"] for c in channels], dtype=np.float32)
    sd = np.array([max(stats[c]["std"], sd_floor) for c in channels], dtype=np.float32)
    return mu, sd


def normalize(feat: np.ndarray, mu: np.ndarray, sd: np.ndarray) -> np.ndarray:
    """Replace NaNs with 0, then z-score per channel.

    Expects ``feat`` of shape (C, H, W) and 1-D mu/sd of length C.
    """
    feat = np.where(np.isfinite(feat), feat, 0.0)
    return (feat - mu[:, None, None]) / sd[:, None, None]


# ---------------------------------------------------------------------------
# Dataset base + augmentation
# ---------------------------------------------------------------------------

def random_d4(feat: np.ndarray, lbl: np.ndarray, rng: np.random.Generator):
    """Random D4 (rot90 x flip) augmentation, in-place safe.

    ``feat`` is (C, H, W), ``lbl`` is (H, W). Returns possibly-rotated/flipped
    copies (always copies because numpy rotations return views).
    """
    k = int(rng.integers(0, 4))
    if k:
        feat = np.rot90(feat, k, axes=(1, 2)).copy()
        lbl = np.rot90(lbl, k).copy()
    if rng.random() < 0.5:
        feat = feat[:, :, ::-1].copy()
        lbl = lbl[:, ::-1].copy()
    return feat, lbl


class CenteredPatchSampler(Dataset):
    """Samples PATCH x PATCH windows centered on points + random backgrounds.

    Subclass usage: the per-task script builds a sampler with a list of
    centroid policies — each policy is a ``(name, points_xy_array)`` pair
    — plus a list of "background block" bounds (a (B, 4) array of
    ``(minx, miny, maxx, maxy)``). On each ``__getitem__`` call we pick which
    policy generates the centroid for that index by cycling through them, and
    if a policy has zero points we fall back to a random block-interior point.

    Args:
        feat_path: Path to the stacked-features GeoTIFF.
        lbl_path: Path to the label GeoTIFF.
        policies: Ordered list of ``(name, xy_array, jitter_m)`` tuples
            describing centered-sampling sources. The dataset cycles through
            them per index modulo ``len(policies) + 1`` (the +1 slot is the
            random-background draw).
        block_bounds: ``(B, 4)`` array of ``(minx, miny, maxx, maxy)`` for
            random background sampling within the split's spatial blocks.
        transform: Rasterio affine of the feature raster (used to map
            world XY -> pixel row/col).
        mu, sd: Per-channel normalisation stats.
        patch: Window side length in pixels (must be even).
        augment: Apply random D4 augmentation.
        seed: Base RNG seed (forked per-worker via ``worker_init_fn``).
    """

    def __init__(
        self,
        feat_path: Path,
        lbl_path: Path,
        policies: list[tuple[str, np.ndarray, float]],
        block_bounds: np.ndarray,
        transform,
        mu: np.ndarray,
        sd: np.ndarray,
        *,
        patch: int = 256,
        augment: bool = True,
        seed: int = 0,
    ):
        self.feat_path = feat_path
        self.lbl_path = lbl_path
        self.policies = policies
        self.block_bounds = block_bounds
        self.transform = transform
        self.mu = mu.astype(np.float32)
        self.sd = sd.astype(np.float32)
        self.patch = patch
        self.augment = augment
        self.seed = seed

        # Stride pattern is (#centered policies + 1 background draw).
        self.stride = len(policies) + 1
        # Length grows with the largest policy, so each pit/road/etc. is
        # seen at least once per epoch.
        max_pts = max((len(arr) for _, arr, _ in policies), default=0)
        self._epoch_len = max(max_pts, 1) * self.stride

        # Lazily-opened rasterio handles (per-worker).
        self._feat: Optional[rasterio.io.DatasetReader] = None
        self._lbl: Optional[rasterio.io.DatasetReader] = None
        self._rng: Optional[np.random.Generator] = None

    def __len__(self) -> int:
        return self._epoch_len

    def _open(self) -> None:
        if self._feat is None:
            self._feat = rasterio.open(self.feat_path)
            self._lbl = rasterio.open(self.lbl_path)
        if self._rng is None:
            wi = torch.utils.data.get_worker_info()
            worker_id = wi.id if wi is not None else 0
            self._rng = np.random.default_rng(self.seed + worker_id)

    def _world_to_rowcol(self, x: float, y: float) -> tuple[int, int]:
        tf = self.transform
        col = (x - tf.c) / tf.a
        row = (y - tf.f) / tf.e
        return int(round(row)), int(round(col))

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
        # Fallback / background draw: uniform inside a random block.
        bb = self.block_bounds[rng.integers(0, len(self.block_bounds))]
        return rng.uniform(bb[0], bb[2]), rng.uniform(bb[1], bb[3])

    def __getitem__(self, idx: int):
        self._open()
        cx, cy = self._pick_center(idx)
        row, col = self._world_to_rowcol(cx, cy)
        H, W = self._feat.height, self._feat.width
        r0 = int(np.clip(row - self.patch // 2, 0, H - self.patch))
        c0 = int(np.clip(col - self.patch // 2, 0, W - self.patch))
        win = Window(c0, r0, self.patch, self.patch)
        feat = self._feat.read(window=win).astype(np.float32)
        lbl = self._lbl.read(1, window=win).astype(np.int64)
        feat = normalize(feat, self.mu, self.sd)
        if self.augment:
            feat, lbl = random_d4(feat, lbl, self._rng)
        return torch.from_numpy(feat), torch.from_numpy(lbl)


# ---------------------------------------------------------------------------
# Epoch / training driver
# ---------------------------------------------------------------------------

def _amp_ctx(enabled: bool):
    return torch.amp.autocast(device_type="cuda", enabled=enabled)


def run_epoch(
    model: nn.Module,
    loader: DataLoader,
    opt: Optional[torch.optim.Optimizer],
    loss_fn: nn.Module,
    scaler: Optional[torch.amp.GradScaler],
    n_classes: int,
    *,
    train: bool,
) -> tuple[float, list[float]]:
    """Run one epoch. Returns ``(mean_loss, per_class_iou)``."""
    model.train(mode=train)
    use_amp = DEVICE.type == "cuda"
    total = 0.0
    n_batches = 0
    inter = np.zeros(n_classes)
    union = np.zeros(n_classes)
    ctx_grad = torch.enable_grad() if train else torch.no_grad()
    with ctx_grad:
        for x, y in loader:
            x = x.to(DEVICE, non_blocking=True)
            y = y.to(DEVICE, non_blocking=True)
            if train and opt is not None:
                opt.zero_grad(set_to_none=True)
            with _amp_ctx(use_amp):
                logits = model(x)
                loss = loss_fn(logits, y)
            if train and opt is not None and scaler is not None:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            total += float(loss)
            n_batches += 1
            pred = logits.argmax(1)
            for c in range(n_classes):
                pm = pred == c
                tm = y == c
                inter[c] += int((pm & tm).sum())
                union[c] += int((pm | tm).sum())
    iou = [(inter[c] / union[c]) if union[c] else float("nan") for c in range(n_classes)]
    return total / max(n_batches, 1), iou


def train_loop(
    *,
    model: nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    loss_fn: nn.Module,
    epochs: int,
    lr: float,
    n_classes: int,
    out_dir: Path,
    checkpoint_extra: dict,
    score: Callable[[list[float]], float],
    weight_decay: float = 1e-4,
    log_name: str = "train_log.csv",
    ckpt_name: str = "best.pt",
    extra_iou_names: Iterable[str] = (),
) -> dict:
    """Full training loop. Writes ``train_log.csv`` and saves best ckpt.

    Args:
        score: Function (val_iou) -> scalar; higher is better, used to pick
            the best epoch.
        checkpoint_extra: Extra fields merged into the saved checkpoint dict.
        extra_iou_names: Column suffixes for per-class IoUs in the log CSV
            (e.g. ``("bg", "floor", "wall")``). Length must equal ``n_classes``.
    """
    extra_iou_names = tuple(extra_iou_names) or tuple(f"c{c}" for c in range(n_classes))
    if len(extra_iou_names) != n_classes:
        raise ValueError(f"extra_iou_names must have len {n_classes}")

    model.to(DEVICE)
    loss_fn.to(DEVICE)
    opt = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)
    scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

    out_dir.mkdir(parents=True, exist_ok=True)
    log_rows: list[dict] = []
    best_score = -float("inf")
    for ep in range(1, epochs + 1):
        t0 = time.time()
        tr_loss, _ = run_epoch(model, train_loader, opt, loss_fn, scaler, n_classes, train=True)
        va_loss, va_iou = run_epoch(model, val_loader, None, loss_fn, None, n_classes, train=False)
        sched.step()
        dt = time.time() - t0
        s = float(score(va_iou))
        iou_str = "  ".join(f"{name}={va_iou[i]:.3f}" for i, name in enumerate(extra_iou_names))
        print(f"ep {ep:3d}/{epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
              f"va_iou {iou_str}  score={s:.3f}  {dt:.1f}s")
        row = {"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
               "score": s, "sec": dt}
        for i, name in enumerate(extra_iou_names):
            row[f"iou_{name}"] = va_iou[i]
        log_rows.append(row)
        if s > best_score:
            best_score = s
            ckpt = {"state_dict": model.state_dict(), "epoch": ep,
                    "score": s, **checkpoint_extra}
            torch.save(ckpt, out_dir / ckpt_name)
            print(f"    -> new best (score={s:.3f}), saved")
    pd.DataFrame(log_rows).to_csv(out_dir / log_name, index=False)
    print(f"\nBest score: {best_score:.3f}. Outputs in {out_dir}")
    return {"best_score": best_score, "log": log_rows}


# ---------------------------------------------------------------------------
# Sliding-window inference
# ---------------------------------------------------------------------------

def predict_full_tile(
    model: nn.Module,
    features_path: Path,
    mu: np.ndarray,
    sd: np.ndarray,
    *,
    patch: int,
    overlap: int,
    n_classes: int,
    batch: int = 16,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Sliding-window full-tile inference with overlap averaging.

    Returns ``(prob, argmax, src_profile)``.
    """
    if overlap >= patch:
        raise ValueError(f"overlap ({overlap}) must be < patch ({patch})")
    step = patch - overlap
    with rasterio.open(features_path) as r:
        H, W = r.height, r.width
        profile = r.profile.copy()

    def _row_cols(extent: int) -> list[int]:
        # Tile + ensure right/bottom edge always covered exactly once.
        xs = list(range(0, max(extent - patch + 1, 1), step))
        if not xs or xs[-1] != extent - patch:
            xs.append(extent - patch)
        return sorted(set(max(x, 0) for x in xs))

    rs, cs = _row_cols(H), _row_cols(W)
    print(f"Inference grid: {len(rs)} x {len(cs)} = {len(rs)*len(cs)} patches")

    prob = np.zeros((n_classes, H, W), dtype=np.float32)
    count = np.zeros((H, W), dtype=np.float32)
    use_amp = DEVICE.type == "cuda"

    # Patches are moved to DEVICE below, so the model must be there too. Callers
    # that train first get this from train_loop; a caller that loads a
    # checkpoint and predicts straight away does not, and used to die with
    # "Input type (torch.cuda.HalfTensor) and weight type (torch.FloatTensor)".
    model.to(DEVICE)
    model.eval()
    buf_x: list[np.ndarray] = []
    buf_pos: list[tuple[int, int]] = []

    def flush() -> None:
        if not buf_x:
            return
        x = torch.from_numpy(np.stack(buf_x)).to(DEVICE)
        with torch.no_grad(), _amp_ctx(use_amp):
            p = torch.softmax(model(x), 1).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+patch, c0:c0+patch] += arr
            count[r0:r0+patch, c0:c0+patch] += 1
        buf_x.clear(); buf_pos.clear()

    t0 = time.time()
    with rasterio.open(features_path) as src:
        for r0 in rs:
            for c0 in cs:
                f = src.read(window=Window(c0, r0, patch, patch)).astype(np.float32)
                f = normalize(f, mu, sd)
                buf_x.append(f); buf_pos.append((r0, c0))
                if len(buf_x) >= batch:
                    flush()
        flush()
    print(f"  inference done in {time.time()-t0:.1f}s")

    np.maximum(count, 1, out=count)
    prob /= count
    argmax = prob.argmax(0).astype(np.uint8)
    return prob, argmax, profile
