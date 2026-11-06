# Framework 4.8. Leaf-off optical imagery

**Tier B.** Coverage probe with a bounded chip pilot. Full depth written 2026-11-05 by the build agent from the 60-line draft. Change freely.
**Evidence level.** (a) drawn feature, for visibility of drawn pits and pads. (b) historical, only where a dated photo shows a feature before a known date.
**Depends on.** Nothing for the probe. P2 audit blocks must be excluded if the chips are ever used for scoring.
**Blocks.** Any D10 bulk imagery fetch. Any optical review layer for candidates.
**Code.** `expansions/4_modalities/4_8_leafoff_optical/src/` (built 2026-11-05, see the README build table).

## 1. Problem and objective
Leaf-off aerial photos can show bare ground, roads and pads under deciduous cover. How much of the study areas has usable leaf-off imagery is unknown. An earlier chip check reported 10 of 13 chips blank. A review reported that figure. Nobody re-checked it. Blank chips were never separated from chips that show nothing.

**Objective.** Two tables. A coverage table of programs, dates and seasons. A chip status table on a preregistered sample that separates missing data from genuine non-detection and records the visible ground fraction.

**Hypotheses.** H1. At least one source gives a usable share above the gate (section 9) on the 9t sample. H0. No source does. This is a readiness test of the imagery. It is not a test of the lidar model.

## 2. Scope
**In.** Coverage search, season check, a 60-feature chip sample, georegistration at road intersections, visible ground fraction, blind interpretability by two reviewers, the D10 decision.
**Out.** Training an optical model. Fusing optical and lidar features. Scoring candidates against optical evidence. Any claim that a feature absent from a photo is absent on the ground.

## 3. Definitions
- **Feature.** One drawn polygon in the `pit_inside` or `pad` layer of `qgis/annotations/annotations_proj_v2.gpkg` whose centroid lies in 9t.
- **Chip.** A 100 m square around the feature centroid, 700 by 700 pixels, EPSG:6346.
- **Leaf-off.** An acquisition date in November to April. A date in May to October is leaf-on.
- **Chip status.** Exactly one of usable, low visible ground, cloud or shadow, unregistered, off-season, undated, blank, unavailable. The order of tests follows that list in reverse. Unavailable means the service returned nothing. Blank means mostly nodata, near-white or near-uniform. Undated means the flight date is not verified. The draft had six statuses. Undated and low visible ground were added so that no chip is forced into a wrong class.
- **Usable chip.** Verified leaf-off date, median registration offset of its source at or under 5 m, and visible ground fraction in the footprint at or above the cutoff.
- **Visible ground fraction.** Share of pixels in the feature footprint buffered 5 m with excess green (2g minus r minus b on chromatic coordinates) below 0.05 and mean brightness from 40 to 230. It approximates soil and leaf litter seen through bare branches. It cannot tell leaf litter from bare soil.
- **Usable share.** Usable chips over all sampled chips of one source. Missing chips count against the share. They never count as negatives for any feature.
- **Interpretability.** A reviewer's yes, no or cannot tell on whether the drawn feature is visible on a usable chip, blind to lidar and to the outline.

## 4. Inputs and data inventory
| Input | Path | State |
|---|---|---|
| Annotated pits and pads, roads | `qgis/annotations/annotations_proj_v2.gpkg` | held |
| PEMA county mosaics (PASDA PEMAImagery2018, layers 242 Venango, 110 Forest) | map service, URL in `notebooks/wellsight_v2/s5_eval/_pit_leafoff_geotiff_9t.py` | reachable, dates unverified |
| NAIP 2015, 2017, 2019, 2022 | Planetary Computer STAC, see `_pit_naip_chip_9t.py` | reachable, all leaf-on |
| Earlier chips | `data/9t/results/pit/photo/pit_leafoff_photo_<id>_9t.tif`, `data/9t/results/pit/pit_leafoff_chip_288_9t.png` | held |
| Other state orthophotos | D7 and D10 metadata search | not searched |
| Leaf-off mosaic GeoTIFF for offline chips | `expansions/4_modalities/4_8_leafoff_optical/data/raw/leafoff_mosaic_9t.tif` | assumed |
| Program search log | `expansions/4_modalities/4_8_leafoff_optical/data/raw/leafoff_programs.csv` | assumed |
| Reviewer sheets | `expansions/4_modalities/4_8_leafoff_optical/data/raw/reviews/*.csv` | assumed |

