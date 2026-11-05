# Authoritative protocol, gates and metrics

**Date:** 2026-11-04
**Status:** authoritative. Where this file disagrees with `README.md`, an individual plan, `docs/iterations/expansion_options_methods.md` or `docs/iterations/expansion_gameplan_feasibility.md`, this file wins. Built from two adversarial reviews (`adversarial_codex_review_20261104.md`, `adversarial_review_claude.md`) after each finding was checked. See `review_response_20261104.md` for what was accepted, narrowed or rejected. A third review (`adversarial_codex_review_revised_20261104.md`) was checked the same day. Its dispositions are in section 16 and in `review_response_20261104.md` section 8. The affected rules below were edited in place.

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
2. **Reference.** Two separate references. (a) Archival. The historical sweep, rebuilt from its own fold object tables, cutoffs, fold areas and tie rules (`notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py`, lines 99 to 144). That script fits the cutoff and calibrator on the other four folds and floors the budget on each fold's own area. (b) New baseline. One declared deployment policy (one model or an ensemble) applied identically to isolated, fold-local-normalised 9t out-of-fold predictions and to the target. The saved mosaic `pit_prob_floor_outoffold_9t_05.tif` is uint8 (probability = DN / 254, 255 is nodata). Quantisation changes scores and ties, and polygonising across fold seams differs from the per-fold tables. It is not an exact record of the original scores. Do not use 0.928. The old 9t estimate is a historical diagnostic, not an unbiased new baseline.
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
5. Preprocessing is frozen at 0.5 m, the resolution the models read (`features_pit_9t_05.tif`). At 0.5 m, 45.2% of 9t cells hold no ground return (`BACKLOG.md`). Warren derivatives on disk are 1 m from another pipeline. Rebuild at 0.5 m with the 9t code. Report void fraction per block. The primary transfer test uses native target data through the frozen 0.5 m pipeline. Paired downward-thinning arms are a separate sensitivity analysis. Thinning cannot add information. Matching a mean density does not reproduce canopy holes, scan geometry or classification error.
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
5. **Statistics.** Primary radius fixed before analysis (pits 50 m, pads inside the polygon). Report normalised excess association over the null, with an interval. It is not link precision. The ratio 1 minus null over observed is not predictive value and is not used as one. Shifted records can overlap features even when every observed link is right. Link PPV needs blinded identity adjudication of a probability sample of accepted links, with ambiguous outcomes kept and inclusion weights. The pre-fixed 50 m rate for active records (0.111 against 0.090) was also inside the null in the withdrawn run, so there is no working positive control for pits yet.
6. **Positive control.** Active wells at pad level. The user reports (2026-11-04) that annotators did not have DEP well points visible while drawing, so association with annotations is not circular by that route. Other context the annotators saw is unrecorded. Keep that caveat.
7. **Cohorts.** Newly documented wells (1,316 over 2022 to 2026) may carry better coordinates than 1800-sentinel records. Use excess over a cohort-specific null and stratify by coordinate source once DEP answers. 997 of 1,079 orphan-list spud dates are the 1800 sentinel.
8. **Validation** needs independent coordinates (GNSS, NETL). Proximity excess alone never passes coordinate correction.

## 5. Gates
Every block-sampled comparison uses a 95% block-bootstrap interval for the difference and a margin fixed in the preregistration. **One threshold, in the statistic's own units, serves both success and failure.** Success means the lower bound clears it. Failure means the upper bound lies below it. The band between is inconclusive, reported as such, never as no effect. Margins come from the burden tradeoff (missed features at K, wasted visits, decision value). They never come from variance or fold spread, because more noise must not relax a requirement. Variance sets sample size. A weighted field sample or one with few independent clusters needs inference matched to its design, not a universal block bootstrap. A readiness gate (data present, protocol written) is not a scientific gate.

The effective sample is blocks, sites or pads. Detections, repeated model seeds, site-seasons and extra bootstrap draws are not independent landscapes.

