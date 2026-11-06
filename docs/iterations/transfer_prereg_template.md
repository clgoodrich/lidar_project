# Transfer pre-registration template

**Status:** template. Copy it to `transfer_<area>_prereg.md`, fill every field, commit it, then look at model output. Do not edit the committed copy after scoring. Add an amendment section instead.

## 1. Question
One sentence. Example. Does the tile 9t pit model keep its recall at fixed K in area X.

## 2. Population and unit
- Target population. Pits, pads or both.
- Candidate unit. One detection per pit. Second pieces of one pit are dropped.
- Scored footprint. A polygon file, fixed before scoring. It includes places where the model finds nothing. Path.
- Eligibility rules. Identical for observed and null data. Edge rule.

## 3. Data and provenance
- Lidar source, program, acquisition dates, measured ground density in points per m2. Measure it. Do not infer it from file size.
- Label source and its evidence level. (a) drawn feature, (b) historical evidence, (c) steel anomaly, (d) confirmed well. Never merge levels.
- SHA-256 of every input file and of the checkpoint. Record the commit too.
- Interpreter and package versions. Output of `python -m pip freeze` saved to the run folder.

## 4. Frozen items
Weights, preprocessing, proposal extraction, calibration and threshold or K. Nothing is retuned on the test area.

## 5. Areas
- Adaptation area. Used for any calibration or fine-tuning. Path.
- Test area. Never used to adapt. Separated from adaptation by a spatial buffer of at least 500 m.
- Audit set. Blocks excluded from all training, calibration, negative mining and model selection. List the models and steps that touched each block before calling it untouched. Include the models that supply context features.

## 6. Primary analysis
- One primary metric. Recall at fixed K, or average precision at IoU 0.3.
- One primary radius or tolerance. Others are sensitivity only.
- Uncertainty. Bootstrap over blocks, not over detections. Resamples and seed.
- Platt scaling is monotonic. It cannot change recall at fixed K. Judge calibration by Brier score, log loss and calibration error.

## 7. Decision rule
- Non-inferiority margin. Set before scoring. Compare by a confidence interval for the difference. Overlapping separate intervals are not a test.
- Action if met. Action if not met. Action if inconclusive.

## 8. Labels from the target area
- Who labels, how many reviewers, blinded to score. Categories include "uncertain".
- Unmatched is not negative. Only independently adjudicated confusers become negatives.
- Agreement statistic. Kappa is reported but is not the acceptance criterion.

## 9. Report
- Feature detection and agency-record association reported separately.
- Precision needs independent evidence. Blind lidar interpretation alone does not give well precision.
- Every analysis not listed here is labelled exploratory.

## 10. Amendments
Date, what changed, why, before or after viewing output.

## 11. Required fields added 2026-11-04
Source `docs/plans/protocol_gates_and_metrics.md`.
- Primary metric is recall at K candidates per km² of scored area. State K and its policy. State the 9t reference at the same K and the raster it comes from.
- Report features per km² in reference and target blocks. Add a secondary at K scaled to density.
- Score complete blind blocks, including blocks with no features.
- State the buffer and how it was derived. State the split file and its hash. Label splits historical or future.
- Normalisation is fitted inside the fold. Preprocessing at 0.5 m.
- State the sampling unit and the effective sample. Seeds, site-seasons and detections are not independent.
- State the margin and where it comes from. Readiness gates are separate from scientific gates.
- Project the interval width before spending annotation time.

## 12. Scoring and checkpoint fields added 2026-11-06

The 3.0 decision report and the 3.1 scorer read these fields and compare them with the reference tables and the target run. A mismatch stops the gate. Source: `expkit.policy_for` and `expkit.assert_same_policy` in `expansions/_shared/src/expkit.py`.

- `scoring.cutoff`. Pit 0.35, pad 0.525. 0.10 is a sensitivity only.
- `scoring.iou`. 0.3.
- `scoring.order`. `score` (greedy in score order). `iou` is a sensitivity only.
- `scoring.dedupe`. A second blob inside a matched feature is a duplicate.
- `scoring.void_cap`. Largest void fraction of a complete block. 0.5 (user default 2026-11-06).
- `scoring.k_per_km2`. 40. 30 is a sensitivity only.
- `checkpoint.family`. For example `pit/unet_cv5`. The provisional transfer model for 3.4 to 3.7 is the five-fold 9t ensemble `pit/unet_cv5` and `pad/unet_cv5_iso` under `fold_mean` (user default 2026-11-06).
- `checkpoint.lineage`. `isolated` or `provisional`. A provisional checkpoint gives a descriptive result only.
- `checkpoint.sha256`. Hash of every checkpoint file used.

## 13. Defaults accepted 2026-11-06

The user accepted these defaults ("take defaults"). A preregistration may state other values with a reason.

- `margin`. 0.03 recall for any non-inferiority margin. A useful gain (`delta_gain`) is also 0.03 recall.
- `multiplicity`. Holm over the declared primary gates of the expansion only. List them as `multiplicity.family` and name this file's gate as `multiplicity.gate`. Secondaries and sensitivities are reported and never gated.
- Holm gate. The one-sided bootstrap share is the fraction of difference draws at or below minus the margin. Success needs the Holm-adjusted share under 0.025. Failure needs the upper bound below minus the margin. A family of one gives the plain interval rule. Code `expansions/3_geography/3_0_transfer_protocol/src/_transfer_holm_gate.py`.
- `max_undefined`. 0. Any undefined bootstrap draw makes the gate inconclusive.
- `scoring.void_cap`. 0.5.
- Fill rule for feature-free 9t blocks. Round robin is primary. Fold mean is the sensitivity.
- 3.3 footprint. All blocks, including the pit-free blocks.
- Transfer checkpoint for 3.4 to 3.7. Label every result "provisional transfer model". The fold that seeds fine-tuning is not decided.