### Assumed data
Each item is assumed to exist so the code could be built. Each is tagged VERIFY with the check that confirms it.

| Assumption | Tag | How to verify |
|---|---|---|
| The PEMA Venango 2020 mosaic was flown leaf-off | VERIFY | Read the PASDA layer metadata or the PEMA flight report. Record the date in `config_4_8.json` |
| The PEMA Forest layer has its own flight date, possibly a different year | VERIFY | Same check for layer 110 |
| A statewide or county leaf-off program other than PEMA covers 9t | VERIFY | Search PASDA, USGS EarthExplorer and county GIS offices. Log in the programs CSV |
| A leaf-off mosaic can be downloaded as a GeoTIFF for offline chips | VERIFY | Check PASDA download terms and tile sizes before D10 |
| Map service georeferencing is within 5 m of the lidar | VERIFY | S3 measures it on 10 road intersections |
| Warren has a bbox on file for the coverage table | VERIFY | Set `areas.warren` in the config. It is null on 2026-11-05 |
| Two reviewers are available and blind to lidar | VERIFY | Name them in the decisions file before S5 |
| Licence allows internal figures of the photos | VERIFY | Read the PASDA and PEMA terms |

## 5. Prerequisites and decisions
Fix before any chip is opened. The seed, the sample size of 60, the visible ground cutoff (0.15) and the usable share gate (0.60). All four sit in `config_4_8.json` and are copied into the preregistration. Commit the sample file from S1 before S2 runs. The cutoff and gate are build-agent defaults. The user may change them before S1 and never after S2.

## 6. Procedure
**S0. Coverage table.** Script `src/_leafoff_coverage_table_9t.py`.
- Inputs. Known sources in the config and the program search log.
- Algorithm. Merge, flag each program leaf-off, leaf-on, mixed or undated by month, compute cover share of each area bbox.
- Output. `results/tables/leafoff_coverage_9t.csv` and `.md`. Copy the markdown to `docs/iterations/leafoff_coverage_probe.md`.
- Check. NAIP dates on file are June, September, May and July. NAIP is leaf-on here and serves as a season control only.

**S1. Feature sample.** Script `src/_leafoff_feature_sample_9t.py`.
- Draws 60 features from pits and pads in proportion to their counts with the master seed. A second run gives the same rows.
- Output. `results/tables/leafoff_feature_sample_9t.csv`. Commit it before S2.

**S2. Chip pull and status.** Script `src/_leafoff_chip_status_9t.py`.
- Inputs. The sample, the annotations, the S3 summary if present, one or more sources.
- Algorithm. Fetch a chip per feature and source, save it as a GeoTIFF, compute measures, assign the status in the fixed order.
- Outputs. Chips under `data/interim/chips/<source>/` (git-ignored). Table `data/9t/results/optical/leafoff_chip_status_9t.csv`.
- Checks. Row count equals features times sources. Every sampled feature exists in the annotations.

**S3. Georegistration.** Script `src/_leafoff_georeg_offset_9t.py`.
- Template mode finds road intersections in the drawn roads layer and draws 10 with the seed. A person clicks the intersection centre on each photo in QGIS.
- Summary mode reports median, maximum and RMSE of the offset and the mean shift per source. A source is registered when the median is at or under 5 m.
- Rerun S2 after S3 so chip status carries the measured offset.

**S4. Visible ground fraction.** Computed inside S2 by `image_measures` in `src/_leafoff_kit_4_8.py`. It is reported for the footprint and for the whole chip.

**S5. Interpretability and gate.** Script `src/_leafoff_review_gate_9t.py`.
- Two reviewers mark yes, no or cannot tell on usable chips only, blind to lidar and to the outline.
- Outputs. `data/9t/results/optical/leafoff_gate_9t.json` and `leafoff_status_by_source_9t.png`.

