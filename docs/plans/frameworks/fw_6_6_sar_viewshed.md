# Framework 6.6. Search and rescue viewshed tool (self-contained, not a well result)

**Tier A by instruction (user, 2026-11-05, stop deferring).** Written to full depth so it can be modified later. Nothing here has been run.
**Evidence level.** None for wells. This tool adds no evidence at level (a), (b), (c) or (d). Do not cite it in any well report.
**Depends on.** Nothing in the well program. It reuses the 0.5 m DEM and canopy height model (CHM) that already exist on 9t.
**Blocks.** Nothing.
**Separation.** Own resources, own deliverable folder, own tests. A failure here changes nothing in the well work.

## 1. Problem and objective
Search planning needs to know what an observer or searcher can see from a point, which cells are hidden, and how long it takes to walk between places. The terrain models already hold the inputs.

**Question 1 (visibility).** Does a terrain-model line-of-sight calculation agree with ground-truth sight checks at the tolerance a search planner needs?
**Question 2 (opacity).** How much does the vegetation-opacity assumption change the answer, and which setting is closest to field truth by season?
**Question 3 (travel cost).** Does the modelled walking time agree with measured GNSS walk times within a stated tolerance?

**Hypotheses.** H1. Agreement of visible and hidden calls with field checks is at least the acceptance level in section 10 for open ground. H2. Agreement degrades under dense summer canopy unless opacity is calibrated. H3. Modelled time is within the time tolerance of measured time on walked routes.

## 2. Scope
In. Single-point and multi-point viewshed, line-of-sight profile between two points, cumulative viewshed for a set of observers, visible-area and hidden-pocket maps, slope-based travel-time surface, least-cost route, a command-line interface, validation, documentation.
Out. Well detection. Any link to the pit, pad or road models. Drone or aircraft line of sight. Radio propagation. Real-time rescue operations. Person detection probability (what a searcher would notice) beyond a simple visibility fraction.
**Not a well result.** Say so in the tool's help text, the README and every figure footer.

## 3. Definitions
- **Bare-earth model (DEM).** Ground surface. File `data/9t/derived/05/dem_9t_05.tif` (held).
- **Surface model (DSM).** First-return surface including canopy and buildings. `data/9t/derived/05/dsm_9t_05.tif` (held).
- **Canopy height model (CHM).** DSM minus DEM. `data/9t/derived/05/chm_9t_05.tif` (held).
- **Observer.** A point with an eye height above ground (default 1.7 m). **Target height.** The height of the thing seen (default 0 m for ground, 1.7 m for a standing person).
- **Line of sight (LOS).** The straight ray from eye to target. It is blocked if the terrain, or opaque vegetation, rises above the ray.
- **Opacity model.** A rule for how vegetation blocks the ray.
  - O0 terrain only (DEM).
  - O1 surface blocks (DSM, fully opaque canopy).
  - O2 partial. Vegetation transmits a share of rays by path length through canopy using Beer-Lambert, T = exp(−k L), with k an extinction coefficient per metre set by season (leaf-on or leaf-off) and calibrated in S4. L is the ray length through cells where CHM exceeds 2 m.
- **Visible fraction.** Share of cells in the analysis radius visible from the observer. **Hidden pocket.** A connected set of hidden cells larger than a set area inside the radius.
- **Travel-time cost.** Seconds to cross a cell, from a slope function. Starting form is Tobler's hiking function with a land-cover multiplier. Parameters are calibrated in S5.
- **Agreement.** For paired sight checks, the share of calls (visible or hidden) that match. Report sensitivity (visible truth called visible) and specificity separately.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| 9t DEM, DSM, CHM at 0.5 m | `data/9t/derived/05/dem_9t_05.tif`, `dsm_9t_05.tif`, `chm_9t_05.tif` | held |
| 9t derivative builder | `notebooks/wellsight_v2/s1_build/_build_derivatives.py` | held |
| Landcover for travel cost | `data/9t/derived/landcover/` | held, confirm product and legend |
| Roads for travel cost | `data/9t/results/road/` model products | held, optional |
| Path helper | `notebooks/wellsight_v2/_common.py` `path_for` | held |
| Field sight checks and GNSS tracks | `data/<area>/source/sar_field/` | assumed, see section 5 |
| Leaf-on and leaf-off lidar for the same site | tiles of two flight dates | assumed, see section 5 |

