# Framework 3.3. Low-relief sensitivity (slope stratification, then edits)

**Tier A.** Step 1 costs no new data and can run now.
**Evidence level.** (a). It measures sensitivity to slope and relief context, not Midwest performance.
**Depends on.** 3.0 scorer (step 1 can use a minimal version). P1 for the isolated model (edits).
**Blocks.** The decision to fetch Illinois or Michigan lidar.

## 1. Problem and objective
The model learned pits in steep, forested terrain. In flat farmland the background differs. Both reviews say a synthetic plane lacks the interpolation texture of real 0.5 m lidar, so edits on planes are out of distribution.

**Question 1 (no new data).** Does out-of-fold recall at K = 40 per km² depend on local slope and relief?
**Question 2 (edits).** If a real pit-shaped depression is inserted into real low-relief 9t ground, does the model still score it, and by how much does the score and rank change compared with sham edits?

**Hypotheses.** Q1. Recall in the lowest slope tercile is not lower than the top tercile by more than Δ. Q2. Real-pit edits score above sham edits and above background.

## 2. Scope
In. Slope stratification on 9t. Edits on real low-relief 9t backgrounds with all derivatives recomputed.
Out. Claims about Illinois or Michigan. Those need the area test (listed windows, gated on this).

## 3. Definitions
- **Local slope.** Mean slope in a 25 m window around the feature centroid from the 1 m DEM (check the DEM product used by the derivatives).
- **Relief.** Max minus min elevation in a 50 m window.
- **Terciles.** Computed over all annotated pit-bearing blocks and over features separately. Report both.
- **Edit.** A DEM modification that inserts a depression with the shape statistics of real pits (diameter, depth, rim) at a chosen location.
- **Sham.** A non-pit modification (smooth bump, ramp, flat cut) with matched area and amplitude.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| 9t out-of-fold rasters | `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` | held |
| 9t DEM, slope | `data/9t/derived/` (confirm which 0.5 m or 1 m DEM feeds the stack) | held |
| Annotated pits | `qgis/annotations/annotations_proj.gpkg` layers `pit_inside`, `pit_full` | held |
| Pit morphology bins | `notebooks/wellsight_v2/s7_analysis/_pad_morphology_bins.py` pattern, `docs/iterations/well_age_morphology.md` | held |
| Derivative builders | `s1_build/_build_derivatives.py`, `_build_extra_channels.py` | held |
| Illinois and Michigan windows | lidar list rows for Illinois Cumberland, Marion, Crawford and Michigan | listed, gated |

## 5. Prerequisites and decisions
Step 1 needs nothing. Step 2 needs the isolated model (P1) so edits are not scored by a model that saw those blocks. Margin Δ set before step 1 scoring.

## 6. Procedure
**S1. Slope and relief per feature and per block.**
- Script `notebooks/wellsight_v2/s5_eval/_recall_by_slope_9t.py` (new). Compute slope and relief rasters from the DEM. Attach to each annotated feature and to each block (mean). Tercile cut points saved in the output.
- Join to matching results at K = 40 (use the 3.0 scorer's `transfer_blocks.csv` and a per-feature matched flag).
- Outputs `data/9t/results/terrain/recall_by_slope_9t.csv`, figure `recall_by_slope_9t.png` (recall with bootstrap interval per tercile, blue for observed, grey for overall).

**S2. Confound checks.**
- Compare feature size, depth, and void fraction across terciles. A recall difference may reflect pit size, not slope. Fit a logistic model of matched flag on slope, relief, area, depth and void fraction, with block as cluster. Report slope's partial effect.

**S3. Edit builder.**
- Script `notebooks/wellsight_v2/s7_analysis/_terrain_edit_test_9t.py` (new). Steps.
  1. Choose 200 low-relief locations in 9t (lowest slope tercile, at least the derived buffer from any annotated feature, not in audit blocks).
  2. Sample pit shapes from the annotated floor and rim polygons (diameter, depth from DEM, rim height). Insert by blending a scaled copy of a real pit's local DEM patch (donor patch minus its local plane, added to the target plane). Feather over 3 pixels.
  3. Sham edits at the same locations. Smooth bump with the same footprint, ramp with the same relief, flat cut with the same area.
  4. Recompute every derivative channel from the edited DEM in a window with 128 m margin using the exact 9t builders. Never paste derivative layers.
  5. Run the frozen model on the edited stack. Record the score at the edit centre (max probability within the edit footprint) and the rank among all candidates in the scene.
- Output `data/9t/results/terrain/terrain_edit_paired_scores_9t.csv`, one row per location with background, pit-edit and sham scores and ranks.

**S4. Seam and realism checks.**
- Plot ten edits as hillshade before and after. Compute the interpolation-texture statistic (local variance of the DEM Laplacian) inside and outside the edit and require agreement within 20%. Flag edits that fail.

**S5. Area test (gated).**
- Only if S1 shows lowest-tercile recall is below the top tercile by more than Δ, or the user asks. Fetch the Illinois Cumberland window (80 tiles, 3.61 GB, `IL_8County_2020_A20`) and run 3.0. Measure ground density first.

## 7. Statistical analysis plan
- Q1 primary. Recall (lowest tercile) minus recall (highest tercile), block bootstrap, non-inferiority against Δ.
- Q2 primary. Paired score change pit-edit minus sham at the same location, median and bootstrap interval over locations. Rank change likewise.
- Secondary. Detection rate of edits at K = 40 per km². Dose-response against edit depth and diameter.
- Report paired differences. No half-score threshold.

## 8. Quality control
- Edits do not overlap annotated features or audit blocks.
- Derivatives recomputed from the edited DEM, checked by diffing against the originals outside the edit window (must be zero).
- Seed per location.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Q1 success | Lower bound above minus Δ | No slope penalty found on 9t. Flat counties are not ruled out |
| Q1 failure | Upper bound below minus Δ | Slope penalty. Plan adaptation before any flat county |
| Q2 | Pit edits exceed shams with interval above 0 | The model uses pit shape, not just any dent |
| Inconclusive | Intervals wide | Report. Increase locations |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_recall_by_slope_9t.py`, `s7_analysis\_terrain_edit_test_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\terrain\` outputs
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\low_relief_sensitivity_9t.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Few low-relief features on 9t | Report counts. Use features and blocks both |
| Edits look unnatural | Use donor patches from real pits. Seam checks. Drop failures and report the count |
| Model scored edit blocks in training | Use the isolated model and the audit-excluded blocks |

## 12. Resources
S1 and S2 about 6 hours, no GPU. S3 to S4 about 12 hours plus minutes of GPU. Illinois window 3.6 GB on F: only if gated in.

## 13. Handoff and open questions
- Confirm the DEM used for slope.
- Margin Δ.

## 14. Documentation updates
`low_relief_sensitivity_9t.md`, `analysis_log.md`, master plan, BACKLOG.
