# Plans for future work

**Start here.** [EXPANSION_MASTER_PLAN.md](EXPANSION_MASTER_PLAN.md) is the single entry point. This file is the index and shared rules.

One document per problem. Each says what the problem is, what to build, and how to know it worked. Nothing here has been run. No numbers in these files are results. Facts marked **unverified** must be checked before work starts.

Authoritative. `protocol_gates_and_metrics.md` wins over everything else here. See also `review_response_20261104.md` (what two adversarial reviews changed) and `download_manifest.md` (everything that must be downloaded or requested, with gates).

Older source documents. `docs/iterations/expansion_options_methods.md`, `docs/iterations/expansion_gameplan_feasibility.md`. Both are superseded in part. Each plan ends with a **Review revisions** section that overrides the text above it.

## Rules every plan inherits
1. **Feature is not well.** Keep four evidence levels apart. (a) terrain feature matched to a drawn polygon. (b) historical evidence. (c) steel anomaly. (d) confirmed well by record or visible wellhead. Never merge them.
2. **Pre-register first.** Copy `docs/iterations/transfer_prereg_template.md`, fill it, commit it, then look at output.
3. **Freeze before scoring.** Weights, preprocessing, proposals, cutoff and K.
4. **Unmatched is not negative.** Only independently adjudicated confusers become negatives. Keep an "uncertain" class. Freeze an audit set before mining errors.
5. **Platt scaling is monotonic.** It cannot change recall at fixed K. Judge calibration by Brier score, log loss and calibration error. Judge ranking by recall at fixed K.
6. **Uncertainty.** Block bootstrap, not detection bootstrap. Compare with a confidence interval for the difference and a margin set in advance.
7. **Spatial splits with derived buffers.** Buffer covers receptive field and patch support plus the range of an empirical correlogram. Windows that touch held-out ground are rejected. Normalisation is fitted inside the fold. No untouched 9t block exists, so absolute final claims need a new area.
8. **QL2 is a nominal aggregate density.** It does not guarantee ground returns under canopy. Measure ground density per area.
9. **Record association is proposed, not corrected.** A pad centroid is not a borehole. Coordinate improvement needs independent positions. Record coordinate provenance. Use the full detector output as input, never only unmatched leftovers.
10. **Provenance.** Hash inputs and checkpoints. Save the package list. Record the commit.
11. **K is candidates per km².** Transfer recall is judged at one fixed K per km² of scored area, with target density reported. Never at a K equal to the annotation count.
12. **Downloads follow the manifest.** Measure size first, pass the gate, use an own folder, hash, log provenance.

## Repo conventions
- Python only, plain `python`. PDAL through the CLI with a pipeline JSON file.
- Names follow `<section>_<what>_<meaning>_<area>`, about 45 characters or fewer. Scripts start with an underscore.
- Outputs under `data/<area>/results/<section>/`. State the full path of every new file.
- Any file of 100 MB or more gets a `.gitignore` rule in the same change.
- Colourblind-safe graphics. Reuse blue `#1F5FA8`, orange `#D97706`, grey `#8E959B`. Validate over all pairs with the dataviz validator.
- Never write "WellSight" in audience-facing material.
- Document in `docs/iterations/<name>.md`, `docs/analysis_log.md` (newest first), `docs/iterations/BACKLOG.md` and `docs/iterations/LEADERBOARD.md`. Cite literature in `literature/CITATIONS.md`.
- Never overwrite `output_wells.csv` or the DEP export. Write new files.
- Commit and push with selective staging. Many unrelated files are modified.
- Write in short declaratives. No em-dashes. No prose colons or semicolons. Use they/them.

