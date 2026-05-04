# 01 — Project Scope (WellSight)

**Status:** draft 1 · **Date:** 2026-04-13 · **Authority:** `Claude.md` (WellSight Formation Prompt)

## 1. Mission

Detect candidate **orphaned oil/gas well locations** in western Pennsylvania
LiDAR by identifying surface terrain signatures (pad scars, depressions,
cleared patches, access road remnants, vegetation anomalies) and validating
against the PA DEP documented-well ground truth.

The system is called **WellSight**. Candidates are always reported as
*candidate* or *probable* — never as confirmed wells.

## 2. Study area (current pilot)

- **Tile:** `data/files/output2.las`
- **Spatial extent:** 622 500 – 624 000 E, 4 594 500 – 4 596 000 N (UTM 17N, NAD83(2011))
- **Size:** 1.5 × 1.5 km = 2.25 km²
- **Location:** Venango County, PA (President Twp predominantly,
  Allegheny Twp fringe) — confirmed via the `Location_n` column of the
  documented-well CSV.
- **Terrain regime:** Appalachian Plateau, moderate–steep slopes, mixed
  deciduous forest, deeply incised drainages, ≥150 yr industrial activity.

A wider area (50+ adjacent `.laz` tiles covering ~75 km²) is available in
`data/files/` for scale-up after the pilot validates.

## 3. Ground truth

- **Source:** `data/files/output_wells.csv`
- **Records inside the tile:** 84 wells, all `Status = "Orphan"`, all
  originating from the PA DEP 5/9/2022 release.
- **Coordinate provenance:** `Latitude` / `Longitude` (EPSG:4326). No GPS-quality
  flag is present in the CSV — treat all coordinates as *documentary*, not
  survey-grade. Historic PA DEP orphan records commonly carry 30–100+ m
  positional uncertainty for pre-1990 wells.
- **Implication for detection logic:** candidate generation must tolerate well
  coordinates that do **not** land on the actual pad. A feature is useful even
  if it is merely *near* a record.

## 4. Deliverables (pilot scope)

1. **LAS inspection report** (`docs/03_las_inspection_report.md`).
2. **Wells data dictionary** (`docs/02_data_dictionary_wells.md`).
3. **Design spec** and **pipeline diagram** (`docs/04`, `docs/05`).
4. **Cached base rasters:** DEM, DSM, CHM, ground-return density (1 m).
5. **Per-feature candidate layer(s):** starting with pad scars. Output format:
   GeoPackage with geometry + attributes as specified in the design spec.
6. **Validation summary** per WellSight reporting rule: candidate count,
   true-positive rate vs. known wells, FP count/characterization, parameters,
   next steps.
7. **Running analysis log** (`docs/analysis_log.md`).

## 5. Out of scope

- Well-capping priority ranking or remediation recommendations.
- Field verification of candidates (external activity).
- Auto-ingestion of remote data (TNM API / EPT streaming). The pilot operates
  on local files only.
- Full-area scale-up. That follows the pilot per the WellSight Bootstrap rule.

## 6. Success criteria

| Criterion                                                                 | Measure                                                                                  |
|---------------------------------------------------------------------------|------------------------------------------------------------------------------------------|
| Detection clusters above chance near documented wells                     | Median candidate → nearest-well distance is lower than random-placement null distribution |
| Reproducibility                                                           | Every derivative and candidate layer re-generates deterministically from raw inputs       |
| CRS consistency                                                           | No layer leaves the pipeline in an unverified CRS                                        |
| Documentation completeness                                                | All five WellSight docs exist before any detector code runs                              |
| Each candidate carries confidence score, detection method, nearest-well m | Enforced by the output schema in the design spec                                         |

## 7. Constraints & conventions

- **Toolchain** (per WellSight doc):
  - Python primary.
  - PDAL via subprocess CLI for LAS/LAZ pipelines (Python bindings are
    disabled in this environment; use the `run_pipeline()` helper).
  - WhiteboxTools for terrain derivatives where its algorithms beat a
    hand-rolled Python version.
  - `laspy` permitted only for lightweight header inspection / small custom
    reads, not for production pipelines.
- **CRS:** LAS is NAD83(2011)/UTM 17N + NAVD88 Geoid12B (both metric). All
  rasters and candidate layers inherit this CRS. Wells are reprojected from
  EPSG:4326 to this CRS at ingest.
- **Caching:** DEM, DSM, CHM, ground-density raster are computed **once** and
  persisted under `data/derivatives/` for reuse.
- **Bootstrap:** any new detection technique is first validated on a
  sub-window surrounding 3–5 known wells before running tile-wide.
- **Reporting cadence:** every "major analysis pass" (new detector, threshold
  change, parameter sweep) ends with the summary format defined by the doc and
  is appended to `docs/analysis_log.md`.

## 8. Open questions (to escalate, not guess)

- **Multiple drilling eras.** The documented wells are a flat list with no
  drilling-date attribute. Decision needed: do we pursue era-specific
  detectors (cable-tool pads ≠ modern pads) or a single catch-all detector?
- **Coordinate uncertainty model.** Without a per-well accuracy flag, the
  validation math has to assume a uniform positional error. A literature-based
  default of ~50 m for pre-1990 PA DEP records will be used unless the user
  supplies better.
- **Scale-up trigger.** What pilot metric must be met before processing the
  neighbouring `.laz` tiles? Proposal in the design spec, to be confirmed.
