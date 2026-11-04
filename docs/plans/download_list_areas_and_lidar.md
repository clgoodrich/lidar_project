# Download list. Areas with many old wells, and the lidar that covers them

> **Caveat from the third review (2026-11-04).** This list is for discovery. The cover figures are tile-count ratios, not area covered. The listing scripts do not paginate (max 200 per query), return an empty result after repeated failure, and drop duplicate URLs across windows. Repair these and verify union coverage from tile geometries before any total becomes a download budget. See protocol section 16 item 5 and `docs/iterations/BACKLOG.md`.

**Date:** 2026-11-04
**Status:** well databases are downloaded. Lidar is **listed only**. No point cloud has been downloaded. Sizes come from the USGS catalogue API and the files themselves.
Extends `download_manifest.md` (items D11, D13, D14, D15 now point here).

## 1. How this list was made
1. **Well databases first.** The USGS Documented Unplugged Orphaned Oil and Gas Well Dataset (2022 release, 117,672 wells, 27 states) gives a county count of documented orphans. I joined it to Census county areas to get a density per km².
2. **Old wells.** That database holds no spud dates. Where a state database holds dates (New York, Kentucky) I counted wells completed before 1930. Dated records are sparse, so these are floors, not totals.
3. **Lidar next.** For every county in the ranking, the USGS National Map (TNM) Access API listed the 3DEP lidar point cloud projects that cover it. I also found the densest 5 km by 5 km cluster of orphan wells in each county, and listed the exact tiles that cover that 25 km² window. 25 km² is close to tile 9t (20 km²).
4. **Nothing was fetched except metadata and well databases.**

