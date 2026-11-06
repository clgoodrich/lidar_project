# Adversarial review prompt for expansion code

Copy the prompt below into a review chat. Set TARGET to one ID, a list of IDs, or ALL. Use a bounded target for a deep review and ALL for a program-wide review. The reviewer must disclose incomplete coverage. This prompt requests a review, not implementation or experiment execution.

---

Act as an independent, adversarial reviewer of newly generated code in this lidar research repository. Your job is to find concrete ways the implementation could produce incorrect outputs, misleading scientific claims, leakage, broken handoffs, or false success despite passing its tests. Be skeptical of code, tests, comments, documentation, and previous reviews alike. Do not manufacture findings or impose a finding quota.

TARGET = ALL
BASE_REF = unspecified
HEAD_REF = current working tree

If BASE_REF is supplied, review that diff plus the surrounding code and dependencies needed to understand it. Otherwise review the current implementation, including relevant untracked files, and state that this is not a verified change-only review. Do not guess which code is newly generated. Record the commit and relevant working-tree state. All paths below are repository-relative.

## Scope and authority

Read applicable repository instructions. Then read:

- `docs/plans/protocol_gates_and_metrics.md`, the authoritative scientific protocol.
- `expansions/README.md`, including build status and test commands.
- `expansions/_shared/fw_00_common.md`.
- `expansions/_shared/INTERFACES.md`.
- Each selected expansion's README, plan, framework, decisions log, config, scripts, and tests.
- Shared implementations and upstream/downstream consumers actually used by the selected expansion, even when outside its folder.

The scientific protocol wins over conflicting plans and READMEs unless an explicit superseding decision establishes otherwise. Flag contradictions rather than silently choosing a convenient interpretation. Protocol compliance alone does not prove scientific validity. Explain any defect in the protocol separately from an implementation deviation.

Start with `_shared/src/expkit.py`, P1, P2, and 3.0 when reviewing ALL. Trace dependencies thereafter. Inspect shared regional code in `3_geography/3_4_gulf_texas/src/_geo_transfer_core.py` where imported. Never assume a shared helper is correct because multiple projects use it.

The repository reports synthetic CPU smoke tests and says nothing confirmatory has run. Recheck current evidence. Distinguish implementation presence, synthetic validation, real-data execution, readiness, and scientific validation. Treat existing reviews as leads to verify, not findings to repeat.

## Review boundaries

Review without modifying production code or canonical artifacts. Small temporary reproductions and fixtures are allowed in an isolated scratch directory. Inspect imports and test side effects before executing them. Do not run training, large downloads, field workflows, freeze audit sets, change preregistrations, access sealed audit labels, contact people, commit, or push. Do not overwrite result tables, models, source data, `output_wells.csv`, or DEP exports. Missing gated inputs are an assessment limitation unless code incorrectly bypasses the gate or misrepresents readiness.

Do not stop the entire review because one experiment is blocked. Review its guard behavior and continue independent work. Do not repair defects during this review. Propose the smallest correction and a meaningful regression check.

## Method

1. Inventory selected stages, entry points, configs, tests, imports, required artifacts, and declared gates. Map producer to artifact to consumer. Record paths, schemas, IDs, units, CRS, geometry type, hashes, and model policy where relevant.
2. Trace each claimed runnable stage from input loading through validation, transformations, statistics, gate decision, saved outputs, and provenance. Inspect actual call sites, not only helper definitions. Check whether config values are used or merely recorded.
3. Compare implementation with the authoritative estimand and stage contract. Look for duplicated implementations, copied defaults, placeholders, TODOs, hard-coded answers, silently skipped work, and statuses that claim more than the code supports.
4. Run relevant existing tests after inspecting their behavior. Use the documented interpreter/environment. Record exact commands, exit codes, failures, skips, and environmental blockers. Do not install dependencies or treat an import failure as a confirmed algorithmic defect.
5. Construct targeted counterexamples for consequential risks. Use independently derived expected outputs, not the implementation itself as the oracle. Prefer a tiny end-to-end fixture through the actual CLI and output reader when testing a handoff.
6. Follow each confirmed defect through its consumers. Report one root cause with its affected expansions rather than duplicating the same shared bug 20 times.
7. Maintain coverage throughout. If time or context limits prevent completion, list the exact stages and files not reviewed. Do not label sampled coverage as a complete review.