| Experiment | Readiness gate | Primary statistic | Success | Failure | Δ comes from |
|---|---|---|---|---|---|
| P1 split repair | Software only | Block lists identical across 3 fresh processes, whole-window exclusion test, and every fitted preprocessing object traced to training blocks | Identical in all folds and both tests pass | Any difference or failure | None. Identical lists alone do not certify no leakage |
| 3.0 protocol check | Archival tables present (fold object tables, cutoffs, fold areas) | Two checks. Archival. Rebuild the historical statistic from its own tables. New baseline. Frozen policy on isolated out-of-fold predictions, computed twice from a clean state | Archival matches with every discrepancy explained. New baseline repeats exactly | Unexplained archival mismatch, or the baseline differs between runs | None. Neither check is a transfer success |
| 3.1 Warren transfer | Complete blind labels, projected interval width at most 2Δ, derived buffer, 0.5 m rebuild | Recall difference at policy K with target density reported. Secondary at density-scaled K | Lower bound above minus Δ | Upper bound below minus Δ | Tolerable missed-feature burden at K, stated in the preregistration. Not fold spread. Interval width forecast over plausible target densities and clustering, with reference uncertainty |
| 3.3 slope context | 9t out-of-fold recall by slope tercile exists | Recall by slope tercile, with feature counts and independent clusters (an association, not slope causation). Paired score and rank change for edits on real low-relief backgrounds | Lowest tercile lower bound above top tercile minus Δ | Upper bound below it | Loss that would change the decision to try a flat county |
| 4.5 change at plugging | Flight-date bounds, dated eligible wells, adequate spatial support, and a passed recovery test of a specified physical change through the whole chain | Flag rate at eligible pads minus the rate at eligible pads without the intervention | Lower bound above the useful rate difference δ_rate and n meets the prereg minimum | Upper bound below δ_rate | δ_rate comes from the decision the flag changes. The 0.16 to 0.22 m height floor is a separate measurement specification in metres. It is not a rate threshold |
| 4.6 historic source | Source dates, scale and coverage listed | Per source and date. Provenance, legibility, coverage, two-digitiser agreement and total positional uncertainty (registration plus symbol placement plus borehole offset) | Meets the stated use. Individual matching or regional presence only | Unusable for that use, or no interpretable symbols on several dates | The positional error at which the intended matching stays useful. Agreement with lidar or DEP is a separate later outcome and never decides readiness |
| 4.7 drone density | Dataset identity and site selection verified | Recall versus thinned ground density, same sites. A curve, not a gate | None | None | None. Label it conditional on selection by lidar visibility |
| 5.6 association | Section 4 contract met | Exploratory. Normalised excess association per group. Deployment. Adjudicated link PPV with unresolved bounds. Coordinate correction. Paired position error before and after on independently surveyed identities | Exploratory. Excess lower bound above 0. Deployment. PPV lower bound above the crew minimum | Deployment. PPV upper bound below the minimum | Wasted visits a crew accepts. A pad-level positive control does not validate a different cohort |
| A6 cohort association | Corrected input, coordinate provenance known | Difference in normalised excess over cohort-specific nulls, stratified by coordinate source | Descriptive only | Descriptive only | No recall-equivalence gate. A recall margin needs independently verified denominators, coordinate error and eligibility. Spatial excess alone does not identify detection sensitivity |
| 6.3 confusers (prespecify both benefits) | P1, P2, reviewer pair | Difference in labelled-confuser detections per km² at policy K between the confuser arm and a matched random-negative arm, plus change in drawn-feature recall, pooled blind labels, at least 3 seeds each | Reduction lower bound above 0 and recall-loss lower bound above minus Δ | Reduction upper bound below 0, or recall-loss upper bound below minus Δ | The useful confuser reduction and the acceptable feature-recall loss, both stated before the run. Seed spread is not a margin. Adjudicate the union of each arm's top-K |
| 5.1 context | One shared fold scheme, leakage audit passed | Ranking gain at policy K with nested spatial folds | Gain lower bound above the useful gain δ_gain | Upper bound below δ_gain | δ_gain from the downstream value and cost. A positive gain below it is real but does not justify deployment |
| 4.1 magnetometry pilot | Instrument QC, controls | Anomaly present or absent per site by era stratum | Not a gate at 3 to 5 sites | Not a gate | Population sensitivity needs section 6 |
| 7.5 campaign | Partner, frame, blinding, inclusion weights per arm | Weighted share by identity status (section 6) with bounds that include every ambiguous or inaccessible case, plus sampling uncertainty | Bound width at or under the target | A negative result is allowed. For example a candidate class whose confirmed-well share is too low to justify deployment | Precision the decision needs. A wide unresolved remainder is inconclusive, not negative |
| 4.2, 4.3 thermal, vegetation | Observability gate in section 9 | Contrast against a predefined useful contrast | Detect it | Exclude it | A physically meaningful contrast |
| 5.4 density | Distinct-well accounting | Conditional bounds and sensitivity | Not a gate | Not a gate | If recall can approach zero a finite upper bound may not exist |
| 7.1, 7.2 | Independent final area, validation-only stopping | Improvement per stated resource | See section 12 | See section 12 | Stated before the run |

