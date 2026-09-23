# Threshold-free precision/recall and score calibration, pit and pad CV5 on 9t

**Date:** 2026-09-23
**Status:** done. These are Phases 1 and 2 of `docs/iterations/operating_point_policy_plan.md`.
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
- **Proposal cutoff** is set per fold on inner val. It is the pixel cutoff with the highest inner-val recall, with ties going to the higher cutoff. Its only job is to decide which blobs reach the candidate list. It never looks at held-out data.
- **AP** is average precision. It is the area under the precision-recall curve. At each recall the best precision at that recall or higher is used (Everingham et al. 2010).
- **FROC** is recall plotted against false positives per km² of held-out ground (Chakraborty 1989).
- **ECE** is expected calibration error. It is the weighted gap between the mean score in a bin and the hit rate in that bin (Naeini et al. 2015).
- **Block bootstrap** resamples the 375 m blocks within each fold, 2,000 times. Blocks are the unit the folds were split on. The same resampled blocks are used for every model, so model comparisons are paired.

## Check that the recorder is faithful

The recorder re-polygonizes every fold on a finer grid, from 0.05 to 0.95 in steps of 0.025.
At cutoff 0.30 its held-out counts must equal the CV5 run's own.
**They match exactly on every fold, for all three models.**

## A design correction made during the run

The first design traced the curve by sweeping the pixel cutoff. That curve turned out to measure the wrong thing.

Raising the cutoff shrinks each blob to its core. A core stops overlapping the annotated floor enough to pass IoU 0.3.
So pit precision peaks at 0.71 near cutoff 0.58 and then **falls**. It is 0.45 by 0.875.
At cutoff 0.85 the unmatched pit blobs have a median area of 6.3 m². Matched blobs have 10.4 m².

The sweep curve therefore mixes two skills. One is outlining a feature. The other is ranking candidates.

**Consequence: raising the pixel cutoff is the wrong way to buy precision.**
The right way is to fix a proposal cutoff that keeps recall, then rank the blobs by score and cut the ranked list.
The headline therefore became the ranked list. The sweep is kept as a secondary result.

## Phase 1 results: ranked candidate list (headline)

Held-out, pooled over five folds. Brackets are the 95% block bootstrap. Pits: 503 annotated floors on 16.17 km². Pads: 650 pads on 18.14 km².

| Model | IoU | AP | 95% CI | per-fold mean (sd) | recall ceiling | candidates |
|---|---|---|---|---|---|---|
| pit, vendor ground | 0.3 | **0.823** | 0.787–0.857 | 0.830 (0.052) | 0.940 | 764 |
| pit, SMRF ground | 0.3 | **0.820** | 0.778–0.862 | 0.831 (0.036) | 0.930 | 752 |
| pad, vendor ground | 0.3 | **0.744** | 0.702–0.789 | 0.759 (0.042) | 0.906 | 1,006 |
| pit, vendor ground | 0.5 | 0.650 | 0.600–0.703 | 0.653 (0.078) | 0.789 | |
| pit, SMRF ground | 0.5 | 0.565 | 0.513–0.620 | 0.572 (0.060) | 0.734 | |
| pad, vendor ground | 0.5 | 0.592 | 0.542–0.646 | 0.607 (0.064) | 0.760 | |

The recall ceiling is the recall of the whole candidate list. No cut of the list can go higher.

### Recall at a fixed false-alarm density (IoU 0.3, pits, vendor ground)

Phase 3's review-budget policy reads its cutoff directly from this table.

| False positives per km² | Recall | 95% CI |
|---|---|---|
| 1 | 0.272 | 0.199–0.413 |
| 2 | 0.453 | 0.376–0.576 |
| 5 | 0.734 | 0.662–0.808 |
| 10 | 0.893 | 0.848–0.934 |
| 20 | 0.940 | 0.921–0.959 |

The same table for SMRF and pads is in the summary JSON under `recall_at_fp_per_km2`.

### Vendor against SMRF ground, paired

| IoU | ΔAP (SMRF − vendor) | per-fold Δ | paired t (df 4) | paired bootstrap 95% CI |
|---|---|---|---|---|
| 0.3 | −0.003 | +0.054, −0.022, +0.022, −0.018, −0.033 | 0.05 | −0.031 to +0.026 |
| 0.5 | **−0.085** | +0.090, −0.131, −0.130, −0.066, −0.169 | −1.77 | **−0.135 to −0.028** |

At IoU 0.3 there is no difference. This agrees with `docs/iterations/smrf_ground_retrain_pit_cv5.md`.

At IoU 0.5 SMRF is worse in four of five folds. The bootstrap interval excludes zero. The paired t does not reach 2.
The two tests disagree because the bootstrap resamples blocks only. It does not capture training variation between fold models.
The paired t does capture it. So this is **suggestive, not established**.
The earlier F2 result pointed the same way (−0.082, t −1.91). That doc read the SMRF difference as noise. With two independent views now leaning the same way, "SMRF outlines pits slightly worse" is the better working hypothesis.

