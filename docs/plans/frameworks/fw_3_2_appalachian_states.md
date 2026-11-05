# Framework 3.2. Ohio, West Virginia, New York and Kentucky

**Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded or scored.**
**Evidence level.** (a) drawn feature, per window. State records enter only as level (b) and only through 5.6. Level (c) and (d) are never produced here.
**Depends on.** 3.0 scorer, P1 (isolated model and derived buffer), P2 (audit guard). 3.1 supplies the preregistration template and annotation guide. Desk steps S0 to S4 do not wait for 3.1.
**Blocks.** State program briefings. 5.2 and 5.6 for the dated NY and KY records.

## 1. Problem and objective
The 9t model learned pits and pads in Venango County, Pennsylvania. Old wells in Ohio, West Virginia, New York and Kentucky sit in similar terrain. Their records, status codes and lidar programs differ. This framework measures whether the frozen model ranks drawn features as well there as on 9t.

**Q1 (primary, per window).** Is recall at K = 40 candidates per km² on native lidar in a window not worse than the 9t reference by more than a margin Δ_w?
**Q2 (descriptive, per state).** Do the two windows in one state agree?
**Q3 (conditional, own preregistration).** If a primary window fails, does adaptation on its companion window recover recall on the primary window?
**Q4 (desk).** Which state records can feed 5.2 and 5.6, and at what position quality? No scoring.

**Hypotheses (Q1).** H0 recall(window) minus recall(9t reference) is at or below minus Δ_w. H1 it is above minus Δ_w.

**What this study can show.** Whether ranking of drawn features transfers to seven windows in four states under native lidar density, with intervals.
**What it cannot show.**
- That any candidate is a well. Every result is level (a).
- A state effect. Two windows per state give a pair, not a variance. No between-state statistic is estimated.
- Whether program, sensor or ground causes a gap. Geography and acquisition move together. Thinning to 9t density is a sensitivity arm and cannot reproduce canopy holes or scan geometry.
- Performance outside windows chosen for many documented wells. Selection raises feature density, and recall at a per-km² budget moves with density alone. Density is reported and a density-scaled secondary is computed.
- Agreement with any annotator other than the 9t annotators' feature concept.

## 2. Scope
In. Desk inventory, status harmonisation, union-coverage audit, ground-density audit, blind annotation of complete blocks, zero-shot scoring, a conditional adaptation experiment, a hand-off table to 5.6.
Out. Between-state comparison statistics. Level (d) claims. Association scoring (5.6). Roads. Any state with no window in section 4.

