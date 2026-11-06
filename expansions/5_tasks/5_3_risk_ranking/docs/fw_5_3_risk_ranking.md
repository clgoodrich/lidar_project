# Framework 5.3. Risk ranking (scenario ranking with three separate quantities)

**Tier A (rewritten 2026-11-05).** The user withdrew the deferral. This file assumes the datasets in section 4A exist and is written so each assumption can be swapped later.
**Status.** Plan only. Nothing here has been run, downloaded or measured.
**Evidence level.** A ranking is a scenario product. It is not evidence about wells. Inputs carry their own levels. P is level (a) today. H and E are measured at documented wells, which is level (b) records plus (d) where field data exist.
**Depends on.** 5.6 corrected (well-level units), 3.0 scorer (out-of-fold candidate scores), P1 (splits). 7.5 Arm B (candidate precision) and 6.5 (field methane) only improve the quantities. They are not needed to start.
**Blocks.** 7.4 agency tooling. Any partner use of a priority list.

## 1. Problem and objective
An agency plugs a limited number of wells per year. It must choose which sites to verify and plug first. A defensible order uses three different things. The chance a well is there. The harm it does if it is there. The people and resources it can harm. The project has no P(well) today. It has P(feature), the chance a drawn-feature class is present (`docs/plans/adversarial_review_claude.md`, finding on well-level claims). So any ranking that includes candidates is conditional on the feature model.

**Decision.** In one funding round for one county (Venango first), which N sites does the agency send a crew to first for verification and, if confirmed, plugging.
**Decision user.** A DEP orphan well program staff member, or a partner doing the same job. Proposed. VERIFY that DEP will name one in R1.
**Measurable endpoint (independent of the ranking inputs).** Measured methane emission rate in kg per hour at the site by a field flux method (6.5 protocol), or a documented gas, brine or oil complaint tied to the site by DEP records. Primary is the rate, measured with a protocol fixed before ranking. Secondary is the complaint flag. The endpoint must not enter H or E.

**Questions.**
- Q1. Among documented wells (existence known), does ranking by H, E or a stated scenario put more endpoint events in the top N than random order does.
- Q2. How stable is the top N when weights, inputs and candidate scores move within their stated uncertainty.
- Q3. For candidates with no record, what does the ranking show when P is carried as a separate column. This is descriptive and conditional.

**Hypotheses.** Q1. Enrichment of high-emission sites in the top N exceeds the useful enrichment δ_enrich. Q2. Median top-N Jaccard across scenarios is at least the preregistered stability floor. Q3 has no hypothesis.

## 2. Scope
In. Venango County and the 9t footprint as the pilot. Documented wells and candidates, with P, H and E as three columns. Scenario rankings. Sensitivity and bootstrap. An endpoint test on documented wells only.
Out. One combined risk score presented as truth. Any claim that candidates are wells. Any claim of validated harm from agreement with an agency list. Cost-benefit of plugging. Health risk assessment.

## 3. Definitions
- **Site.** One well, resolved from blobs and records by 5.6. Not a blob, not a pad. Unresolved multi-well pads stay one site with a flag.
- **P (existence).** Probability a well is at the site.
  - Documented wells. P = 1 by record, with a position-uncertainty note (DEP coordinate source, 1800 sentinel dates are not used as era).
  - Candidates. P is the feature model's out-of-fold score band at policy K = 40 per km². It is P(feature), not P(well). Until 7.5 Arm B gives precision per band, P is carried as an ordinal band (K rank tercile), never as a probability.
