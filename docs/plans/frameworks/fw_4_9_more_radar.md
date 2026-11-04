# Framework 4.9. More radar (scope note only)

**Tier B.** A write-up. No new experiment until a new rationale exists.
**Evidence level.** Scope-limited negative evidence.

## 1. Problem and objective
The tested NISAR radar features did not add to detection. The risk is over-reading that as "radar fails". The risk the other way is repeating the same test.

**Objective.** A scope note that states exactly what was tested and found, what was not, and what would count as a genuinely different test.

## 2. Scope
In. The note, a list of untested signals, a rule for starting new radar work.
Out. New radar processing.

## 3. Definitions
- **Tested.** NISAR L-band products over tiles 9t and 613590, with the feature set in `s5_eval/_nisar_feat_*`. Results after de-duplicating decoys.
- **Result.** Gain of -0.004 for pits and -0.008 for pads (AUC) on 9t. On 613590 held-out pits the gain is -0.017 with every resampling giving an upper 95% bound of +0.018 or less, so +0.05 is excluded. Pad evidence is 9t only. On 9t pits, "no gain" and "no room" cannot be told apart because the lidar baseline AUC is already 0.968.

## 4. Inputs
`data/9t/results/nisar/nisar_pit_dedupe_auc_9t_slc.csv`, `nisar_pad_dedupe_auc_9t_slc_local1500.csv`, `docs/iterations/outside_review_response_20261103.md`, `nisar_checks_9t.md`, `nisar_writeup/README.md`.

## 5. Prerequisites and decisions
None.

## 6. Procedure
1. Write `docs/iterations/radar_scope_note.md`. Sections. What was tested (products, features, areas, targets). Results with intervals and the ceiling caveat. What was not tested (other wavelengths, polarimetry, time-series displacement, different applications such as steel detection or road change). The rule. A new radar experiment needs a new written rationale and a preregistration before data are fetched.
2. Add a pointer from the NISAR write-up.
3. List untested signals with the reason each might differ, without running anything.

## 7. Statistical analysis plan
None. Quote existing intervals with source files.

## 8. Quality control
Every number traced to a saved CSV.

## 9. Gates
The note is committed and cited from the NISAR write-up.

## 10. Deliverables
`C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\radar_scope_note.md`.

## 11. Failure modes
Overstatement. Do not claim that every coarse sensor fails.

## 12. Resources
3 hours.

## 13. Handoff
None.

## 14. Documentation updates
Note, `analysis_log.md`, master plan.
