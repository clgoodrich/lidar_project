# Iter 03 — SMP U-Net on 11-channel multi-scale + curvature + geomorphons

**Branch:** `iter-03-multiscale-features`
**Date:** 2026-05-19
**Status:** Pushed, awaiting PR review
**Outputs:** `data/derivatives/9t/iterations/03_multiscale_feats/`
**Code:** `notebooks/wellsight/pits/iter_03_multiscale_feats/`

## Goal / Hypothesis

Iter 02 lost 4 test pits relative to iter 01 — all shallow / asymmetric ones the pretrained ResNet34 couldn't distinguish from the surrounding terrain. The problem isn't capacity (24 M params is plenty); it's that ImageNet features don't encode *geomorphological semantics*. The encoder sees gradients and textures, not "concave depression in a hillside."

**Hypothesis:** if we give the model input channels that *already encode* terrain shape — multi-scale residuals, signed curvature, and a categorical landform classifier — then the ImageNet encoder doesn't have to invent those concepts from scratch. It just learns the mapping from "geomorphons-class-9 plus negative curvature plus negative LRM at 5m and 25m" to "this is a pit floor."

If the hypothesis holds, iter 03 recovers the lost detection rate without giving up iter 02's sharper boundaries.

## What changed

Two pieces of work this iteration:

### Piece 1 — Build an 11-channel feature stack

Code: `build_features.py`. Output: `data/derivatives/9t/iterations/03_multiscale_feats/features_pit_v2_9t_05.tif` (float32, 11 bands, BIGTIFF, deflate-compressed).

| Band | Name | Source | New? |
|---|---|---|---|
| 1 | lrm_25 | existing | — |
| 2 | lrm_5 | existing | — |
| 3 | slope | existing | — |
| 4 | tpi_05 | existing | — |
| 5 | openness_pos | existing | — |
| 6 | openness_neg | existing | — |
| 7 | roughness_11 | existing | — |
| 8 | lrm_11 | already on disk; not used previously | **new in stack** |
| 9 | lrm_51 | already on disk; not used previously | **new in stack** |
| 10 | curvature | Laplacian of (Gaussian-smoothed σ=1.0) DTM, computed in `build_features.compute_curvature()` | **NEW** |
| 11 | geomorphons | WhiteboxTools `geomorphons(dem, search=50, fdist=0, forms=True)` — uint8 classes 1..10 | **NEW** |

Per-channel mean/std computed over **TRAIN-block pixels only** (no test leakage). Stored at `feature_stats_v2.json` and used for z-score normalization at train + inference time.

The multi-scale LRMs already existed on disk but weren't fed to the model. The new channels are:

- **Curvature** — second derivative of the elevation surface, lightly pre-smoothed to suppress LiDAR noise. Negative = concave (pit-like), positive = convex (rim/ridge). One-channel scalar.
- **Geomorphons** — Jasiewicz & Stepinski's landform classifier. Each pixel gets a categorical label 1..10 (flat, peak, ridge, shoulder, spur, slope, hollow, footslope, valley, pit). Class 10 ("pit") is exactly what we're trying to detect; class 9 ("valley") catches connected depressions. Treated as an integer raster (not one-hot) — the model learns the embedding implicitly through the first conv.

### Piece 2 — Train iter 02 architecture on the 11-channel stack

Code: `train.py`. Architecture is identical to iter 02 (SMP U-Net + ImageNet ResNet34), with `in_channels=11`. SMP's first conv expands to accept 11 input channels by replicating averaged pretrained weights.

Loss, optimizer, schedule, augmentation, TTA, checkpoint criterion — all unchanged from iter 02.

## Parameters

