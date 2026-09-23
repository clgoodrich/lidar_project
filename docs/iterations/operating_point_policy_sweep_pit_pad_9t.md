# Operating-point policy sweep: cost ratio, review budget, recall guarantee and F-β, pit and pad CV5 on 9t

**Date:** 2026-09-23
**Status:** swept. **No policy is chosen yet. The choice is the user's.**
This is Phase 3 of `docs/iterations/operating_point_policy_plan.md`. It builds on `docs/iterations/cv5_threshold_free_pr_and_calibration_pit_pad_9t.md`.
**Script:** `notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py`
**Models:** `data/9t/models/pit/unet_cv5/` and `data/9t/models/pad/unet_cv5/`, ann712, five folds. CPU only.

## Goal

Phase 1 showed that the operating point should be a cut of the ranked candidate list, not a pixel cutoff.
This phase asks how to choose where to cut, and compares every candidate policy on the same held-out data.

## Setup

- **Candidates.** Each fold's blobs at its proposal cutoff, ranked by Platt-calibrated score. This is the same list as Phase 1.
- **Everything is set leave-one-fold-out.** For fold k, the calibrator and each policy's cut are fitted on the other four folds' held-out candidates. Fold k's labels are read only to score. Inner val is not used, because it cannot be reproduced. The Phase 1–2 doc explains why.
- **Scoring.** Held-out recall and precision at IoU 0.3, pooled over five folds. Candidates and false positives are counted per km² of held-out ground. The 95% CI is a block bootstrap. "Fold recall min–max" shows how much one fold's result can differ from the pooled one.

## The four policy families

