# Expansion projects

One folder per expansion, grouped by section, same skeleton in every folder. Created 2026-11-05 by `tools/scaffold_expansions.py`. Every move is in `docs/MOVES.csv` (phase `expansions`) and reverses with `python tools/apply_moves.py --undo --phase expansions`.

```
expansions/
  README.md            this index
  _shared/             fw_00_common.md, inherited by every framework
  _template/           empty skeleton for a new expansion
  0_prerequisites/  3_geography/  4_modalities/  5_tasks/  6_adjacent/  7_scale/
    <id>_<slug>/
      README.md        status, links, folder rules
      docs/            plan_*.md, fw_*.md, decisions_<id>.md
      src/             scripts
      data/raw/  data/interim/  data/processed/    not in git
      models/                                       not in git
      results/figures/  results/tables/             small, in git
```

Program-level documents stay in `docs/plans/`: `EXPANSION_MASTER_PLAN.md` (entry point), `protocol_gates_and_metrics.md` (wins on any conflict), the reviews and the download lists. Products for a new study area go to `data/<area>/` as everywhere else. Scripts use `path_for("expansions")`.

## Frameworks

**Date:** 2026-11-04
**Status:** plan only. Nothing here has been run.
**Rule:** `fw_00_common.md` holds the machinery every process inherits (environment, provenance, statistics, QC, documentation, handoff). `docs/plans/protocol_gates_and_metrics.md` wins on any conflict.

One framework per process. Each says what the problem is, what the estimand is, what inputs exist, the stages with scripts and output paths, the statistical analysis plan, QC and leakage checks, the gates, deliverables, failure modes, resources and the handoff.

**Update 2026-11-05.** The user ended deferral. The 21 frameworks marked † were rewritten to full depth (140 to 205 lines) on the stated assumption that the data, access and partners exist. Each has an "Assumed data" section with every assumption tagged VERIFY, and an early pre-specified close outcome where the physics or the evidence may rule it out (4.2, 4.3, 4.4). Their gates still bind. Writing a framework does not mean the process has passed its gate or that the data is real. The tier text below describes the earlier state.

**Tiers.** A is exhaustive (can run soon or decides the program). B is full (clear design, later start). C is scoped (deferred, so each lists its gate, a minimum feasibility step and what a full framework would add). Depth follows value and readiness. A deferred process that has not passed its gate does not get a full build specification, because the gate result would change it.

Script names are proposals. Paths of existing files were taken from the repo. Items to confirm before execution are listed in each Handoff section.

[Common framework](_shared/fw_00_common.md)

