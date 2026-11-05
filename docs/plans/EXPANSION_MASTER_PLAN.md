# Expansion master plan

**Date:** 2026-11-04
**Status:** plan only. Nothing in the expansion has been run, except a few 9t checks that are marked below. This file is the single entry point. Everything else hangs off it.

## 1. What this program is
The 9t work detects terrain features (pits, pads, roads) in lidar over Venango County, Pennsylvania. The expansion asks four things.
1. Does the detector still work somewhere else (geographic).
2. Can another signal add to it (modality).
3. Can the output do more (task, adjacent uses).
4. Can it be scaled and checked (scale, method).

The central unknown sits under all four. Whether a drawn feature is a well. On 9t only 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m. Four evidence levels stay separate throughout. (a) terrain feature matched to a drawn polygon. (b) historical evidence. (c) steel anomaly. (d) confirmed well. Level (a) results say nothing about wells.

## 2. How the pieces fit
| Document | Role |
|---|---|
| This file | Overview, every idea, order of work, decisions needed |
| [protocol_gates_and_metrics.md](protocol_gates_and_metrics.md) | **Authoritative.** K policy, splits, null rules, gates, field design |
| [review_response_20261104.md](review_response_20261104.md) | What two adversarial reviews changed and what I got wrong |
| [download_manifest.md](download_manifest.md) | Everything to download or request, with gates |
| [download_list_areas_and_lidar.md](download_list_areas_and_lidar.md) | Areas with many old wells, well databases fetched, tile-level lidar lists |
| [README.md](README.md) | Index of the plan files and shared rules |
| [frameworks/README.md](frameworks/README.md) | **One execution framework per process** (37 plus a common one). Stages, scripts, paths, statistics, QC, gates, handoff |
| 37 plan files | One per idea. Review revision blocks at the end of 23 of them match the edited text above them |
| `docs/iterations/expansion_options_methods.md`, `expansion_gameplan_feasibility.md` | Older source documents. Superseded in part by the protocol |
| [adversarial_codex_review_20261104.md](adversarial_codex_review_20261104.md), [adversarial_review_claude.md](adversarial_review_claude.md) | The two reviews |