## 3. Definitions
- **Window.** A 25 km² square (about 177 blocks of 375 m) centred on the densest cluster of documented orphans in a county (`lidar_win_windows_us.csv`). Chosen by well count alone.
- **Primary window.** The window whose Q1 gate decides the state's headline. **Companion window.** A second county on the same lidar project, used as a second descriptive test or as the adaptation source for Q3. A window is never test and adaptation in the same experiment.
- **Roles.** Test (scored once), audit (P2 guard, final claims, checked once), adaptation (Q3 only, companion windows only). Roles inside one window are separated by the derived P1 buffer. If that buffer leaves fewer than N_min eligible test blocks, the window is enlarged to 10 km by 10 km (proposed extension) and the tile list is rebuilt.
- **Eligible block.** Complete 375 m block, inside tile union, void fraction at or below the cap, ground density at or above the eligibility rule. The density rule is a chosen rule, not the QL2 definition. Reason. Blocks below the 5th percentile of 9t block ground density lie outside the training regime. They form a labelled low-density stratum, never a silent drop.
- **Harmonised status.** Original status code, original definition text, and one scheme (active, plugged, abandoned, orphan, other). The original columns are kept.
- Unit, K, scored footprint, matching and intervals follow `fw_00_common.md` section 4. K = 40 per km² of eligible area. 30 is a sensitivity only.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| State well records | `data/_source/reference/wells_ny_dec/`, `wells_oh_odnr/`, `wells_ky_kgs/`, `wells_wv_dep/`, `wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| County orphan counts | `data/_source/reference/wells_us_orphan_2026/area_orphan_counts_by_county_us.csv` | held |
| Rebuilt windows, projects, tile lists | `data/_source/reference/lidar_catalogue/lidar_win_windows_us.csv`, `lidar_win_projects_us.csv`, `lidar_win_download_list_us.csv`, `lidar_win_download_summary_us.csv`, `lidar_win_query_log_us.csv` | held (discovery only) |
| 9t out-of-fold pit raster | `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` | held (sanity only) |
| Isolated models, split file, derived buffer, audit guard | P1 and P2 outputs | future |
| 9t derivative builders | `notebooks/wellsight_v2/s1_build/_build_derivatives.py`, `_build_extra_channels.py` | held |
| Scorer, inference wrapper, projected-width tool | `s5_eval/_transfer_score.py`, `s4_infer/_transfer_infer.py`, `s5_eval/_project_ci_width_9t.py` | 3.0 deliverables |
| Annotation guide and layers | 3.1 S6 (`pit_inside`, `pit_full`, pad) | held, locate |

### 4A. Assumed data
Each line says what is assumed to exist. VERIFY says how to check it before the step that needs it.
| Item | Assumed | Format, resolution, fields, CRS, licence | VERIFY |
|---|---|---|---|
| Primary windows | NY Allegany, OH Washington, KY Lee, WV Pleasants | LAZ, 3DEP QL2 (NY_SouthwestNY_2017_A17, OH_Statewide_Phase2_2020_B20, KY_WestCentral_2017_C19, WV_FEMAR3_Southcentral_2018_D19). Native CRS and vertical datum from each header, NAD83 UTM 17N (EPSG:6346) expected for all four windows. USGS public domain | `pdal info --summary` on one tile per window through `run_pipeline`. Assert CRS, point count, class-2 count |
| Companion windows | NY Cattaraugus, OH Monroe, KY Powell, and a WV Ritchie window (proposed, not in the rebuilt list) | Same projects as the primary where listed. Ritchie project unknown | Run the listing script for Ritchie. Pleasants has 57 documented wells in its window, so a thin test |
| Union coverage | Tiles cover the windows | Allegany A17 covers 0.933 of the window (`best_partial`). Cover is an area upper bound from tile boxes | Compute union area from tile geometries inside the window. Drop uncovered blocks. Never use tile-count ratios |
| Pleasants project | WV D19 FEMA project is the right one | The rebuilt list shows 42 tiles at 4.06 GB. The superseded list showed 19 Ohio-project tiles | Intersect tile geometries with the window. Name the project that covers it |
| Flight dates and season | Leaf-off or low-leaf | USGS project metadata XML. The API has none (publication date is not flight date) | Open each project's metadata. Record dates in `docs/iterations/lidar_acquisition_dates.md` |
| Ground classification | ASPRS class 2 present and usable | LAS 1.4, classes 2 and 9 | Count class 2 per block. If missing, reclassify with PDAL SMRF through the CLI and call it a separate pipeline arm |
| State records | Coordinates usable at pad scale | Fields assumed. Latitude, longitude, status, well type, spud or completion date, coordinate method. Datum may be NAD27 for legacy records | Read each data dictionary. Record datum per source. Compare 20 records to hillshade pads |
| Dated old wells | NY since 1860 and KY completion dates | `ny_oil_gas_regulated_wells_since_1860.csv`, KY `kyog_dd.zip` | Count rows with a date before 1930. Treat the 1800 sentinel as unknown, never early |
| Land cover | NLCD 2021 30 m | GeoTIFF, EPSG:5070 | Pattern of `s1_build/_fetch_nlcd_9t.py` (proposed `_fetch_nlcd_appalachia.py`) |
| Annotators | Two reviewers per window and one adjudicator who have not seen model output for these blocks | People | Roster file `docs/iterations/transfer_roster_appalachia.md` (proposed). Log exposure |
| 9t reference | Isolated out-of-fold predictions under one declared policy | P1 outputs | P1 gate passed. Else state original-sampler optimism |

## 5. Prerequisites and decisions
P1 and P2 done. The 3.0 scorer is certified on 9t. Per window, before annotation.
- Union coverage, void and ground-density audit written.
- Δ_w fixed in burden units (additional missed features per km² a state program would accept, set against the cost of reviewing 40 candidates per km²). It is converted to recall points with the frozen truth density, still before any model scoring.
- Model policy named (one model or an ensemble) with hash.
- Preregistration `docs/iterations/transfer_prereg_<tag>.md` committed (tags `ny_alg`, `ny_cat`, `oh_wash`, `oh_mon`, `ky_lee`, `ky_pow`, `wv_ple`).

## 6. Procedure
**S0. Desk inventory.** Script `notebooks/wellsight_v2/s1_build/_inventory_wells_appalachia.py` (new). Per state record source, status definitions, coordinate method and accuracy field, datum, dates, access route, licence, row count and hash. Output `data/_source/reference/state_inventory_appalachia.csv` and `docs/iterations/state_data_inventory.md`.

**S1. Status harmonisation and datum.** Script `s1_build/_harmonise_well_status_us.py` (new). Output `data/_source/reference/wells_status_harmonised.csv`. Check row counts per source equal inputs. Convert any NAD27 coordinates with a logged transformation and report the shift in metres. Flag records with a coordinate precision under 5 decimal places.

**S2. Coverage and query audit.** Script `s1_build/_window_coverage_union_us.py` (new). Read `lidar_win_query_log_us.csv` and separate successful-empty, failed and incomplete queries. Compare returned totals with retrieved counts. Compute union tile coverage per window from geometries. Output `data/_source/reference/lidar_catalogue/lidar_win_union_cover_us.csv`. Windows below the prereg cover share are enlarged or dropped.

**S3. Ground density and void audit.** Script `s1_build/_ground_density_by_block_us.py` (new, shared with 3.4 and 3.5). Fetch one tile per window first (gated, hash, own folder). Measure class-2 density and 0.5 m void fraction per block with the PDAL CLI. Compare with 9t (2.70 points per m² overall, void 45.2% of cells at 0.5 m). Output `data/<area>/results/transfer/xfer_density_void_<tag>.csv`. Ohio 2006 and 2007 projects (about 3 MB tiles) are not used. Stop for a user decision if a window median is far below the 9t 5th percentile.

**S4. Blocks and roles.** Script `s1_build/_transfer_blocks_us.py` (new). Lay 375 m blocks on the tile union. Mark edge, void and low-density blocks. Draw roles by seeded draw (seed in prereg), stratified by slope tercile from the 1 m DEM. Output `data/<area>/results/transfer/xfer_blocks_roles_<tag>.gpkg` and `audit_blocks_<tag>_v1.csv`.

**S5. Projected width and go decision.** Run `_project_ci_width_9t.py` with the planned test block count and a grid of target densities and cluster sizes, not only 9t resampling. Resample blocks of the 9t out-of-fold map for the reference side and report that its own uncertainty enters the difference. If projected width exceeds 2Δ_w, change the design before labelling. Output `data/9t/results/transfer/projected_ci_width_appalachia.csv`.

**S6. Time one block, then derivatives.** One reviewer annotates one block (minutes, features). Build 0.5 m derivatives with the 9t builders and identical parameters on native points. Output `data/<area>/derived/05/features_pit_<tag>_05.tif` (add a `.gitignore` rule per new directory, `F:` for heavy files). Assert channel order equals `features_pit_9t_05.tif`.

**S7. Preregistration, then blind annotation.** Fill the template and commit. Two reviewers per test block annotate complete blocks, including empty ones. No model output, no state well points, no scores. Adjudicate by a third look. Re-annotate a random 20% of blocks independently and report IoU-matched agreement as a reproducibility reference, not a ceiling. Output `data/<area>/results/transfer/xfer_truth_features_<tag>.gpkg`.

**S8. Inference and scoring, once.** `_transfer_infer.py` then `_transfer_score.py` per window with the frozen policy. Write `xfer_score_k40_<tag>.json`. One scoring run per preregistration.

**S9. Sensitivities.** (i) K = 30. (ii) Density-scaled K. (iii) 9t block-thinned arm to 9t ground density on the same blocks, labelled sensitivity. (iv) Low-density stratum. (v) Super-block bootstrap (side set by the P1 correlogram range). If (v) changes a gate outcome, report both and flag for the user.

**S10. Error review.** Characterise misses by size, slope, void and ground density. Unmatched candidates go to the confuser codebook (6.3), never straight to negatives.

**S11. Adaptation (Q3, conditional).** Only if a primary window fails. Companion window zero-shot score is recorded first and then the window is burned for adaptation. Fine-tune from the isolated checkpoint with norm statistics fitted on adaptation blocks only. Evaluate on the primary window's test blocks, paired. Own preregistration. Output `data/<area>/results/transfer/xfer_adapt_paired_<tag>.json`.

**S12. State table and hand-off.** Script `s5_eval/_state_transfer_table_appalachia.py` (new). One descriptive row per window, no pooled gate. Pass the harmonised records to 5.6 without scoring them.

## 7. Statistical analysis plan
- **Estimand.** θ_w = recall at K = 40 per km² in window w minus recall at the same K on the 9t reference, pooled counts over complete eligible blocks.
- **Unit.** The 375 m block. Pits on one pad are one cluster inside a block. Detections and seeds are not independent.
- **K policy.** 40 per km² of eligible area, top K ranked by score, ties by larger area then blob id.
- **Interval.** Independent block bootstraps per area, B = 2000, percentile 95%. Fewer than 15 test blocks adds a permutation interval and a note that the bootstrap is unreliable.
- **Roles.** Adaptation fits the model (Q3 only). Test is scored once. Audit supports the final claim and is opened once. Nothing in test or audit may select a threshold, epoch or margin.
- **Buffers.** Derived (receptive field plus patch support plus correlogram range of 9t out-of-fold residuals), never 500 m.
- **Primary.** One estimand per window. Non-inferiority against minus Δ_w.
- **Secondary.** Recall at density-scaled K. Brier, log loss, ECE. Target feature density. The reference reuses 9t uncertainty.
- **Exploratory.** Recall by slope, void, ground density and block feature density, labelled exploratory.
- **State summary.** A table of windows with intervals. Optional pooled descriptive recall across windows is a different estimand (average over these windows, not a population of states) and carries no gate.

## 8. Quality control and leakage
1. Row counts at every join. Expected and observed counts in the run log.
2. CRS asserted on every read (6346 for the primary windows). Per-window EPSG is a config value. Datum of each state record source recorded.
3. No NaN block ids. No duplicate ids. No candidate counted twice.
4. No training window intersects any test or audit block. Normalisation fitted on training windows only. No audit block in any training, calibration, mining or selection list.
5. Annotators did not see model output, scores or state well points. Exposure logged per block.
6. Union coverage from geometries. Query log reconciled (empty, failed, incomplete kept apart, totals compared).
7. Hash match for tiles, checkpoints, split file and prereg.
8. Same module hash for 9t and target scoring. A second run with the same config gives identical outputs.
9. Registration check. Ten annotated features per window plotted on hillshade.
10. Every number in a doc comes from a saved file.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Union cover at least the prereg share, at least N_min eligible test blocks, projected width at most 2Δ_w | Annotate |
| Success (per window) | Lower bound of θ_w above minus Δ_w | Report transfer for this window at level (a). State headline remains a pair of windows, not a state effect |
| Failure | Upper bound of θ_w below minus Δ_w | Error review. No transfer claim. Q3 allowed |
| Inconclusive | Interval spans minus Δ_w, or projected width above 2Δ_w | Report as inconclusive. Add blocks from the extension |
| Density | Window median ground density under the rule | Low-density stratum reported. Window dropped before annotation if under N_min eligible blocks |
Margin source. Δ_w comes from the missed-feature burden at K = 40 versus review cost, fixed in the prereg before scoring. It never comes from fold spread or interval width. Inconclusive is expected for the small windows (Pleasants).

## 10. Deliverables
All paths are repo-relative.
- `notebooks/wellsight_v2/s1_build/_inventory_wells_appalachia.py`, `_harmonise_well_status_us.py`, `_window_coverage_union_us.py`, `_ground_density_by_block_us.py`, `_transfer_blocks_us.py`
- `notebooks/wellsight_v2/s5_eval/_state_transfer_table_appalachia.py`
- `data/_source/reference/state_inventory_appalachia.csv`, `wells_status_harmonised.csv`, `lidar_catalogue/lidar_win_union_cover_us.csv`
- `data/ny_allegany/results/transfer/`, `data/ohio_washington/results/transfer/`, `data/ky_lee/results/transfer/`, `data/wv_pleasants/results/transfer/` and the companion folders, each with density, blocks, truth, score and figures
- `docs/iterations/state_data_inventory.md`, `transfer_prereg_<tag>.md`, `lidar_acquisition_dates.md`, `transfer_appalachia_9t_model.md`
- Figures use blue `#1F5FA8`, orange `#D97706`, grey `#8E959B`. Validator worst-pair numbers go beside the palette in each plotting script.

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Window coverage partial (Allegany 0.933) | Union geometry audit. Drop uncovered blocks and report area |
| Wrong project assumed (Pleasants) | Name the project from geometry before fetch |
| Low ground density or heavy void | Low-density stratum. Stop for user if far below 9t |
| Datum error in legacy records | Datum recorded per source. Shift measured. Matters for 5.6, not for scoring |
| Leaf-on flight | Flight dates first. Report season. Exclude from the claim if leaf-on |
| Annotators remember 9t outputs | Roster and exposure log. Use reviewers new to these blocks |
| Selection toward high well counts | Report density. Density-scaled K |
| Correlated neighbouring blocks | Super-block bootstrap sensitivity |
| Small windows give wide intervals | Projected width gate. Enlarge to 10 km |

