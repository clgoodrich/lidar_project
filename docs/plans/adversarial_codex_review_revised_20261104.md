# Adversarial Codex Review of the Revised Expansion Plans

**Reviewed:** 2026-11-04. Independent scientific review of the current revision, including the new master plan, authoritative protocol, acquisition documents and all 37 individual plans. This supplements, rather than overwrites, `adversarial_codex_review_20261104.md`.

**Overall judgment:** The revision substantially improves the program. It withdraws invalid analyses, distinguishes feature detection from well confirmation, and moves historical and field evidence ahead of speculative scaling. Nevertheless, the authoritative protocol is **not ready to preregister as written**. Several new acceptance rules would certify quantities that have not been measured, reject useful evidence, or give contradictory verdicts. These are repairable design problems. They do not justify abandoning the entire program.

The most consequential findings are:

1. `1 - null / observed` is not the predictive value of proposed record links. Using it to promise acceptable wasted field visits invalidates that inference.
2. Exact reproduction of the historical operating-point sweep from the saved probability mosaic is not an established capability. The original sweep uses fold-specific candidate tables, cutoffs and budgets. Changing to isolated training and fold-local normalization also creates a new baseline.
3. Some gates can declare the same result both successful and unsuccessful. The change-detection gate also compares a rate difference with a margin expressed in metres.
4. The field design now has the right three sampling frames, but its unresolved-outcome bounds are incomplete. An unknown-date sentinel is also being treated as evidence of an early well.
5. The new lidar inventory is useful discovery work, not verified spatial coverage. Tile-count ratios cannot establish coverage, and the listing scripts do not establish query completeness.
6. Historic-source acceptance still depends partly on agreement with another incomplete inventory. This can discard precisely the independent historical positives the program needs.

**Recommended investment:** repair the protocol and provenance first; pursue a bounded historical-source probe and a probability-based field design; prepare one geographically bounded transfer test; repair association as an exploratory analysis. Defer broad regional downloads, context retraining, pretraining and application products until these steps change a scientific decision.

## Review scope and evidence status

The review read the current plan hierarchy starting with `docs/plans/README.md`, the master plan and protocol, every individual plan including its overriding revision, the response and download documents, and the two supporting expansion documents. Underlying checks included the association loader and matching inputs, split and training code, the operating-point implementation and saved probability metadata, lidar-listing scripts and saved catalogue tables, and relevant saved evaluation reports. Existing reviews were treated as claims to check, not as evidence of correctness.

Local citations below are repository-relative paths with one-based line numbers, rooted at **`C:\Users\colto\Documents\GitHub\lidar_project`**. They refer to the version inspected on this date. No plans were executed, models trained, large datasets downloaded, or people contacted. Only this review document was added.

- **Verified** means supported by inspected current text, code, artifacts or a cited primary source. It does not mean the proposed experiment has run.
- **Contradicted** means inspected evidence conflicts with the particular claim.
- **Plausible but unverified** means feasible in principle but dependent on missing validation or data.
- **Not assessable** means the necessary evidence is unavailable here, such as partner access, undiscovered historical coverage or field-search sensitivity.

### Corrections that deserve credit

The first association and recall-gap results are explicitly withdrawn, with the correct input-selection failure described (`protocol_gates_and_metrics.md:45–50`). The old Warren cutoff recall is no longer passed off as recall at a review budget. K is now the user's chosen **40 candidates/km²**, and full-block annotation and target-density reporting are required (`protocol_gates_and_metrics.md:14–24`). I accept that operational choice; it is not an empirically established optimum.

The revision correctly separates historical held-out assignments from unrecoverable inner splits, requires whole-window exclusion and fold-local normalization for new training, acknowledges that 9t is not untouched, and recognizes Warren as a within-survey comparison (`protocol_gates_and_metrics.md:26–42`; `plan_geo_warren_forest.md:48`). It also corrects the NETL sample from confirmed wells to lidar-selected potential sites (`plan_mod_drone_lidar.md:33–35`), replaces ordinary-terrain change controls with eligible pads, separates restoration from plugging, and retains an inconclusive outcome (`plan_mod_multitemporal_lidar.md:32–36`). These are substantive improvements.

**Correction to my earlier review:** direct bounds checks support the revised statement that the 209 pit and 345 pad rows without block IDs are off-tile annotations. They are not evidence of excluded in-tile evaluation features. This does not resolve the distinct NaN inner-split or full-window sampling problems. The user also reports that annotators did not see DEP well points. That particular circularity objection is closed; other annotation context remains unrecorded (`EXPANSION_MASTER_PLAN.md:116–122`).

## A. Coverage table

Decisions describe the strongest defensible next research scope, not authorization to execute it. A bounded pilot can establish feasibility or local evidence; it does not imply population validation. Filenames are under `docs/plans/`.

