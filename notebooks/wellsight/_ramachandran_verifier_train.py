"""Ramachandran replication — EfficientNet-B3 verifier training.

Faithful-as-possible replica of the paper's verifier:
  - Backbone: EfficientNet-B3, ImageNet pretrained (timm)
  - Input: 300x300 RGB (B3 default)
  - Loss: focal (alpha=0.25, gamma=2.0)
  - Optim: Adam, LR 1e-6 (paper)
  - Positives: GT bbox crops from positive tiles
  - Negatives: random crops from negative-only tiles (no-pad chips)

Notes on chip-coord scaling:
  Source `annotations_image` bboxes are in 640-px coords (paper's source tile),
  but we fetched chips at 512 px. Scale factor: 512/640 = 0.8.
"""
import ast
import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
CSV = ROOT / "data/external/ramachandran_2024/permian_denver_data/training/well-pad_dataset.csv"
CHIPS = ROOT / "data/external/ramachandran_2024/naip_chips"
OUT = ROOT / "data/derivatives/ramachandran_verifier"
OUT.mkdir(parents=True, exist_ok=True)

SRC_PX = 640      # paper's source tile size (annotations_image coord space)
CHIP_PX = 512     # what we downloaded
SCALE = CHIP_PX / SRC_PX
INPUT_PX = 300    # EfficientNet-B3 input

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ----------------------- data --------------------------------------------
def parse_boxes(s):
    """annotations_image -> list of [x1,y1,x2,y2] in CHIP_PX coords."""
    boxes = ast.literal_eval(s)
    out = []
    for b in boxes:
        x1, y1, x2, y2 = b["bbox"]
        out.append([x1 * SCALE, y1 * SCALE, x2 * SCALE, y2 * SCALE])
    return out


def build_index(splits=("train", "valid", "test")):
    """Return rows of (chip_path, label, bbox_or_None).

    label 1 = pad crop (GT bbox), label 0 = random crop from neg tile.
    """
    df = pd.read_csv(CSV)
    df["has_pad"] = df["annotations_latlon"] != "[]"
    rows = []
    for r in df.itertuples():
        if r.split not in splits:
            continue
        chip = CHIPS / r.split / f"{r.image_id}.jpg"
        if not chip.exists():
            continue
        if r.has_pad:
            for bb in parse_boxes(r.annotations_image):
                rows.append((str(chip), 1, bb, r.split))
        else:
            rows.append((str(chip), 0, None, r.split))
    return pd.DataFrame(rows, columns=["chip", "label", "bbox", "split"])


