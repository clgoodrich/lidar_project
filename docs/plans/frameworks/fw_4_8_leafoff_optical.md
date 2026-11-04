# Framework 4.8. Leaf-off optical imagery

**Tier B.** Coverage probe.
**Evidence level.** (a) and (b).
**Depends on.** None.

## 1. Problem and objective
Leaf-off aerial imagery can show bare ground, roads and pads under deciduous cover. How much of the study areas has usable leaf-off imagery is unknown. An earlier chip check reported that 10 of 13 chips were blank (reported by a review, not re-checked).

**Objective.** A coverage table and a small chip status table that separates unavailable or blank chips from genuine non-detection, with visible-ground fraction.

## 2. Scope
In. Coverage by program and date, georegistration check, chip sample.
Out. Training an optical model.

## 3. Definitions
- **Usable chip.** Valid date in leaf-off months, georegistered within 5 m, visible ground fraction above a preregistered level.
- **Chip status.** One of usable, blank, cloud or shadow, off-season, unregistered, unavailable.

## 4. Inputs
| Input | State |
|---|---|
| Annotated features 9t | held |
| State orthophotos (PASDA PAMAP and others), NAIP | metadata search (D7, D10) |
| Earlier chip scripts | `data/9t/results/pit/photo/`, `pit_leafoff_chip_288_9t.png` | held |

## 5. Prerequisites and decisions
Sample size and the visible-ground cutoff set before looking.

## 6. Procedure
1. **Coverage table** `docs/iterations/leafoff_coverage_probe.md`. Programs, dates, season, resolution, access method, for 9t and Warren.
2. **Chip sample.** Script `s5_eval/_leafoff_chip_status_9t.py` (new). Draw 60 annotated features at random (seed in the preregistration). Pull chips through a map service or tile download. Record status per chip. Output `data/9t/results/optical/leafoff_chip_status_9t.csv`.
3. **Georegistration check.** Measure offset on 10 road intersections per source.
4. **Visible ground fraction.** Segment bare ground from imagery (excess-green threshold plus brightness) on each chip. Record the fraction.
5. **Interpretability.** Two reviewers judge whether a feature is visible (yes, no, cannot tell) blind to lidar.
6. **Fetch full imagery** only if usable share is high (D10).

## 7. Statistical analysis plan
Proportions with exact intervals. Agreement between reviewers. Absence in imagery is not rejection of a feature.

## 8. Quality control
Dates verified. Offsets documented. Blank chips never counted as negatives.

## 9. Gates
Usable share above the preregistered level (say 60%) means fetch D10. Below means the source is unusable here. Else inconclusive.

## 10. Deliverables
Coverage doc, chip table, `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\optical\`.

## 11. Failure modes
Evergreen cover. Registration offsets. Service limits.

## 12. Resources
10 hours. Small downloads.

## 13. Handoff
Reviewers for interpretability.

## 14. Documentation updates
Coverage doc, `analysis_log.md`, master plan.
