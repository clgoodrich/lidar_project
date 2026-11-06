# Framework 3.0. Transfer protocol

**Tier A.** The shared test that every geographic item uses.
**Evidence level.** (a) drawn features. It does not score well records.
**Depends on.** P1, P2, K policy (decided, 40 per km²).
**Blocks.** 3.1 to 3.8, 7.4.

## 1. Problem and objective
Without one shared protocol each region gets a different, hard-to-compare test. The first draft defined K two ways and compared against a cutoff-based reference.

**Objective.** One deterministic scoring pipeline that takes a probability raster, a scored footprint and a set of annotated features, and returns recall at K per km² with block-bootstrap intervals, calibration and density. The same code scores 9t and every target.

**Hypotheses.** For a target area T and the 9t reference R at K = 40 per km². H0 recall(T) is worse than recall(R) by at least the margin. H1 it is not. Margin set per experiment before scoring.

## 2. Scope
In. Scoring code, inference wrapper for new areas, preregistration template use, reproduction on 9t.
Out. Annotation (3.1), association with records (5.6), model retraining.

## 3. Definitions
- Primary metric, candidates and matching, scored footprint, interval method. See `fw_00_common.md` section 4.
- K = 40 candidates per km² of scored eligible area (user, 2026-11-04).
- **Eligible area.** Union of complete scored blocks minus edge blocks that touch the data boundary or have void fraction above a preregistered cap.
- **Secondary metric.** Recall at K = c times target feature density per km², c fixed from 9t.
- Reference. Two. Archival, rebuilt from the sweep's own fold object tables, cutoffs, fold areas and tie rules (`s5_eval/_operating_point_policy_sweep_pit_pad_9t.py`). New baseline, one declared policy on isolated, fold-local-normalised out-of-fold predictions. The saved mosaic `pit_prob_floor_outoffold_9t_05.tif` is uint8 (DN / 254) and only supports a sanity check. Pad rasters, path to confirm.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| 9t out-of-fold pit raster | `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` | held |
| 9t annotations | `qgis/annotations/annotations_proj.gpkg` (layers `pit_inside`, `pit_full`, pads) | held |
| 9t blocks | `data/9t/derived/05/pit_blocks_9t.gpkg` | held |
| Operating-point sweep results | `docs/iterations/operating_point_policy_sweep_pit_pad_9t.md` and its script | held, locate the script |
| Frozen model checkpoints | `data/9t/models/pit/unet_cv5/fold*/` (original), `unet_iso_cv5/` (after P1) | held / future |
| Target lidar | per area, see 3.1 and others | varies |
| Inference templates | `notebooks/wellsight_v2/s4_infer/_infer_pit_pad_613590_05.py`, `_predict_on_tile.py` | held |

## 5. Prerequisites and decisions
P1 done. P2 done (for final claims). K = 40 per km² decided. The margin is set in each preregistration.

## 6. Procedure
**S0. Locate and read the operating-point code.**
- `grep -rn "candidates per km\|FROC\|budget" notebooks/wellsight_v2/s5_eval/ | head`. Record the script that produced the sweep. Do not rewrite it. Wrap it.

**S1. Scoring module.**
- Script `notebooks/wellsight_v2/s5_eval/_transfer_score.py` (new). CLI.
  `python _transfer_score.py --prob <raster> --footprint <gpkg> --truth <gpkg:layer> --blocks <gpkg> --k 40 --prereg <md> --out <run_dir>`
- Steps.
  1. Read footprint and blocks. Assert CRS 6346. Derive eligible area in km².
  2. Polygonise the probability raster once over the whole raster at the `ek.policy_for(task)` cutoff (pit 0.35, pad 0.525), min 4 m², mean-probability score. 0.10 is the sensitivity (amended 2026-11-06, review F02).
  3. Dedupe candidates that are second pieces of one feature (centroid inside an already matched truth feature).
  4. Greedy one-to-one matching at IoU 0.3 in candidate score order, then rank and keep the top K times area (amended 2026-11-06).
  5. Per block counts (candidates kept, truth, matched).
  6. Pooled recall. Block bootstrap (B = 2000, seed from preregistration). Density per km².
  7. Secondary recall at K = c times density.
  8. Calibration metrics from raw probabilities (Brier, log loss, ECE).
  9. Write `transfer_score.json`, `transfer_blocks.csv`, and a recall-versus-K curve figure (K from 10 to 80).
- Outputs include the hash of every input and the preregistration.