class VerifierDataset(Dataset):
    def __init__(self, df, training):
        self.df = df.reset_index(drop=True)
        self.training = training
        self.tf = transforms.Compose([
            transforms.Resize((INPUT_PX, INPUT_PX)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
        ])
        self.rng = np.random.default_rng(0)

    def __len__(self):
        return len(self.df)

    def _crop(self, img, bbox, label):
        W, H = img.size
        if label == 1:
            x1, y1, x2, y2 = bbox
            # Pad bbox by 10% on each side, clip to image
            bw, bh = x2 - x1, y2 - y1
            x1 = max(0, x1 - 0.1 * bw); y1 = max(0, y1 - 0.1 * bh)
            x2 = min(W, x2 + 0.1 * bw); y2 = min(H, y2 + 0.1 * bh)
        else:
            # Random 128-256 px crop from negative tile
            cs = self.rng.integers(128, 257)
            x1 = self.rng.integers(0, max(1, W - cs)); y1 = self.rng.integers(0, max(1, H - cs))
            x2, y2 = x1 + cs, y1 + cs
        return img.crop((x1, y1, x2, y2))

    def __getitem__(self, i):
        r = self.df.iloc[i]
        img = Image.open(r.chip).convert("RGB")
        crop = self._crop(img, r.bbox, r.label)
        if self.training and self.rng.random() < 0.5:
            crop = crop.transpose(Image.FLIP_LEFT_RIGHT)
        return self.tf(crop), int(r.label)


# ----------------------- model + loss ------------------------------------
class FocalLoss(nn.Module):
    def __init__(self, alpha=0.25, gamma=2.0):
        super().__init__()
        self.alpha = alpha
        self.gamma = gamma

    def forward(self, logits, target):
        ce = F.binary_cross_entropy_with_logits(logits, target.float(), reduction="none")
        p = torch.sigmoid(logits)
        pt = p * target + (1 - p) * (1 - target)
        w = self.alpha * target + (1 - self.alpha) * (1 - target)
        return (w * (1 - pt) ** self.gamma * ce).mean()


def build_model():
    m = timm.create_model("efficientnet_b3", pretrained=True, num_classes=1)
    return m.to(DEVICE)


# ----------------------- train ------------------------------------------
def run_epoch(model, loader, loss_fn, optim, training, scaler=None, log_every=50):
    model.train(training)
    total, n_correct, n = 0.0, 0, 0
    all_p, all_y = [], []
    t0 = time.time()
    use_amp = scaler is not None
    for i, (x, y) in enumerate(loader):
        x, y = x.to(DEVICE, non_blocking=True), y.to(DEVICE, non_blocking=True)
        with torch.set_grad_enabled(training):
            with torch.amp.autocast("cuda", enabled=use_amp):
                logits = model(x).squeeze(1)
                loss = loss_fn(logits, y)
            if training:
                optim.zero_grad()
                if use_amp:
                    scaler.scale(loss).backward()
                    scaler.step(optim)
                    scaler.update()
                else:
                    loss.backward()
                    optim.step()
        prob = torch.sigmoid(logits.float())
        pred = (prob > 0.5).long()
        total += loss.item() * x.size(0)
        n_correct += (pred == y).sum().item()
        n += x.size(0)
        all_p.append(prob.detach().cpu().numpy())
        all_y.append(y.cpu().numpy())
        if training and (i + 1) % log_every == 0:
            rate = n / (time.time() - t0)
            print(f"  batch {i+1}/{len(loader)}  loss={total/n:.4f}  acc={n_correct/n:.3f}  {rate:.1f} img/s", flush=True)
    return total / n, n_correct / n, np.concatenate(all_p), np.concatenate(all_y)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch", type=int, default=48)
    ap.add_argument("--lr", type=float, default=1e-6)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit-train", type=int, default=0, help="0 = all")
    ap.add_argument("--amp", action="store_true", default=True, help="mixed precision")
    args = ap.parse_args()

    print(f"Device: {DEVICE}")
    idx = build_index()
    print(f"Index: {idx.groupby(['split','label']).size().to_dict()}")
    idx.to_csv(OUT / "index.csv", index=False)

    train_df = idx[idx.split == "train"]
    valid_df = idx[idx.split == "valid"]
    if args.limit_train:
        train_df = train_df.sample(n=args.limit_train, random_state=0)

    train_ds = VerifierDataset(train_df, training=True)
    valid_ds = VerifierDataset(valid_df, training=False)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                          num_workers=args.workers, pin_memory=True, drop_last=True)
    valid_dl = DataLoader(valid_ds, batch_size=args.batch, shuffle=False,
                          num_workers=args.workers, pin_memory=True)

    model = build_model()
    optim = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = FocalLoss(0.25, 2.0)
    scaler = torch.amp.GradScaler("cuda") if args.amp else None
    print(f"AMP: {args.amp}, epochs: {args.epochs}, batch: {args.batch}", flush=True)

    history = []
    best_val = float("inf")
    has_val = len(valid_df) > 0
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr_loss, tr_acc, _, _ = run_epoch(model, train_dl, loss_fn, optim, True, scaler=scaler)
        if has_val:
            va_loss, va_acc, vp, vy = run_epoch(model, valid_dl, loss_fn, optim, False)
        else:
            va_loss, va_acc, vp, vy = float("nan"), float("nan"), None, None
        dt = time.time() - t0
        print(f"ep{ep}/{args.epochs} tr_loss={tr_loss:.4f} tr_acc={tr_acc:.3f} "
              f"va_loss={va_loss:.4f} va_acc={va_acc:.3f} ({dt:.0f}s)")
        history.append(dict(epoch=ep, tr_loss=tr_loss, tr_acc=tr_acc,
                            va_loss=va_loss, va_acc=va_acc, sec=dt))
        if has_val and va_loss < best_val:
            best_val = va_loss
            torch.save({"model": model.state_dict(), "args": vars(args)},
                       OUT / "verifier_best.pt")
            np.savez(OUT / "valid_probs_best.npz", prob=vp, label=vy)
        elif not has_val:
            torch.save({"model": model.state_dict(), "args": vars(args)},
                       OUT / "verifier_last.pt")

    pd.DataFrame(history).to_csv(OUT / "train_history.csv", index=False)
    print(f"Best valid loss: {best_val:.4f} -> {OUT/'verifier_best.pt'}")


if __name__ == "__main__":
    main()
