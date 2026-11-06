# Adversarial Codex Review of Research Expansion Plans

**Reviewer:** Codex, acting as an independent adversarial scientific reviewer.
**Date:** 2026-11-04
**Repository:** C:\Users\colto\Documents\GitHub\lidar_project
**Scope:** Review of the current research expansion plans and supporting evidence. This review is not authorization to execute the plans.

---

**Overall judgment: preserve a small evidence-building program, but do not execute the expansion portfolio as written.** The strongest directions are independent historical evidence, a bounded field-method pilot, a properly isolated nearby transfer test, and confuser reduction. Density estimation, coordinate correction, and operational risk ranking remain unsupported.

The most consequential findings are:

1. **The saved association and recall-gap studies use unmatched candidates, not the full detector output.** A filtering bug removes all 481 matched pit detections. The pad input also contains only unmatched leftovers. Their low detection rates cannot support conclusions about overall well recall or justify stopping association work.
2. **The original training sampler can read held-out pixels and labels.** An isolated pad implementation already corrects this, but the transfer plans still reference the original model family. Saving block lists alone does not repair the leakage.
3. **The Warren preregistration compares different estimands.** Its “fixed K” depends on the number of test annotations, while its reference recall comes from an F2-selected threshold.
4. **Independent searches are necessary but insufficient to identify well recall.** Field searches themselves miss wells. Magnetometry establishes a magnetic anomaly, not necessarily a well; historically important wells without detectable casing remain a blind spot.
5. **The current plans contain substantial, useful corrections.** I credit the separation of features from wells, the corrected density equation, rejection of unmatched-as-negative labels, independent historical interpretation, and one-time final audits. Those corrections need to be carried through the scripts and supporting documents.

I read the README, all 37 individual plans, both supporting expansion documents, and relevant code and saved artifacts. Checks were read-only; I did not train models, execute the plans, contact anyone, or modify repository files.

**A. Coverage table**

“Proceed” below means the stated preparatory work is defensible. It does not authorize execution. “Blocked” identifies an unavailable dependency; “redesign” identifies an inadequate experiment.

