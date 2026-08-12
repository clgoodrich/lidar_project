# Iteration: `_drainage_unet_1m.py` — drainage-focused U-Net (road model, flipped)

**Date:** 2026-06-16
**Script:** `notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py`
**Output:** `data/derivatives/tiles/9t/drainage_unet_1m/`
**Status:** trained, validated — clean drainage/road separation

## Goal
A dedicated **drainage** detector. Drainage already existed only as the negative
class in the road model; here it becomes the positive of interest. Symmetric twin
of `_road_unet_1m_recall.py`: identical 9t-clean data, channels, and 3-class label
raster (0=bg 1=road 2=drainage), with the focal weights flipped.

## Inputs / provenance
- **Features:** `tiles/9t/features_pit_9t_1m.tif` (7-band: lrm_25, lrm_5, slope,
  tpi_05, openness_pos, openness_neg, roughness_5), z-scored via `feature_stats_1m.json`.
- **Labels:** `tiles/9t/labels_road_9t_1m.tif` — class 2 = drainage (179,928 px),
  buffered drainage lines. Drainage chunks: 1067 train / 136 val / 249 test.
- GT lines: `annotations_proj.gpkg` layer `drainage` (1,791), clipped to 9t.

## Method
- 3-class U-Net (base=32), patch 256/overlap 64, D4 aug, jitter 30 m.
- **FOCAL_ALPHA = (0.10, 0.25, 0.72)** → bg, road(−, confuser), **drainage(+)**
  (road model was (0.10, 0.72, 0.25)). gamma 2.0, weight_decay 2e-4, lr 1e-3.
- Sampling policies ordered drainage-first; road/not_road kept as hard negatives so
  the net learns "this linear feature is a ROAD, not drainage" (in-model, not a filter).
- Checkpoint on val drainage IoU. 40 epochs, GTX 1070 Ti (~285 s/ep).

## Results (9t held-out test)
| metric | value |
|---|---|
| best val drainage IoU | **0.811** |
| pixel IoU drainage (test) | **0.532** |
| **AP drainage-vs-road** | **0.990** |
| mean P(drain) on drainage | **0.696** |
| mean P(drain) on road | **0.0016** |

The road/drainage discrimination is excellent: roads are essentially never lit up
as drainage (P=0.0016). 613590 predict: 154,998 px ≥0.5, mean P 0.65 where ≥0.3.

## Interpretation
Flipping the road model's focal weights yields a strong drainage detector for free —
same data, same pipeline. The 0.99 AP confirms the two linear classes are cleanly
separable with terrain channels alone. Drainage IoU (0.53) is lower than road IoU
because drainage lines are narrower/less buffered, not because of confusion.

## Reproduce
```bash
python notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py --epochs 40
# eval only (uses best.pt):
python notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py --eval-only
```

## Next
- Apply `_road_optimize.py` to `drainage_prob` for centerline vectors (drainage is
  linear → the road extractor applies directly; just swap the prob raster).
- Optionally fold drainage_prob into the pit/road masks as a negative gate.

See [[project_road_recall_alpha_fix]], `_road_unet_1m_recall.py`.
