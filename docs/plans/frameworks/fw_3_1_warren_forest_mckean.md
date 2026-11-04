# Framework 3.1. Warren, Forest and McKean transfer

**Tier A.** The first real transfer test.
**Evidence level.** (a) drawn features. Association with records is separate (5.6).
**Depends on.** 3.0, P1, P2, reviewers. K = 40 per km² (decided). McKean in scope (decided).
**Blocks.** 3.2 to 3.5 as precedent.

## 1. Problem and objective
The 9t model was trained and tested on one 20 km² tile in Venango County. It is unknown whether its ranking holds in nearby areas.

**Arms.**
- **Arm 1. Within-survey spatial transfer.** Warren (and Forest D20). The same USGS WesternPA 2019 D20 program as 9t. Tests whether the model holds on other ground from the same sensor.
- **Arm 2. Sensor shift.** McKean and the Forest B19 piece. Allegheny National Forest QL1 (about 9 points per m², `PA_Northcentral_2019_B19`). Tests whether the model holds on denser lidar from another program. Gated on Arm 1.

**Hypotheses.** Non-inferiority of recall at K = 40 per km² against 9t, per arm, margin Δ set before scoring.

## 2. Scope
In. Annotation of complete blind test blocks, scoring, preregistration, calibration reporting.
Out. Adaptation fine-tuning (only if Arm 1 fails and the area can hold an adaptation role), association with records.

## 3. Definitions
- Unit, K, scored footprint and interval method as in 3.0.
- **Complete block.** Every feature in the block is annotated, including blocks that hold none. A second annotator re-annotates a random 20% of blocks to estimate completeness.
- **Roles.** Adaptation, test and audit, separated by the derived buffer from P1 S4 (not 500 m). An area too small for all three drops adaptation.

## 4. Inputs
| Input | Path / source | State |
|---|---|---|
| Warren LAZ (7 tiles D20) | `data/_source/lidar/warren_sheffield/USGS_LPC_PA_WesternPA_2019_D20_17TPG*.laz`, 312 MB compressed, 2.8 GB with `_merged_warren_1m.las` | held |
| Warren 1 m derivatives | `data/warren/derived/1m/` | held, wrong resolution, do not use for the frozen model |
| Warren pumpjack pilot | `notebooks/wellsight_v2/s5_eval/_lidar_pumpjack_pilot_warren.py`, `docs/iterations/lidar_pumpjack_pilot_warren.md` | held, context only |
| Warren dense window (15 D20 tiles, 0.79 GB) | `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv` filter Pennsylvania, Warren | listed |
| Forest D20 window (20 tiles, 0.91 GB) and B19 | same list | listed |
| McKean B19 window (36 tiles, 2.11 GB), whole-county subset | list, and `mckean_full.las` (455 MB, EPSG:6346, on F:) | listed / held |
| DEP export | `data/_source/reference/dep_wells/` | held |
| Frozen models | P1 outputs | future |
| Flight dates | USGS project metadata (manifest D1) | to fetch (small) |

## 5. Prerequisites and decisions
- P1 and P2 done. 3.0 scorer certified on 9t.
- Reviewers and an adjudicator named (open).
- The margin Δ for each arm, set in the preregistration.
- The Warren preregistration draft `docs/iterations/transfer_warren_prereg.md` is invalid. Rewrite it from the template.

## 6. Procedure
**S0. Inventory (desk).**
- Script `notebooks/wellsight_v2/s1_build/_warren_inventory.py` (new). `pdal info --summary` per LAZ (CLI through the `run_pipeline` helper). Record tile bounds, point counts, CRS from the header (a reviewer reports NAD83(2011) UTM 17N plus NAVD88, which contradicts an older note), ground-return counts and density per tile.
- Output `data/warren/results/transfer/warren_tile_inventory.csv`.
- Fetch flight dates from USGS project metadata (D1) for the D20 and B19 projects. Record in `docs/iterations/lidar_acquisition_dates.md`.

**S1. Area and block design.**
- Script `notebooks/wellsight_v2/s1_build/_warren_blocks.py` (new). Lay 375 m blocks on the tile mosaic. Mark edge and void blocks.
- Compute the available area. If under about 7 km² after buffers, mark the adaptation role as dropped.
- Assign roles by seeded draw (seed in the preregistration) from blocks stratified by terrain (slope tercile from the 1 m DEM). Audit blocks go to `audit_blocks_warren_v1.csv` (P2 S4).
- Output `data/warren/results/transfer/warren_blocks.gpkg` with `role`.