| ID and filename | Decision | Evidence legitimately obtainable | Main unresolved issue | Smallest defensible next step |
|---|---|---|---|---|
| [README.md](C:/Users/colto/Documents/GitHub/lidar_project/docs/plans/README.md:5) | Redesign | Consistent study rules | Fixed buffer and evidence categories do not guarantee valid inference | Establish one authoritative protocol and dependency list |
| P1 [plan_prereq_splits_manifests.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/0_prerequisites/p1_splits_manifests/docs/plan_prereq_splits_manifests.md:11) | Proceed | Reproducible future partitions | Exported splits are not recovered historical train/validation splits; sampler leakage persists | Audit actual pixel support, then specify new immutable splits |
| P2 [plan_prereq_audit_set.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/0_prerequisites/p2_audit_set/docs/plan_prereq_audit_set.md:11) | Proceed | Documented evaluation independence | No demonstrated untouched 9t audit population | Inventory exposure; reserve a new area if history is uncertain |
| 3.0 [plan_geo_transfer_protocol.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_0_transfer_protocol/docs/plan_geo_transfer_protocol.md:11) | Redesign | Feature detection in a defined target footprint | Model choice, ranking budget, baseline and label completeness | Define one deployable pipeline and comparable evaluation |
| 3.1 [plan_geo_warren_forest.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_1_warren_forest_mckean/docs/plan_geo_warren_forest.md:9) | Bounded pilot | Nearby, same-program feature transfer | Warren draft’s K/reference mismatch; Forest unverified | Inventory existing Warren tiles and design blind complete-block labels |
| 3.2 [plan_geo_appalachian_states.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_2_appalachian_states/docs/plan_geo_appalachian_states.md:7) | Defer | County case studies | No verified county inputs; one county cannot identify state effects | One candidate-county inventory after Warren |
| 3.3 [plan_geo_low_relief_midwest.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_3_low_relief_slope/docs/plan_geo_low_relief_midwest.md:11) | Bounded pilot | Frozen-model sensitivity to controlled terrain edits | Synthetic realism and limited external validity | Paired realistic edits, shams and natural low-slope examples |
| 3.4 [plan_geo_gulf_east_texas.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_4_gulf_texas/docs/plan_geo_gulf_east_texas.md:5) | Defer | Feature performance by wetness/coverage | Records are not automatically accurate coordinates; ground visibility | Verify one footprint and record reliability fields |
| 3.5 [plan_geo_oklahoma_kansas.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_5_oklahoma_kansas/docs/plan_geo_oklahoma_kansas.md:11) | Defer | Incremental modality value on common sites | No established matched acquisition/label population | Coverage intersection and temporal-eligibility table |
| 3.6 [plan_geo_california.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_6_california/docs/plan_geo_california.md:11) | Defer | Observable pad/equipment detection | Distinct target and many wells per pad | Define the observable target and its decision use |
| 3.7 [plan_geo_canada.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_7_canada/docs/plan_geo_canada.md:11) | Defer | Regional feature case studies | Coverage, licensing and local interpretation | Province comparison using actual metadata |
| 3.8 [plan_geo_alaska.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_8_alaska/docs/plan_geo_alaska.md:11) | Defer | LOS displacement near known wells | Coherence, stable reference and thaw/hydrology confounding | Metadata-only feasibility assessment |
| 4.1 [plan_mod_magnetometry.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_1_magnetometry/docs/plan_mod_magnetometry.md:11) | Bounded pilot | Anomaly detectability and survey practicality | Casing condition, confusers and localization error | Known casing, metal-confuser and blank-site protocol |
| 4.2 [plan_mod_thermal.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_2_thermal/docs/plan_mod_thermal.md:11) | Redesign | Surface-temperature contrast at sensor support | Target dilution and canopy; unclear useful effect | Estimate visible target fraction and detectable contrast first |
| 4.3 [plan_mod_vegetation_stress.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_3_vegetation_stress/docs/plan_mod_vegetation_stress.md:11) | Redesign | Vegetation differences around disturbances | No leak labels or demonstrated triage benefit | Choose morphology screening or independently labelled leakage as the question |
| 4.4 [plan_mod_methane_plumes.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_4_methane_plumes/docs/plan_mod_methane_plumes.md:11) | Defer | Catalogue-specific regional association | Targeted observation and source attribution | Audit usable observation footprints and source localization |
| 4.5 [plan_mod_multitemporal_lidar.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_5_multitemporal_lidar/docs/plan_mod_multitemporal_lidar.md:9) | Blocked | Pad-scale terrain change associated with dated work | Flight dates, earthwork labels and suitable controls | Establish flight bounds and actual restoration eligibility |
| 4.6 [plan_mod_historic_maps_aerials.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_6_historic_maps_aerials/docs/plan_mod_historic_maps_aerials.md:11) | Bounded pilot | Historical surface evidence independent of lidar | Symbol identity, displacement and selective visibility | Several sources/dates, known-positive checks and independent registration checks |
| 4.7 [plan_mod_drone_lidar.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_7_drone_lidar/docs/plan_mod_drone_lidar.md:9) | Blocked | Conditional sensitivity to thinning one acquisition | Unverified point-cloud provenance and selected “63” sites | Verify dataset identity and site-selection/confirmation history |
| 4.8 [plan_mod_leafoff_optical.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_8_leafoff_optical/docs/plan_mod_leafoff_optical.md:11) | Bounded pilot | Coverage and interpretable surface corroboration | Visible-ground fraction; absence is not rejection | Inspect a small, predefined chip sample |
| 4.9 [plan_mod_more_radar.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_9_more_radar/docs/plan_mod_more_radar.md:11) | Defer | Scope-limited negative evidence | No new signal-specific rationale | Preserve existing result with its actual uncertainty and population |
| 5.1 [plan_task_context_features.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_1_context_features/docs/plan_task_context_features.md:11) | Redesign | Incremental feature-ranking benefit | Nested upstream exclusions and annotation-context bias | Trace every outer-fold upstream model before fitting |
| 5.2 [plan_task_era_classification.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_2_era_classification/docs/plan_task_era_classification.md:9) | Blocked | Era prediction within validated date support | Old wells lack reliable dates; pad reuse | Audit date meaning and identity-linked historical bounds |
| 5.3 [plan_task_risk_ranking.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_3_risk_ranking/docs/plan_task_risk_ranking.md:9) | Defer | Scenario sensitivity and exposure summaries | Existence probability and hazard are unidentified | Define a decision and independently measurable hazard endpoint |
| 5.4 [plan_task_undocumented_density.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_4_undocumented_density/docs/plan_task_undocumented_density.md:11) | Proceed, sensitivity only | Identifiability analysis and conditional bounds | Well precision/recall and counting units | List unidentified terms; withdraw reliance on current recall-gap result |
| 5.5 [plan_task_polygon_area_cost.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_5_polygon_area_cost/docs/plan_task_polygon_area_cost.md:11) | Bounded pilot | Repeatability and error of visible footprint area | Drawn footprint versus restoration footprint | Independent redraws with explicit boundary definitions |
| 5.6 [plan_task_record_association.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/5_tasks/5_6_record_association/docs/plan_task_record_association.md:11) | Redesign | Proximity evidence; later, independently checked association accuracy | Wrong candidate inputs and unverified null | Repair input contract and declare exploratory reanalysis |
| 6.1 [plan_adj_co2_geothermal.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_1_co2_geothermal/docs/plan_adj_co2_geothermal.md:11) | Defer | Screening-layer usefulness | No completeness or integrity evidence | Define the partner decision and required subsurface information |
| 6.2 [plan_adj_coal_features.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_2_coal_features/docs/plan_adj_coal_features.md:11) | Defer | Class-specific feature confusion | Inventory position/completeness; new annotation burden | Small inventory-to-imagery identity audit |
| 6.3 [plan_adj_negative_classes.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_3_confuser_classes/docs/plan_adj_negative_classes.md:11) | Bounded pilot | Confuser reduction while preserving feature recall | Morphological consensus may misidentify well features | Pilot the codebook, evidence rules and review-time measurement |
| 6.4 [plan_adj_hydrogen.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_4_hydrogen/docs/plan_adj_hydrogen.md:11) | Defer | Reuse of screening layers | No distinct scientific question | No separate pipeline |
| 6.5 [plan_adj_field_methane.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_5_field_methane/docs/plan_adj_field_methane.md:11) | Blocked | Repeatable concentration enhancement | Instrument access and local source attribution | Instrument-specific background and repeat-measurement protocol |
| 6.6 [plan_adj_sar_viewshed.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/6_adjacent/6_6_sar_viewshed/docs/plan_adj_sar_viewshed.md:11) | Defer | Line-of-sight agreement in a separate project | No contribution to well uncertainty | Separate scope and resource allocation |
| 7.1 [plan_scale_pretraining.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_1_pretraining/docs/plan_scale_pretraining.md:11) | Defer | Label-efficiency benefit on a new area | Baseline integrity and unspecified resource objective | Define total-compute versus annotation-efficiency comparison |
| 7.2 [plan_scale_active_learning.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_2_active_learning/docs/plan_scale_active_learning.md:11) | Redesign | Improvement per reviewer-hour | Candidate-only sampling misses proposal failures | Include random area discovery and a separate stopping set |
| 7.3 [plan_scale_benchmark.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_3_benchmark/docs/plan_scale_benchmark.md:11) | Defer | Reproducible terrain-feature comparison | Current baseline leakage and audit provenance | Release design after P1/P2, with explicit partial-label handling |
| 7.4 [plan_scale_agency_tooling.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_4_agency_tooling/docs/plan_scale_agency_tooling.md:11) | Defer | Reproducible execution and local feature calibration | Scientific input contract not stabilized | Freeze reference pipeline and unsupported-input tests |
| 7.5 [plan_scale_field_campaign.md](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_5_field_campaign/docs/plan_scale_field_campaign.md:11) | Redesign | Candidate verification yield and bounded search recall | Imperfect reference search and inaccessible sites | Separate candidate-verification and independent-area-search designs |

