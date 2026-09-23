# Threshold-free precision/recall and score calibration, pit and pad CV5 on 9t

**Date:** 2026-09-23 (first run the same day, superseded by the leave-one-fold-out rerun described below)
**Status:** done. These are Phases 1 and 2 of `docs/iterations/operating_point_policy_plan.md`. Phase 3 is `docs/iterations/operating_point_policy_sweep_pit_pad_9t.md`.
**Scripts:**
- recorder `notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py`
- analysis `notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py`

**Models, all ann712, same five folds:**
- `data/9t/models/pit/unet_cv5/` is pits on vendor ground.
- `data/9t/models/pit/unet_cv5_smrf/` is pits on SMRF ground.
- `data/9t/models/pad/unet_cv5/` is pads on vendor ground.

No training and no GPU. Everything reads the fold probability rasters that the CV5 runs already wrote.

## Goal

Until now every pit and pad number was read at one cutoff. That cutoff was picked on inner val by F1 or F2.
F2 assumes a miss costs four false alarms. We chose that ratio. The data did not.

This pass answers two questions without choosing any cutoff:

1. **Which model ranks candidates better?** This is Phase 1.
2. **Does a score mean a probability?** This is Phase 2.

## Terms

- **Recall** is the share of annotated features that a candidate matches.
- **Precision** is the share of candidates that match an annotated feature.
- **Match** means greedy 1:1 IoU matching by score, the same as the CV5 scripts. IoU is intersection over union. The rule is IoU ≥ 0.3, and IoU ≥ 0.5 as a stricter check.
- **Leave-one-fold-out (LOFO).** Anything fitted for fold k is fitted on the held-out blocks of the other four folds. Each of those blocks was scored by a model that never saw it. Fold k's own labels are read only to score.
- **Proposal cutoff** is the pixel cutoff with the highest LOFO recall, with ties going to the higher cutoff. Its only job is to decide which blobs reach the candidate list. It came out at 0.35 for every pit fold, 0.30–0.325 for SMRF pits, and 0.50–0.55 for pads.
- **AP** is average precision. It is the area under the precision-recall curve. At each recall the best precision at that recall or higher is used (Everingham et al. 2010).
- **FROC** is recall plotted against false positives per km² of held-out ground (Chakraborty 1989).
- **ECE** is expected calibration error. It is the weighted gap between the mean score in a bin and the hit rate in that bin (Naeini et al. 2015).
- **Block bootstrap** resamples the 375 m blocks within each fold, 2,000 times. Blocks are the unit the folds were split on. The same resampled blocks are used for every model, so model comparisons are paired.

## Check that the recorder is faithful

The recorder re-polygonizes every fold on a finer grid, from 0.05 to 0.95 in steps of 0.025.
At cutoff 0.30 its held-out counts must equal the CV5 run's own.
**They match exactly on every fold, for all three models.**

## Two design corrections made during the work

### 1. The pixel-cutoff sweep measures the wrong thing

The first design traced the curve by sweeping the pixel cutoff.

Raising the cutoff shrinks each blob to its core. A core stops overlapping the annotated floor enough to pass IoU 0.3.
So pit precision peaks at 0.71 near cutoff 0.58 and then **falls**. It is 0.45 by 0.875.
At cutoff 0.85 the unmatched pit blobs have a median area of 6.3 m². Matched blobs have 10.4 m².

The sweep curve therefore mixes two skills. One is outlining a feature. The other is ranking candidates.

**Consequence: raising the pixel cutoff is the wrong way to buy precision.**
The right way is to fix a proposal cutoff that keeps recall, then rank the blobs by score and cut the ranked list.
The headline therefore became the ranked list. The sweep is kept as a secondary result.

### 2. Inner val cannot be reproduced, so fitting is leave-one-fold-out

The first run fitted the proposal cutoff and the calibrators on each fold's inner-val blocks. Phase 3 then found that the inner-val split is not reproducible.

- The manifests hold features with no block: 209 of 712 pits and 345 of 995 pads.
- The CV scripts build the split from `sorted(set(block_id))`, and that set contains NaN.
- NaN's hash depends on the object's identity. Sorting around NaN depends on input order. So the inner-val draw changes between processes.
- Evidence: the pit training log shows 64 inner-val pits in fold 2. Re-drawing gave 63, and then 61.
- Matching every fold's logged train and val counts leaves 2–6 candidate sets in 8 of the 10 pit and pad folds. The true sets cannot be recovered.

A re-drawn "inner val" can therefore include blocks the fold's model trained on.
Held-out folds are not affected. They come from the saved fold-assignment CSV.
Every fit now uses LOFO. The first run's numbers are superseded. Most moved by less than 0.01. The exception is the SMRF comparison at IoU 0.5, below.

The training-script bug is logged in `docs/iterations/BACKLOG.md`. The training scripts are not changed here.

## Phase 1 results: ranked candidate list (headline)

