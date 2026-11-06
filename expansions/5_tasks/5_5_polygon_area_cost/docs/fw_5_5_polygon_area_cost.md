# Framework 5.5. Polygon area and cost

**Tier B.** Full design. Assumes a field or drone reference and an agency cost table exist. Nothing here has been run.
**Evidence level.** (a) drawn feature with area as an attribute, checked against an independent surveyed reference. Area says nothing about wells.
**Depends on.** P2 audit set (pads not used to train the scored model). Pad model and threshold products on 9t.
**Blocks.** Any budget estimate that uses predicted area.

## 1. Problem and objective
Pad polygons give a disturbed area. An agency may use area to plan restoration and to estimate cost. How close predicted area is to a surveyed area is unknown. How error in area moves cost is unknown.

The review reports that the pad model over-claims area about 2 times. The source in the repo (`docs/iterations/LEADERBOARD.md`, around line 317) compares flagged area on the tile at threshold 0.50 (197.95 ha) with total annotated pad area (about 110 ha). That ratio includes false-positive regions and merged blobs. It is a tile-level flagged-area ratio. It is not a per-pad area ratio. VERIFY which one the review means before using the figure.

**Objective.** Measure agreement of predicted pad polygons with an independent surveyed outline, define the decision that needs area, and propagate area error to cost with stated uncertainty.

**Hypotheses.** H1. Median log ratio of predicted to reference area lies within ±δ_area of zero and the 90th percentile absolute log ratio is within the cost tolerance. H0. It does not. A bias correction (a scale factor fitted on a calibration set) is tested as a second arm.

## 2. Scope
In. Area agreement at the pad level, boundary definitions, cost model structure, error propagation, a restoration-budget decision.
Out. Total plugging cost without a cost table. Contamination footprint, subsurface excavation and well depth. Any claim about wells.

## 3. Definitions
- **Decision.** The agency allocates a restoration budget per pad. Area enters the surface restoration term only. A decision error is a pad whose predicted cost lands outside the tolerance band around the reference cost.
- **Disturbed surface.** The cleared or graded surface of the pad as seen from the pad edge, excluding access road and pits. This is the primary boundary definition (user decision to confirm).
- **Graded pad.** Disturbed surface restricted to the levelled platform. A second definition, reported as sensitivity.
- **Footprint with road.** Disturbed surface plus the access road within 30 m of the pad edge. Third definition, sensitivity only.
- **Reference area A_ref.** Area of the surveyed outline under the chosen definition. Field GNSS (RTK, walked perimeter) or a drone orthomosaic and DSM (RTK or ground control, digitised by two people).
- **Predicted area A_hat.** Area of the model polygon at the frozen threshold, after the declared dedupe and merge rules, clipped to the same boundary definition.
- **Log area ratio.** r = ln(A_hat / A_ref). Unit is the pad.
- **Cost model.** C = F + c_a × A + c_r × L_road, with F the per-well fixed cost (mobilisation, plugging, which depends on depth and condition and not on area), c_a unit surface restoration cost per area, and c_r unit road restoration cost per length. Only c_a × A depends on the polygon area.
- **Area share of cost.** f = c_a A_ref / C_ref.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Annotated pad polygons | `qgis/annotations/annotations_proj.gpkg` layer `plat` | held |
| Model pad polygons and threshold products | `data/9t/results/pad/` and `data/9t/models/pad/unet_cv5_iso/`, builders `_pad_threshold_products_9t.py` | held |
| Pad cover split | `data/9t/results/pad/pad_cover_split_9t.gpkg` | held |
| Operating-point sweep and flagged area table | `docs/iterations/LEADERBOARD.md` (flagged-area table around line 310) | held |
| Surveyed outlines (GNSS or drone) | `data/_source/pad_survey/pad_outlines_survey.gpkg` | proposed |
| Drone orthomosaic and DSM for the same pads | `data/_source/pad_survey/<pad_id>/` | proposed |
| Agency cost table | `data/_source/reference/cost/restoration_cost_table.csv` | proposed |
| Reviewer redraws | `data/9t/results/pad/pad_redraw_reviewers_9t.gpkg` | proposed |

