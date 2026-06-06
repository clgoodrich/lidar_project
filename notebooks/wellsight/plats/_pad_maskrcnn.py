"""Plat (pad) instance segmentation with Mask R-CNN on 9t.

Single foreground class ("plat") trained on 79 hand-annotated pad polygons
(51 train / 16 val / 9 test). Larger patch than pits (384 px = 192 m) since
pads are typically 30-80 m across and need surrounding context for the model
to distinguish a pad scar from natural clearings.

Outputs under data/derivatives/9t/iterations/pad_05_maskrcnn/:
    best.pt         best-val checkpoint
    train_log.csv   per-epoch metrics
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
import rasterio
import torch
from torch.utils.data import DataLoader, Dataset

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pits"))
from _common import DERIV_9T  # noqa: E402
import _instance_common as ic  # noqa: E402
from _pit_maskrcnn import build_model, collate, train_one_epoch, val_loss, DEVICE  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "pad_05_maskrcnn"
PATCH = 384         # 192 m at 0.5 m/px - matches plat_unet baseline
JITTER_M = 40.0     # matches multitask_unet pad policy
PATCHES_PER_INST = 4


class PadPatchDataset(Dataset):
    def __init__(self, inst: ic.InstanceSet, split: str, mu: np.ndarray,
                 sd: np.ndarray, patch: int = PATCH, jitter_m: float = JITTER_M,
                 patches_per_inst: int = PATCHES_PER_INST, seed: int = 0):
        self.inst = inst
        self.mu, self.sd = mu, sd
        self.patch = patch
        self.feat = ic.load_feature_array(mu, sd)   # cached in-RAM (C,H,W)
        self.parent_tf = ic.feature_parent_transform()
        gdf_split = inst.for_split(split)
        centers = np.array([[g.centroid.x, g.centroid.y] for g in gdf_split.geometry])
        rng = np.random.default_rng(seed)
        if split == "train":
            self.centers = ic.jittered_centers(centers, jitter_m, rng, patches_per_inst)
        else:
            self.centers = centers
        self.all_polys = inst.gdf

    def __len__(self) -> int:
        return len(self.centers)

    def __getitem__(self, idx: int):
        cx, cy = self.centers[idx]
        win = ic.patch_window_around(float(cx), float(cy), self.parent_tf, self.patch)
        feat = ic.slice_feat_patch(self.feat, win)
        polys = ic.polygons_intersecting(self.all_polys, win, self.parent_tf)
        target = ic.build_maskrcnn_target(polys, win, self.parent_tf, self.patch)
        target["image_id"] = torch.tensor([idx], dtype=torch.int64)
        return torch.from_numpy(feat), target


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=2)  # larger patch -> smaller batch
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0,
                    help="global RNG seed; fixes head init + batch order (GPU "
                         "training is still not bit-exact — roi_align backward)")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 1

    # Pin RNGs (head init + batch order). NB: GPU Mask R-CNN is still not
    # bit-exact run to run — roi_align backward has no deterministic kernel.
    ic.set_determinism(args.seed)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    print(f"Device: {DEVICE}  seed: {args.seed}")
    mu, sd = ic.load_feature_stats()
    n_ch = len(mu)
    print(f"feature channels ({n_ch}): {ic.FEATURE_CHANNELS}")

    pad_set = ic.load_pad_set()
    ppi = 2 if args.smoke else PATCHES_PER_INST
    train_ds = PadPatchDataset(pad_set, "train", mu, sd, seed=42, patches_per_inst=ppi)
    val_ds = PadPatchDataset(pad_set, "val", mu, sd, seed=43, patches_per_inst=1)
    print(f"train patches: {len(train_ds)}  val patches: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, collate_fn=collate,
                              generator=ic.make_loader_generator(args.seed),
                              worker_init_fn=ic.seed_worker)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.workers, collate_fn=collate,
                            worker_init_fn=ic.seed_worker)

    model = build_model(num_classes=2, in_channels=n_ch).to(DEVICE)
    print(f"Mask R-CNN params: {sum(p.numel() for p in model.parameters())/1e6:.1f} M")

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                                  lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    log_path = OUTDIR / "train_log.csv"
    log_path.write_text("epoch,tr_loss,va_loss,lr,sec\n")
    best_val = float("inf")
    for epoch in range(args.epochs):
        t0 = time.time()
        tr = train_one_epoch(model, train_loader, optimizer)
        va = val_loss(model, val_loader)
        sched.step()
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"  ep {epoch:02d}  tr={tr:.3f}  va={va:.3f}  lr={lr_now:.2e}  {dt:.1f}s")
        with log_path.open("a", newline="") as f:
            csv.writer(f).writerow([epoch, tr, va, lr_now, dt])
        if va < best_val:
            best_val = va
            torch.save({
                "state_dict": model.state_dict(),
                "epoch": epoch, "patch": PATCH, "num_classes": 2,
                "in_channels": n_ch, "channels": list(ic.FEATURE_CHANNELS),
                "mu": mu, "sd": sd, "val_loss": va,
                "arch": "maskrcnn_resnet50_fpn_v2",
                "seed": args.seed,
            }, OUTDIR / "best.pt")
            print(f"    saved best.pt (val={va:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
