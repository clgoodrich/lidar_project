# Orphan Well Detection — LiDAR Terrain Analysis

## Project Goal

Develop a transferable methodology for detecting probable orphan and abandoned oil and gas wells using LiDAR-derived terrain signatures and machine learning. The core research contribution is not simply detecting wells in one area, but demonstrating that a model trained in one well-documented region can generalize to other regions without full retraining.

The United States has an estimated 2–3 million undocumented orphan wells from over a century of oil and gas production. These pose methane emission, groundwater contamination, and surface collapse hazards. Federal funding through the IIJA (~$4.7 billion) is available for remediation, but agencies cannot plug wells they cannot find. This pipeline provides a scalable, LiDAR-based screening tool to flag candidate locations for field verification.

---

## Research Questions

1. Can abandoned well sites be reliably distinguished from natural terrain using LiDAR-derived terrain derivatives alone?
2. Which terrain features are most diagnostic — and which degrade when applied across different terrain contexts?
3. How much does model performance drop when applied to a second region without retraining (direct transfer)?
4. How many labeled samples from a new region are needed to recover performance (partial retraining)?

---

## Study Design

**Training region**: Western Pennsylvania — birthplace of the U.S. oil industry (1859), highest concentration of historic wells nationally, good 3DEP LiDAR coverage, two well datasets available for validation.

**Transfer region**: TBD — to be selected based on terrain contrast with PA and 3DEP LiDAR availability. Candidates include Ohio (similar geology, easier test), Kansas (flat terrain, strong contrast), or West Virginia (similar but more rugged).

**Data sources**:
- USGS 3DEP airborne LiDAR, 1m point spacing, ground-classified
- PADEP Historic Oil and Gas Wells — 30,527 wells digitized from WPA-era maps (1930s), variable positional accuracy
- USGS National Documented Orphan Wells — 117,672 wells across 27 states, filtered to orphaned and abandoned status codes

---

## Directory Structure

The data folder is gitignored. It contains hundreds of GB of LiDAR tiles and processed rasters that cannot be synced to GitHub.

```
project/
├── data/                    # gitignored — all LiDAR and raster data lives here
│   ├── files/               # Raw LAZ / COPC.LAZ point cloud tiles
│   ├── dem_tiles/           # Per-tile bare-earth DEMs
│   ├── derivatives/         # Terrain derivative rasters
│   └── full_dem.tif         # Mosaicked bare-earth DEM
├── notebooks/               # Jupyter notebooks
├── CLAUDE.md                # This file
└── .gitignore               # Includes /data/
```

---

## Pipeline — What Has Been Built

### Stage 1 — LiDAR to Bare-Earth DEM
Raw airborne LiDAR point cloud tiles (LAZ format) are filtered to ground-classified returns only (Class 2) and interpolated into 1-meter bare-earth DEMs using TIN gridding. Processing is incremental — new tiles can be added at any time without reprocessing existing work. COPC-format tiles (a newer cloud-optimized variant) require conversion to standard LAZ before processing, since the current WhiteboxTools version does not support COPC directly. This conversion strips COPC-specific metadata that blocks writing via a fresh LasData object.

### Stage 2 — DEM Mosaicking
Individual DEM tiles are merged into a single continuous surface. CRS must be explicitly reassigned to EPSG:26917 (UTM Zone 17N) after mosaicking, as the merge operation drops the projection metadata.

### Stage 3 — Terrain Derivative Generation
Seven terrain derivatives are computed from the bare-earth DEM and form the feature space for classification. A key implementation challenge was discovered here: scipy's uniform_filter propagates NaN values outward from nodata areas, causing entire derivative layers to be all-NaN when applied to a mosaic with coverage gaps. The solution is to fill nodata areas with a neutral value before filtering and restore the original nodata mask afterward. This applies to TPI, roughness, and any other derivative using moving-window averaging.

The seven derivatives are:
- TPI at 5m, 15m, and 50m radii — measures local elevation relative to a neighborhood mean; negative values indicate depressions; multiple scales capture signatures at different spatial frequencies
- Slope — well pads are characteristically flat relative to surrounding Appalachian terrain
- Plan curvature — captures the circular geometry of pad edges and berm margins
- Local relief — elevation range within a moving window; engineered flat surfaces show anomalously low local relief within high-relief landscapes
- Surface roughness — standard deviation of slope in a moving window; pads exhibit low roughness relative to natural hillslopes

