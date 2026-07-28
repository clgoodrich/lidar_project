# pad U-Net, 5-fold cross-validation on 9t

**Date:** 2026-07-28
**Script:** `notebooks/wellsight_v2/plats/_pad_unet_cv5.py`
**Outputs:** `data/derivatives/tiles/9t/pad_unet_cv5/`
**Companion to:** [[pit_unet_cv5_9t]]

## Goal

Direct companion to the pit cross-validation. Every pad number we quoted rested
on 93 test pads from one split. This trains five models, each holding out a
different fifth of the tile, so all 650 in-tile pads get scored by a model that
never saw them.

Parameters are copied verbatim from `_plat_unet.py`. Patch 384, jitter 40 m,
2 classes, focal alpha 0.15/0.85, 40 epochs. This measures the split, not a new
model.

## Design

Split by **block**, balanced on **pad count**, same greedy-deficit assignment and
same seed (`CV_SEED = 20260727`) as the pit CV. 650 pads across 129 blocks.

| fold | blocks | pads |
|---|---|---|
| 0 | 24 | 130 |
| 1 | 27 | 129 |
| 2 | 26 | 129 |
| 3 | 27 | 132 |
| 4 | 25 | 130 |

Folds came out within 3 pads of each other, tighter than the pit folds managed.

## Metrics

Same as the pit CV, with one substitution. Pits have `pit_inside` and
`pit_outside`, so containment meant floor-centroid-inside-rim. **Pads have only
one annotated polygon**, so the locate metric becomes "annotated pad contains at
least one predicted centroid". It answers the same question — did the model
*find* the pad, regardless of whether it drew the outline well.

## Result

Pooled over all 5 folds, 650 pads.

| selection | thresholds chosen | recall @ IoU 0.3 | precision @ 0.3 | recall @ IoU 0.5 | locate |
|---|---|---|---|---|---|
| by **F1** | 0.55, 0.60, 0.55, 0.60, 0.65 | **0.917** (0.894–0.946, sd 0.021) | 0.606 | 0.782 | 0.928 (603/650) |
| by **F2** | 0.55, 0.50, 0.55, 0.55, 0.55 | **0.920** (0.879–0.946, sd 0.025) | 0.591 | 0.788 | 0.909 (591/650) |

Per fold, F1-selected:

| fold | thr | R@0.3 | P@0.3 | R@0.5 | locate |
|---|---|---|---|---|---|
| 0 | 0.55 | 0.931 | 0.672 | 0.785 | 120/130 |
| 1 | 0.60 | 0.915 | 0.599 | 0.806 | 122/129 |
| 2 | 0.55 | 0.946 | 0.570 | 0.822 | 121/129 |
| 3 | 0.60 | 0.894 | 0.559 | 0.788 | 118/132 |
| 4 | 0.65 | 0.900 | 0.643 | 0.708 | 122/130 |

### IoU strictness scale, pooled

Each fold keeps the threshold already selected on its own inner val split, held
fixed across every row. Computed by
`notebooks/wellsight_v2/eval/_pad_cv5_tau_scale.py`.

| IoU required | pad R (F1-sel) | pad P (F1-sel) | pad R (F2-sel) | pad P (F2-sel) |
|---|---|---|---|---|
| 0.30 | 0.917 | 0.606 | 0.922 | 0.592 |
| 0.40 | 0.865 | 0.571 | 0.872 | 0.561 |
| 0.50 | 0.782 | 0.516 | 0.788 | 0.506 |
| 0.60 | 0.622 | 0.411 | 0.625 | 0.402 |
| 0.70 | 0.380 | 0.251 | 0.397 | 0.255 |

## Interpretation

**The single split was pessimistic here too.** We had been quoting pad recall
0.882 and precision 0.547 at IoU 0.3. Cross-validated over all 650 pads it is
0.917 and 0.606. Same direction as the pits, smaller magnitude.