## 3. Every idea
| ID | Idea | Track | Decision | Data or requests | Plan |
|---|---|---|---|---|---|
| P1 | Reproducible splits and manifests | Foundation | Proceed, rescoped | None | [plan_prereq_splits_manifests.md](plan_prereq_splits_manifests.md) |
| P2 | Audit set and training history | Foundation | Proceed, rescoped | None | [plan_prereq_audit_set.md](plan_prereq_audit_set.md) |
| 3.0 | Transfer protocol | Transfer | Bounded pilot | None. Uses the sweep's own tables, then a clean baseline | [plan_geo_transfer_protocol.md](plan_geo_transfer_protocol.md) |
| 3.1 | Warren and Forest | Transfer | Redesign as within-survey case study | Warren on disk. D1 metadata. Forest D20 window listed. B19 gated | [plan_geo_warren_forest.md](plan_geo_warren_forest.md) |
| 3.2 | Ohio, West Virginia, New York, Kentucky | Transfer | Defer | Windows listed (NY, OH, KY, WV) | [plan_geo_appalachian_states.md](plan_geo_appalachian_states.md) |
| 3.3 | Illinois and Michigan, low relief | Model | Redesign, slope stratification first | IL and MI windows listed, gated | [plan_geo_low_relief_midwest.md](plan_geo_low_relief_midwest.md) |
| 3.4 | Gulf and Texas | Transfer | Defer | LA, TX, AR windows listed, gated | [plan_geo_gulf_east_texas.md](plan_geo_gulf_east_texas.md) |
| 3.5 | Oklahoma and Kansas | Transfer | Defer | OK, KS, MO windows listed, gated | [plan_geo_oklahoma_kansas.md](plan_geo_oklahoma_kansas.md) |
| 3.6 | California | Transfer | Defer | LA window listed | [plan_geo_california.md](plan_geo_california.md) |
| 3.7 | Canada | Transfer | Defer | Not listed. Inventory first | [plan_geo_canada.md](plan_geo_canada.md) |
| 3.8 | Alaska | Transfer | Defer | Not listed. Feasibility note first | [plan_geo_alaska.md](plan_geo_alaska.md) |
| 4.1 | Magnetometry | Evidence about wells | Redesign, then pilot | R3 instrument. Era strata | [plan_mod_magnetometry.md](plan_mod_magnetometry.md) |
| 4.2 | Thermal | Modality | Defer | None until observability gate | [plan_mod_thermal.md](plan_mod_thermal.md) |
| 4.3 | Vegetation stress | Modality | Defer | None | [plan_mod_vegetation_stress.md](plan_mod_vegetation_stress.md) |
| 4.4 | Methane plumes | Modality | Close for Pennsylvania after one check | D4 product guide | [plan_mod_methane_plumes.md](plan_mod_methane_plumes.md) |
| 4.5 | Multitemporal lidar | Evidence about wells | Blocked | D1 flight dates, R7 restoration records | [plan_mod_multitemporal_lidar.md](plan_mod_multitemporal_lidar.md) |
| 4.6 | Historic maps and aerials | Evidence about wells | Proceed as a probe, elevated | D5 to D9 | [plan_mod_historic_maps_aerials.md](plan_mod_historic_maps_aerials.md) |
| 4.7 | Drone lidar | Evidence about wells | Proceed as a request | R2, D12 (size unknown) | [plan_mod_drone_lidar.md](plan_mod_drone_lidar.md) |
| 4.8 | Leaf-off optical | Modality | Bounded pilot | D7, D10 gated | [plan_mod_leafoff_optical.md](plan_mod_leafoff_optical.md) |
| 4.9 | More radar | Modality | Note only | None | [plan_mod_more_radar.md](plan_mod_more_radar.md) |
| 5.1 | Context features | Model | Redesign, shared fold scheme | None. Retrain upstream | [plan_task_context_features.md](plan_task_context_features.md) |
| 5.2 | Era classification | Task | Blocked | Needs 4.6 | [plan_task_era_classification.md](plan_task_era_classification.md) |
| 5.3 | Risk ranking | Task | Defer | None | [plan_task_risk_ranking.md](plan_task_risk_ranking.md) |
| 5.4 | Undocumented density | Task | Identifiability note only | R1 | [plan_task_undocumented_density.md](plan_task_undocumented_density.md) |
| 5.5 | Polygon area and cost | Task | Defer | None | [plan_task_polygon_area_cost.md](plan_task_polygon_area_cost.md) |
| 5.6 | Record association | Evidence about wells | Redesign, repair the input first | Well databases held. R1, R4 | [plan_task_record_association.md](plan_task_record_association.md) |
| 6.1 | CO2 and geothermal screening | Adjacent | Defer | None | [plan_adj_co2_geothermal.md](plan_adj_co2_geothermal.md) |
| 6.2 | Coal features | Adjacent | Defer | None | [plan_adj_coal_features.md](plan_adj_coal_features.md) |
| 6.3 | Confuser classes | Model | Redesign, then pilot | R6 reviewers | [plan_adj_negative_classes.md](plan_adj_negative_classes.md) |
| 6.4 | Hydrogen | Adjacent | Defer | None | [plan_adj_hydrogen.md](plan_adj_hydrogen.md) |
| 6.5 | Field methane | Evidence about wells | Protocol only, with 7.5 | Instrument | [plan_adj_field_methane.md](plan_adj_field_methane.md) |
| 6.6 | Search and rescue viewshed | Adjacent | Defer, separate project | None | [plan_adj_sar_viewshed.md](plan_adj_sar_viewshed.md) |
| 7.1 | Self-supervised pretraining | Scale | Defer | None | [plan_scale_pretraining.md](plan_scale_pretraining.md) |
| 7.2 | Active learning | Scale | Redesign, then defer | R6 | [plan_scale_active_learning.md](plan_scale_active_learning.md) |
| 7.3 | Benchmark | Scale | Defer | None | [plan_scale_benchmark.md](plan_scale_benchmark.md) |
| 7.4 | Agency tooling | Scale | Defer | None | [plan_scale_agency_tooling.md](plan_scale_agency_tooling.md) |
| 7.5 | Field campaign | Evidence about wells | Redesign, highest value | R3, R4, a partner | [plan_scale_field_campaign.md](plan_scale_field_campaign.md) |

## 3b. Review verdicts (third review, 2026-11-04)
Where this table and the Decision column in section 3 differ, this table wins. Verdict is the strongest defensible next scope, not authority to execute. A bounded pilot shows feasibility or local evidence, not population validation. Source. `adversarial_codex_review_revised_20261104.md` coverage table, checked in `review_response_20261104.md` section 8.

