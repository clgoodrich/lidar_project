# WellSight Pipeline Scripts

## Stage 1 — Raster Building (LAZ to GeoTIFF via PDAL)

These scripts take raw LAS/LAZ point clouds, ground-classify with SMRF, grid to 1m DEMs,
and generate all terrain derivatives (slope, hillshade, LRM, TPI, openness, CHM, roughness,
ground density, local relief). PDAL is invoked via subprocess JSON pipelines.

| Script | What It Builds |
|--------|---------------|
| `_build_9tile_1m.py` | 9-tile training area (4.5 x 4.5 km, tile tag `9t`) |
| `_build_mckean_5x5.py` | McKean County 5x5 tile (tag `mk5`) |
| `_build_mckean_full.py` | McKean County full extent (tag `mkf`) |
| `_run_single_tiles.py` | Two standalone test tiles (607594, 610605) — 14-15 km from training |
| `_run_hotspots_and_mckean.py` | Two high-density orphan well tiles (616593, 610594) + applies model to mk5 |

## Stage 2 — Detection and Analysis (rasters only, no PDAL)

These scripts work on the GeoTIFF derivatives from Stage 1. No point cloud processing.

| Script | What It Does |
|--------|-------------|
| `_pit_pipeline_1m.py` | Main pipeline: template learning, NCC scanning, 48-feature extraction, XGB+LGB+HGB ensemble, isotonic calibration. Produces `pit_1m_candidates_ensemble.gpkg` |
| `_retrain_675.py` | Earlier retrain run with 675 pits across 2 regions (predecessor to the 861-pit pipeline) |
| `_pit_morphology_audit_1m.py` | Measures pit dimensions (depth, radius, diameter, volume, aspect ratio) + anomaly detection (z-scores, Mahalanobis, Isolation Forest, PCA). Produces `pit_1m_morphology_audit.gpkg` |
| `_pit_rim_polygons.py` | Spoke-based rim polygon extraction (36-spoke radial tracing). Produces `pit_1m_polygons.gpkg` |
| `_build_geomorphon_enc.py` | Geomorphon enclosure rasters at 3 lookup distances. Future work only |

## Stage 3 — Paper and Notebook Generation

| Script | What It Produces |
|--------|-----------------|
| `_build_wellsight_notebook.py` | Generates `wellsight_morphology_pipeline.ipynb` programmatically |
| `_build_paper_docx.py` | Generates `WellSight_Paper_v5.docx` (full text) |
| `_build_paper_skeleton.py` | Generates `WellSight_Paper_skeleton_v3.docx` (headers + figures only, for manual writing) |
| `_generate_paper_figures.py` | Generates `paper_fig_*.png` figures |

## Consolidated Notebook

`wellsight_morphology_pipeline.ipynb` — Run top-to-bottom. Covers Stage 2 end-to-end
(template learning through paper figures). Requires Stage 1 derivatives to already exist.
