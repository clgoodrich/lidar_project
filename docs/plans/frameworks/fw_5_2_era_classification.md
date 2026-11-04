# Framework 5.2. Era classification

**Tier B.** Blocked until valid dates exist.
**Evidence level.** (a) with era as an attribute.
**Depends on.** 4.6 (historic bounds), a date audit.

## 1. Problem and objective
Wells of different eras leave different surface marks. A classifier that estimates era from morphology could help date features and prioritise. An earlier note found a weak era signal in morphology and no dated well before 1956. About 92% of the DEP orphan-list spud dates are the 1800 sentinel (997 of 1,079).

**Objective.** Define which dates are trustworthy, build bounds from historical sources, and fit an ordinal model only on wells with valid dates.

## 2. Scope
In. Date audit, historical bounds, censored model.
Out. Using the 1800 sentinel as data.

## 3. Definitions
- **Valid date.** A spud or completion date from a source that is not a placeholder (not 1800/01/01 or 1900/01/01).
- **Upper bound on construction.** Presence on a dated map or aerial shows the feature existed by that date. Absence is censored, not evidence of a later date.
- **Identity.** Pads are reused. Link historical marks to wells by identity (record, wellhead) before position.

## 4. Inputs
DEP export fields `SPUD_DATE`, `DATE_PLUGG`, `PERMIT_DAT`. NY dated records (since 1860) and KY completion dates for cross-region morphology only. Historic marks (4.6). Morphology features (`docs/iterations/well_age_morphology.md`, `_pad_morphology_bins.py`).

## 5. Prerequisites and decisions
4.6 usable source. Date audit result.

## 6. Procedure
1. **Date audit** `docs/iterations/era_label_audit.md`. Count placeholders, check date distributions, and compare permit date to spud date.
2. **Bounds table** from 4.6 marks (earliest map date with mark at the position).
3. **Model.** Ordinal or interval-censored regression (for example a proportional-odds model or Cox with interval censoring) with morphology predictors (pad area, pit depth, rim sharpness, road geometry). Script `s7_analysis/_era_model_9t.py` (new). Output `data/9t/results/era/era_predictions_9t.csv`.
4. **Evaluate** on dated held-out wells (blocks as the resampling unit) with rank correlation and calibration.

## 7. Statistical analysis plan
Primary. Spearman correlation between predicted and valid dates on held-out wells with block bootstrap interval. Secondary. Ordinal accuracy by era bin.

## 8. Quality control
No placeholder dates. No leakage between blocks.

## 9. Gates
Success when the correlation lower bound is above a preregistered level. Else report the weak signal.

## 10. Deliverables
Audit doc, model script, predictions.

## 11. Failure modes
Too few valid dates. Pad reuse. Era signal confounded with land use.

## 12. Resources
15 hours after 4.6.

## 13. Handoff
Needs 4.6 output.

## 14. Documentation updates
Audit doc, `analysis_log.md`, master plan.