## 6. Field campaign and magnetometry design
- **Three arms.** (A) A probability sample of drawn features, to measure what share are wells. (B) A score-stratified sample of model candidates, to measure precision. (C) Probability-sampled areas searched independently, to bound missed wells. Candidate verification alone cannot give recall.
- **Outcomes.** Confirmed well (d). Steel anomaly only (c). Nothing found. Unresolved. Inaccessible. Keep every access failure.
- **Identity status.** Record it separately from the outcome. Each sampled site is confirmed well, definite non-well or ambiguous. Steel alone is not identity. A negative search of unknown sensitivity is not a definite non-well. An inaccessible sampled site stays in the frame as ambiguous.
- **Bounds.** With known sampling weights, the lower bound is confirmed-well weight over total sampled weight. The upper bound is one minus definite-non-well weight over total sampled weight. Every ambiguous and inaccessible case sits in the gap. Add sampling uncertainty around both bounds. If search sensitivity cannot be bounded by repeated independent searches or complementary evidence, report conditional recall only.
- **Casing.** Magnetometry detects ferromagnetic material of any kind. Casing remnants and other oil-field metal both give anomalies, so an anomaly is not a well. Wood has no magnetic signature. NETL states that wells with wooden or removed casing are invisible to it (`https://netl.doe.gov/node/9506`). A review cites Hammack et al. (2023) for missed 1860 to 1880 wells in forested Pennsylvania. That citation is reported, not yet read.
- **Era strata.** Report P(anomaly) separately for documented steel-era wells, early-era wells (independently dated, for example on a historic map), unknown-date wells (the 1800 sentinel, its own stratum and never counted as early era), pits with no record, metal confusers and blank controls. Never pool. Add non-magnetic evidence for the early stratum, such as cellar walls, wood casing remnants, cable-tool debris and historic map position.
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
- **Methane.** Kang et al. (2014) measured 19 abandoned Pennsylvania wells (42 measurements), mean about 0.27 kg per day per well, with 3 of 19 high emitters (checked at the Princeton record). Carbon Mapper lists a Tanager 90% detection probability of 90 to 180 kg per hour at 3 m/s wind, 35 degree solar zenith, 25% albedo and 30 m GSD (checked 2026-11-04 at carbonmapper.org). The mean well is about 0.011 kg per hour, so the gap is about four orders of magnitude. That closes routine satellite screening of individual small wells under those conditions. It does not bound rare large emitters or aggregation. Observation counts do not remove selection toward known emitters. A plume footprint is not a source-location uncertainty region.
- **Alaska.** Specify line-of-sight displacement, reference stability and seasonal and hydrology confounding first.