| ID and filename | Decision | Evidence it can legitimately produce | Main unresolved issue | Smallest defensible next step |
|---|---|---|---|---|
| P1 `plan_prereq_splits_manifests.md` | Proceed | Reproducible future splits and an honest historical provenance record | Historical inner roles cannot be recreated by dropping NaN now | Specify immutable future splits and whole-window/normalization checks; mark historical uncertainty |
| P2 `plan_prereq_audit_set.md` | Proceed | Prospective comparisons among new models on reserved 9t blocks | Past model selection already used 9t | Inventory every use of each block; reserve a separate final area |
| 3.0 `plan_geo_transfer_protocol.md` | Redesign | Comparable feature recall under a declared deployment budget | Historical reproduction and new baseline are conflated | Separate archival regression checks from a new frozen inference policy |
| 3.1 `plan_geo_warren_forest.md` | Bounded pilot | Local feature transfer within D20; a separate geography/acquisition comparison in McKean | Labels, margin, target precision and baseline policy remain unresolved | Audit one eligible footprint and measure blind annotation effort before sizing |
| 3.2 `plan_geo_appalachian_states.md` | Defer | Local transfer cases in selected counties | Listing is not coverage validation; one county cannot represent a state | Repair catalogue completeness and select one contrast only after 3.1 |
| 3.3 `plan_geo_low_relief_midwest.md` | Bounded pilot | Association of existing feature recall with slope; controlled model-response diagnostics | Slope differences do not identify slope causation or flat-region transfer | Prespecify a retrospective slope diagnostic with counts and uncertainty |
| 3.4 `plan_geo_gulf_east_texas.md` | Defer | Performance for a separately defined target morphology | Vegetation, acquisition and industrial setting shift together; Pecos is not East Texas | Define observable targets and audit one candidate area's metadata |
| 3.5 `plan_geo_oklahoma_kansas.md` | Defer | Performance in selected visible oil-field settings | Detectable feature definition and representative labels absent | Verify coverage and target morphology before data expansion |
| 3.6 `plan_geo_california.md` | Defer | Detection of specified surviving surface structures | Urban removal/burial breaks the terrain-feature proxy | State an observable target and decision use; audit a small example set |
| 3.7 `plan_geo_canada.md` | Defer | Province-specific transfer if data and labels exist | Coverage, terms and reviewers remain unverified | Metadata and access inventory only |
| 3.8 `plan_geo_alaska.md` | Defer | Potential line-of-sight surface-motion evidence | Motion is not well integrity; seasonal reference/confounding problems | Write an observability and stable-reference feasibility note |
| 4.1 `plan_mod_magnetometry.md` | Redesign | Operational detectability of ferromagnetic anomalies in specified strata | Unknown dates are misclassified; anomalies are not well identities | Correct strata and pilot known targets, metal confusers and blanks |
| 4.2 `plan_mod_thermal.md` | Defer | Specified surface-temperature contrasts under usable acquisitions | Target dilution, canopy and no independent leak labels | Quantify target support and detectable contrast before imagery work |
| 4.3 `plan_mod_vegetation_stress.md` | Defer | Vegetation differences conditional on site and acquisition | Disturbance, moisture and canopy can mimic the proposed signal | Choose morphology screening or independently labelled leakage first |
| 4.4 `plan_mod_methane_plumes.md` | Defer | Large-emitter plume evidence under stated sensor conditions | Mean small-well emissions do not bound the population tail | Close routine individual-small-well screening with a scoped detectability note |
| 4.5 `plan_mod_multitemporal_lidar.md` | Blocked | Detectable surface change associated with dated restoration | Flight dates, restoration eligibility and dimensionally valid gate | Establish date bounds and eligible site count; design full-chain recovery checks |
| 4.6 `plan_mod_historic_maps_aerials.md` | Bounded pilot | Historical presence and date bounds for interpretable, locatable symbols | Coverage unverified; source gate partly circular | Inspect source coverage/legibility independently of lidar or DEP agreement |
| 4.7 `plan_mod_drone_lidar.md` | Blocked | Within-acquisition sensitivity to retained ground points at selected sites | Release, selection history and independent identities unavailable | Await the user's NETL request; assess terms and metadata if supplied |
| 4.8 `plan_mod_leafoff_optical.md` | Bounded pilot | Added visible surface evidence when ground is observable | Missing/blank imagery and canopy censor observations | Predefine a small chip set and record acquisition and visibility separately |
| 4.9 `plan_mod_more_radar.md` | Defer | A scoped negative result for tested radar products and targets | Existing results do not exclude every sensor or target | Finalize the narrow negative-result statement; no new imagery campaign |
| 5.1 `plan_task_context_features.md` | Redesign | Incremental feature-ranking performance under nested spatial evaluation | Upstream provenance and contradictory useful-gain gate | Specify common folds and all cross-fitting before retraining |
| 5.2 `plan_task_era_classification.md` | Blocked | Construction-date bounds or classes supported by independent history | Sentinel dates and historical absence are not era labels | Build a small identity-resolved dated subset through 4.6 |
| 5.3 `plan_task_risk_ranking.md` | Defer | Potential decision ranking against an independently measured hazard endpoint | No validated well probability or hazard target | Identify the decision and measurable endpoint before scoring |
| 5.4 `plan_task_undocumented_density.md` | Redesign | Conditional bounds and sensitivity analysis | Well precision and undocumented-well recall are unidentified | Write distinct-well accounting and show bounds as recall varies |
| 5.5 `plan_task_polygon_area_cost.md` | Defer | Reproducibility of visible footprint measurement | Footprint does not identify restoration extent or cost | Establish a decision requiring area and an independent reference |
| 5.6 `plan_task_record_association.md` | Redesign | Exploratory spatial association; validated links only with adjudication | Proposed predictive value is not PPV; old input is invalid | Repair full-output contract, footprints and assignment; rename excess statistic |
| 6.1 `plan_adj_co2_geothermal.md` | Defer | Surface inventory contribution to a partner's screening | Surface detection does not establish subsurface construction/integrity | Specify partner decision and missing subsurface information |
| 6.2 `plan_adj_coal_features.md` | Defer | A separate morphology-classification problem | Independent identities and regional utility unestablished | Small inventory-to-imagery identity audit if a use case appears |
| 6.3 `plan_adj_negative_classes.md` | Bounded pilot | Confuser reduction relative to equal-budget random negatives | Codebook ambiguity, reviewer capacity and well-proxy mismatch | Blind codebook/throughput pilot before training the three arms |
| 6.4 `plan_adj_hydrogen.md` | Defer | No distinct validated evidence beyond a surface inventory | No additional question or endpoint | Keep out of the current pipeline |
| 6.5 `plan_adj_field_methane.md` | Bounded pilot | Instrument- and visit-specific methane observations | Concentration is not flux; intermittent emissions and weather | Prepare background, repeat and calibration procedures alongside 7.5 |
| 6.6 `plan_adj_sar_viewshed.md` | Defer | A separate terrain/viewshed product | Does not reduce well-research uncertainty | Treat as a separate project |
| 7.1 `plan_scale_pretraining.md` | Defer | Improvement under one explicitly chosen resource budget | Baseline integrity and total-cost comparison | Choose the estimand and cost accounting after P1/P2 |
| 7.2 `plan_scale_active_learning.md` | Defer | Label-efficiency gains under independent stopping and evaluation | Candidate-only acquisition misses absent proposals; labor differs | Design random-area discovery and time-based accounting |
| 7.3 `plan_scale_benchmark.md` | Defer | A reproducible feature benchmark with explicit label limits | Splits, partial labels, licences and final-area provenance | Draft a datasheet after P1/P2, before packaging |
| 7.4 `plan_scale_agency_tooling.md` | Defer | Reliable implementation of a validated reference policy | Reference policy and supported input envelope not frozen | Specify input validity and provenance requirements only |
| 7.5 `plan_scale_field_campaign.md` | Redesign | Weighted feature-to-well share, candidate precision and conditional search recall | Incomplete ambiguity bounds, access and search sensitivity | Repair outcome accounting and sampling frames; then partner feasibility pilot |

