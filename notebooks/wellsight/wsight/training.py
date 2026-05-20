"""Training loop building blocks.

All iterations share the same per-epoch loop shape:

  for each (x, y) in DataLoader:
      forward
      compute focal-CE loss
      AMP backward + step (if training)
      accumulate per-class IoU

These two functions capture that exactly. Iteration runners just construct
the model + loss + opt + dataloaders and call train_segmentation().
"""
from __future__ import annotations
from pathlib import Path
import json
import time
import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

from .metrics import per_class_iou


def run_epoch(model, loader, opt, loss_fn, scaler, train: bool, device, n_classes: int):
    """Single forward+(backward) pass over one loader. Returns (mean_loss, iou_list)."""
    model.train() if train else model.eval()
    total_loss = 0.0
    n_batches = 0
    inter = np.zeros(n_classes)
    union = np.zeros(n_classes)
    ctx = torch.enable_grad() if train else torch.no_grad()
    with ctx:
        for x, y in loader:
            x = x.to(device, non_blocking=True)
            y = y.to(device, non_blocking=True)
            if train:
                opt.zero_grad(set_to_none=True)
            with torch.amp.autocast(device_type="cuda", enabled=device.type == "cuda"):
                logits = model(x)
                loss = loss_fn(logits, y)
            if train:
                scaler.scale(loss).backward()
                scaler.step(opt)
                scaler.update()
            total_loss += loss.item()
            n_batches += 1
            pred = logits.argmax(1)
            for c in range(n_classes):
                pm = pred == c
                tm = y == c
                inter[c] += (pm & tm).sum().item()
                union[c] += (pm | tm).sum().item()
    iou = [(inter[c] / union[c]) if union[c] else float("nan") for c in range(n_classes)]
    return total_loss / max(n_batches, 1), iou


def train_segmentation(model, train_loader, val_loader, *,
                       loss_fn, opt, scheduler, scaler, device,
                       n_classes: int,
                       epochs: int,
                       miou_classes: list[int],
                       ckpt_path: Path,
                       ckpt_extras: dict,
                       log_path: Path,
                       label: str = "iter"):
    """End-to-end training loop with best-miou checkpoint.

    Parameters
    ----------
    miou_classes : list of int
        Which class indices to average for the checkpoint criterion. For pit
        3-class: [1, 2] (floor + wall, excluding bg). For binary plat/road
        tasks: [1] (the positive class).
    ckpt_extras : dict
        Extra keys to embed in the checkpoint (mu, sd, channels, encoder, etc.).
    """
    log = []
    best_miou = -1.0
    for ep in range(1, epochs + 1):
        t0 = time.time()
        tr_loss, _ = run_epoch(model, train_loader, opt, loss_fn, scaler, train=True,
                               device=device, n_classes=n_classes)
        va_loss, va_iou = run_epoch(model, val_loader, opt, loss_fn, scaler, train=False,
                                    device=device, n_classes=n_classes)
        scheduler.step()
        dt = time.time() - t0
        miou = float(np.nanmean([va_iou[c] for c in miou_classes]))
        iou_strs = "  ".join(f"c{c}={va_iou[c]:.3f}" for c in range(n_classes))
        print(f"ep {ep:3d}/{epochs}  tr_loss={tr_loss:.4f} va_loss={va_loss:.4f}  "
              f"va_iou {iou_strs}  miou_pos={miou:.3f}  {dt:.1f}s")
        log.append({"epoch": ep, "tr_loss": tr_loss, "va_loss": va_loss,
                    **{f"iou_c{c}": va_iou[c] for c in range(n_classes)},
                    "miou_pos": miou, "sec": dt})
        if miou > best_miou:
            best_miou = miou
            torch.save({"state_dict": model.state_dict(),
                        "epoch": ep, "miou": miou, "n_classes": n_classes,
                        **ckpt_extras},
                       ckpt_path)
            print(f"    -> new best {label} miou={miou:.3f}, saved")
    pd.DataFrame(log).to_csv(log_path, index=False)
    print(f"\nBest val miou ({label}): {best_miou:.3f}")
    return best_miou
