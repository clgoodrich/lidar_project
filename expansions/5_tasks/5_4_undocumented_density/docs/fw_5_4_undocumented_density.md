# Framework 5.4. Undocumented well density (identifiability)

**Tier B.** An identifiability analysis only. No density map.
**Evidence level.** An estimate under stated assumptions. Not a count.
**Depends on.** 5.6 (corrected), R1, 7.5.

## 1. Problem and objective
How many wells exist that no record lists is unknown. Detector output alone cannot answer it.

**Objective.** State which quantities are identified, which are not, and what sensitivity range follows. Do not publish a density surface.

## 2. Scope
In. Equation, unit definition, sensitivity grid, requirements for identification.
Out. Any density map or total.

## 3. Definitions
- **Counting unit.** A well. Not a blob, not a pad.
- **D.** Distinct candidates in the eligible footprint.
- **p.** Well-level precision, the probability a candidate is a well.
- **r.** Well-level recall, the probability a well in the eligible population yields a candidate.
- **Total wells.** D p over r. **Missed by the detector.** D p (1 minus r) over r. **Undocumented.** Total minus the complete documented population in the same unit.
- The equation is valid only when D p counts distinct true wells in the candidate population, r concerns the same eligible well population, multi-feature and multi-well relations are resolved, and documentation and acquisition scope align.

## 4. Inputs
| Input | State |
|---|---|
| Candidates, annotated features | held |
| DEP records, status, dates | held |
| Corrected 5.6 outputs | future |
| Field precision (7.5 Arm B) and bounds on recall (Arm C) | future |

## 5. Prerequisites and decisions
Well-level precision and recall estimates need field data. The recall-gap result is withdrawn (its input dropped matched detections and mixed cohort coordinate quality).

## 6. Procedure
1. **Identifiability note** `docs/iterations/density_identifiability.md`. Write the equation, the assumptions, and a table of each term with its current evidence and what would identify it.
2. **Sensitivity grid.** Script `s5_eval/_density_sensitivity_9t.py` (new). D from the 9t candidate count at K = 40 per km². p from 0.05 to 0.9 and r from 0.1 to 0.9. Output the implied total, missed and undocumented counts for the 9t footprint and the DEP complete population. File `data/9t/results/density/density_sensitivity_9t.csv` and a heat map (sequential single hue, labelled).
3. **Bounds.** If r can approach 0 the total has no finite upper bound. State it.
4. **Cohort association redo.** After 5.6 is corrected, compare newly documented against previously documented wells using normalised excess over cohort-specific nulls, stratified by DEP coordinate source. Descriptive only. It gives no recall-equivalence gate and no density input until verified denominators and coordinate error exist.
5. **Capture-recapture (diagnostic).** Describe a two-source (records and detector) estimate and its independence assumptions. It is not automatically a lower bound.

## 7. Statistical analysis plan
Sensitivity and bounds. Intervals only after field data. Newcombe or exact for cohort differences.

## 8. Quality control
Every number from a saved file. Unit counting checked (blob to well resolution).

## 9. Gates
Not a pass-fail. Output is a clear statement of what is identified. A density map is not allowed until p and r have defensible bounds.

## 10. Deliverables
`C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\density_identifiability.md`, `data\9t\results\density\`.

## 11. Failure modes
Misuse of the sensitivity grid as an estimate. Label it as sensitivity.

## 12. Resources
10 hours. No GPU.

## 13. Handoff
Needs 7.5 and R1.

## 14. Documentation updates
Identifiability doc, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Write distinct-well accounting and show bounds as recall varies. No density gate from spatial excess alone.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
