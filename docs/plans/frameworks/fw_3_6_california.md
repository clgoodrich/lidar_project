# Framework 3.6. California (observable pad target, then transfer scoring)

**Tier A (full design, data assumed).** Written 2026-11-05 after the user ended deferral. Nothing here has been run, fetched or measured. Every assumed input is tagged VERIFY in section 5.
**Evidence level.** (a) drawn feature only. Administrative status (idle, orphan, active) is a record. It is an attribute and never a label. No level (b), (c) or (d) evidence can come from this study.
**Depends on.** 3.0 scorer, P1 isolated pad model (the pad reference), 3.3 result for slope context (read only).
**Blocks.** Any California well-level claim. Any California density or association work.

## 1. Problem and objective
California holds many idle and orphaned wells beside visible surface equipment. Whether a well is idle or orphaned is a regulator's record. A lidar surface or an aerial photograph cannot show it. The first draft of this plan already said so. The third review added that urban removal and burial break the terrain-feature proxy.

This framework separates two things.
- **The observable target.** A well pad whose surface and equipment can be seen on a stated date. This is what the detector can be scored on.
- **Administrative status.** A CalGEM record joined to the pad afterward. It describes the pad. It never defines it.

**Question 1 (primary).** Does a frozen pad model, trained only on Pennsylvania terrain, recover drawn California oil-field pads at the review budget of K = 40 candidates per km², compared with its 9t out-of-fold reference?
**Question 2 (descriptive).** For pads with equipment visible, what share carry each status in the state record, and how many records of idle or orphan wells sit on pads that look active? This measures record and surface mismatch. It is not a gate.
**Question 3 (exploratory).** Does a simple above-ground-object rule on lidar (equipment shows as non-ground returns) find equipped pads that the terrain model misses?

**Hypotheses.** Q1. Pad recall at K on California is not worse than the 9t reference by more than Δ_pad. Q3. The object rule adds recall on equipped pads when paired with the model on the same blocks.

**What this study can show.** Whether terrain-trained pad detection transfers to a different region, climate and surface type, by pad class, at a fixed review burden. How well two people agree on what an observable pad is.
**What it cannot show.** That a pad holds an idle or orphaned well. How many wells a pad holds beyond the record. Whether equipment still works. Anything about wells with no pad. Any level (b), (c) or (d) result. A California orphan-well count.

## 2. Scope
In. One to three oil-field areas with visible pads. Two-annotator blind labels on imagery plus lidar. Frozen-model scoring under 3.0. Status join as a descriptive table.
Out. Retraining on California. Orphan labels from imagery. Wells per pad as a target (it is an attribute from the record). Thermal, methane and SAR work.