## Phase 1 results: pixel-cutoff sweep (secondary)

| Model | AP IoU 0.3 | AP IoU 0.5 |
|---|---|---|
| pit, vendor | 0.667 (0.621–0.714) | 0.502 |
| pit, SMRF | 0.679 (0.634–0.724) | 0.506 |
| pad, vendor | 0.558 (0.519–0.602) | 0.401 |

All are lower than the ranked-list AP because of the core-shrinking effect above.
**Do not compare these numbers with the ranked-list numbers.** They measure different things.

## Phase 2 results: does a score mean a probability?

### Candidate blobs

The label is "matched an annotated feature at IoU 0.3". The calibrators are fit on inner-val blobs and scored on held-out blobs.

| Model | held-out blobs | hit rate | ECE raw | ECE Platt | ECE isotonic | Brier raw → Platt |
|---|---|---|---|---|---|---|
| pit, vendor | 764 | 0.619 | 0.183 | **0.051** | 0.072 | 0.198 → 0.157 |
| pit, SMRF | 752 | 0.622 | 0.202 | **0.039** | 0.050 | 0.204 → 0.157 |
| pad, vendor | 1,006 | 0.586 | 0.157 | 0.052 | **0.035** | 0.223 → 0.178 |

- **Raw blob scores are not probabilities.** A blob with mean score 0.40 is a match about 10% of the time. A blob with 0.70 is a match about 95% of the time. The raw scores sit in a narrow band.
- **Platt is the calibrator to use.** It cuts ECE by a factor of three to five on every model. Isotonic is close on ECE, but it has worse log loss on pits: 0.683 against 0.485. That is the overfitting Niculescu-Mizil & Caruana (2005) warn about for small calibration sets.
- The Platt slope on logit(score) is 3.3 to 7.2 across folds and models. A slope far above 1 means the raw score badly understates how sure the model is.
- Per-fold ECE after Platt is 0.04–0.13. That is noisier than the pooled value, because each fold has only about 150 blobs in 10 bins.

### Pixels

A Platt fit on logit(p) is temperature scaling plus a bias term (Guo et al. 2017). The full softmax temperature cannot be fitted, because only the floor or pad probability was saved.

| Model | Platt slope (T = 1/slope) | intercept | ECE raw | ECE Platt | ECE raw, p ≥ 0.05 | ECE Platt, p ≥ 0.05 |
|---|---|---|---|---|---|---|
| pit | 2.42–2.54 (T 0.39–0.41) | −0.71 to −1.19 | 0.028 | 0.0002 | 0.087 | 0.068 |
| pad | 2.14–2.62 (T 0.38–0.47) | −1.50 to −1.94 | 0.121 | 0.003 | 0.164 | 0.017 |

- **The network is under-confident.** A temperature near 0.4 means the logits should be stretched by about 2.5. This is the documented behaviour of focal loss (Mukhoti et al. 2020).
- **Focal α inflates the positive class.** The negative intercept pulls every probability down after stretching.
- Together they mean that **a raw pixel score of 0.5 is not 50%.** In held-out pixels a raw 0.5 is a floor pixel about 36% of the time for pits, and a pad pixel about 17% of the time for pads.
- Platt fixes pads almost completely. It fixes pits less well above p 0.05, because a single logistic cannot follow the pit curve's S-shape.
- **An observation, not a justification.** The raw pixel score where calibrated probability reaches 50% is 0.57–0.62 for pits and 0.66–0.70 for pads. Those bands contain the hand-set deployed cutoffs of 0.60 and 0.70. Whoever set them may have tuned by eye toward even odds per pixel. Even odds per pixel is still not an operating-point policy.

## Interpretation

1. **Pits rank better than pads.** Ranked AP is 0.823 against 0.744, and the intervals barely touch. The pad model's weakness is precision at every depth of the list, not recall.
2. **The operating point should be a cut of the ranked list, not a pixel cutoff.** The proposal cutoff keeps recall near its ceiling. Phase 3 then decides how far down the list to go.
3. **Calibrate with Platt before any cost-based cut.** Raw scores would put a cost-ratio cutoff in the wrong place.
4. **Every precision here is a lower bound.** Unannotated real features count as false. The pad review moved pad precision from 0.623 to 0.898. Phase 5 addresses this.

## Outputs

All under `data/9t/results/operating_point/`:

- `cv5_sweep_counts_per_block_{pit,pit_smrf,pad}_thr0p05to0p95_9t.csv` holds held-out counts per block, per cutoff, per IoU, plus inner-val totals.
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

The bootstrap seed is 20260923 with B = 2000. Proposal cutoffs and the calibrator fits are deterministic.
