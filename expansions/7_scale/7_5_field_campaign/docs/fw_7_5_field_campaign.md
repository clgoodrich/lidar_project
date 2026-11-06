# Framework 7.5. Field campaign

**Tier A.** Highest evidentiary value. Partner dependent.
**Evidence level.** (d) confirmed well and (c) steel anomaly.
**Depends on.** A partner with site access, 4.1 pilot, 6.5 protocol, P2 (frozen sampling frame), R3.
**Blocks.** 5.4 (density), the feature-to-well share, everything that claims anything about wells.

## 1. Problem and objective
All results so far are lidar and records. Only field visits say whether drawn features and model candidates are wells, and whether the detector misses wells. On 9t only 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m.

**Questions.**
- **Arm A.** What share of drawn pits and pads are wells, by morphology and era stratum.
- **Arm B.** What share of model candidates (by score band) are wells. Precision.
- **Arm C.** In probability-sampled areas searched independently, how many wells exist that neither the records nor the detector flagged. Bounds on recall.

## 2. Scope
In. Design, sampling frames, protocols, sheets, database, analysis plan, partner agreement points.
Out. Executing the visits (a field team).

## 3. Definitions
- **Confirmed well (d).** Visible wellhead, casing, wellbore access or an agency record tied by on-site evidence.
- **Steel anomaly only (c).** A magnetic or metal-detector anomaly without a visible wellhead.
- **Nothing found.** Search completed, no evidence.
- **Unresolved.** Search incomplete or evidence ambiguous.
- **Inaccessible.** Site could not be reached or permission was refused.
- Search sensitivity. The probability that a defined search finds a well that is present. Not assumed to be 1.

## 4. Inputs
| Input | State |
|---|---|
| Drawn features (pits, pads) with era proxies | held (`annotations_proj.gpkg`, `well_age_morphology.md`) |
| Model candidates at frozen K = 40 per km² | P2 frozen frame |
| DEP records and status | held |
| Historic marks (4.6) for era strata | future |
| Magnetometer and field methane instruments | R3, 6.5 |
| Land access permissions | partner |

## 5. Prerequisites and decisions
A partner and a safety plan. Landowner permissions. A decision on what counts as a confirmed well. Primary estimate and precision target.

## 6. Procedure
**S0. Design document.**
- `docs/iterations/field_campaign_design.md`. Contents. Target estimands for each arm, sampling frames, strata, sample sizes, protocols, blinding, data sheets, outcomes, handling of unresolved, analysis plan, safety, permissions, budget.

**S1. Sampling frames and draws.**
- Script `notebooks/wellsight_v2/s6_review/_field_sample_draw.py` (new). Draw with a saved seed. Record inclusion probabilities.
  - Arm A frame. All annotated pits and pads in audit blocks or a reserved area. Strata. Morphology type and era proxy (record date class with unknown dates (1800 sentinel) as their own class, dated historic map presence). Allocation proportional with a floor of 10 per stratum.
  - Arm B frame. Candidates at the frozen K, five equal-count score bands, equal allocation.
  - Arm C frame. Random 250 m by 250 m cells from the reserved area, with a buffer around Arm A and B sites. Search each cell in full.
- Output `data/<area>/results/field/field_sample_v1.csv` frozen with hash.

**S2. Sample size.**
- Per estimate n = 1.96 squared times 0.25 over d squared under simple random sampling. 43 for plus or minus 15 points, 96 for 10, 24 for 20. Inflate by a design effect (default 1.5) and for inaccessible sites (default 20%). Forty sites in total cannot support five score bins. State the primary estimate (default Arm A overall share) and size for it. Report per-stratum results as exploratory unless sized.
- Correction 2026-11-06 (review 7.5-01). n = 182 sizes each identity bound alone to plus or minus 10 points. It does not size the share. With 20% inaccessible in the gap the expected bound width at n = 182 is 0.407, over the 0.30 target. The target needs about 746 allocated sites under the same deff and access share. The table field_sample_size_v1.csv now gives both numbers.

