# Phase 3 — rasterisation and training prep

Companion to `phase_3_rasterization_training_prep.ipynb`.

Phase 3 is the handover. Phase 1 makes terrain derivatives from the point cloud.
Phase 2 turns the QGIS drawings into one clean GeoPackage. Phase 3 turns both
into the exact files a U-Net trainer opens, and nothing else.

Everything it writes lands in `data/<target_folder>/derived/`.

Set `target_folder` in cell 0 and the whole notebook follows. It currently reads
`OTHER_DATA`.

---

## What it produces

Twelve files. Cell 25 checks for all of them.

| file | what it is |
|---|---|
| `features_pit_<area>_1m.tif` | the 7-band input stack |
| `feature_stats_1m.json` | per-channel mean and standard deviation |
| `labels_pit_<area>_1m.tif` | 0 background, 1 pit floor, 2 pit wall |
| `labels_pad_<area>_1m.tif` | 0 background, 1 pad |
| `labels_road_<area>_1m.tif` | 0 background, 1 road, 2 drainage |
| `labels_road_binary_<area>_1m.tif` | 0 background, 1 road |
| `mask_pad_<area>_1m.tif` | pad footprint, value 2 |
| `pit_blocks_<area>.gpkg` | the 144 blocks, carrying the pit split |
| `pad_blocks_<area>.gpkg` | the same blocks, carrying the pad split |
| `road_chunks_<area>.gpkg` | road geometry as ~40 m pieces, so eval can draw what it scored |
| `pit_dataset_manifest.csv` | one row per pit floor |
| `pad_dataset_manifest.csv` | one row per pad |
| `road_dataset_manifest.csv` | one row per road chunk |
| `road_classifier_samples.csv` | one row per point sampled along a line |

---

## The walkthrough

### Cell 0 — constants

Everything downstream keys off these.

- `RNG_SEED = 42`. The split is random, so it has to be a *reproducible* random.
  Change this and every train/val/test assignment changes with it.
- `SPLIT_FRACS = {train 0.70, val 0.15, test 0.15}`.
- `GRID_BLOCK_X_DIM, GRID_BLOCK_Y_DIM = 12, 12` — a 12x12 grid, so 144 blocks.
- `ROAD_BUFFER_M = 1.5`, `DRAIN_BUFFER_M = 2.0`. Roads and channels are drawn as
  lines and have to become areas. Channels get the wider buffer because they are
  wider on the ground.
- `CHUNK_M = 40.0` — how long a road piece is. See cell 20.
- `SAMPLE_STRIDE_M = 4.0` — how far apart the classifier sample points sit.

### Cell 1 — one grid, fixed once

Opens the DEM and keeps its `transform`, height, width, bounds and CRS.

**Every raster written later uses this grid.** That is why the labels line up
with the features by construction rather than by luck. If a channel disagrees
with it, cell 10 raises rather than quietly resampling.

### Cells 2-3 — pit labels

Burns `pit_wall` as 2, then `pit_inside` as 1 **in that order**, so a pixel
inside both ends up as floor. Floor is the thing being delineated; wall is the
ring around it.

`label_profile` sets `nodata=255`. That is not cosmetic — the trainer's loss is
`FocalLoss(ignore=255)`, so 255 means "do not learn from this pixel".

Cell 3 writes a separate pad mask. It is a leftover; nothing reads it.

### Cell 5 — the block grid

Cuts the DEM extent into 12x12 rectangles and numbers them 0-143.

### Cell 7 — pits into blocks

Takes each pit floor's **centroid** and asks which block contains it, via
`sjoin(..., predicate="within")`.

Centroids rather than polygons on purpose. A pit straddling a block boundary
would otherwise be counted twice and could land in two splits at once.

### Cell 8 — the pit split

This is the part that matters most, and the reason it is not a plain random
split of pits:

**Training patches are sampled around features with 30 m of jitter.** A patch
centred on a training pit can physically overlap a neighbouring pit. If that
neighbour is in the test set, the model has seen its ground during training and
the test number is inflated. Splitting by *block* rather than by *pit* puts a
hard spatial wall between the sets.

The fill is **greedy on deficit, balanced by pit count, not block count.** Blocks
are shuffled once with `RNG_SEED`, then each block goes to whichever split is
furthest below its target. Pits cluster heavily on pads, so blocks hold wildly
different numbers of them — balancing block count would hand one split twice the
data and still call it 70/15/15.