- **H (hazard if it exists).** An ordinal or continuous index of harm potential given the well exists. Components proposed below in section 6 S2. Built only from records, mapped inputs and literature priors. Never from the endpoint.
- **E (exposure).** Receptor count and sensitivity within defined distances of the site. Water wells, public supply areas, buildings, streams, protected areas.
- **Scenario.** A named rule that orders sites from P, H and E. It states a weight vector or a lexicographic order.
- **Top N.** N sites per round. N is set by the agency budget. Default for analysis N = 50 or 5% of eligible sites, whichever is smaller.
- **Enrichment.** Endpoint events in the top N over the events expected in a random N, using documented wells with known endpoint status.
- **Rank stability.** Overlap (Jaccard) of top N sets and Kendall tau of full orders across scenarios and across bootstrap draws.
- **Conditional statement.** Every table and caption carries the words "conditional on the feature model" for any row whose P is a feature score.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Out-of-fold candidate rasters and tables | `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif`, `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg` | held |
| Well-level resolution (5.6 S0) | `data/9t/results/records/detector_output_pit_full_9t.gpkg`, `detector_output_pad_full_9t.gpkg` | to build in 5.6 |
| DEP wells (Venango) | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held |
| 2026 US orphan list | `data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| 2022 orphan list | `data/_source/reference/wells_us_orphan_2022/` | held |
| Roads | `data/_source/reference/tiger_roads/tl_2024_42121_roads.shp` (Venango) | held |
| County boundaries | `data/_source/reference/census_boundaries/cb_2023_us_county_5m.zip` | held |
| Annotated features | `qgis/annotations/annotations_proj.gpkg` | held |
| Exposure layers (water wells, buildings, streams, protected areas, land cover) | `data/_source/reference/risk_exposure/` (proposed) | see section 4A |
| Land cover | `data/_source/reference/PA_LandCover/` and `landcover/` exist and are empty | proposed |
| Hazard and endpoint data | `data/_source/reference/risk_hazard/` (proposed) | see section 4A |

## 4A. Assumed data
Every row is an assumption. None is verified. The executor must check each before use and stop if one fails.
| Layer | What is assumed | Proposed path | VERIFY how |
|---|---|---|---|
| Private water wells | Point layer for Venango with location, depth, use and construction date. Positional error under 100 m | `data/_source/reference/risk_exposure/water_wells_venango.gpkg` | Confirm source (PA Groundwater Information System or county records) and licence. Count rows against a published county total. Check 20 points against imagery for plausibility. Record median positional error from the source's own method note |
| Public water supply | Intake points and source water protection areas, polygons | `.../public_supply_swpa_venango.gpkg` | Confirm from the DEP or state geospatial portal. Check CRS and that polygons cover the known intakes |
| Buildings | Footprints for the county with occupied or not flag where available | `.../buildings_venango.gpkg` | Confirm vintage and completeness by counting buildings in three 1 km squares against imagery. Occupancy is probably absent. Treat as count only |
| Streams and wetlands | Mapped hydrography and wetlands with flow class | `.../hydrography_venango.gpkg`, `.../wetlands_venango.gpkg` | Check against lidar-derived channels from the existing DEM. Record the mismatch share |
| Protected areas | Game lands, state forest, preserves, conservation easements | `.../protected_areas_venango.gpkg` | Confirm source and vintage. Check boundaries against the county file |
| Land cover | A categorical raster, 30 m or finer | `data/_source/reference/PA_LandCover/` | The folder is empty. Confirm a source and download date. Check class legend |
| Hazard attributes in records | DEP fields for status, depth, formation, plugging, last inspection | in `venango_wells_all.gpkg` | List the columns. Report missingness per column. Drop any column more than 50% missing from H |
| Gas and brine observations | Inspection notes or measurements of gas, brine, oil at a subset of documented wells, with date and method | `.../risk_hazard/dep_inspections_venango.csv` | Ask DEP in R1 whether this exists, how it was collected and whether it can be released. Record the count and selection rule |
| Complaints | DEP oil and gas complaint records with location and resolution | `.../risk_hazard/dep_complaints_venango.csv` | Same request. A complaint is a reporting event. It depends on who lives nearby, so it is correlated with E. Mark that |
| Emission measurements | Field flux rates at orphan and abandoned wells | `.../risk_hazard/field_flux_pa.csv` | Literature values only until 6.5 runs. Kang et al. 2014 reports 19 wells with mean about 0.27 kg per day and 3 high emitters. Re-read the paper before citing. Ours must come from our own protocol |
| Subsurface | Formation depth tops and known pressure regime, for H priors | `.../risk_hazard/subsurface_tops_venango.csv` | Ask the state geological survey. Check coverage near 9t |

If the endpoint data (inspections, complaints or flux) do not exist for enough documented wells, Q1 cannot be run. Record that. The framework then delivers only Q2 and Q3 and says so.

## 5. Prerequisites and decisions
- Decision, user and endpoint named and committed in `docs/iterations/risk_ranking_design.md` before any scoring.
- Endpoint data selection rule written down. Which wells were measured and why. Selection toward known problem wells inflates enrichment.
- Preregistered before any ranking is computed against the endpoint. N, δ_enrich, the stability floor, the scenario list, the weight grid, the seeds.
- User decisions. N, δ_enrich, whether complaints may be the endpoint, which scenario is the agency default.
- Data access. Written confirmation of each section 4A row, or its removal from the run.
- Section 7 of `fw_00_common.md` conventions apply. Paths from `path_for`.

## 6. Procedure
**S0. Design note and data audit.**
- Write `docs/iterations/risk_ranking_design.md`. Decision, user, endpoint, unit, the three quantities, the verification result for each row of section 4A. A table of missingness per layer and per column.
- Script `notebooks/wellsight_v2/s7_analysis/_risk_data_audit_9t.py` (new). Reads every layer, asserts CRS EPSG:6346 after reprojection, counts rows, reports positional error where known, writes `data/9t/results/risk/risk_data_audit_9t.csv`.

**S1. Exposure layers.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_exposure_layers_9t.py` (new). For every site compute distance to and count of receptors in distance bands 50, 100, 250, 500 m. Streams by flow class. Water wells with a positional error buffer. Buildings as counts. Protected area membership as a flag, not a weight.
- Output `data/9t/results/risk/risk_exposure_layers_9t.gpkg` with layers `sites`, `receptors_water_wells`, `receptors_buildings`, `receptors_streams`.
- E is built as a vector of components, then as an index only inside a scenario. Component list and units are saved in the summary JSON.

