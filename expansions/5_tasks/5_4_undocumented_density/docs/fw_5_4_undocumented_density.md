# Framework 5.4. Undocumented well density (identifiability)

**Tier B.** An identifiability analysis with conditional bounds. No density map.
**Status.** Rewritten to full depth 2026-11-05 by the build agent. Code exists in `src/`. Nothing has been scored.
**Evidence level.** An estimate under stated assumptions. Not a count. D is level (a). p and r need level (d) from 7.5. Records are level (b) for position and existence.
**Depends on.** 5.6 corrected (well-level units, cohort excess), R1 (DEP coordinate provenance), 7.5 Arm B (precision) and Arm C (recall bounds).
**Blocks.** Any total or density figure in a proposal, report or slide.

## 1. Problem and objective
Nobody knows how many wells exist that no record lists. Detector output alone cannot answer it. A candidate is a drawn-feature-like blob, not a well. On 9t, 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m (protocol section 1).

The estimate has one form. Total wells equal D times p over r. D is the number of distinct candidate sites. p is the share of those sites that are wells. r is the share of wells in the same eligible population that yield a candidate. Each term must be measured in the same unit and population.

**Objective.** State which terms are identified today, which are not, and what follows for each value they could take. Publish sensitivity and bounds only. Never a density surface.

**Questions.**
- Q1. What is D in distinct sites, not blobs, at the policy budget K = 40 per km²?
- Q2. For each pair (p, r), what totals, missed wells and undocumented wells follow?
- Q3. Once field data exist, what are the bounds on p and r, and is the upper bound on the total finite?
- Q4. Is a two-source capture-recapture estimate defensible here, and what does it assume?

**Hypotheses.** None. This process has no gate (protocol section 5 table, 5.4 row).

## 2. Scope
In. Distinct-well accounting for D. The documented population in the same unit. A sensitivity grid. Field-based bounds when 7.5 delivers. A capture-recapture diagnostic. A term-by-term identifiability table.
Out. Any density map, any county total, any smoothing of candidate counts into a surface. Any use of the withdrawn recall-gap result.

## 3. Definitions and estimand
- **Counting unit.** A well. Not a blob, not a pad.
- **Candidate site.** One or more candidate blobs merged into one site when their centroids lie within the merge radius (proposed 15 m, VERIFY against pit spacing). A pad holding several sites keeps them all and is flagged.
- **D.** Distinct candidate sites in the eligible footprint, taken from the top K by score, K = 40 per km² of scored eligible area. Ties by larger area, then id (fw_00 section 4).
- **Eligible footprint.** The 115 pit-bearing 375 m blocks on 9t, including blocks where the model found nothing.
- **p.** Well-level precision. The probability that a candidate site holds at least one well.
- **m.** Wells per positive site. Default 1. A multi-well pad raises it. A sensitivity term.
- **r.** Well-level recall. The probability that a well in the eligible population yields a candidate site.
- **Total.** T = D p m over r. **Missed.** D p m (1 minus r) over r. **Undocumented.** T minus N_doc.
- **N_doc.** The complete documented population in the same unit and footprint. DEP records of drilled wells (statuses that imply a hole), merged when two records sit within 5 m.
- **Validity conditions.** D p m counts distinct true wells. r concerns the same eligible population. Multi-feature and multi-well relations are resolved. Documentation scope and acquisition scope align. Until all four hold, every output is a sensitivity value.
- **Bound rule.** When the lower bound on r is 0, the upper bound on T is infinite. Say so.

## 4. Inputs and data inventory
| Input | Path | State |
|---|---|---|
| Full pit detector output | `expansions/5_tasks/5_6_record_association/data/processed/detector_output_pit_full_9t.gpkg` | built 2026-11-05 by 5.6 S0 |
| Pit blocks | `data/9t/derived/05/pit_blocks_9t.gpkg` | held |
| DEP wells | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held, read-only |
| 5.6 proposals and cohort excess | `expansions/5_tasks/5_6_record_association/results/` | built, exploratory |
| 7.5 Arm B precision sample | `expansions/7_scale/7_5_field_campaign/data/processed/arm_b_candidate_outcomes.csv` | assumed |
| 7.5 Arm C search areas | `expansions/7_scale/7_5_field_campaign/data/processed/arm_c_search_outcomes.csv` | assumed |
| DEP coordinate provenance | `data/_source/reference/dep_wells/dep_coordinate_source_venango.csv` | requested in R1 |

