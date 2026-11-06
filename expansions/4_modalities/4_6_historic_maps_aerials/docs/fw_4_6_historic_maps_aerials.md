# Framework 4.6. Historic maps and aerials

**Tier A.** The only plausible independent evidence for pre-1880 wells.
**Evidence level.** (b) historical.
**Depends on.** Nothing for the probe. 5.6 and 5.2 later use its output.
**Blocks.** 5.2 (era). Informs 4.1 and 7.5 sampling.

## 1. Problem and objective
Lidar sees terrain. Magnetics miss wooden casing. Old maps and photos may show derricks, wells or lease roads that no record lists. Whether any source is usable here is unknown. One 1922 topographic sheet (Oil City, 1:62,500) showed no well symbols in the part that covers 9t, and the sheet's north neatline cuts through 9t. That is one sheet and one look.

**Objective.** Decide, per source and date, whether it is usable here, unusable here or inconclusive. For usable sources, digitise well marks with stated positional accuracy.

**Hypotheses.** H1. At least one source with date before 1950 shows interpretable well, derrick or tank symbols over 9t with georeferencing error under the limit (set in the preregistration, nominal 30 m). H0. None does.

## 2. Scope
In. Source search, probe, georeferencing check, digitising, match to lidar and records.
Out. Era classification (5.2). Training on historical labels.

## 3. Definitions
- **Usable.** Symbols can be identified by two independent digitisers (agreement above a preregistered level), localised within the error limit, and cover a meaningful share of 9t.
- **Positional accuracy.** RMSE of independent check points (road intersections, stream confluences, buildings that still exist in lidar) not used for georeferencing.
- **Historical positive.** A mark that two digitisers agree is a well, derrick or associated structure.
- **Null.** DEP record positions shifted by 200 to 500 m, kept inside the oil field footprint, 300 shifts, used to test whether marks match records beyond chance.

## 4. Inputs
| Source | State | Notes |
|---|---|---|
| USGS historic topo, 31 sheets over 9t (1922 to 1967) | listed via TNM, one downloaded (`data/_source/historic_topo_probe/oil_city_1922_62500.tif`, 8.7 MB, GeoTIFF NAD27 polyconic) | Probed once, no symbols. Neatline cuts 9t |
| Three more topo sheets (earliest, one 1:24,000, one other date) | D5 about 30 MB | to fetch |
| 1870s and 1880s oil-region maps (Second Geological Survey of Pennsylvania) and 1860s atlases | D6 search | existence and coverage **unverified** |
| Aerials 1937 to 1942 (PennPilot at Penn State, USGS EarthExplorer single frames) | D7 index | an index entry does not guarantee a scan |
| State oil-field maps | search | **unverified** |
| DEP export | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held |
| Lidar and annotations | held | for check points and comparison |

## 5. Prerequisites and decisions
Preregister the RMSE limit, digitiser agreement level, and the shifted-null radius. The limit is set so chance matching inside that radius stays under a stated share (compute from the DEP density first).

## 6. Procedure
**S0. Source search (no download).**
- Search Library of Congress, David Rumsey, Penn State, USGS Library and state archives. For each candidate record scale, date, coverage of the 9t corner (619500 to 624000 E, 4593000 to 4597500 N, EPSG:6346; convert to lat and lon for search), scan resolution, rights.
- Output `docs/iterations/historic_source_search_9t.md` with a table of sources and verdict "candidate", "no coverage" or "unknown". Log dates searched.

**S1. Three-sheet topo probe.**
- Fetch D5 sheets with the fetch conventions. Crop each to 9t. Render at 2x and 4x. Two digitisers independently note every well, derrick, tank or oil-related symbol (do not show lidar or records). Record legend symbols used by that sheet edition.
- Output per sheet in `data/_source/historic_topo_probe/` crops and `docs/iterations/historic_imagery_probe_9t.md`.

