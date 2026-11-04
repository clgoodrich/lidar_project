# 3.2 Ohio, West Virginia, New York, Kentucky

**Problem.** Other Appalachian oil states have orphaned wells in similar terrain. Their records, status definitions and lidar differ. It is unknown how much of the model carries over.

**Why it matters.** It shows how far the approach reaches and which state programs could use it.

**Evidence level produced.** (a) per county. Treat results as case studies. One county per state cannot separate a state effect from county differences.

**Inputs.** State well inventories and lidar programs. Coverage and access are **unverified** for each state.

**Architecture.**
1. `docs/iterations/state_data_inventory.md`. One table row per state with record source, status definitions, coordinate method, lidar program, acquisition dates, access route.
2. One county per state, chosen by data availability and well density, recorded in a prereg per county.
3. Reuse plan 3.0 scripts per county.
4. `data/<county>/results/transfer/` for outputs.

**Method outline.** Harmonise status labels into one table before comparison. Record survey dates and coordinate accuracy. Keep eligibility rules identical across counties.

**Acceptance test.** A harmonised status table exists. Each county has a committed prereg before scoring.

**Risks and unknowns.** Record schemas differ. Some inventories may be restricted. Lidar leaf-off timing varies.

**Depends on.** 3.0, 3.1.

**Executor notes.** One county at a time. Do not pool counties into one statistic.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Desk inventory table only (record source, status definitions, coordinate method, lidar program, dates, access). One county per state cannot separate state from county effects, so report case studies, never a between-state variance.

**Downloads and requests.** D14 gated on the inventory.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

One county per state is a case study. The Ohio 2006 and 2007 projects use about 3 MB tiles, which points to very low density. Use the 2020 statewide project.

| State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB | Centre lon, lat |
|---|---|---|---|---|---|---|---|
| New York | Allegany | 1049 | NY_SouthwestNY_2017_A17 | 2017 | 11 | 1.15 | -78.0728, 42.079 |
| New York | Cattaraugus | 991 | NY_SouthwestNY_2017_A17 | 2017 | 20 | 2.12 | -78.5102, 42.0141 |
| Kentucky | Lee | 635 | KY_WestCentral_2017_C19 | 2017 | 16 | 1.68 | -83.7161, 37.6816 |
| Kentucky | Powell | 425 | KY_WestCentral_2017_C19 | 2017 | 20 | 2.03 | -83.7196, 37.7407 |
| Ohio | Washington | 413 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.61 | -81.4441, 39.6036 |
| Ohio | Perry | 258 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 4.19 | -82.0806, 39.5847 |
| Ohio | Monroe | 198 | OH_Statewide_Phase2_2020_B20 | 2020 | 186 | 4.06 | -81.1571, 39.6965 |
| Ohio | Noble | 193 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.67 | -81.4523, 39.6487 |
| Kentucky | Estill | 184 | KY_WestCentral_2017_C19 | 2017 | 20 | 1.43 | -83.8954, 37.7333 |
| Ohio | Licking | 161 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.01 | -82.368, 40.0188 |
| Ohio | Jefferson | 130 | OH_Statewide_Phase2_2020_B20 | 2020 | 196 | 3.65 | -80.6945, 40.5119 |
| Ohio | Columbiana | 127 | OH_Statewide_Phase2_2020_B20 | 2020 | 200 | 2.39 | -81.0371, 40.8694 |
| Kentucky | Cumberland | 120 | KY_CentralEast_A23 | 2024 | 20 | 2.1 | -85.4217, 36.6524 |
| Kentucky | Ohio | 115 | KY_WesternKY_A22 | 2023 | 20 | 2.8 | -86.9065, 37.559 |
| Kentucky | Clinton | 89 | KY_CentralEast_A23 | 2024 | 16 | 1.5 | -85.1928, 36.8012 |
| West Virginia | Pleasants | 49 | OH_Statewide_Phase2_2020_B20 | 2020 | 19 | 0.17 | -81.2344, 39.3705 |
| Tennessee | Overton | 34 | TN_27_County_QL2_LiDAR_Cumberland_Plateau_BAA | 2023 | 17 | 1.54 | -85.1976, 36.4202 |
