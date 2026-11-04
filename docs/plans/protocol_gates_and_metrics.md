# Authoritative protocol, gates and metrics

**Date:** 2026-11-04
**Status:** authoritative. Where this file disagrees with `README.md`, an individual plan, `docs/iterations/expansion_options_methods.md` or `docs/iterations/expansion_gameplan_feasibility.md`, this file wins. Built from two adversarial reviews (`adversarial_codex_review_20261104.md`, `adversarial_review_claude.md`) after each finding was checked. See `review_response_20261104.md` for what was accepted, narrowed or rejected.

Nothing here has been run. Items marked **user decision** block the preregistration of the experiment they name and nothing else.

## 1. What the plans can and cannot show
Most plans produce evidence about drawn terrain features. Whether a drawn feature is a well is the unknown that sets the project's value.
- On 9t, 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m (`docs/iterations/LEADERBOARD.md`, line 491).
- Any result at evidence level (a) is silent on wells. Only levels (b) historical, (c) steel and (d) confirmed can speak to wells.
- The first scientific question is therefore what share of drawn features are wells, by morphology and era. Section 6 designs that study.

## 2. Review budget K and the transfer metric
**Problem found.** K was defined two ways. The Warren draft used the count of annotated features. The operating-point work uses candidates per km². The 9t reference of 0.928 is a cutoff-based recall, not recall at fixed K.

**Rules**
1. **Primary metric.** Recall of annotated features at a fixed review budget of K candidates per km² of scored eligible area. Same code, same proposal extraction, same tie handling and same model policy on the 9t out-of-fold raster and on the target.
2. **Reference.** 9t recall at that same K, computed from `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` (pad equivalent to be located). It is deterministic. Do not use 0.928.
3. **Report target density.** Features per km² in the 9t reference blocks and in the target blocks. Recall at a per-km² budget moves with density alone.
4. **Secondary metric.** Recall at K scaled to target density, K = c times density, with c fixed from 9t before scoring. It separates density from ranking quality.
5. **Complete blocks.** Score against blocks annotated in full, including blocks that hold no features. Annotation completeness is checked by a second pass on a random subset.
6. **Agency records** are scored in the separate association analysis (section 4). Plan 3.0 scores against drawn polygons only.
7. **K policy. Decided 2026-11-04: 40 candidates per km².** `docs/iterations/operating_point_policy_plan.md` recommends the review budget. The 9t sweep gives 0.781 at 30 per km² (0.739 to 0.822, fold range 0.723 to 0.900) and 0.909 at 40 (0.881 to 0.935). Recall is steep in K there, so the chosen K sets how sensitive a transfer test is to density. The primary K is 40 per km², chosen by the user (the default). State it in every preregistration. 30 may be reported as a sensitivity only.

## 3. Splits, leakage and what is auditable
**Facts checked**
- Held-out folds are deterministic and valid. The fold assignment groups on block id and drops NaN.
- The inner validation and training blocks are not reproducible. `sorted(set(block_ids) - held)` places the NaN block (the 209 pit rows and 345 pad rows with no block id) at a position that changes between processes. In four fresh Python 3.13 processes the inner validation list differed in folds 0, 2 and 4. The logged runs cannot be reconstructed from the code.
- `_save_cv_split_manifests_9t.py` drops NaN before shuffling. Its saved train and validation roles do not match the trained models. Only its held-out lists are valid.
- The original sampler (`notebooks/wellsight_v2/_dl.py`, lines 249 to 275) draws a centre inside a training block and then reads a full window clipped only to the raster. A window can reach held-out ground. The trainer comment that `block_bounds` prevents this is wrong.
- The isolated pad trainer `_pad_unet_iso_cv5.py` fixes this for pads. It rejects any window that touches a held-out or inner-validation block (`docs/iterations/nisar_checks_9t.md`, section 7). There is no isolated pit trainer.
- The trainers compute 14 normalisation numbers once over the original training blocks and reuse them for every fold. This leaks into each fold (trainer docstring).
- The 209 and 345 rows with no block id are annotations off the tile, not unscored in-tile features (`LEADERBOARD.md`, line 303).