| Family | What a person supplies | Rule for fold k | What it promises | How the promise is checked |
|---|---|---|---|---|
| **Cost ratio** (Elkan 2001) | r = cost of a missed well ÷ cost of a wasted check | keep candidates with calibrated p ≥ 1/(1+r) | the lowest expected cost | regret: extra cost over the best single cut in hindsight on fold k |
| **Review budget** | K = candidates crews can check per km² | keep the top K × area by score | exactly K per km² | exact by construction; recall is what varies |
| **Recall guarantee** (conformal risk control, Angelopoulos et al. 2022) | ρ = the recall to guarantee | highest cut whose corrected calibration miss rate is ≤ 1 − ρ | expected block-level recall ≥ ρ | block-mean held-out recall against ρ |
| **F-β** (today's rule, moved onto the ranked list) | β, where β² is the miss-to-false-alarm weight | cut that maximises F-β on the other folds | nothing | — |

Today's pixel cutoffs are included as reference rows:
- **F1** and **F2** are read from the CV5 per-fold CSVs.
- **Deployed** is 0.60 for pits and 0.70 for pads, from `notebooks/wellsight_v2/s4_infer/_postfilter_tile_candidates.py`. Its 20/300 m² area floor and its morphology are not applied, so this row flatters the deployed filter.

## Main finding: every ranked-list policy beats today's pixel cutoffs

All four families cut the same ranked list, so they all land on one curve. The figures show this.
Today's pixel cutoffs sit **below** that curve.

Same effort, better result. Each of today's cutoffs is compared with a ranked cut that keeps the **same number of candidates per km²**:

| Task | Today's cutoff | Candidates/km² | Today: recall / precision | Ranked cut: recall / precision | Change |
|---|---|---|---|---|---|
| pit | F1 pixel cutoff | 39.0 | 0.861 / 0.686 | 0.901 / 0.725 | +0.040 / +0.039 |
| pit | F2 pixel cutoff | 45.6 | 0.928 / 0.633 | 0.936 / 0.666 | +0.008 / +0.033 |
| pit | deployed 0.60 | 36.2 | 0.809 / 0.695 | 0.881 / 0.759 | +0.072 / +0.064 |
| pad | F1 pixel cutoff | 53.3 | 0.888 / 0.597 | 0.898 / 0.606 | +0.011 / +0.009 |
| pad | F2 pixel cutoff | 55.7 | 0.912 / 0.587 | 0.900 / 0.586 | −0.012 / −0.001 |
| pad | **deployed 0.70** | 41.2 | **0.640 / 0.556** | **0.822 / 0.717** | **+0.182 / +0.161** |

- **The deployed pad cutoff is the worst operating point measured.** At the same effort, a ranked cut finds 18 points more pads, and 16 points more of its candidates are real.
- The pad F2 row is the one exception. That cutoff keeps nearly every candidate, so it sits at the list's recall ceiling of 0.90. No cut of the list can beat a point at its ceiling.

## How the families compare

1. **They reach the same points.** The families differ only in the question a person has to answer. The curve is fixed by the model.
2. **The review budget is the most stable across folds, and needs no labels.** Pads at 30 per km² range 0.628–0.674 across folds. The recall guarantee at a similar effort (ρ 0.70, 32.9 per km²) ranges 0.566–0.792. A budget adapts to how many candidates each area has. A probability cut does not. The budget also transfers to a new tile unchanged, because it needs no calibration there.
3. **The recall guarantee keeps its promise to within about 0.01.** The guaranteed quantity is block-mean recall.
   - For pits it meets or misses by at most 0.009, for example ρ 0.80 gives 0.791.
   - For pads it misses by at most 0.006.
   - Pooled recall meets the target for every feasible pit setting.
   - The guarantee is in expectation. A single fold can fall well short: at ρ 0.70 the worst pit fold is 0.590.
   - Targets above the list's ceiling are infeasible: pits at 0.95, pads at 0.90 and 0.95. The rule then keeps every candidate and says so.
   - On a new tile the guarantee needs labelled calibration blocks from that tile.
4. **The cost ratio is sound, but its input is the hardest to supply.** Regret is 2–18% for pits and 1–9% for pads, largest when misses are cheap.
   - It saturates at r ≈ 32 for pits and r ≈ 16 for pads. Beyond that every candidate already passes.
   - It needs a defensible C_FN/C_FP. It also needs calibration that transfers to the new tile.
5. **F-β promises nothing.** F-β 2 is today's rule on the ranked list. It lands close to cost ratio 4 (pit recall 0.926 against 0.922). That is expected, since β² = 4 encodes the same trade.

## What each setting costs

The full sweep is below. Recall is held-out at IoU 0.3. Precision is a lower bound, because unannotated real features count as false.

To read the tables:
- **Candidates/km²** is field effort.
- **FP/km²** is wasted effort, as a lower bound.
- **Fold recall min–max** shows how far a single area can fall from the pooled figure.

### pit

| Policy | Setting | Recall (95% CI) | Precision | Candidates/km² | FP/km² | Fold recall min–max | Promise check |
|---|---|---|---|---|---|---|---|
| cost ratio C_FN/C_FP | 0.5 | 0.684 (0.639–0.730) | 0.823 | 25.8 | 4.6 | 0.560–0.780 | regret 17.6% |
| cost ratio C_FN/C_FP | 1 | 0.841 (0.808–0.872) | 0.782 | 33.5 | 7.3 | 0.760–0.901 | regret 12.5% |
| cost ratio C_FN/C_FP | 2 | 0.891 (0.861–0.918) | 0.745 | 37.2 | 9.5 | 0.869–0.921 | regret 10.0% |
| cost ratio C_FN/C_FP | 4 | 0.922 (0.899–0.945) | 0.698 | 41.1 | 12.4 | 0.883–0.941 | regret 9.8% |
| cost ratio C_FN/C_FP | 8 | 0.938 (0.919–0.958) | 0.657 | 44.4 | 15.2 | 0.903–0.960 | regret 7.4% |
| cost ratio C_FN/C_FP | 16 | 0.944 (0.926–0.962) | 0.620 | 47.4 | 18.0 | 0.913–0.960 | regret 9.0% |
| cost ratio C_FN/C_FP | 32 | 0.946 (0.928–0.964) | 0.611 | 48.2 | 18.7 | 0.913–0.970 | regret 5.1% |
| cost ratio C_FN/C_FP | 64 | 0.946 (0.928–0.964) | 0.611 | 48.2 | 18.7 | 0.913–0.970 | regret 2.9% |
| cost ratio C_FN/C_FP | 128 | 0.946 (0.928–0.964) | 0.611 | 48.2 | 18.7 | 0.913–0.970 | regret 1.5% |
| budget, candidates/km² | 2 | 0.058 (0.038–0.079) | 0.967 | 1.9 | 0.1 | 0.050–0.070 | exact by construction |
| budget, candidates/km² | 5 | 0.147 (0.111–0.185) | 0.937 | 4.9 | 0.3 | 0.131–0.180 | exact by construction |
| budget, candidates/km² | 10 | 0.284 (0.233–0.334) | 0.894 | 9.9 | 1.1 | 0.253–0.340 | exact by construction |
| budget, candidates/km² | 15 | 0.417 (0.367–0.468) | 0.875 | 14.8 | 1.9 | 0.374–0.490 | exact by construction |
| budget, candidates/km² | 20 | 0.541 (0.491–0.592) | 0.845 | 19.9 | 3.1 | 0.505–0.630 | exact by construction |
| budget, candidates/km² | 25 | 0.664 (0.613–0.712) | 0.833 | 24.8 | 4.1 | 0.604–0.780 | exact by construction |
| budget, candidates/km² | 30 | 0.781 (0.739–0.822) | 0.814 | 29.9 | 5.6 | 0.723–0.900 | exact by construction |
| budget, candidates/km² | 40 | 0.909 (0.881–0.935) | 0.717 | 39.4 | 11.1 | 0.869–0.970 | exact by construction |
| budget, candidates/km² | 50 | 0.946 (0.928–0.964) | 0.629 | 46.8 | 17.4 | 0.913–0.970 | exact by construction |
| recall target | 0.6 | 0.646 (0.597–0.692) | 0.833 | 24.1 | 4.0 | 0.530–0.750 | block-mean 0.613 |
| recall target | 0.7 | 0.738 (0.694–0.779) | 0.810 | 28.3 | 5.4 | 0.590–0.861 | block-mean 0.693 |
| recall target | 0.75 | 0.785 (0.744–0.826) | 0.801 | 30.5 | 6.1 | 0.650–0.870 | block-mean 0.743 |
| recall target | 0.8 | 0.829 (0.797–0.861) | 0.787 | 32.8 | 7.0 | 0.730–0.911 | block-mean 0.791 |
| recall target | 0.85 | 0.879 (0.846–0.908) | 0.761 | 35.9 | 8.6 | 0.840–0.921 | block-mean 0.851 |
| recall target | 0.9 | 0.924 (0.901–0.948) | 0.709 | 40.6 | 11.8 | 0.883–0.950 | block-mean 0.915 |
| recall target | 0.95 | 0.946 (0.928–0.964) | 0.611 | 48.2 | 18.7 | 0.913–0.970 | block-mean 0.941, infeasible in 5/5 folds |
| F-β | 0.5 | 0.759 (0.717–0.803) | 0.808 | 29.2 | 5.6 | 0.650–0.881 | — |
| F-β | 1 | 0.857 (0.824–0.887) | 0.764 | 34.9 | 8.2 | 0.780–0.911 | — |
| F-β | 2 | 0.926 (0.903–0.949) | 0.687 | 41.9 | 13.1 | 0.883–0.950 | — |
| F-β | 3 | 0.934 (0.913–0.955) | 0.652 | 44.6 | 15.5 | 0.883–0.960 | — |
| F-β | 4 | 0.940 (0.922–0.959) | 0.632 | 46.3 | 17.1 | 0.913–0.960 | — |
| today | F1 pixel cutoff | 0.861 | 0.686 | 39.0 | 12.2 | 0.810–0.911 | — |
| today | F2 pixel cutoff | 0.928 | 0.633 | 45.6 | 16.8 | 0.899–0.950 | — |
| today | deployed pixel cutoff 0.60 (no area floor) | 0.809 | 0.695 | 36.2 | 11.1 | 0.758–0.835 | — |

### pad

| Policy | Setting | Recall (95% CI) | Precision | Candidates/km² | FP/km² | Fold recall min–max | Promise check |
|---|---|---|---|---|---|---|---|
| cost ratio C_FN/C_FP | 0.5 | 0.563 (0.515–0.607) | 0.792 | 25.5 | 5.3 | 0.419–0.654 | regret 9.2% |
| cost ratio C_FN/C_FP | 1 | 0.743 (0.701–0.782) | 0.750 | 35.5 | 8.9 | 0.667–0.815 | regret 7.5% |
| cost ratio C_FN/C_FP | 2 | 0.842 (0.808–0.873) | 0.702 | 42.9 | 12.8 | 0.814–0.885 | regret 6.3% |
| cost ratio C_FN/C_FP | 4 | 0.888 (0.856–0.916) | 0.653 | 48.7 | 16.9 | 0.864–0.923 | regret 5.8% |
| cost ratio C_FN/C_FP | 8 | 0.900 (0.873–0.925) | 0.587 | 54.9 | 22.7 | 0.879–0.931 | regret 8.4% |
| cost ratio C_FN/C_FP | 16 | 0.900 (0.873–0.925) | 0.575 | 56.1 | 23.9 | 0.879–0.931 | regret 5.3% |
| cost ratio C_FN/C_FP | 32 | 0.900 (0.873–0.925) | 0.575 | 56.1 | 23.9 | 0.879–0.931 | regret 3.0% |
| cost ratio C_FN/C_FP | 64 | 0.900 (0.873–0.925) | 0.575 | 56.1 | 23.9 | 0.879–0.931 | regret 1.6% |
| cost ratio C_FN/C_FP | 128 | 0.900 (0.873–0.925) | 0.575 | 56.1 | 23.9 | 0.879–0.931 | regret 0.8% |
| budget, candidates/km² | 2 | 0.048 (0.030–0.067) | 0.912 | 1.9 | 0.2 | 0.038–0.054 | exact by construction |
| budget, candidates/km² | 5 | 0.128 (0.101–0.156) | 0.954 | 4.8 | 0.2 | 0.115–0.140 | exact by construction |
| budget, candidates/km² | 10 | 0.238 (0.202–0.278) | 0.871 | 9.8 | 1.3 | 0.223–0.264 | exact by construction |
| budget, candidates/km² | 15 | 0.354 (0.310–0.397) | 0.858 | 14.8 | 2.1 | 0.346–0.364 | exact by construction |
| budget, candidates/km² | 20 | 0.460 (0.411–0.505) | 0.831 | 19.8 | 3.4 | 0.450–0.470 | exact by construction |
| budget, candidates/km² | 25 | 0.558 (0.512–0.601) | 0.807 | 24.8 | 4.8 | 0.546–0.569 | exact by construction |
| budget, candidates/km² | 30 | 0.648 (0.602–0.689) | 0.778 | 29.8 | 6.6 | 0.628–0.674 | exact by construction |
| budget, candidates/km² | 40 | 0.803 (0.763–0.839) | 0.722 | 39.9 | 11.1 | 0.783–0.853 | exact by construction |
| budget, candidates/km² | 50 | 0.889 (0.858–0.917) | 0.640 | 49.8 | 17.9 | 0.864–0.923 | exact by construction |
| recall target | 0.6 | 0.617 (0.570–0.661) | 0.792 | 27.9 | 5.8 | 0.496–0.723 | block-mean 0.609 |
| recall target | 0.7 | 0.700 (0.657–0.741) | 0.763 | 32.9 | 7.8 | 0.566–0.792 | block-mean 0.697 |
| recall target | 0.75 | 0.740 (0.698–0.780) | 0.747 | 35.5 | 9.0 | 0.667–0.831 | block-mean 0.750 |
| recall target | 0.8 | 0.798 (0.760–0.834) | 0.724 | 39.5 | 10.9 | 0.736–0.869 | block-mean 0.798 |
| recall target | 0.85 | 0.845 (0.810–0.877) | 0.705 | 42.9 | 12.7 | 0.814–0.900 | block-mean 0.844 |
| recall target | 0.9 | 0.897 (0.869–0.922) | 0.586 | 54.8 | 22.7 | 0.876–0.931 | block-mean 0.889, infeasible in 4/5 folds |
| recall target | 0.95 | 0.900 (0.873–0.925) | 0.575 | 56.1 | 23.9 | 0.879–0.931 | block-mean 0.891, infeasible in 5/5 folds |
| F-β | 0.5 | 0.700 (0.655–0.741) | 0.758 | 33.1 | 8.0 | 0.566–0.792 | — |
| F-β | 1 | 0.843 (0.808–0.875) | 0.709 | 42.6 | 12.4 | 0.814–0.869 | — |
| F-β | 2 | 0.886 (0.856–0.914) | 0.652 | 48.7 | 17.0 | 0.841–0.931 | — |
| F-β | 3 | 0.895 (0.866–0.922) | 0.631 | 50.8 | 18.7 | 0.864–0.931 | — |
| F-β | 4 | 0.895 (0.866–0.922) | 0.625 | 51.3 | 19.2 | 0.864–0.931 | — |
| today | F1 pixel cutoff | 0.888 | 0.597 | 53.3 | 21.5 | 0.803–0.938 | — |
| today | F2 pixel cutoff | 0.912 | 0.587 | 55.7 | 23.0 | 0.886–0.938 | — |
| today | deployed pixel cutoff 0.70 (no area floor) | 0.640 | 0.556 | 41.2 | 18.3 | 0.535–0.746 | — |

## Choosing

The user needs to answer one question, depending on the family chosen:

- **Budget:** how many candidates can a crew check per km²? At 20/km² you find about half the pits. At 40/km² you find about 90%.
- **Recall guarantee:** what recall must be guaranteed? ρ 0.85 costs about 36 pit candidates/km² or 43 pad candidates/km².
- **Cost ratio:** how many wasted checks is one missed well worth?

Once chosen, the policy is recorded in `docs/iterations/operating_point_policy_plan.md`. The deployed filter is then replaced with the matching ranked cut.

## Limits

- One tile, and one seed per fold model.
- Precision and FP/km² are lower bounds until Phase 5's blind review.
- A matched pair is credited to the block holding the candidate's centroid. A pit on a block edge can be credited to its neighbour.
- The recall guarantee assumes calibration and held-out blocks are exchangeable. Here they come from one tile but are scored by different fold models, so this holds only approximately.

## Outputs

All under `data/9t/results/operating_point/`:

- `policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.csv` holds every row above, including the per-fold cut values (`rule_per_fold`) and per-fold recall.
- `policy_sweep_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.json` holds the same rows as JSON.
- `policy_sweep_run_cv5_pit_pad_9t.log` is the run log.

Figures are under `data/9t/results/operating_point/figures/`:

- `policy_sweep_recall_vs_candidates_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.png` places every policy and today's cutoffs on recall against candidates per km².
- `policy_sweep_precision_vs_recall_cost_budget_conformal_fbeta_heldout_cv5_iou0p30_pit_pad_9t.png` shows the same points on precision against recall.
- `policy_sweep_promise_check_conformal_cost_regret_budget_heldout_cv5_iou0p30_pit_pad_9t.png` checks each promise: conformal target against realized recall, cost regret, and budget against recall.

The palette is the lost/found set plus sky: `#1F5FA8`, `#D97706`, `#A31515` and `#5FB4E0`. It was validated on 2026-09-23 with the dataviz validator using `--mode light --pairs all`. The worst pair is `#A31515`/`#D97706` at ΔE 21.1 for deuteranopia and 22.6 for normal vision, and every colour has at least 3:1 contrast. There is no green. Each family also has its own marker, and today's cutoffs are black glyphs.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py        # once, ~35 min
python notebooks/wellsight_v2/s5_eval/_cv5_pr_calibration_pit_pad_9t.py          # ~5 min
python notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py  # ~1 min
```