The master plan, protocol and acquisition documents are cross-cutting prerequisites, not additional experiments. The **master plan needs correction**, the **protocol needs redesign**, and the **catalogue is suitable for discovery only**. The review-response file records useful corrections but does not substitute for these repairs.

## B. Prioritized findings

### 1. Excess spatial association is being promoted to link precision and recall

**Severity:** invalidates inference. **Affected:** 5.6, A6, 5.4 and any field-use claim built on their estimates.

**Location and claim:** `docs/plans/protocol_gates_and_metrics.md:57` and `:76` call `1 - null / observed` predictive value and gate it against acceptable wasted visits. `plan_task_record_association.md:38` repeats this. Protocol `:59` and `:77` use a difference in cohort-specific excess association as the recall-gap quantity, with a margin motivated by density estimation.

**Evidence/status:** **Contradicted as an interpretation**, independently of what the repaired data will show. A shifted-set null estimates matches under a chosen spatial randomization. It does not count incorrect identities among the observed accepted links. Even if every observed link were correct, shifted records could still overlap features, yielding a positive null and an alleged PPV below one. Conversely, local development density or record-placement conventions can raise observed proximity without establishing well identity. The protocol itself acknowledges spatial gradients at `:56`.

**Failure mechanism:** a crew could pass the gate despite many wrong links. Separately, coordinate accuracy, documentation selection, feature visibility and well prevalence can all alter cohort proximity. Subtracting separate null rates does not identify detection sensitivity. Even the restrictive mixture model `o = r + (1-r)q` would imply `r = (o-q)/(1-q)`, not simply `o-q`; real assignment and coordinate error make that model insufficient as a correction.