| Setting | Iter 02 | **Iter 03** |
|---|---|---|
| Architecture | SMP U-Net + ResNet34 + ImageNet | same |
| In-channels | 7 | **11** |
| Params | 24.45 M | **24.46 M** (one extra conv on stem) |
| Patch size | 256 × 256 px @ 0.5 m | same |
| Loss / opt / schedule | FocalCE / AdamW 1e-3 / cosine 40ep | same |
| Augmentation | rot + flip | same |
| Checkpoint criterion | miou(pit) | same |
| Inference | 8-fold TTA | same |

## Training

40 epochs in ~3 minutes (faster than iter 02 even with more channels — likely cache effects on the per-tile reads). Same lift-off pattern as iter 02:

- ep 4: miou(pit) = 0.400 (iter 02: 0.331)
- ep 10: miou(pit) = 0.566
- ep 22: miou(pit) = 0.629
- ep 26: best @ miou(pit) = **0.639**

The 11-channel stack converged a bit faster and to a higher plateau than the 7-channel stack at the same architecture — exactly the prediction.

## Results — 20 held-out test pits

| Metric | Iter 01 | Iter 02 | **Iter 03** | Δ vs Iter 02 |
|---|---:|---:|---:|---:|
| Val miou(pit) — best ckpt | 0.594 | 0.617 | **0.639** | +0.022 |
| Floor pixel IoU (test region) | 0.385 | 0.440 | **0.456** | +0.016 |
| Wall pixel IoU (test region) | 0.446 | 0.465 | **0.505** | +0.040 |
| Mean per-pit IoU | 0.637 | 0.564 | **0.648** | **+0.084** |
| Median per-pit IoU | 0.684 | 0.696 | **0.726** | +0.030 |
| Detected ≥10% recall | **20 / 20** | 16 / 20 | 18 / 20 | **+2 pits** |
| Local IoU > 0.3 | **18 / 20** | 16 / 20 | 17 / 20 | +1 |

Iter 03 is the **best single model on every boundary-quality metric** in the leaderboard. Per-pit table: `data/derivatives/9t/iterations/03_multiscale_feats/test_per_pit.csv`.

## Honest read

Hypothesis was **mostly confirmed**.

- The richer feature stack let SMP recover 2 of the 4 pits iter 02 missed (16 → 18 detected). Adding geomorphological semantics as input channels closed about half of iter 02's coverage gap.
- Boundary quality improved further on top of iter 02's gains. Median per-pit IoU jumped from 0.696 to **0.726**, a real and visible improvement.
- Mean per-pit IoU climbed +8.4 pts vs iter 02 (because two more pits are no longer zeros).

But:

- Iter 01 still wins detection rate (20/20 vs 18/20). Two pits remain unconquered. They're the same kind of failure mode iter 02 had — very shallow, low-contrast features the ResNet34 stem still loses spatial detail on. Adding more derivative-style features didn't fully fix that; the architectural choice does.
- Curvature alone might have contributed less than geomorphons did. We didn't run an ablation. If the next experiment cares about feature attribution, that's worth doing.

The geomorphons output is uint8 categorical, fed as a single integer channel. A one-hot encoding would let each class get its own learnable embedding without sharing scales with continuous features. Tried-and-true; worth trying in a follow-up.

## What's next

Iter 03 is now the **single-model leader** on most metrics, but the leaderboard hasn't collapsed to one winner. Three obvious next moves:

1. **Iter 04 candidate — iter 01 + iter 03 ensemble.** Average or max the two models' softmax outputs at inference. Iter 01 contributes the 20/20 detection rate; iter 03 contributes the sharper boundaries. Cheap to implement (no new training), should produce the strongest single number we can post without new labels.
2. **Replace the ResNet34 stem with something less aggressive** — dilated stem, or HRNet, or ResNet34 with stride-1 first conv. Targets the remaining 2 lost pits directly by preserving more spatial detail at the bottleneck.
3. **More labels.** 110 pits is small. Pushing to 300+ would help every iteration uniformly. The user has indicated this is the next major effort outside the modeling loop.

If only one: (1) — biggest reward for least new work.