## 12. Resources
These are estimates to be replaced by measurement in S3 and S6.
- Desk S0 to S2. About 10 hours per state, 40 hours in total.
- Per window. Tile fetch 1.2 to 4.5 GB compressed (Ohio 182 to 205 small tiles, 3.5 to 13.6 GB by window). Decompressed clouds run 3 to 9 times larger (Warren is 312 MB to 2.8 GB). Derivative stack is about 0.4 GB per channel for 25 km² at 0.5 m. Put heavy files on F:.
- Annotation. Blocks times minutes per block times two reviewers. Planning placeholder 60 blocks and 15 minutes per block gives about 30 reviewer-hours per window. Replace with S6 timing.
- Inference. Minutes to an hour per window on the GTX 1070 Ti. Q3 adaptation needs measured epoch time first (the backlog notes epoch time was under-reported by 1.8 times).
- Run the large-file audit after every fetch and build.

## 13. Handoff and open questions
- Margin Δ_w in burden units, and N_min.
- Confirm the primary versus companion pairing. KY Cumberland (A23) is a different program and is held in reserve.
- Reviewers and an adjudicator.
- Confirm the Ritchie window and the Pleasants project.
- Whether a super-block disagreement should override the block bootstrap.
- Confirm all state coordinate datums.

## 14. Documentation updates
`state_data_inventory.md`, `transfer_prereg_<tag>.md`, `transfer_appalachia_9t_model.md`, `analysis_log.md` (top entry each pass), `LEADERBOARD.md` (transfer rows), `BACKLOG.md`, `literature/CITATIONS.md` for any new method, master plan status.

## Review revision 2 (third review, 2026-11-04)
The catalogue is discovery only. Repair completeness (pagination, failed versus empty queries, asset-to-window table, union coverage) before selecting a county. One county does not represent a state.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

## Review revision 3 (full rewrite, 2026-11-05)
Built in from `adversarial_review_claude.md` and `review_response_20261104.md`. Native density is primary and thinning is a sensitivity. The buffer is derived. The margin comes from burden. The reference is the isolated 9t baseline with its own uncertainty. Coverage comes from geometries. No state variance is estimated and no level (d) claim is made.
