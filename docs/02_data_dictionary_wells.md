# 02 — Data Dictionary: `output_wells.csv`

**File:** `data/source_laz/westernpa/output_wells.csv` · **Treat as read-only ground truth** · **Date inspected:** 2026-04-13

## Overview

| Property                | Value                                                          |
|-------------------------|----------------------------------------------------------------|
| Shape                   | 84 rows × 26 columns                                           |
| Source                  | Pennsylvania Department of Environmental Protection (PA DEP)   |
| Release date            | 2022-05-09 (value of `Data_file_date`, homogeneous)            |
| Spatial coverage        | All 84 records fall within tile `output2.las` (Venango County) |
| Status homogeneity      | `Status == "Orphan"` for every row                             |
| Coord duplicates        | 0 — every `(Latitude, Longitude)` pair is unique               |
| Horizontal CRS of coords | **EPSG:4326 (WGS84)** — decimal degrees                       |

## Column catalogue

| #  | Column            | Type     | Non-null / 84 | Unique | Role                   | Notes                                                                                                                                                                               |
|----|-------------------|----------|--------------:|-------:|------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1  | `OBJECTID_1`      | int/null |             0 |      0 | legacy GIS id         | Entirely null. Drop on ingest.                                                                                                                                                      |
| 2  | `Well_ident`      | str      |            84 |     84 | **primary key**        | Format: `API:14-digit`. Real API numbers. State prefix `37` = Pennsylvania (expected).                                                                                              |
| 3  | `State`           | str      |            84 |      1 | attr                   | Always "Pennsylvania". Redundant.                                                                                                                                                   |
| 4  | `County`          | str      |            84 |      1 | attr                   | Always "Venango".                                                                                                                                                                   |
| 5  | `Well_name`       | str      |            84 |     84 | attr                   | Operator-assigned name, e.g. "WOIDECK 33Q". Useful for human audit; not reliable as a key.                                                                                           |
| 6  | `Well_numbe`      | —        |             0 |      0 | —                      | Entirely null. Drop.                                                                                                                                                                |
| 7  | `Type`            | —        |             0 |      0 | —                      | Entirely null (gas/oil/CBM flag not populated). Drop.                                                                                                                               |
| 8  | `Status`          | str      |            84 |      1 | attr                   | Always "Orphan". Consistent with the release being the PA DEP orphan-well subset. Could be dropped, retained for audit clarity.                                                     |
| 9  | `Latitude`        | float    |            84 |     77 | **geometry**           | Decimal degrees, WGS84. Range fits Venango County.                                                                                                                                  |
| 10 | `Longitude`       | float    |            84 |     79 | **geometry**           | Decimal degrees, WGS84.                                                                                                                                                             |
| 11 | `Prime_meri`      | —        |             0 |      0 | —                      | PLSS principal-meridian slot. Null across the whole file. Drop.                                                                                                                     |
| 12 | `Township`        | int      |            84 |      1 | —                      | Always "0" — PLSS placeholder, not populated. Drop.                                                                                                                                 |
| 13 | `T_dir`           | —        |             0 |      0 | —                      | PLSS township direction placeholder. Drop.                                                                                                                                          |
| 14 | `Range`           | int      |            84 |      1 | —                      | Always "0". Drop.                                                                                                                                                                   |
| 15 | `R_dir`           | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 16 | `Section`         | int      |            84 |      1 | —                      | Always "0". Drop.                                                                                                                                                                   |
| 17 | `Qtr`             | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 18 | `Qtr_qtr`         | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 19 | `Qtr_qtr_qt`      | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 20 | `Source`          | str      |            84 |      1 | attr                   | Always "Pennsylvania Department of Environmental Protection". Retain for provenance.                                                                                                |
| 21 | `Data_file_date`  | str      |            84 |      1 | attr                   | Always "5/9/2022" — the release date, not individual plugging dates. Retain.                                                                                                        |
| 22 | `Well_info`       | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 23 | `Location_n`      | str      |            84 |      3 | attr                   | Free-text municipality. Values: "Municipality: President Twp" (78), "Municipality: Allegheny Twp" (5), "Municipality: President Twp." (1 — trailing period is a normalisation bug). |
| 24 | `Other_note`      | —        |             0 |      0 | —                      | Drop.                                                                                                                                                                               |
| 25 | `x`               | float    |            84 |     79 | geometry (dup)         | Same as `Longitude` but printed to ≥13 dp. Ignore in favour of `Longitude`.                                                                                                         |
| 26 | `y`               | float    |            84 |     77 | geometry (dup)         | Same as `Latitude` to ≥13 dp. Ignore.                                                                                                                                               |

## Usable subset after cleanup

```text
Well_ident, Well_name, Latitude, Longitude, Location_n, Source, Data_file_date
```

Everything else is either constant or null across the 84 rows. PLSS fields
never populated in this county's DEP release, likely because PA is a metes-
and-bounds state.

## Critical data-quality notes

1. **No drilling date / plugging date / drill operator-era flag.** There is no
   column that distinguishes a pre-1900 cable-tool well from a 1960s rotary
   well. A detector that depends on era-specific pad size is unsupported by
   the ground truth. Mitigation: treat era as a hidden variable.
2. **No coordinate accuracy flag.** PA DEP historic orphan records carry
   positional uncertainty commonly cited as 30–100 m for pre-1990 wells. A
   literature-based default of 50 m is applied for validation statistics
   unless we later obtain per-well accuracy metadata.
3. **Municipality normalisation bug.** One row has trailing punctuation
   ("President Twp."). If we ever group-by municipality, normalise first.
4. **Duplicate coordinate columns.** `(Latitude, Longitude)` and `(y, x)` carry
   the same values to different precision. Use `Latitude` / `Longitude` as
   canonical; log the presence of `x` / `y` but do not reproject twice.
5. **All records are currently "Orphan".** This is a subset of the PA DEP
   universe — "Plugged" and "Active" records are absent. Any per-status
   analysis is therefore vacuous on this file.
6. **Sample well IDs parse as real APIs.** Example: `API:37121220500000` →
   state 37 (PA), county 121 (Venango), permit 22050, side-track 00, sub 00.
   API-number structure is trustable; coordinates less so.

## Validation ingest rule

On load:
1. Keep only the columns listed in "Usable subset".
2. Reproject `Latitude`/`Longitude` → CRS of the LAS tile (EPSG:6346).
3. Clip to the LAS bounding box (+ small buffer to retain near-edge wells).
4. Drop duplicate `Well_ident`. (Currently none, but defensive.)
5. Output a GeoPackage `data/derivatives/wells_in_tile.gpkg` that downstream
   code treats as authoritative. Do not re-read the raw CSV after that point.
