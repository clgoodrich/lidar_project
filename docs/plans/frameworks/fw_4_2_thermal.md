# Framework 4.2. Thermal (mechanism and contrast gate, then a test against the lidar baseline)

**Tier A (rewritten 2026-11-05 at the user's request to stop deferring).** Stage T0 needs only held data plus the assumed thermal products. Nothing here has been run.
**Evidence level.** (a) at best. A thermal difference between a pad and a clearing is a surface difference. It is not evidence level (b), (c) or (d), and it does not identify a well or a leak.
**Depends on.** 9t pad polygons and the lidar canopy height model (CHM). P1 is not needed. The 3.0 scorer is needed only for stage T4.
**Blocks.** Any thermal or drone-thermal acquisition.
**Pre-specified outcomes.** The framework may end at stage T0 with a CLOSE for satellites. That is a valid result.

## 1. Problem and objective
Pads are clearings. A clearing in forest has a different land surface temperature (LST) from the canopy around it. The lidar CHM already measures the clearing. A leaking well adds no thermal signal at ordinary flow because methane leaves at ground temperature. So the only believable thermal contrast between a pad and the forest is land cover, which lidar already holds.

**Question 0 (mechanism).** Is there any physical route by which thermal data carry pad information that the CHM and land cover do not?
**Question 1 (observable contrast).** At the pixel size of each sensor, how large is the expected pad-minus-matched-clearing LST difference, compared with retrieval noise and with the spread among clearings?
**Question 2 (added value).** If Question 1 passes, does adding LST features to a lidar-only pad-versus-clearing ranking raise recall at K = 40 per km² on held-out blocks?

**Hypotheses.** H0. Pad LST minus matched-clearing LST is inside the useful band around zero at the sensor pixel size. H1. It is outside the band and LST features add ranking gain beyond lidar.

## 2. Scope
In. Satellite LST (Landsat TIRS, ECOSTRESS, ASTER if archived) over 9t. Pad versus matched non-well clearing versus forest. A drone thermal design as a conditional appendix.
Out. Leak detection. Any claim about well identity. Any claim that a satellite null excludes a drone signal. Other counties until 9t passes.

## 3. Definitions
- **LST.** Land surface temperature in kelvin from a thermal-infrared retrieval.
- **Fill fraction f.** Pad area inside one sensor pixel divided by pixel area. Computed per pad from the pad polygon and the sensor grid, for the real pixel footprint and not the resampled one.
- **Diluted contrast.** f times the true surface temperature difference between the pad and its surroundings. A pixel that holds 5% pad shows at most 5% of the pad signal.
- **Matched clearing.** A non-well clearing from the control set (logging landing, utility corridor, field edge) matched to the pad on CHM class, area band, slope, aspect and age band. Source layer is the annotated non-pad disturbance and the land-cover layer.
- **Lidar null.** A model of LST using only CHM, NLCD class, slope, aspect and modelled solar loading. Thermal is added value only if it beats this.
- **Modelled solar loading.** Clear-sky irradiance at the overpass time from the 1 m DEM slope and aspect. It is a lidar-derived covariate.
- **Useful contrast δ_T.** The pixel-scale LST difference that would change a decision. Proposed default 1.0 K. User decision, fixed before T1.
- **Unit and K.** Unit is the pad (clustered by block). K is 40 per km² for the ranking test.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Pad polygons and non-pad disturbance | `qgis/annotations/annotations_proj.gpkg` (layer names to confirm) and `data/9t/results/pad/pad_cover_split_9t.gpkg` | held |
| CHM and DEM at 0.5, 1 and 2 m | `data/9t/derived/multires_chm_window/chm_chmwindow_9t_1m.tif` and `dem_chmwindow_9t_1m.tif` | held |
| NLCD land cover | `data/9t/derived/landcover/nlcd_2019_landcover_9t.tif` | held |
| Weather and leaf state | `data/9t/derived/weather/weather_prism_daily_9t.csv`, `leaf_state_ndvi_curve_9t.csv` | held |
| Block and fold lists | from the 3.0 scorer `transfer_blocks.csv` | held after 3.0 |
| LST scenes (see section 5) | `data/9t/derived/thermal/` | proposed, assumed to exist |
| Gate script and outputs | `data/9t/results/thermal/` | proposed |

## 5. Assumed data
The user instructed that the datasets and access exist. Each item is an assumption, tagged VERIFY with the check.

| Assumed item | Detail assumed | VERIFY by |
|---|---|---|
| Landsat 8 and 9 TIRS surface temperature (Collection 2 Level 2) | Native 100 m, delivered 30 m resampled. 16-day revisit per satellite, about 8 days combined. Overpass about 10:15 local solar time. 2013 to 2026. Fields ST_B10, ST_QA, QA_PIXEL. Public domain (USGS) | Read the Collection 2 Level 2 product guide. Confirm 100 m native and the ST uncertainty field |
| ECOSTRESS ECO2LSTE.002 (LP DAAC) | About 70 m native, resampled to 70 m grid. Irregular revisit from the ISS, varying time of day. 2018 to 2026. Fields LST, LST_err, cloud, QC. NASA open data | Read the LP DAAC user guide. Count scenes over 9t by season and hour. Confirm the instrument status in 2026 |
| ASTER L2 surface kinetic temperature (archive) | 90 m native, on-demand. Optional | Check archive coverage and end of mission |
| Drone thermal imager (conditional appendix only) | Radiometric, 640 by 512, 0.05 to 0.3 m ground sample, flown pre-dawn and midday | Vendor accuracy specification. Permit and site access |
| Pixel footprints | Native footprint polygons, not the resampled grid | Product metadata |
| Retrieval noise | Order 1 to 2 K per pixel for LST products (assumed) | Product validation papers and the uncertainty bands in the scenes |
| Emissivity | Retrieval uses a land-cover emissivity that differs between clearings and forest | Product algorithm document |
| Licence | USGS and NASA data are open. Drone data are ours | Confirm terms of use |
| Optional higher-resolution LST (commercial) | Not assumed. Listed only so a decision to buy is explicit | Cost quote |

## 6. Prerequisites and decisions
- User decision. δ_T, fixed before T1 and written in the preregistration.
- User decision. Whether a drone appendix is allowed if the satellite gate closes.
- Control set. A matched-clearing list drawn before any LST is read.
- Date window. Leaf-off clear nights and leaf-on clear mornings, chosen from `leaf_state_ndvi_curve_9t.csv` before extraction.

## 7. Procedure
**T0. Mechanism note (no data).**
- Write `docs/iterations/thermal_mechanism_9t.md`. List every physical route for a pad signal. Land cover and canopy removal, bare gravel thermal inertia, soil moisture, slope and aspect loading, and leaking gas. State for each whether the lidar CHM or NLCD already carries it.
- Rule. Any route that lidar already carries is a null route. Only routes with an independent thermal term (thermal inertia of gravel, moisture) are tested. Gas flow at ordinary rates gives no temperature term and is listed as not testable here.

**T1. Observable-contrast gate.**
- Script `notebooks/wellsight_v2/s5_eval/_thermal_gate_contrast_9t.py` (proposed).
- Step 1. Fill fraction f per pad for each sensor from the native footprint. Report the distribution and the share of pads with f at or above 0.25.
- Step 2. Usable scenes per sensor. Cloud free over the block, QC pass, in the chosen window. Report counts by season and hour.
- Step 3. Registration error. Compare scene geolocation with lidar-derived road and clearing edges on 10 scenes. Report RMSE in metres against pixel size.
- Step 4. Expected diluted contrast. For each pad take the median surface temperature difference between pad and matched clearing from a drone-free proxy. Proxy is the 30 m Landsat difference between NLCD classes at matched solar loading. Multiply by f.
- Step 5. Noise and variability. Scene retrieval noise from the uncertainty band. Spread of LST among matched clearings after the lidar null. Contrast-to-spread ratio per scene.
- Outputs `data/9t/results/thermal/thermal_gate_by_pad_9t.csv` and `thermal_gate_summary_9t.json`, figure `thermal_gate_fill_vs_contrast_9t.png`.

**T2. Samples and extraction (only if T1 passes).**
- Script `s5_eval/_thermal_extract_samples_9t.py` (proposed). For each pad, matched clearing and forest control, extract the pixel-weighted LST by area overlap, the scene time, the cloud flag and the covariates (CHM class, NLCD, slope, aspect, solar loading, antecedent rain from PRISM, leaf state).
- Output `data/9t/results/thermal/thermal_samples_by_scene_9t.csv`. One row per site and scene.

**T3. Covariate-adjusted contrast.**
- Script `s5_eval/_thermal_contrast_model_9t.py` (proposed). Mixed model of LST on site class (pad, matched clearing), the lidar null covariates and scene as a random effect, with block as cluster. Primary estimate is pad minus matched clearing at the same scene.

**T4. Added value over lidar.**
- Script `s5_eval/_thermal_added_value_9t.py` (proposed). Out-of-fold pad-versus-clearing ranking from lidar features alone, then lidar plus LST features. Same folds, same blocks. Recall at K = 40 per km² and AUC, paired by block.

**T5. Drone appendix (conditional).** Written as a design only. Matched pairs of pads and clearings, pre-dawn and midday flights, 40 or more pairs, blinded analyst. Not scheduled by this framework.

## 8. Statistical analysis plan
- Primary (T3). Pad minus matched-clearing LST at pixel scale. Scene-level difference averaged to site, then block bootstrap (B = 2000) over blocks. Site-scenes are not independent.
- Primary (T4). Recall at K difference, lidar plus LST minus lidar only, block bootstrap, paired. Success threshold is the useful gain δ_gain.
- Secondary. Dose response of contrast against f, season split, leaf-off versus leaf-on. Labelled exploratory.
- Calibration is not reported for this arm. It is a contrast test.
- Few blocks or pads in a stratum. Report permutation intervals and the bootstrap caveat from fw_00 section 4.
- The satellite result is conditional on pixel size. A null excludes only the stated pixel-scale contrast.

## 9. Quality control and leakage checks
1. Row counts at every join (pad to footprint, footprint to scene). State expected and observed.
2. CRS of footprints, scenes and polygons asserted. Scene transforms checked against the lidar DEM.
3. Matched clearings drawn before LST is read. Matching variables exclude LST.
4. No control overlaps a pad buffer or an audit block. No pad appears twice.
5. Cloud and QC masks applied before extraction. Scenes with a partial pixel overlap are flagged.
6. The control set is not tuned to make the contrast small or large. Second run with the same config gives identical output.
7. Sanity render of two pads over hillshade with the native pixel grid drawn.
8. Every number in a document comes from a saved file.

## 10. Gates
Margin source. δ_T is the pixel-scale difference that would change the screening decision. It is never set from noise or fold spread. Noise sets the number of scenes.

| Stage | Success | Failure | Inconclusive | Action |
|---|---|---|---|---|
| T0 mechanism | At least one route has an independent thermal term | No route beyond land cover | Routes unclear | Failure closes satellite arm and records a CLOSE |
| T1 observable contrast | Median diluted contrast lower bound above δ_T and contrast-to-spread at least 1, with at least 15 usable scenes | Median diluted contrast upper bound below δ_T | Interval spans δ_T | Failure is a pre-specified CLOSE for that sensor. Drone appendix may be requested |
| T3 contrast | Lower bound of pad minus clearing above δ_T | Upper bound below δ_T | Otherwise | Report. Failure means no detectable contrast at that pixel size |
| T4 added value | Gain lower bound above δ_gain | Upper bound below δ_gain | Otherwise | Failure means lidar already holds the signal |

A pass at T3 or T4 is still evidence level (a). It never reads as a leak or a well.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\thermal_mechanism_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\thermal_observability_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_thermal_gate_contrast_9t.py`, `_thermal_extract_samples_9t.py`, `_thermal_contrast_model_9t.py`, `_thermal_added_value_9t.py` (all proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\thermal\` with `thermal_gate_by_pad_9t.csv`, `thermal_gate_summary_9t.json`, `thermal_gate_fill_vs_contrast_9t.png`, `thermal_samples_by_scene_9t.csv`, `thermal_contrast_estimates_9t.csv`, `thermal_added_value_9t.csv`
- Raw scenes (heavy) in `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\derived\thermal\` with a `.gitignore` rule in the same change

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Pad fills under a quarter of a pixel | The gate reports it and closes the sensor |
| Contrast is land cover only | Matched clearings and the lidar null. Report as a null route |
| Time of day differs across ECOSTRESS scenes | Time in the model and in the matching window |
| Emissivity differs between clearing and forest | Use matched clearings. Report emissivity source |
| Registration error near pixel size | Step 3 of T1. Drop scenes above half a pixel |
| Overpass bias to clear weather | State it. Do not extrapolate to cloudy days |
| Drone signal exists where satellite does not | A satellite null excludes only the stated pixel-scale contrast |

## 13. Resources
T0 about 4 hours. T1 about 12 hours with 10 scenes of registration work. T2 to T4 about 25 hours. No GPU. Scene storage tens of GB on F:. Drone appendix is not budgeted.

## 14. Handoff and open questions
- Confirm scene access and the product versions in section 5.
- Decide δ_T and δ_gain.
- Locate where earlier thermal work lives. None was found in `docs/` (2026-11-04).
- Confirm the layer names in `annotations_proj.gpkg` for pads and non-pad disturbance.

## 15. Documentation updates
`docs/iterations/thermal_mechanism_9t.md`, `thermal_observability_9t.md`, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, `literature/CITATIONS.md` (product guides and validation papers once read), `docs/plans/EXPANSION_MASTER_PLAN.md`.

## Rewrite note (2026-11-05)
Replaces the Tier C scoped text. The mechanism and contrast gate comes from `docs/plans/adversarial_review_claude.md` B13 and `docs/plans/protocol_gates_and_metrics.md` section 9. Source for the pixel sizes is those documents and is not yet read.
