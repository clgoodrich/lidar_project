# Framework 3.7. Canada (Alberta, British Columbia, Ontario)

**Tier A (full design, data assumed).** Written 2026-11-05 after the user ended deferral. Nothing here has been run, fetched or measured. Every assumed input is tagged VERIFY in section 5.
**Evidence level.** (a) drawn feature. Provincial orphan and inventory records are administrative. They enter only as level-(d) candidates after the verification ladder in section 3. No level (b) or (c) work is planned. Level (d) needs a field visit.
**Depends on.** 3.0 scorer, P1 isolated model, 3.3 result (Alberta prairie is low relief).
**Blocks.** Any Canadian claim. Any pooled North American statement.

## 1. Problem and objective
Alberta, British Columbia and Ontario hold large orphan and legacy well inventories. The Orphan Well Association (OWA) in Alberta and similar bodies keep lists. Lidar coverage, point density, licence terms, record fields and coordinate quality differ by province. The first draft said Ontario might go first. That rationale was never checked, so this framework lets measured criteria decide.

**Question 1 (primary, per province).** Does a frozen model trained on Pennsylvania terrain recover drawn well features in a province at K = 40 candidates per km², compared with the 9t reference?
**Question 2 (descriptive, per province).** How well do provincial records line up with drawn features, after a shifted-record null, and how good are the record coordinates?
**Question 3 (decision).** Which province, if any, is worth a second window, ranked by the preregistered rule in S2.

**Hypotheses.** Q1 is a non-inferiority test per province with its own margin. Provinces are never pooled. With three provinces there is no inference about "Canada".

**What this study can show.** Whether lidar derivatives and a frozen model transfer into three different land settings (prairie farmland, boreal and foothills forest, southern Ontario farmland and woodlot). How accurate and complete the provincial coordinates look against independent surface features.
**What it cannot show.** That any drawn feature or any record location is a well. That a record is an orphan well. Anything about wells with no surface expression. Province-wide recall, because one window per province is one landscape. Level (d) anything without field verification.

## 2. Scope
In. One pilot window per province (25 km², chosen by criteria, not well count). Blind drawn labels with a local reviewer. Frozen-model scoring under 3.0. Record association inside each province.
Out. Retraining on Canadian data. Pooling provinces. Publishing candidate coordinates on private, Crown or First Nations land without a handling decision. Field visits (a later step needing a partner).

## 3. Definitions
- **Drawn feature.** The 9t classes (pit, pad) drawn by annotators from derivatives. Rules identical to 9t, plus province notes from the reviewer.
- **Record.** A row in a provincial or OWA inventory.
- **Verification ladder for records.**
  - V0. Record exists. Coordinates unverified.
  - V1. The coordinate method is documented (surveyed, GNSS, legal land description converted, unknown) and an uncertainty is stated or can be bounded.
  - V2. An independent source agrees. A site assessment report, regulator photograph or an independent drawn feature inside the stated uncertainty, judged blind.
  - V3. Field confirmed (a person on site, casing or wellhead seen or detected).
  Only V2 records are called level-(d) candidates. Only V3 is level (d). V0 and V1 are never described as candidates for confirmation.
- **Legal land description (LSD).** Alberta and Prairie surface locations are often given as a quarter-section subdivision, so a converted coordinate can be off by hundreds of metres. Ontario legacy wells may be located by lot and concession.
- **Block.** 375 m square, complete blocks only. Eligible area excludes edge blocks and blocks above the void-fraction cap.
- **Window.** 25 km² area chosen by the S2 rule. Primary metric, matching and bootstrap per `fw_00_common.md` section 4.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Frozen model and 9t references | `data/9t/models/pit/unet_cv5/`, `unet_iso_cv5/` (after P1), pad equivalents | held, confirm |
| Scorer and wrapper | `notebooks/wellsight_v2/s5_eval/_transfer_score.py`, `s4_infer/_transfer_infer.py` | planned in 3.0 |
| 9t builders | `s1_build/_build_derivatives.py`, `_build_extra_channels.py` | held |
| Association code (after repair) | 5.6 framework scripts | planned |
| Provincial lidar and records | `data/_source/lidar/<province>/`, `data/_source/reference/wells_<province>/` | proposed |
| US lidar catalogue | `data/_source/reference/lidar_catalogue/` | held, United States only, gives no Canadian tiles |

