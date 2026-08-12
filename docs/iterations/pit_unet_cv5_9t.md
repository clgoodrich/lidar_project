# pit U-Net, 5-fold cross-validation on 9t

**Date:** 2026-07-27
**Script:** `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py`
**Outputs:** `data/derivatives/tiles/9t/pit_unet_cv5/`

## Goal

Every pit number we had quoted rested on 65 test pits from one split. That is
small enough that a 3-point difference is noise. It also invites a fair
objection, that the split was lucky.

This trains five models. Each holds out a different fifth of the tile. Two
things follow.

1. All 426 hand-drawn pits get scored, each by a model that never saw it.
2. The spread across folds says whether a number is stable or noise.

No new annotation. No change to architecture, loss, channels or schedule.

## Design

Folds split by **block**, never by well. Training patches are 128 m with 30 m
jitter, so a patch centred on a training pit can physically overlap a
neighbouring held-out pit. The unit has to be the block.

Folds are balanced on **pit count**, not block count, because pits cluster on
pads. Seed `CV_SEED = 20260727`.

Per fold k:

| split | source | share of pits |
|---|---|---|
| held-out | fold k blocks | ~20% |
| inner val | 20% of remaining blocks | ~16% |
| train | the rest | ~64% |

The held-out fold never influences its own threshold or its own best epoch.
That is what makes the number defensible.

| fold | blocks | pits |
|---|---|---|
| 0 | 21 | 86 |
| 1 | 22 | 87 |
| 2 | 23 | 87 |
| 3 | 23 | 83 |
| 4 | 22 | 83 |

## Threshold selection, declared before scoring

The probability threshold is selected on the **inner val** split, twice, under
two objectives named in advance.

- **F1** weights recall and precision equally.
- **F2** weights recall 4x precision. A missed well costs more than a false
  alarm, which is the real asymmetry in this project.

Both are frozen, then scored once on the held-out fold. Reporting both, chosen
before any held-out data is seen, is the opposite of cherry-picking. Picking
whichever looked better afterwards would not be.

The full recovery curve over all 16 probability thresholds is also reported, so
no cutoff has to be defended at all.

## Metrics

- **recall @ IoU** — predicted floor against annotated floor (`pit_inside`),
  greedy 1:1 matching.
- **containment** — predicted floor centroid inside the annotated rim
  (`pit_outside`). This asks whether the model *located* a pit, not whether it
  *delineated* it.
- **precision** — predictions restricted to the held-out fold's block
  footprint. Without this the model is charged for detections in blocks that
  hold no scored ground truth.

Ground truth is hand-drawn annotation only. No state well coordinate is used to
score anything.

## Result

Pooled over all 5 folds, 426 pits, 424 rims.

| selection | thresholds chosen | recall @ IoU 0.3 | precision @ IoU 0.3 | recall @ IoU 0.5 | containment |
|---|---|---|---|---|---|
| by **F1** | 0.40, 0.50, 0.50, 0.50, 0.55 | **0.854** (0.736–0.954, sd 0.088) | 0.617 | 0.711 | 0.899 (381/424) |
| by **F2** | 0.30, 0.30, 0.30, 0.35, 0.55 | **0.920** (0.880–0.953, sd 0.035) | 0.553 | 0.730 | 0.955 (405/424) |

Per fold:

| fold | F1 thr | R@0.3 | P@0.3 | contain | F2 thr | R@0.3 | P@0.3 | contain |
|---|---|---|---|---|---|---|---|---|
| 0 | 0.50 | 0.907 | 0.722 | 78/85 | 0.30 | 0.953 | 0.617 | 83/85 |
| 1 | 0.40 | 0.954 | 0.585 | 83/87 | 0.30 | 0.943 | 0.522 | 84/87 |
| 2 | 0.50 | 0.736 | 0.566 | 74/87 | 0.35 | 0.885 | 0.550 | 82/87 |
| 3 | 0.55 | 0.880 | 0.575 | 76/82 | 0.55 | 0.880 | 0.575 | 76/82 |
| 4 | 0.50 | 0.795 | 0.660 | 70/83 | 0.30 | 0.940 | 0.513 | 80/83 |

### Threshold-free recovery curve, pooled

| prob thr | recall @0.3 | precision @0.3 | F1 @0.3 | recall @0.5 | containment | per-fold recall@0.3 range |
|---|---|---|---|---|---|---|
| 0.20 | 0.850 | 0.369 | 0.515 | 0.446 | 0.969 | 0.771–0.943 |
| 0.25 | 0.932 | 0.464 | 0.619 | 0.603 | 0.972 | 0.916–0.964 |
| **0.30** | **0.941** | 0.503 | 0.655 | 0.737 | 0.974 | 0.908–0.964 |
| 0.35 | 0.934 | 0.549 | 0.692 | 0.826 | 0.953 | 0.885–0.976 |
| 0.40 | 0.915 | 0.580 | 0.710 | 0.831 | 0.941 | 0.828–0.976 |
| **0.45** | 0.894 | 0.610 | **0.725** | 0.779 | 0.915 | 0.805–0.964 |
| 0.50 | 0.859 | 0.624 | 0.723 | 0.695 | 0.908 | 0.736–0.943 |
| 0.60 | 0.742 | 0.649 | 0.692 | 0.552 | 0.842 | 0.518–0.872 |
| 0.70 | 0.545 | 0.620 | 0.580 | 0.291 | 0.703 | 0.325–0.744 |
| 0.80 | 0.261 | 0.563 | 0.356 | 0.087 | 0.401 | 0.084–0.430 |