**Minimum correction:** call the statistic normalized excess association, specify its null and report it descriptively. Estimate link PPV from blinded identity adjudication of a probability sample of accepted links, retaining ambiguous outcomes and inclusion weights. Evaluate coordinate improvement on independently surveyed identities, comparing before/after errors. Call A6 a cohort association comparison until a verification design establishes recall for the same eligible population.

**Still unknowable:** undocumented-well sensitivity, representativeness of newly documented wells, and population well density. Accurate GNSS coordinates help location error; they do not remove documentation-selection bias.

### 2. Historical reproduction and a leakage-controlled baseline are incompatible requirements

**Severity:** materially weakens inference; exact-reproduction demand is also an execution risk. **Affected:** P1/P2, 3.0–3.8, 5.1, 6.3, 7.1–7.3.

**Location and claim:** protocol `:18–24` and `:70` require exact reproduction of the old operating-point sweep from the saved OOF mosaic. `plan_geo_transfer_protocol.md:33–35` also requires isolated training and fold-local normalization. `EXPANSION_MASTER_PLAN.md:130` labels held-out CV recall valid without qualification.

**Evidence/status:** **Verified implementation mismatch.** `notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py:99–132` reads per-fold object tables, selects a proposal cutoff using other folds and fits a calibrator. At `:143–144`, the review budget is floored separately for each fold's eligible area. This is not specified by merely passing a mosaic through one proposal policy. Direct inspection of `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` found probability encoded as `DN / 254`, with 255 as nodata. Quantization changes scores/ties and potentially thresholded objects; polygonization across fold seams can also differ.

The original sampler reads full windows beyond their selected training block (`notebooks/wellsight_v2/_dl.py:249–275`). The isolated pad trainer improves window exclusion but still loads the shared statistics file (`notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py:113`, `:310`). Thus deterministic held-out IDs do not certify leakage-free predictions. The revised protocol correctly acknowledges both issues at `:31–34`; the master plan's blanket validity label is inconsistent with that acknowledgment.

**Failure mechanism:** a scientifically correct repaired baseline fails the exact-match gate; alternatively, reproducing a compromised historical result is mistaken for validation. A global target top-K and a fold-allocated reference top-K can differ even with identical underlying ranking quality.

**Minimum correction:** separate two tasks. An archival check reproduces the historical statistic from its actual candidate tables, fold areas, cutoffs, matching and tie rules. A new scientific baseline uses explicit isolated training, fold-local preprocessing and one deployment-compatible policy. Preserve unquantized artifacts where available; do not require quantized mosaics to recover lost information. Define whether deployment uses one model or an ensemble and make the reference comparable. Treat the old 9t estimate as a historical diagnostic, not an unbiased new baseline.

**Still unknowable:** historical contamination magnitude and exact inner roles absent trustworthy logs/checkpoint metadata. A frozen old model can still receive a valid absolute test in a genuinely new area, but that does not repair the historical reference used for a transfer difference.

### 3. Several gates are mathematically inconsistent or use noise to set usefulness

**Severity:** invalidates inference for overlapping/unit-mismatched gates; materially weakens transfer decisions. **Affected:** 3.1, 4.5, 5.1 and the shared gate policy.

**Location:** protocol `:63`, `:71`, `:73`, `:79`.

**Evidence/status:** **Verified in the current table.** Context success is lower confidence bound above zero; failure is upper bound below the useful gain. If the useful gain is 0.03 and the interval is [0.01, 0.02], both rules pass. These numbers illustrate the logical defect; they are not proposed scientific margins. Change detection has the same overlap and lists a 0.16–0.22 m detectability floor as the basis of a gate whose primary statistic is a difference in flag rates. Metres and probability points are different quantities.

The Warren margin is to be “floored by 9t fold spread.” Fold spread measures instability and heterogeneity, not an acceptable operational loss. Increasing noise must not automatically relax a noninferiority requirement. Projecting interval width from 9t resampling alone also does not establish precision in Warren, whose feature density, clustering and eligible area differ.

**Failure mechanism:** the same finding receives opposite decisions; a weak study appears acceptable because its margin widens with its noise; a useful target study is prematurely rejected using an unrepresentative source-area precision forecast.

**Minimum correction:** use one decision threshold in the statistic's units for both success and failure, with the region between designated inconclusive. Derive acceptable recall loss from missed-feature burden at K=40 and derive useful gain from the decision it changes. Use variance to determine sample requirements, not usefulness. Forecast target precision across plausible target-density and clustering scenarios, including reference uncertainty. Use inference appropriate to the sampling design; a universal block bootstrap is not automatically suitable for a weighted field sample or very few independent clusters.

**Still unknowable:** the actual decision margins and attainable target precision until the user specifies the burden tradeoff and a blinded label/coverage pilot measures target conditions.

### 4. The field design can understate uncertainty and mislabel early-era sites

**Severity:** invalidates a claimed population bound if unresolved identities are treated as negatives; materially weakens era-specific inference. **Affected:** 4.1, 5.2, 5.4, 6.5, 7.5.