The README's suite command uses Bash. On PowerShell, discover the same intended test files and run each with `python -m pytest -q <file> -p no:cacheprovider`. Capture every invocation's exit code so a final passing file cannot hide earlier failures. Check whether separate-process tests hide shared-import collisions or other integration failures. Passing smoke tests are evidence only for what they assert.

## Universal attack checks

### Input contracts and reproducibility

- Missing, empty, truncated, corrupt, stale, and wrong-schema inputs must produce distinguishable outcomes. A failed catalogue request must not become an empty successful inventory.
- Check pagination, retry behavior, incomplete downloads, returned totals, duplicate pages, and union coverage rather than tile-count proxies.
- Test missing columns, null and duplicate IDs, string/numeric ID mismatches, leading zeros, many-to-many joins, and changed row order. Verify join cardinality and unmatched-row accounting.
- Confirm paths resolve from the documented configuration and repository helpers. Check arbitrary working directories and Windows paths with spaces. Identify personal absolute paths or ignored local artifacts required by an advertised clean-checkout workflow.
- Verify deterministic split membership in fresh processes and under input reordering where order should not matter. Inspect fold/arm seeds, stable tie rules, and unordered containers.
- Check cache keys and resume behavior against input, config, split, preprocessing, and checkpoint hashes. A changed parameter must not reuse incompatible output.
- Provenance must describe the inputs actually consumed and parameters actually used. Missing checkpoints, null hashes, incomplete runs, and dry-run outputs must not masquerade as verified production artifacts.
- Check write collisions, partial writes, overwrites, and success flags after failed stages. Separate nondeterministic metadata timestamps from scientific output reproducibility.

### Geospatial correctness

- Assert horizontal CRS, units, vertical datum where applicable, transform, extent, resolution, alignment, and nodata. A Pennsylvania CRS default must not silently apply to another region. Handle supported compound CRS explicitly.
- Challenge degree-versus-metre distances, square-degree areas, feet-versus-metres elevations, half-pixel shifts, row/column swaps, axis ordering, and differing pixel origins.
- Test nodata and NaN independently from valid zeros, including DN/254 probability decoding and 255 nodata where that format is used. Inspect categorical versus continuous resampling and masks at tile seams.
- Test empty and invalid geometries, multipolygons, boundary-touching objects, clipped objects, overlapping blocks, and duplicate detections across tiles. Ensure repair does not silently alter the scientific unit.
- Check that area denominators use the actual eligible scored footprint, including zero-feature blocks, and that physical thresholds remain consistent across resolutions.

### Leakage and model policy

- Trace geometry of entire training windows and augmentation support, not just center points or block IDs. Exclude held-out, inner-validation, and reserved audit ground as required.
- Fit normalization, imputation, feature selection, calibration, and tuning only on permitted data. Test indirect leakage through caches, inherited checkpoints, hard-negative mining, context features, and active-learning queues.
- Verify immutable future manifests and exposure history. Historical inner splits must not be presented as reconstructed. Reserved 9t data must not be called historically untouched.
- Ensure baseline and target use the declared compatible checkpoint, preprocessing, channel order, cutoff, calibration, and deployment policy. Missing isolated models must not silently fall back to historical models.
- Distinguish inductive evaluation from any declared transductive use of unlabeled target or audit imagery.

### Metrics and inference

