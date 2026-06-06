"""Generate notebooks/wellsight/training_walkthrough.ipynb.

A teaching notebook for the pit Mask R-CNN training pipeline: it loads the
inputs (feature stack + annotations), shows one labelled patch, builds the
dataset and the model, runs a short SMOKE training loop, and then runs the
just-trained model on a held-out patch. It imports the real production pieces
(PitPatchDataset / build_model / val_loss from pits/_pit_maskrcnn.py) so it is a
faithful, runnable explanation of what that script does.

Regenerate (and re-execute, embedding fresh outputs) with:
    C:/Python313/python.exe notebooks/wellsight/build/_make_training_walkthrough_nb.py --run
"""
from __future__ import annotations

import argparse
from pathlib import Path

import nbformat as nbf
from nbformat.v4 import new_code_cell, new_markdown_cell, new_notebook

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
OUT_NB = ROOT / "notebooks" / "wellsight" / "training_walkthrough.ipynb"


def md(t):
    return new_markdown_cell(t)


def code(t):
    return new_code_cell(t.strip("\n"))


def build_cells() -> list:
    cells: list = []

    cells.append(md(
        "# WellSight — Model Training Walkthrough (Pit Detector)\n"
        "\n"
        "This notebook shows **how a detector is trained**, one step per cell: inputs "
        "in → trained model out. It uses the **pit** instance-segmentation model "
        "(torchvision Mask R-CNN) as the example; the pad model works the same way.\n"
        "\n"
        "It imports the real production pieces from "
        "`notebooks/wellsight/pits/_pit_maskrcnn.py` and "
        "`notebooks/wellsight/_instance_common.py`, so what you see here is exactly "
        "what the training script does — just unpacked and visualised.\n"
        "\n"
        "**The flow**\n"
        "0. **Inputs** — the 7-band feature stack + the hand-drawn pit polygons.\n"
        "1. **Peek at one labelled example** — patch + its floor/wall masks.\n"
        "2. **Build the patch dataset** — jittered training patches + targets.\n"
        "3. **Build the model** — COCO-pretrained Mask R-CNN, widened to 7 bands.\n"
        "4. **Train** (a short smoke run) — watch the loss fall.\n"
        "5. **Run the trained model** on a held-out patch.\n"
        "\n"
        "> ⚠️ This runs a **smoke training** (1–2 epochs, a couple of patches per pit) "
        "so it finishes in a few minutes. The real run is "
        "`python notebooks/wellsight/pits/_pit_maskrcnn.py --epochs 30`, which saves "
        "`best.pt`. Don't judge accuracy from this notebook's tiny run."
    ))

    # ---- 0. INPUTS -------------------------------------------------------
    cells.append(md(
        "## 0. Inputs — feature stack + annotations\n"
        "\n"
        "Two things go in:\n"
        "* **The 7-band feature stack** `features_pit_9t_05.tif` — the terrain "
        "derivatives from the *derivatives* notebook, stacked into one image. We load "
        "the per-band normalisation stats (`mu`, `sd`) so patches can be z-scored.\n"
        "* **The annotations** — hand-drawn `pit_inside` (floor) and `pit_outside` "
        "(wall) polygons, split into train / val / test."
    ))
    cells.append(code(r'''
import sys
from pathlib import Path
import numpy as np
import torch
import matplotlib.pyplot as plt

ROOT = Path(r"C:\Users\colto\Documents\GitHub\lidar_project")
# put the package dirs on the path so the real modules import cleanly
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight"))
sys.path.insert(0, str(ROOT / "notebooks" / "wellsight" / "pits"))

import _instance_common as ic                       # the shared data helpers
from _pit_maskrcnn import (                          # the real training pieces
    PitPatchDataset, build_model, val_loss, collate, DEVICE,
)

print("device:", DEVICE)
print("feature channels:", ic.FEATURE_CHANNELS)

# per-band mean/std for z-scoring the 7 bands
mu, sd = ic.load_feature_stats()
print("mu:", np.round(mu, 3))
print("sd:", np.round(sd, 3))

# annotations with floor + wall classes, joined to the train/val/test split
pit_set = ic.load_pit_set(with_walls=True)
for split in ("train", "val", "test"):
    g = pit_set.for_split(split)
    print(f"  {split:5s}: {len(g):3d} polygons")
''' ))

    # ---- 1. PEEK AT ONE EXAMPLE -----------------------------------------
    cells.append(md(
        "## 1. Peek at one labelled example\n"
        "\n"
        "Load the full feature stack into RAM once (≈1.3 GB, ~20 s), then cut a patch "
        "centred on one training pit and show three of its feature bands next to the "
        "**floor** (red) and **wall** (cyan) masks the human drew. This is the kind of "
        "(input, answer) pair the model learns from."
    ))
    cells.append(code(r'''
from rasterio.features import rasterize
from shapely.geometry import box as shp_box
import rasterio

# load + z-score the whole stack once; cached in RAM and reused everywhere below
feat_arr = ic.load_feature_array(mu, sd)          # (7, H, W) float32
parent_tf = ic.feature_parent_transform()
print("feature stack:", feat_arr.shape)

# pick one training pit (its floor polygon) and centre a patch on it
train_floor = pit_set.for_split("train")
train_floor = train_floor[train_floor.cls == "floor"] if "cls" in train_floor.columns else train_floor
g0 = train_floor.geometry.iloc[0]
cx, cy = g0.centroid.x, g0.centroid.y
PATCH = 256
win = ic.patch_window_around(float(cx), float(cy), parent_tf, PATCH)
patch = ic.slice_feat_patch(feat_arr, win)         # (7, 256, 256) z-scored

# rasterize the floor + wall polygons that fall in this window, for display
tf = rasterio.windows.transform(win, parent_tf)
minx, miny, maxx, maxy = rasterio.windows.bounds(win, parent_tf)
pbox = shp_box(minx, miny, maxx, maxy)
polys = ic.polygons_intersecting(pit_set.gdf, win, parent_tf)
floor_m = np.zeros((PATCH, PATCH), np.uint8)
wall_m  = np.zeros((PATCH, PATCH), np.uint8)
for r in polys.itertuples():
    clip = r.geometry.intersection(pbox)
    if clip.is_empty:
        continue
    m = rasterize([(clip, 1)], out_shape=(PATCH, PATCH), transform=tf, fill=0, dtype="uint8")
    if getattr(r, "cls", "floor") == "wall":
        wall_m |= m
    else:
        floor_m |= m

# show three feature bands + the masks overlaid on band 0
names = ic.FEATURE_CHANNELS
fig, axes = plt.subplots(1, 4, figsize=(20, 5))
for ax, b in zip(axes[:3], (0, 2, 4)):
    ax.imshow(patch[b], cmap="RdBu_r", vmin=-2, vmax=2)
    ax.set_title(f"band {b}: {names[b]} (z-scored)", fontsize=10)
    ax.set_xticks([]); ax.set_yticks([])
ax = axes[3]
ax.imshow(patch[0], cmap="gray", vmin=-2, vmax=2)
ax.imshow(np.ma.masked_where(floor_m == 0, floor_m), cmap="autumn", alpha=0.6)
ax.imshow(np.ma.masked_where(wall_m == 0, wall_m), cmap="cool", alpha=0.6)
ax.set_title("labels: floor (red) + wall (cyan)", fontsize=10)
ax.set_xticks([]); ax.set_yticks([])
plt.tight_layout(); plt.show()
''' ))

    # ---- 2. DATASET ------------------------------------------------------
    cells.append(md(
        "## 2. Build the patch dataset\n"
        "\n"
        "`PitPatchDataset` turns the polygons into training samples. For each pit it "
        "cuts a 256×256 patch; for the **train** split it makes several per pit, each "
        "nudged by a random offset (*jitter*) so the model can't memorise exact "
        "positions. Each sample is a `(feature_patch, target)` pair, where the target "
        "is the torchvision dict: boxes + per-instance masks + class labels "
        "(1=floor, 2=wall).\n"
        "\n"
        "We use a small `patches_per_inst` here to keep the smoke run quick."
    ))
    cells.append(code(r'''
SMOKE_PATCHES_PER_INST = 2     # production default is 4

train_ds = PitPatchDataset(pit_set, "train", mu, sd, seed=42,
                           patches_per_inst=SMOKE_PATCHES_PER_INST)
val_ds   = PitPatchDataset(pit_set, "val",   mu, sd, seed=43,
                           patches_per_inst=1)
print(f"train patches: {len(train_ds)}   val patches: {len(val_ds)}")

# pull one sample and inspect the target the model will be trained against
feat_t, target = train_ds[0]
print("feature patch tensor:", tuple(feat_t.shape), feat_t.dtype)
print("  boxes :", tuple(target["boxes"].shape), "(x0,y0,x1,y1 per instance)")
print("  labels:", target["labels"].tolist(), " (1=floor, 2=wall)")
print("  masks :", tuple(target["masks"].shape), "(one binary mask per instance)")

# draw the boxes over band 0 of the patch
import matplotlib.patches as mpatches
fig, ax = plt.subplots(figsize=(6, 6))
ax.imshow(feat_t[0].numpy(), cmap="gray", vmin=-2, vmax=2)
for (x0, y0, x1, y1), lab in zip(target["boxes"].tolist(), target["labels"].tolist()):
    color = "red" if lab == 1 else "cyan"
    ax.add_patch(mpatches.Rectangle((x0, y0), x1-x0, y1-y0, fill=False,
                                    edgecolor=color, linewidth=2))
ax.set_title("one training target: boxes (floor=red, wall=cyan)", fontsize=11)
ax.set_xticks([]); ax.set_yticks([])
plt.show()
''' ))

    # ---- 3. MODEL --------------------------------------------------------
    cells.append(md(
        "## 3. Build the model\n"
        "\n"
        "`build_model` starts from a **COCO-pretrained** Mask R-CNN "
        "(`maskrcnn_resnet50_fpn_v2`, ~45.9 M params) and adapts it two ways:\n"
        "* **First-conv widening** — the pretrained stem expects 3 channels (RGB); we "
        "replace it with a 7-channel conv, copying the RGB weights into the first 3 "
        "slots and warm-starting the extra 4 from their mean. This keeps all the "
        "pretrained shape/edge knowledge while accepting our 7-band stack.\n"
        "* **New heads** — the classification/box and mask heads are reinitialised for "
        "**3 classes** (background / floor / wall)."
    ))
    cells.append(code(r'''
n_ch = len(ic.FEATURE_CHANNELS)
model = build_model(num_classes=3, in_channels=n_ch).to(DEVICE)

conv1 = model.backbone.body.conv1
n_params = sum(p.numel() for p in model.parameters()) / 1e6
print(f"params: {n_params:.1f} M")
print(f"stem conv1 now accepts {conv1.in_channels} input channels "
      f"(was 3 for RGB) -> out {conv1.out_channels}")
print("box predictor classes:", model.roi_heads.box_predictor.cls_score.out_features,
      "(bg / floor / wall)")
''' ))

    # ---- 4. TRAIN --------------------------------------------------------
    cells.append(md(
        "## 4. Train (smoke run)\n"
        "\n"
        "The training loop is the heart of it: for each batch of patches the model "
        "**predicts**, the loss says **how wrong** it was (Mask R-CNN sums five "
        "losses: region-proposal objectness + box, then classifier + box-refine + "
        "mask), we **back-propagate**, clip the gradients, and the optimizer **nudges** "
        "the weights. After each epoch we measure validation loss the same way. "
        "(The real script runs ~30 epochs with a cosine learning-rate schedule and "
        "saves the best-val checkpoint to `best.pt`.)"
    ))
    cells.append(code(r'''
from torch.utils.data import DataLoader

EPOCHS = 2          # smoke; production uses ~30
BATCH  = 2
LR     = 5e-4

train_loader = DataLoader(train_ds, batch_size=BATCH, shuffle=True,
                          num_workers=0, collate_fn=collate)
val_loader   = DataLoader(val_ds,   batch_size=BATCH, shuffle=False,
                          num_workers=0, collate_fn=collate)
optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                              lr=LR, weight_decay=1e-4)

history = []
for epoch in range(EPOCHS):
    model.train()
    running, n = 0.0, 0
    for imgs, targets in train_loader:
        imgs = [im.to(DEVICE) for im in imgs]
        targets = [{k: (v.to(DEVICE) if torch.is_tensor(v) else v) for k, v in t.items()}
                   for t in targets]
        if all(len(t["boxes"]) == 0 for t in targets):   # skip empty patches
            continue
        loss_dict = model(imgs, targets)       # forward -> dict of 5 losses
        loss = sum(loss_dict.values())         # total loss
        optimizer.zero_grad()
        loss.backward()                        # back-propagate
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
        optimizer.step()                       # update weights
        running += float(loss); n += 1
    tr = running / max(n, 1)
    va = val_loss(model, val_loader)           # same loss, no weight update
    history.append((tr, va))
    print(f"  epoch {epoch}:  train_loss={tr:.3f}   val_loss={va:.3f}")

# plot the (very short) loss curve
h = np.array(history)
plt.figure(figsize=(6, 4))
plt.plot(h[:, 0], "o-", label="train")
plt.plot(h[:, 1], "s-", label="val")
plt.xlabel("epoch"); plt.ylabel("loss"); plt.legend()
plt.title("smoke training loss (2 epochs)"); plt.grid(alpha=0.3); plt.show()
''' ))

    # ---- 5. INFERENCE ON A PATCH ----------------------------------------
    cells.append(md(
        "## 5. Run the trained model on a held-out patch\n"
        "\n"
        "Finally, put the model in eval mode and run it on a patch centred on a "
        "**test** pit it never saw during training. The model returns boxes, masks, "
        "and confidence scores; we keep detections above score 0.3 and draw their "
        "masks. (With only 2 epochs the masks will be rough — the point is to see the "
        "input → prediction path. The full pipeline does this with a sliding window "
        "over the entire tile in `_pit_maskrcnn_infer.py`.)"
    ))
    cells.append(code(r'''
model.eval()

# centre a patch on a test-split pit
test_floor = pit_set.for_split("test")
test_floor = test_floor[test_floor.cls == "floor"] if "cls" in test_floor.columns else test_floor
gt = test_floor.geometry.iloc[0]
win = ic.patch_window_around(float(gt.centroid.x), float(gt.centroid.y), parent_tf, PATCH)
patch = ic.slice_feat_patch(feat_arr, win)
img_t = torch.from_numpy(patch).to(DEVICE)

with torch.no_grad():
    out = model([img_t])[0]
scores = out["scores"].cpu().numpy()
masks  = out["masks"].cpu().numpy()[:, 0]
labels = out["labels"].cpu().numpy()
keep = scores >= 0.3
print(f"detections above score 0.3: {keep.sum()}  (raw {len(scores)})")

fig, ax = plt.subplots(figsize=(7, 7))
ax.imshow(patch[0], cmap="gray", vmin=-2, vmax=2)
for m, lab, s in zip(masks[keep], labels[keep], scores[keep]):
    cmap = "autumn" if lab == 1 else "cool"
    ax.imshow(np.ma.masked_where(m < 0.5, m), cmap=cmap, alpha=0.5)
ax.set_title("predicted masks on a held-out test pit (floor=warm, wall=cool)", fontsize=11)
ax.set_xticks([]); ax.set_yticks([])
plt.show()
''' ))

    # ---- RECAP -----------------------------------------------------------
    cells.append(md(
        "## Recap — how this maps to the real pipeline\n"
        "\n"
        "| Notebook step | Production code |\n"
        "|---|---|\n"
        "| Load stats + annotations | `_instance_common.load_feature_stats` / `load_pit_set` |\n"
        "| Patch dataset + jitter | `_pit_maskrcnn.PitPatchDataset` |\n"
        "| Build model (conv1 widening) | `_pit_maskrcnn.build_model` |\n"
        "| Train loop + val loss | `_pit_maskrcnn.train_one_epoch` / `val_loss` → saves `best.pt` |\n"
        "| Per-patch inference | scaled up to a sliding window in `_pit_maskrcnn_infer.py` |\n"
        "\n"
        "**To train for real** (saves `best.pt`, logs per-epoch metrics):\n"
        "```\n"
        "python notebooks/wellsight/pits/_pit_maskrcnn.py --epochs 30 --batch 4\n"
        "```\n"
        "**Then run full-tile inference + scoring:**\n"
        "```\n"
        "python notebooks/wellsight/pits/_pit_maskrcnn_infer.py\n"
        "```\n"
        "The pad detector mirrors this exactly via `plats/_pad_maskrcnn.py` "
        "(patch 384, single foreground class)."
    ))
    return cells


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", action="store_true",
                    help="execute the notebook so outputs/plots are embedded")
    args = ap.parse_args()

    nb = new_notebook(cells=build_cells())
    nb.metadata["kernelspec"] = {
        "display_name": "Python 3", "language": "python", "name": "python3",
    }

    if args.run:
        from nbclient import NotebookClient
        client = NotebookClient(
            nb, timeout=1800, kernel_name="python3",
            resources={"metadata": {"path": str(OUT_NB.parent)}},
        )
        print("executing notebook (loads 1.3 GB stack + smoke-trains on GPU)...")
        client.execute()

    nbf.write(nb, OUT_NB)
    print(f"wrote {OUT_NB.relative_to(ROOT)}  ({len(nb.cells)} cells)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