| Tier | Process | Framework | Lines |
|---|---|---|---|
| A | p1 | [Framework P1. Reproducible splits and manifests](0_prerequisites/p1_splits_manifests/docs/fw_p1_splits_manifests.md) | 139 |
| A | p2 | [Framework P2. Audit set and training history](0_prerequisites/p2_audit_set/docs/fw_p2_audit_set.md) | 109 |
| A | 3.0 | [Framework 3.0. Transfer protocol](3_geography/3_0_transfer_protocol/docs/fw_3_0_transfer_protocol.md) | 121 |
| A | 3.1 | [Framework 3.1. Warren, Forest and McKean transfer](3_geography/3_1_warren_forest_mckean/docs/fw_3_1_warren_forest_mckean.md) | 126 |
| A | 3.3 | [Framework 3.3. Low-relief sensitivity (slope stratification, then edits)](3_geography/3_3_low_relief_slope/docs/fw_3_3_low_relief_slope.md) | 103 |
| A | 4.1 | [Framework 4.1. Magnetometry pilot](4_modalities/4_1_magnetometry/docs/fw_4_1_magnetometry.md) | 92 |
| A | 4.5 | [Framework 4.5. Multitemporal lidar at plugged wells](4_modalities/4_5_multitemporal_lidar/docs/fw_4_5_multitemporal_lidar.md) | 97 |
| A | 4.6 | [Framework 4.6. Historic maps and aerials](4_modalities/4_6_historic_maps_aerials/docs/fw_4_6_historic_maps_aerials.md) | 113 |
| A | 4.7 | [Framework 4.7. Drone lidar density ladder](4_modalities/4_7_drone_lidar/docs/fw_4_7_drone_lidar.md) | 96 |
| A | 5.1 | [Framework 5.1. Context features (second-stage model)](5_tasks/5_1_context_features/docs/fw_5_1_context_features.md) | 108 |
| A | 5.6 | [Framework 5.6. Record association](5_tasks/5_6_record_association/docs/fw_5_6_record_association.md) | 125 |
| A | 6.3 | [Framework 6.3. Confuser classes and negative-class training](6_adjacent/6_3_confuser_classes/docs/fw_6_3_confuser_classes.md) | 105 |
| A | 7.5 | [Framework 7.5. Field campaign](7_scale/7_5_field_campaign/docs/fw_7_5_field_campaign.md) | 110 |
| A† | 3.2 | [Framework 3.2. Ohio, West Virginia, New York, Kentucky](3_geography/3_2_appalachian_states/docs/fw_3_2_appalachian_states.md) | 180 |
| A† | 3.4 | [Framework 3.4. Gulf Coast and Texas](3_geography/3_4_gulf_texas/docs/fw_3_4_gulf_texas.md) | 173 |
| A† | 3.5 | [Framework 3.5. Oklahoma and Kansas](3_geography/3_5_oklahoma_kansas/docs/fw_3_5_oklahoma_kansas.md) | 177 |
| A† | 4.4 | [Framework 4.4. Methane plumes (detection-limit check, then close or proceed)](4_modalities/4_4_methane_plumes/docs/fw_4_4_methane_plumes.md) | 148 |
| B | 4.8 | [Framework 4.8. Leaf-off optical imagery](4_modalities/4_8_leafoff_optical/docs/fw_4_8_leafoff_optical.md) | 60 |
| A† | 4.9 | [Framework 4.9. More radar (scope note only)](4_modalities/4_9_more_radar/docs/fw_4_9_more_radar.md) | 171 |
| A† | 5.2 | [Framework 5.2. Era classification](5_tasks/5_2_era_classification/docs/fw_5_2_era_classification.md) | 174 |
| B | 5.4 | [Framework 5.4. Undocumented well density (identifiability)](5_tasks/5_4_undocumented_density/docs/fw_5_4_undocumented_density.md) | 64 |
| B | 6.5 | [Framework 6.5. Field methane screening](6_adjacent/6_5_field_methane/docs/fw_6_5_field_methane.md) | 55 |
| A† | 7.2 | [Framework 7.2. Active learning](7_scale/7_2_active_learning/docs/fw_7_2_active_learning.md) | 152 |
| A† | 7.3 | [Framework 7.3. Terrain-feature benchmark](7_scale/7_3_benchmark/docs/fw_7_3_benchmark.md) | 168 |
| A† | 3.6 | [Framework 3.6. California](3_geography/3_6_california/docs/fw_3_6_california.md) | 173 |
| A† | 3.7 | [Framework 3.7. Canada](3_geography/3_7_canada/docs/fw_3_7_canada.md) | 170 |
| A† | 3.8 | [Framework 3.8. Alaska](3_geography/3_8_alaska/docs/fw_3_8_alaska.md) | 173 |
| A† | 4.2 | [Framework 4.2. Thermal](4_modalities/4_2_thermal/docs/fw_4_2_thermal.md) | 151 |
| A† | 4.3 | [Framework 4.3. Vegetation stress](4_modalities/4_3_vegetation_stress/docs/fw_4_3_vegetation_stress.md) | 141 |
| A† | 5.3 | [Framework 5.3. Risk ranking](5_tasks/5_3_risk_ranking/docs/fw_5_3_risk_ranking.md) | 204 |
| A† | 5.5 | [Framework 5.5. Polygon area and cost](5_tasks/5_5_polygon_area_cost/docs/fw_5_5_polygon_area_cost.md) | 158 |
| A† | 6.1 | [Framework 6.1. CO2 storage and geothermal screening](6_adjacent/6_1_co2_geothermal/docs/fw_6_1_co2_geothermal.md) | 182 |
| A† | 6.2 | [Framework 6.2. Coal and mine features](6_adjacent/6_2_coal_features/docs/fw_6_2_coal_features.md) | 144 |
| A† | 6.4 | [Framework 6.4. Hydrogen storage screening](6_adjacent/6_4_hydrogen/docs/fw_6_4_hydrogen.md) | 152 |
| A† | 6.6 | [Framework 6.6. Search and rescue viewshed](6_adjacent/6_6_sar_viewshed/docs/fw_6_6_sar_viewshed.md) | 148 |
| A† | 7.1 | [Framework 7.1. Self-supervised pretraining](7_scale/7_1_pretraining/docs/fw_7_1_pretraining.md) | 160 |
| A† | 7.4 | [Framework 7.4. Agency tooling](7_scale/7_4_agency_tooling/docs/fw_7_4_agency_tooling.md) | 195 |

## Dependency order
P1, then P2, then 3.0. Then 3.1, 3.3 (step 1 needs no data), 5.6 repair, 4.6 probe and 4.5 date check in parallel as they share no dependency. 6.3 and 5.1 need P1 and P2 and reviewers. 4.1, 4.7 and 7.5 wait on outside parties. Tier B and C follow their gates.