### Stage 4 — Well Data Integration
Two datasets are merged into a single well point layer. The PADEP historic shapefile covers Pennsylvania only and is derived from WPA-era map digitization — positional accuracy is variable and can be off by tens to hundreds of meters. The USGS national dataset covers 27 states and is filtered to orphaned and abandoned status codes. The Type field in the USGS dataset is not used for filtering because it is inconsistently coded across state agency sources — Status is the reliable field.

### Stage 5 — Feature Extraction
Terrain derivative values are extracted at well point locations and at an equal number of randomly generated non-well locations. Both point-based and patch-based extraction have been implemented. Patch-based extraction computes statistics (mean, min, std) over a 15m radius buffer around each point, which is preferred because historic well coordinates can be off by 30-100 meters, making single-pixel extraction unreliable.

### Stage 6 — Classification
A Random Forest classifier has been trained and evaluated. Current accuracy is approximately 57%, only marginally better than chance. This is believed to primarily reflect positional accuracy issues in the historic well records rather than an absence of terrain signal. Patch extraction is the next diagnostic step.

---

## Current Status

The pipeline is functional end-to-end. Accuracy is poor and under active investigation. The most likely causes in order of probability are:

- WPA-era well coordinates off by tens to hundreds of meters, so feature extraction samples the wrong terrain
- The current test tile coverage may not include enough wells with preserved surface signatures
- Steep Appalachian hillslopes have inherently high TPI variance that can mask subtle well depressions

---

## Known Methodological Issues to Address

**Positional accuracy**: Historic well coordinates are unreliable. Patch extraction at 15m radius partially compensates but cannot fully solve this. Ground truth field verification would be needed to fully resolve it.

**Spatial autocorrelation**: Random train/test splits inflate apparent accuracy because nearby samples share similar terrain features. Spatially blocked cross-validation is required before any results are formally reported.

**False positives**: Mining subsidence, farm ponds, natural depressions, sinkholes, and old homestead cellars all produce similar TPI signatures to well depressions, especially in Pennsylvania which has extensive coal mining history.

**Temporal mismatch**: LiDAR was collected in 2019. Wells plugged and reclaimed before that date may have had their surface signatures deliberately obliterated.

**Terrain transferability uncertainty**: Well signatures express differently across soil types. Clay-rich Appalachian soils preserve depressions for decades; sandy or wind-reworked soils may infill quickly. This is the central question of the transfer experiment.

---

## Modeling Plan

The notebook should be structured as a modular comparison framework so that multiple classifiers can be trained and evaluated on the same feature set without rewriting the pipeline. The intended progression is:

**Random Forest** — interpretable baseline. Feature importance directly informs the transferability analysis. Features that rank highly and show similar distributions across regions are candidates for robust cross-regional detection.

**XGBoost** — sequential gradient boosting, consistently outperforms Random Forest on tabular data by targeting residual errors from prior trees. Supports SHAP values for per-prediction explainability, which is valuable for understanding why the model succeeds or fails in specific terrain contexts.

**Feedforward neural network** — if Random Forest and XGBoost leave meaningful accuracy on the table, a simple network on the extracted tabular features is the next step. Requires more careful feature scaling and regularization. A CNN on raw terrain patches is a potential stretch goal if labeled sample sizes grow large enough.

The notebook should make it easy to swap classifiers and compare precision, recall, F1, and feature importance side by side across all three. Results should be presented as a comparison table, not separate analyses.

---

## Transfer Experiment Design (Planned)

1. Train the final model on Pennsylvania data with spatially blocked cross-validation
2. Apply directly to a second region without retraining — quantify performance degradation
3. Compare feature distributions between regions to identify which features shift and explain performance loss
4. Determine how many labeled samples from the second region are needed to recover Pennsylvania-level accuracy
5. Report which terrain features are regionally stable and which are locally specific — this is the primary scientific finding

---

## Environment Notes

- Windows, Python via .venv, no conda
- PDAL is not usable — requires C++ compilation that is incompatible with pip-only workflow
- WhiteboxTools is the primary LiDAR processing tool, installed via pip
- lazrs must be installed into the same venv as the Jupyter kernel and the kernel must be restarted before laspy can detect it

---

## Visualization Convention

User is red-green colorblind. All visualizations must use colorblind-safe palettes. Sequential data uses cividis. Diverging data such as TPI and curvature uses coolwarm_r with a zero-centered norm — blue indicates depressions, warm tones indicate ridges. Red-green colormaps are never used.