**S3. Protocol and sheets.**
- Search protocol per site. GNSS position (state datum and accuracy), a standard search radius and time, photographs, magnetometer pass (4.1), methane screen (6.5), evidence checklist, searcher ID. Blinded where possible. Searchers do not see model score or record status.
- Data sheet `docs/iterations/field_sheet_template.md` and a database schema (CSV with codebook, or an Artifact database if the partner wants a shared sheet).

**S4. Search sensitivity.**
- For a subset (at least 10 sites) a second independent searcher repeats the search without knowing the first outcome. Estimate the agreement and use a two-searcher capture-recapture style estimate as a diagnostic, not a guarantee. Where a documented well is present (a seeded control, for example a known DEP well in the cell) record whether the search found it.
- If search sensitivity cannot be bounded, report conditional recall only.

**S5. Execution tracking.**
- Log every attempted visit, including refusals, access failures and weather. Store `field_visit_log.csv`. Non-visits count in the denominator of inaccessible.

**S6. Analysis.**
- Script `notebooks/wellsight_v2/s5_eval/_field_analysis.py` (new). Weighted proportions with inclusion probabilities, cluster-robust intervals (cluster on lease or pad), bounds with unresolved counted as non-wells and as wells. Arm C yields undocumented wells found per km² searched with its search-sensitivity bounds.

**S7. Feed-forward.**
- Update 5.4 (density sensitivity), 5.6 (record accuracy), 6.3 (labels) and 3.0 reference sets.
- The 5.4 handoff is `src/_field_density_export.py`. It writes `data/processed/arm_b_candidate_outcomes.csv` and `data/processed/arm_c_search_outcomes.csv` in the 5.4 schema, plus two companion files for zero-well cells and detector links.

## 7. Statistical analysis plan
- Primary. Arm A share of drawn features that are confirmed wells, Horvitz-Thompson weights, exact or Wilson interval, bounds for unresolved.
- Interval method (2026-11-06, review F04). Linearisation variance with clusters as PSUs inside the sampling strata, then a Korn-Graubard interval. A sampled stratum with one PSU makes the result inconclusive.
- Secondary. Arm B precision by score band (descriptive unless sized). Arm C wells per km² with sensitivity bounds.
- Era strata always reported separately (magnetometry is blind to wooden or removed casing, per NETL).

## 8. Quality control
- Searcher blinding logged. Coordinates checked against the sampling frame. Duplicates reconciled. Photographs stored.
- No site visited twice by different teams without a record.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Design ready | Partner, permissions, sizing, frame frozen | Execute |
| Success (precision) | Bound width at or under the target | Report the share and use it |
| Not applicable | There is no failure condition for a measurement | |
| Inconclusive | Width over the target | Report bounds. Add sites |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\field_campaign_design.md`, `field_sheet_template.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\<area>\results\field\` sampling files and visit log
- Scripts as named

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| No partner | Plan stays on paper. Everything stays at level (a) |
| Many inaccessible sites | Oversample, report the inaccessible share, bound the result |
| Wooden or removed casing | Non-magnetic evidence for the early stratum |
| Selection toward easy sites | Probability sampling and inclusion probabilities |
| Safety risks near open wells (gas) | Safety plan, methane screening before approach |

## 12. Resources
Design 20 hours. Field effort depends on sites (about 43 to 96 per estimate plus Arm C area search). Partner time, vehicles, instruments. Not estimated without a partner.

## 13. Handoff and open questions
- The partner. The primary estimand. Land access.

## 14. Documentation updates
Design doc, field sheets, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Identity status is separate from outcome. Lower bound is confirmed-well weight over total sampled weight. Upper bound is one minus definite-non-well weight over total. Ambiguous and inaccessible sites sit in the gap. Use inference suited to a weighted, clustered sample.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
