# Framework 5.2. Era classification from morphology

**Tier B.** Full design. Assumes 4.6 delivers an identity-resolved dated subset. Nothing here has been run.
**Evidence level.** (a) drawn feature with era as an attribute. Dates come from (b) historical sources. No claim reaches (c) steel or (d) confirmed well.
**Depends on.** 4.6 (dated positions with identity), P1 and P2 (splits, audit blocks), the date audit in this framework.
**Blocks.** Era strata in 4.1 and 7.5 sampling, and any era term in 5.3 risk ranking.

## 1. Problem and objective
Wells from different eras leave different surface marks. An earlier note (`docs/iterations/well_age_morphology.md`) found a weak association between pad morphology and spud year inside the permit era. Pad perimeter gave rho -0.273, wells on pad -0.258, compactness +0.232 and area -0.203 on 615 pad-matched dated wells. No real-dated well in that area predates 1956. That is a result about 1956 and later. It says nothing about the 1860 to 1955 wells that matter most.

About 92% of DEP orphan-list spud dates are the 1800-01-01 sentinel (997 of 1,079 in Venango). The sentinel means "historic, date unknown". It is not a date and it is not "early".

**Objective.** Build era labels only from independently dated wells, test whether surface morphology predicts era beyond location and land use, and state what a classifier can and cannot claim about wells whose dates are unknown.

**Hypotheses.** H1. Morphology ranks an early-era well above a modern-era well with AUC above 0.5 plus δ_era on blocks the model did not see, after controlling for location. H0. It does not. The sentinel stratum is never used to test H1.

## 2. Scope
In. Date audit, label construction from 4.6, class definitions, label audit, block-split model, evaluation, a transportability check to the sentinel stratum.
Out. Using the sentinel as data in either direction. Treating map absence as a later date. Claims that a well is of a given era. Any magnetometer or field claim.

## 3. Definitions
- **Valid date.** A date from a source other than a placeholder (1800-01-01, 1900-01-01), checked in the audit. Spud, completion, permit and plug dates are kept separate.
- **Independently dated.** A well whose date comes from a source that does not depend on the lidar or on the DEP spud field. Examples are a dated map symbol identity-resolved by 4.6, a completion report, a lease record, a dated aerial.
- **Interval label.** Each dated well has an interval [lo, hi] for construction year. A map mark on a map dated D gives [1859, D] (left-censored, 1859 being the first Pennsylvania oil well). A spud date from a record gives [y, y]. Absence on a map gives no label.
- **Era classes (proposed, user decision).**
  - E1 early cable-tool, construction up to 1899.
  - E2 mid, 1900 to 1955.
  - E3 permit era, 1956 and later.
  - U unknown. The sentinel stratum. It is its own stratum, never a class that the model predicts and never merged into E1.
- **Ordinal target.** Interval-censored construction year, modelled on log scale. Classes are for reporting only.
- **Identity.** Pads are reused. A map mark is linked to a well record or wellhead before position, and the identity-resolution rule is the one 4.6 preregisters. A position-only link is flagged `identity = position_only` and excluded from primary training.
- **Unit of analysis.** The well-feature pair (one well to one pad or pit). Resampling unit is the block.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| DEP export with `SPUD_DATE`, `PERMIT_DAT`, `DATE_PLUGG` | `data/_source/reference/dep_wells/venango_wells_all.gpkg` (2026-04 export) | held, read-only |
| DEP orphan list, 2022-05-09 | `data/_source/reference/dep_wells/` (confirm file name) | held |
| Annotated pads and pits | `qgis/annotations/annotations_proj.gpkg` layers `plat`, `pit_inside` | held |
| Morphology script | `notebooks/wellsight_v2/s7_analysis/_well_age_morphology.py`, `_pad_morphology_bins.py` | held |
| Prior era note | `docs/iterations/well_age_morphology.md` | held |
| Historic marks, identity-resolved | `data/9t/results/historic/historic_well_marks_9t.gpkg` | proposed, from 4.6 S4 |
| 4.6 positional accuracy table | `docs/iterations/historic_imagery_probe_9t.md` | proposed |
| Cross-region dated records (NY since 1860, KY completion dates) | `data/_source/reference/` (confirm) | cross-region morphology only, VERIFY |
| Pad and pit probability rasters | `data/9t/models/pad/unet_cv5_iso/`, `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` | held |
| Block folds | split file from P1 | proposed |