- Verify recall at K uses candidates per square kilometre, the declared budget rounding and allocation, deterministic ties, complete truth denominators, and the same policy on reference and target.
- Current shared rules specify primary K=40, K=30 as sensitivity, proposal cutoffs pit=0.35 and pad=0.525, minimum blob area 4 m², and score-ordered one-to-one IoU matching at 0.3. Verify current authority and amendments before treating these as fixed requirements. A 0.10 sensitivity must not silently become primary.
- Challenge duplicate matches, greedy matching order, zero eligible area, zero truths, zero candidates, fractional budgets, ties, and quantized scores. Undefined recall must not become perfect recall or evidence of no effect.
- Bootstrap independent blocks/sites as designed, preserving repeated draws' multiplicity. Recompute pooled counts. Paired arms need the same sampled units. Repeated seeds, visits, and detections are not independent sample size.
- Verify interval methods for small samples, few clusters, weighted samples, paired designs, and undefined replicates. Check the implementation's fallback against the actual statistical design.
- Exercise gate bounds below, at, and above thresholds, crossing intervals, NaNs, and reversed bounds. Check non-inferiority signs, dimensional consistency, and mutually exclusive success/failure/inconclusive outcomes. Missing evidence must never default to success.
- Keep ranking, calibration, association, identity, density, and causal effects separate. Monotonic calibration cannot establish a ranking improvement at fixed K without another policy change.
- Check multiplicity, post-hoc threshold selection, independent controls, and claimed power. Margins must not be made easier by increased variance.

### Tests and integration

- Identify tests that assert only file existence, shape, non-null values, or results computed by the same helper. Check mocks that bypass the very transform or validation being tested.
- Test the producer's actual artifact with the actual consumer. Look for incompatible field names, missing sidecars, schema drift, checkpoint naming differences, and dry-run/canonical path confusion.
- Verify missing prerequisites fail clearly without writing misleading success outputs. Distinguish a legitimately deferred stage from an advertised runnable stage that cannot execute.
- Check runtime/memory complexity on plausible input sizes, especially pairwise matching, raster materialization, and bootstrap loops. Quantify the concern instead of speculating.

## Expansion-specific review matrix

Apply the following attacks in addition to the universal checks. Resolve each ID through the supplied folder and current README. These are hypotheses to investigate, not presumed defects.