**Rules**
1. Label every split one of historical held-out (valid), historical inner (unrecoverable) or future (immutable, saved before training).
2. Every 9t block was in the training or validation set of four of the five CV models. There is no untouched 9t block. Audit blocks on 9t support comparative tests between new models only. Absolute final claims need a new area.
3. Any new training code rejects whole windows that intersect held-out ground, fits normalisation inside the fold, and reads splits from a saved file. Stale caches are invalidated when the model, data or split hash changes.
4. Buffer width is derived, not fixed. It covers receptive field and patch support (pit 128 m, pad 192 m or 384 px as used) plus the range of an empirical correlogram of 9t out-of-fold residuals. A fixed 500 m has no stated basis and does not remove landscape dependence. Pits on one pad or lease are one effective cluster.
5. Preprocessing is frozen at 0.5 m, the resolution the models read (`features_pit_9t_05.tif`). At 0.5 m, 45.2% of 9t cells hold no ground return (`BACKLOG.md`). Warren derivatives on disk are 1 m from another pipeline. Rebuild at 0.5 m with the 9t code. Report void fraction per block. Thin to 9t ground density first, then grid at 0.5 m.
6. QL2 is a nominal aggregate pulse density. Measure ground density per block. A threshold of two ground points per m² is a chosen eligibility rule, not the QL2 definition, and needs a stated reason.

## 4. Record association and recall-gap rules
**Withdrawn.** The first association run and the recall-gap run (`record_assoc_pits_9t.md`, `recall_gap_newly_documented_9t.md`) are withdrawn as evidence.
- The loader drops every row with `dup_on_pit = 1`. All 481 matched pit detections carry that flag, so only the 204 unmatched leftovers were used.
- The pad file is the unmatched leftover from the matching step, not the full output.
- The one-to-one proposals are not global. There are 197 rows and 153 unique detection coordinates.
- The pit footprint (115 blocks) was reused for pads (129 blocks).
The question is open and the result can move either way.

**Rules for the corrected analysis**
1. **Input contract.** Full detector output at the frozen cutoff, matched and unmatched, with one deployment-compatible deduplication rule. State the row counts. Run a second analysis on novel candidates only and label it so.
2. **Footprints.** Use each modality's own footprint, or a declared intersection. Identical eligibility and edge rules for observed and null.
3. **Assignment.** Assign globally across statuses, or label per-status outputs as competing proposals.
4. **Null.** Translate the whole record set as one. Keep the count and composition of records fixed by rejecting shifts that lose records, or report each shift's retained count. A null that translates clustered records does not establish exchangeability across spatial gradients in oil development. State what it conditions on.
5. **Statistics.** Primary radius fixed before analysis (pits 50 m, pads inside the polygon). Report excess over the null and the predictive value 1 minus null over observed, with an interval. The pre-fixed 50 m rate for active records (0.111 against 0.090) was also inside the null in the withdrawn run, so there is no working positive control for pits yet.
6. **Positive control.** Active wells at pad level. The user reports (2026-11-04) that annotators did not have DEP well points visible while drawing, so association with annotations is not circular by that route. Other context the annotators saw is unrecorded. Keep that caveat.
7. **Cohorts.** Newly documented wells (1,316 over 2022 to 2026) may carry better coordinates than 1800-sentinel records. Use excess over a cohort-specific null and stratify by coordinate source once DEP answers. 997 of 1,079 orphan-list spud dates are the 1800 sentinel.
8. **Validation** needs independent coordinates (GNSS, NETL). Proximity excess alone never passes coordinate correction.

## 5. Gates
Every comparison uses a 95% block-bootstrap interval for the difference and a margin Δ fixed in the preregistration. Success means the interval clears the bar. Failure means it lies wholly past it. Anything else is inconclusive, reported as such, never as no effect. A readiness gate (data present, protocol written) is not a scientific gate.