| ID | Verdict | Smallest defensible next step |
|---|---|---|
| P1 | Proceed | Immutable future splits, whole-window and normalisation checks. Historical roles stay unknown |
| P2 | Proceed | Inventory every use of each 9t block. Reserve a separate final area |
| 3.0 | Redesign | Separate the archival check from a new frozen policy |
| 3.1 | Bounded pilot | Audit one footprint's coverage. Measure blind annotation effort before sizing |
| 3.2 | Defer | Repair catalogue completeness first. Pick one contrast after 3.1 |
| 3.3 | Bounded pilot | Prespecified retrospective slope diagnostic with counts and uncertainty |
| 3.4 | Defer | Define observable targets. Audit one area's metadata |
| 3.5 | Defer | Verify coverage and target morphology |
| 3.6 | Defer | State an observable target and a decision use. Audit a small example set |
| 3.7 | Defer | Metadata and access inventory only |
| 3.8 | Defer | Observability and stable-reference note |
| 4.1 | Redesign | Correct strata. Pilot known targets, metal confusers and blanks |
| 4.2 | Defer | Quantify target support and detectable contrast first |
| 4.3 | Defer | Choose morphology screening or independently labelled leakage first |
| 4.4 | Defer | Close routine small-well screening with a scoped note. Threshold now checked |
| 4.5 | Blocked | Date bounds and eligible site count. Then full-chain recovery |
| 4.6 | Bounded pilot | Inspect coverage and legibility apart from lidar or DEP agreement |
| 4.7 | Blocked | Wait for the NETL request. Check terms and metadata |
| 4.8 | Bounded pilot | Small predefined chip set. Record acquisition and visibility apart |
| 4.9 | Defer | Finish the narrow negative-result statement. No new imagery |
| 5.1 | Redesign | Common folds and all cross-fitting specified before retraining |
| 5.2 | Blocked | Small identity-resolved dated subset through 4.6 |
| 5.3 | Defer | Name the decision and a measurable endpoint first |
| 5.4 | Redesign | Distinct-well accounting and bounds as recall varies |
| 5.5 | Defer | Establish a decision that needs area, and an independent reference |
| 5.6 | Redesign | Repair the input. Rename the statistic. Adjudicate a sample for PPV |
| 6.1 | Defer | Specify the partner decision and missing subsurface information |
| 6.2 | Defer | Small identity audit only if a use case appears |
| 6.3 | Bounded pilot | Blind codebook and throughput pilot before training |
| 6.4 | Defer | Keep out of the current pipeline |
| 6.5 | Bounded pilot | Background, repeat and calibration procedures with 7.5 |
| 6.6 | Defer | Separate project |
| 7.1 | Defer | Choose the estimand and cost accounting after P1 and P2 |
| 7.2 | Defer | Random-area discovery and time-based accounting |
| 7.3 | Defer | Datasheet after P1 and P2 |
| 7.4 | Defer | Input validity and provenance requirements only |
| 7.5 | Redesign | Repair outcome accounting and sampling frames. Then a partner pilot |

Cross-cutting. The protocol was redesigned (done). The catalogue is discovery only. The review-response file records corrections but does not replace these edits.

## 4. Order of work
Desk work first. It needs no labels, no outside party and almost no data.
1. **Decisions.** K policy, margin basis, whether annotators saw DEP points, McKean scope, reviewers (section 6).
2. **P1.** Make the inner split deterministic, label historical splits, specify an isolated pit trainer.
3. **Send requests R1 to R3.** NETL, DEP coordinate provenance, magnetometer partner. Longest lead time. Drafts exist.
4. **3.0.** Archival check from the original tables, then a clean new baseline. Project the Warren interval width by resampling 9t blocks.
5. **4.6 search.** Look for pre-1880 map sources and 1937 to 1942 aerials. Then three more topo sheets.
6. **5.6 repair.** Fix the association input, then rerun as exploratory.
7. **3.3 step 4.** Slope stratification of existing recall.
8. **4.5 step 1.** Flight dates and eligible well count.
9. **Notes.** 4.9 radar scope, 4.4 detection limit, 5.4 identifiability.

After decisions or labels. 3.1 annotation (only if the projected interval is narrow enough), 6.3 pilot, 5.1, other states.
After outside parties. 4.7, 4.1, 7.5, 5.6 validation.

What would justify scaling up. A field pilot or a historical source that shows what share of drawn pits are wells, with a usable interval. Without that, more geographic transfer only measures agreement with one annotator's idea of a feature.

## 5. Where it would run and what it needs
Twelve densest of the 52 windows, rebuilt 2026-11-04 on the USGS 2026 well file (documented orphan wells in a 25 km² block, newest 3DEP project covering at least 95% of the window by area). Cover is the share of the window covered by the union of tile bounding boxes, an upper bound. Full tables in `data/_source/reference/lidar_catalogue/lidar_win_*.csv`.

