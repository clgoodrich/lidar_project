# Framework 4.3. Vegetation stress (label gate, then two separate questions)

**Tier A (rewritten 2026-11-05 at the user's request to stop deferring).** Nothing here has been run.
**Evidence level.** (a) for the disturbance question. The leak question can only be asked if independent leak labels exist, and even then it supports screening and not well identity. Vegetation signals are not evidence level (d).
**Depends on.** 9t pad polygons, the lidar CHM, the 3.0 scorer for the ranking test. Label source from DEP (request R1 family).
**Blocks.** Any claim that a vegetation index flags leaks.
**Pre-specified outcomes.** The leak question closes if fewer than the required labelled sites exist. The disturbance question still runs. Both are valid endings.

## 1. Problem and objective
Gas migration can kill or stress vegetation near a well. Pads are also disturbed ground, with compacted soil, gravel and regrowth of different age. A vegetation index difference between a pad and forest mostly measures disturbance. The lidar CHM already measures regrowth height and canopy gaps.

**Question A (disturbance and morphology).** Does a vegetation index separate pads from matched non-well disturbance beyond what the CHM and land cover give?
**Question B (leak).** Among pads with independently labelled leak or non-leak status, does a vegetation stress index separate them after adjusting for pad age, cover and CHM?

Without independent leak labels, Question B cannot be asked. The result would be a difference in disturbed ground. This is stated in every output.

**Hypotheses.** A. Index features add ranking gain at K = 40 per km² beyond the lidar-only model. B. Stress index differs between leak and non-leak pads by more than a useful AUC gain.

## 2. Scope
In. Multi-date optical indices on 9t pads and matched controls. Labelled leak study on whichever Pennsylvania sites have labels.
Out. Any claim that an index shows leakage without labels. Methane retrieval (see 4.4). Other counties until the 9t gate passes.

## 3. Definitions
- **Vegetation index.** NDVI (near-infrared minus red over their sum), NDRE (red-edge version), NDMI (near-infrared against shortwave infrared, a moisture index), and EVI.
- **Stress anomaly.** Index at the pad minus the index in a matched ring, relative to the same site's own history, season by season. Not a raw index.
- **Matched control.** Non-well disturbance (logging landing, utility corridor, old road bed) matched to the pad on area band, age band, CHM class, aspect and soil unit. Drawn before indices are read.
- **Leak label.** A leak or non-leak status from a source independent of imagery and of the lidar model. Allowed sources are in section 7 stage V0.
- **Site-season.** One site in one season. Repeated site-seasons are dependent. The unit of inference is the pad.
- **Useful contrast δ_veg.** The index difference or AUC gain that would change a screening decision. User decision, fixed before V2.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Pad polygons and non-pad disturbance | `qgis/annotations/annotations_proj.gpkg` (layer names to confirm), `data/9t/results/pad/pad_cover_split_9t.gpkg` | held |
| CHM and DEM | `data/9t/derived/multires_chm_window/chm_chmwindow_9t_1m.tif`, `dem_chmwindow_9t_1m.tif` | held |
| NLCD 2006 and 2019 | `data/9t/derived/landcover/nlcd_2019_landcover_9t.tif` | held |
| Sentinel-2 stack, three months | `data/9t/derived/optical_s2/s2_jun_green_red_nir_swir_scl_9t_5m.tif` and the Sep and Oct files | held, bands lack red edge |
| Weather, leaf state | `data/9t/derived/weather/weather_prism_daily_9t.csv`, `leaf_state_ndvi_curve_9t.csv` | held |
| DEP well records | DEP export and `venango_wells_all` (path through `path_for`, confirm) | held |
| Multi-date imagery (section 5) | `data/9t/derived/vegstress/` | proposed, assumed to exist |
| Leak labels (section 5) | `data/9t/derived/vegstress/leak_labels_9t.csv` | proposed, assumed to exist |

## 5. Assumed data
Each item is assumed to exist. Tag VERIFY with the check.

| Assumed item | Detail assumed | VERIFY by |
|---|---|---|
| Sentinel-2 L2A surface reflectance | 10 m (B2 to B4, B8), 20 m (B5 to B7, B8A, B11, B12). 5-day revisit. 2017 to 2026. Scene classification layer for cloud. Open licence (Copernicus) | Count cloud-free scenes per month over 9t. Confirm that the held 5 m stack is a resample and lacks B5 to B7 |
| Landsat 8 and 9 surface reflectance | 30 m, 8-day combined revisit, 2013 to 2026. Public domain | Count scenes. Check pixel fill against pad area |
| NAIP four-band orthoimagery | About 0.6 m, red, green, blue, near-infrared, Pennsylvania cycle of about two years, leaf-on. Public | Confirm Pennsylvania years and bands. Earlier visible chips were blank in 10 of 13 samples (D10), so check usability |
| Commercial 3 m daily imagery (optional) | Four band, daily. Licence restricts redistribution | Licence and cost. Not required for the gate |
| DEP complaint records | Complaint tracking with date, location text, complaint type such as gas migration or well venting, resolution. Public through the DEP file system, with some fields redacted | Ask under R1. Confirm fields, location precision and year range |
| DEP inspection records | Inspection with violation codes for leaking or venting at orphan, abandoned and plugged wells | Confirm violation code list and coordinate quality |
| Crew screening (from 7.5) | Handheld methane reading at a probability sample of pads, with identity status | Depends on the campaign. Not assumed for the first pass |
| Pad age | From DEP spud date where not the 1800 sentinel, otherwise from lidar era history (2006 to 2008 versus recent) | Check sentinel share. Unknown age is its own stratum |
| Soil map | SSURGO soil units for matching | Download and join check |

## 6. Prerequisites and decisions
- User decision. Which question first. The framework runs A regardless and runs B only if V0 passes.
- User decision. δ_veg and δ_gain.
- Control and ring definitions fixed before any index is read.
- Season set fixed from `leaf_state_ndvi_curve_9t.csv`. Leaf-on peak, leaf-off, and one shoulder.

## 7. Procedure
**V0. Label gate (before any imagery work).**
- Script `notebooks/wellsight_v2/s5_eval/_vegstress_label_audit_9t.py` (proposed).
- Collect DEP complaint and inspection records that fall within 100 m of a pad polygon and carry a leak or gas migration code. Also collect non-leak pads with a clean inspection record in the same years. Record the coordinate source and precision for each.
- A label is accepted only if it is independent of imagery, independent of the lidar model, and dated. A complaint is a report by a person. It is not a measurement. Mark it as a weak label in the output. Handheld or flux measurement is a strong label.
- Required count. At least 40 leak pads and 40 non-leak pads, so that an AUC of 0.70 has a lower bound above 0.5 under Hanley and McNeil variance (VERIFY the arithmetic at preregistration). Pads are clustered by lease, so count independent leases too.
- Output `data/9t/results/vegstress/vegstress_label_audit_9t.csv` and `vegstress_label_counts_9t.json`.
- Rule. If counts fail, Question B closes by pre-specification. Question A continues.

**V1. Observability.** Script `s5_eval/_vegstress_observability_9t.py` (proposed). Pad area over pixel area for 10, 20 and 30 m. Cloud-free scene counts per season. Canopy overhang from the CHM at pad edges (an index from above a clearing edge reads canopy). Output `vegstress_observability_by_pad_9t.csv`.

**V2. Extraction.** Script `s5_eval/_vegstress_extract_sites_9t.py` (proposed). For each pad, control and ring, compute the area-weighted index per scene using only pad-interior pixels with CHM below 2 m. Output `data/9t/results/vegstress/vegstress_by_site_9t.csv`, one row per site and scene.

**V3. Question A ranking.**
- Script `s5_eval/_vegstress_added_value_9t.py` (proposed). Out-of-fold ranking of pad versus matched control from lidar features alone (CHM, morphology, NLCD), then lidar plus index features. Same folds and blocks. Recall at K and AUC, paired by block.

**V4. Question B (only if V0 passes).**
- Script `s5_eval/_vegstress_leak_test_9t.py` (proposed). Site-level model of stress anomaly on label with pad age, CHM and cover as covariates, scene as a random effect, lease as cluster. Nested spatial cross-validation for the AUC. Weak and strong labels reported separately.

## 8. Statistical analysis plan
- Primary A. Recall at K = 40 per km², lidar plus index minus lidar only, block bootstrap B = 2000, paired.
- Primary B. AUC difference over the covariate-only model, cluster bootstrap at lease level. Clopper-Pearson for any proportion of labelled sites. Newcombe for differences of proportions.
- Repeated seasons are averaged to the site before inference or modelled with a site random effect.
- Covariate adjustment does not establish leakage. A positive B result shows an association with labels, with measurement type stated.
- Secondary and exploratory. Index choice, season, ring width. Each is a sensitivity, not a new primary.
- A weighted or small sample uses inference matched to its design (fw_00 revision 2).

## 9. Quality control and leakage checks
1. Row counts asserted at joins (pad to scene, pad to label). Expected and observed stated.
2. Labels carry source, date and coordinate precision. No label is built from imagery.
3. Matching variables exclude indices.
4. Pads at the same lease stay in one fold. No audit block in any fitting list.
5. Cloud and scene-classification mask before extraction. Shadow from the CHM sun angle.
6. Index date within the season window. Phenology differences between years tracked with the leaf-state curve.
7. A second run gives identical output. Sanity render of two pads and the pixel grid.
8. Every number in a document comes from a saved file.

## 10. Gates
| Stage | Success | Failure | Inconclusive | Action |
|---|---|---|---|---|
| V0 labels | At least 40 per class and at least 15 independent leases per class | Fewer than 20 per class | Between | Failure closes Question B. Record it as a pre-specified outcome |
| V1 observability | Median pad interior pixels at least 4 and at least 3 usable scenes per season | Median under 1 pixel | Between | Failure closes that sensor |
| V3 Question A | Gain lower bound above δ_gain | Upper bound below δ_gain | Otherwise | Failure means the CHM and land cover hold the signal |
| V4 Question B | AUC gain lower bound above δ_gain | Upper bound below δ_gain | Otherwise | Success is a screening association, not leak detection |

Margin source. δ_gain comes from the value of one avoided field visit, not from variance.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\vegstress_protocol_9t.md` and `vegstress_results_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_vegstress_label_audit_9t.py`, `_vegstress_observability_9t.py`, `_vegstress_extract_sites_9t.py`, `_vegstress_added_value_9t.py`, `_vegstress_leak_test_9t.py` (all proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\vegstress\` with the CSV and JSON files named above plus `vegstress_added_value_9t.png`
- Imagery in `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\derived\vegstress\` with a `.gitignore` rule in the same change

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Too few labels | V0 closes B. Report that only disturbance was measured |
| Complaint is a person's report | Mark weak. Report strong labels alone as sensitivity |
| Disturbance and age confound | Age strata, matched controls, CHM adjustment |
| Pad smaller than a pixel | V1. Use NAIP near-infrared at 0.6 m for a finer check |
| Canopy shadow and edge overhang | CHM mask |
| Phenology shift between years | Leaf-state curve, season windows |
| Labels cluster at a few leases | Lease-level bootstrap |

## 13. Resources
V0 about 15 hours of records work and an outreach wait. V1 to V3 about 30 hours. V4 about 15 hours. No GPU. Imagery tens of GB on F:.

## 14. Handoff and open questions
- Confirm the DEP complaint and inspection fields and years (R1 family).
- Confirm the held Sentinel-2 stack lacks red edge, and fetch bands if it does.
- Decide δ_veg and δ_gain.
- Decide whether a crew screening arm is added.

## 15. Documentation updates
`docs/iterations/vegstress_protocol_9t.md`, `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, `literature/CITATIONS.md`, `docs/plans/EXPANSION_MASTER_PLAN.md`. Add the label request to `docs/iterations/outreach_requests_drafts.md`.

## Rewrite note (2026-11-05)
Replaces the Tier C scoped text. The label requirement follows `docs/plans/protocol_gates_and_metrics.md` section 9.