**Pads are the more stable model.** Per-fold recall spread is sd 0.021, against
sd 0.088 for pits under the same F1 rule. The reason is size. A pad has a median
annotated area of 1,343 m² against ~26 m² for a pit floor, so a few pixels of
boundary disagreement barely move a pad's IoU and can move a pit's a lot.

**F1 and F2 nearly agree.** Pooled recall differs by 0.003 between the two
objectives. On three of five folds they selected the same threshold outright.
The operating point is not sensitive to which objective you argue for, which is
a useful thing to be able to say to a reviewer.

**One honest wrinkle.** On fold 3 the F2 selection scored recall 0.879, *below*
the F1 selection's 0.894, even though F2 is supposed to favour recall. F2 did
pick the lower threshold as designed (0.55 against 0.60); that threshold simply
scored slightly worse on the held-out fifth. Val and held-out do not always
agree. This is exactly why both objectives are declared in advance and both
reported, rather than whichever wins.

**Precision remains the ceiling**, as with pits. It peaks at 0.606 and falls
away with strictness. The model finds nearly every pad and draws too many.

### What this does not show

Every fold is still 9t. **This measures whether the number is stable. It does
not measure whether it transfers.**

### Known limitations, stated not hidden

1. **Shared normalisation stats.** `feature_stats.json` (7 means, 7 sds) is
   reused across folds rather than recomputed per fold. 14 global numbers enter
   each fold. Same disclosure as the pit CV.
2. **Folds were run in two batches**, 0–1 then 2–4, because the first run was
   killed. Under the code as it stood, the inner-val draw depended on how many
   folds had run before it in the same process, so fold 2's inner val was 93 pads
   in the first batch and 112 in the resumed one. **Held-out sets are identical
   either way** (deterministic fold assignment), so no scored number is affected
   and no held-out data influenced any threshold. Only exact reproducibility was
   hurt. Fixed after this run by seeding per fold; see below.

## Bugs found and fixed in this pass

1. **Resume could reuse a partial checkpoint.** The run was killed at epoch 35/40
   of fold 2, leaving a `best.pt` from an incomplete schedule. The resume path
   would have reused it, silently giving fold 2 fewer epochs than its siblings
   and breaking the one thing cross-validation controls for. `train_log.csv` row
   count is now the completion record and a short fold retrains from scratch.
2. **Inner-val draw was execution-order dependent.** One RNG was created before
   the fold loop, so skipped folds shifted every later draw. Now seeded per fold
   with `CV_SEED + 1000 * k`, independent of which folds run.
3. **`flush()` crashed on an empty result set**, which broke the dry-run path
   used to check fold balance before spending GPU time.

## Files

All under `data/derivatives/tiles/9t/pad_unet_cv5/`:

| file | content |
|---|---|
| `pad_cv5_per_fold_9t.csv` | one row per fold per objective |
| `pad_cv5_recovery_curve_9t.csv` | per fold, all 16 probability thresholds |
| `pad_cv5_iou_strictness_scale_9t.csv` | recall/precision vs IoU, per fold |
| `pad_cv5_iou_strictness_scale_9t.md` | the pooled table above |
| `pad_cv5_fold_assignment_9t.csv` | plat_id, block_id, fold |
| `fold{0..4}/best.pt` | checkpoint, gitignored |
| `fold{0..4}/pad_prob_cvfold{k}_9t_05.tif` | full-tile pad probability, gitignored |
| `fold{0..4}/train_log.csv` | per-epoch training log |

Run logs: `data/derivatives/tiles/9t/_pad_cv5_run.log` (folds 0–1, killed during
fold 2) and `_pad_cv5_resume.log` (folds 2–4).

Total 88.9 min for folds 2–4, roughly 30 min per fold at patch 384.

## Reproduce

```bash
python notebooks/wellsight_v2/plats/_pad_unet_cv5.py --folds 5 --epochs 40
python notebooks/wellsight_v2/eval/_pad_cv5_tau_scale.py
```

Finished checkpoints and probability rasters are reused. Delete a fold directory
to force it to retrain.
