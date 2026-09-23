# Operating-point policy plan: choosing precision against recall without hand-picked cutoffs

**Date:** 2026-09-23
**Status:** Phases 0–2 done. Phase 3 is swept, and its policy choice is pending with the user. Phases 4–6 are not started.
**Phase 1–2 results:** `docs/iterations/cv5_threshold_free_pr_and_calibration_pit_pad_9t.md`
**Phase 3 sweep:** `docs/iterations/operating_point_policy_sweep_pit_pad_9t.md`

## The problem

Every detector ends in a cutoff. Above it a blob is a candidate. Below it the blob is dropped.
Where that cutoff sits decides the balance between precision and recall.

Precision is the share of candidates that are real.
Recall is the share of real features that become candidates.

Today several values that move this balance were set by hand.
Hand-set values carry the setter's bias. They are also hard to defend to a reviewer.

## The principle

Some human judgement cannot be removed.
The balance depends on what a miss costs compared with a false alarm. Data cannot supply that ratio.

The aim is to shrink that judgement to **one stated policy**.
It is written down before any test result is seen.
Every other value is either derived from data or searched by cross-validation.

## Phases

| # | Phase | Needs | Status |
|---|---|---|---|
| 0 | Inventory every hand-set value | grep | **done** (below) |
| 1 | Threshold-free model comparison: AP, FROC, block bootstrap, paired tests | CPU, saved fold rasters | **done** |
| 2 | Calibrate scores so a score means a probability | CPU, saved fold rasters | **done** |
| 3 | Set the operating point from a stated policy | **one user decision** | **swept 2026-09-23; choice pending** |
| 4 | Search training weights by nested CV; test whether the α bump was only a threshold shift | GPU | not started |
| 5 | Blind, stratified review of detections to measure precision without annotation gaps | analyst time | not started |
| 6 | Learn pit/pad/road fusion weights by stacked logistic regression | CPU | not started |

### Phase 3 policy options

Only one of these is chosen, and it is recorded here once chosen.

1. **Cost ratio.** On calibrated scores the best cutoff is `t* = C_FP / (C_FP + C_FN)`.
   `C_FP` is the cost of one wasted field check. `C_FN` is the cost of one missed well.
   Both can be estimated from DEP plugging and verification costs.
2. **Review budget.** Crews can check K candidates per km². Keep the top K by score.
   Phase 1's FROC curve gives the recall at each K directly.
3. **Recall guarantee.** Conformal risk control picks the cutoff that holds recall at or above a stated target.
   The guarantee holds in finite samples.

Recommended: the review budget. It matches how candidates are used in the field. The sweep also shows it is the most stable across folds, and it needs no labels on a new tile.

**Chosen policy:** _not yet chosen._

## Phase 0: inventory of hand-set values

Scope is the active pit, pad and road pipeline. Paths are under `notebooks/wellsight_v2/`.

"Effect" says what a value changes:

- **operating point** moves the precision/recall balance of a fixed model
- **model** changes what the network learns, and so its ranking
- **metric** changes what counts as found
- **none** is compute only; scores do not change

| Value | Where | Current | Set by | Effect | Derivable? |
|---|---|---|---|---|---|
| Threshold objective (F1 vs F2) | `s3_train/_pit_unet_cv5.py:33`, `_pad_unet_cv5.py` | both reported | declared up front | operating point | The β=2 in F2 is a cost ratio of 4. Phase 3 replaces it. |
| Probability threshold | same | pit 0.35–0.60, pad 0.50–0.65 per fold | inner val | operating point | Already data-selected. It inherits the F1/F2 bias. |
| **Deployed pit cutoff** | `s4_infer/_postfilter_tile_candidates.py:92` | **0.60** | hand | operating point | **Disagrees with CV.** The F2-selected pit cutoffs are 0.35–0.45. |
| **Deployed pad cutoff** | `s4_infer/_postfilter_tile_candidates.py:93` | **0.70** | hand | operating point | **Disagrees with CV.** Every CV-selected pad cutoff is 0.50–0.65. |
| **Deployed pit min area** | `s4_infer/_postfilter_tile_candidates.py:94` | **20 m²** | hand | operating point | **158 of 712 annotated pit floors (22%) are smaller than 20 m².** CV uses 4 m². |
| Deployed pad min area | `s4_infer/_postfilter_tile_candidates.py:95` | 300 m² | hand | operating point | 2 of 995 annotated pads are smaller. CV uses 100 m². |
| CV pit min area | `_pit_unet_cv5.py` `MIN_AREA_M2` | 4 m² | hand | operating point (weak) | Smallest annotated floor is 6.1 m². Consistent. |
| CV pad min area | `_pad_unet_cv5.py:114` | 100 m² | hand, from data | operating point (weak) | Smallest annotated pad is 260.5 m². Consistent. |
| Pit focal α | `_pit_unet_cv5.py` `FOCAL_ALPHA` | (0.05, 0.475, 0.475) | hand | model + calibration | Phase 4 searches it. |
| Pad focal α | `_pad_unet_cv5.py:112` | (0.15, 0.85) | hand | model + calibration | Phase 4 |
| Road focal α | `s3_train/_road_unet_1m_recall.py:54` | (0.10, **0.72**, 0.25) | **hand bump from 0.60 for recall** | model + calibration | Phase 4 tests whether it only shifted the threshold. |
| Focal γ | all trainers | 2.0 | Lin et al. 2017 default | model | Phase 4 |
| Selection IoU τ | `_pit_unet_cv5.py:114` | 0.3 | hand | metric | Phase 1 reports τ 0.3 and 0.5 side by side. |
| Road match tolerance | `s5_eval/_road_threshold_products_9t.py:83` | 5 m, 50% cover | hand | metric | Out of Phase 1–2 scope. |
| Road hysteresis | `s5_eval/_road_optimize.py:420` | hi 0.6, lo 0.4 | swept on val | operating point | Already swept. |
| Well-counting radius | `s5_eval/_uncounted_well_recovery_9t.py:72,84` | 25 m; pit 25, pad 40 | prior work | metric | Keep as a reported curve over `RADII`. |
| Score buffer | CV scripts `SCORE_BUF_M` | 40 / 80 m | hand | none | No effect on scores. |
| Patch, jitter, epochs, lr, inner-val fraction | CV scripts | — | hand | model | Phase 4, lower priority |

### What Phase 0 changes now

The deployed cutoffs in `_postfilter_tile_candidates.py` are the most urgent item.
They are stricter than anything CV selected.
The 20 m² pit floor could drop about a fifth of real pits before scoring starts.
Annotated area and predicted blob area differ, so the real loss needs measuring. It is not measured here.

This is escalated to the user. The defaults are not changed here.
Phase 3 will replace all four values with policy-derived ones.