**S6. Fetch full imagery.** Only after a success at the gate. D10 goes to F: with a `.gitignore` rule in the same change.

## 7. Statistical analysis plan
- **Primary estimand.** Usable share per source on the 60-feature sample, with a Clopper-Pearson interval. One primary per source. The PEMA Venango source is primary because it already covers most of 9t.
- **Secondary.** Share judged visible by both reviewers on usable chips, with an exact interval. Cohen's kappa over three categories. Visible ground fraction by layer (pit against pad). All exploratory.
- **Sample size.** 60 gives about plus or minus 13 points at a share near 0.5 under simple random sampling. Features cluster on pads, so treat the interval as optimistic. The design effect is not measured.
- **Missing data.** Blank, unavailable and undated chips are reported with their counts. They are never folded into a no.
- Absence of a feature in a photo is not rejection of the feature.

## 8. Quality control and leakage checks
1. Row counts asserted at the sample draw and after the chip pull.
2. CRS asserted on the annotations, the mosaic and every saved chip.
3. No duplicate feature keys in the sample.
4. A second S1 run gives the same sample. Tested.
5. Dates verified from metadata before any chip is called usable. File dates are not flight dates.
6. Offsets measured on road intersections that are independent of the features.
7. Reviewers blind to lidar. Outlines hidden.
8. Sanity render. Open five usable and five blank chips in QGIS over the hillshade.
9. If chips ever feed scoring, no P2 audit block may appear in the sample.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Lower bound of usable share above 0.60 | Fetch D10 for that source. Plan an optical review layer |
| Failure | Upper bound below 0.60 | Unusable here for that source and date. Record and move on |
| Inconclusive | Interval spans 0.60 | Report. Raise the sample or verify the dates, then rerun S2 |
The gate concerns imagery readiness. It never uses agreement with the lidar model.

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\leafoff_coverage_probe.md` (copied from the S0 markdown)
- `C:\Users\colto\Documents\GitHub\lidar_project\expansions\4_modalities\4_8_leafoff_optical\results\tables\leafoff_coverage_9t.csv`, `leafoff_feature_sample_9t.csv`, `leafoff_offsets_summary_9t.csv`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\optical\leafoff_chip_status_9t.csv`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\optical\leafoff_gate_9t.json`, `leafoff_status_by_source_9t.png`
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\expansions\4_modalities\4_8_leafoff_optical\src\`

## 11. Failure modes and mitigations
| Risk | Mitigation |
|---|---|
| Evergreen cover hides features | Report green share per chip. Do not count green chips as negatives |
| Registration offsets above 5 m | Status unregistered. Fit a shift only if offsets are a constant translation |
| Service limits or outages | Unavailable is a status. Rerun later. Never impute |
| Flight dates wrong or unknown | Undated status until verified |
| Map service returns white tiles outside a county mosaic | Blank status. Try the neighbouring county layer as the earlier script did |
| Visible ground proxy counts leaf litter as ground | Reviewers judge interpretability. The proxy only screens |
| Reviewers see the outline | Chips are saved without outlines. Outline overlays stay in QGIS only after review |

## 12. Resources
About 10 hours. Search 3, sample and pull 2, registration clicks 2, review 2, write-up 1. Chips are under 1 MB each. No GPU.

## 13. Handoff checklist and open questions
- Flight dates of PEMA layers 242 and 110.
- Names of the two reviewers.
- Warren bbox for the coverage table.
- Confirm the cutoff 0.15 and the gate 0.60 before S1.
- Stop and report if every source is undated after the search.

## 14. Documentation updates
Coverage doc, `docs/analysis_log.md` entry, `docs/plans/EXPANSION_MASTER_PLAN.md` status, `docs/iterations/BACKLOG.md` for a D10 fetch if the gate passes, `literature/CITATIONS.md` for the excess green index (Woebbecke et al. 1995) in the same change that runs S2.

## Review revisions (2026-11-04)
Bounded pilot. Coverage and date table and a small predefined chip sample. Separate blank or unavailable chips from non-detection. Earlier chips were reported blank 10 of 13 times. Absence of a feature in imagery is not rejection. Source `docs/plan_mod_leafoff_optical.md`.