## 5. Assumed data
Every row is an assumption and every row carries a VERIFY test. Portal names are starting points to check, not confirmed addresses.
| Province | Item | Assumed to exist | Format, CRS | Fields | Licence and access | VERIFY (how) |
|---|---|---|---|---|---|---|
| Alberta | Lidar | Provincial bare-earth and point cloud for part of the province, mostly agriculture and forest | LAZ or LAS, NAD83(CSRS) with 3TM or UTM zones 11 and 12, CGVD2013 | Classification, return, GPS time | Open government licence, terms for derived products unchecked | Find the lidar catalogue. List projects over known orphan clusters. Read a header. Measure ground density, void fraction, flight date |
| Alberta | Wells | Regulator licence list with well status, surface location, spud and abandonment dates | CSV or database, locations from legal land description converted to lat and lon | UWI, status, licensee, spud, abandonment, surface coordinates, coordinate source | Open, terms unchecked | Download one snapshot with its date and hash. Count rows. Check whether a coordinate-method field exists and what share of wells have one |
| Alberta | Orphan list | OWA inventory of orphan wells, pipelines and sites | Web list or CSV | Licence number, status, location, site type | Public listing, reuse terms unchecked | Obtain the list. Record fields, date, count. Treat every row as V0 |
| British Columbia | Lidar | LidarBC airborne programme, many projects, province-wide gaps | LAZ, NAD83(CSRS) UTM 9 to 11, CGVD2013 | Classification, return, GPS time | Open government licence, terms unchecked | List projects over oil and gas areas (northeast). Read headers. Measure density and forest cover |
| British Columbia | Wells | Energy regulator well records and the dormant or orphan site programmes | Shapefile or CSV, NAD83 | Well authorisation number, status, surveyed location, dates | Open, terms unchecked | Download. Check status vocabulary. Check coordinate method |
| British Columbia | Orphan list | Orphan site inventory kept by the regulator or its fund | Web list | Site, status, location | Unknown | Ask for the list. Treat as V0 |
| Ontario | Lidar | Provincial lidar programme, with classified point clouds over southern Ontario | LAZ, NAD83(CSRS) UTM 17 (or 16 and 18), CGVD2013 | Classification, return, GPS time | Open government licence, terms unchecked | List projects over Lambton, Elgin, Norfolk. Read headers. Measure density and flight season |
| Ontario | Wells | Oil, Gas and Salt Resources Library well records | Database export, mixed coordinate sources | Well ID, status, depth, drill date, location, source of location | Public library, bulk export terms unchecked | Check for a bulk export. Count wells with pre-1930 drill dates. Check how many locations come from lot and concession |
| Ontario | Orphan list | Provincial orphan or abandoned well lists, plugged and unplugged | Unknown | Unknown | Unknown | Find out whether any exists. If none, drop the V-ladder test for Ontario and say so |
| All | Imagery | Provincial or satellite imagery near the lidar date | GeoTIFF, 0.2 to 1 m | Date | Varies | Confirm the date and licence. Do not use any source whose terms bar drawing labels |
| All | Reviewer | One regional reviewer per province who knows the local well types | Not data | Class decisions on 20 features | Volunteer | Confirm a name before any labelling. If none, that province is not run |

Vertical datums are CGVD2013 or CGVD28 and the 9t stack uses NAVD88. Elevation differences between datums are constant offsets and do not change derivatives. Record which datum each tile uses.

