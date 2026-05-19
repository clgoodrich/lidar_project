# Pit Detection Iteration Leaderboard

Live comparison of all pit-detection iterations on the **same** held-out test set: 20 pits in 3 spatial blocks, none seen during training or used for checkpoint selection.

All numbers are on the 9t tile at 0.5 m/px, evaluated with 8-fold TTA. Training set: 74 pits in 17 blocks. Validation set (used for checkpoint selection): 16 pits in 4 blocks.

**Last updated:** 2026-05-19, after iter 04.

## Headline table

| Iteration | Branch | Val miou(pit) | Floor pixel IoU | Wall pixel IoU | Mean per-pit IoU | Median per-pit IoU | Detected ≥10% | IoU > 0.3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline (`pit_unet_v2`) | `main` | 0.541 | 0.364 | 0.402 | 0.566 | 0.668 | 16/20 | 16/20 |
| [iter 01](iter_01_tta_miou.md) — TTA + miou checkpoint | `iter-01-tta-miou` | 0.594 | 0.385 | 0.446 | 0.637 | 0.684 | **20/20** | **18/20** |
| [iter 02](iter_02_smp_pretrained.md) — SMP U-Net + ImageNet ResNet34 | `iter-02-smp-pretrained` | 0.617 | 0.440 | 0.465 | 0.564 | 0.696 | 16/20 | 16/20 |
| [iter 03](iter_03_multiscale_feats.md) — SMP + 11-ch (multi-scale + curvature + geomorphons) | `iter-03-multiscale-features` | **0.639** | 0.456 | 0.505 | 0.648 | 0.726 | 18/20 | 17/20 |
| [iter 04](iter_04_ensemble_01_03.md) **mean** — iter 01 + iter 03 ensemble | `iter-04-ensemble-01-03` | n/a | 0.439 | **0.513** | 0.669 | **0.726** | **20/20** | **18/20** |
| [iter 04](iter_04_ensemble_01_03.md) **maxpit** — iter 01 + iter 03, pit-favored | `iter-04-ensemble-01-03` | n/a | 0.422 | 0.458 | **0.677** | 0.715 | **20/20** | **18/20** |

Bold = column leader. Bolds split across rows are deliberate — multiple iterations now share the top of the detection-rate / solid-hit columns.

## Honest reads

**Iter 01 — detection-rate champion.**
Two trivial changes (save by `miou(pit)`, not `val_loss`; 8-fold TTA at inference) turned 16/20 detection into 20/20. Highest cheap win in the project. Mean per-pit IoU jumped to 0.637.

**Iter 02 — boundary-quality on the easy pits, but loses coverage.**
ResNet34's ImageNet-pretrained encoder gives sharper boundaries on the pits it sees, but the encoder's 32× spatial downsampling + texture bias miss four shallow / asymmetric pits that iter 01's custom UNet catches.

**Iter 03 — best single model on every boundary-quality metric.**
Adding multi-scale LRM (5 + 11 + 25 + 51), DTM Laplacian curvature, and WhiteboxTools geomorphons gives the pretrained SMP encoder explicit geomorphological semantics. Recovered 2 of the 4 pits iter 02 missed (16 → 18 detected); median per-pit IoU 0.726.

**Iter 04 mean ensemble — best overall single eval.**
Mean of (iter 01 softmax, iter 03 softmax) at inference. Combines iter 01's 20/20 detection with iter 03's 0.726 median IoU; sets new project-best wall pixel IoU at 0.513. No new training, no new labels — just two existing checkpoints averaged.

**Iter 04 maxpit ensemble — most aggressive detection.**
Per-pixel max of pit-class probs from both models, then re-normalized. Highest mean per-pit IoU yet (0.677) but pixel IoUs drop slightly because it over-predicts where either model is confident.

## What this implies

- The ensemble is approximately the **ceiling of what's reachable with current labels**. Two complementary models can be averaged; that's the end of the "free gains" road.
- To meaningfully beat iter 04, we need more labels (110 → 300+) or an architectural change targeted at preserving spatial detail (HRNet, dilated-stem ResNet, no-downsample input branch). Both are real next moves; more labels has higher expected leverage.
- For operational deployment (candidate generation in QGIS, field review): **use iter 04 mean** as the canonical probability raster. Iter 03 remains the single-model champion when a one-network deployment is needed.

## Metric definitions

| Term | Definition |
|---|---|
| **Val miou(pit)** | Mean of (floor IoU, wall IoU) on the 16-pit validation set during training; **excludes background**. The checkpoint criterion as of iter 01. Not applicable to inference-only ensembles. |
| **Floor / Wall pixel IoU** | Class IoU computed over only test-block pixels on the full 9t tile inference (8-fold TTA where applicable). |
| **Mean / Median per-pit IoU** | Per test pit, IoU of (predicted pit pixels) vs (ground-truth pit floor + wall) within a ±6 m window around the pit's labeled inner geometry. Then aggregated across the 20 test pits. |
| **Detected ≥10%** | Number of test pits for which at least 10% of the labeled pit pixels were predicted as pit. Detection-rate proxy. |
| **IoU > 0.3** | Number of test pits whose local-window pit-vs-bg IoU exceeded 0.3. A "solid hit" threshold. |