**S2. Projected width and go decision.**
- Run `_project_ci_width_9t.py` with the number of test blocks and expected density. If projected width exceeds 2Δ, stop. Options. Add tiles from the Warren dense window (listed), add the Forest D20 window, or change Δ with a stated reason. Do not annotate before this passes.

**S3. Rebuild derivatives at 0.5 m.**
- Run the 9t derivative builders on the Warren LAZ with identical parameters (`_build_derivatives.py`, `_build_extra_channels.py`). Thin to 9t ground density if the Warren density differs, then grid at 0.5 m.
- Output `data/warren/derived/05/features_pit_warren_05.tif` (add `.gitignore` rule) and a void-fraction raster. Assert channel order equals `features_pit_9t_05.tif`.
- Time one block first and extrapolate.

**S4. Time one block of annotation.**
- One reviewer annotates one block following the 9t annotation guide (find it in `docs/` and `qgis/annotations`). Record minutes and features found. Use it to size the labelling budget. No model output shown.

**S5. Preregistration.**
- Fill `transfer_prereg_template.md` and commit. Include K = 40, margin, model policy, roles, buffer, hash of the model and split files, and the annotation protocol.

**S6. Blind annotation.**
- Two reviewers per test block using the 9t annotation layers (`pit_inside`, `pit_full`, pad). No model output, no DEP points, no scores. Adjudicate disagreements with a third look. Save `data/warren/results/transfer/warren_truth.gpkg`.
- Completeness check. 20% of blocks re-annotated independently. Report agreement as IoU-matched recall between annotators. This is a reproducibility reference, not a ceiling.

**S7. Inference and scoring.**
- `_transfer_infer.py` on the Warren stack. `_transfer_score.py` on test blocks. Run once.
- Arm 2. Repeat on McKean B19 blocks only after Arm 1 is reported.

**S8. Error review and report.**
- Missed features. Characterise by size, slope, void fraction. Unmatched candidates go to the confuser codebook (6.3), never straight to negatives.
- Write `docs/iterations/transfer_warren_9t_model.md`.

**S9. Association (separate, optional).**
- Hand over to 5.6. Do not mix.

## 7. Statistical analysis plan
- Primary per arm. Recall at K = 40 per km², target minus 9t, block bootstrap, non-inferiority.
- Secondary. Density-scaled K. Calibration shift (Brier, log loss, ECE). Void fraction and ground density as covariates in exploratory regression of block recall.
- Power. Report projected width at the planned block count.
- Dependent units. Pits on one pad are one cluster inside a block. The block is the resampling unit.

## 8. Quality control
- Warren derivatives equal 9t in channel order, units and normalisation.
- Annotated blocks contain no model output exposure (log who annotated).
- Test blocks are at least the derived buffer from adaptation blocks.
- A sample of annotated features is plotted on hillshade and checked for registration.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Projected width at most 2Δ | Annotate |
| Success | Lower bound above minus Δ | Report transfer within survey. Release Arm 2 and 3.2 |
| Failure | Upper bound below minus Δ | Error review. Consider adaptation if the area can hold it. No transfer claim |
| Inconclusive | Spans minus Δ | Report. Add blocks from the listed windows |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\data\warren\results\transfer\` (inventory, blocks, truth, scores, figures)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\transfer_warren_prereg.md` (rewritten), `lidar_acquisition_dates.md`, `transfer_warren_9t_model.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Warren too small | Add the dense window (15 tiles) or Forest D20 window. Drop adaptation |
| Annotation labour too large | Time one block. Reduce blocks only if projected width stays under 2Δ |
| Annotators remember 9t model outputs | Use annotators who have not seen outputs for these blocks, and log it |
| Ground density lower than 9t | Thin 9t to match as a sensitivity arm |
| Forest lidar not ready | Keep Forest unverified until measured. Do not plan on it |

## 12. Resources
Inventory and blocks 8 hours. Derivatives 6 hours plus compute. Annotation unknown until S4, plan two reviewers and an adjudicator. Inference minutes. Disk about 5 GB for Warren, 3 GB for the McKean window.

## 13. Handoff and open questions
- Reviewers. Margin Δ. Whether Warren alone gives enough blocks. Flight dates.

## 14. Documentation updates
New iteration docs above, `analysis_log.md`, master plan, `LEADERBOARD.md` (transfer rows), `BACKLOG.md`.