**S2. Hazard proxy.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_hazard_proxy_9t.py` (new). H components from records and priors only.
  - Status (orphan, abandoned, plugged, active). Age bracket, with the 1800 sentinel kept as its own "unknown" class.
  - Depth and formation where present. Plugging record present or absent.
  - Surface evidence. Pit and pad size and position of the associated feature. Evidence level (a). Kept as a separate flag.
  - Proximity to streams and mapped wetlands as a pathway flag, not a hazard itself.
- Output `data/9t/results/risk/risk_hazard_proxy_9t.csv`. Every column names its source and its missing share.
- Forbidden inputs. Any measured flux, inspection result or complaint. Those belong to the endpoint.

**S3. Scenario rankings.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_scenarios_9t.py` (new). Scenarios, all labelled as rules, not findings.
  - A. Exposure first. Sort by E, break ties by H.
  - B. Hazard first. Sort by H, break ties by E.
  - C. Existence first for candidates. Documented wells ahead of candidates, then E.
  - D. Product. P band x H x E with each rescaled to ranks. Labelled "conditional on the feature model" and not used as the primary.
  - E. Agency default, if the agency supplies one (VERIFY in R1).
- Every output table has columns P, H, E, scenario rank, and a flag for whether P is a record or a feature band. Never a lone score.
- Output `data/9t/results/risk/risk_scenario_ranks_9t.csv`.