## 5. Assumed data
| Assumption | Tag | How to verify |
|---|---|---|
| Surveyed outlines exist for at least 60 pads in at least 4 independent blocks, each drawn without seeing model polygons | VERIFY | Count pads and blocks in the survey file. Read the survey protocol. Confirm blinding |
| Survey accuracy is at most 0.10 m horizontal (RTK GNSS or a drone with ground control) | VERIFY | Read instrument and processing report. Check against 5 control points |
| Surveyed pads are a probability sample of the pad population in the target blocks, or the selection rule is known | VERIFY | Read the sampling rule. A convenience sample (pads near roads) is flagged and weighted or labelled |
| At least some surveyed pads lie in blocks the scored model did not train on | VERIFY | Join to the fold and audit lists. Use the isolated pad model (`unet_cv5_iso`) |
| Survey date is close to the lidar date, or pad change between dates is documented | VERIFY | Compare dates. Check against imagery for earthwork between flights |
| An agency table gives unit costs for restoration area, road length and plugging, with year and basis (PA DEP or federal program table) | VERIFY | Read the table, record source, year, units, and whether costs are per acre of disturbed area |
| The cost table separates the area-dependent term from fixed per-well cost | VERIFY | Check line items. If not separable, f cannot be estimated and cost claims stop at area |
| The review's "about 2 times" figure refers to flagged area, not per-pad area | VERIFY | Recompute per pad from the saved polygons (S1) and compare with the tile ratio |
| Reviewers are available for two independent redraws of 30 pads | VERIFY | Confirm people and hours |

## 6. Prerequisites and decisions
1. Boundary definition. Disturbed surface as primary.
2. Decision tolerance. The cost error the agency accepts per pad (proposed ±25%, user decision). This margin comes from the decision, not from the data spread.
3. Which model and threshold. Frozen before scoring.
4. Survey plan and who walks or flies.
5. Preregistration committed.

## 7. Procedure
**S0. Protocol.**
- Write `docs/iterations/polygon_area_protocol.md` with the three boundary definitions, how roads, pits, berms and spoil piles are treated, slope and canopy rules and examples. Two reviewers pilot on 5 pads and agree wording. The protocol is frozen before the survey is read.

**S1. Existing comparison (no survey).**
- Script `notebooks/wellsight_v2/s5_eval/_pad_area_by_pad_9t.py` (proposed). For each annotated pad, match model polygons by IoU 0.3 and one-to-one. Compute per-pad A_hat, A_drawn, IoU, log ratio and merged or split flags. Separately sum flagged area on the tile and compare to the annotated total, so the review figure is reproduced and decomposed into false-positive area, merged-blob area and per-pad bias.
- Output `data/9t/results/pad/pad_area_by_pad_9t.csv`, `pad_area_tile_decomposition_9t.json`.

**S2. Reviewer redraws.**
- 30 pads, two reviewers, independent, blind to model polygons and each other. Inter-reviewer IoU and area ratio are a reproducibility reference, not a ceiling.
- Output `data/9t/results/pad/pad_redraw_agreement_9t.csv`.

**S3. Survey ingest.**
- Script `notebooks/wellsight_v2/s1_build/_ingest_pad_survey.py` (proposed). Assert CRS and transform to EPSG:6346, NAVD88 for any DSM. Convert survey outlines to the boundary definition by the protocol. Two people digitise drone outlines. Report their IoU. Hash inputs.
- Output `data/_source/pad_survey/pad_outlines_survey.gpkg` (source) and `data/9t/derived/pad/pad_reference_area_9t.csv`.

**S4. Area agreement.**
- Script `notebooks/wellsight_v2/s5_eval/_pad_area_agreement_9t.py` (proposed). Per pad A_hat, A_ref, r, absolute percent error, IoU, mean symmetric boundary distance and 95th percentile boundary distance (Hausdorff 95). Bland-Altman limits on log scale. Regression of ln A_hat on ln A_ref (slope and intercept) to separate scale bias from proportional bias. Stratify by pad size tercile, slope, canopy and pad type.
- Output `data/9t/results/pad/pad_area_agreement_9t.csv`, `pad_area_agreement_summary_9t.json`.

**S5. Calibration arm.**
- Fit a scale factor on half the blocks, apply to the other half, swap. A correction is reported only if cross-block error drops. Fit never uses the audit pads.

**S6. Cost propagation.**
- Script `notebooks/wellsight_v2/s7_analysis/_pad_cost_propagation_9t.py` (proposed). Monte Carlo with 10,000 draws per pad. Inputs. The empirical distribution of r (resampled by block, so the pad-level r is not treated as independent noise), the cost table range for c_a as a lognormal fitted to the table's low and high values, F as given per well condition class, c_r from the table. Compute C_hat and C_ref per pad and per portfolio of N pads.
- Closed form for reference. Relative cost error from area alone is f × (exp(r) − 1). With f = 0.3 and r = ln 2 the area error alone moves cost by 30%. State f from the table, never assume it.
- Portfolio view. Total area error over many pads partly cancels if errors are unbiased, and does not cancel if bias is present, so report per pad and per portfolio separately.
- Output `data/9t/results/pad/pad_cost_error_9t.csv`, `pad_cost_error_summary_9t.json`, figure `data/9t/results/pad/figures/pad_cost_error_9t.png`.