| ID | Folder under `expansions/` | Targeted attacks |
|---|---|---|
| P1 | `0_prerequisites/p1_splits_manifests/` | Immutable manifests, fresh-process determinism, NaN/off-tile handling, full-window isolation, fold-local statistics, derived buffer units/support, honest historical versus future split labels. |
| P2 | `0_prerequisites/p2_audit_set/` | Audit hashes, reserve/freeze guards, complete exposure ledger, exclusion from every training/calibration/mining/selection path, separate new-area final evaluation. |
| 3.0 | `3_geography/3_0_transfer_protocol/` | Independent hand calculation of candidate extraction, matching, area budgets, reference counts and intervals. Separate archival sweep reproduction from new isolated baseline. |
| 3.1 | `3_geography/3_1_warren_forest_mckean/` | Frozen 0.5 m pipeline, ground-density/void eligibility, blind complete-block labels, acquisition confounding, county-specific footprints, deployment-compatible checkpoint. |
| 3.2 | `3_geography/3_2_appalachian_states/` | Catalogue pagination and coverage unions, state schemas, county selection, query failure states, local evidence incorrectly generalized to a state. |
| 3.3 | `3_geography/3_3_low_relief_slope/` | Slope units/bin edges, sparse strata, dependence of multiple features per block, density confounding, synthetic edits changing unintended channels, slope association presented as causation. |
| 3.4 | `3_geography/3_4_gulf_texas/` | Shared transfer core, undefined policy checkpoint, regional CRS, observable morphology/depth assumptions, ecological and acquisition shifts, Gulf/East Texas/Pecos conflation. |
| 3.5 | `3_geography/3_5_oklahoma_kansas/` | Regional coverage, footprint and target definitions, copied Pennsylvania defaults, density-adjusted sensitivity, guard behavior before transfer prerequisites exist. |
| 3.6 | `3_geography/3_6_california/` | Urban removal/burial and missing surface observability, imagery/label dates, regional CRS, terrain evidence incorrectly treated as well absence. |
| 3.7 | `3_geography/3_7_canada/` | Province-specific schemas, datum and units, access/coverage assumptions, model-policy handoff, unsupported national extrapolation. |
| 3.8 | `3_geography/3_8_alaska/` | InSAR units/sign/LOS geometry, stable reference, seasonality, atmospheric/permafrost confounding, acquisition timing, motion incorrectly equated with integrity or leakage. |
| 4.1 | `4_modalities/4_1_magnetometry/` | Unknown-date strata, sensor/background corrections, site-level independence, metal confusers/blanks, ferromagnetic anomaly incorrectly equated with well identity. |
| 4.2 | `4_modalities/4_2_thermal/` | Kelvin/Celsius and scaling, target dilution, canopy/cloud masks, acquisition/weather matching, repeated visits, independent leakage labels. |
| 4.3 | `4_modalities/4_3_vegetation_stress/` | Reflectance scaling and band formulas, cloud/season masks, disturbance/moisture confounding, site-season leakage, morphology labels substituted for leakage labels. |
| 4.4 | `4_modalities/4_4_methane_plumes/` | Preserve closure for ordinary small-well screening. Check emission/detection-limit units and weather assumptions. Population means do not bound emission tails. Any large-emitter exception needs explicit scope. |
| 4.5 | `4_modalities/4_5_multitemporal_lidar/` | Flight-date bounds versus restoration dates, vertical/coregistration bias, stable controls, full-chain injected recovery, change detection limits, plugging versus restoration claims. |
| 4.6 | `4_modalities/4_6_historic_maps_aerials/` | Georeferencing error, symbol identities, duplicate sources, date bounds, blind source selection, circular acceptance based on agreement with DEP/lidar. |
| 4.7 | `4_modalities/4_7_drone_lidar/` | Nested thinning and seed pairing, measured ground density, site-selection bias, acquired versus simulated density, unsupported inference to new acquisitions or confirmed wells. |
| 4.8 | `4_modalities/4_8_leafoff_optical/` | Actual leaf-off dates, canopy/cloud/quality masks, co-registration, review-gate enforcement, matched eligible footprints, optical-source leakage. |
| 4.9 | `4_modalities/4_9_more_radar/` | Linear/dB transformations, polarization/band metadata, speckle and incidence geometry, temporal matching, duplicated arms, unverified assumed inputs, multiple-comparison selection. |
| 5.1 | `5_tasks/5_1_context_features/` | Out-of-fold first-stage predictions, train-only second-stage fitting, DEP/label-derived feature leakage, feature availability at deployment, fair matched-budget comparison. |
| 5.2 | `5_tasks/5_2_era_classification/` | 1800/unknown sentinels, interval-censored dates, label-source uncertainty, temporal leakage, selective labelled sample, class support and held-out calibration. |
| 5.3 | `5_tasks/5_3_risk_ranking/` | Score direction and units, missingness, arbitrary weight sensitivity, double-counted correlated factors, heuristic score incorrectly described as calibrated probability or validated harm. |
| 5.4 | `5_tasks/5_4_undocumented_density/` | Identifiability, detection/verification probabilities, field inclusion weights, unresolved outcomes, area denominators, terrain-candidate counts incorrectly converted into well totals. |
| 5.5 | `5_tasks/5_5_polygon_area_cost/` | Projected area, overlapping polygons, holes/slivers, price-year/currency/unit conventions, uncertainty propagation, footprint proxy incorrectly equated with remediation cost. |
| 5.6 | `5_tasks/5_6_record_association/` | Full matched and unmatched outputs, stable det_id, global uniqueness across statuses, task-specific footprints, whole-set shift nulls, edge retention, proximity excess incorrectly called link PPV. |
| 6.1 | `6_adjacent/6_1_co2_geothermal/` | Full-output handoff and deduplication, site/buffer units, missing subsurface evidence, screening indicators incorrectly promoted to storage suitability or integrity. |
| 6.2 | `6_adjacent/6_2_coal_features/` | Coal/mine label provenance, inventory completeness, class confusion and overlap, source-specific evaluation, surface features incorrectly treated as mapped underground hazards. |
| 6.3 | `6_adjacent/6_3_confuser_classes/` | Train-only hard-negative mining, mixed/unknown labels, audit contamination, class balance, false-positive reduction achieved only through recall loss or changed review budgets. |
| 6.4 | `6_adjacent/6_4_hydrogen/` | Distinct hydrogen assumptions, full-output handoff, missing geology/integrity evidence, copied CO2 criteria presented as hydrogen validation. |
| 6.5 | `6_adjacent/6_5_field_methane/` | Instrument units/calibration, background/wind, repeated visits, detection limits, location/source attribution, non-detection treated as absence, screening treated as emissions quantification. |
| 6.6 | `6_adjacent/6_6_sar_viewshed/` | Here SAR means search and rescue. Check observer/target heights, DEM versus DSM, nodata occlusion, range/curvature assumptions, and geometric visibility incorrectly treated as person detection probability. |
| 7.1 | `7_scale/7_1_pretraining/` | Unlabelled-data exposure, audit geography contamination, checkpoint provenance, train-only normalization, comparable compute/tuning budgets, incremental value over supervised baseline. |
| 7.2 | `7_scale/7_2_active_learning/` | Audit exclusion, acquisition before labels, duplicate selections, round lineage, fixed comparison budgets, actual reviewer time, adaptive-selection bias in evaluation. |
| 7.3 | `7_scale/7_3_benchmark/` | Fresh-checkout runnable package, immutable split hashes, hidden local dependencies, preprocessing parity, dev/test separation, licensing/provenance, leaderboard-induced test tuning. |
| 7.4 | `7_scale/7_4_agency_tooling/` | Stable exported IDs/CRS/schema, unresolved evidence labels, input/path validation, export/import round trips, stale model/result display, unsupported confidence or readiness claims. |
| 7.5 | `7_scale/7_5_field_campaign/` | Sampling frames and inclusion probabilities, arm overlap, nonresponse and unresolved outcomes, blinded verification, duplicate sites, population weighting, lineage into 5.4. |