## 5. Assumed data
Every item is assumed to exist. Each carries VERIFY. Nothing below is confirmed.

| Item | Assumption | VERIFY |
|---|---|---|
| DEM, DSM, CHM share one grid | The three 9t rasters have the same transform, CRS (EPSG:6346) and size. | Read all three. Assert identical transform and shape. Check that CHM equals DSM minus DEM where all are valid. |
| DSM is a true first-return surface | `dsm_9t_05.tif` was built from first returns or the highest point per cell, not from a smoothed or ground-filled product. | Read the builder. Spot-check ten cells under canopy against raw points. |
| Void handling | Cells without ground return are interpolated in the DEM. | Report the void fraction per block (9t is 45.2% at 0.5 m per `BACKLOG.md`). Mask interpolated cells in all outputs and log the count. |
| Leaf state of the 9t lidar | The acquisition date and leaf state are known. | Read the LAS header and tile metadata for the flight date. If unknown, treat season as unverified. |
| Field sight checks | A planner or partner can supply at least 100 paired sight checks (observer point, target point, visible yes or no, canopy state, date, GNSS error) at 20 or more observer stations. | Check the form with a pilot of 10 checks. Count independent stations, not pairs. |
| GNSS walk test | At least 10 walked routes of 0.5 to 3 km with 1 Hz tracks from a GNSS unit with stated error. | Check track sample rate and horizontal error. Record carrier and device. |
| Second lidar date | Optional. A leaf-off and a leaf-on lidar over the same ground to bound the canopy effect. | Check both flight dates. Do not assume. |
| Licence | The lidar is public. Partner data are shared with consent. | Record the data source and any use limits in `literature/CITATIONS.md`. |

If a VERIFY fails, stop and report.

## 6. Prerequisites and decisions
User decisions. A named user and the decision the tool supports (for example volunteer search planning). Observer height defaults. Acceptance levels (section 10). Where the field validation is done. Margin sources are stated in section 10.
Resource separation. Time for this tool is logged apart from the well work.

## 7. Procedure
**S0. Scope and contract (about 4 hours).** Write `docs/iterations/sar_viewshed_scope.md` listing inputs, opacity models, default heights, resolution, analysis radius and outputs. Preregister the acceptance levels before any validation data are scored.

**S1. Core line-of-sight engine.**
- Script `tools/sar_viewshed.py` (proposed, plain Python with numpy and rasterio, no GIS server). Subcommands `viewshed`, `profile`, `cumulative`, `cost`, `route`.
- Algorithm. For each target cell, sample the terrain along the eye-to-cell line at half-cell steps with bilinear interpolation. Compare the ray height with surface height. Radial sweep with running maximum slope for speed, checked against the brute-force profile on random pairs.
- Earth curvature and refraction correction is applied (standard coefficient 0.13) and logged. At radii under 2 km it is small and the flag stays on.
- Parameters. `--dem`, `--surface`, `--chm`, `--observer x,y`, `--eye-height`, `--target-height`, `--radius`, `--opacity O0|O1|O2`, `--k`, `--season`.
- Output rasters `sar_viewshed_<observer>_<opacity>.tif` (1 visible, 0 hidden, nodata for masked), plus `sar_viewshed_<observer>_frac.tif` for O2 (probability of visibility).

**S2. Unit tests on synthetic terrain.** Plane, single hill, pit, wall, a canopy block of known height. Expected visibility computed by hand. Include seam, edge and nodata cases. Require exact agreement on the synthetic cases.

**S3. Scale and speed.** Run on a full 9t tile with a 1 km radius. Record wall time and memory. Set a tiling plan for radii above 2 km. Report the cost per observer.

**S4. Field validation of visibility.**
- Script `tools/sar_viewshed_validate.py` (proposed). Read the paired checks. Predict each under O0, O1 and O2. Compute agreement, sensitivity and specificity by canopy state and distance band.
- Calibrate k on half of the stations (by station, not pair) and score on the other half. Report with the holdout only.
- Compare with a second lidar date if S5 data exist.

