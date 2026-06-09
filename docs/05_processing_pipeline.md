# 05 — Processing Pipeline

**Status:** draft 1 · **Date:** 2026-04-13 · **Governs:** notebook order, tool choices per stage, cached artefacts

## 1. Stages (top-level)

```
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│  A. Ingest         │   │  B. Raster base    │   │  C. Terrain deriv. │
│  LAS + CSV in      │──▶│  DEM / DSM / CHM / │──▶│  slope / rough /   │
│  wells_in_tile     │   │  ground_density    │   │  TPI / tpi_grad /  │
└────────────────────┘   └────────────────────┘   │  local_relief      │
                                                  └─────────┬──────────┘
                                                            │
                                                            ▼
┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
│  F. Reporting +    │   │  E. Validation     │   │  D. Pad detector   │
│  analysis_log      │◀──│  null-baseline &   │◀──│  flat mask → morph │
│  update            │   │  within-uncert.    │   │  → polygons →      │
└────────────────────┘   └────────────────────┘   │  shape/pos gates   │
                                                  └────────────────────┘
```

Each arrow moves **cached GeoTIFF / GeoPackage files**, never in-memory
Python state. This is what makes the pipeline reproducible and the WellSight
"cache intermediate products" rule compliant.

## 2. Per-stage detail

### A. Ingest

| Step | Tool                        | Input                            | Output                                               |
|------|-----------------------------|----------------------------------|------------------------------------------------------|
| A1   | **PDAL CLI** (`pdal info`)  | `output2.las`                    | `docs/03_las_inspection_report.md` (already written) |
| A2   | Python + `geopandas`        | `output_wells.csv`               | `data/derivatives/wells_in_tile.gpkg` (EPSG:6346)    |

Notebook: `notebooks/01_preprocessing.ipynb` (current file, light edits to
replace laspy raster gridding with PDAL TIN — see stage B).

### B. Raster base products

Written to `data/derivatives/` as deflate-compressed float32 GeoTIFFs
(uint8 for hillshade), always at 1 m resolution, always snapped to integer
metres, always in EPSG:6346.

| File                     | Source                                              | Tool                  |
|--------------------------|-----------------------------------------------------|-----------------------|
| `dem_1m.tif`             | `class=2` ground points                             | **PDAL CLI**: `readers.las` → `filters.range("Classification[2:2]")` → `filters.delaunay` → `writers.gdal(output_type="idw")` or `writers.gdal(output_type="min")` |
| `dsm_1m.tif`             | `ReturnNumber == 1` first returns                   | **PDAL CLI**: same pattern, filter on `ReturnNumber[1:1]`, `output_type="max"` |
| `chm_1m.tif`             | `dsm_1m.tif − dem_1m.tif`, floored at 0             | Python (`rasterio` + numpy)                           |
| `ground_density.tif`     | Count of `class=2` per 1 m cell                     | **PDAL CLI**: `writers.gdal(output_type="count")`     |
| `hillshade.tif`          | Hillshade of DEM, az 315°, alt 45°                  | **WhiteboxTools** `Hillshade` *or* `gdaldem hillshade` |

**`run_pipeline()` helper.** Every PDAL invocation goes through the exact
subprocess pattern spelled out in `Claude.md` — JSON pipeline to temp file,
`subprocess.run([PDAL_EXE, 'pipeline', tmp], ...)`, capture stdout/stderr
into the analysis log.

### C. Terrain derivatives

| File                  | Formula                                                                 | Tool                      |
|-----------------------|-------------------------------------------------------------------------|---------------------------|
| `slope.tif`           | Horn (1981) 3×3 finite-difference slope                                  | **WhiteboxTools** `Slope` |
| `roughness_11.tif`    | σ of elevation within 11×11 window                                       | Python (`scipy.ndimage`)  |
| `local_relief_10.tif` | max−min of elevation in a 10 m disk                                      | Python (`scipy.ndimage`)  |
| `tpi_05.tif`          | z − mean(z in disk r=5 m)                                                | **WhiteboxTools** `RelativeTopographicPosition` or hand-rolled |
| `tpi_15.tif`          | z − mean(z in disk r=15 m)                                               | same                      |
| `tpi_51.tif`          | z − mean(z in disk r=51 m)                                               | same                      |
| `tpi_grad_mag.tif`    | ‖∇(tpi_15)‖                                                              | Python (`numpy.gradient`) |
| `tpi_grad_dir.tif`    | arctan2 of ∇(tpi_15)                                                     | Python                    |