## 6. Prerequisites and decisions
User decisions before preregistration.
- **D-CA-N1.** Margin Δ per province (missed features per 100 at K) with its source.
- **D-CA-N2.** Which provinces to run first. Default is the inventory ranking, not Ontario.
- **D-CA-N3.** Data handling. Whether candidate coordinates may be stored beyond the project, and how land tenure is respected.
- **D-CA-N4.** Reviewer names.
Prerequisites. P1, 3.0 scorer certified, 3.3 result read (Alberta prairie is low relief and may need that gate first).

## 7. Procedure
**S0. Metadata verification.** Run every VERIFY check. Write `docs/iterations/canada_data_inventory.md` with one table per province. Record links, dates, counts, hashes. Stop at any failure and report.
- Script `notebooks/wellsight_v2/s1_build/_can_inventory_pull.py` (proposed). Output `data/_source/reference/wells_can/` per-province snapshots with SHA-256, and `data/can/results/can_inventory_rows.csv`.
- Query helper rule. Separate successful-empty, failed and incomplete results. Paginate and compare the returned total with the retrieved count.

**S1. Measure one tile per province.** Fetch one lidar tile. Measure ground density, void fraction, classes, flight date. Script `s1_build/_can_tile_probe.py` (proposed). Output `data/can/results/can_tile_probe.csv`.

**S2. Window choice by a preregistered rule.** Ranking is lexicographic, not a weighted score.
1. Licence allows derived products and internal labelling. 2. Measured ground density at or above the eligibility cut. 3. Record coordinates carry a documented method. 4. A regional reviewer is committed. 5. At least 15 blocks with expected drawn features by a pilot count. 6. Terrain and cover similarity to 9t (slope, canopy) as a tie-break only.
- Script `s1_build/_can_window_pick.py` (proposed). Output `data/can/results/can_window_scores.csv`. Windows are not chosen by well count alone.
- Pilot first. Label 3 to 5 features near records in the chosen window and confirm the pipeline runs before scaling.

**S3. Fetch, derive, infer.** One window per province. Build 0.5 m derivatives with the 9t builders. Run the frozen model. Output to `data/<prov>/results/transfer/<run_id>/` with `<prov>` as `ab1`, `bc1`, `on1` (proposed).
- Scripts `s4_infer/_transfer_infer.py` (3.0). Checks as in 3.0 S3.

**S4. Blind labelling.** Annotators draw pits and pads with no model output and no record points. The reviewer checks 20 features and rules on province types. Two annotators repeat a 20% block subset.
- Script `s2_labels/_can_label_agreement.py` (proposed). Output `data/<prov>/results/can_label_agreement_<prov>.json`.

**S5. Scoring.** `s5_eval/_transfer_score.py` per province, own prereg, own margin. Report density, void fraction, ceiling per block.

**S6. Record association and coordinate quality.** After scoring is frozen. Use the corrected 5.6 rules. Full detector output, shifted-set null translating the whole record set, normalised excess with an interval, never a precision claim. Per record, report the nearest drawn feature distance and the coordinate method. Assign V-ladder levels only with independent evidence.
- Script `s5_eval/_can_record_association.py` (proposed). Output `data/<prov>/results/can_record_assoc_<prov>.csv`.

**S7. Province ranking.** Fill the section 10 ranking table from measured values. Write the recommendation.

## 8. Statistical analysis plan
- **Primary per province.** Recall at K = 40 per km² on drawn features, province minus 9t reference, block bootstrap B = 2000, non-inferiority against Δ for that province.
- **Projected width first.** `_project_ci_width_9t.py` with the province block count and density. Change design if width exceeds 2 Δ.
- **Secondary.** Recall at density-scaled K. Calibration shift. Recall by slope tercile and void fraction (exploratory).
- **Association (exploratory).** Excess over the shifted null at the preregistered radius per province. LSD records use a radius set from their stated uncertainty. Report retained record count per shift.
- **Between provinces.** Descriptive only. Three landscapes cannot identify what differs.
- **Few blocks.** Add a permutation interval below 15 blocks.
- Each table carries a level. Drawn-feature rows are (a). Record rows say V-level and never claim (d).

