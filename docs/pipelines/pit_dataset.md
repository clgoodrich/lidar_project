# Pit Dataset Pipeline

End-to-end picture of how hand-drawn pit polygons become training tensors that feed a U-Net.

Cross-references: [annotations pipeline](annotations.md) for the polygon prep, [feature stack pipeline](feature_stack.md) for the input rasters.

## The whole flow

```
hand-drawn shapefiles (EPSG:4326)
    │
    ▼
_prep_annotations.py
    │   reproject to EPSG:6346
    │   validate / fix geometry
    │   build pit_wall = pit_outside - pit_inside
    │   spatial-join plat_id onto each layer
    ▼
annotations_proj.gpkg
    │
    ▼
_build_pit_dataset.py
    │   rasterize labels (0=bg, 1=floor, 2=wall) at 0.5 m
    │   chop tile into 12x12 spatial blocks
    │   pit-count-balanced split into train/val/test
    ▼
labels_pit_9t_05.tif  +  pit_blocks_9t.gpkg  +  pit_dataset_manifest.csv
    │
    ▼  (+ features_pit_9t_05.tif from feature stack pipeline)
PitTiles(Dataset) inside the trainer
    │   per __getitem__:
    │     1. pick a pit centroid (with jitter) or a random bg point in this split's blocks
    │     2. read a 256x256 window from features + labels
    │     3. z-score normalize via train-block stats
    │     4. 4-way rotation + horizontal-flip augmentation (train only)
    ▼
(C, H, W) float32 tensor + (H, W) int64 label tensor for the network
```

## Train / Val / Test discipline

- **Split unit is a 375 m spatial block**, never an individual pit. Two pits at the same site cannot land in different splits.
- **Pit-count balanced.** With 144 blocks and only 26 of them containing any pits, naive shuffling would yield wildly imbalanced splits. The assignment is greedy: shuffle the pit-bearing blocks (seed 42), assign each block to whichever split is most below its 70/15/15 pit-count target.

Resulting allocation:

| Split | Blocks | Pits | Purpose |
|---|---:|---:|---|
| train | 17 | 74 | Optimizer sees these. |
| val | 4 | 16 | Picks the best checkpoint per iteration. |
| test | 3 | 20 | **Untouched until the final iteration eval.** Headline numbers come from here. |
| unused | 120 | 0 | Empty blocks. Background sampling can still draw from these via the trainer's bg sampler — see below. |

The block boundaries are persisted at `data/derivatives/9t/pit_blocks_9t.gpkg`. Visualize them in QGIS to verify no leakage.

## Label rasterization details

Inside `_build_pit_dataset.py`:

```python
label = rasterize(
    shapes_wall + shapes_floor,    # walls burned first, floors on top
    out_shape=(H, W),
    transform=transform,
    fill=0,                         # background everywhere else
    dtype="uint8",
    all_touched=False,              # conservative — only pixels mostly inside the polygon
)
```

Burn order: wall pixels get value 2; floor pixels then overwrite with value 1 where they overlap. `all_touched=False` keeps boundary pixels from being aggressively claimed.

The product `labels_pit_9t_05.tif` is the **ground truth** that every pit model is scored against. Its class balance is on every label-rasterization page (and is brutal: 99.89% bg).

## Sampling inside the trainer

The `PitTiles(Dataset)` class in `_pit_unet_v2.py` (reused by iter 01 and iter 03's `PitTiles11`) implements per-epoch sampling:

```
__len__() = len(self.pits) * (1 + BG_PER_POS)  # 1 bg sample per pit by default
```

Per `__getitem__(idx)`:

- If `idx < len(self.pits)`: **pit-centered window**. Pick pit `idx`, jitter the center by ±30 m so the pit isn't always dead-center, read a 256 px (128 m) patch around it.
- Else: **random background window**. Pick a uniformly-random point inside one of this split's blocks, read a 256 px patch.

This gives a roughly 1:1 ratio of pit-centered to background patches per epoch, which is well-matched to focal-loss's alpha settings (0.05 bg / 0.475 floor / 0.475 wall).

Augmentation (train only): pick a random k ∈ {0, 1, 2, 3} and rotate the patch by 90k°. Independently, flip horizontally with probability 0.5. Labels are augmented identically.

## What this means in practice

- **Test contamination is not possible** through normal use of the split. Pit-centered windows can only land in train-blocks if the pit is in `train`. Background windows can only land in this split's block bounds.
- **The model never sees the exact same tile twice**, even if it picks the same pit, because of the ±30 m centroid jitter and the rotation/flip augmentation.
- **Background patches do not avoid pits in unused/test blocks.** They sample uniformly inside *this split's* blocks. So a train-bg patch may contain pit pixels if a pit happens to lie at the patch boundary — those pit pixels are labeled correctly (1 or 2), not zero. This is by design: it teaches the model to find pits that aren't centered.

## Manifest schema

`data/derivatives/9t/pit_dataset_manifest.csv` is the canonical per-pit table. 110 rows, columns:

| Column | Type | Meaning |
|---|---|---|
| `pit_id` | int | Stable identifier; matches `pit_id` in `annotations_proj.gpkg` |
| `plat_id` | int or NaN | Plat polygon this pit's centroid sits inside, if any |
| `block_id` | int | Spatial block this pit's centroid sits inside |
| `split` | str | One of `train`, `val`, `test`, `unused` |
| `centroid_x`, `centroid_y` | float | Pit centroid in EPSG:6346 (meters) |

The trainer reads this CSV and pulls `(centroid_x, centroid_y)` for every pit in its split.

## Adding new pits without breaking comparability

If new annotations are added, the **test set must not change**. The iterations to date all evaluate against the *same* 20 test pits — if you add new pits and reshuffle, the numbers in the leaderboard become incomparable.

Two safe ways to add pits:

1. **Append to train/val only.** Assign new pits to their natural blocks; if the natural block is currently `test`, force-assign the pit to `train` or `val`. Document the override in this file.
2. **Expand the test set in a labeled way.** Build a new manifest version (`pit_dataset_manifest_v2.csv`) that adds new test pits. Run all old models against it to extend the leaderboard. Don't overwrite the v1 numbers.

The safer default is (1) — only train/val grows, test stays fixed forever.
