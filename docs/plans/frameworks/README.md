# Process frameworks

**Date:** 2026-11-04
**Status:** plan only. Nothing here has been run.
**Rule:** `fw_00_common.md` holds the machinery every process inherits (environment, provenance, statistics, QC, documentation, handoff). `docs/plans/protocol_gates_and_metrics.md` wins on any conflict.

One framework per process. Each says what the problem is, what the estimand is, what inputs exist, the stages with scripts and output paths, the statistical analysis plan, QC and leakage checks, the gates, deliverables, failure modes, resources and the handoff.

**Tiers.** A is exhaustive (can run soon or decides the program). B is full (clear design, later start). C is scoped (deferred, so each lists its gate, a minimum feasibility step and what a full framework would add). Depth follows value and readiness. A deferred process that has not passed its gate does not get a full build specification, because the gate result would change it.

Script names are proposals. Paths of existing files were taken from the repo. Items to confirm before execution are listed in each Handoff section.

[Common framework](fw_00_common.md)

| Tier | Process | Framework | Lines |
|---|---|---|---|
| A | p1 | [Framework P1. Reproducible splits and manifests](fw_p1_splits_manifests.md) | 139 |
| A | p2 | [Framework P2. Audit set and training history](fw_p2_audit_set.md) | 109 |
| A | 3.0 | [Framework 3.0. Transfer protocol](fw_3_0_transfer_protocol.md) | 121 |
| A | 3.1 | [Framework 3.1. Warren, Forest and McKean transfer](fw_3_1_warren_forest_mckean.md) | 126 |
| A | 3.3 | [Framework 3.3. Low-relief sensitivity (slope stratification, then edits)](fw_3_3_low_relief_slope.md) | 103 |
| A | 4.1 | [Framework 4.1. Magnetometry pilot](fw_4_1_magnetometry.md) | 92 |
| A | 4.5 | [Framework 4.5. Multitemporal lidar at plugged wells](fw_4_5_multitemporal_lidar.md) | 97 |
| A | 4.6 | [Framework 4.6. Historic maps and aerials](fw_4_6_historic_maps_aerials.md) | 113 |
| A | 4.7 | [Framework 4.7. Drone lidar density ladder](fw_4_7_drone_lidar.md) | 96 |
| A | 5.1 | [Framework 5.1. Context features (second-stage model)](fw_5_1_context_features.md) | 108 |
| A | 5.6 | [Framework 5.6. Record association](fw_5_6_record_association.md) | 125 |
| A | 6.3 | [Framework 6.3. Confuser classes and negative-class training](fw_6_3_confuser_classes.md) | 105 |
| A | 7.5 | [Framework 7.5. Field campaign](fw_7_5_field_campaign.md) | 110 |
| B | 3.2 | [Framework 3.2. Ohio, West Virginia, New York, Kentucky](fw_3_2_appalachian_states.md) | 62 |
| B | 3.4 | [Framework 3.4. Gulf Coast and Texas](fw_3_4_gulf_texas.md) | 55 |
| B | 3.5 | [Framework 3.5. Oklahoma and Kansas](fw_3_5_oklahoma_kansas.md) | 55 |
| B | 4.4 | [Framework 4.4. Methane plumes (detection-limit check, then close or proceed)](fw_4_4_methane_plumes.md) | 59 |
| B | 4.8 | [Framework 4.8. Leaf-off optical imagery](fw_4_8_leafoff_optical.md) | 60 |
| B | 4.9 | [Framework 4.9. More radar (scope note only)](fw_4_9_more_radar.md) | 52 |
| B | 5.2 | [Framework 5.2. Era classification](fw_5_2_era_classification.md) | 55 |
| B | 5.4 | [Framework 5.4. Undocumented well density (identifiability)](fw_5_4_undocumented_density.md) | 64 |
| B | 6.5 | [Framework 6.5. Field methane screening](fw_6_5_field_methane.md) | 55 |
| B | 7.2 | [Framework 7.2. Active learning](fw_7_2_active_learning.md) | 61 |
| B | 7.3 | [Framework 7.3. Terrain-feature benchmark](fw_7_3_benchmark.md) | 56 |
| C | 3.6 | [Framework 3.6. California (scoped)](fw_3_6_california.md) | 26 |
| C | 3.7 | [Framework 3.7. Canada (scoped)](fw_3_7_canada.md) | 24 |
| C | 3.8 | [Framework 3.8. Alaska (scoped)](fw_3_8_alaska.md) | 24 |
| C | 4.2 | [Framework 4.2. Thermal (scoped)](fw_4_2_thermal.md) | 30 |
| C | 4.3 | [Framework 4.3. Vegetation stress (scoped)](fw_4_3_vegetation_stress.md) | 26 |
| C | 5.3 | [Framework 5.3. Risk ranking (scoped)](fw_5_3_risk_ranking.md) | 24 |
| C | 5.5 | [Framework 5.5. Polygon area and cost (scoped)](fw_5_5_polygon_area_cost.md) | 24 |
| C | 6.1 | [Framework 6.1. CO2 storage and geothermal screening (scoped)](fw_6_1_co2_geothermal.md) | 24 |
| C | 6.2 | [Framework 6.2. Coal and mine features (scoped)](fw_6_2_coal_features.md) | 24 |
| C | 6.4 | [Framework 6.4. Hydrogen storage screening (scoped)](fw_6_4_hydrogen.md) | 22 |
| C | 6.6 | [Framework 6.6. Search and rescue viewshed (scoped)](fw_6_6_sar_viewshed.md) | 22 |
| C | 7.1 | [Framework 7.1. Self-supervised pretraining (scoped)](fw_7_1_pretraining.md) | 26 |
| C | 7.4 | [Framework 7.4. Agency tooling (scoped)](fw_7_4_agency_tooling.md) | 25 |

## Dependency order
P1, then P2, then 3.0. Then 3.1, 3.3 (step 1 needs no data), 5.6 repair, 4.6 probe and 4.5 date check in parallel as they share no dependency. 6.3 and 5.1 need P1 and P2 and reviewers. 4.1, 4.7 and 7.5 wait on outside parties. Tier B and C follow their gates.
