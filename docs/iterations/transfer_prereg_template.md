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