**S2. Aerial frame probe.**
- From the D7 index pick frames over 9t by date. Measure each frame size and fetch one per date. Judge legibility at the scale of a derrick or a cleared pad (about 20 m).
- Verdict per frame date.

**S3. Georeferencing and accuracy.**
- Script `notebooks/wellsight_v2/s7_analysis/_georef_check_historic.py` (new). Use GDAL (`gdal_translate -gcp`, `gdalwarp`) with a polynomial or thin-plate transform from at least 12 ground control points, plus at least 10 independent check points. Report RMSE and max error in metres. Store GCPs and check points as `data/_source/historic_topo_probe/<source>_gcp.csv`.
- A source is "unusable here" if RMSE exceeds the limit.

**S4. Digitising.**
- For usable sources only. Two digitisers mark points in QGIS on a project `qgis/historic_marks_9t.qgz` (new). Third look adjudicates. Agreement computed as the share of marks within 25 m of an independent mark.
- Output `data/9t/results/historic/historic_well_marks_9t.gpkg` with columns source, date, digitiser, symbol, accuracy_m, adjudicated.

**S5. Compare.**
- Script `notebooks/wellsight_v2/s5_eval/_historic_vs_lidar_records_9t.py` (new). Three comparisons.
  1. Marks versus annotated pits and pads (distance distribution).
  2. Marks versus DEP records, with the shifted-set null inside the oil field footprint.
  3. Marks versus model candidates at K = 40 per km² and versus the model score at the mark, including marks with low scores.
- Historical positives are kept even when the lidar score is low. A low score is a model miss, not a label failure.

**S6. Report.**
- Verdict per source and date. List of positives. Counts of marks with no record and no feature.

## 7. Statistical analysis plan
- Georeferencing. RMSE with bootstrap interval over check points.
- Symbol agreement. Proportion with exact interval.
- Association (separate, later outcome). Excess match to DEP over shifted null at the preregistered radius. Interval from the null distribution. It never decides source readiness.
- Match to model candidates. Fraction of marks within the feature polygon at K = 40, exact interval.
- Exploratory. Era of the source against feature morphology type.

## 8. Quality control
- Check points are independent of GCPs.
- Digitisers blind to lidar and records during marking.
- Marks plotted over lidar hillshade for ten samples.
- Never merge marks from sources with different accuracy without carrying accuracy.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Source usable for a stated use | Provenance, dates and coverage known, total positional uncertainty (registration, symbol placement, borehole offset) within the use's limit, two-digitiser agreement above level, interpretable symbols | Digitise and use as level (b) evidence |
| Source unusable here | RMSE over limit, or no interpretable symbols across several dates | Record and move on. Never generalise from one sheet |
| Inconclusive | Coverage or interpretation insufficient | Report and test the next source |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\historic_source_search_9t.md`, `historic_imagery_probe_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\historic_topo_probe\` (crops, GCP tables)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\historic\historic_well_marks_9t.gpkg`
- Scripts in `s7_analysis` and `s5_eval` as named.

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| No pre-1880 source covers 9t | Record the null. Move to aerials and later topo |
| Symbols ambiguous | Two digitisers, report agreement. Do not force a label |
| Georeferencing error above 30 m | Use more GCPs, thin-plate, or declare unusable |
| Marks are displaced by cartographic convention | Report an offset distribution and do not snap |
| Rights restrict reuse | Record terms in provenance. Cite only |

## 12. Resources
Search 6 hours, probe 8 hours, georeferencing 6 hours per source, digitising 10 hours per usable source with two digitisers. Disk under 1 GB. No GPU.

## 13. Handoff and open questions
- Two digitisers. Which sources exist for 9t.
- Check the north neatline of 9t sheets so coverage is not partial.

## 14. Documentation updates
New docs above, `literature/CITATIONS.md` (each source), `analysis_log.md`, master plan (4.6 and 5.2).

## Review revision 2 (third review, 2026-11-04)
Source readiness depends on provenance, dates, legibility, coverage and total positional uncertainty, never on agreement with lidar or DEP. Association is a separate later outcome.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