**S7. Decision analysis.**
- For each tolerance (±15%, ±25%, ±40%) report the share of pads whose C_hat is within tolerance of C_ref, with a block interval. Include the break-even f below which area error does not matter.

## 8. Statistical analysis plan
- **Primary.** Median log area ratio r with a block-bootstrap interval (B = 2000, block as unit, pads in one block are one cluster). Also the 90th percentile of |r|. Decision. Success if the interval for the median sits within ±δ_area and the 90th percentile of |r| is within ln(1 + tolerance). δ_area comes from the decision tolerance (for ±25% cost and area share f, δ_area = ln(1 + 0.25 / f) as a proposal, user to confirm). Failure if the interval lies outside ±δ_area. Else inconclusive.
- **Secondary.** IoU and boundary distance. Mean absolute percent error. Bland-Altman limits. Agreement by definition (graded pad, footprint with road).
- **Reference noise.** Compare inter-reviewer area ratio and survey-to-redraw agreement. Model error is judged against the survey, and survey digitiser noise is subtracted in a sensitivity run.
- **Sample size.** n pads for the median of a log ratio with SD s and half-width d is about (1.96 s / d) squared times the design effect. State s from S1 (existing per-pad ratio), not assumed. If fewer than 15 blocks, add a permutation interval.
- **Proportions.** Clopper-Pearson for the share within tolerance.
- **Effective sample.** Blocks, not pads in one lease.
- **Not used.** F1 alone for area. Pixel accuracy.

## 9. Quality control and leakage checks
1. Row counts asserted for every join of pads, polygons and survey outlines.
2. CRS and units asserted. Area computed in the projected CRS, never in degrees.
3. Pads scored by the isolated model, in blocks it did not train on. Audit pads excluded from calibration.
4. The survey was made without model polygons visible. Confirm.
5. Boundary definition identical for model and reference. Check on 5 pads by overlay.
6. Survey and lidar dates compared for earthwork.
7. Cost table year and units normalised, with the inflation basis stated.
8. Second run reproduces outputs. Seeds recorded.
9. Sanity render of 6 pads with model, annotator and survey outlines over hillshade.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Survey n at least 60 pads in 4 or more blocks, cost table with separable area term | Proceed. Else run S0, S1, S2 only |
| Success | Median r interval within ±δ_area and P90 |r| within tolerance | Predicted area may enter a restoration estimate for the tested pad type |
| Failure | Median r interval outside ±δ_area | Do not use predicted area for cost. Test the calibration arm |
| Inconclusive | Interval crosses the margin | Report. State n needed |
Margin source. The agency tolerance on pad cost, through the area share f. Not the spread across annotators.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\polygon_area_protocol.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\pad_area_cost_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\pad_area_cost_prereg.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_pad_area_by_pad_9t.py`, `_pad_area_agreement_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_ingest_pad_survey.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\_pad_cost_propagation_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\pad\` (CSV, JSON, `figures\`)
- `.gitignore` rule for `data/_source/pad_survey/` if drone rasters reach 100 MB.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Boundary ambiguity inflates disagreement | Protocol, three definitions, overlay checks |
| Tile-level 2 times read as per-pad bias | S1 decomposition |
| Survey sample is not the target population | Record the rule. Weight or label |
| Cost table lacks a separable area term | Stop at area. State that cost cannot be estimated |
| Survey and lidar dates differ | Date check. Drop changed pads |
| Merged or split polygons distort area | Flag and report with and without |
| Area error is small but cost error large because of F | Report f. Area is not the dominant cost term |
| Few independent blocks | Permutation interval |

## 13. Resources
S0 to S2 about 10 hours plus reviewer time. Survey field days depend on partners and are a calendar dependency. S3 to S7 about 16 hours, CPU only.

## 14. Handoff and open questions
- Boundary definition and tolerance.
- Who surveys, with what instrument.
- Source and year of the cost table.
- Whether the review's 2 times is tile-level or per pad.
- Stop if the cost table cannot separate the area term.

## 15. Documentation updates
Protocol doc, `pad_area_cost_9t.md`, `analysis_log.md`, LEADERBOARD if a model result is reported, master plan, BACKLOG, `literature/CITATIONS.md` for any cost or survey-accuracy source.
