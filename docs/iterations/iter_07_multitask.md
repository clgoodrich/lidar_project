# Iter 07 — Multi-task U-Net (pit + road + plat joint segmentation)

**Branch:** `pit-iter-06-dem-only` (created here; promote to its own branch when run)
**Date:** 2026-05-28
**Status:** Scaffolded, not yet trained
**Code:** `notebooks/wellsight/multitask/_multitask_unet.py`
**Outputs (planned):** `data/derivatives/9t/multitask_unet/`

## Goal / Hypothesis

Up to iter 06 we trained three separate U-Nets — `pit_unet_v2`, `road_unet`,
`plat_unet` — each with its own copy of the 4-level encoder and decoder. They
share the same input feature stack and the same spatial blocks, but no
parameters. That means:

1. **No cross-task signal.** The pit model never sees that "this region is
   inside a known plat" — exactly the context a human annotator uses.
2. **Three times the training cost** for what is largely the same encoder
   work (LRMs, slope, TPI, openness — all describing micro-topography).
3. **No principled handling of confounders.** A road cut next to a plat edge
   often fires the pit head as a false positive; the pit model has no
   gradient pushing it to suppress road-shaped features specifically.

Iter 07 tests whether **a single shared encoder + three task-specific
decoders** can match or beat the per-task models, while baking in
roads/not_roads/plats as auxiliary supervision that should pull the encoder
toward features that disambiguate all three classes simultaneously.

## Architecture

`MultiHeadUNet` (in `multitask/_multitask_unet.py`):

- **Shared encoder** — identical to `_dl.UNet` down-path: 4 conv-BN-ReLU
  blocks + bottleneck, base=32, in_ch=7. Reuses `_cbr` from `_dl.py`.
- **Three independent heads** (`_Head`), each a full U-Net up-path with skip
  connections back to the shared encoder, ending in a 1×1 conv:
  - `pit` head — 3 classes (bg / floor / wall)
  - `road` head — 2 classes (bg / road)
  - `plat` head — 2 classes (bg / plat)
- **Param count:** 13.9 M (vs ~8 M for a single-head U-Net, ~24 M for three
  independent U-Nets — so ~42 % savings against the per-task ensemble).

Independent decoders (rather than a single decoder with three output convs)
are a deliberate cost. A bad gradient on one task can't corrupt another
task's decoder filters; only the shared encoder absorbs cross-task pressure.

## Sampler

`MultiLabelPatchSampler` opens the features raster and **all three label
rasters** (`labels_pit_9t_05.tif`, `labels_road_9t_05.tif`,
`labels_plat_9t_05.tif`) and returns a 4-tuple `(feat, lbl_pit, lbl_road,
lbl_plat)` for the same window. Every patch contributes to every head's loss.

Sampling policies (cycled per `__getitem__`, plus one random-background
slot — so stride = 5):

| Slot | Source | Jitter | Rationale |
|---|---|---|---|
| 0 | pit centroid (`pit_dataset_manifest.csv`) | 30 m | Centers on pits |
| 1 | plat centroid (`plat_dataset_manifest.csv`) | 40 m | Centers on well pads |
| 2 | road midpoint (`road_dataset_manifest.csv`, kind=road) | 30 m | Centers on roads |
| 3 | **not_road** midpoint (kind=not_road) | 30 m | **Hard-negative** for road head — drainages, footpaths, terrain edges that look road-shaped but aren't |
| 4 | uniform inside a random training block | — | Background context, ensures the encoder isn't overfit to feature-dense windows |

Augmentation is D4 (rot90 × flip) applied jointly to feat + all three label
tiles so they stay aligned. Patch size is **384 px (192 m at 0.5 m/px)** —
matches the plat trainer (plats need that context), still leaves plenty of
margin around centered pits/roads, and is divisible by 16 for the 4-level
encoder.

## Loss

Three `FocalCE` instances, one per head, with the same per-class `alpha`
weights the per-task trainers already use:

- pit: α = (0.05, 0.475, 0.475), γ = 2.0
- road: α = (0.10, 0.90), γ = 2.0
- plat: α = (0.15, 0.85), γ = 2.0

Combined loss:

```
L = 1.0 · L_pit + 0.6 · L_road + 0.6 · L_plat
```

Pit gets the highest weight because pits are the actual detection target.
Road and plat are auxiliary supervision — we care about them mostly because
they should push the encoder toward features that suppress pit false
positives. If road/plat heads dominate the gradient, the pit head won't
specialize enough.

## Score / checkpoint criterion

The "best" epoch is the one that maximises:

```
score = mean( miou(pit_floor, pit_wall),  iou(road),  iou(plat) )
```

i.e., the three heads weighted equally on the metric we actually care about.
This intentionally differs from the loss weighting — the loss is tuned for
gradient balance during training; the score is tuned for downstream
usefulness at eval.

## Outputs

Under `data/derivatives/9t/multitask_unet/`:

- `best.pt` — checkpoint (state_dict + mu/sd + cfg + head_classes)
- `train_log.csv` — per-epoch losses (all + per-head) and per-class IoUs
- `pit_prob.tif`, `pit_argmax.tif` — full-tile pit foreground prob + argmax
- `road_prob.tif`, `road_argmax.tif`
- `plat_prob.tif`, `plat_argmax.tif`

Inference uses sliding-window with PATCH=384, OVERLAP=96, averaging softmax
over overlapping cells (same scheme as `_dl.predict_full_tile`).

## How to run

```bash
# Smoke test (1 epoch, default batch=8) — verifies all readers + heads work
python notebooks/wellsight/multitask/_multitask_unet.py --smoke

# Full run
python notebooks/wellsight/multitask/_multitask_unet.py --epochs 40 --batch 8

# Train only, no full-tile inference at the end
python notebooks/wellsight/multitask/_multitask_unet.py --epochs 40 --no-infer
```

## Expected results / comparison plan

Baselines to beat (from per-task trainers, same blocks, same features, same
test split):

- `pit_unet_v2`     — val mean(floor, wall) IoU on `pit_unet_v2/train_log.csv`
- `road_unet`       — test pixel-IoU + line-AP in `road_unet/test_metrics.json`
- `plat_unet`       — test pixel-IoU + mean per-plat IoU in `plat_unet/test_metrics.json`

Multi-task is a **win** if `score` at convergence ≥ mean of the three
per-task scores AND any individual head doesn't drop more than ~0.05 IoU
vs its solo counterpart. A drop on plat with a big gain on pit is still
acceptable; a big drop on pit is not.

## Open questions / follow-ups

- **Loss weighting** is set by intuition; if pit underperforms at convergence
  consider dynamic weighting (e.g. uncertainty weighting from Kendall et al.)
  or freezing road/plat heads after they stabilise.
- **Encoder transfer** — once trained, the shared encoder might be a better
  starting point for fine-tuning on other regions (Marcellus, Oil Creek)
  than the pit-only encoder. Test by initializing iter 08 from this ckpt.
- **Not_road samples** currently feed only the road head; consider expanding
  them to also assert background for the pit head (no pit should land on a
  drainage/cornrow scar either).
