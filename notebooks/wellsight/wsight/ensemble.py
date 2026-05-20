"""Ensemble inference helpers.

`sliding_window_predict_pair` runs two models on the same tile (potentially
on different feature stacks) and returns both their TTA-averaged softmax
probability volumes, ready for `mean_ensemble` or `maxpit_ensemble`.
"""
from __future__ import annotations
from pathlib import Path
import time
import numpy as np
import rasterio
from rasterio.windows import Window
import torch

from .inference import tta_predict_batch


def sliding_window_predict_pair(model_a, feat_path_a: Path, mu_a, sd_a,
                                model_b, feat_path_b: Path, mu_b, sd_b,
                                *, device, n_classes: int,
                                patch: int = 256, overlap: int = 64,
                                batch: int = 8, verbose: bool = True):
    """Run two models over the same tile with 8-fold TTA each.

    Returns (prob_a, prob_b), each of shape (C, H, W), averaged across
    overlapping windows. The two probability volumes are spatially aligned
    so they can be ensembled per-pixel.
    """
    with rasterio.open(feat_path_a) as r:
        H, W = r.height, r.width
    step = patch - overlap
    rs = sorted(set(list(range(0, H - patch + 1, step)) + [H - patch]))
    cs = sorted(set(list(range(0, W - patch + 1, step)) + [W - patch]))
    if verbose:
        print(f"Ensemble inference grid: {len(rs)}x{len(cs)} = {len(rs)*len(cs)} patches (TTA 8x each, two models)")

    prob_a = np.zeros((n_classes, H, W), dtype=np.float32)
    prob_b = np.zeros((n_classes, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)
    src_a = rasterio.open(feat_path_a)
    src_b = rasterio.open(feat_path_b)
    model_a.eval(); model_b.eval()
    buf_a, buf_b, buf_pos = [], [], []
    t0 = time.time()

    def flush():
        if not buf_a:
            return
        x_a = torch.from_numpy(np.stack(buf_a)).to(device)
        x_b = torch.from_numpy(np.stack(buf_b)).to(device)
        with torch.no_grad():
            p_a = tta_predict_batch(model_a, x_a, device).cpu().numpy()
            p_b = tta_predict_batch(model_b, x_b, device).cpu().numpy()
        for arr_a, arr_b, (r0, c0) in zip(p_a, p_b, buf_pos):
            prob_a[:, r0:r0+patch, c0:c0+patch] += arr_a
            prob_b[:, r0:r0+patch, c0:c0+patch] += arr_b
            cnt[r0:r0+patch, c0:c0+patch] += 1
        buf_a.clear(); buf_b.clear(); buf_pos.clear()

    for r0 in rs:
        for c0 in cs:
            win = Window(c0, r0, patch, patch)
            fa = src_a.read(window=win).astype(np.float32)
            fa = np.where(np.isfinite(fa), fa, 0.0)
            fa = (fa - mu_a[:, None, None]) / sd_a[:, None, None]
            fb = src_b.read(window=win).astype(np.float32)
            fb = np.where(np.isfinite(fb), fb, 0.0)
            fb = (fb - mu_b[:, None, None]) / sd_b[:, None, None]
            buf_a.append(fa); buf_b.append(fb); buf_pos.append((r0, c0))
            if len(buf_a) >= batch:
                flush()
    flush()
    src_a.close(); src_b.close()
    if verbose:
        print(f"  ensemble inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1)
    return prob_a / cnt, prob_b / cnt


def mean_ensemble(prob_a: np.ndarray, prob_b: np.ndarray) -> np.ndarray:
    """Symmetric mean of two softmax probability volumes. Same shape in, same shape out."""
    return 0.5 * (prob_a + prob_b)


def maxpit_ensemble(prob_a: np.ndarray, prob_b: np.ndarray) -> np.ndarray:
    """Aggressive pit-favored ensemble for 3-class (bg / floor / wall) outputs.

    bg gets the more skeptical of the two; floor and wall get the more
    confident of the two. Then renormalize so each pixel sums to 1.

    Catches more pit pixels than mean_ensemble, at the cost of more road-
    shoulder false positives (see iter 05 family for filters that clean those).
    """
    bg = np.minimum(prob_a[0], prob_b[0])
    floor = np.maximum(prob_a[1], prob_b[1])
    wall = np.maximum(prob_a[2], prob_b[2])
    out = np.stack([bg, floor, wall], axis=0)
    s = out.sum(axis=0, keepdims=True)
    return out / np.clip(s, 1e-8, None)