**B. Prioritized findings**

**1. The association and recall-gap inputs exclude successful detections.**

**Severity: invalidates inference. Status: verified. Affects 5.6, 5.4 and any downstream justification using their results.**

The association loader concatenates the matched and undecided pit layers, then filters both with `dup_on_pit == 0`. See [loader, lines 51–55](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py:51).

However, the package builder defines that flag as “centroid inside any annotated pit,” including when packaging matched detections. See [flag construction, lines 249–275](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py:249).

Direct inspection found:

| Layer | Rows | Flag distribution | Retained |
|---|---:|---|---:|
| Matched pits | 481 | All have `dup_on_pit=1` | 0 |
| Undecided pits | 207 | 204 zero; 3 one | 204 |

The pad problem is separate and equally consequential. `_match_rules_pit_pad_9t.py` returns only predictions **not matched to annotations**, then exports those leftovers as `pad_candidates_filtered_heldout_9t.shp`. The association loader uses that file. See [leftover construction and export, lines 190–226](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_match_rules_pit_pad_9t.py:190).

The recall-gap script calls the same `ra.load()`. See [lines 61–79](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_recall_gap_newly_documented_9t.py:61).

**Failure mechanism:** successful feature detections are systematically removed before measuring proximity to records. The resulting statistic concerns residual unmatched candidates. The reported 22/141 versus 0/6 therefore is not full-detector well recall.