**S4. Sensitivity analysis.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_sensitivity_9t.py` (new).
  - Weight sweep. For scenario D and a weighted-sum variant, sweep each weight from 0 to 1 over a 0.1 grid with the other two rescaled to keep the sum at 1. Also a Dirichlet draw of 2000 weight vectors, seed from the preregistration.
  - One-at-a-time. Remove each E component, each H component and the P band in turn. Record top-N change.
  - Distance-band choice. Repeat with bands 25, 50, 100 m for water wells.
  - Output `data/9t/results/risk/risk_weight_sweep_9t.csv` and `risk_oneout_change_9t.csv`. A figure with top-N membership by weight (single-hue sequential, direct labels).

**S5. Rank-stability bootstrap.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_rank_bootstrap_9t.py` (new). Each draw perturbs inputs within stated uncertainty.
  - Candidate scores. Resample blocks (375 m) with replacement for the score-band cut points. B = 2000.
  - Positions. Jitter record positions by the source's stated error. Candidate positions by the match radius.
  - Missing attributes. Impute by draw from the observed distribution, never by the mean.
  - Per draw compute scenario ranks. Save top-N membership frequency per site, rank interval per site, Kendall tau and Jaccard between the draw and the base ranking.
- Output `data/9t/results/risk/risk_rank_stability_9t.csv`, per-site `risk_site_rank_interval_9t.csv`.

**S6. Endpoint check on documented wells (conditional on data existing).**
- Script `notebooks/wellsight_v2/s5_eval/_risk_endpoint_check_9t.py` (new). Restrict to documented wells with endpoint data. Compute enrichment in top N and Spearman of H and E against measured flux, per scenario. Block bootstrap by 1 km cell (wells on one lease are one cluster).
- Compare with a random order, with a records-only order (status and age), and with the agency list if supplied. Agreement with the agency list is reported as agreement. It is never described as validation.
- Output `data/9t/results/risk/risk_endpoint_enrichment_9t.csv`.

**S7. Report.**
- Script `notebooks/wellsight_v2/s7_analysis/_risk_report_tables_9t.py` (new). Writes the tables for the iteration doc. Every table has the three columns and the conditional statement.

## 7. Statistical analysis plan
- **Primary (Q1).** Enrichment ratio in the top N for the preregistered scenario, endpoint = measured emission above a fixed rate cutoff or the top decile of measured rates. Block bootstrap over cells, B = 2000. Non-inferiority does not apply. Superiority against δ_enrich.
- **Secondary.** Spearman of H and E with log emission rate. Precision at N for the complaint flag. Each scenario is secondary and exploratory. One primary scenario is named before scoring.
- **Stability (Q2).** Median and 5th percentile of top-N Jaccard across the bootstrap and across scenarios A to D. Per-site rank interval. A site is "stable in" if it is in the top N in at least 90% of draws.
- **Sensitivity.** Weight grid, Dirichlet draws, one-out, distance bands, N at half and double.
- **Multiplicity.** One primary. Radii, N and scenarios other than the primary are sensitivity.
- **Small endpoint counts.** If events in documented wells are under 15, report the exact Clopper-Pearson interval for the share, not an enrichment ratio with a bootstrap.
- **Selection.** Inverse inclusion weights if the endpoint sample was selected by a rule. If the rule is unknown, say so and report conditional results only.
- **Calibration.** None. The three quantities are not probabilities of harm.

## 8. Quality control and leakage checks
1. Row counts at every join. Sites in equals sites out. No site counted twice.
2. CRS asserted on every layer. Distances computed in metres in EPSG:6346.
3. Endpoint isolation. A test that no endpoint column or any value derived from it appears in H, E or P. Grep and column-lineage check in the summary JSON.
4. Weights and scenarios are written before the endpoint file is opened. Hash of the preregistration stored in the run folder.
5. Candidate scores for 9t use out-of-fold predictions only. In-sample predictions inflate P.
6. Position-error jitter applied identically in every draw. A seed per draw.
7. The same configuration run twice gives identical outputs.
8. Check ten sites on hillshade with receptors drawn.
9. Banned phrases in outputs and docs. "validated", "risk score" used alone, "probability of a well" for a feature band.
10. Every number in the doc comes from a saved file.

