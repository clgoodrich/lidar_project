# Iter 04 — Iter 01 + Iter 03 ensemble

**Branch:** `iter-04-ensemble-01-03`
**Date:** 2026-05-19
**Status:** Pushed, awaiting PR review
**Outputs:** `data/derivatives/9t/iterations/04_ensemble_01_03/`
**Code:** `notebooks/wellsight/pits/iter_04_ensemble_01_03/`

## Goal / Hypothesis

The leaderboard after iter 03 had a clear pattern: **iter 01** owns detection rate (20/20), **iter 03** owns boundary quality (median IoU 0.726). The two models have different architectures (custom 8M UNet vs SMP+ResNet34 24M), different feature stacks (7 vs 11 channels), and complementary failure modes (iter 03 misses 2 shallow pits iter 01 catches; iter 01 has fuzzier boundaries on the easy pits iter 03 nails).

**Hypothesis:** averaging their softmax outputs at inference should combine the strengths — get iter 01's 20/20 detection back, keep iter 03's sharp boundaries. No new training, no new labels, purely combining two already-saved checkpoints. The cheapest possible iteration.

## What changed

Pure inference-time ensemble. No training. Code at `iter_04_ensemble_01_03/infer.py`.

For each sliding window on the 9t tile:
1. Read the **7-channel features**, normalize with iter 01's stats, run **iter 01's custom UNet** with 8-fold TTA → softmax_A (3 × 256 × 256).
2. Read the **11-channel features**, normalize with iter 03's stats, run **iter 03's SMP+ResNet34** with 8-fold TTA → softmax_B (3 × 256 × 256).
3. Combine into **two** ensemble outputs:
    - **Mean ensemble:** `0.5 * (softmax_A + softmax_B)`. Standard, symmetric, smooth.
    - **Max-pit ensemble:** `bg = min(A_bg, B_bg)`, `floor = max(A_floor, B_floor)`, `wall = max(A_wall, B_wall)`, then re-normalize so each pixel's probabilities sum to 1. Aggressive on coverage: pixel is pit if *either* model is confident.

Both schemes evaluated separately against the 20 test pits.

## Parameters

| Setting | Value |
|---|---|
| Models | iter 01 best.pt (UNet, 7-ch) + iter 03 best.pt (SMP+ResNet34, 11-ch) |
| Patch size | 256 × 256 px @ 0.5 m |
| Overlap | 64 px |
| TTA | 8-fold per model (4 rotations × 2 flips) — so 16 forward passes per patch total |
| Ensemble schemes | mean / max-pit |
| Inference batch | 8 patches |
| New training | none |

## Inference cost

2209 patches × 16 forward passes ≈ 35,000 forward passes total. ~820 seconds (~14 minutes) on the 1070 Ti. ~2.6× iter 03's TTA cost because both models run per patch.

This is the ceiling of "free" gains — no new gradient steps, no new data.

## Results — 20 held-out test pits

| Metric | Iter 01 | Iter 03 | **Iter 04 mean** | Iter 04 maxpit |
|---|---:|---:|---:|---:|
| Floor pixel IoU (test region) | 0.385 | 0.456 | 0.439 | 0.422 |
| Wall pixel IoU (test region) | 0.446 | 0.505 | **0.513** | 0.458 |
| Mean per-pit IoU | 0.637 | 0.648 | 0.669 | **0.677** |
| Median per-pit IoU | 0.684 | 0.726 | **0.726** | 0.715 |
| Detected ≥10% recall | **20 / 20** | 18 / 20 | **20 / 20** | **20 / 20** |
| Local IoU > 0.3 | **18 / 20** | 17 / 20 | **18 / 20** | **18 / 20** |

Per-pit tables: `test_per_pit_mean.csv`, `test_per_pit_maxpit.csv`. Headline JSON: `test_metrics.json`.

## Honest read

**Hypothesis confirmed.** The mean ensemble holds iter 01's 20/20 detection rate **and** iter 03's 0.726 median per-pit IoU at the same time. Wall pixel IoU set a new project-best at 0.513. This is the strongest single eval in the leaderboard.

But not by a huge margin:

- Mean per-pit IoU climbed from 0.648 (iter 03) to 0.669 — a real but modest +0.021 lift. The ensemble doesn't generate new model knowledge; it just removes idiosyncratic errors that don't agree across the two models.
- Floor pixel IoU **dropped slightly** vs iter 03 alone (0.439 vs 0.456). The mean is pulled down by iter 01's fuzzier floor boundaries. Wall improved because the two models agree more on rim location than on floor extent — so averaging tightens rims and loosens floors.
- The maxpit scheme posts the highest mean per-pit IoU (0.677) but pays for it with lower pixel IoUs across the board. Max-of-confidences predicts more pit pixels everywhere — slight over-prediction. Worth keeping as a "detection-favored" output but not as the default.

The two pits that iter 03 missed but iter 01 caught: both now show up in the ensemble at >10% recall, exactly as the mechanism predicts.

## What's next

Iter 04 is approximately the **ceiling of what's reachable with the current labels**. To go further, three real options:

1. **More labels.** 110 → 300+ pits. Same architectures, same features, much more data. This is the only lever expected to give >5 IoU pts at this point. The user has indicated this is a real near-term effort.
2. **Replace ResNet34 stem** with something less aggressive (stride-1 first conv, or HRNet, or dilated ResNet). Targets the remaining 2 marginal pits iter 03 misses on its own — but the ensemble already papers over that, so the marginal gain is limited.
3. **Confidence calibration.** Iter 04 picks argmax for the headline numbers; the actual operational output is the probability raster. Calibrating those probabilities (Platt scaling or isotonic regression on val) would let downstream filtering at "≥0.7 confidence" mean something honest. Useful before deploying candidates for field review.

Going forward, **iter 04 mean is the canonical model output** for QGIS overlays and candidate generation. Iter 03 is still the single-model champion if a one-network deployment is needed.
