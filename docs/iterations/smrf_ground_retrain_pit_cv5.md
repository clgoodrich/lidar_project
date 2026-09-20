# Does recovering the withheld ground improve pit detection? No.

**Date:** 2026-09-19
**Status:** answered — closes the top item in `BACKLOG.md`
**Stack builder:** `notebooks/wellsight_v2/s7_analysis/_smrf_feature_stack_9t.py`
**Trainer:** `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py --tag smrf`
**Arms:** vendor ground `data/9t/models/pit/unet_cv5/` vs SMRF ground
`data/9t/models/pit/unet_cv5_smrf/`

## Why

The Data QA work established that the March-2020 flight block withholds every
at-ground return beyond 18° off nadir, that this leaves 13.8% of the training
area with no ground measurement under it, and that classifying the ground
ourselves closes most of it. Three skeptic tests then showed the withheld
returns measure as well as the ones kept — 0.089 m against 0.087 m, matched at
every slope — and that putting them back leaves no seam.

All of that is about the **input**. None of it showed the **output** changes.
Until a model trained on the recovered ground was scored on the same folds, the
honest position was that the 18° cut may have cost nothing we needed.

## How the comparison was kept honest

Both arms use the same labels, the same `pit_blocks_9t.gpkg` split, the same
five folds, the same inner-validation fold for epoch and threshold selection,
the same architecture and schedule. The **only** difference is which points are
classified ground.

The SMRF stack was written on the **same grid as the vendor stack**, asserted
rather than assumed — `9000 × 9000 @ 0.5 m`, identical transform — so labels,
blocks and patches line up without resampling. Normalisation statistics were
recomputed over train blocks only, from the SMRF stack's own distributions.

One trap was caught on the way. `_build_derivatives.py` writes `roughness_5` at
0.5 m and the stack wants `roughness_11`. `BACKLOG` B5 records `roughness_11` as
a mislabel of `roughness_5`, which would have made substituting it look safe.
Checked against the vendor band instead:

    recomputed 5×5   vs vendor roughness_11:  corr 0.568, means 0.076 / 0.151
    recomputed 11×11 vs vendor roughness_11:  corr 0.996, mean |diff| 0.0013

The mislabel holds at 1 m, where a 5-cell window spans the same ground as 11
cells at 0.5 m. It does not hold here. Using the 5×5 would have changed channel
7 between the arms and confounded the result.

## What the input change looks like

The SMRF surface is measurably rougher in every channel — train-block standard
deviation, SMRF ÷ vendor:

| channel | sd ratio |
|---|---|
| lrm_5 | 1.42 |
| openness_neg | 1.28 |
| tpi_05 | 1.26 |
| lrm_25 | 1.25 |
| openness_pos | 1.23 |
| roughness_11 | 1.15 |
| slope | 1.09 |

So the intervention did something. The question is whether it is signal.

## Result — paired by fold

Both arms ran identical folds, so the paired difference is the right test.

**F1-selected threshold**

| metric | vendor | SMRF | delta | folds better | paired mean ± sd | t |
|---|---|---|---|---|---|---|
| recall @ IoU 0.3 | 0.861 | 0.893 | +0.032 | 3/5 | +0.031 ± 0.084 | +0.83 |
| precision @ IoU 0.3 | 0.690 | 0.680 | −0.009 | 1/5 | −0.009 ± 0.047 | −0.42 |
| F1 @ IoU 0.3 | 0.764 | 0.770 | +0.006 | 3/5 | +0.006 ± 0.017 | +0.82 |
| recall @ IoU 0.5 | 0.700 | 0.748 | +0.048 | 3/5 | +0.047 ± 0.199 | +0.53 |
| containment | 0.914 | 0.934 | +0.020 | 4/5 | +0.020 ± 0.054 | +0.81 |

**F2-selected threshold**

| metric | vendor | SMRF | delta | folds better | paired mean ± sd | t |
|---|---|---|---|---|---|---|
| recall @ IoU 0.3 | 0.928 | 0.915 | −0.014 | 1/5 | −0.014 ± 0.027 | −1.19 |
| precision @ IoU 0.3 | 0.639 | 0.652 | +0.013 | 3/5 | +0.013 ± 0.049 | +0.57 |
| F1 @ IoU 0.3 | 0.755 | 0.758 | +0.003 | 3/5 | +0.003 ± 0.036 | +0.19 |
| recall @ IoU 0.5 | 0.823 | 0.742 | **−0.082** | 1/5 | −0.082 ± 0.096 | −1.91 |
| containment | 0.956 | 0.952 | −0.004 | 2/5 | −0.004 ± 0.024 | −0.39 |

**No |t| reaches 2.** The two threshold objectives disagree in sign on recall,
which is what a null result looks like. The largest single effect is SMRF being
*worse* at the tighter IoU 0.5 under F2 selection.

## Interpretation

**Recovering the withheld ground does not improve pit detection.** The 18° cut
removed a great deal of measurement, and the measurement was good, and the model
did not need it.

That is not a surprising outcome in hindsight, and the reason is in the earlier
tests: only **26.8%** of the 1 m void cells hold nothing but wide-angle returns.
**68.1% contain near-nadir returns and still have no ground**, because the canopy
occluded it. SMRF cannot fix those. The angle rule explains about a quarter of
the holes, and closing a quarter of the holes moved nothing detectable.

The rougher SMRF surface (sd ratios 1.09–1.42) is the other half of the story.
Whatever real micro-relief it recovers appears to be offset by low vegetation
retained as ground. Net zero.

**A prediction was made before the run and it held.** The stated expectation was
"roughly flat, possibly slightly worse." An interim note after fold 0 alone
(recall 0.932 against a 0.864 baseline fold) read as a gain; the remaining four
folds removed it. One fold of five is not a direction, and it should not have
been described as one.

## What this changes

**The Data QA section of the talk stays a rigour story, not a results story.**
The defensible claim is unchanged and now fully supported:

- the delivered surface has systematic, stripe-shaped gaps
- the returns that would fill them measure as well as the ones already in it
- we checked whether that mattered to detection, and it did not

That last line is the one to add. A section that demonstrates a problem and
never tests whether it matters invites the question from the floor. A section
that tests it and reports a null answers it.

**Do not reprocess the other 175 squares.** `BACKLOG` deferred that day of
compute pending this re-score. The re-score says no.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_smrf_feature_stack_9t.py --workers 3
python notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py \
    --features data/9t/derived/smrf05/features_pit_smrf_9t_05.tif \
    --stats    data/9t/derived/smrf05/feature_stats_smrf.json --tag smrf
```

Stack build ~2.5 h (9 squares SMRF + derivatives + stack), retrain 53.9 min.

## Outputs

`data/9t/models/pit/unet_cv5_smrf/`

- `pit_cv5_per_fold_9t.csv`
- `pit_cv5_recovery_curve_9t.csv`
- `pit_cv5_fold_assignment_9t.csv`
- `fold<k>/best.pt`, `fold<k>/pit_prob_floor_cvfold<k>_9t_05.tif` (gitignored)

`data/9t/derived/smrf05/` (gitignored — 1,316 MB stack plus ~2 GB classified LAZ)

- `features_pit_smrf_9t_05.tif`, `feature_stats_smrf.json`
- `roughness_11_smrf9t_05.tif` and the other per-channel derivatives