**Minimum correction:** define and verify a complete prediction input; retain matched detections; use a deployment-compatible deduplication rule; distinguish full-output association from novel-candidate association. Recompute later as an explicitly corrected exploratory analysis.

**Still unknowable:** whether nearby detections identify the correct well, actual coordinate improvement, and recall for genuinely undocumented wells. The corrected analysis might change the numerical result in either direction.

---

**2. Spatial isolation is not implemented by the original samplers, and the split exporter cannot recover historical splits.**

**Severity: invalidates claims of fully isolated validation; materially weakens generalization estimates. Status: verified. Affects P1/P2, 3.0–3.7, 5.1, 6.3, 7.1–7.4.**

The original pit trainer says `block_bounds` prevents patches reaching held-out ground. That statement is contradicted by the sampler:

- Feature-centered sampling jitters coordinates without checking block containment.
- Background sampling chooses a center inside a block.
- The whole feature and label window is then read, clipped only to raster boundaries.

See [trainer assertion](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py:363) and [sampler implementation](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/_dl.py:249).

**This is partly corrected already.** The isolated pad trainer explicitly rejects windows intersecting held-out blocks. Its saved report shows recall falling from 0.912 to 0.891 under the F2 comparison. I am not treating that corrected implementation as still having the original window bug. See [isolated trainer](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py:1) and [comparison](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/nisar_checks_9t.md:135).

But the transfer protocol points to the original family, and P1 addresses block lists rather than the actual windows.

Separately, the split exporter drops NaN rows before reconstructing splits. The historical trainers did not. The calibration report states that the original inner splits cannot be uniquely recovered. See [exporter](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s3_train/_save_cv_split_manifests_9t.py:33) and [historical reconstruction failure](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/cv5_threshold_free_pr_and_calibration_pit_pad_9t.md:62).

**Minimum correction:** distinguish historical held-out assignments, unknown historical inner splits, and newly specified future splits. Enforce full-window exclusion, fold-local fitted preprocessing, and immutable model/data/split provenance. Invalidate stale caches when those inputs change.

A blanket 500 m buffer is not a proof of independence. It must cover feature construction, patch/context support and relevant spatial dependence. Nearby pits on one pad or lease may still form one effective cluster.

**Still unknowable:** the exact amount of optimism in the original pit results without controlled retraining; the isolated pad comparison does not establish it for pits or repair all other selection effects.

---

**3. Warren’s success criterion does not compare the same quantity.**

**Severity: invalidates the proposed pass/fail inference. Status: verified. Affects 3.0/3.1 and later transfer studies.**

The draft specifies:

- K equals the number of annotated features in the test footprint.
- Reference recall is 0.928 at an F2 cutoff.

See [Warren preregistration, lines 29–30](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/transfer_warren_prereg.md:29).

**Failure mechanism:** the review budget changes with test prevalence and annotation completeness. The reference is threshold-based rather than recall at that same budget. An apparently successful transfer could simply receive more candidates to review.

The saved 613590 CSV genuinely contains 153 floors and the reported threshold-based transfer results. It does not supply a fixed-budget comparison, and its five models evaluate the same target tile—not five independent landscapes. See [saved transfer results](C:/Users/colto/Documents/GitHub/lidar_project/data/_comparisons/pit_heldout_and_transfer_2026-09-20/613590_transfer_from_9t_cv5_05/pit_transfer_recall_per_fold_613590_05.csv:1).

**Minimum correction:** set a review budget from reviewer capacity, expressed as candidates per eligible area or total candidates for a specified footprint. Fix proposal extraction, model/ensemble policy and tie handling. Recalculate the reference at exactly that rule. Independently enumerate features in complete test blocks, including blocks with no features.

**Still unknowable:** county-wide performance from a convenience subset, well identity from feature labels, and general transfer to other acquisition programs.

---

**4. The repaired association null still has population and assignment problems.**

**Severity: materially weakens inference. Status: verified implementation; adequacy of the null unverified. Affects 5.6 and recall-gap interpretation.**

I credit the repair that includes zero-detection blocks and translates the record set together. It does not complete the audit.

The script uses the **pit** footprint for both modalities. Direct manifest checks found 115 pit blocks and 129 pad blocks: five pit blocks lack pad-CV coverage, while 19 pad blocks are omitted by the pit footprint. See [shared footprint assignment](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py:102).

The null translates an already footprint-filtered record set and drops shifted points outside coverage. Thus the number and composition of records change with each shift. Preserving initial clustering does not establish exchangeability across spatial gradients in oil development, roads or mapped-feature availability. See [null loop](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py:109).