**Location:** protocol `:87–94`; `plan_mod_magnetometry.md:33–37`; `plan_scale_field_campaign.md:33–36`.

**Evidence/status:** **Verified ambiguity in the rules.** The outcomes separately list steel only, nothing found, unresolved and inaccessible, but the bounds only vary the category named unresolved. Steel alone does not establish well identity. A negative search with unknown sensitivity does not establish absence. Inaccessible sampled sites remain part of the frame. The text also treats the 1800 sentinel as an early-era stratum despite describing it as a sentinel in `:59`.

**Failure mechanism:** excluding access failures or counting unsuccessful searches as definite non-wells yields artificially narrow bounds. Unknown construction dates can then look like an early-era magnetic failure, confounding chronology, casing retention and search quality.

**Minimum correction:** define an identity-status variable independent of the observational outcome. All cases not definitively confirmed or excluded remain ambiguous for identity bounds, regardless of outcome label. With known sampling weights, lower identification bound is confirmed-well weight divided by total sampled weight; upper bound is one minus definitively-nonwell weight divided by total sampled weight. Add sampling uncertainty around those bounds. Report unknown dates separately from independently dated early wells. Stratify by actual casing evidence where available; date is an imperfect proxy.

Magnetometry detects ferromagnetic material, including non-well infrastructure. “Needs intact steel casing” is too categorical. Casing remnants and other metal can produce anomalies; wood itself supplies no corresponding magnetic signature. NETL describes both casing targets and other oil-field infrastructure in its [technical report](https://www.osti.gov/servlets/purl/916923). Retain positive controls and metal confusers rather than equating anomaly with well.

**Still unknowable:** wells lacking both observable remains and recoverable documentation. Repeated searches do not identify sensitivity unless their dependence and confirmation standard are addressed. The proposed simple-random-sample sizes are rough planning approximations, not guarantees for clustered, weighted, inaccessible field samples.

### 5. Lidar recommendations are not based on verified spatial coverage

**Severity:** execution risk with material inference consequences if coverage defines the sample. **Affected:** all geographic plans, download manifest and master resource totals.

**Location and claim:** `download_list_areas_and_lidar.md:122` chooses the newest project covering at least half the window's tiles. The master treats the listing as valid at `EXPANSION_MASTER_PLAN.md:130`.

**Evidence/status:** **Verified failure of the coverage proxy; completeness unverified.** In `data/_source/reference/lidar_catalogue/lidar_pilot_windows_summary_us.csv:25–29`, Missouri/Jackson's 2020 project has 16 tiles and `cover=0.4444`, while the recommended 2006 project has 36 and `cover=1`. These values are tile-count ratios, not geographic coverage. At `:76–78`, 19 Ohio-project tiles in Pleasants receive `cover=0.5` relative to 38 West Virginia tiles. Different tile sizes, overlaps and footprints invalidate the ratio. These examples do not prove which project covers more area; they prove that the recommendation has not established it.

`notebooks/wellsight_v2/s1_build/_list_lidar_pilot_windows_us.py:90–95` asks for at most 200 results without pagination or checking returned total against count. Lines `:43–51` collapse repeated request failure into an empty result. Lines `:97–99` deduplicate by URL across windows, which can discard a tile's membership in another window. The county-discovery script samples five small locations rather than exhaustively inventorying the county. A sample mean tile size multiplied by an API count is an estimate, not a guaranteed size upper bound. A row at exactly 200 tiles is a truncation warning, not proof of truncation.

**Failure mechanism:** a complete recent acquisition can be rejected because its tiles are larger, a partial acquisition accepted because it has many small tiles, or a failed API call reported as absent data. The resulting labels may cover a selected fragment of the intended population. Resource totals can omit tiles or misallocate shared ones.

**Minimum correction:** retain tile geometries and verify union coverage of the actual eligible window, including overlap with target records. Paginate and distinguish successful-empty, failed and incomplete queries. Maintain separate unique-asset and asset-to-window tables. Match project identity explicitly, verify acquisition metadata, and report count/size uncertainty. Recompute recommendations only after these checks. Do not download more data merely to fix metadata accounting.

**Still unknowable:** effective under-canopy ground density, usable returns and actual flight dates from a download URL alone. The new well databases are a useful availability advance, but row counts and hashes do not establish coordinate accuracy, status harmonization or representative undocumented-well coverage.

### 6. Historical-source validation still risks circular rejection

**Severity:** materially weakens inference. **Affected:** 4.6, 5.2, 7.5 and the central feature-to-well question.

**Location:** protocol `:74` requires a positive excess over a shifted null for historic-source success, while `:123` and `plan_mod_historic_maps_aerials.md:36` correctly say to retain historical positives with low lidar scores. `EXPANSION_MASTER_PLAN.md:136` elevates sources with metre-scale positions.

**Evidence/status:** **Verified conflicting objectives; actual source coverage unverified.** If the excess statistic is agreement with current lidar detections or DEP records, source acceptance depends on another incomplete measurement. A valid source revealing omitted wells could fail. The protocol does not specify the counterpart sufficiently to remove this ambiguity. Held-out control-point RMSE measures registration, not all symbol-placement, source-survey, symbol-size or borehole-offset error.

**Failure mechanism:** the experiment preferentially accepts sources that confirm existing detections, then calls the resulting agreement independent corroboration. A broad but useful source could also be rejected by an unjustified metre-scale requirement.

**Minimum correction:** source readiness should depend on provenance, dates, interpretable symbols, coverage and independently measured positional uncertainty appropriate to the intended matching task. Keep association with lidar/records as a separate outcome. Include original symbol-location uncertainty and identity ambiguity when choosing match rules. A poor source can be unusable for individual matching yet useful for regional historical presence.

**Still unknowable:** whether any suitable source covers 9t, how completely it enumerates wells, or whether an old platform and a later borehole are the same entity. A dated presence can bound existence; absence still cannot establish a later construction date.

### 7. Mandatory density thinning changes the transfer question

**Severity:** materially weakens inference. **Affected:** 3.0–3.8 and comparisons with 4.7.

**Location:** protocol `:41` says to thin to 9t ground density first, then grid at 0.5 m. The drone revision correctly limits thinning interpretation (`plan_mod_drone_lidar.md:34–35`).

**Evidence/status:** **Verified design inconsistency.** Downsampling cannot raise density in a lower-density acquisition. Matching a mean density also cannot reproduce canopy holes, scan geometry, classification errors, noise or footprint support. Moreover, degrading available target data changes the operational performance being estimated.

**Minimum correction:** use native target information through the frozen 0.5 m processing pipeline as the primary deployment test. Use prespecified paired downward-thinning arms where possible to investigate information sensitivity, retaining spatial density/void maps and thinning variability. Do not substitute upsampling or interpolation for added information. Describe McKean as a joint geography/acquisition contrast unless a design separates those factors.

**Still unknowable:** causal attribution of a transfer difference to sensor, terrain, canopy, label conventions or industrial history. The current correction that a domain classifier cannot supply that attribution is sound.

### 8. Closing routine satellite methane screening is justified; a statewide impossibility claim is not

**Severity:** materially weakens the scope of a negative conclusion, not a reason to fund this expansion. **Affected:** 4.4.

**Location:** `plan_mod_methane_plumes.md:30–35`; protocol `:116`.

**Evidence/status:** **Verified primary specifications.** Carbon Mapper lists Tanager 90% detection probability at 90–180 kg/h under 3 m/s wind, 35-degree solar zenith angle, 25% albedo and 30 m GSD. These are conditional specifications, not universal realized sensitivity. [Carbon Mapper specifications](https://carbonmapper.org/articles/tanager-methane-performance-specifications).

Kang et al.'s 19 Pennsylvania wells had mean emissions about 0.27 kg/day, or 0.01125 kg/h, with a heterogeneous high-emitter subset. The ratio to the stated sensor threshold is approximately 8,000–16,000. This supports rejecting routine satellite screening for individual wells resembling that sample mean. It does not bound rare large emitters, aggregation or every Pennsylvania source. [Kang et al., institutional publication record](https://collaborate.princeton.edu/en/publications/direct-measurements-of-methane-emissions-from-abandoned-oil-and-g/).

**Minimum correction:** close the specified small-well discovery use case on observability and opportunity-cost grounds. State that the conclusion concerns ordinary individual low-rate sources under these sensor conditions. Keep broad plume-source attribution as a separate, currently unjustified research question.

**Still unknowable:** the relevant tail of emission rates and acquisition-specific detection probability. No additional broad plume search is warranted merely to qualify the wording.

### 9. Administrative contradictions can cause work on the wrong dependency

**Severity:** minor, with execution risk if acted upon. **Affected:** acquisition and sequencing documents.

`download_manifest.md:32` gates older DEP snapshots on a “D3 reply,” but D3 is literature acquisition; the intended dependency appears to be the R1 coordinate-provenance reply. Its R4/R5 rows still ask decisions already recorded in master `:116–122`; its body retains older disk figures and an unconfirmed McKean scope despite the top-level update. `plan_task_record_association.md:39` likewise repeats the answered DEP-visibility question.

**Minimum correction:** reconcile statuses and dependency IDs in place, then remove superseded contradictory instructions instead of relying indefinitely on appended overrides. The user has already chosen K, restored McKean to scope and taken responsibility for outreach. Do not request those decisions again.

**Still unknowable:** reply timing, reviewer availability and field-access calendar. These are external dependencies, not coding estimates.

## C. Revised experimental gates

These replace the defective rules without inventing numerical scientific margins. Let `[L,U]` denote an uncertainty interval justified by the sampling design. Lock the primary population, statistic, matching policy, exclusions and margin before final scoring. Use one primary comparison per decision; label other radii, strata, models and operating budgets exploratory or specify multiplicity handling. Changing a gate after seeing results creates a new exploratory analysis, not a successful preregistration.

| Experiment | Defensible gate and interpretation |
|---|---|
| P1/P2 readiness | Immutable split files reproduce assigned roles; every training window and fitted preprocessing object passes exclusion/provenance checks. Historical unknowns stay unknown. Identical block lists alone do not certify leakage absence. |
| 3.0 archival check | Reproduce the historical sweep from its original objects and policy. Explain every discrepancy attributable to artifacts or encoding. Separately test the new pipeline against a frozen, adequately precise reference artifact. Neither is a scientific transfer success. |
| 3.1 transfer | Define `d = target recall - comparable reference recall` at K=40 per eligible km². Success if `L > -Δ`; meaningful unacceptable loss if `U < -Δ`; otherwise inconclusive. Set Δ from tolerated missed-feature burden, not fold spread. Propagate uncertainty from both populations. Report target density and the prespecified density-scaled sensitivity separately. |
| 3.3 slope | Report feature counts, independent clusters and recall by fixed slope strata. Treat differences as associations. A controlled edit must preserve realistic backgrounds, recompute derivatives and include sham edits. Neither result alone gates all flat-region feasibility. |
| 4.5 change | First demonstrate recoverability of a specified physical change through the full preprocessing chain at relevant sizes, slopes and seams. Then define a useful difference `δ_rate` in eligible-pad flag rates. Success if `L > δ_rate`; evidence against a useful rate increase if `U < δ_rate`; otherwise inconclusive. A physical height threshold is a separate measurement specification. Use dated restoration and eligible non-restoration controls; causal wording still requires justified exchangeability. |
| 4.6 history | Source passes for a stated use when provenance, legibility, coverage and total positional uncertainty meet that use's requirements, independent of detector score. Record usable/unusable/inconclusive per source/date. Test correspondence to lidar or records only afterward. |
| 5.6 association | Exploratory excess answers whether observed association exceeds a specified spatial null. A deployment gate instead uses independently adjudicated link PPV with unresolved bounds, compared with a crew-defined minimum. Coordinate correction needs a separate paired-error endpoint on independent identities. Passing an active-pad positive control cannot establish validity in a different target cohort. |
| A6 / 5.4 | No recall-equivalence or density gate from spatial excess alone. Report cohort association differences. Permit a recall margin only when independently verified denominators, coordinate error and sampling eligibility support actual sensitivity. Density remains conditional bounds until distinct-well precision and recall refer to the same population. |
| 5.1 context | Define useful gain `δ_gain` in recall/ranking benefit at K=40 based on downstream value and cost. Success if `L > δ_gain`; evidence against useful gain if `U < δ_gain`; otherwise inconclusive. A positive but too-small effect can be real without justifying deployment. |
| 6.3 confusers | Prespecify useful reduction in confuser detections/km² and acceptable feature-recall loss. Require both benefits using paired blocks and matched baseline/random-negative arms. Blindly adjudicate the union of each arm's top-K output and evaluate feature recall against independent complete labels. Preserve uncertainty classes. Seeds characterize training variability, not new landscapes. |
| 4.1 / 6.5 pilot | Instrument controls, repeatability, localization and field throughput establish operational readiness only. Three to five sites cannot pass population sensitivity or well-precision gates. Methane non-detection is conditional on the instrument, visit and environmental conditions. |
| 7.5 field | Predefine frame and inclusion weights for each of the three arms. Report weighted outcome proportions, identity bounds incorporating every ambiguous/access-failed case, and sampling uncertainty. Scale only if those bounds can change the stated decision at acceptable effort. Conditional search recall stays conditional unless search sensitivity is independently constrained. |
| 4.2 / 4.3 | Establish observable target support and an independently motivated useful contrast before sampling. Detecting that contrast establishes surface-condition evidence. An upper bound below it excludes that specified contrast under studied acquisitions, not leakage or a finer-resolution signal. |
| 4.7 | Report a paired within-acquisition response curve over retained ground density, with selection and thinning uncertainty. No universal density threshold or cross-platform equivalence claim. |
| 7.1 / 7.2 | Declare whether the benefit is per label, reviewer-hour, total compute or total cost; evaluate under that resource constraint. Use an independent stopping set and final area. Candidate discovery must include random areas. Scale only when the interval clears a decision-based useful improvement. |

The existing radar result remains valuable as a **scoped negative experiment**. `plan_mod_more_radar.md:30` appropriately separates the held-out 613590 pit result from the 9t ceiling and pad-only local evidence. Preserve the tested product/feature/area/operating-point scope. Do not silently translate a cutoff-based radar comparison into the newly selected fixed-budget K=40 policy without evaluating that policy.

## D. Feasible sequence and critical path

**Can begin now as desk work:** correct the estimands and gates; separate historical and new baseline definitions; audit catalogue geometry/query accounting; inventory immutable split/provenance requirements; specify field identity classes and independent sampling frames; inspect historical coverage indexes and flight-date metadata. Retrospective 9t slope analysis and repaired spatial association can be informative exploratory diagnostics once their inputs are correct. None requires a national lidar expansion.

**First bounded information-gathering work:** a historical-source legibility/position pilot, a blind annotation/codebook throughput pilot, and one target-footprint coverage check. These answer whether independent evidence and adequate labels can actually be obtained. They should determine sample size and resource estimates before extensive model code is written. The user will handle the already-decided requests; this review does not authorize contacting anyone.

**Transfer critical path:** comparable baseline/policy → verified target footprint and data conditions → reviewer capacity and blind complete-block label pilot → decision-based margin and target precision forecast → frozen scoring. Warren is a local case study; McKean adds a contrast but does not isolate a sensor effect. Keep native information primary and any thinning experiment separate.

**Identity critical path:** field partner/access plus independent confirmation protocol → probability sampling with recorded refusals and ambiguity → feature-to-well and candidate-precision bounds. Historical sources can contribute independently while field access is arranged. This path determines whether later density, risk and agency outputs have defensible well-level meaning.

**Change critical path:** usable acquisition-date bounds and independently dated restoration → eligible treated/control population → full-chain signal recovery → appropriately powered comparison. If the dates cannot classify exposure, stop the intervention claim without interpreting that as evidence that restoration is invisible.

**Wait:** additional regions, shared-fold context retraining, active learning, pretraining, benchmark packaging and agency tooling. Each could generate outputs now, but none resolves the central feature-to-well uncertainty efficiently. An exception is a genuinely cheap, prespecified diagnostic that changes which of these investments is worthwhile.

Resource estimates must separate coding, machine time, annotation, adjudication, access and calendar delay. The current protocol correctly recognizes that the former A0–A9 estimate totals roughly 49 hours before debugging (`protocol_gates_and_metrics.md:139`). That is arithmetic, not evidence of total completion time. Measure one actual annotation block and inference run. Do not replace the old estimate with another unsupported number. Catalogue compressed-byte totals also need complete coverage and explicit derivative/decompressed storage before becoming a download budget.

## E. Strongest surviving ideas

**Historical-source probing remains unusually valuable.** A valid positive can establish historical presence even when lidar scores are poor; a carefully documented failure can show that a particular source/date cannot support individual matching. It directly addresses an evidence gap that additional terrain models cannot fill. It must not be selected for agreement with those models.

**The three-arm field design is the program's most important redesign.** Separate frames for drawn features, candidates and independently searched areas finally separate the questions of feature identity, candidate precision and missed wells. Correct ambiguity bounds and access accounting can produce useful negative results: for example, evidence that the confirmed-well yield of a specified candidate class is too low to justify deployment. A broad unidentified remainder is an inconclusive result, not a negative one.

**A bounded Warren transfer experiment is still worth doing.** It tests whether useful feature detection survives a specific move within the acquisition program. A precise unacceptable loss would prevent wasteful national scaling; acceptable transfer would justify one deliberately chosen next contrast. It cannot establish national applicability or well identity.

**Confuser training has a strong, testable local question.** The revised equal-count random-negative comparison and pooled blind adjudication help distinguish targeted confuser learning from simply adding labels. Retaining possible-well outcomes prevents an apparent precision gain from hiding the removal of uncertain positives. Its value is reduced review burden, not verified well discovery unless field evidence supplies that link.

**The narrow radar negative result and properly gated change experiment deserve preservation.** A negative result is useful when its interval excludes a benefit that matters under a stated operating policy. Change detection can similarly delimit detectable restoration signatures after timing and signal recovery are established. Neither should be turned into a universal sensor-failure claim.

**Association repair is useful but secondary.** It can reveal which spatial relationships survive correct counting and null construction. It cannot cheaply replace identity validation, and a nonzero excess should not trigger density or coordinate-correction products by itself.

## Questions whose answers would most change these recommendations

1. **What independent evidence will adjudicate a sampled site as a well or a definite non-well, and what can the field team actually search?** This determines whether the central identity study can yield narrow bounds at all.
2. **At K=40, how many additional missed features or unproductive visits would change the intended operational decision?** Those answers define the margins; source-area variance cannot define them.
3. **Which exact model and proposal policy will be deployed in a new area, and are original unquantized fold predictions/candidate artifacts available for its reference?** This determines whether transfer comparison is coherent and reproducible.
4. **Do independent historical sources or surveyed well identities cover the target footprint, with useful positional uncertainty and a documented selection mechanism?** Existence alone is insufficient, but a positive answer could move identity validation ahead of further model work.
5. **Can reviewers, field access and restoration/acquisition dates be secured for enough independent units?** These external dependencies, rather than the ease of producing code or maps, determine the feasible critical path.

K, McKean scope, DEP-point visibility during annotation, and responsibility for outreach are already decided. They are not reopened by this review.
