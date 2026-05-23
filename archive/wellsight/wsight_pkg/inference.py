"""Inference utilities: TTA, sliding-window full-tile prediction, raster writers."""
from __future__ import annotations
from pathlib import Path
import time
import numpy as np
import rasterio
from rasterio.windows import Window
import torch


def tta_predict_batch(model, x, device):
    """8-fold TTA: 4 rotations x 2 flips, averaged softmax.

    Returns a tensor of shape [B, C, H, W] in float32 with softmax already applied.
    """
    outs = []
    for k in range(4):
        for flip in (False, True):
            x_aug = x
            if k:
                x_aug = torch.rot90(x_aug, k=k, dims=(2, 3))
            if flip:
                x_aug = torch.flip(x_aug, dims=(3,))
            with torch.amp.autocast(device_type="cuda", enabled=device.type == "cuda"):
                logits = model(x_aug)
            p = torch.softmax(logits, dim=1)
            if flip:
                p = torch.flip(p, dims=(3,))
            if k:
                p = torch.rot90(p, k=-k, dims=(2, 3))
            outs.append(p.float())
    return torch.stack(outs, dim=0).mean(dim=0)


def sliding_window_predict(model, feature_path: Path, mu, sd, *,
                           device, n_classes: int,
                           patch: int = 256, overlap: int = 64,
                           batch: int = 8, use_tta: bool = True,
                           verbose: bool = True):
    """Run the model over the entire feature TIF with overlapping windows.

    Returns averaged softmax probabilities of shape (C, H, W).
    """
    with rasterio.open(feature_path) as r:
        H, W = r.height, r.width
    step = patch - overlap
    rs = sorted(set(list(range(0, H - patch + 1, step)) + [H - patch]))
    cs = sorted(set(list(range(0, W - patch + 1, step)) + [W - patch]))
    n_patches = len(rs) * len(cs)
    if verbose:
        tta_msg = f" (TTA 8x)" if use_tta else ""
        print(f"Inference grid: {len(rs)}x{len(cs)} = {n_patches} patches{tta_msg}")

    prob = np.zeros((n_classes, H, W), dtype=np.float32)
    cnt = np.zeros((H, W), dtype=np.float32)

    src = rasterio.open(feature_path)
    model.eval()
    buf_x, buf_pos = [], []
    t0 = time.time()

    def flush():
        if not buf_x:
            return
        x = torch.from_numpy(np.stack(buf_x)).to(device)
        with torch.no_grad():
            if use_tta:
                p = tta_predict_batch(model, x, device).cpu().numpy()
            else:
                with torch.amp.autocast(device_type="cuda", enabled=device.type == "cuda"):
                    p = torch.softmax(model(x), 1).cpu().numpy()
        for arr, (r0, c0) in zip(p, buf_pos):
            prob[:, r0:r0+patch, c0:c0+patch] += arr
            cnt[r0:r0+patch, c0:c0+patch] += 1
        buf_x.clear(); buf_pos.clear()

    for r0 in rs:
        for c0 in cs:
            f = src.read(window=Window(c0, r0, patch, patch)).astype(np.float32)
            f = np.where(np.isfinite(f), f, 0.0)
            f = (f - mu[:, None, None]) / sd[:, None, None]
            buf_x.append(f)
            buf_pos.append((r0, c0))
            if len(buf_x) >= batch:
                flush()
    flush()
    src.close()

    if verbose:
        print(f"  inference done in {time.time()-t0:.1f}s")
    cnt = np.maximum(cnt, 1)
    return prob / cnt


def write_prob_raster(prob_band: np.ndarray, reference_path: Path, out_path: Path):
    """Write a single-band float32 probability raster aligned to the reference grid."""
    with rasterio.open(reference_path) as r:
        profile = r.profile.copy()
    profile.update(dtype="float32", count=1, compress="deflate", predictor=3,
                   tiled=True, blockxsize=512, blockysize=512, BIGTIFF="YES", nodata=-1.0)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(prob_band.astype(np.float32), 1)


def write_argmax_raster(argmax: np.ndarray, reference_path: Path, out_path: Path):
    """Write a single-band uint8 argmax raster aligned to the reference grid."""
    with rasterio.open(reference_path) as r:
        profile = r.profile.copy()
    profile.update(dtype="uint8", count=1, compress="deflate", predictor=2,
                   tiled=True, blockxsize=512, blockysize=512, nodata=255)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(argmax.astype(np.uint8), 1)