## 10. Historical evidence (4.6, 5.2)
- A source verdict is usable here, unusable here or inconclusive, per source and date. One failed sheet is not a verdict. The 1922 Oil City sheet showed no well symbols in the mapped part.
- Probe higher-yield sources first. 1870s and 1880s Second Geological Survey oil-region maps, 1860s oil-region atlases, and 1937 to 1942 aerials. Existence and coverage over 9t are **unverified**.
- Source readiness rests on provenance, dates, legibility, coverage and independently measured positional uncertainty. It never rests on agreement with lidar detections or DEP records. A valid source that finds omitted wells must not fail. Association with lidar or records is a later, separate outcome.
- For that association the null is the shifted-set null inside the oil field. Slope-matched random forest points sit outside oil fields and pass trivially. A poor source can be unusable for matching individual wells and still useful for regional presence.
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
Report inventory time, annotation labour, machine runtime and calendar dependencies separately. The A0 to A9 sum is about 49 hours before debugging, which is over six eight-hour days. Benchmark one real block of annotation and one real inference run before extrapolating. A county is not 20 GB. Estimate from real tile sizes with decompressed clouds, derivative stacks and checkpoints. The Warren tiles are 312 MB compressed and 2.8 GB with the merged LAS. Independent work (historical coverage, instrument planning, date bounds) does not wait for label review. Lidar catalogue totals are discovery estimates. Tile-count ratios do not measure area covered. Verify union coverage of the window from tile geometries before any total becomes a budget (section 16 item 5).

## 14. Reproducibility
Pin the interpreter and package versions in a lock file. Plain `python` with a user-site install is not a reproducibility guarantee, and `python -I` breaks here for that reason. Hash inputs and checkpoints. Record the commit. Keep a split file, not a seed, as the source of truth.

## 15. Superseded text
In `docs/iterations/expansion_gameplan_feasibility.md`, the gate table, A2 gate, A3 half-score rule, B7 density surface, recall-gap gate (overlap of intervals), historic-only gate (matched random points) and the A1 audit draw of about 20% of scored blocks are superseded by sections 3 to 5 and 10 to 12 here. In `docs/iterations/expansion_options_methods.md`, the between-state variance from one county per state, the claim that a domain classifier can attribute transfer failure, historical absence as an era target, "plan on 40 sites per estimate" and the use of "different lidar programs" for Warren are superseded. A domain classifier shows distinguishability under its features. It does not identify the cause of failure. From the third review. The `1 - null / observed` predictive value, exact reproduction of the sweep from the saved mosaic, margins floored by fold spread, the 4.5 metre-based rate gate, the 1800 sentinel as early era, the 4.6 shifted-null excess as a source gate, and thinning to 9t density as the primary arm are superseded.

## 16. Third review, 2026-11-04 (dispositions)
Source. `docs/plans/adversarial_codex_review_revised_20261104.md`. Checked against the repo before use. Full table in `review_response_20261104.md` section 8.
1. **Excess is not PPV.** Accepted. Section 4 rule 5 and the 5.6 and A6 gate rows were rewritten. 5.4 stays conditional bounds only.
2. **Reproduction versus a clean baseline.** Accepted. The sweep fits per fold and floors the budget per fold area (verified). The saved mosaic is uint8 with DN / 254 (verified). Section 2 rule 2 and the 3.0 row split archival from new baseline.
3. **Gates.** Accepted. 5.1 and 4.5 had overlapping success and failure rules (verified). 4.5 mixed a rate with a height in metres (verified). Margins no longer come from fold spread. The shared rule in section 5 now holds one threshold.
4. **Field ambiguity and the 1800 sentinel.** Accepted. Section 6 has an identity status and weighted bounds. Unknown dates are their own stratum.
5. **Lidar coverage.** Accepted. The Jackson, Missouri row shows 16 tiles at cover 0.44 against 36 tiles at 1.00 for a 2006 project. The Pleasants row compares 19 Ohio-project tiles with 38 West Virginia tiles (both verified in the summary CSV). The listing script asks for at most 200 results without pagination, turns repeated failure into an empty result, and drops duplicate URLs across windows (verified). The catalogue is discovery only. Required repairs are in `docs/iterations/BACKLOG.md`. Not checked here. The claim that the county script samples five small locations.
6. **Circular source acceptance.** Accepted. The 4.6 row and section 10 separate readiness from association.
7. **Thinning.** Accepted. Native data is primary. Thinning is a paired sensitivity arm. McKean is a joint geography and acquisition contrast.
8. **Methane.** Accepted. The threshold is now checked. The closure covers ordinary small wells only.
9. **Administrative.** Accepted. D2 now depends on R1. R4 and R5 are marked answered. The 5.6 plan no longer asks R4.