Tool rule of thumb: use **WhiteboxTools** where it ships a pre-tested
implementation for a named geomorphometric quantity (slope, TPI,
curvature). Use **hand-rolled Python + scipy** for derived quantities that
are trivially vectorisable and benefit from NaN-awareness (local relief,
roughness, TPI gradient).

Notebook: `notebooks/02_derivatives.ipynb` (to be written *after* stage A
produces DEM).

### D. Pad detector

Single notebook `notebooks/03_pad_detector.ipynb`. Implements the stages in
§3 of the design spec (`docs/04_feature_detection_design_spec.md`):

1. Build flatness mask from slope / roughness / local relief GeoTIFFs.
2. Closing r=1 cell (no opening — preserves small pads).
3. Connected components → polygonise (`rasterio.features.shapes`).
4. Per-polygon attributes (area, shape, mean-derivative stats).
5. Apply shape + position + size gates.
6. Compute confidence score (§5 of design spec).
7. Compute nearest-well distance via `gpd.sjoin_nearest`.
8. Export `data/derivatives/experiments/candidates/candidates_pads.gpkg` + Parquet.

**Bootstrap gate.** Before the full-tile run, the notebook runs the detector
on 3–5 well-window sub-extracts (§8 of design spec). Tile-wide execution is
gated behind an `assert` that verifies the pilot passed the acceptance
criteria.

### E. Validation

Notebook `notebooks/04_validation.ipynb`. Implements §7 of the design spec
(random-baseline + within-uncertainty recall). Outputs:

- `data/derivatives/validation/baseline_nulls.parquet` (per-run null
  distributions).
- `data/derivatives/validation/summary_run_<id>.md` (markdown summary
  appended to the analysis log).

### F. Reporting & log

Every stage that produces a new artefact appends a dated entry to
`docs/analysis_log.md` with:

- run_id (UTC timestamp + git short SHA if available)
- stage letter + tool invoked
- parameters used (copy of the JSON / thresholds)
- artefact path(s) produced
- headline numbers (point counts, candidate counts, median distances)
- anomalies flagged (CRS mismatch, low-density voids, etc.)

## 3. Cached artefacts — exhaustive list

```
data/derivatives/
├── wells_in_tile.gpkg            ← stage A
├── dem_1m.tif                    ← stage B
├── dsm_1m.tif                    ← stage B
├── chm_1m.tif                    ← stage B
├── ground_density.tif            ← stage B
├── hillshade.tif                 ← stage B
├── slope.tif                     ← stage C
├── roughness_11.tif              ← stage C
├── local_relief_10.tif           ← stage C
├── tpi_05.tif                    ← stage C
├── tpi_15.tif                    ← stage C
├── tpi_51.tif                    ← stage C
├── tpi_grad_mag.tif              ← stage C
├── tpi_grad_dir.tif              ← stage C
├── candidates/
│   └── candidates_pads.gpkg      ← stage D
└── validation/
    ├── baseline_nulls.parquet    ← stage E
    └── summary_run_*.md          ← stage E
```

All files are **deterministic products** of the raw inputs. Deleting them
and re-running the notebooks must produce byte-identical GeoTIFFs modulo
compression artefacts.

## 4. Notebook order (canonical)

```
notebooks/
├── 01_preprocessing.ipynb       (stage A + first parts of stage B via PDAL CLI)
├── 02_derivatives.ipynb         (stage C)
├── 03_pad_detector.ipynb        (stage D, includes bootstrap pilot)
└── 04_validation.ipynb          (stage E)
```

No side notebooks, no gallery notebooks, no alternative-filter sections. The
only way to produce a candidate is to run the canonical order. Gallery and
QA figures are cells **inside** the relevant notebook, not separate files.

## 5. Out-of-scope for the pipeline (pilot)

- Intensity-anomaly / specular-surface detectors (needs flight-line overlap
  work).
- Canopy-density / CHM-anomaly detectors (belong to a future vegetation
  notebook, tracked as a separate feature-type layer).
- Streaming from AWS EPT tiles (local-files-only pilot per project scope).
- Machine-learning scoring on extracted per-candidate feature vectors.
  Possible once the rule-based v0.2 run has a labelled candidate set.
