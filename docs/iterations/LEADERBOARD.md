# Pit Detection Iteration Leaderboard

Live comparison of all pit-detection iterations on the **same** held-out test set: 20 pits in 3 spatial blocks, none seen during training or used for checkpoint selection.

All numbers are on the 9t tile at 0.5 m/px, evaluated with 8-fold TTA when noted. Training set: 74 pits in 17 blocks. Validation set (used for checkpoint selection): 16 pits in 4 blocks.

**Last updated:** 2026-05-19, after iter 03.

## Headline table

| Iteration | Branch | Val miou(pit) | Floor pixel IoU | Wall pixel IoU | Mean per-pit IoU | Median per-pit IoU | Detected ≥10% | IoU > 0.3 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| baseline (`pit_unet_v2`) | `main` | 0.541 | 0.364 | 0.402 | 0.566 | 0.668 | 16/20 | 16/20 |
| [iter 01](iter_01_tta_miou.md) — TTA + miou checkpoint | `iter-01-tta-miou` | 0.594 | 0.385 | 0.446 | **0.637** | 0.684 | **20/20** | **18/20** |
| [iter 02](iter_02_smp_pretrained.md) — SMP U-Net + ImageNet ResNet34 | `iter-02-smp-pretrained` | 0.617 | 0.440 | 0.465 | 0.564 | 0.696 | 16/20 | 16/20 |
| [iter 03](iter_03_multiscale_feats.md) — SMP + 11-ch (multi-scale + curvature + geomorphons) | `iter-03-multiscale-features` | **0.639** | **0.456** | **0.505** | **0.648** | **0.726** | 18/20 | 17/20 |

Bold = column leader. Bolds split across rows are deliberate — no single iteration dominates every column.

## Honest reads

**Iter 01 — detection-rate champion.**
Two trivial changes (save by `miou(pit)`, not `val_loss`; 8-fold TTA at inference) turned 16/20 detection into 20/20. Highest cheap win in the project. Mean per-pit IoU jumped to 0.637 — still the highest mean in the leaderboard except for iter 03, because iter 02's misses pull its mean down hard.

**Iter 02 — boundary-quality champion among easy pits, but loses coverage.**
ResNet34's ImageNet-pretrained encoder gives sharper boundaries on the pits it does see, but the encoder's 32× spatial downsampling + texture bias miss four shallow / asymmetric pits that iter 01's custom UNet catches. Median per-pit IoU edges up; mean drops because of the misses.

**Iter 03 — best overall on every boundary-quality metric.**
Adding multi-scale LRM (5 + 11 + 25 + 51), DTM Laplacian curvature, and WhiteboxTools geomorphons gives the pretrained SMP encoder the explicit geomorphological semantics it was missing. Recovered 2 of the 4 pits iter 02 missed (16 → 18 detected); val miou hit 0.639, median per-pit IoU 0.726. Still loses to iter 01 on raw detection rate.

## What this implies

- The two unconquered pits at iter 03 are the same failure mode as iter 02: very shallow / subtle features that the ResNet34 stem (`/2` then `/2` immediately) loses spatial detail on.
- An **iter 01 + iter 03 ensemble** (max or average of softmax over the two models) is the obvious next move: iter 01 contributes detection, iter 03 contributes boundary quality. Likely the strongest single eval without acquiring new labels.
- Beyond ensembling: more labels is the real lever (110 → 300+ pits). Architectural improvements past iter 03 (HRNet, dilated-stem ResNet, full-resolution encoders) only justify themselves if labels stop being the bottleneck.

## Metric definitions

| Term | Definition |
|---|---|
| **Val miou(pit)** | Mean of (floor IoU, wall IoU) on the 16-pit validation set during training; **excludes background**. The checkpoint criterion as of iter 01. |
| **Floor / Wall pixel IoU** | Class IoU computed over only test-block pixels on the full 9t tile inference (8-fold TTA where applicable). |
| **Mean / Median per-pit IoU** | Per test pit, IoU of (predicted pit pixels) vs (ground-truth pit floor + wall) within a ±6 m window around the pit's labeled inner geometry. Then aggregated across the 20 test pits. |
| **Detected ≥10%** | Number of test pits for which at least 10% of the labeled pit pixels were predicted as pit. Detection-rate proxy. |
| **IoU > 0.3** | Number of test pits whose local-window pit-vs-bg IoU exceeded 0.3. A "solid hit" threshold. |