## 5. Assumed data
| Assumption | Tag | How to verify |
|---|---|---|
| 4.6 delivers at least one usable dated source covering part of 9t or a neighbouring Venango tile | VERIFY | Read 4.6 verdict table per source and date. A source marked "unusable here" supplies nothing |
| The dated subset holds at least 100 identity-resolved wells, with at least 20 in E1 and 20 in E2 | VERIFY | Count rows after S2. If lower, the design below drops to descriptive only (gate section 10) |
| Identity resolution by 4.6 has a stated false-link rate from a blind adjudicated sample | VERIFY | Read the adjudication table. The link PPV bound enters section 8 as label noise |
| Positional accuracy of marks is at most 30 m RMSE (the 4.6 nominal limit) | VERIFY | Read the 4.6 georeferencing check. Pad association radius follows from it |
| At least some dated wells sit on annotated pads or pits in blocks outside the audit blocks | VERIFY | Join marks to annotations. Count per block |
| Date field semantics of the DEP export (spud, completion, permit) are documented | VERIFY | Read the data dictionary in `docs/`. Ask DEP if a field is undefined |
| Land-use and lease context layers (roads, cover, distance to oil-field boundary) exist for 9t | VERIFY | Locate rasters in `data/9t/derived/`. Needed for confound control |
| The DEP sentinel share is stable across the 2022 and 2026 snapshots | VERIFY | Count sentinel rows in each snapshot and diff keyed on (county, permit) |

## 6. Prerequisites and decisions
1. 4.6 verdict "usable" for at least one source. Otherwise this process does not start.
2. User decisions. Class boundaries (1899 and 1955 proposed), δ_era, and whether cross-region records may enter training (proposed no, validation of morphology direction only).
3. Preregistration committed before scoring.

## 7. Procedure
**S0. Date audit.**
- Script `notebooks/wellsight_v2/s7_analysis/_era_label_audit_9t.py` (proposed). Count by field. Sentinel (1800-01-01), 1900-01-01, null, impossible (before 1859 for oil, plug before spud, spud before permit by more than a stated gap, future dates). Compare permit year to spud year. Report each count and share.
- Output `docs/iterations/era_label_audit.md` and `data/9t/results/era/era_date_audit_9t.csv`. Every number comes from the CSV.

**S1. Stratum table.**
- One row per well in the study footprint with `stratum` in {dated_record, dated_map, sentinel, undated_other}. The sentinel stratum is kept as its own column value and never imputed. Output `data/9t/results/era/era_strata_wells_9t.csv`.

**S2. Interval labels and identity.**
- Script `notebooks/wellsight_v2/s7_analysis/_era_labels_9t.py` (proposed). Join 4.6 marks to wells by identity, then to pads and pits by the 4.6 radius. Write `lo`, `hi`, `source`, `source_date`, `identity_basis`, `pos_error_m`, `link_flag`. A well with several dated sources takes the tightest interval and keeps the others as a check column.
- Output `data/9t/results/era/era_interval_labels_9t.csv`.

**S3. Label audit.**
- Blind recheck of a probability sample of 60 labels, or all if fewer. A second person checks the source, date and link without seeing the morphology or model output. Stratify by class. Report agreement and the link-error rate with a Clopper-Pearson interval. Disagreements stay in the file with `audited = disputed` and enter a sensitivity run that drops them.
- Output `data/9t/results/era/era_label_audit_sample_9t.csv`.

**S4. Features.**
- Per well-feature pair. Pad area, perimeter, compactness, elongation, wells on pad, pit depth, rim sharpness, void fraction, road geometry and distance, local slope, and model probability. Computed from the frozen 0.5 m pipeline. Frozen list in the preregistration.
- Confound covariates kept apart. Easting and northing (smooth), distance to nearest mapped road, land cover class, distance to the oil-field boundary, lidar flight year (a sensor change could mimic era).
- Output `data/9t/results/era/era_features_pairs_9t.csv`.

**S5. Split.**
- Block folds from P1 (375 m blocks). Buffer derived as in the protocol, at least 128 m for pits and 192 m for pads, plus the correlogram range. Wells on one pad or lease are one cluster and stay in one fold. Audit blocks are excluded from training, tuning and feature selection and scored once. Split file hash recorded.

**S6. Models.**
- Script `notebooks/wellsight_v2/s7_analysis/_era_model_9t.py` (proposed). Arms.
  - M0 location only (smooth easting and northing).
  - M1 covariates only (road, cover, flight year).
  - M2 morphology only.
  - M3 morphology plus covariates.
  - Model family. Interval-censored accelerated failure time with a log-normal or Weibull link as the primary, a gradient-boosted classifier on E1 versus E3 as a secondary. Hyperparameters tuned inside training folds only. Normalisation fitted inside the fold.
- Output `data/9t/results/era/era_predictions_9t.csv` (out-of-fold only) and `era_model_summary_9t.json`.

**S7. Transportability check to the sentinel stratum.**
- Compare feature distributions of sentinel wells against dated wells per class. Compute overlap, not a domain classifier verdict (a classifier shows distinguishability only). Record whether sentinel wells fall inside the support of the training features. Outside support means predictions there are labelled "extrapolated".
- Dated wells are chosen by map visibility and record keeping, so the dated set may differ from the sentinel set in more than era. Say so in every output that predicts for U.
- Output `data/9t/results/era/era_sentinel_support_9t.csv`.

**S8. Figures.**
- `data/9t/results/era/figures/era_auc_by_arm_9t.png` (AUC with block interval per arm, blue M3, orange M0, grey M1, direct labels). `era_pred_vs_interval_9t.png` (predicted year against label interval as bars, with block-coloured markers).

