# Plans for future work

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
- [Review response](review_response_20261104.md)
- [Download manifest](download_manifest.md)
- [Codex adversarial review](adversarial_codex_review_20261104.md)
- [Claude adversarial review](adversarial_review_claude.md)
### Geographic
- [3.0 Transfer protocol](plan_geo_transfer_protocol.md)
- [3.1 Warren and Forest](plan_geo_warren_forest.md)
- [3.2 Ohio, West Virginia, New York, Kentucky](plan_geo_appalachian_states.md)
- [3.3 Illinois and Michigan](plan_geo_low_relief_midwest.md)
- [3.4 Gulf and East Texas](plan_geo_gulf_east_texas.md)
- [3.5 Oklahoma and Kansas](plan_geo_oklahoma_kansas.md)
- [3.6 California](plan_geo_california.md)
- [3.7 Canada](plan_geo_canada.md)
- [3.8 Alaska](plan_geo_alaska.md)
### Modality
- [4.1 Magnetometry](plan_mod_magnetometry.md)
- [4.2 Thermal](plan_mod_thermal.md)
- [4.3 Vegetation stress](plan_mod_vegetation_stress.md)
- [4.4 Methane plumes](plan_mod_methane_plumes.md)
- [4.5 Multitemporal lidar](plan_mod_multitemporal_lidar.md)
- [4.6 Historic maps and aerials](plan_mod_historic_maps_aerials.md)
- [4.7 Drone lidar](plan_mod_drone_lidar.md)
- [4.8 Leaf-off optical](plan_mod_leafoff_optical.md)
- [4.9 More radar](plan_mod_more_radar.md)
### Task
- [5.1 Context features](plan_task_context_features.md)
- [5.2 Era classification](plan_task_era_classification.md)
- [5.3 Risk ranking](plan_task_risk_ranking.md)
- [5.4 Undocumented density](plan_task_undocumented_density.md)
- [5.5 Polygon area and cost](plan_task_polygon_area_cost.md)
- [5.6 Record association](plan_task_record_association.md)
### Adjacent
- [6.1 CO2 and geothermal](plan_adj_co2_geothermal.md)
- [6.2 Coal features](plan_adj_coal_features.md)
- [6.3 Negative classes](plan_adj_negative_classes.md)
- [6.4 Hydrogen](plan_adj_hydrogen.md)
- [6.5 Field methane](plan_adj_field_methane.md)
- [6.6 Search and rescue viewshed](plan_adj_sar_viewshed.md)
### Scale and method
- [7.1 Self-supervised pretraining](plan_scale_pretraining.md)
- [7.2 Active learning](plan_scale_active_learning.md)
- [7.3 Benchmark](plan_scale_benchmark.md)
- [7.4 Agency tooling](plan_scale_agency_tooling.md)
- [7.5 Field campaign](plan_scale_field_campaign.md)
### Cross-cutting prerequisites
- [P1 Reproducible splits and manifests](plan_prereq_splits_manifests.md)
- [P2 Audit set and training history](plan_prereq_audit_set.md)
