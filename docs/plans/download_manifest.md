# Download and acquisition manifest

**Date:** 2026-11-04
**Status:** plan only. Nothing here has been downloaded or requested. Sizes marked **estimate** are guesses from related files. Sizes marked **measure** must be taken from the provider's listing or API before any bulk fetch. Anything marked **unverified** has not been seen to exist.

## 1. Rules for every download
1. **Measure first.** Get the file count and byte size from the provider's API, a HEAD request or a listing. Write them in the table below before fetching. The TNM Access API answers from this machine.
2. **Gate first.** Each row names the condition that must hold before it is fetched. Do not fetch deferred items.
3. **Own folder.** Put each source in its own new empty folder `data/_source/<topic>/`. Downloaded files are untrusted data. Never run a script that arrived with a download. Keep fetch scripts in `notebooks/wellsight_v2/s1_build/`, not beside the data. Pass paths as arguments. `python -I` breaks here because the project packages live in user site, so read downloads with a small reader script run from another folder and never import from inside the data folder.
4. **Where.** Anything over about 5 GB goes to F: (about 3.2 TB free). C: has about 145 GB free. Add the `.gitignore` rule in the same change as the fetch script. After each fetch run the large-file audit from `CLAUDE.md`.
5. **Provenance.** Write `data/_source/<topic>/_PROVENANCE.json` with URL, access date, byte size, SHA-256, licence or terms, and the plan item. Hash after download and again before use.
6. **Scripts.** One fetch script per source named `_fetch_<source>_<area>.py`. It resumes, skips files that already match their hash, never overwrites, and holds no credentials. Existing example `notebooks/wellsight_v2/s1_build/_fetch_nlcd_9t.py`.
7. **Terms.** Record licence and use restrictions. Public data only, or data supplied to us with terms. Requests to people are logged in `docs/iterations/outreach_log.md` (new, one line per message).
8. **Literature.** Every paper that drives a decision goes in `literature/CITATIONS.md` in the same change. PDFs to `literature/papers/`. Paywalled ones are marked cite-only.

## 2. Already on disk (no download)
| What | Where | Size | Notes |
|---|---|---|---|
| Warren 7 LAZ tiles, USGS_LPC_PA_WesternPA_2019_D20 | `data/_source/lidar/warren_sheffield/` | 2.8 GB with the merged LAS (about 312 MB compressed) | Same D20 program as 9t. Headers report NAD83(2011) UTM 17N plus NAVD88 (Geoid12B), per the Codex review. Creation dates are not flight dates |
| Warren 1 m derivatives | `data/warren/derived/1m/` | measure | Wrong resolution for the frozen models. Rebuild at 0.5 m locally. No download |
| DEP export April 2026 | `data/_source/reference/dep_wells/` | measure | Read-only |
| 2022 orphan list | `data/_source/reference/legacy_data/US_Documented_Orphan_Wells.csv` | small | |
| McKean lidar `mckean_full.las` | F: | 455 MB | Scope is unconfirmed (see below) |
| Historic topo, Oil City 1922, 1:62,500 | `data/_source/historic_topo_probe/` | 8.7 MB | One sheet probed. No well symbols seen |

## 3. Small downloads, safe to do first
| ID | What | Plan | Source | Size | Gate | Verify before fetch |
|---|---|---|---|---|---|---|
| D1 | USGS 3DEP project metadata and flight-date fields for the 2006 to 2008 and 2019 surveys over 9t and Warren | 4.5, P2, 3.1 | TNM Access API, project XML | under 10 MB, measure | none | Which metadata field holds acquisition dates. File creation dates do not count |
| D2 | Older DEP oil and gas location releases (dated snapshots) | 5.4, A6 | PASDA and DEP archives | measure each, probably under 100 MB | after D3 reply, to see if useful | Whether snapshots finer than 4 years exist. **Unverified** |
| D3 | Literature PDFs and page snapshots, listed in section 7 | all | publishers, agency sites | under 100 MB total | none | Open access or cite-only |
| D4 | Carbon Mapper product guide and a Pennsylvania plume subset | 4.4 | carbonmapper.org | under 100 MB | none | Detection-limit table. Needed to decide whether 4.4 closes |
| D5 | Three more historic topo sheets, different dates and scales | 4.6 | USGS TNM (31 sheets listed over 9t) | about 10 MB each, **estimate**, about 30 MB | none | Pick the earliest sheet and one 1:24,000 sheet. Check neatline cover of 9t. The one probed sheet cut 9t at its north neatline |
| D6 | Metadata-only search for pre-1880 sources | 4.6, 5.2 | Library of Congress, David Rumsey, Penn State, USGS Library, state archives | none | none | Which sources exist, scale, coverage of the 9t corner, scan resolution, rights. **Unverified** that any covers 9t. This step is a search, not a download |
| D7 | Aerial frame index for 9t, 1937 to 1942 and later | 4.6, 4.8 | USGS EarthExplorer single-frame, Penn State historical aerials | index is small | none | An index entry does not guarantee a usable scan. Measure each frame's size |