| State | County | Orphans in window | Recommended project | Tiles | GB | Cover |
|---|---|---|---|---|---|---|
| New York | Allegany | 1187 | NY_SouthwestNY_2017_A17 (partial) | 17 | 1.86 | 0.93 |
| Kentucky | Lee | 1084 | KY_WestCentral_2017_C19 | 23 | 2.42 | 1.00 |
| New York | Cattaraugus | 996 | NY_SouthwestNY_2017_A17 | 20 | 2.12 | 1.00 |
| California | Los Angeles | 824 | CA_LosAngeles_B23 | 37 | 3.00 | 1.00 |
| Illinois | Cumberland | 752 | IL_8County_2020_A20 | 87 | 3.79 | 1.00 |
| Pennsylvania | McKean | 698 | PA_Northcentral_2019_B19 | 36 | 2.08 | 1.00 |
| Pennsylvania | Butler | 636 | PA_WesternPA_2019_D20 | 21 | 1.82 | 1.00 |
| Ohio | Washington | 559 | OH_Statewide_Phase2_2020_B20 | 204 | 3.83 | 1.00 |
| Pennsylvania | Venango | 543 | PA_WesternPA_2019_D20 | 20 | 2.49 | 1.00 |
| Pennsylvania | Forest | 518 | PA_WesternPA_2019_D20 | 20 | 0.95 | 1.00 |
| Pennsylvania | Warren | 514 | PA_WesternPA_2019_D20 | 19 | 1.02 | 1.00 |
| Oklahoma | Washington | 420 | OK_Statewide_D22 | 16 | 1.40 | 1.00 |

| What | Status |
|---|---|
| Well databases | Downloaded. USGS national 2022 and 2026, NY, KY, OK, IL, WV, OH, KS. The 2026 file differs from 2022 (Illinois down 4,494, Venango down 418). Cause not known |
| Lidar | **Listed, not downloaded.** 52 windows, 3,458 unique tiles touching a window (150.5 GB across all projects). Recommended projects: 2,792 tiles, about 126.9 GB, Pennsylvania about 13 GB. Every query was paged and returned ok. Coverage is by area from tile boxes. One window (Allegany NY) has no project at 0.95 and is marked partial |
| Already on disk | Tile 9t (D20), Warren 7 D20 tiles (2.8 GB with the merged LAS), McKean B19 subset |
| Disk | C: about 108 GB free. F: about 3.0 TB free. Put lidar on F: |
| Not yet searched | Canada, Alaska, state lidar portals, Texas and California state databases |

## 6. Decisions
**Decided 2026-11-04**
| Decision | Answer | Effect |
|---|---|---|
| K policy | **40 candidates per km²** (the default) | Primary metric for every transfer test. Protocol section 2 |
| Annotators saw DEP well points while drawing | **No** | Association of drawn features with DEP records is not circular by that route. Other context the annotators saw (roads, pads, imagery) is still unrecorded |
| McKean | **In scope for the expansion** | Add McKean to 3.1 as the B19 (about 9 points per m²) arm. A 36-tile window is listed (2.1 GB) |
| Margin for acceptable recall loss | **Decide per experiment, before scoring** | Each preregistration sets it. Warren needs it before any scoring |
| Where the thermal work lives | **Unknown, even to the user** | Treated as no prior work. 4.2 stays deferred and starts from scratch if revived |
| Reviewers | Acknowledged as needed. **No names yet** | 6.3 and 3.1 annotation stay blocked until two reviewers and an adjudicator exist |
| Outreach requests R1 to R3 and the USGS 2026 CSV | **The user will send and download** | Track replies in `docs/iterations/outreach_log.md` |

**Still open**
- Reviewers (two plus an adjudicator).
- The recall-loss margin for each experiment.
- Replies from DEP, NETL and a magnetometer partner.

## 7. What has actually been run
- **Valid with caveats.** The saved split held-out lists. The NISAR negative result and the change-detection placebo, each within its tested scope. The county ranking from public databases (counts, not coordinate accuracy). CV recall on 9t is a historical diagnostic. Full-window reads and shared normalisation leak by an amount not measured.
- **Discovery only.** The lidar listing. Its cover figures are tile-count ratios and the listing scripts do not paginate or separate failed queries from empty ones. The 106 GB total is an estimate.
- **Withdrawn.** The first record-association run and the recall-gap run. Their input dropped all 481 matched detections.
- **Not valid as saved.** The train and validation roles in the split manifests.
- **Invalid as written.** The Warren preregistration draft.

## 8. What would change the plan
1. A pre-1880 source that gives well positions over 9t with metre-scale error. That moves 4.6 ahead of magnetometry.
2. DEP saying the 2022 to 2026 additions are GNSS located. That makes the recall-gap study repairable.
3. A small Warren area. If the projected interval is wider than twice the margin, 3.1 changes before annotation.
4. A field partner. Without one, 7.5 and 4.1 stay on paper, and everything stays at level (a).
5. NETL declining to release the drone data. 4.7 closes.