Held-out, pooled over five folds. Brackets are the 95% block bootstrap.
Pits: 503 annotated floors on 16.17 km². Pads: 650 pads on 18.14 km².
These are the features inside the block grid. The features with no block are never scored by any CV run.

| Model | IoU | AP | 95% CI | per-fold mean (sd) | recall ceiling | candidates |
|---|---|---|---|---|---|---|
| pit, vendor ground | 0.3 | **0.818** | 0.778–0.857 | 0.833 (0.051) | 0.946 | 779 |
| pit, SMRF ground | 0.3 | **0.818** | 0.780–0.856 | 0.829 (0.038) | 0.934 | 775 |
| pad, vendor ground | 0.3 | **0.745** | 0.703–0.789 | 0.757 (0.035) | 0.900 | 1,018 |
| pit, vendor ground | 0.5 | 0.637 | 0.580–0.697 | 0.652 (0.090) | 0.795 | |
| pit, SMRF ground | 0.5 | 0.495 | 0.430–0.564 | 0.501 (0.131) | 0.686 | |
| pad, vendor ground | 0.5 | 0.582 | 0.532–0.634 | 0.593 (0.060) | 0.748 | |

The recall ceiling is the recall of the whole candidate list. No cut of the list can go higher.

### Recall at a fixed false-alarm density (IoU 0.3, pits, vendor ground)

| False positives per km² | Recall | 95% CI |
|---|---|---|
| 1 | 0.294 | 0.223–0.367 |
| 2 | 0.404 | 0.319–0.506 |
| 5 | 0.748 | 0.618–0.831 |
| 10 | 0.903 | 0.855–0.937 |
| 20 | 0.946 | 0.927–0.964 |

The same table for SMRF and pads is in the summary JSON under `recall_at_fp_per_km2`.

### Vendor against SMRF ground, paired

| IoU | ΔAP (SMRF − vendor) | per-fold Δ | paired t (df 4) | paired bootstrap 95% CI |
|---|---|---|---|---|
| 0.3 | +0.000 | +0.043, −0.062, +0.013, −0.028, +0.014 | −0.22 | −0.028 to +0.029 |
| 0.5 | **−0.143** | −0.076, −0.164, −0.062, −0.138, −0.317 | **−3.33** | **−0.200 to −0.085** |

At IoU 0.3 there is no difference. This agrees with `docs/iterations/smrf_ground_retrain_pit_cv5.md`.

**At IoU 0.5 SMRF is worse in all five folds.** Both tests agree.
The size of the gap depends on the proposal cutoff. The first, inner-val run gave −0.085 (t −1.77) with four of five folds negative. The LOFO cutoffs for SMRF are lower (0.30–0.325 against 0.35). Lower cutoffs make larger blobs, which fail IoU 0.5 more often.
So the direction is stable across two fitting schemes and the earlier F2 result (−0.082, t −1.91). The size is not.
The reading: SMRF pits are found as often but outlined less tightly. It is still one seed per arm on one tile.

## Phase 1 results: pixel-cutoff sweep (secondary)

| Model | AP IoU 0.3 | AP IoU 0.5 |
|---|---|---|
| pit, vendor | 0.667 (0.621–0.714) | 0.502 |
| pit, SMRF | 0.679 (0.634–0.724) | 0.506 |
| pad, vendor | 0.558 (0.519–0.602) | 0.401 |

All are lower than the ranked-list AP because of the core-shrinking effect above. The sweep fits nothing, so the LOFO change did not touch it.
**Do not compare these numbers with the ranked-list numbers.** They measure different things.

## Phase 2 results: does a score mean a probability?

### Candidate blobs

The label is "matched an annotated feature at IoU 0.3". The calibrators are fitted LOFO (roughly 600–850 calibration blobs per fold) and scored on the held-out fold.

| Model | held-out blobs | hit rate | ECE raw | ECE Platt | ECE isotonic | Brier raw → Platt |
|---|---|---|---|---|---|---|
| pit, vendor | 779 | 0.611 | 0.199 | **0.043** | 0.045 | 0.202 → 0.160 |
| pit, SMRF | 775 | 0.607 | 0.199 | **0.029** | 0.048 | 0.209 → 0.164 |
| pad, vendor | 1,018 | 0.575 | 0.173 | 0.031 | **0.024** | 0.224 → 0.174 |

- **Raw blob scores are not probabilities.** A pit blob scoring 0.45 or less is a match 10% of the time. One scoring 0.65–0.70 is a match 92% of the time. For pads, 0.55–0.60 gives 17% and 0.70–0.75 gives 87%. The raw scores sit in a narrow band.
- **Platt is the calibrator to use.** It cuts ECE four- to sevenfold. Isotonic is close on ECE, but its log loss is worse on all three models (pit 0.544 against 0.492). That is the overfitting Niculescu-Mizil & Caruana (2005) warn about. Platt is also two numbers, which makes it easy to carry to a new tile.
- The Platt slope on logit(score) is 4.2–5.7 across folds and models. A slope far above 1 means the raw score badly understates how sure the model is.
- Per-fold ECE after Platt is 0.06–0.15. That is noisier than the pooled value, because each fold has only about 150–200 blobs in 10 bins.