## 4. Gated downloads
| ID | What | Plan | Source | Size | Gate |
|---|---|---|---|---|---|
| D8 | Pre-1880 map or atlas sheets that cover 9t | 4.6 | from D6 | **estimate** 20 to 200 MB per scan, only the sheets that cover 9t | D6 finds a source with usable scale and coverage |
| D9 | Aerial frames over 9t | 4.6, 4.8 | from D7 | **estimate** 50 to 150 MB per scan, **measure**. Perhaps 5 to 15 frames | D7 lists frames with dates, and one frame passes a legibility look |
| D10 | Leaf-off orthoimagery for 9t and Warren | 4.8 | PA state orthoimagery on PASDA, NAIP | **measure** | A small chip sample shows usable visible ground. Earlier chips were blank 10 of 13 times (reported by the Claude review) |
| D11 | ANF QL1 `PA_Northcentral_2019_B19` tiles for eastern Warren and Forest, if they exist | 3.1 sensor-shift arm | TNM Access API | **measure**. About 9 points per m². McKean is already held (455 MB) | 3.1 within-survey result is in, the tile list is counted, and Forest lidar readiness is verified. **Unverified** |
| D12 | Oil Creek drone lidar point clouds | 4.7 | NETL, by request | **unknown**. Possibly tens of GB. Goes to F: | NETL replies. The page does not say the data are released |
| D13 | Texas RRC orphan layer 2 | 3.4 | ArcGIS REST query | under 50 MB, **estimate** | 3.4 is un-deferred. Needs the RRC location reliability fields |
| D14 | Public lidar for one county each in OH, WV, NY, KY | 3.2 | state programs, TNM | **measure**. A county is multi-GB. Not 20 GB | One candidate county chosen from a metadata-only inventory table |
| D15 | One flat county each in Illinois and Michigan | 3.3 | state programs, TNM | **measure** | 3.3 step 4 (slope stratification on existing 9t output) is done first |

## 5. Not to be downloaded now
- Thermal (Landsat TIRS, ECOSTRESS), vegetation time series, any SAR time series (4.2, 4.3, 3.8). The observability gate in `protocol_gates_and_metrics.md` section 9 comes first.
- Oklahoma, Kansas, California, Canada, Alaska lidar and records (3.5 to 3.8). Build a metadata-only inventory table first. Coverage, licence and access are **unverified**.
- Pretraining corpora (7.1). Decide the comparison first.
- Methane plume imagery beyond the D4 subset.

## 6. By request to people, not by download
| ID | What | From | Needed for | Notes |
|---|---|---|---|---|
| R1 | Coordinate provenance for DEP orphan and abandoned records, and any GNSS-surveyed wells | DEP Orphan and Abandoned Well Program | 5.6, A6, 5.4 | Draft in `docs/iterations/outreach_requests_drafts.md`. Also ask about the 1800 spud sentinel and the 2022 to 2026 additions |
| R2 | NETL drone lidar, selection history of the sites, coordinates and any field confirmation | NETL | 4.7, 5.6 | NETL's page says "63 potential well sites were located on two hillsides using LiDAR data". Not 63 wells. Not confirmed. Do not repeat "63 wells" |
| R3 | Magnetometer loan or partner | university geophysics, survey | 4.1 | Instrument, base station, training |
| R4 | Whether annotators had DEP well points visible while drawing | the user | 5.6 | Decides whether association with annotations is circular |
| R5 | Whether McKean is still set aside, and where the thermal work lives | the user | 3.1 scope, 4.2 | Open since July 2026 |
| R6 | Reviewers for confuser labels and annotation of the test blocks | the user | 6.3, 3.1 | Two reviewers per candidate, plus an adjudicator |
| R7 | Surface restoration records, not only plug dates | DEP | 4.5 | Plug dates do not show earthwork |

## 7. Literature to obtain (add each to `literature/CITATIONS.md`)
| Reference | Used for | Access |
|---|---|---|
| Hammack, Veloski, Sams and Kohnke (2023). Aeromagnetic surveys for the location of undocumented orphaned wells. The Leading Edge 42(12) | Era-blind magnetometry (4.1, 7.5) | Not yet read. Cite-only likely |
| Kang et al. (2014). Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania. PNAS 111(51) | Methane scale (4.4, 6.5). Checked at the Princeton record, 19 wells, mean about 0.27 kg per day | Download PDF |
| NETL, Oil Creek orphan well page `https://netl.doe.gov/node/9506` | 4.1, 4.7. Checked. States the 63 potential sites and the casing limit | Save a page snapshot |
| Carbon Mapper product guide | 4.4 detection limits | Download PDF |
| USGS Lidar Base Specification tables | QL2 meaning | Download |
| ECOSTRESS ECO2 user guide (LP DAAC), NASA Landsat 8 mission page | Thermal pixel size (4.2) | Download |
| Texas RRC public GIS viewer tool guide | Location reliability (3.4) | Download PDF |
| 40 CFR 146.84 (eCFR) | Class VI information requirements (6.1) | Save a snapshot |

## 8. Disk and order
- **Critical path (D1, D3, D4, D5, D6, D7 index).** Well under 1 GB in total. It fits on C: with no planning.
- **Gated and measured items (D8 to D15).** Unknown until measured. Keep a running total in `data/_source/_download_ledger.csv` (new). Stop at a stated budget and ask which gate to relax.
- **D12 is the one open-ended item.** Hold F: space for it.
- **Order.** D1, then D3 and D4, then D6 and D7 as searches, then D5. Fetch D8 and D9 only for what D6 and D7 find. Everything else waits on its gate.
