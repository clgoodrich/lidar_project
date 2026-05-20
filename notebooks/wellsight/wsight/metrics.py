"""Pixel-level segmentation metrics."""
import numpy as np
import torch


def per_class_iou(pred: torch.Tensor, target: torch.Tensor,
                  n_classes: int, ignore_index: int = 255) -> list[float]:
    """Per-class IoU across a batch of predictions.

    pred, target: [B, H, W] long tensors.
    Returns a list of length n_classes; NaN for classes absent from the batch.
    """
    out: list[float] = []
    valid = target != ignore_index
    for c in range(n_classes):
        p = (pred == c) & valid
        t = (target == c) & valid
        inter = (p & t).sum().item()
        union = (p | t).sum().item()
        out.append(float("nan") if union == 0 else inter / union)
    return out


def pixel_iou_in_mask(argmax: np.ndarray, labels: np.ndarray,
                      mask: np.ndarray, n_classes: int) -> dict:
    """Per-class IoU computed only over pixels where `mask` is True.

    Returns {class_idx: iou_or_None}. None when class absent in mask region.
    """
    out: dict[int, float | None] = {}
    for c in range(n_classes):
        p = (argmax == c) & mask
        t = (labels == c) & mask
        inter = int((p & t).sum())
        union = int((p | t).sum())
        out[c] = (inter / union) if union else None
    return out