Full curve: `data/derivatives/tiles/9t/pit_unet_cv5/pit_cv5_pooled_recovery_curve_9t.csv`
Per-fold curve: `.../pit_cv5_recovery_curve_9t.csv`

## Interpretation

**The single-split number was pessimistic, not optimistic.** We had been quoting
pit recall 0.754 at IoU 0.3. Cross-validated over all 426 pits it is 0.854 under
the same F1 selection rule, and 0.920 under F2. The old split was one of the
harder fifths, and its val-selected threshold of 0.60 sits past the point where
recall falls away.

**Recall is stable, precision is the weak number.** Under F2 selection the
per-fold recall spread is 0.880 to 0.953, sd 0.035. That is a real result, not
noise. Precision runs 0.51 to 0.66 and never gets better than 0.65 at any
threshold, so the model produces roughly one false polygon for every two true
ones at its best operating point.

**Fold 2 and fold 4 are the hard folds.** Both drop about 15 points of recall
under F1 selection, and both recover under F2. Their inner-val split picked a
threshold of 0.50 that did not transfer. This is threshold sensitivity, not a
model that failed on those blocks.

**Containment separates locating from delineating.** At probability 0.30 the
model puts a detection inside 974 of every 1000 annotated rims, while floor IoU
recall at 0.5 is 0.737. Most of the loss between those two numbers is boundary
disagreement on features whose median annotated floor is ~26 m². The model finds
the pit and disagrees about its edge.

**F1 peaks flat between 0.40 and 0.55.** F1 moves 0.710, 0.725, 0.723, 0.722
across that span. Nothing distinguishes those four thresholds. Any claim resting
on choosing 0.45 over 0.50 is not a result.

### What this does not show

Every fold is still 9t. One landscape, one survey, one canopy condition, one
operator's annotation style. **This measures whether our number is stable. It
does not measure whether it transfers.** A held-out tile is still the open
question, and remains the single largest unquantified optimism in every pit
number we publish.

### Known limitations, stated not hidden

**1. Shared normalisation statistics.** `feature_stats.json` (7 means and 7
standard deviations) was computed once over the original training blocks and is
reused for every fold. It is not recomputed per fold. This leaks 14 global
numbers into each fold. The effect is small but it is not zero, and it is
cheaper to disclose than to re-derive.

**2. Fold 4's inner-val draw differs from folds 0–3.** Added 2026-07-28, found
while running the pad CV. The script created one RNG before the fold loop, so
the inner-val draw depended on how many folds had already run in that process.
Folds 0–3 were scored in one pass; fold 4 crashed and was re-scored alone, which
gave it the *first* draw rather than the fifth.

**Held-out sets are identical either way**, because fold assignment is
deterministic and independent of the RNG. No scored number is affected and no
held-out data influenced any threshold. What breaks is exact reproducibility —
re-running `--folds 5` today will not reproduce fold 4's threshold selection
bit-for-bit.

Fixed after this run by seeding per fold (`CV_SEED + 1000 * k`), so each fold's
draw is independent of execution order. **That fix also means a fresh run will
not reproduce folds 0–3 exactly either.** The numbers on this page stand as
scored; they are simply not bit-reproducible under the current code.

## Bugs found and fixed in this pass

1. **Results were written only after the loop.** Fold 4 died and took four folds
   of finished work with it. The script now flushes both CSVs after every fold,
   and carries forward rows for folds it is not re-running.
2. **`predict_full_tile` never moved the model to the GPU.** It moved the input
   patches and relied on `train_loop` having moved the model earlier. A caller
   that loads a checkpoint and predicts straight away died with
   `Input type (torch.cuda.HalfTensor) and weight type (torch.FloatTensor)`.
   Fixed in `notebooks/wellsight_v2/_dl.py`, not worked around in the caller.
3. **Scoring polygonized the whole 9000x9000 tile at 16 thresholds.** Now the
   probability raster is zeroed outside the val and held-out footprints, buffered
   by 40 m so no scored blob is clipped mid-object. Scoring went from stalling to
   ~2 s per threshold. No scored number changes.

## Files

All under `data/derivatives/tiles/9t/pit_unet_cv5/`:

| file | content |
|---|---|
| `pit_cv5_per_fold_9t.csv` | one row per fold per objective, the table above |
| `pit_cv5_recovery_curve_9t.csv` | per fold, all 16 probability thresholds |
| `pit_cv5_pooled_recovery_curve_9t.csv` | pooled across folds, all 16 thresholds |
| `pit_cv5_fold_assignment_9t.csv` | pit_id, block_id, fold — the split itself |
| `fold{0..4}/best.pt` | checkpoint, gitignored |
| `fold{0..4}/pit_prob_floor_cvfold{k}_9t_05.tif` | full-tile floor probability, gitignored |
| `fold{0..4}/train_log.csv` | per-epoch training log |

Run log: `data/derivatives/tiles/9t/_pit_cv5_rescore.log`, fold 4 in
`.../_pit_cv5_fold4.log`.

## Reproduce

```bash
python notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py --folds 5 --epochs 40
# one fold only, reusing finished checkpoints and rasters:
python notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py --folds 5 --only-folds 4
```

Existing checkpoints and probability rasters are reused as-is. Delete a fold
directory to force it to retrain.