## Index
### Authoritative
- [Protocol, gates and metrics](protocol_gates_and_metrics.md)
- [Process frameworks (one per process, with a common framework)](../../expansions/README.md)
- [Review response](review_response_20261104.md)
- [Download manifest](download_manifest.md)
- [Download list: areas with many old wells, and the lidar that covers them](download_list_areas_and_lidar.md)
- [Codex adversarial review](adversarial_codex_review_20261104.md)
- [Claude adversarial review](adversarial_review_claude.md)
### Geographic
- [3.0 Transfer protocol](../../expansions/3_geography/3_0_transfer_protocol/docs/plan_geo_transfer_protocol.md)
- [3.1 Warren and Forest](../../expansions/3_geography/3_1_warren_forest_mckean/docs/plan_geo_warren_forest.md)
- [3.2 Ohio, West Virginia, New York, Kentucky](../../expansions/3_geography/3_2_appalachian_states/docs/plan_geo_appalachian_states.md)
- [3.3 Illinois and Michigan](../../expansions/3_geography/3_3_low_relief_slope/docs/plan_geo_low_relief_midwest.md)
- [3.4 Gulf and East Texas](../../expansions/3_geography/3_4_gulf_texas/docs/plan_geo_gulf_east_texas.md)
- [3.5 Oklahoma and Kansas](../../expansions/3_geography/3_5_oklahoma_kansas/docs/plan_geo_oklahoma_kansas.md)
- [3.6 California](../../expansions/3_geography/3_6_california/docs/plan_geo_california.md)
- [3.7 Canada](../../expansions/3_geography/3_7_canada/docs/plan_geo_canada.md)
- [3.8 Alaska](../../expansions/3_geography/3_8_alaska/docs/plan_geo_alaska.md)
### Modality
- [4.1 Magnetometry](../../expansions/4_modalities/4_1_magnetometry/docs/plan_mod_magnetometry.md)
- [4.2 Thermal](../../expansions/4_modalities/4_2_thermal/docs/plan_mod_thermal.md)
- [4.3 Vegetation stress](../../expansions/4_modalities/4_3_vegetation_stress/docs/plan_mod_vegetation_stress.md)
- [4.4 Methane plumes](../../expansions/4_modalities/4_4_methane_plumes/docs/plan_mod_methane_plumes.md)
- [4.5 Multitemporal lidar](../../expansions/4_modalities/4_5_multitemporal_lidar/docs/plan_mod_multitemporal_lidar.md)
- [4.6 Historic maps and aerials](../../expansions/4_modalities/4_6_historic_maps_aerials/docs/plan_mod_historic_maps_aerials.md)
- [4.7 Drone lidar](../../expansions/4_modalities/4_7_drone_lidar/docs/plan_mod_drone_lidar.md)
- [4.8 Leaf-off optical](../../expansions/4_modalities/4_8_leafoff_optical/docs/plan_mod_leafoff_optical.md)
- [4.9 More radar](../../expansions/4_modalities/4_9_more_radar/docs/plan_mod_more_radar.md)
### Task
- [5.1 Context features](../../expansions/5_tasks/5_1_context_features/docs/plan_task_context_features.md)
- [5.2 Era classification](../../expansions/5_tasks/5_2_era_classification/docs/plan_task_era_classification.md)
- [5.3 Risk ranking](../../expansions/5_tasks/5_3_risk_ranking/docs/plan_task_risk_ranking.md)
- [5.4 Undocumented density](../../expansions/5_tasks/5_4_undocumented_density/docs/plan_task_undocumented_density.md)
- [5.5 Polygon area and cost](../../expansions/5_tasks/5_5_polygon_area_cost/docs/plan_task_polygon_area_cost.md)
- [5.6 Record association](../../expansions/5_tasks/5_6_record_association/docs/plan_task_record_association.md)
### Adjacent
- [6.1 CO2 and geothermal](../../expansions/6_adjacent/6_1_co2_geothermal/docs/plan_adj_co2_geothermal.md)
- [6.2 Coal features](../../expansions/6_adjacent/6_2_coal_features/docs/plan_adj_coal_features.md)
- [6.3 Negative classes](../../expansions/6_adjacent/6_3_confuser_classes/docs/plan_adj_negative_classes.md)
- [6.4 Hydrogen](../../expansions/6_adjacent/6_4_hydrogen/docs/plan_adj_hydrogen.md)
- [6.5 Field methane](../../expansions/6_adjacent/6_5_field_methane/docs/plan_adj_field_methane.md)
- [6.6 Search and rescue viewshed](../../expansions/6_adjacent/6_6_sar_viewshed/docs/plan_adj_sar_viewshed.md)
### Scale and method
- [7.1 Self-supervised pretraining](../../expansions/7_scale/7_1_pretraining/docs/plan_scale_pretraining.md)
- [7.2 Active learning](../../expansions/7_scale/7_2_active_learning/docs/plan_scale_active_learning.md)
- [7.3 Benchmark](../../expansions/7_scale/7_3_benchmark/docs/plan_scale_benchmark.md)
- [7.4 Agency tooling](../../expansions/7_scale/7_4_agency_tooling/docs/plan_scale_agency_tooling.md)
- [7.5 Field campaign](../../expansions/7_scale/7_5_field_campaign/docs/plan_scale_field_campaign.md)
### Cross-cutting prerequisites
- [P1 Reproducible splits and manifests](../../expansions/0_prerequisites/p1_splits_manifests/docs/plan_prereq_splits_manifests.md)
- [P2 Audit set and training history](../../expansions/0_prerequisites/p2_audit_set/docs/plan_prereq_audit_set.md)
