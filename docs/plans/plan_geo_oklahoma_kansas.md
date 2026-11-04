# 3.5 Oklahoma and Kansas

**Problem.** Large orphan inventories sit in open terrain with active infrastructure. Lidar, optical and fusion approaches have not been compared there.

**Why it matters.** It tests whether combining modalities helps where lidar alone is weak.

**Evidence level produced.** (a) per modality.

**Inputs.** State well records and public lidar and optical imagery (all **unverified**).

**Architecture.**
1. `docs/iterations/okks_data_inventory.md` lists records, lidar, optical, dates.
2. One shared site list and one spatial split used by all three arms (lidar, optical, fusion).
3. Matched label budgets and tuning effort across arms, recorded in the prereg.
4. `_modality_compare.py` scores the three arms on identical sites.
5. Missingness and active-infrastructure confounding tables.

**Method outline.** Identical sites, splits and effort. Report modality-specific missing data.

**Acceptance test.** Three arms scored on the same test blocks with paired differences and intervals.

**Risks and unknowns.** Substantial data engineering. Active infrastructure may look like abandoned sites.

**Depends on.** 3.0.

**Executor notes.** Do not tune one arm harder than the others.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Optical and fusion arms need target-area labels. Matched effort is not measurable as written. Coverage and temporal-eligibility table only.

**Downloads and requests.** None until the inventory exists.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

Kansas statewide tiles are large (about 400 MB each) and few cover a window.

| State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB | Centre lon, lat |
|---|---|---|---|---|---|---|---|
| Kansas | Neosho | 225 | KS_Statewide_2018_A18 | 2018 | 4 | 1.46 | -95.1957, 37.5779 |
| Missouri | Jackson | 225 | KS_JACKSONCO_2006 | 2006 | 36 | 0.45 | -94.5806, 38.9068 |
| Oklahoma | Rogers | 174 | OK_Statewide_D22 | 2024 | 18 | 1.35 | -95.5234, 36.5728 |
| Kansas | Montgomery | 163 | KS_Statewide_2018_A18 | 2018 | 4 | 2.39 | -95.9238, 37.1027 |
| Oklahoma | Okmulgee | 143 | OK_Statewide_D22 | 2024 | 19 | 1.21 | -95.8188, 35.6416 |
| Oklahoma | Washington | 136 | OK_Statewide_D22 | 2024 | 16 | 1.31 | -95.9573, 36.866 |
| Missouri | Cass | 125 | MO_WestCentral_2018_D19 | 2018 | 16 | 0.71 | -94.579, 38.8198 |
| Oklahoma | Nowata | 122 | FEMA_R6_OK_Craig_Nowata_QL2_Lidar | 2023 | 19 | 0.51 | -95.6573, 36.7636 |
| Kansas | Labette | 102 | KS_Statewide_2018_A18 | 2018 | 4 | 1.58 | -95.4691, 37.2449 |
| Oklahoma | Kay | 91 | OK_Statewide_D22 | 2024 | 16 | 1.52 | -97.1957, 36.9495 |
| Oklahoma | Muskogee | 87 | OK_ArkansasCacheLCimarron_D25 | 2026 | 76 | 1.53 | -95.6936, 35.7158 |
| Oklahoma | Tulsa | 73 | OK_Statewide_D22 | 2024 | 11 | 1.13 | -95.8425, 35.8932 |
| Oklahoma | Pawnee | 71 | OK_Statewide_D22 | 2024 | 16 | 2.12 | -96.6727, 36.2276 |
| Oklahoma | Creek | 61 | OK_Statewide_D22 | 2024 | 20 | 1.95 | -96.2885, 35.8882 |