The effective sample is blocks, sites or pads. Detections, repeated model seeds, site-seasons and extra bootstrap draws are not independent landscapes.

| Experiment | Readiness gate | Primary statistic | Success | Failure | Δ comes from |
|---|---|---|---|---|---|
| P1 split repair | Software only | Block lists identical across 3 fresh processes | Identical in all folds | Any difference | None |
| 3.0 protocol check | Deterministic reference raster present | Recall at policy K reproduced from the saved raster against the operating-point sweep | Matches the sweep exactly | Any mismatch | None |
| 3.1 Warren transfer | Complete blind labels, projected interval width at most 2Δ, derived buffer, 0.5 m rebuild | Recall difference at policy K with target density reported. Secondary at density-scaled K | Lower bound above minus Δ | Upper bound below minus Δ | Tolerable missed-feature burden, floored by 9t fold spread at that K |
| 3.3 slope context | 9t out-of-fold recall by slope tercile exists | Recall by slope tercile. Paired score and rank change for edits on real low-relief backgrounds | Lowest tercile lower bound above top tercile minus Δ | Upper bound below it | Loss that would change the decision to try a flat county |
| 4.5 change at plugging | Flight-date bounds, dated eligible wells, adequate spatial support | Flag rate at eligible pads minus the rate at eligible pads without the intervention, plus a recovery test through the whole processing chain | Lower bound above 0 and n meets the prereg minimum | Upper bound below the smallest change worth detecting | The detectable floor (0.16 to 0.22 m mean on slopes under 15 degrees) |
| 4.6 historic source | Source dates, scale and coverage listed | Georeferencing RMSE on held-out control points, two-digitiser agreement on symbols, excess over an in-oil-field shifted null | RMSE under the limit and excess lower bound above 0 | RMSE over the limit, or no interpretable symbols on several dates | The RMSE at which chance matching stays under a stated share |
| 4.7 drone density | Dataset identity and site selection verified | Recall versus thinned ground density, same sites. A curve, not a gate | None | None | None. Label it conditional on selection by lidar visibility |
| 5.6 association | Section 4 contract met, independent coordinates held | Excess and predictive value per group. Position error before and after on independent points | Positive control excess lower bound above 0 and the target group's predictive-value lower bound above the field-use minimum | Positive control passes and the target group's upper bound is below the minimum | Wasted visits a crew accepts |
| A6 recall gap | Corrected input, coordinate provenance known | Difference in excess over cohort-specific nulls, stratified by coordinate source | Lower bound above minus Δ | Upper bound below minus Δ | The gap that would change a density estimate by a stated factor |
| 6.3 confusers | P1, P2, reviewer pair | Difference in labelled-confuser detections per km² at policy K between the confuser arm and a matched random-negative arm, plus change in drawn-feature recall, pooled blind labels, at least 3 seeds each | Reduction lower bound above 0 and recall-loss lower bound above minus Δ | Reduction upper bound below 0, or recall-loss upper bound below minus Δ | Acceptable feature-recall loss against seed spread |
| 5.1 context | One shared fold scheme, leakage audit passed | Ranking gain at policy K with nested spatial folds | Gain lower bound above 0 | Upper bound below the useful gain | Smallest gain worth the cost |
| 4.1 magnetometry pilot | Instrument QC, controls | Anomaly present or absent per site by era stratum | Not a gate at 3 to 5 sites | Not a gate | Population sensitivity needs section 6 |
| 7.5 campaign | Partner, frame, blinding | Stratum-weighted share with outcome (d), (c) or unresolved, with bounds for unresolved | Bound width at or under the target | Not applicable | Precision the decision needs |
| 4.2, 4.3 thermal, vegetation | Observability gate in section 9 | Contrast against a predefined useful contrast | Detect it | Exclude it | A physically meaningful contrast |
| 5.4 density | Distinct-well accounting | Conditional bounds and sensitivity | Not a gate | Not a gate | If recall can approach zero a finite upper bound may not exist |
| 7.1, 7.2 | Independent final area, validation-only stopping | Improvement per stated resource | See section 12 | See section 12 | Stated before the run |

