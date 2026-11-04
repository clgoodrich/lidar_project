# Framework 3.2. Ohio, West Virginia, New York, Kentucky

**Tier B.** Deferred behind 3.1.
**Evidence level.** (a) per county, as case studies.
**Depends on.** 3.0, 3.1 result, P2.

## 1. Problem and objective
Other Appalachian oil states hold old wells in similar terrain with different records and lidar. The question is whether the 9t model carries over and which state programs could use it. One county per state cannot separate a state effect from a county effect, so no between-state variance is estimated.

**Objective.** Per state, a case study with the 3.0 protocol on one or two dense windows, after a desk inventory.

## 2. Scope
In. Inventory, harmonised status table, windows, 3.0 scoring.
Out. Between-state comparison statistics.

## 3. Definitions
- Window. Densest 25 km² cluster of documented orphans in the county (listed).
- Harmonised status. A table mapping each state's status codes to one scheme (active, plugged, abandoned, orphan, other).

## 4. Inputs
| Input | State |
|---|---|
| Well databases NY, KY, OH, WV (and PA) | downloaded (`data/_source/reference/wells_*`) |
| Windows and tile URLs | listed: NY Allegany A17 (11 tiles, 1.15 GB), Cattaraugus A17 (20, 2.12), OH Washington B20 (192, 3.61), Monroe, Noble, Perry; KY Lee C19 (16, 1.68), Powell, Cumberland; WV Pleasants D19 (about 628 tiles over the county, window to compute) |
| Dated old wells | NY (since 1860), KY (completion date) |

## 5. Prerequisites and decisions
3.1 result. Choose one county per state from the inventory. Margin Δ.

## 6. Procedure
1. **Inventory.** `docs/iterations/state_data_inventory.md` per state. Record source, status definitions, coordinate method and accuracy fields, lidar program and dates, access route, licence, spud and completion dates available. Output a table CSV `data/_source/reference/state_inventory_appalachia.csv`.
2. **Status harmonisation.** Script `s1_build/_harmonise_well_status_us.py` (new). Output `data/_source/reference/wells_status_harmonised.csv`.
3. **County choice.** Highest feature candidate, public lidar since 2015, dated records available. One county per state. Write the rule in the preregistration.
4. **Measure ground density** on one tile per window (PDAL CLI). Compare with 9t (2.70 points per m²). Stop if far below.
5. **Fetch window** (gated). From `lidar_download_list_pilot_5km_us.csv`. Hash.
6. **Build 0.5 m derivatives with the 9t code, infer, annotate** as in 3.1 (blind, complete blocks), **score with 3.0**.
7. **Report per state as a case study** with recall at K = 40 per km², density, and the interval.
Note. Ohio 2006 and 2007 projects use about 3 MB tiles and likely have very low density. Use the 2020 statewide project.

## 7. Statistical analysis plan
Per case study as 3.1. No pooled statistic across states. Optional descriptive table.

## 8. Quality control
As 3.0 and 3.1. Check coordinate datum per state.

## 9. Gates
Per case study as 3.1. Inconclusive is expected for small windows.

## 10. Deliverables
Per state docs `transfer_<state>_9t_model.md` and `data/<county>/results/transfer/`.

## 11. Failure modes
Record schema differences. Restricted data. Leaf-off timing. Low density.

## 12. Resources
Inventory 10 hours per state. Each case study resembles 3.1 (annotation dominates).

## 13. Handoff and open questions
County per state. Reviewers.

## 14. Documentation updates
Inventory doc, per-state docs, master plan.