Writes `pit_blocks_<area>.gpkg` and `pit_dataset_manifest.csv`.

### Cell 10 — the 7-band feature stack

Reads seven channels in a fixed order:

```
lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_5
```

**The order is frozen.** The trainer indexes bands by position, so a different
order silently feeds slope into the channel the model learned as openness.

Two things worth noticing:

The grid check. Each channel is compared against the DEM's transform and shape,
and a mismatch raises. Cheaper than discovering it as a bad training run.

**The statistics come from training blocks only.** `training_mask` is built by
rasterising just the `split == "train"` blocks, and mean/std/p2/p98 are computed
inside that mask. Using the whole tile would leak val and test pixels into the
normalisation constants — a small leak, but a real one, and free to avoid.

### Cell 12 — road labels, 3-class

Burns drainage as 2, then road as 1 **on top**, so a road crossing a channel
stays labelled road.

Drainage is its own class rather than background because the road model kept
firing on stream channels. Making drainage a class the model must *name* fixed
that in training instead of with a post-filter.

### Cell 14 — three helpers

- `chunk_line` — cuts a line into ~`CHUNK_M` pieces, preserving shape by
  interpolating intermediate vertices.
- `assign_split` — given a geometry or point, returns `(block_id, split)` by
  finding the block that contains it. Returns `(None, "unused")` for anything
  outside the grid.
- `sample_along_line` — points every `SAMPLE_STRIDE_M` along a line.

### Cells 17-18 — binary pad and road rasters

Simple 0/1 versions, for models that do not need the extra class.

### Cell 19 — pad manifest

One row per pad, with the block and split from `assign_split`.

**At this point `blocks_gdf` still carries the pit split**, so this manifest is
pad rows on the pit split. That is deliberate and matches the production script,
which propagates the pit split into the pad and road manifests. Cell 24 then
rewrites it on the pad split. If you want the pit-split version, take it before
cell 23 runs.

### Cell 20 — road chunk manifest

Roads and `not_roads` are cut into ~40 m chunks. Drainage is not.

**Why chunk at all.** A road can be a kilometre long. Sampling one patch per road
means one patch for that kilometre and one for a 30 m stub — the long road is
barely trained on and barely scored. Chunking makes every ~40 m its own sampling
centre and its own evaluation unit.

**Why `not_roads` are here.** They are lines a human looked at and ruled out.
Feeding them as hard negatives teaches the model "this linear feature is not a
road", which it cannot learn from background alone.

The geometry is written out as well as the table, so evaluation can draw exactly
what it scored rather than approximate it.

### Cell 21 — classifier sample points

Points every 4 m along roads and not_roads, labelled 1 and 0. Feeds the
non-U-Net road classifier.

### Cells 22-24 — the pad split

Same greedy fill as cell 8, balanced on pad count instead of pit count, writing
`pad_blocks_<area>.gpkg`.

**Why a second split at all.** Pads and pits are not distributed the same way —
995 pads hold 712 pit floors across the project, and blocks dense in one are not
dense in the other. A split balanced on pits can hand the pad model a badly
unbalanced 70/15/15.

Cell 24 then rewrites `pad_dataset_manifest.csv` against the pad split, so the
manifest and `pad_blocks_<area>.gpkg` agree. Without it they disagree and only
the blocks file knows.

### Cell 25 — handover check

Lists the expected outputs with sizes, then the row counts and split breakdown
for the three manifests. Anything MISSING is an input the trainer will not find.

---

## Ordering hazard

`blocks_gdf["split"]` is written **three times** in one run:

| cell | what it holds afterwards |
|---|---|
| 8 | the pit split |
| 10 | reads it to pick training blocks for the statistics |
| 23 | the pad split |

Top to bottom this is correct. Out of order it is silently wrong — re-running
cell 10 after cell 23 computes the channel statistics over the pad training
blocks, and nothing will complain. If you re-run anything in the second half of
the notebook, re-run from cell 8.

---

## What phase 3 does not do

- **No training.** That is `s3_train/`, and there is no phase 4 notebook yet.
- **No derivatives.** The seven channels must already exist in `SRC`; cell 10
  raises if one is missing.
- **No area outside the DEM.** Any annotation whose centroid falls outside the
  grid gets `block_id = None` and `split = "unused"`. That is how a manifest can
  hold more rows than the tile has features — the surplus are annotations
  elsewhere in the project.
