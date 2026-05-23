"""Loss functions used across pit / plat / road segmentation tasks."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class FocalCE(nn.Module):
    """Multi-class focal cross-entropy with per-class alpha balancing.

    Loss = -alpha_c * (1 - p_c)^gamma * log(p_c) for the true class c at each pixel.

    Alpha for pits (3-class): (0.05, 0.475, 0.475) — bg gets 5%, floor + wall split 95%.
    Alpha for binary (plat or road): (0.10, 0.90) or (0.15, 0.85) — tune per task.
    """

    def __init__(self, alpha=(0.05, 0.475, 0.475), gamma: float = 2.0, ignore_index: int = 255):
        super().__init__()
        self.gamma = gamma
        self.ignore_index = ignore_index
        self.register_buffer("alpha", torch.tensor(alpha, dtype=torch.float32))

    def forward(self, logits, target):
        # logits: [B, C, H, W];  target: [B, H, W] int64
        log_p = F.log_softmax(logits, dim=1)
        p = log_p.exp()
        valid = target != self.ignore_index
        t = target.clone()
        t[~valid] = 0
        n_classes = logits.shape[1]
        oh = F.one_hot(t, num_classes=n_classes).permute(0, 3, 1, 2).float()
        focal = (1.0 - p) ** self.gamma
        a = self.alpha.view(1, -1, 1, 1)
        loss = -(oh * a * focal * log_p).sum(dim=1)
        return loss[valid].mean()