Scripts, all in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\`
- `_fetch_well_databases_multi.py` and `_fetch_arcgis_wells_paged.py` (well databases)
- `_list_lidar_by_county_us.py` (projects per county)
- `_list_lidar_pilot_windows_us.py` (tile lists for the densest window)

## 2. Where the old wells are
Documented orphans per county, top 30 of the 2022 release. Venango (our tile) is first, and its 4,786 matches the count already held locally.

| State | County | Documented orphans | km² | Per km² |
|---|---|---|---|---|
| Pennsylvania | Venango | 4786 | 1770 | 2.7 |
| Pennsylvania | McKean | 3299 | 2549 | 1.29 |
| New York | Allegany | 3047 | 2679 | 1.14 |
| Ohio | Washington | 2786 | 1657 | 1.68 |
| Pennsylvania | Warren | 2338 | 2329 | 1.0 |
| Ohio | Monroe | 1996 | 1186 | 1.68 |
| Oklahoma | Okmulgee | 1845 | 1819 | 1.01 |
| Missouri | Jackson | 1711 | 1597 | 1.07 |
| New York | Cattaraugus | 1640 | 3424 | 0.48 |
| Oklahoma | Washington | 1544 | 1099 | 1.4 |
| California | Los Angeles | 1398 | 10608 | 0.13 |
| Oklahoma | Nowata | 1343 | 1504 | 0.89 |
| Ohio | Licking | 1277 | 1782 | 0.72 |
| Ohio | Noble | 1209 | 1048 | 1.15 |
| Pennsylvania | Forest | 1175 | 1113 | 1.06 |
| Oklahoma | Creek | 1173 | 2510 | 0.47 |
| Pennsylvania | Washington | 1167 | 2229 | 0.52 |
| Louisiana | Caddo | 1116 | 2422 | 0.46 |
| Kansas | Montgomery | 1102 | 1686 | 0.65 |
| Illinois | Marion | 1097 | 1493 | 0.73 |
| Kentucky | Lee | 961 | 548 | 1.75 |
| Oklahoma | Kay | 954 | 2445 | 0.39 |
| Oklahoma | Rogers | 887 | 1843 | 0.48 |
| Illinois | Crawford | 882 | 1154 | 0.76 |
| Pennsylvania | Butler | 866 | 2062 | 0.42 |
| Oklahoma | Tulsa | 865 | 1520 | 0.57 |
| Ohio | Perry | 856 | 1061 | 0.81 |
| Kansas | Labette | 794 | 1693 | 0.47 |
| Wyoming | Campbell | 791 | 12448 | 0.06 |
| Kentucky | Cumberland | 777 | 804 | 0.97 |

Full table, all counties, with bounding boxes. `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\reference\wells_us_orphan_2022\area_orphan_counts_by_county_us.csv`

**Read this table with care**
- A count of documented orphans shows where a state has compiled a list. It is not a count of old wells. Ohio and Pennsylvania compile large lists. Los Angeles County has a large urban area, so its density is diluted.
- Four regions stand out. **Appalachian oil region** (northwest Pennsylvania, southwest New York, southeast Ohio, eastern Kentucky, West Virginia). **Mid-continent** (Oklahoma, Kansas, southern Illinois, Missouri). **Gulf** (Louisiana, Texas). **West** (California and others, lower density).
- Only the Appalachian region holds wells from the 1860s. The Mid-continent fields date mostly from the 1900s to 1920s.

Completed before 1930, from the state databases that carry dates. Only dated records count, so true numbers are higher.

| State | County | Wells in database | With a date | Completed before 1930 | Before 1900 |
|---|---|---|---|---|---|
| Kentucky | FLOYD | 4089 | 3012 | 645 | 1 |
| New York | Erie | 3504 | 2571 | 624 | 35 |
| Kentucky | LAWRENCE | 3998 | 2228 | 444 | 1 |
| Kentucky | JOHNSON | 3784 | 1749 | 442 | 0 |
| Kentucky | LEE | 6387 | 3603 | 393 | 0 |
| New York | Cattaraugus | 11981 | 5682 | 296 | 36 |
| New York | Chautauqua | 6367 | 5453 | 248 | 1 |
| Kentucky | MAGOFFIN | 5322 | 2575 | 230 | 0 |
| New York | Allegany | 16449 | 3053 | 227 | 9 |
| Kentucky | BOYD | 420 | 282 | 145 | 0 |
| New York | Genesee | 880 | 795 | 139 | 7 |
| Kentucky | MARTIN | 2231 | 1745 | 137 | 9 |
| Kentucky | OHIO | 6287 | 3431 | 135 | 0 |
| New York | Onondaga | 295 | 243 | 114 | 67 |

Source files. `wells_ny_dec` and `wells_ky_kgs` below. Table at `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\reference\wells_us_orphan_2022\area_old_well_counts_ny_ky.csv`. Illinois has 30,872 wells completed before 1930 in the ISGS file, but that file has no county column, so it is not broken down here.

## 3. Well databases already downloaded
These are small and public. Files over 100 MB were not fetched. Zips are ignored by git. The ledger is at `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\_download_ledger.csv`.

| Folder under data/_source/reference/ | File | MB | Rows | Accessed | SHA-256 (first 10) |
|---|---|---|---|---|---|
| wells_il_isgs | IL_WELLS_Borings_Location_Pt.zip | 21.5 |  | 2026-11-04 | dc3d2b6ea5 |
| wells_ks_kgs | ks_kgs_oil_gas_wells.csv.gz | 67.3 | 519749 | 2026-11-04 | 7af50f3a32 |
| wells_ky_kgs | kyog_dd.zip | 17.0 |  | 2026-11-04 | c87ca3311d |
| wells_ky_kgs | kyog_info.txt | 0.0 |  | 2026-11-04 | 11d1be9b26 |
| wells_ny_dec | ny_oil_gas_regulated_wells_since_1860.csv | 22.6 |  | 2026-11-04 | 74b9f6d153 |
| wells_ny_dec | ny_orphaned_wells.csv | 0.9 |  | 2026-11-04 | 901be66511 |
| wells_oh_odnr | oh_odnr_wells.csv.gz | 19.4 | 238601 | 2026-11-04 | 164e5a0ddb |
| wells_ok_occ | RBDMS_WELLS.zip | 45.9 |  | 2026-11-04 | 563aecedd1 |
| wells_ok_occ | orphan-well-list.xlsx | 2.3 |  | 2026-11-04 | 659b93c36f |
| wells_ok_occ | orphan-wells-data-dictionary.xlsx | 0.0 |  | 2026-11-04 | 19ba20dd52 |
| wells_ok_occ | rbdms-wells-data-dictionary.xlsx | 0.0 |  | 2026-11-04 | 87f249f0c6 |
| wells_us_orphan_2022 | US_orphaned_wells.csv | 22.2 |  | 2026-11-04 | 231ba0154d |
| wells_us_orphan_2022 | US_orphaned_wells.xml | 0.1 |  | 2026-11-04 | d293b94c8f |
| wells_us_orphan_2026 | US_orphaned_wells_2026.xml | 0.1 |  | 2026-11-04 | 196f39dc27 |
| wells_wv_dep | wv_dep_all_wells.csv.gz | 13.6 | 154254 | 2026-11-04 | b82ba36d40 |

**Not downloadable by script, or not yet fetched**
| Source | What | Status |
|---|---|---|
| USGS Documented Orphaned Well Database **2026**, doi:10.5066/P13FHBYG | 130,121 wells, 28 states, with ownership | The CSV and XLSX are flagged unpublished on ScienceBase and S3 refuses access. **Download by hand** from the DOI page. Only its metadata XML is here |
| Ohio ODNR | Statewide wells | Paged from the ODNR service (see table). An official bulk county export may carry more fields |
| Pennsylvania DEP | Statewide export | Only Venango is held. Fetch the statewide export from PASDA when a second county is needed |
| Texas RRC | Orphan layer 2 and reliability fields | Documented in memory. Fetch when 3.4 is un-deferred |
| California CalGEM, Michigan EGLE, Louisiana SONRIS, Alaska AOGCC | State databases | Not searched. Deferred with their plans |
| Alberta AER, Ontario OGSR, British Columbia | Provincial databases | Not searched. Coverage and terms **unverified** |

## 4. Lidar list for the densest 25 km² window in each county
`51` windows, `3116` tiles, `126.4` GB if every listed project were fetched. Only the newest project per window is recommended, which is much smaller (section 5).

Files, all under `C:\Users\colto\Documents\GitHub\lidar_project\data\_source\reference\lidar_catalogue\`
- `lidar_download_list_pilot_5km_us.csv`. **The download list.** One row per tile with state, county, project, tile name, MB, publication date and URL.
- `lidar_pilot_windows_us.csv`. The window for each county, centre and bounding box.
- `lidar_pilot_windows_summary_us.csv`. The table below, with every project.
- `lidar_projects_by_county_us.csv`. Every project that covers each county, with whole-county tile counts and size upper bounds.

Recommended project per window. The newest by year guess among projects that cover at least half of the window's tiles. A newer project that covers only a corner is listed under alternates.

| Region | State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB for window | Whole county GB (upper) | Lon | Lat |
|---|---|---|---|---|---|---|---|---|---|---|
| Appalachian | New York | Allegany | 1049 | NY_SouthwestNY_2017_A17 | 2017 | 11 | 1.15 | 47 | -78.0728 | 42.079 |
| Appalachian | New York | Cattaraugus | 991 | NY_SouthwestNY_2017_A17 | 2017 | 20 | 2.12 | 101 | -78.5102 | 42.0141 |
| West | California | Los Angeles | 832 | CA_LosAngeles_B23 | 2025 | 35 | 2.9 | 836 | -118.2653 | 34.0608 |
| Appalachian | Pennsylvania | Venango | 782 | PA_WesternPA_2019_D20 | 2019 | 20 | 0.81 | 81 | -79.538 | 41.5056 |
| Mid-continent | Illinois | Cumberland | 751 | IL_8County_2020_A20 | 2020 | 80 | 3.61 | 136 | -88.032 | 39.3163 |
| Appalachian | Kentucky | Lee | 635 | KY_WestCentral_2017_C19 | 2017 | 16 | 1.68 | 37 | -83.7161 | 37.6816 |
| Appalachian | Pennsylvania | McKean | 597 | PA_Northcentral_2019_B19 | 2019 | 36 | 2.11 | 221 | -78.5524 | 41.9725 |
| Mid-continent | Illinois | Marion | 548 | IL_SouthCentral_2021_D21 | 2021 | 80 | 2.56 | 45 | -89.0027 | 38.5838 |
| Appalachian | Pennsylvania | Forest | 548 | PA_WesternPA_2019_D20 | 2019 | 20 | 0.91 | 55 | -79.4834 | 41.5605 |
| Appalachian | Pennsylvania | Warren | 500 | PA_WesternPA_2019_D20 | 2019 | 15 | 0.79 | 69 | -79.0553 | 41.7768 |
| Appalachian | Kentucky | Powell | 425 | KY_WestCentral_2017_C19 | 2017 | 20 | 2.03 | 30 | -83.7196 | 37.7407 |
| Appalachian | Ohio | Washington | 413 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.61 | 665 | -81.4441 | 39.6036 |
| Appalachian | Ohio | Perry | 258 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 4.19 | 376 | -82.0806 | 39.5847 |
| Mid-continent | Kansas | Neosho | 225 | KS_Statewide_2018_A18 | 2018 | 4 | 1.46 | 29 | -95.1957 | 37.5779 |
| Mid-continent | Missouri | Jackson | 225 | KS_JACKSONCO_2006 | 2006 | 36 | 0.45 | 17 | -94.5806 | 38.9068 |
| Appalachian | Ohio | Monroe | 198 | OH_Statewide_Phase2_2020_B20 | 2020 | 186 | 4.06 | 202 | -81.1571 | 39.6965 |
| Appalachian | Ohio | Noble | 193 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.67 | 322 | -81.4523 | 39.6487 |
| Appalachian | Kentucky | Estill | 184 | KY_WestCentral_2017_C19 | 2017 | 20 | 1.43 | 34 | -83.8954 | 37.7333 |
| Mid-continent | Oklahoma | Rogers | 174 | OK_Statewide_D22 | 2024 | 18 | 1.35 | 42 | -95.5234 | 36.5728 |
| Mid-continent | Illinois | Crawford | 172 | IL_8County_2020_A20 | 2020 | 111 | 2.57 | 80 | -87.9286 | 39.1525 |
| Mid-continent | Kansas | Montgomery | 163 | KS_Statewide_2018_A18 | 2018 | 4 | 2.39 | 46 | -95.9238 | 37.1027 |
| Appalachian | Ohio | Licking | 161 | OH_Statewide_Phase2_2020_B20 | 2020 | 192 | 3.01 | 183 | -82.368 | 40.0188 |
| Mid-continent | Oklahoma | Okmulgee | 143 | OK_Statewide_D22 | 2024 | 19 | 1.21 | 89 | -95.8188 | 35.6416 |
| Gulf | Louisiana | Caddo | 142 | LA_Sabine_River_Lidar_2018_D18 | 2018 | 36 | 7.69 | 842 | -93.9433 | 32.7439 |
| Mid-continent | Oklahoma | Washington | 136 | OK_Statewide_D22 | 2024 | 16 | 1.31 | 46 | -95.9573 | 36.866 |
| Appalachian | Ohio | Jefferson | 130 | OH_Statewide_Phase2_2020_B20 | 2020 | 196 | 3.65 | 202 | -80.6945 | 40.5119 |
| West | New Mexico | Chaves | 130 | NM_SouthEast_2018_D19 | 2018 | 17 | 0.38 | 370 | -103.8692 | 33.6256 |
| Appalachian | Ohio | Columbiana | 127 | OH_Statewide_Phase2_2020_B20 | 2020 | 200 | 2.39 | 198 | -81.0371 | 40.8694 |
| Mid-continent | Missouri | Cass | 125 | MO_WestCentral_2018_D19 | 2018 | 16 | 0.71 | 33 | -94.579 | 38.8198 |
| Mid-continent | Oklahoma | Nowata | 122 | FEMA_R6_OK_Craig_Nowata_QL2_Lidar | 2023 | 19 | 0.51 | 18 | -95.6573 | 36.7636 |
| Appalachian | Kentucky | Cumberland | 120 | KY_CentralEast_A23 | 2024 | 20 | 2.1 | 61 | -85.4217 | 36.6524 |
| Appalachian | Kentucky | Ohio | 115 | KY_WesternKY_A22 | 2023 | 20 | 2.8 | 103 | -86.9065 | 37.559 |
| West | Wyoming | Campbell | 108 | WY_North_Converse_2020_D20 | 2020 | 42 | 0.99 | 155 | -105.6267 | 44.3713 |
| Appalachian | Pennsylvania | Butler | 104 | PA_WesternPA_2019_D20 | 2019 | 20 | 1.31 | 67 | -79.8062 | 40.998 |
| Mid-continent | Kansas | Labette | 102 | KS_Statewide_2018_A18 | 2018 | 4 | 1.58 | 34 | -95.4691 | 37.2449 |
| Gulf | Texas | Pecos | 95 | TX_WestTexas_2018_D19 | 2018 | 24 | 2.35 | 1215 | -102.8184 | 31.2363 |
| Mid-continent | Oklahoma | Kay | 91 | OK_Statewide_D22 | 2024 | 16 | 1.52 | 66 | -97.1957 | 36.9495 |
| Appalachian | Kentucky | Clinton | 89 | KY_CentralEast_A23 | 2024 | 16 | 1.5 | 34 | -85.1928 | 36.8012 |
| Mid-continent | Oklahoma | Muskogee | 87 | OK_ArkansasCacheLCimarron_D25 | 2026 | 76 | 1.53 | 151 | -95.6936 | 35.7158 |
| Gulf | Arkansas | Ouachita | 85 | AR_Ouachita_FEMA_R6_Lidar_2016_D17 | 2016 | 16 | 1.19 | 99 | -93.0892 | 33.4073 |
| Appalachian | Pennsylvania | Washington | 75 | PA_WesternPA_2019_D20 | 2019 | 20 | 4.2 | 224 | -80.3458 | 40.1658 |
| Mid-continent | Oklahoma | Tulsa | 73 | OK_Statewide_D22 | 2024 | 11 | 1.13 | 40 | -95.8425 | 35.8932 |
| Mid-continent | Oklahoma | Pawnee | 71 | OK_Statewide_D22 | 2024 | 16 | 2.12 | 105 | -96.6727 | 36.2276 |
| Great Lakes | Michigan | Charlevoix | 67 | MI_CharlevoixCounty_2018_A18 | 2018 | 56 | 0.92 | 120 | -84.7963 | 45.155 |
| Mid-continent | Oklahoma | Creek | 61 | OK_Statewide_D22 | 2024 | 20 | 1.95 | 128 | -96.2885 | 35.8882 |
| Appalachian | West Virginia | Pleasants | 49 | OH_Statewide_Phase2_2020_B20 | 2020 | 19 | 0.17 | 30 | -81.2344 | 39.3705 |
| Appalachian | Tennessee | Overton | 34 | TN_27_County_QL2_LiDAR_Cumberland_Plateau_BAA | 2023 | 17 | 1.54 | 77 | -85.1976 | 36.4202 |
| West | Colorado | Logan | 26 | CO_NESEColorado_2019_C20 | 2019 | 42 | 1.99 | 179 | -103.3464 | 40.682 |
| Mid-continent | Indiana | Rush | 15 | IN_Indiana_Statewide_LiDAR_2017_B17 | 2017 | 20 | 0.57 | 15 | -85.6024 | 39.6431 |
| West | Nebraska | Cheyenne | 12 | NE_Statewide_D23 | 2024 | 32 | 7.47 | 781 | -103.0132 | 41.1929 |
| West | North Dakota | McKenzie | 9 | ND McKenzieCo 2014 | 2014 | 25 | 0.35 | 0 | -102.8017 | 48.0135 |

**Columns.** Year is the year in the project name, or the publication year if the name has none. Publication date is not flight date. Whole county GB is an upper bound because it counts tiles in the county's bounding box and a tile size is the mean of 100 sampled tiles.

Older or alternate projects over the same windows.

| State | County | Older or alternate project | Year (guess) | Tiles | GB |
|---|---|---|---|---|---|
| New York | Allegany | NY_Southwest_2_County_2016_A16 | 2016 | 16 | 2.46 |
| California | Los Angeles | CA LosAngeles 2016 L4 | 2016 | 48 | 0.7 |
| Pennsylvania | Venango | PA_STATEWIDE_N_2006_2008 | 2006 | 6 | 0.47 |
| Kentucky | Lee | KY_CentralEast_A23 | 2024 | 2 | 0.25 |
| Pennsylvania | McKean | PA_STATEWIDE_N_2006_2008 | 2006 | 6 | 0.39 |
| Illinois | Marion | IL_5_County_2014_15 | 2014 | 87 | 0.3 |
| Pennsylvania | Forest | PA_STATEWIDE_N_2006_2008 | 2006 | 6 | 0.49 |
| Pennsylvania | Warren | PA_STATEWIDE_N_2006_2008 | 2006 | 6 | 0.47 |
| Ohio | Washington | OH_SOUTH_2007 | 2007 | 20 | 0.07 |
| Ohio | Perry | OH_SOUTH_2007 | 2007 | 15 | 0.06 |
| Missouri | Jackson | MO_FEMANRCS_2020_D20 | 2020 | 16 | 0.94 |
| Missouri | Jackson | MO_WestCentral_2018_D19 | 2018 | 6 | 0.21 |
| Kansas | Neosho | Kansas_2013_LiDAR | 2013 | 4 | 0.32 |
| Ohio | Monroe | OH_SOUTH_2007 | 2007 | 20 | 0.08 |
| Ohio | Noble | OH_SOUTH_2007 | 2007 | 15 | 0.05 |
| Kansas | Montgomery | Kansas_2013_LiDAR | 2013 | 4 | 0.92 |
| Ohio | Licking | OH_SOUTH_2006 | 2006 | 16 | 0.05 |
| Ohio | Jefferson | OH_NORTH_2006 | 2006 | 16 | 0.06 |
| Ohio | Columbiana | OH_NORTH_2006 | 2006 | 20 | 0.04 |
| Kentucky | Ohio | NRCS_Lower_and_MiddleGreenPondRough | 2016 | 20 | 1.43 |
| Pennsylvania | Butler | PA_STATEWIDE_S_2006_2008 | 2006 | 7 | 0.6 |
| Kansas | Labette | Kansas_2013_LiDAR | 2013 | 4 | 0.31 |
| Oklahoma | Kay | NRCS_Dam_Rehab_Assessment | 2016 | 9 | 0.12 |
| Kentucky | Clinton | KY_WestCentral_2017_C19 | 2017 | 16 | 1.02 |
| Oklahoma | Muskogee | OK_Statewide_D22 | 2024 | 20 | 1.46 |
| Pennsylvania | Washington | PA_STATEWIDE_S_2006_2008 | 2006 | 9 | 0.38 |
| Oklahoma | Tulsa | OK_Woodward_FEMA_R6_Lidar_2016_D17 | 2016 | 22 | 1.07 |
| Oklahoma | Pawnee | NRCS_Dam_Rehab_Assessment | 2016 | 9 | 0.14 |
| Oklahoma | Creek | NRCS_Dam_Rehab_Assessment | 2016 | 9 | 0.19 |
| West Virginia | Pleasants | WV_FEMAR3_Southcentral_2018_D19 | 2018 | 38 | 3.66 |
| West Virginia | Pleasants | OH_SOUTH_2007 | 2007 | 5 | 0.01 |
| Indiana | Rush | Eastern_Indiana_QL3_Lidar | 2016 | 24 | 0.46 |
| Nebraska | Cheyenne | NE_South_Platte_2015 | 2015 | 32 | 0.57 |
| North Dakota | McKenzie | ND_Phase11_C24 | 2026 | 12 | 0.74 |

## 5. Budget by tier
Recommended project only.

| Tier | Counties | Tiles (newest project only) | GB |
|---|---|---|---|
| A same program as 9t (Pennsylvania) | 6 | 131 | 10.1 |
| B Appalachian other states | 17 | 1529 | 41.1 |
| C Mid-continent | 18 | 566 | 28.5 |
| D Gulf, West, Great Lakes | 10 | 325 | 26.2 |

- Disk. C: has about 108 GB free as of today (it was 145 GB earlier in the session). F: has about 3.0 TB free. Put every lidar set on F: and keep derivatives there.
- Whole-county downloads are 10 to 100 times larger than a pilot window. Do not fetch a county before a window result justifies it.
- A decompressed LAS is several times the LAZ size. The Warren tiles are 312 MB compressed and 2.8 GB with the merged LAS.

## 6. Priority order
1. **Tier A, Pennsylvania.** Same D20 program as 9t for Warren, Forest and Butler, and B19 for McKean and Forest. The first test (3.1) uses Warren, which is already on disk. A Forest D20 window is the next listed item. Windows run from under 1 GB to a few GB each (see the table).
2. **Tier B, Appalachian.** Allegany and Cattaraugus NY (the densest windows among the 51 counties listed, 1,049 and 991 orphans in 25 km²), Washington, Monroe and Noble OH, Lee, Powell and Cumberland KY, Pleasants WV. These are the best test of whether the model reaches other old-oil landscapes.
3. **Tier C, Mid-continent.** Okmulgee, Washington and Nowata OK, Montgomery, Labette and Neosho KS, Cumberland, Marion and Crawford IL. Different terrain and well age.
4. **Tier D.** Defer.

## 7. Cautions
- **Ohio.** The 2020 statewide project (B20) is listed as 186 to 200 small tiles per window. The older OH_SOUTH 2006 and 2007 tiles are about 3 MB each, which points to very low point density. Do not use them for pit-scale work without measuring ground density.
- **Window choice.** Windows are chosen by orphan count only. They say nothing about canopy, leaf-off timing, slope or ground return density. Measure ground density on one tile before fetching a window.
- **Flight year.** A project name year is a guide. Check acquisition dates in project metadata (manifest D1).
- **3DEP only.** State portals (for example KyFromAbove, Ohio OGRIP, New York ITS, Illinois ILHMP, Texas TNRIS) may hold the same or additional lidar. They were not searched.
- **Orphan definitions differ by state.** Oklahoma and Kentucky counts include wells with no production for a set period. Pennsylvania counts DEP lists.
- **Venango and McKean** are already partly held. Venango D20 is 1,060 tiles for the county box, of which tile 9t is nine.
- **Terms.** 3DEP lidar is public domain. State databases carry their own terms. Kentucky Geological Survey data is copyrighted and needs acknowledgement. Record terms in each `_PROVENANCE.json`.

## 8. Doing the download later
A fetch script for lidar does not exist yet. It should
1. read `lidar_download_list_pilot_5km_us.csv` and take a state, county and project filter,
2. check each URL's size with a HEAD request and stop at a stated total,
3. save to its own folder on F: such as `F:\lidar_pilot\<state>_<county>_<project>\`, never overwrite, write `_PROVENANCE.json`,
4. add a `.gitignore` rule for the folder in the same change,
5. read one tile with PDAL (CLI, pipeline file) and record ground density and acquisition dates before fetching the rest of the window.