## 6. Field campaign and magnetometry design
- **Three arms.** (A) A probability sample of drawn features, to measure what share are wells. (B) A score-stratified sample of model candidates, to measure precision. (C) Probability-sampled areas searched independently, to bound missed wells. Candidate verification alone cannot give recall.
- **Outcomes.** Confirmed well (d). Steel anomaly only (c). Nothing found. Unresolved. Inaccessible. Keep every access failure.
- **Bounds.** Report the share with unresolved counted as non-wells and again as wells. If search sensitivity cannot be bounded by repeated independent searches or complementary evidence, report conditional recall only.
- **Casing.** Magnetometry needs intact steel casing. NETL states that wells with wooden or removed casing are invisible to it (`https://netl.doe.gov/node/9506`). A review cites Hammack et al. (2023) for missed 1860 to 1880 wells in forested Pennsylvania. That citation is reported, not yet read.
- **Era strata.** Report P(anomaly) separately for documented steel-era wells, early-era wells (1800 sentinel, or on a dated historic map), pits with no record, metal confusers and blank controls. Never pool. Add non-magnetic evidence for the early stratum, such as cellar walls, wood casing remnants, cable-tool debris and historic map position.
- **Sample size.** n equals 1.96 squared times 0.25 over d squared per estimate under simple random sampling. About 43 sites gives plus or minus 15 points, 96 gives 10 and 24 gives 20. Forty sites in total cannot give plus or minus 15 in each of five score bins. Clustering, weighting and inaccessible sites widen intervals.
- **Pilot scope.** Three to five sites test practicality. They do not measure sensitivity.
- **Wells with no casing and no surface expression** stay unreachable. A narrow interval around a model estimate does not cover them.

## 7. Confuser experiment (6.3)
1. Define the target morphology independent of model score. The codebook's positive class uses access traces and oil-field setting, which context features can also learn. Keep "possible well" and "uncertain".
2. Three arms on the same non-audit blocks. Baseline, confuser negatives, and an equal-count random-negative arm. At least 3 seeds per arm.
3. Pool the top-K detections of every arm in the audit blocks, deduplicate, label once blind to arm, then score each arm on the pooled labels.
4. Track how many "possible well" and "uncertain" detections each arm suppresses. A class such as charcoal hearth may hold early well platforms.
5. Pilot the codebook first. Measure real review throughput and ambiguity before sizing. The 30 reviewer-hours figure is an estimate.

## 8. Context stacking (5.1)
Assign one block-fold scheme to pit, pad and road. Every upstream model that feeds outer fold k must have excluded fold k, for both second-stage training and test inputs. Pit and pad folds are balanced on different counts today, so the current checkpoints cannot be stacked. Retrain upstream pad and road models on the shared scheme. Budget runtime from measured epoch time (`BACKLOG.md` notes epoch time was under-reported by 1.8 times). Annotation context bias is separate. Context features can raise agreement with how annotators searched without raising well discovery.

## 9. Observability gate for new modalities
Before any statistical test quantify
- the fraction of the pixel or footprint the target fills
- usable acquisitions and their dates
- the effective spatial support (Landsat TIRS is 100 m native and resampled to 30 m, ECOSTRESS about 70 m, per the NASA and LP DAAC specifications cited by the review, not yet read)
- registration uncertainty
- the plausible signal relative to variability

A smaller delivered pixel is not more target information.
- **Thermal and vegetation.** Covariate adjustment does not establish leakage. Without independent leak labels the result is a difference in surface conditions. A satellite null excludes only a specified contrast. It cannot exclude a finer drone signal.
- **Methane.** Kang et al. (2014) measured 19 abandoned Pennsylvania wells (42 measurements), mean about 0.27 kg per day per well, with 3 of 19 high emitters (checked at the Princeton record). The review states a Tanager 90% detection probability of 90 to 180 kg per hour. That figure is not yet checked. If it holds, the gap is about four orders of magnitude for the mean well. Check the product guide before closing 4.4 for Pennsylvania. Observation counts do not remove selection toward known emitters. A plume footprint is not a source-location uncertainty region.
- **Alaska.** Specify line-of-sight displacement, reference stability and seasonal and hydrology confounding first.