## 9. Gates
Margin sources follow `docs/plans/protocol_gates_and_metrics.md` section 5. One threshold serves both success and failure.
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Decision, endpoint, section 4A rows and preregistration committed | Start S1. Otherwise stop |
| Q1 success | Enrichment lower bound above δ_enrich for the primary scenario, with at least 15 endpoint events | Ranking beats random on documented wells. Say so for documented wells only |
| Q1 failure | Enrichment upper bound below δ_enrich | Ranking is no better than the useful gain. Revise H and E, or keep the agency list |
| Q1 inconclusive | Interval straddles δ_enrich, or fewer than 15 events | Report. Get more endpoint data. Do not deploy |
| Q2 success | 5th percentile top-N Jaccard at or above the stability floor | Ranking is robust to its inputs. This is stability, not validity |
| Q2 failure | Median Jaccard below the floor | List the sites that flip. Report which input drives it |
| Q3 | No gate | Descriptive |
**δ_enrich comes from the visit-cost tradeoff.** The agency states how many extra confirmed high-emission sites per N visits justify the data work. It never comes from the bootstrap width. The stability floor comes from how many sites the agency is willing to see swap in or out of a round.

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\risk_ranking_design.md` and `risk_ranking_9t.md`
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\` named `_risk_data_audit_9t.py`, `_risk_exposure_layers_9t.py`, `_risk_hazard_proxy_9t.py`, `_risk_scenarios_9t.py`, `_risk_sensitivity_9t.py`, `_risk_rank_bootstrap_9t.py`, `_risk_report_tables_9t.py`. `_risk_endpoint_check_9t.py` in `s5_eval\`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\risk\` run folder with the CSVs, `risk_exposure_layers_9t.gpkg`, figures `risk_rank_stability_9t.png`, `risk_weight_sweep_9t.png`, `_PROVENANCE.json`, `_RUN.md`
- Update `docs/analysis_log.md`, `docs/iterations/BACKLOG.md`, `docs/plans/EXPANSION_MASTER_PLAN.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| No P(well) | Carry P as a separate column and an ordinal band. State "conditional on the feature model" everywhere. Rank documented wells and candidates in separate lists as well as together |
| No ground truth for harm in enough wells | Deliver Q2 and Q3 only. Say Q1 was not run |
| Endpoint selection bias | Selection rule written. Inverse weights or conditional claim |
| Circularity (hazard proxy uses endpoint) | Forbidden-input rule and lineage check |
| Complaints track where people live, so they track E | Use flux as primary. Report complaints as secondary with this caveat |
| Receptor layers are stale or incomplete | Section 4A verification. Sensitivity with receptors removed |
| Position error larger than distance bands | Jitter in the bootstrap. Report share of sites where error exceeds band |
| Agency list agreement read as proof | Label as agreement in every caption |
| Heavy-tailed emissions make enrichment unstable | Use rank-based statistics and exact intervals |
| Rank flips look like a result | Report stability separately from validity |

## 12. Resources
S0 about 10 hours plus the data requests. S1 and S2 about 16 hours. S3 to S5 about 14 hours. S6 and S7 about 8 hours. No GPU. Disk under 5 GB on C:. Calendar dependency is DEP data release. Estimate 50 hours of work. Measure one S5 draw before scaling to 2000.

## 13. Handoff and open questions
- Does DEP hold inspections or flux for enough wells (at least 15 events).
- Who is the decision user. What are N and δ_enrich.
- May complaints be used. Is there an agency default list.
- Which receptor sources are licensed for use here.
- Confirm that 5.6 well-level resolution exists before candidates enter the ranking.
- Stop and report if the endpoint leaks into any input.

## 14. Documentation updates
`risk_ranking_design.md`, `risk_ranking_9t.md`, `analysis_log.md`, `BACKLOG.md`, master plan, `literature/CITATIONS.md` for Kang et al. 2014 and any receptor-weighting source used.

## Review revision (2026-11-05)
Deferral withdrawn at the user's request. Data are assumed. Each assumption is tagged VERIFY in section 4A. The prior "no P(well)" finding is kept as a stated condition on every output.
Source. `docs/plans/protocol_gates_and_metrics.md` sections 1, 5 and 9.