**S5. GNSS walk test.** Fit the Tobler parameters and land-cover multipliers on half the routes. Score modelled time against measured time on the rest.

**S6. Documentation and release.** README with a clear statement of limits, example commands, a worked example on 9t, and a table of assumptions.

## 8. Statistical analysis plan
- Unit of independence is the observer station for visibility and the route for time. Pairs and track points are not independent.
- **Primary (Q1).** Agreement per opacity model on held-out stations, with a station-level bootstrap (B = 2000). With fewer than 15 stations also report a permutation interval and say the bootstrap is unreliable.
- **Primary (Q3).** Median relative time error per route and its interval over routes.
- Sensitivity and specificity are reported separately. A search planner cares most about falsely visible calls, which hide a gap in coverage.
- Secondary (exploratory). Agreement by distance band, slope, canopy height class and season.
- Calibration of k is fit on the calibration stations only.
- One primary estimand per question. Everything else is exploratory.

## 9. Quality control
- All three rasters share one grid. Assert it.
- Interpolated (void) cells are masked and counted in every output.
- Brute-force and radial sweeps agree on 1,000 random pairs (zero disagreements outside half-cell tolerance).
- Observer cell and target cell inside the raster extent. Out of range is an error, not a silent clip.
- Field stations are split by station before any fitting. No station appears in both halves.
- GNSS horizontal error is carried into the validation as a tolerance band, so an error smaller than the GNSS error is not counted as a model miss.
- Deterministic output on the same inputs. Provenance file for each run (inputs with SHA-256, parameters, commit, interpreter).
- Sanity render over hillshade for two known viewpoints.
- Every number in the doc comes from a saved file.

## 10. Gates (acceptance test, protocol form)
Margins come from the planning decision (a falsely visible call leaves a gap, so specificity matters more). They are set by the named user before scoring.
| Outcome | Rule | Action |
|---|---|---|
| Q1 success | Lower bound of agreement for the chosen opacity model above the acceptance level A | Release for that canopy state |
| Q1 failure | Upper bound below A | Do not release as a visibility predictor for that state. Release as terrain-only with the limit stated |
| Q3 success | Upper bound of median relative time error below the time tolerance | Release the cost surface |
| Q3 failure | Lower bound above the time tolerance | Recalibrate or drop the cost surface |
| Inconclusive | Intervals straddle A or the tolerance, or fewer than the minimum stations | Report. Collect more stations |
The opacity assumption is the key uncertainty. If no opacity model passes in leaf-on, the tool is released for leaf-off and open ground only.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\tools\sar_viewshed.py`, `tools\sar_viewshed_validate.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\sar\` (viewshed rasters, validation tables, figures, run folders)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\sar_viewshed_scope.md`, `sar_viewshed_validation.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\tests\test_sar_viewshed.py` (proposed)
- Colourblind-safe figures. Blue `#1F5FA8` visible, orange `#D97706` hidden, grey `#8E959B` masked. Validate all pairs.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Opacity assumption wrong by season | Calibrate k per season. Release only the states that pass |
| DSM misses thin branches and stems | Report the bias. Use O2 with k fit to field truth |
| Interpolated DEM cells give false terrain | Mask and count. Report masked fraction |
| GNSS error under canopy larger than model error | Carry error as a tolerance band. Prefer stations with fixes |
| Too few stations | Report inconclusive. Do not extrapolate |
| Scope creep into detection or operations | Keep a separate folder, resource log and gate. No link to the well models |
| Users read visibility as detection probability | Say so in the help text. Output a visibility fraction only |

## 13. Resources
S0 4 hours. S1 to S3 about 20 hours with tests. S4 to S5 depend on field days (partner time, not ours). Compute is CPU, minutes per observer at 1 km radius (to be measured in S3). Disk under 5 GB.

## 14. Handoff and open questions
- Named user and decision. Acceptance level A and time tolerance. Where field data come from. Leaf state of the lidar.
- Stop and report if any VERIFY fails.

## 15. Documentation updates
`sar_viewshed_scope.md`, `sar_viewshed_validation.md`, `analysis_log.md`, `BACKLOG.md`, master plan, `literature/CITATIONS.md` (viewshed algorithm, Tobler 1993, canopy transmission), a one-line pointer from the README saying this is not a well tool.