## 8. Statistical analysis plan
- **Primary.** AUC of the M3 score for E1 or E2 against E3 on out-of-fold, non-audit blocks, minus the AUC of M1 (covariates only). The comparison to covariates is the claim that morphology adds beyond context. Block bootstrap, B = 2000, same blocks both arms. Decision uses superiority with threshold δ_era in AUC (proposed 0.05, user decision). Success if lower bound > δ_era. Failure if upper bound < δ_era. Inconclusive otherwise.
- **Secondary.** Spearman correlation of predicted and interval-midpoint year, E1 against E2 AUC, ordinal accuracy by class, and the exact-date subset alone.
- **Interval-censored fit.** Report concordance for interval data (Harrell-type for interval censoring) with block bootstrap. Calibration of predicted class probabilities by Brier score and expected calibration error.
- **Label noise.** Re-run with link-error rate p drawn from the S3 interval. Report the primary under the worst plausible p.
- **Sample size.** For a correlation rho, Fisher z half-width is 1.96 over sqrt(n - 3), inflated by a design effect (default 1.5 until measured, then use the measured clustering). At n = 100 and rho = 0.3 the unadjusted interval is about 0.11 to 0.47. At fewer than 15 blocks, add a permutation interval and say the bootstrap is unreliable.
- **Effective sample.** Blocks and pad clusters. Not wells on one pad.
- **Prior.** The 1956 and later weak association is a prior for the direction in M3, not a result for E1. Do not carry its correlations as expected values.
- **Multiplicity.** One primary. Everything else exploratory.

## 9. Quality control and leakage checks
1. Row counts asserted at each join, with expected and observed.
2. No placeholder or impossible date in any label. The sentinel appears only in the strata table.
3. No NaN block ids. No duplicate well ids. One well gives one row per feature pair, and pairs of one well share a fold.
4. No training window touches a held-out or audit block. Whole-window rejection tests pass.
5. Normalisation and tuning fitted in training folds only. A second run reproduces the outputs.
6. No dated mark used to place or draw a feature. Annotators did not see the historic marks while drawing. Confirm.
7. Flight year and sensor checked as a covariate so that era is not a proxy for acquisition.
8. Identity links logged with basis. Position-only links excluded from the primary.
9. Every number in a document from a saved file.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | At least 100 identity-resolved dated wells, 20 per class E1 and E2 | Proceed. Below that, run S0 to S3 and report counts only |
| Success | Primary lower bound above δ_era | Morphology carries an era signal beyond context for dated wells. Plan validation on a second tile. Still silent on sentinel wells |
| Failure | Primary upper bound below δ_era | Morphology does not add to context in the dated subset. Do not use era in 5.3 |
| Inconclusive | Interval spans δ_era | Report. State the n needed |
Margin source. The use is visit prioritisation. δ_era is the AUC gain that would change which sites a crew visits first. It is not variance or fold spread.

## 11. What a classifier can claim
- Can claim. Among independently dated wells in the study area, morphology is associated with era beyond location and land cover, with stated intervals.
- Can claim. Where sentinel wells lie inside the support of the dated wells, a predicted era with an "unvalidated for U" flag.
- Cannot claim. That a sentinel well is early. That a well is of a given date. That map absence implies later construction. That the result holds in another county. That a feature is a well.
- Every output file carries `evidence_level = a` and `era_basis = interval` or `predicted_unvalidated`.

## 12. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\era_label_audit.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\era_classification_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\era_classification_prereg.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\_era_label_audit_9t.py`, `_era_labels_9t.py`, `_era_model_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\era\` (CSV, JSON, `figures\`)

## 13. Failure modes
| Risk | Mitigation |
|---|---|
| Too few dated early wells | Gate in section 10. Report counts. Pool E1 and E2 only with a preregistered rule |
| Era confounded with land use, location or flight year | M0 and M1 arms. Report morphology over context |
| Pad reuse mislabels era | Identity basis and flag. Drop position-only links from the primary |
| Dated set biased by map visibility | S7 support check. Label predictions for U as unvalidated |
| Interval-censored fit unstable | Fall back to the E1-versus-E3 classifier. Say which was run |
| Historical mark linked to the wrong well | S3 blind audit and p sensitivity |
| Sentinel misread as early | Strata column. Tests that fail if any model input contains the sentinel |

## 14. Resources
S0 to S3 about 12 hours. S4 to S8 about 20 hours. CPU only. Audit about 4 reviewer-hours. Calendar dependency is 4.6 delivery.

## 15. Handoff and open questions
- Class boundaries and δ_era.
- Whether cross-region records are used.
- Confirm DEP date field meanings.
- Stop if the dated subset is below the readiness gate.

## 16. Documentation updates
`era_label_audit.md`, `era_classification_9t.md`, `analysis_log.md`, LEADERBOARD (any model result), master plan, BACKLOG, `literature/CITATIONS.md` for the censored-survival method.

## Review revision 2 (third review, 2026-11-04)
Sentinel dates and historical absence are not era labels. Build a small identity-resolved dated subset through 4.6.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