**S2. Reproduce 9t.**
- Archival check. Rebuild the historical statistic from the sweep's per-fold object tables (`cv5_sweep_objects_*`), fold-specific cutoffs, fold areas (budget floored per fold) and tie rules. Target 0.781 at 30 (fold range 0.723 to 0.900) and 0.909 at 40 (0.881 to 0.935). Acceptance. Matches to three decimals. Every discrepancy is explained.
- Mosaic check. Run S1 on the uint8 mosaic as a sanity comparison only. Quantisation and seams are expected to differ. Report the gap, do not gate on it.
- New baseline. After P1, run S1 on isolated out-of-fold predictions under one declared policy (one model or an ensemble). Compute it twice from a clean state. It must repeat exactly.
- Write `docs/iterations/transfer_reproduce_9t.md`. Neither check is a transfer result.

**S3. Inference wrapper for new areas.**
- Script `notebooks/wellsight_v2/s4_infer/_transfer_infer.py` (new). CLI.
  `python _transfer_infer.py --area warren --tiles <list> --model <ckpt dir> --out <run_dir>`
- Steps. Build 0.5 m derivatives with the 9t code path (`s1_build/_build_derivatives.py`, `_build_extra_channels.py`), not a different pipeline. Native target density is primary. A thinned arm is a separate sensitivity analysis. Run the frozen model over all five folds and average probabilities only if the preregistration says so (otherwise one model, named). Write probability raster and a void fraction raster.
- Check. Channel count and order equal the 9t feature stack. Normalisation from the saved `norm_stats`. Assert no NaN band.

**S4. Projected width tool.**
- Script `notebooks/wellsight_v2/s5_eval/_project_ci_width_9t.py` (new). Input n_blocks and feature density. Resample from the 9t blocks. Output the median interval width and the share of resamples with lower bound above minus Δ for a few Δ values. Write `data/9t/results/transfer/projected_ci_width_9t.csv`.

**S5. Preregistration.**
- Copy `docs/iterations/transfer_prereg_template.md` (section 11 fields). Fill and commit before any target scoring.

**S6. Pad and road extensions.**
- Same scorer with the pad out-of-fold raster and pad truth. Roads need a length-based recall and are out of scope here.

## 7. Statistical analysis plan
- Primary. Difference in recall at K = 40 per km² between target and 9t. Non-inferiority against Δ.
- Secondary. Recall at density-scaled K. Calibration. Target feature density.
- Exploratory. Recall by slope tercile, by void fraction, by block feature density.
- Interval. Independent block bootstraps per area, B = 2000. Report the 9t block spread at that K (0.723 to 0.900 at 30) as the floor below which a difference is not interpretable.

## 8. Quality control
- Footprint area equals sum of block areas. Edge blocks listed.
- Candidate counts at K equal K times area to within rounding.
- Same code path for 9t and target (assert by hash of the module).
- Unit test with a synthetic raster and three known features. Recall must equal 1.0 when all three are ranked within K, and 0.667 when one is ranked outside.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | S2 archival check matches with every discrepancy explained, and the new baseline repeats exactly | Scorer certified |
| Success (transfer) | Lower bound of the difference above minus Δ | Proceed to 3.2 or adaptation |
| Failure | Upper bound below minus Δ | Error review. Do not claim transfer |
| Inconclusive | Interval spans minus Δ, or projected width above 2Δ | Report. Change design or add blocks |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_transfer_score.py`, `_project_ci_width_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s4_infer\_transfer_infer.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\transfer\` with the 9t reproduction run
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\transfer_reproduce_9t.md`, `transfer_protocol.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Sweep code not found or differs | Rebuild from the doc and log the difference |
| Target derivatives differ from 9t | Use the same builder. Report void fraction and ground density per block |
| Few blocks | Projected width tool. Permutation interval |
| Density confound | Secondary metric at density-scaled K |
| Original sampler optimism inflates the reference | Report the reference from the isolated model when P1 S6 exists |

## 12. Resources
Scorer and tests 8 hours. Inference wrapper 6 hours. Inference per area is minutes to an hour on the GPU. Disk per area 1 to 5 GB.

## 13. Handoff and open questions
- Which model policy (single fold model, five-fold average, ensemble). Preregister it.
- Whether the isolated pit model exists at the time. If not, say the reference carries original-sampler optimism.

## 14. Documentation updates
`transfer_protocol.md`, `transfer_reproduce_9t.md`, `analysis_log.md`, master plan, README rule 11.

## Review revision 2 (third review, 2026-11-04)
Split the reference in two. Archival. Rebuild the sweep from the per-fold object tables, cutoffs, fold areas and tie rules. Do not use the uint8 mosaic (DN / 254), which changes scores and ties. New baseline. One declared deployment policy on isolated, fold-local-normalised predictions. A global top-K and a per-fold-area floor differ, so match the sweep's rule in the archival check. The old 9t estimate is a historical diagnostic.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