## 5. Assumed data
| Assumption | Tag | How to verify |
|---|---|---|
| 7.5 Arm B gives one row per sampled candidate site with identity status (confirmed well, definite non-well, ambiguous) and an inclusion weight | VERIFY | Read the 7.5 output schema. Check weights sum to the frame size |
| Arm B sampled from the same top-K frame that defines D | VERIFY | Compare the frame hash in 7.5 provenance with the D table hash |
| 7.5 Arm C gives searched areas with every well found by an independent search, and whether each yielded a candidate | VERIFY | Read the Arm C protocol. Confirm the search did not use the candidate list |
| Arm C search sensitivity is bounded by repeated independent searches | VERIFY | Count repeat searches. Without them r is conditional on what searchers find |
| The merge radius of 15 m separates distinct wells on 9t | VERIFY | Histogram of nearest-neighbour distance between DEP records on 9t. Check pads with several records |
| The DEP statuses kept for N_doc all imply a drilled hole | VERIFY | Read the DEP status definitions. "Operator Reported Not Drilled" and "Proposed But Never Materialized" are excluded |
| DEP coordinates are close enough that two records within 5 m are one well | VERIFY | Await R1 provenance. Report the merge count |
| Lidar acquisition and DEP documentation cover the same footprint | VERIFY | Overlay the footprint on the DEP export. Count records outside lidar |

## 6. Prerequisites and decisions
- 5.6 S0 output exists. It does as of 2026-11-05.
- The merge radius, the kept DEP statuses and the m grid are build-agent proposals. The user may change them.
- No preregistration is needed for the sensitivity grid. Field bounds inherit the 7.5 preregistration.
- Never cite the withdrawn recall-gap run.

## 7. Procedure
**S0. Identifiability table.**
- Script `src/_density_identifiability_terms_9t.py`. One row per term (D, p, m, r, N_doc). Current value or range, evidence level, source file, what would identify it, and status (identified, bounded, unidentified). Status follows from which files exist.
- Output `results/tables/density_identifiability_terms_9t.csv`.

**S1. Distinct-well accounting.**
- Script `src/_density_distinct_wells_9t.py`. Ranks the full pit output by score, keeps the top K per km² of the eligible footprint, merges blobs into sites within the merge radius, and flags sites on one pad. Builds N_doc from DEP records in the same footprint with the same 5 m merge.
- Checks. Row counts at every join. No candidate counted twice. K computed from footprint area, not from candidates.
- Output `results/tables/density_distinct_sites_9t.csv`, `density_accounting_9t.json`.

**S2. Sensitivity grid.**
- Script `src/_density_sensitivity_grid_9t.py`. p from 0.05 to 0.90 and r from 0.10 to 0.90 in steps of 0.05, m in {1, 1.5, 2}. Totals, missed and undocumented per cell. A cell where T is below N_doc is flagged inconsistent, because it would mean the detector population cannot hold the documented wells.
- Output `results/tables/density_sensitivity_9t.csv`, figure `results/figures/density_sensitivity_9t.png`. Single-hue sequential blue, labelled "sensitivity, not an estimate".

**S3. Field bounds.**
- Script `src/_density_field_bounds_9t.py`. From Arm B, p lower is confirmed weight over total and p upper is one minus definite non-well weight over total, each with a Clopper-Pearson interval on the Kish effective n. From Arm C, r with an exact interval, labelled conditional when search sensitivity is unbounded. T bounds are D p_lo m over r_hi and D p_hi m over r_lo. r_lo of 0 gives an infinite upper bound.
- Output `results/tables/density_field_bounds_9t.json`.