Also review `_shared/INTERFACES.md` against actual producers and configs. Inspect `_template/` for copied assumptions that can introduce bugs into future expansions. Do not treat template placeholders as production failures unless an instantiated consumer actually uses them incorrectly.

## Required report

Lead with the most consequential confirmed findings. For every finding provide:

- ID and severity. Critical means widespread result corruption or invalidation of core scientific claims. High means a major wrong output, leakage, or broken required stage. Medium means a narrower consequential defect. Low means a minor actionable defect. Assign severity based on demonstrated impact.
- Expansion IDs and exact current file paths with one-based line numbers.
- Concrete trigger, expected behavior, and actual behavior.
- Evidence: inspected code path, small counterexample, test output, or artifact comparison. State whether reproduced or established by static analysis.
- Downstream consequences for artifacts, metrics, gates, and claims.
- Minimal correction and a regression test that would fail before the correction.

Separate confirmed findings from unverified hypotheses, missing-data limitations, documentation contradictions, and scientific design questions. Do not describe a hypothetical risk as an observed failure. State assumptions and confidence. Report an old finding only if it still exists in current code. Cite authority for protocol deviations and independent reasoning for defects in the authority itself.

Then provide:

1. A coverage table for every selected ID, plus relevant shared components, with files/stages inspected, tests run, and status: reviewed with findings, reviewed with no confirmed findings, partial, or blocked. No blank implied approvals.
2. A test/reproduction log with exact commands, environment, outcomes, and scratch artifact paths. Explicitly say which checks were not run and why.
3. A producer/consumer contract table of confirmed mismatches and unresolved dependencies.
4. The highest-priority repairs in dependency order, with shared root causes first.
5. A readiness assessment that separately addresses code execution, integration, reproducibility/leakage controls, and scientific evidence. State which claims remain unsupported even if every existing test passes.

If no confirmed defects are found, say so and describe the actual coverage and residual uncertainty. Never equate “no confirmed findings” with production readiness or scientific validity.