### Pixels

A Platt fit on logit(p) is temperature scaling plus a bias term (Guo et al. 2017). The full softmax temperature cannot be fitted, because only the floor or pad probability was saved.

| Model | Platt slope (T = 1/slope) | intercept | ECE raw | ECE Platt | ECE raw, p ≥ 0.05 | ECE Platt, p ≥ 0.05 |
|---|---|---|---|---|---|---|
| pit | 2.42–2.49 (T 0.40–0.41) | −0.69 to −0.85 | 0.028 | 0.0001 | 0.088 | 0.045 |
| pad | 2.27–2.41 (T 0.42–0.44) | −1.65 to −1.67 | 0.121 | 0.002 | 0.164 | 0.007 |

- **The network is under-confident.** A temperature near 0.4 means the logits should be stretched by about 2.5. This is the documented behaviour of focal loss (Mukhoti et al. 2020).
- **Focal α inflates the positive class.** The negative intercept pulls every probability down after stretching.
- Together they mean that **a raw pixel score of 0.5 is not 50%.** In held-out pixels a raw 0.5 is a floor pixel about 36% of the time for pits, and a pad pixel about 17% of the time for pads.
- LOFO fits vary much less across folds than the first run's inner-val fits did. That is expected, since each fit now uses about four times as many blocks.
- **An observation, not a justification.** The raw pixel score where the calibrated probability reaches 50% is 0.57–0.59 for pits and 0.67 for pads. The hand-set deployed cutoffs are 0.60 and 0.70, just above. Whoever set them may have tuned by eye toward even odds per pixel. Even odds per pixel is still not an operating-point policy.

## Interpretation

1. **Pits rank better than pads.** Ranked AP is 0.818 against 0.745, and the intervals barely touch. The pad model's weakness is precision at every depth of the list, not recall.
2. **The operating point should be a cut of the ranked list, not a pixel cutoff.** The proposal cutoff keeps recall near its ceiling. Phase 3 then decides how far down the list to go.
3. **Calibrate with Platt before any cost-based cut.** Raw scores would put a cost-ratio cutoff in the wrong place.
4. **Every precision here is a lower bound.** Unannotated real features count as false. The pad review moved pad precision from 0.623 to 0.898. Phase 5 addresses this.

## Outputs

All under `data/9t/results/operating_point/`:

- `cv5_sweep_counts_per_block_{pit,pit_smrf,pad}_thr0p05to0p95_9t.csv` holds held-out counts per block, per cutoff, per IoU. Its inner-val rows are no longer used.
- `cv5_sweep_objects_{pit,pit_smrf,pad}_thr0p05to0p95_9t.csv.gz` holds one row per candidate blob, with score, area, block and match flag.
- `cv5_sweep_records_run_pit_pitsmrf_pad_9t.log` is the recorder's run log.
- `pr_ap_froc_calibration_summary_cv5_pit_pitsmrf_pad_9t.json` holds every number in this doc.
- `pr_froc_curve_points_ranked_candidates_heldout_cv5_pit_pitsmrf_pad_9t.csv` holds the ranked-list curves.
- `pr_froc_curve_points_pixel_cutoff_sweep_heldout_cv5_pit_pitsmrf_pad_9t.csv` holds the sweep curves.
- `pr_ap_froc_calibration_run_cv5_pit_pitsmrf_pad_9t.log` is the analysis run log.

Figures are under `data/9t/results/operating_point/figures/`:

- `pr_curve_ranked_candidates_at_proposal_cutoff_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png`
- `froc_recall_vs_fp_per_km2_ranked_candidates_at_proposal_cutoff_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png`
- `pr_curve_pixel_cutoff_sweep_0p05to0p95_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png`
- `froc_recall_vs_fp_per_km2_pixel_cutoff_sweep_0p05to0p95_heldout_cv5_iou0p30_iou0p50_pit_pitsmrf_pad_9t.png`
- `reliability_object_level_heldout_cv5_raw_platt_isotonic_pit_pit_smrf_pad_9t.png`
- `reliability_pixel_level_heldout_cv5_raw_platt_pit_pad_9t.png`

The figure palette is the lost/found set: `#1F5FA8`, `#D97706` and `#A31515`. It was re-validated on 2026-09-23 with the dataviz validator using `--pairs all`. The worst pair is ΔE 21.1 for deuteranopia and 22.6 for normal vision. There is no green. Every series also has its own marker.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py      # ~35 min, CPU
python notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py        # ~5 min, CPU
```

The bootstrap seed is 20260923 with B = 2000. LOFO fits are deterministic.