## 10. Historical evidence (4.6, 5.2)
- A source verdict is usable here, unusable here or inconclusive, per source and date. One failed sheet is not a verdict. The 1922 Oil City sheet showed no well symbols in the mapped part.
- Probe higher-yield sources first. 1870s and 1880s Second Geological Survey oil-region maps, 1860s oil-region atlases, and 1937 to 1942 aerials. Existence and coverage over 9t are **unverified**.
- The null is the shifted-set null inside the oil field. Slope-matched random forest points sit outside oil fields and pass trivially.
- Historical positives are kept when the lidar score is low. Judge labels by interpretability and positional accuracy.
- Historical presence bounds construction date from above. Absence is censored, not evidence of a later date. Pads are reused, so link by identity, not by position alone.

## 11. Multitemporal change (4.5)
- Controls are eligible pads without the intervention, matched on baseline terrain and disturbance opportunity. The existing controls exclude mapped pads, pits and roads and match slope, so they are ordinary terrain, not exchangeable with plug-eligible sites.
- Distinguish plugging from surface restoration. Prefer independently dated earthwork.
- The 3,368 m² patch threshold belongs to one spatial-null procedure. It is not a physical floor. High-pass processing changes which scales remain measurable. Test signal recovery through the whole chain at relevant sizes, slopes and seam locations.
- The saved v2 result is 19 of 404 flagged pads against about 15.3 expected by placebo. That is not evidence of absence. No detectable change is distinct from no restoration or no plugging.
- Flight dates first. File creation dates are not flight dates.

## 12. Density, pretraining, active learning
- **Density.** The estimate is D times p over r only when D p counts distinct true wells in the candidate population, r concerns the same eligible population, multi-feature and multi-well relations are resolved, and documentation and acquisition scope align. Until then publish sensitivity and bounds. Withdraw reliance on the recall-gap result.
- **Pretraining.** State the comparison. Benefit at a fixed annotation budget, at a fixed total compute budget, or after counting pretraining cost. These are three different questions.
- **Active learning.** Candidate-only sampling cannot find positives absent from the proposal pool. Include random-area discovery. Keep a stopping set separate from the final audit set. The final audit set is checked once.

## 13. Resource accounting
Report inventory time, annotation labour, machine runtime and calendar dependencies separately. The A0 to A9 sum is about 49 hours before debugging, which is over six eight-hour days. Benchmark one real block of annotation and one real inference run before extrapolating. A county is not 20 GB. Estimate from real tile sizes with decompressed clouds, derivative stacks and checkpoints. The Warren tiles are 312 MB compressed and 2.8 GB with the merged LAS. Independent work (historical coverage, instrument planning, date bounds) does not wait for label review.

## 14. Reproducibility
Pin the interpreter and package versions in a lock file. Plain `python` with a user-site install is not a reproducibility guarantee, and `python -I` breaks here for that reason. Hash inputs and checkpoints. Record the commit. Keep a split file, not a seed, as the source of truth.

## 15. Superseded text
In `docs/iterations/expansion_gameplan_feasibility.md`, the gate table, A2 gate, A3 half-score rule, B7 density surface, recall-gap gate (overlap of intervals), historic-only gate (matched random points) and the A1 audit draw of about 20% of scored blocks are superseded by sections 3 to 5 and 10 to 12 here. In `docs/iterations/expansion_options_methods.md`, the between-state variance from one county per state, the claim that a domain classifier can attribute transfer failure, historical absence as an era target, "plan on 40 sites per estimate" and the use of "different lidar programs" for Warren are superseded. A domain classifier shows distinguishability under its features. It does not identify the cause of failure.