## 9. Quality control and leakage checks
1. Row counts at every join. CRS and datum asserted per source. No raster read without a transform check.
2. No Canadian data in any training, cutoff or selection list. Assert by checkpoint hash.
3. Annotators blind to records and scores. Check the label-pack manifest.
4. Record snapshots hashed with the fetch date. Rows never edited in place.
5. Query completeness check (section 7 S0).
6. Same code path as 9t (module hash).
7. Same-config rerun identical. Seed per block.
8. Coordinates of candidates are stored under the D-CA-N3 rule.
9. Sanity render per raster and two features on hillshade.

## 10. Gates
Margin source. The tolerable missed-feature burden at K per province, stated by the user before scoring (D-CA-N1). Never fold spread.
| Outcome | Rule | Action |
|---|---|---|
| Inventory readiness | Every VERIFY row for a province is answered, a reviewer is committed, licence permits use | Run that province |
| Province not runnable | Any of licence, reviewer or lidar density fails | Record. Do not score |
| Success (per province) | Lower bound of recall difference above minus Δ | Terrain-trained detection screens this window. Not a provincial claim |
| Failure | Upper bound below minus Δ | Error review. No claim |
| Inconclusive | Interval spans minus Δ, or projected width above 2 Δ | Report. Add blocks |
| Record association | Not a gate | Exploratory excess with a null |
| Record promotion | V2 evidence for a record | Label a level-(d) candidate. V3 only after a visit |

Ranking table for S7 (filled from data, never from belief).
| Province | Ground density | Licence ok | Coordinate method | Reviewer | Blocks expected | Rank |
|---|---|---|---|---|---|---|

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\canada_data_inventory.md`, `can_transfer_ab1.md`, `can_transfer_bc1.md`, `can_transfer_on1.md`, `can_prereg_<prov>.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_can_inventory_pull.py`, `_can_tile_probe.py`, `_can_window_pick.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s2_labels\_can_label_agreement.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_can_record_association.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\can\results\` and `data\ab1\results\transfer\`, `data\bc1\...`, `data\on1\...`
- Figures. Recall with bootstrap intervals per province, blue observed, grey reference, one panel each. No pooled panel.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Licence bars derived products | Province not run. Record the terms |
| Coordinates from legal land descriptions | Radius from stated uncertainty. Report method share |
| Prairie terrain is flat | 3.3 first. Report slope strata |
| Agricultural tillage hides pads | Flight season recorded. Report void and cover |
| Different well types than Pennsylvania | Reviewer rules. Class notes in the target doc |
| Orphan list rows treated as truth | V-ladder. Never above V0 without evidence |
| Datum or zone mix-ups | Assert per source. Log |
| Candidate coordinates on private or Crown land | D-CA-N3 handling rule |
| Few blocks | Projected width. Permutation interval |

## 13. Resources
Inventory and tile probes about 20 hours across three provinces. Labelling about 15 to 30 hours per province (unmeasured, benchmark one block). Reviewer 2 hours each. GPU minutes per window. Disk 3 to 6 GB per 25 km² window on F: (measure first, do not infer from file size).

## 14. Handoff and open questions
- D-CA-N1 to D-CA-N4. Reviewer names.
- Whether Ontario has any orphan list.
- Whether a provincial licence permits sharing candidate maps.
- The 3.3 slope result for Alberta.
- Stop and report on a failed VERIFY.

## 15. Documentation updates
The inventory doc and province docs, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, master plan, `literature/CITATIONS.md` (data sources and licences cited).

## Review revision 2 (third review, 2026-11-04) and 2026-11-05 expansion
The earlier text allowed metadata only. This framework keeps the inventory as the first stage and adds per-province scoring, the record verification ladder, and a ranking rule that cannot favour Ontario by assumption.
Source. `docs/plans/protocol_gates_and_metrics.md` sections 4, 5 and 16.
