"""Pit instance segmentation with Mask R-CNN (torchvision, ResNet-50 FPN v2).

Single foreground class ("pit") trained on the 110 hand-annotated pit_inside
polygons (74 train / 16 val / 20 test, per pit_dataset_manifest.csv).

Inputs:
    data/derivatives/tiles/9t/rgb3_9t_05.tif      (3-band float32 composite, auto-built)
    data/derivatives/annotations/annotations_proj.gpkg (pit_inside layer)
    data/derivatives/tiles/9t/pit_dataset_manifest.csv       (split assignments)

Outputs under data/derivatives/tiles/9t/iterations/pit_07_maskrcnn/:
    best.pt         best-val checkpoint
    train_log.csv   per-epoch metrics

Run:
    python notebooks/wellsight/pits/_pit_maskrcnn.py --epochs 30 --batch 4
    python notebooks/wellsight/pits/_pit_maskrcnn.py --smoke
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
from torchvision.models.detection import maskrcnn_resnet50_fpn_v2
from torchvision.models.detection.faster_rcnn import FastRCNNPredictor
from torchvision.models.detection.mask_rcnn import MaskRCNNPredictor

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, path_for  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = path_for("models_retired") / "pit_07_maskrcnn"
PATCH = 256          # 128 m at 0.5 m/px - matches pit_unet_v2 baseline
JITTER_M = 30.0      # matches pit_unet_v2
PATCHES_PER_INST = 4 # 74 train x 4 = ~300 training patches per epoch
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


class PitPatchDataset(Dataset):
    """Centred-on-pit patches with jitter. Builds Mask R-CNN targets on the fly."""

    def __init__(self, inst: ic.InstanceSet, split: str, mu: np.ndarray,
                 sd: np.ndarray, patch: int = PATCH, jitter_m: float = JITTER_M,
                 patches_per_inst: int = PATCHES_PER_INST, seed: int = 0):
        self.inst = inst
        self.split = split
        self.mu, self.sd = mu, sd
        self.patch = patch
        self.patches_per_inst = patches_per_inst
        self.feat = ic.load_feature_array(mu, sd)   # cached in-RAM (C,H,W)
        self.parent_tf = ic.feature_parent_transform()
        gdf_split = inst.for_split(split)
        # Center one patch per pit (use floor polygons; walls share the centroid).
        if "cls" in gdf_split.columns and (gdf_split.cls == "floor").any():
            gdf_split = gdf_split[gdf_split.cls == "floor"]
        centers = np.array([[g.centroid.x, g.centroid.y] for g in gdf_split.geometry])
        rng = np.random.default_rng(seed)
        if split == "train":
            self.centers = ic.jittered_centers(centers, jitter_m, rng, patches_per_inst)
        else:
            self.centers = centers  # deterministic, one patch per pit
        # Full polygon set (not just split) for mask building - so off-split pits
        # falling inside a patch still get masked.
        self.all_polys = inst.gdf

    def __len__(self) -> int:
        return len(self.centers)

    def __getitem__(self, idx: int):
        cx, cy = self.centers[idx]
        win = ic.patch_window_around(float(cx), float(cy), self.parent_tf, self.patch)
        feat = ic.slice_feat_patch(self.feat, win)  # (C, P, P) z-scored, in-RAM
        feat_t = torch.from_numpy(feat)
        polys = ic.polygons_intersecting(self.all_polys, win, self.parent_tf)
        target = ic.build_maskrcnn_target(polys, win, self.parent_tf, self.patch)
        target["image_id"] = torch.tensor([idx], dtype=torch.int64)
        return feat_t, target


def collate(batch):
    images, targets = zip(*batch)
    return list(images), list(targets)


def build_model(num_classes: int = 2, in_channels: int = 3) -> torch.nn.Module:
    """Mask R-CNN ResNet50-FPN v2, COCO-pretrained.

    in_channels > 3: widen the backbone's first conv to accept the full UNet
    feature stack. Pretrained RGB weights are copied into the first 3 input
    slots; the extra channels are warm-started from the mean of the RGB
    weights. Everything downstream keeps full COCO pretraining. Because feature
    patches are pre-normalised (z-scored), the detector's input transform is set
    to identity (mean 0 / std 1) over all channels.
    """
    model = maskrcnn_resnet50_fpn_v2(weights="DEFAULT")
    if in_channels != 3:
        old = model.backbone.body.conv1
        new = torch.nn.Conv2d(in_channels, old.out_channels,
                              kernel_size=old.kernel_size, stride=old.stride,
                              padding=old.padding, bias=(old.bias is not None))
        with torch.no_grad():
            w = old.weight  # (64, 3, 7, 7)
            new.weight[:, :3] = w
            if in_channels > 3:
                extra = w.mean(dim=1, keepdim=True).repeat(1, in_channels - 3, 1, 1)
                new.weight[:, 3:] = extra
        model.backbone.body.conv1 = new
        # Patches are pre-normalised -> identity transform over all channels.
        model.transform.image_mean = [0.0] * in_channels
        model.transform.image_std = [1.0] * in_channels
    in_features = model.roi_heads.box_predictor.cls_score.in_features
    model.roi_heads.box_predictor = FastRCNNPredictor(in_features, num_classes)
    in_features_mask = model.roi_heads.mask_predictor.conv5_mask.in_channels
    model.roi_heads.mask_predictor = MaskRCNNPredictor(
        in_features_mask, 256, num_classes,
    )
    return model


@torch.no_grad()
def val_loss(model, loader) -> float:
    # torchvision Mask R-CNN only emits losses in train() mode, but accepts
    # eval-style inference in eval(). Use train() + no_grad to get val loss.
    model.train()
    total, n = 0.0, 0
    for imgs, targets in loader:
        imgs = [im.to(DEVICE) for im in imgs]
        targets = [{k: v.to(DEVICE) if torch.is_tensor(v) else v for k, v in t.items()}
                   for t in targets]
        # Skip degenerate batches (no boxes at all).
        if all(len(t["boxes"]) == 0 for t in targets):
            continue
        loss_dict = model(imgs, targets)
        total += float(sum(loss_dict.values()))
        n += 1
    return total / max(n, 1)


def train_one_epoch(model, loader, optimizer) -> float:
    model.train()
    total, n = 0.0, 0
    for imgs, targets in loader:
        imgs = [im.to(DEVICE) for im in imgs]
        targets = [{k: v.to(DEVICE) if torch.is_tensor(v) else v for k, v in t.items()}
                   for t in targets]
        if all(len(t["boxes"]) == 0 for t in targets):
            continue
        loss_dict = model(imgs, targets)
        loss = sum(loss_dict.values())
        optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()
        total += float(loss)
        n += 1
    return total / max(n, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--batch", type=int, default=4)
    ap.add_argument("--lr", type=float, default=5e-4)
    ap.add_argument("--workers", type=int, default=0)
    ap.add_argument("--seed", type=int, default=0,
                    help="global RNG seed; fixes head init + batch order (GPU "
                         "training is still not bit-exact — roi_align backward)")
    ap.add_argument("--smoke", action="store_true",
                    help="1 epoch, 2 patches/pit - sanity check the pipeline")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 1
        global PATCHES_PER_INST
        PATCHES_PER_INST = 2

    # Pin RNGs (head init + batch order). NB: GPU Mask R-CNN is still not
    # bit-exact run to run — roi_align backward has no deterministic kernel.
    ic.set_determinism(args.seed)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    print(f"Device: {DEVICE}  seed: {args.seed}")
    # Full 7-band UNet feature stack (lrm_25/lrm_5/slope/tpi_05/openness±/roughness_11).
    mu, sd = ic.load_feature_stats()
    n_ch = len(mu)
    print(f"feature channels ({n_ch}): {ic.FEATURE_CHANNELS}")

    # 3-class: bg (0) / floor (1) / wall (2). Walls come from pit_full.
    pit_set = ic.load_pit_set(with_walls=True)
    train_ds = PitPatchDataset(pit_set, "train", mu, sd, seed=42,
                               patches_per_inst=PATCHES_PER_INST)
    val_ds = PitPatchDataset(pit_set, "val", mu, sd, seed=43,
                             patches_per_inst=1)
    print(f"train patches: {len(train_ds)}  val patches: {len(val_ds)}")

    train_loader = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                              num_workers=args.workers, collate_fn=collate,
                              generator=ic.make_loader_generator(args.seed),
                              worker_init_fn=ic.seed_worker)
    val_loader = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                            num_workers=args.workers, collate_fn=collate,
                            worker_init_fn=ic.seed_worker)

    model = build_model(num_classes=3, in_channels=n_ch).to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters()) / 1e6
    print(f"Mask R-CNN params: {n_params:.1f} M")

    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                                  lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    log_path = OUTDIR / "train_log.csv"
    log_path.write_text("epoch,tr_loss,va_loss,lr,sec\n")
    best_val = float("inf")

    for epoch in range(args.epochs):
        t0 = time.time()
        tr_loss = train_one_epoch(model, train_loader, optimizer)
        va_loss = val_loss(model, val_loader)
        sched.step()
        dt = time.time() - t0
        lr_now = optimizer.param_groups[0]["lr"]
        print(f"  ep {epoch:02d}  tr={tr_loss:.3f}  va={va_loss:.3f}  "
              f"lr={lr_now:.2e}  {dt:.1f}s")
        with log_path.open("a", newline="") as f:
            csv.writer(f).writerow([epoch, tr_loss, va_loss, lr_now, dt])
        if va_loss < best_val:
            best_val = va_loss
            torch.save({
                "state_dict": model.state_dict(),
                "epoch": epoch,
                "patch": PATCH,
                "num_classes": 3,
                "class_names": ["bg", "floor", "wall"],
                "in_channels": n_ch,
                "channels": list(ic.FEATURE_CHANNELS),
                "mu": mu, "sd": sd,
                "val_loss": va_loss,
                "arch": "maskrcnn_resnet50_fpn_v2",
                "seed": args.seed,
            }, OUTDIR / "best.pt")
            print(f"    saved best.pt (val={va_loss:.3f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