**S4. Cohort association link.**
- Uses 5.6 S4 (`_records_cohort_strata_9t.py`). Newly documented against previously listed wells by normalised excess over cohort-specific nulls. Descriptive. It gives no recall-equivalence gate and no density input.

**S5. Capture-recapture diagnostic.**
- Script `src/_density_capture_recapture_9t.py`. Two sources. Records (N_doc) and detector sites scaled by p. Overlap from 5.6 proposals within the primary radius. Chapman estimator per p in the grid, pooled and stratified by block halves of record density. A large gap between pooled and stratified estimates shows heterogeneity. The estimate assumes independence of the two sources and a closed population. Records cluster where drilling was permitted and lidar sees cleared ground better, so positive dependence is likely and the estimate is not a lower bound.
- Output `results/tables/density_capture_recapture_9t.csv`.

## 8. Statistical analysis plan
- No primary estimand. No test.
- Sensitivity grid values are deterministic functions of D, p, m and r.
- Field bounds use exact intervals for proportions and the identity-status bounds of protocol section 6.
- Capture-recapture reports the Chapman point value and its usual variance only as a diagnostic.
- Block bootstrap of D over the 115 blocks (B = 2000) is reported so D's own sampling spread is visible.
- Effective sample. Blocks and field sites, not candidates.

## 9. Quality control and leakage checks
1. Row counts asserted at each join. Expected 685 pit rows after dedupe from 5.6 S0.
2. CRS EPSG:6346 asserted on every layer.
3. No candidate in two sites. No record in two N_doc wells.
4. Every number in a document comes from a saved file.
5. The same config gives identical outputs on a second run.
6. Field bounds refuse to run if the Arm B frame hash differs from the D table hash.
7. Banned phrases in outputs. "density map", "estimated total" without "conditional".

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Not a gate | Output is a statement of what is identified | Publish the identifiability table and the grid |
| Bounds finite | r lower bound above 0 and Arm B present | Publish conditional bounds with every condition listed |
| Bounds infinite | r lower bound is 0 | Publish the lower bound only and say the upper bound does not exist |
| Density map | Never, until p and r have defensible bounds per stratum | Refuse |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\expansions\5_tasks\5_4_undocumented_density\src\` scripts as named above
- `C:\Users\colto\Documents\GitHub\lidar_project\expansions\5_tasks\5_4_undocumented_density\results\tables\` CSV and JSON
- `C:\Users\colto\Documents\GitHub\lidar_project\expansions\5_tasks\5_4_undocumented_density\results\figures\density_sensitivity_9t.png`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\density_identifiability.md` (lead to write from the saved tables)

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Grid read as an estimate | Label every figure and table as sensitivity |
| Blobs counted as wells | Site merge and pad flag. Report blobs and sites side by side |
| Multi-well pads | m grid. Report how many sites hold several records |
| Arm B frame differs from D | Hash check refuses the run |
| r unbounded below | State the infinite upper bound |
| Capture-recapture read as a floor | Caveat in every row. Report pooled and stratified |
| Documented and acquisition scopes differ | Footprint overlay. Restrict N_doc to the footprint |

## 13. Resources
S0 to S2 about 6 hours. S3 and S5 about 4 hours once 7.5 data exist. CPU only. Seconds per run.

## 14. Handoff checklist and open questions
- Confirm merge radius and kept DEP statuses.
- Confirm 7.5 Arm B and Arm C schemas against section 5.
- Await R1 for coordinate provenance.
- Stop if a field input's frame hash differs from D.

## 15. Documentation updates
`density_identifiability.md`, `analysis_log.md`, master plan, BACKLOG for anything deferred, `literature/CITATIONS.md` for Chapman (1951) if the diagnostic is reported.

## Review revision 2 (third review, 2026-11-04)
Write distinct-well accounting and show bounds as recall varies. No density gate from spatial excess alone.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