Finally, Hungarian assignment is run separately by status. The saved proposal table has **44 more assignments than unique detection coordinates**, so one-to-one is not global.

**Minimum correction:** use modality-specific coverage or a declared common intersection; specify edge treatment and conditioning variables; verify the null preserves the relevant sampling opportunity. Either assign globally across statuses or explicitly label outputs as separate competing proposals.

**Still unknowable:** false-association probability. A spatial excess is not an estimate of how many accepted links are correct.

---

**5. The field campaign cannot automatically identify total well recall or density.**

**Severity: invalidates population-density inference if unresolved. Status: design gap. Affects 4.1, 5.4, 5.6, 6.1, 6.4, 7.5.**

The field plan correctly adds independent sampled-area searches. But its claim that field visits can establish whether the detector misses wells requires a reference search with known or bounded sensitivity. See [field plan](C:/Users/colto/Documents/GitHub/lidar_project/expansions/7_scale/7_5_field_campaign/docs/plan_scale_field_campaign.md:3).

Steel-casing magnetometry can miss removed or wooden casing. NETL explicitly describes that limitation. Anomaly locations also need not coincide exactly with boreholes. [NETL’s Oil Creek account](https://netl.doe.gov/node/9506).

The density equation \(Dp/r\) is algebraically appropriate only when:

- \(Dp\) counts distinct true wells represented in the candidate population;
- \(r\) concerns the same eligible well population;
- multi-feature/multi-well relationships are resolved;
- documentation and acquisition scope align.

The plan acknowledges several of these requirements. Its dependence on 7.5 nevertheless promises more than that campaign currently identifies.

**Minimum correction:** separate candidate confirmation from probability-sampled area searches. Specify positive, negative and unresolved reference outcomes; assess search detection using complementary evidence or repeat independent searches; retain access failures. If search sensitivity cannot be identified, report conditional recall or bounds, not total-well recall.

**Still unknowable:** wells with neither observable terrain nor detectable casing nor interpretable historical evidence. A narrow interval around a model estimate does not resolve that missing population.

---

**6. The “63 wells” premise is overstated; records also do not guarantee survey-grade positions.**

**Severity: execution risk and materially weakens inference. Status: partly contradicted, partly unverified. Affects 4.7, 5.6, 3.4.**

Plan 4.7 begins with drone lidar covering 63 wells. The primary NETL account says **63 potential well sites on two hillsides identified using lidar**. It does not establish 63 independently confirmed wells, released drone point clouds, or an unbiased sensitivity sample. The current plan’s request for selection provenance is a useful correction, but the opening premise remains unsupported. [Plan](C:/Users/colto/Documents/GitHub/lidar_project/expansions/4_modalities/4_7_drone_lidar/docs/plan_mod_drone_lidar.md:3), [NETL source](https://netl.doe.gov/node/9506).

Likewise, the Gulf plan’s “confirmed locations” wording is too strong for an administrative layer alone. RRC distinguishes location reliability and coordinate sources. [Plan](C:/Users/colto/Documents/GitHub/lidar_project/expansions/3_geography/3_4_gulf_texas/docs/plan_geo_gulf_east_texas.md:5), [RRC GIS reliability guidance](https://www.rrc.state.tx.us/media/xstf1eog/rrc-public-gis-viewer-tool.pdf).

**Minimum correction:** verify dataset identity, acquisition platform, spatial coverage, coordinate method, site selection and confirmation status before specifying the experiment.

Repeated thinning is valuable, but estimates sensitivity to retained points **within that acquisition**. It does not reproduce another platform’s footprint, scan geometry, occlusion or ground-classification errors.

**Still unknowable:** representative well sensitivity and the causal effect of replacing statewide airborne lidar with drone lidar.

---

**7. Complete feature labels, confuser labels and independent well evidence are different reference standards.**

**Severity: materially weakens inference. Status: verified design limitation. Affects 3.x, 4.6/4.8, 5.1/5.5, 6.2/6.3, 7.2/7.3.**

The confuser codebook’s positive category explicitly uses access traces and plausible oil-field setting. Context features can therefore improve agreement with how annotators searched and classified, even without improving well discovery. See [codebook](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/confuser_codebook.md:5).

Two blinded reviewers reduce score-induced bias; agreement does not prove identity. A hearth, road landing and well pad can also coexist spatially.

Candidate-only active learning cannot discover positives absent from the proposal pool. A score-stratified audit estimates properties of that candidate population, not all terrain features.

**Minimum correction:** define the target morphology independently of model scores; distinguish morphological confusers from externally established non-well causes; preserve ambiguous/mixed-use sites. Include independently searched complete areas and random-area discovery in evaluation. For context stacking, outer-fold exclusions must apply to models producing both second-stage training and test features.

**Still unknowable:** whether morphology-specific gains improve undiscovered-well yield without independent confirmation.

For polygon area, redraw agreement is a useful reproducibility result. It does not establish excavation, contamination or restoration area, much less total plugging cost.

---

**8. Several modality plans lack an observability gate before statistical testing.**

**Severity: materially weakens inference. Status: physical concern supported by primary specifications; site-specific magnitude unverified. Affects 4.2–4.5, 3.8.**

For thermal work, Landsat TIRS has 100 m native sampling resampled to 30 m; ECOSTRESS products are approximately 70 m. A smaller delivered pixel is not additional target information. [NASA Landsat specification](https://science.nasa.gov/mission/landsat-8/), [ECOSTRESS guide](https://lpdaac.usgs.gov/documents/423/ECO2_User_Guide_V1.pdf).

A pad/control temperature difference can arise from canopy, emissivity, soil moisture and clearing history. Vegetation differences can similarly reflect disturbance and succession. Covariate adjustment alone does not establish leakage.

Methane catalogue availability is verified, but detection opportunity depends on environmental conditions and observation targeting. Observation counts alone do not remove selection toward known emitters. A plume footprint is also not equivalent to a source-location uncertainty region. [Carbon Mapper product guide](https://data.carbonmapper.org/product_guide.pdf).

**Minimum correction:** first quantify target fraction, usable acquisitions, effective spatial support, registration uncertainty and plausible signal relative to variability. Specify a meaningful screening or physical contrast. Model repeated observations at site/source level. For Alaska, specify LOS displacement, reference stability and seasonal confounding before discussing well-related thaw.

**Still unknowable:** leakage or causal well effects from these associations alone. A sufficiently precise satellite null can rule out a specified observable contrast; it cannot rule out a finer-scale drone signal.

---

**9. The lidar-change plan needs controls matched to the intervention, not merely terrain noise.**

**Severity: materially weakens inference. Status: verified. Affects 4.5.**

The flight-date block is correct and should remain. But the inherited control script excludes locations near mapped pads, pits and roads, then matches slope. See [control construction](C:/Users/colto/Documents/GitHub/lidar_project/notebooks/wellsight_v2/s7_analysis/_change_features_9t.py:69).

**Failure mechanism:** ordinary terrain is not exchangeable with a site eligible for plugging and restoration. Differences can reflect routine disturbance, drainage or regrading unrelated to plugging.

The saved v2 summary confirms 19/404 flagged pads versus about 15.3 expected from its measured placebo rate. That is not evidence of equivalence or absence of restoration. [Saved summary](../../data/9t/results/change/change_features_summary_v2_9t.json:1).

The 3,368 m² patch threshold belongs to a particular spatial-null/classification procedure. It is not a universal physical minimum detectable change area. High-pass processing also changes what spatial scales remain measurable.

**Minimum correction:** use independently dated earthwork where possible, distinguish plugging from surface restoration, and compare similarly eligible pads without the intervention. Test signal recovery through the complete processing chain at relevant sizes, slopes and seam locations.

**Still unknowable:** whether a plugged well was properly sealed, or whether a terrain change was caused by plugging without additional intervention evidence.

---

**10. Statistical gates and uncertainty must match the decision and effective sample.**

**Severity: materially weakens inference. Status: verified omissions. Affects most experiments.**

Many acceptance tests require a table, protocol or successful execution. Those are readiness gates, not scientific success criteria.

The field sample-size arithmetic is reasonable as an approximation for one simple-random-sample proportion. The correction that 40 sites cannot support five precise bin estimates is valid. But repeated site visits do not create independent wells, repeated model seeds do not create independent landscapes, and additional bootstrap draws do not create additional spatial clusters.

The revised active-learning plan correctly checks the final audit once. Pretraining should similarly distinguish:

- benefit at a fixed annotation budget;
- benefit at a fixed total compute budget;
- benefit after accounting for pretraining cost.

“Match budgets exactly” cannot mean all three simultaneously without specifying the comparison.

**Minimum correction:** choose one primary estimand, decision margin and sampling unit; justify margins from use or detectable physical effects; size for interval width using plausible clustering and unresolved outcomes. Use development data for selection, with one final comparison. Treat site-seasons, candidates per pad and repeated observations as dependent.

**Still unknowable:** broad geographic generality from one or two independent areas.

---

**11. Data readiness is mixed; the existing files support reconnaissance, not the calendar.**

**Severity: execution risk. Status: verified locally, otherwise explicitly unverified.**

Verified locally:

- Seven Warren LAZ files exist.
- Their headers report NAD83(2011)/UTM 17N plus NAVD88/Geoid12B, contradicting the earlier statement that CRS is absent. Their file creation date is not a flight date. [Earlier claim](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/lidar_pumpjack_pilot_warren.md:10).
- Pit/pad manifests contain 712/995 rows, with 209/345 missing block IDs.
- Five checkpoints exist in each original pit, original pad and isolated-pad model directory.
- The DEP file contains 20,108 records; 997/1,079 orphan-list spud dates are the 1800 sentinel.

The Warren filenames identify the same D20 program cited for 9t. Calling the planned comparison “different lidar” is not established merely by changing county.

USGS specifies QL2 aggregate nominal **pulse** density of at least 2 pulses/m², not guaranteed ground-return density. The plans’ warning is correct; their separate two-ground-points/m² eligibility threshold still needs justification. [USGS specification](https://www.usgs.gov/ngp-standards-and-specifications/lidar-base-specification-tables).

The codebook’s budget implies **30 reviewer-hours for 150 candidates with two reviewers**, before adjudication. It is an estimate, not measured throughput. Existing Warren files also include a roughly 2.61 GB merged LAS alongside roughly 312 MB of compressed source tiles, demonstrating why download size is not working-storage size.

**Minimum correction:** distinguish inventory time, annotation labor, machine runtime and calendar dependencies. Benchmark a small real workflow before extrapolating. Other regions’ coverage, field partners, instruments, costs and point-cloud access remain **not assessable from the available verified evidence**.

---

**12. Supporting documents still contain conflicting scientific instructions.**

**Severity: execution risk; some conflicts would invalidate inference. Status: verified.**

The gameplan explicitly overrides many old instructions, so I do **not** count the superseded half-score, overlapping-interval or three-day rules as the current intended design.

Nevertheless, the methods document still proposes between-state variance from one county per state, uses historical absence as an era target, and claims a domain-classifier AUC can attribute transfer failure. The individual plans correctly reject or soften these. See [methods, state comparison](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/expansion_options_methods.md:102), [domain-classifier claim](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/expansion_options_methods.md:65), and [era method](C:/Users/colto/Documents/GitHub/lidar_project/docs/iterations/expansion_options_methods.md:365).

A domain classifier diagnoses distinguishability under its features and design. It does not identify the cause of detector failure.

The CO₂ plan’s narrowed screening claim is appropriate. Class VI requirements include subsurface penetrations, construction, depth and plugging information; a surface inventory cannot establish that completeness. [40 CFR 146.84](https://www.ecfr.gov/current/title-40/chapter-I/subchapter-D/part-146/subpart-H/section-146.84).

**Minimum correction:** mark obsolete methods in place and make the individual plan plus finalized preregistration authoritative. Remove downstream promises not supported by upstream evidence.

**Still unknowable:** operational usefulness until a specific user decision and evaluation are defined.

**C. Revised experimental gates**

| Experiment family | Readiness gate | Success / failure / inconclusive rule |
|---|---|---|
| P1/P2 and transfer infrastructure | Verified complete prediction inputs; explicit model/split hashes; zero forbidden training-window overlap; documented preprocessing and audit history | Reproduction establishes implementation fidelity only. Failure blocks confirmatory use; unknown history requires a new test area |
| Geographic transfer | Fixed review capacity, complete blind labels, common matching rule, justified spatial separation and comparable reference | For \(\Delta=R_\text{target}-R_\text{reference}\), noninferiority if the interval lies above \(-M\); meaningful inferiority if wholly below it; otherwise inconclusive. Choose \(M\) from tolerable missed-feature burden |
| Context, confusers and modality fusion | Nested leakage audit; same eligible sites; matched review/tuning effort; validation-selected settings | Require an interval supporting useful benefit and acceptable recall loss. A failed implementation is not evidence the mechanism cannot help |
| Historical/leaf-off probes | Source interpretation, visibility, dates and independent positional checks | Usable if evidence can be interpreted and localized for the stated task; unusable for that source/scale if not; inconclusive when coverage or interpretation is insufficient. Never gate historical truth on lidar score |
| Terrain edits and drone thinning | Plausible edits, shams, derivative recomputation, repeat realizations | Report conditional paired response and uncertainty. Conclude robustness/sensitivity only to the tested perturbation; no geographic extrapolation gate |
| Thermal/vegetation | Demonstrated observable target support and predefined useful contrast | Detect contrast, exclude a specified useful contrast, or remain inconclusive. No leakage conclusion without independent leakage labels |
| Multitemporal lidar | Bounded flights, eligible dated intervention, adequate spatial support and matched disturbance controls | Estimate intervention-associated change with intervals and recovery checks. No detectable change is distinct from no restoration or no plugging |
| Magnetometry/field methane | Instrument-specific QC, positive/confuser/blank controls, position uncertainty and repeatability | Pilot passes on practical reliable measurement under tested conditions. It does not pass on population sensitivity or well identity |
| Record association | Complete candidates, correct footprints, declared matching unit, independently identified wells | Evaluate association correctness and paired position-error change against original coordinates, including wrong matches and abstentions. Proximity excess alone cannot pass coordinate correction |
| Density | Distinct-well accounting plus defensible bounds on precision, recall and documentation | Produce bounds/sensitivity until identified. If recall can approach zero, acknowledge that a finite useful upper bound may be unavailable |
| Active learning/pretraining | Independent final area; validation-only stopping; explicit labor/compute objective | Compare improvement per stated resource with repeated training variability and spatial uncertainty; wide differences remain inconclusive |
| Risk, costs, screening and tooling | A specific decision, input contract and externally checkable outcome | Reproducibility, rank stability and readability are engineering outcomes. Scientific benefit requires an outcome-based comparison |

**D. Feasible sequence**

1. **First resolve evidence integrity.** Audit the candidate-export contracts, historical versus future splits, sampler isolation, checkpoint selection and evaluation units. The association/recall-gap bug should take precedence over expanding either experiment.
2. **In parallel, pursue information-only feasibility work.** Existing Warren headers and metadata, historical-source probes, leaf-off coverage, acquisition-date bounds and field-method design can be assessed without training. These identify whether later experiments are worth doing.
3. **Reserve an independent area and establish the label protocol.** This is the critical path for transfer, confuser retraining, context models, active learning and benchmark claims. Annotation independence matters more than producing another probability map.
4. **Run one nearby transfer study after its prerequisites.** Warren is the strongest first choice because data exist. Treat Forest separately until verified. Freeze the baseline and comparisons before exposing the final test.
5. **Pilot confuser adjudication before scaling annotation.** Measure ambiguity, external-evidence availability and actual reviewer time. Then test confuser-aware training against equal-effort random-negative augmentation.
6. **Pilot field measurement before a population campaign.** Use known casing, difficult cases and metal confusers. Design area searches separately from candidate verification. Partner access and reference-search sensitivity determine whether density work can advance.
7. **Scale only when an earlier result changes the decision.** One deliberately contrasting region is more informative than many convenience counties. Context/pretraining deserve investment only after the remaining error is characterized.
8. **Keep products downstream.** Benchmark release, agency tooling, risk rankings and storage-screening packages should follow validated input contracts. Hydrogen and viewshed work do not currently resolve a central well-research uncertainty.

**E. Strongest surviving ideas**

- **Historical-source feasibility is high value.** It can reveal model misses without conditioning on lidar scores. An interpretable low-score historical positive is useful evidence, not a failed label.
- **Nearby transfer is scientifically necessary.** A valid negative result would establish that the current frozen detector does not retain useful feature recall under a specified deployment budget in that target landscape.
- **Confuser reduction is worth a bounded experiment.** It directly addresses review workload. Its strongest claim is fewer adjudicated confusers at acceptable feature recall—not improved well identity.
- **Magnetometry plus carefully designed field searches addresses the central identity gap.** The small pilot is valuable even if it shows that equipment, casing conditions or access make a larger survey impractical.
- **Conditional density analysis is useful now.** Showing which unknowns dominate the answer can prevent an attractive but unidentified density map.
- **The existing NISAR negative result should survive with limited scope.** Saved deduplicated AUC gains are −0.004 for pits and −0.008 for pads; the pad interval includes zero. This supports deprioritizing that tested configuration, not rejecting radar generally. [Pit results](C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/nisar/nisar_pit_dedupe_auc_9t_slc.csv:1), [pad results](C:/Users/colto/Documents/GitHub/lidar_project/data/9t/results/nisar/nisar_pad_dedupe_auc_9t_slc_local1500.csv:1).

The answers that would most change my recommendations are:

1. Which independent geographic area and reviewers can be reserved without prior model-output exposure?
2. Is there a genuinely independent well-position/identity dataset, with confirmation method and selection history?
3. What actual decision and review capacity define a useful recall loss or improvement?
4. Can a partner support probability-sampled area searches, including inaccessible and unresolved sites?
5. What are the actual flight-date bounds, and are there records of surface restoration rather than plugging dates alone?