## 3. Definitions
- **Pad.** A graded, bare or gravelled working surface that carries or carried wells or equipment. The unit is one pad polygon. A cluster of wells on one pad is one unit.
- **Pad class on the label date.** E1 equipped (at least one pumpjack, tank, separator, wellhead assembly or pipe rack visible on imagery). E2 bare (graded and disturbed, no equipment visible). E3 faint (outline visible only in the lidar surface, vegetated or eroded). E0 uncertain. E1 and E2 are drawn from imagery and are independent of the lidar the model reads. E3 is drawn from the same lidar and is partly circular, so it is reported apart.
- **Primary truth set.** E1 and E2 polygons. E3 and E0 are scored as secondary and never pooled into the primary.
- **Label date.** The acquisition date of the imagery used. **Lidar date** is the flight date from project metadata (not file creation or publication date). **Date gap** is the absolute difference in months.
- **Block.** 375 m square, the 9t size, so the projected-width tool applies unchanged. Complete blocks only, including blocks with no pads.
- **Eligible area.** Union of complete blocks inside the oil-field polygon, minus blocks whose developed-land share exceeds the preregistered cap, and minus edge blocks and blocks above the void-fraction cap.
- **Ceiling.** For a block with density d pads per km², the highest possible recall at K is min(1, K / d). Reported per block.
- **Equipment object (Q3).** A compact cluster of non-ground lidar returns 1.5 to 12 m above the local ground inside a pad polygon or its 10 m buffer. Parameters are fixed before scoring.
- Primary metric, matching, bootstrap. `fw_00_common.md` section 4. K = 40 per km² (user, 2026-11-04). K = 30 is a sensitivity only.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Frozen pad model and isolated 9t out-of-fold pad raster | `data/9t/models/pad/unet_iso_cv5/` (path to confirm, built by `s3_train/_pad_unet_iso_cv5.py`) | held, confirm |
| 9t pad annotations and blocks | `qgis/annotations/annotations_proj.gpkg`, `data/9t/derived/05/` | held |
| Scorer and inference wrapper | `notebooks/wellsight_v2/s5_eval/_transfer_score.py`, `s4_infer/_transfer_infer.py` | planned in 3.0 |
| 9t derivative builders (0.5 m) | `s1_build/_build_derivatives.py`, `_build_extra_channels.py` | held |
| USGS orphan lists (context only) | `data/_source/reference/wells_us_orphan_2022/US_orphaned_wells.csv`, `wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| Los Angeles lidar window | `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv` (project `CA_LosAngeles_B23`, 35 tiles, 2.90 GB, published 2025-06-13, cover 0.73, 832 listed wells) | listed, not fetched |
| CalGEM well records | `data/_source/reference/wells_ca_calgem/` | proposed |
| Imagery chips | `data/ca1/derived/ca_naip_chips_ca1/` | proposed |

The two USGS lists disagree for California. The 2022 file holds 3,338 rows. The 2026 file holds 2,940 (2,237 marked potentially deserted or deserted, 362 marked orphan). Treat both as context. They are not the state inventory.

## 5. Assumed data
Every row is an assumption. Nothing is confirmed. Each carries a VERIFY test that an executor runs before any other stage.
| Item | Assumed to exist | Format, resolution, CRS | Fields | Licence and access | VERIFY (how) |
|---|---|---|---|---|---|
| CalGEM well records (WellSTAR extract or public GIS well layer) | Statewide wells with API, status, type, operator, spud date and coordinates | CSV or feature service. NAD83 geographic or EPSG:3310 | API, status, type, operator, spud date, plugged date, lat, lon, field, pad or lease if present | State open data, terms unchecked | Download one snapshot, record the date and SHA-256, count rows, list status codes, check for a pad or lease field and a coordinate-method field. Compare totals with the two USGS lists |
| Lidar, pilot oil field | A 3DEP QL2 or better project over one Kern or Ventura oil field, flown within 12 months of NAIP | LAZ, EPSG:6339 to 6341 or 26910 and 26911 with NAVD88, at least 2 pts per m² | Classification (ground 2, unclassified 1, building 6), GPS time, return number | USGS public domain | Query the 3DEP catalogue for Kern and Ventura (the earlier listing missed them). Read one tile header. Measure ground density, classes present, flight dates |
| Lidar, Los Angeles | `CA_LosAngeles_B23`, flown about 2025 | LAZ, listed in the catalogue | As above | Public | Verify union coverage from tile geometry. Cover is 0.73 and the window sits in the city, so measure developed-land share before use |
| Imagery | NAIP four-band at 0.6 m or 1 m for a year within 12 months of the lidar | GeoTIFF, EPSG:26910 or 26911 | Acquisition date per image | Public domain (USDA) | Read the date from tile metadata. Check registration to lidar on roads and report the offset |
| Oil-field boundaries | CalGEM field polygons | Shapefile, EPSG:3310 | Field name, code | State open data | Overlay on the lidar window. Check it covers the pad areas |
| Developed-land mask | NLCD developed classes or a building footprint layer | Raster 30 m or vector | Class | Public | Check the year and that it separates yards from active wells |
| Reviewer | One local petroleum or regulatory reviewer for class rules | Not data | Class decisions on 20 pads | Volunteer | Confirm a name and a time slot before labelling starts |

## 6. Prerequisites and decisions
User decisions needed before preregistration.
- **D-CA1.** Δ_pad. The recall loss at K = 40 per km² that a crew accepts before a California screen is judged not to transfer. State it as missed pads per 100.
- **D-CA2.** Minimum label agreement (pad-existence F1 between the two annotators, and class kappa) below which the target counts as not observable.
- **D-CA3.** Maximum date gap in months, and the share of blocks that may exceed it.
- **D-CA4.** Developed-land cap for eligibility.
Prerequisites. P1 and the isolated pad model exist, or the reference carries the stated optimism. 3.0 scorer certified.

## 7. Procedure
**S0. Verify assumed data.** Run every VERIFY check in section 5. Write `docs/iterations/ca_data_verification.md`. Stop at the first failure and report. Pull the state records once and freeze the snapshot date.
- Script `notebooks/wellsight_v2/s1_build/_ca_wellstar_pull.py` (proposed). Output `data/_source/reference/wells_ca_calgem/` raw files with SHA-256, and `data/ca1/derived/ca_wells_snapshot_ca1.gpkg`.

**S1. Area choice (bootstrap pilot first).** Candidate oil fields are scored on stated criteria before any labelling. Pad density, developed-land share, lidar ground density, date gap, imagery date, and vegetation cover. Windows are not chosen by well count alone, which the catalogue review flagged as a flaw.
- Script `s1_build/_ca_area_pick_fields.py` (proposed). Output `data/ca1/results/ca_area_scores_fields.csv`. Pick one pilot area, then a second only if S3 passes.
- Pilot first. Label 3 to 5 pads near listed wells, build derivatives, and confirm the pipeline runs. Then scale.

**S2. Target definition.** Write `docs/iterations/ca_target_definition.md` with class rules, photographed examples, the decision the output serves (where a crew would look for visible pads) and what it must not be used for. Commit before labelling.

**S3. Blind label packs.** For each complete block, build chips of imagery, hillshade and above-ground-height raster. No status, no well points, no model output.
- Script `s2_labels/_ca_label_pack_ca1.py` (proposed). Output `data/ca1/derived/ca_label_packs_ca1/`.
- Two annotators label every block in a 20% random subset. One annotator labels the rest. The reviewer checks 20 pads.
- Script `s2_labels/_ca_label_agreement_ca1.py` (proposed). Output `data/ca1/results/ca_label_agreement_ca1.json`. Pad-existence F1 at IoU 0.3, class kappa, and a second-pass completeness check on empty blocks.

**S4. Derivatives and inference.** Build 0.5 m derivatives with the 9t builders. Run the frozen pad model with the preregistered policy. Write the probability raster and a void-fraction raster per block.
- Scripts `s4_infer/_transfer_infer.py`, then `s5_eval/_transfer_score.py` (both from 3.0). Output `data/ca1/results/transfer/<run_id>/`.
- Check. Channel count and order equal the 9t stack. Normalisation from saved 9t statistics. Ground density per block is recorded.

**S5. Primary scoring.** Score at K = 40 per km² against E1 and E2. Report the ceiling per block, target density, recall by class, and the secondary recall at density-scaled K.
- Script `s5_eval/_ca_pad_recall_by_class_ca1.py` (proposed). Output `data/ca1/results/transfer/ca_pad_recall_by_class_ca1.csv`.

**S6. Unmatched candidate adjudication.** Draw a random sample of 100 unmatched top-K candidates. Two blind labels each (real pad missed by annotators, equipment yard, building or road, natural, other).
- Script `s5_eval/_ca_unmatched_adjudication_ca1.py` (proposed). Output `data/ca1/results/transfer/ca_unmatched_labels_ca1.csv`. This also estimates annotation incompleteness.

**S7. Status join (descriptive).** Join snapshot wells to pad polygons by containment, with a 25 m tolerance. Wells per pad and a status table by pad class.
- Script `s5_eval/_ca_status_mismatch_ca1.py` (proposed). Output `data/ca1/results/transfer/ca_status_by_pad_class_ca1.csv`. State the counts of wells with no pad and pads with no well.

**S8. Object rule (exploratory).** Count non-ground clusters inside pads and recompute recall for model, rule and union on the same blocks.
- Script `s5_eval/_ca_equipment_rule_ca1.py` (proposed). Output `data/ca1/results/transfer/ca_equipment_rule_vs_model_ca1.csv`.

## 8. Statistical analysis plan
- **Primary (confirmatory).** Pad recall at K = 40 per km² on E1 and E2, California minus 9t reference, independent block bootstraps per area, B = 2000, non-inferiority against Δ_pad.
- **Projected width first.** Run `s5_eval/_project_ci_width_9t.py` with the California block count and density before labelling. If the median width exceeds 2 Δ_pad, add blocks or change the design.
- **Secondary.** Recall at density-scaled K with c fixed from 9t. Recall by class (E1, E2, E3). Calibration shift. Candidate precision from S6 with Clopper-Pearson intervals.
- **Exploratory.** Logistic model of matched flag on ground density, void fraction, pad area, slope, wells per pad and class, with block as cluster. Paired model versus rule recall (same resampled blocks). Q2 shares with Clopper-Pearson intervals per class. All labelled exploratory.
- **Few blocks.** Under 15 blocks, add a permutation interval and say the bootstrap is unreliable.
- **Density.** Report pads per km² for 9t and California. If more than 25% of blocks have ceiling below 0.9, the primary is not interpretable, and the secondary becomes the descriptive result.
- Evidence label on every table. All primary and secondary rows are (a). Q2 rows say record, not evidence level.

## 9. Quality control and leakage checks
1. Row counts asserted at every join, expected and observed.
2. CRS asserted on every layer. Lidar vertical datum recorded. Imagery to lidar offset measured and logged.
3. No model output, status or well point visible to annotators. Check the label-pack manifest.
4. The frozen model never saw California. Assert by checkpoint hash and the 9t training manifest. No California block enters calibration, cutoff fitting or selection.
5. Annotators did not choose blocks after seeing scores. Blocks are fixed by a seeded draw saved before labelling.
6. Date gap per block saved. Blocks above the cap are flagged and reported both ways.
7. Candidate dedupe, tie rule and K identical to 3.0 (module hash equal).
8. Same-config rerun gives identical outputs. Seed per block.
9. Sanity render for each new raster. Check two pads on hillshade.
10. Status fields never appear in the label, feature or scoring tables. Only S7 reads them, after scoring is frozen.

## 10. Gates
Margin source for Δ_pad. The tolerable missed-pad burden at K, set by the user (D-CA1) before scoring. Never from fold spread.
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Target definition committed, agreement above D-CA2, date gap rule met, at least 15 complete blocks, projected width at most 2 Δ_pad | Proceed to S5 |
| Target not observable | Agreement below D-CA2 after one definition amendment | Stop. Report. This is a target result, not a model failure |
| Success (Q1) | Lower bound of recall difference above minus Δ_pad | A terrain-trained pad model screens visible California pads at this budget. Plan a second area |
| Failure (Q1) | Upper bound below minus Δ_pad | Error review by class, density and void fraction. No California claim |
| Inconclusive | Interval spans minus Δ_pad, or ceiling rule hit | Report. Add blocks or use density-scaled K as the descriptive result |
| Q3, Q2 | Not gates | Descriptive and exploratory |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\ca_data_verification.md`, `ca_target_definition.md`, `ca_pad_transfer_ca1.md`, `ca_pad_prereg_ca1.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_ca_wellstar_pull.py`, `_ca_area_pick_fields.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s2_labels\_ca_label_pack_ca1.py`, `_ca_label_agreement_ca1.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_ca_pad_recall_by_class_ca1.py`, `_ca_unmatched_adjudication_ca1.py`, `_ca_status_mismatch_ca1.py`, `_ca_equipment_rule_ca1.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\ca1\results\transfer\` and `data\ca1\results\ca_area_scores_fields.csv`
- Figures. Recall by class with block-bootstrap intervals, blue observed and grey reference. Candidate overlays on hillshade with class shown by marker shape as well as colour.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Urban terrain and burial remove the pad surface | Developed-land cap. Report excluded area. Never score removed pads |
| Equipment present, status says idle | Q2 table keeps both. Status never edits a label |
| Many wells on one pad | Pad is the unit. Wells per pad is an attribute |
| Dense fields exceed K per km² | Ceiling per block. Density-scaled K |
| Imagery and lidar dates differ | Date gap flag and cap. Stratify |
| Equipment displaced by orthorectification | Draw pad ground outline. Equipment as attribute points |
| E3 labels circular with the lidar | Report E3 apart. Never in primary |
| Arid bare ground makes pads look like natural scars | S6 adjudication. Report precision by cover |
| Annotator disagreement | Agreement gate and one definition amendment |
| Frozen model fails on bare terrain | Report as a failure of transfer. Do not retune on the test area |

## 13. Resources
Setup and verification about 24 hours. Labelling about 60 blocks at roughly 20 minutes plus the 20% second pass, about 30 hours (unmeasured, benchmark one block first). Adjudication about 4 hours. Reviewer 2 hours. GPU minutes per window. Disk 3 to 6 GB per 25 km² window on F: (the Los Angeles window is 2.90 GB compressed, measure the rest).

## 14. Handoff and open questions
- Decisions D-CA1 to D-CA4. Pilot field choice.
- Which pad model policy and where the isolated pad out-of-fold raster lives.
- Whether CalGEM carries a pad or lease field.
- Whether a second California field is worth the cost after the first result.
- Stop and report on any failed VERIFY check.

## 15. Documentation updates
The four iteration docs in section 11, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, master plan status, `literature/CITATIONS.md` if any method is taken from a paper.

## Review revision 2 (third review, 2026-11-04) and 2026-11-05 expansion
Urban removal and burial break the terrain-feature proxy. This framework states an observable target, keeps status out of the labels, scores by pad class, reports the density ceiling, and separates imagery-drawn classes from the lidar-drawn class.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16, `docs/plans/adversarial_review_claude.md`.
