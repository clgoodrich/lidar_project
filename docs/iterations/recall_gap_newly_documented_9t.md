# Recall gap on newly documented wells, tile 9t

**Date:** 2026-11-04
**Script:** `notebooks/wellsight_v2/s5_eval/_recall_gap_newly_documented_9t.py`
**Output:** `data/9t/results/records/record_recall_gap_9t.json`
**Plan item:** A6 in `expansion_gameplan_feasibility.md`

## Goal
Check whether wells that entered the DEP abandoned or orphan inventory after the 2022-05-09 orphan list are detected less often than wells already on that list.

## Inputs
- DEP export April 2026, `data/_source/reference/dep_wells/venango_wells_all.gpkg`. Status in DEP Orphan List, DEP Abandoned List or Abandoned.
- Baseline `data/_source/reference/legacy_data/US_Documented_Orphan_Wells.csv`, Venango rows, keyed on permit number.
- Held-out pit detections and pad polygons as in `record_assoc_pits_9t.md`. Scored footprint is the 115 pit-bearing CV blocks.

## Result
| Outcome | On 2022 list | Newly documented |
|---|---|---|
| Pit detection within 50 m or inside a pad polygon | 22 of 141 (0.156, exact 95% 0.100 to 0.227) | 0 of 6 (exact 95% 0 to 0.459) |
| Difference, new minus old | | -0.156 (Newcombe 95% -0.225 to 0.238) |

## Interpretation
- Six newly documented wells sit in the scored footprint. The interval for that group runs from 0 to 0.46. The data cannot show a gap and cannot rule one out. The result is inconclusive.
- The proxy mixes true new discoveries with reclassifications of wells that were already on the ground. It is not a count of undocumented wells.
- Venango only. Warren and other counties have no dated baseline, so they do not add to this cohort.
- The old group is detected only 16% of the time by pits or pad polygons. That low rate is itself the larger point and matches `record_assoc_pits_9t.md`.

## Not done
- A non-inferiority margin was not set in advance, so no pass or fail is declared.
- Power needs far more newly documented wells inside scored ground. Run it on a larger scored area first.

## Reproduce
`python notebooks/wellsight_v2/s5_eval/_recall_gap_newly_documented_9t.py`
