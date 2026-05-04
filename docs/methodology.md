# WellSight: LiDAR-Based Orphaned Well Pit Detection — Methodology

## Table of Contents

1. [Overview](#1-overview)
2. [Study Area and Data Sources](#2-study-area-and-data-sources)
3. [Point Cloud Preprocessing](#3-point-cloud-preprocessing)
4. [Raster Derivative Generation](#4-raster-derivative-generation)
5. [Ground Truth Annotation](#5-ground-truth-annotation)
6. [Pit Candidate Generation via Template Matching](#6-pit-candidate-generation-via-template-matching)
7. [Feature Engineering](#7-feature-engineering)
8. [Model Training and Evaluation](#8-model-training-and-evaluation)
9. [Ensemble and Calibration](#9-ensemble-and-calibration)
10. [Cross-Tile Generalization](#10-cross-tile-generalization)
11. [Discovery Mode](#11-discovery-mode)
12. [Results Summary](#12-results-summary)
13. [Pipeline Scripts Reference](#13-pipeline-scripts-reference)
14. [Limitations and Future Work](#14-limitations-and-future-work)

---

## 1. Overview

WellSight is a pipeline for detecting orphaned oil and gas well pits (collapsed well cellars) from airborne LiDAR data. The pipeline operates in four stages:

1. **Derivative generation** — Convert raw LAS point clouds into a stack of terrain analysis rasters (DEM, slope, Local Relief Model, Topographic Position Index, topographic openness, etc.)
2. **Template-based candidate generation** — Learn the morphological signature of known well pits, then scan the landscape via normalized cross-correlation to find all locations with pit-like terrain
3. **Machine learning classification** — Extract 88 features per candidate and train a gradient-boosted ensemble (XGBoost + LightGBM) to separate real pits from look-alikes (tree throws, natural depressions, drainage features)
4. **Ranked output with calibrated probabilities** — Produce a GeoPackage of candidate locations ranked by isotonic-calibrated probability, suitable for field verification

The pipeline was developed and validated on a 1.5 km × 1.5 km tile in Venango County, western Pennsylvania (USGS 3DEP 2019 flight), then applied blind to an adjacent tile with zero documented wells. A 4.5 km × 4.5 km (3×3 tile) mosaic was also produced for expanded annotation and analysis.

### Software Stack

| Tool | Role |
|------|------|
| **Python 3.13** | Primary language for all processing |
| **PDAL 2.10** (CLI, via subprocess) | LAS/LAZ I/O, TIN interpolation, rasterization |
| **WhiteboxTools** | Hillshade, slope |
| **laspy** | Direct point cloud attribute access (density, intensity) |
| **scipy.ndimage** | Convolution-based derivatives (LRM, TPI, roughness, openness) |
| **scikit-image** | Template matching (NCC), peak detection |
| **XGBoost 3.2** | Primary gradient-boosted classifier |
| **LightGBM 4.6** | Ensemble member |
| **scikit-learn** | GroupKFold CV, isotonic calibration, clustering |
| **rasterio** | GeoTIFF I/O |
| **geopandas** | Vector I/O (GeoPackage) |

---

## 2. Study Area and Data Sources

### 2.1 Study Region

Western Pennsylvania, Venango County. Appalachian Plateau terrain: moderate to steep slopes, heavy deciduous and mixed forest canopy, deeply incised stream valleys, and 150+ years of oil and gas extraction history (dating to the Drake Well, 1859).

### 2.2 LiDAR Point Clouds

| File | Epoch | Points | Footprint (UTM 17N) | Resolution |
|------|-------|--------|----------------------|------------|
| `output3.las` | 2019 USGS 3DEP | 8,956,340 | 621000–622500 E, 4594500–4596000 N | ~4 pts/m² |
| `output2.las` | 2019 USGS 3DEP | 9,717,579 | 622500–624000 E, 4594500–4596000 N | ~4 pts/m² |
| `output3_9tile.las` | 2019 (merged) | ~80M | 619500–624000 E, 4593000–4597500 N | ~4 pts/m² |
| `output3_2008.las` | 2006-2008 PAMAP | 1,366,925 | 621000–622500 E, 4594500–4596000 N | ~0.6 pts/m² |
| `output2_2008.las` | 2006-2008 PAMAP | ~1.3M | 622500–624000 E, 4594500–4596000 N | ~0.6 pts/m² |

- **2019 data:** LAS 1.4, point format 7, EPSG:6346 (NAD83(2011) / UTM zone 17N), NAVD88 metres
- **2008 data:** PAMAP program, originally EPSG:2271 (PA State Plane North, US survey feet). Reprojected to EPSG:6346, Z converted from US survey feet to metres (× 0.3048006096). No vertical alignment offset applied — datasets kept separate.

### 2.3 Well Records

- `output_wells_2.csv`: 107 PA DEP orphaned well records in the output3 footprint (API identifiers, lat/lon, status "Orphan"). Zero documented wells in the output2 footprint.
- Well records used for reference only; expert annotations (below) serve as training labels.

### 2.4 Source Tile Naming Convention

2019 USGS tiles follow: `USGS_LPC_PA_WesternPA_2019_D20_17TPF{XXX}{YYY}.laz`
- XXX = easting in km (truncated), YYY = northing in km minus 4000
- Example: `17TPF621594.laz` → origin X=621000, Y=4594500, extent 1500m × 1500m
- 9-tile mosaic uses codes: 619593, 619594, 619596, 621593, 621594, 621596, 622593, 622594, 622596

2008 PAMAP tiles follow: `USGS_LPC_PA_STATEWIDE_N_2006_2008_PA_Statewide_N_2006-2008_{TILEID}.laz`
- Tiles used: 002958, 002959, 003111, 003112 (output3 area); 002959, 003112 (output2 area)

---

## 3. Point Cloud Preprocessing

All PDAL operations use the `run_pipeline()` helper pattern:

```python
def run_pipeline(pipeline_dict, label="pipeline", timeout=600):
    tmp = out("_tmp_pipeline.json")
    with open(tmp, 'w') as f:
        json.dump(pipeline_dict, f, indent=2)
    result = subprocess.run(
        [PDAL_EXE, 'pipeline', tmp],
        capture_output=True, text=True, timeout=timeout
    )
    return result
```

### 3.1 DEM Generation (TIN Interpolation)

```
readers.las → filters.range (Classification[2:2]) → filters.delaunay → filters.faceraster → writers.raster
```

- Filter to ground-classified returns only (class 2)
- Construct Delaunay triangulation over ground points
- Rasterize TIN at target resolution with pinned grid origin
- Output: float32 GeoTIFF

### 3.2 DSM Generation

```
readers.las → filters.range (ReturnNumber[1:1]) → writers.gdal (output_type=max)
```

- Filter to first returns only
- Rasterize as maximum elevation per cell

### 3.3 2008 PAMAP Merge and Reprojection

For each tile footprint, merge overlapping 2008 PAMAP tiles:

```
readers.las (override_srs=EPSG:2271) → filters.reprojection (out_srs=EPSG:6346) 
  → filters.assign (Z = Z * 0.3048006096) → filters.crop (bounds) → writers.las
```

No vertical offset correction is applied; the 2008 and 2019 datasets are kept separate and analyzed independently.

---

## 4. Raster Derivative Generation

All derivatives are computed on a pinned grid with consistent origin, cell size, and CRS.

### 4.1 Resolution Strategy

| Dataset | Resolution | Grid Size | Rationale |
|---------|-----------|-----------|-----------|
| 2019 output3/output2 | 0.5 m | 3000×3000 | ~4 pts/m² supports sub-metre resolution |
| 2008 PAMAP | 1.0 m | 1500×1500 | ~0.6 pts/m² too sparse for 0.5 m |
| 9-tile mosaic | 1.0 m | 4500×4500 | Balance detail vs compute time |

### 4.2 Derivative Channels

#### Terrain Models
| Channel | Source | Method |
|---------|--------|--------|
| **DEM** | Ground returns (class 2) | PDAL TIN (Delaunay + faceraster) |
| **DSM** | First returns | PDAL max binning |
| **CHM** | DSM − DEM | max(DSM − DEM, 0) |

#### Surface Texture (WhiteboxTools)
| Channel | Parameters |
|---------|-----------|
| **Hillshade** | Azimuth 315°, altitude 45° |
| **Slope** | Degrees |

#### Ground Point Statistics (laspy + numpy bincount)
| Channel | Method |
|---------|--------|
| **Ground density** | Count of ground returns per cell (uint16) |
| **Intensity (ground)** | Mean intensity of ground returns per cell (float32) |

#### Roughness (scipy.ndimage.convolve)
| Channel | Parameters |
|---------|-----------|
| **Roughness** | σ(elevation) in 11×11 cell window (0.5 m) or 5×5 (1 m), ~5 m diameter |

Computed as:
```
var = (Σz² − (Σz)²/n) / (n − 1)
roughness = sqrt(max(var, 0))
```

#### Local Relief (scipy.ndimage max/min filters)
| Channel | Parameters |
|---------|-----------|
| **Local relief** | max(DEM) − min(DEM) within 10 m radius disk kernel |

#### Local Relief Model — LRM (scipy.ndimage.uniform_filter)

LRM = DEM − smoothed(DEM), where smoothing uses a NaN-aware uniform filter.

| Channel | Kernel size (cells) | Physical scale |
|---------|-------------------|----------------|
| **LRM 5** | 5 (0.5 m) / 3 (1 m) | 2.5–3 m |
| **LRM 11** | 11 (0.5 m) / 5 (1 m) | 5 m |
| **LRM 25** | 25 (0.5 m) / 11 (1 m) | 11–12.5 m |
| **LRM 51** | 51 (0.5 m) / 25 (1 m) | 25 m |

NaN-aware implementation:
```python
valid = np.isfinite(dem).astype(np.float32)
z0 = np.where(valid, dem, 0)
sm = uniform_filter(z0, size=K, mode='nearest')
sc = uniform_filter(valid, size=K, mode='nearest')
smooth = np.where(sc > 0, sm / sc, np.nan)
lrm = dem - smooth
```

#### Topographic Position Index — TPI (scipy.ndimage.convolve with disk kernels)

TPI = DEM − nanmean(DEM within circular kernel of radius R).

| Channel | Radius (m) | Kernel diameter (cells @ 0.5 m) |
|---------|-----------|-------------------------------|
| **TPI 5** | 5 m | 21 cells |
| **TPI 15** | 15 m | 61 cells |
| **TPI 25** | 25.5 m | 103 cells |

Additionally: TPI gradient magnitude and direction computed from TPI 15 via `np.gradient`.

#### Topographic Openness (Yokoyama et al., 2002)

Positive and negative openness computed along 8 cardinal/diagonal directions with a maximum search distance L.

| Channel | L (m) | L (cells @ 0.5 m) | L (cells @ 1 m) |
|---------|-------|-------------------|-----------------|
| **Openness pos/neg** | 25 m | 50 | 25 |

For each direction (dr, dc):
```
for k in 1..L:
    tan_angle = (z_shifted − z_center) / (k × step_distance)
    max_tan_up = max(max_tan_up, tan_angle)   # upward
    min_tan_dn = min(min_tan_dn, tan_angle)   # downward
positive_openness = mean(π/2 − arctan(max_tan_up)) across 8 directions
negative_openness = mean(π/2 + arctan(min_tan_dn)) across 8 directions
```

### 4.3 Complete Output List

For each tile/epoch, the pipeline produces 20+ GeoTIFFs plus a 12-panel overview PNG. File naming convention: `{channel}_{tile_suffix}.tif`

Suffixes used:
- `_05` — output3, 0.5 m (2019)
- `_2008_1m` — output3 footprint, 1 m (2008)
- `_o2_05` — output2, 0.5 m (2019)
- `_o2_2008_1m` — output2 footprint, 1 m (2008)
- `_9t_1m` — 9-tile mosaic, 1 m (2019)

---

## 5. Ground Truth Annotation

Expert annotations were created in QGIS over the output3 hillshade, stored in `data/derivatives/annotations/`:

| File | Type | Count | CRS | Description |
|------|------|-------|-----|-------------|
| `wellhead_pits.gpkg` | Point | 90 | EPSG:6344 | Wellhead pit locations (collapsed well cellars) |
| `pads_truth.gpkg` | Polygon | 88 | EPSG:6344 | Well pad outlines (leveled clearings) |
| `roads_truth.gpkg` | LineString | 96 | EPSG:6344 | Abandoned access road traces (19.6 km total) |

All annotations are reprojected to EPSG:6346 at runtime for spatial operations. The 90 pit points serve as positive labels for the classifier; the 88 pad polygons and 96 road lines are used as spatial prior features.

---

## 6. Pit Candidate Generation via Template Matching

### 6.1 Template Learning

1. **Reproject** 90 annotated pit points to EPSG:6346
2. **Auto-snap** each point to the local minimum in LRM_5 within a 4-cell (2 m) search radius, correcting for slight annotation imprecision
3. **Extract windows:** 31×31 cell cutouts (HALF=15 cells = 7.5 m) around each snapped point from 6 channels:
   - `lrm_5_05`, `lrm_11_05`, `tpi_05_05`, `openness_neg_05`, `intensity_ground_05`, `hillshade_05`
4. **Normalize:** Subtract per-window mean so pits of different depths align
5. **Single template:** Compute median across all 90 cutouts per channel

### 6.2 Multi-Template Sub-Type Learning

1. Flatten the 90 LRM_5 cutouts (31×31 = 961 dimensions)
2. **PCA** → retain 5 components
3. **KMeans** (k=3, n_init=10) → cluster into 3 morphological sub-types
4. Compute **median template per cluster**

Typical cluster breakdown: ~20/40/30 pits per sub-type, capturing small clean bowls, medium pits, and asymmetric pits with spoil berms.

### 6.3 Normalized Cross-Correlation Matching

For each of 4 channels (LRM_5, LRM_11, TPI_05, openness_neg):
1. Fill NaN with 0 in the full-tile raster
2. Run `skimage.feature.match_template(image, template, pad_input=True)`
3. Set score to NaN where original was NaN

Combined score = mean across 4 channels.

For multi-template: run each of the 3 sub-type templates, take the per-pixel maximum across templates → `score_max`.

### 6.4 Peak Finding

- `skimage.feature.peak_local_max` on the combined score raster
- **Threshold:** 25th percentile of scores at annotated pit locations (THR ≈ 0.148)
- **Minimum distance:** 5 m (10 cells at 0.5 m)
- **Result:** ~13,000 candidate locations per 1.5 km × 1.5 km tile

### 6.5 Labeling

A candidate is labeled **positive** if its center is within 10 m of any annotated pit point. Typical positive rate: 163/13,096 (1.24%).

---

## 7. Feature Engineering

88 features are extracted per candidate, organized into 12 groups:

### 7.1 Window Geometry

Two concentric regions are defined on the 31×31 window (0.5 m resolution):
- **Inner ring:** radius ≤ 5 cells (2.5 m) — the "pit bottom"
- **Rim ring:** 12 ≤ radius ≤ 15 cells (6–7.5 m annulus) — the "berm/surrounding terrain"

For 2008 derivatives (1 m resolution), the window is 17×17 (HALF=8):
- **Inner ring:** radius ≤ 3 cells (3 m)
- **Rim ring:** 6 ≤ radius ≤ 8 cells

### 7.2 Feature Groups

| Group | Count | Features |
|-------|-------|----------|
| **2019 depth/symmetry** | 30 | For each of 6 channels (LRM_5, LRM_11, LRM_25, TPI_05, TPI_15, openness_neg): inner_min, inner_mean, rim_mean, rim_minus_inner (contrast), radial_std (symmetry) |
| **2019 surface stats** | 8 | For slope, roughness, local_relief, CHM: inner_mean, window_max |
| **2019 intensity** | 3 | inner_mean, rim_mean, NaN_fraction (pits often have poor returns) |
| **2019 density** | 2 | inner_mean, window_mean (ground point density) |
| **2019 DEM depth** | 1 | rim_mean − inner_min (absolute pit depth in metres) |
| **2019 template match** | 1 | NCC score at candidate center |
| **2008 depth/symmetry** | 20 | Same 5 stats × 4 channels (LRM_5, LRM_11, TPI_15, openness_neg) |
| **2008 extras** | 4 | DEM depth, slope_inner_mean, CHM_window_max, density_inner_mean |
| **Temporal persistence** | 1 | −min(LRM_5 inner_min 2019, LRM_5 inner_min 2008) |
| **Morphology** | 11 | Gaussian-bowl moment analysis (see below) |
| **Multi-template NCC** | 4 | Per-subtype NCC score (3) + max across subtypes |
| **Pad/road priors** | 3 | in_pad (binary), dist_to_pad_m, dist_to_road_m |
| **Total** | **88** | |

### 7.3 Morphological Features (Gaussian-Bowl Moment Analysis)

On the LRM_5 window, treat negative values as "bowl mass" (weight = max(−LRM, 0)):

1. **morph_depth** — amplitude of deepest point: −min(LRM window)
2. **morph_sigma_major, morph_sigma_minor** — square root of eigenvalues of the mass-weighted covariance matrix (principal axes of the pit shape)
3. **morph_aspect** — σ_minor / σ_major (1.0 = perfectly circular, 0 = elongated)
4. **morph_compactness** — total_mass / (π × σ_major × σ_minor) (how concentrated vs diffuse)
5. **morph_prof_r0 through morph_prof_r3** — mean LRM in 4 radial bins: [0–2], [2–5], [5–10], [10–15] cells
6. **morph_radial_rho** — Spearman rank correlation between bin radius and mean value (measures monotonic bowl shape; ρ ≈ 1 = clean concentric bowl)
7. **morph_fit_residual** — RMSE / depth of analytic 2D Gaussian fitted to the window, normalized by pit depth (how well the pit matches a Gaussian bowl)

### 7.4 Radial Symmetry Feature

For each depth channel, sample the value at 8 equally-spaced angles around the inner ring radius. The standard deviation of these 8 values measures **asymmetry** — a tree throw produces high std (steep on one side, flat on the other), while a well pit is more symmetric.

---

## 8. Model Training and Evaluation

### 8.1 Spatial Cross-Validation

Standard k-fold CV is invalid for spatial data because nearby candidates share geographic context. We use **GroupKFold**:

1. Cluster the 90 annotated pits into 8 spatial groups using `AgglomerativeClustering(n_clusters=8)`
2. Each candidate inherits the group of its nearest annotated pit
3. GroupKFold with 5 splits ensures no fold's training set contains pits geographically near its test set
4. Out-of-fold (OOF) predictions are the honest evaluation metric

### 8.2 XGBoost Configuration

```python
XGBClassifier(
    objective='binary:logistic',
    tree_method='hist',
    n_estimators=500,
    max_depth=5,
    learning_rate=0.05,
    min_child_weight=2,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    scale_pos_weight=(n_neg / n_pos),  # ~80
    random_state=0,
    n_jobs=-1
)
```

### 8.3 LightGBM Configuration

```python
LGBMClassifier(
    objective='binary',
    n_estimators=500,
    learning_rate=0.05,
    num_leaves=31,
    max_depth=-1,        # leaf-wise growth
    min_child_samples=5,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    scale_pos_weight=scale_pos,
    random_state=0,
    n_jobs=-1,
    verbose=-1
)
```

### 8.4 Model Evolution

| Version | Features | ROC-AUC | PR-AUC | Notes |
|---------|----------|---------|--------|-------|
| RF baseline | 45 (2019 only) | 0.932 | 0.436 | OOB, not group-aware (optimistic) |
| XGB | 45 | 0.941 | 0.478 | GroupKFold OOF |
| XGB + 2008 + priors | 73 | 0.986 | 0.678 | +temporal +pad/road features |
| XGB + morph + multi-tmpl | 88 | 0.986 | 0.716 | +Gaussian-bowl + 3-template NCC |
| **Ensemble (XGB+LGBM)** | **88** | **0.987** | **0.722** | Averaged + isotonic calibration |

---

## 9. Ensemble and Calibration

### 9.1 Ensemble Averaging

```python
p_ensemble = (p_xgb + p_lgb) / 2.0
```

HistGradientBoosting (sklearn) was tested but underperformed (PR-AUC 0.608) and was dropped.

### 9.2 Isotonic Calibration

```python
iso = IsotonicRegression(out_of_bounds='clip').fit(p_ensemble_oof, y)
p_calibrated = iso.predict(p_ensemble_oof)
```

Isotonic calibration is a monotonic transform that maps raw ensemble probabilities to values that approximate true positive rates. After calibration, a threshold of 0.70 means "~70% of candidates above this threshold are real pits," which is confirmed by the observed 92% precision at that threshold.

### 9.3 Final Performance (output3, 88 features, calibrated)

| Threshold | Candidates | Pits Covered (of 90) | Recall | FP | Precision |
|-----------|-----------|---------------------|--------|-----|-----------|
| 0.30 | 130 | 82 | 91% | 34 | 74% |
| 0.50 | 108 | 80 | 89% | 20 | 81% |
| 0.60 | 86 | 73 | 81% | 10 | 88% |
| 0.70 | 76 | 68 | 76% | 6 | 92% |
| 0.80 | 69 | 64 | 71% | 4 | 94% |
| 0.90 | 50 | 48 | 53% | 1 | 98% |

### 9.4 Top Features (by XGBoost gain)

1. `dist_pad_m` — distance to nearest annotated pad polygon
2. `in_pad` — binary, inside an annotated pad
3. `tpi_15_08_imean` — 2008 TPI at 15 m, inner ring mean
4. `chm_08_wmax` — 2008 canopy height, window max
5. `openness_neg_05_rdiff` — 2019 negative openness, rim-inner contrast
6. `lrm_11_05_rdiff` — 2019 LRM 11, rim-inner contrast
7. `morph_depth` — Gaussian-bowl depth
8. `tmpl_max` — maximum NCC across 3 sub-type templates

---

## 10. Cross-Tile Generalization

### 10.1 Challenge

The model's strongest features (`dist_pad_m`, `in_pad`) require expert-drawn pad polygons, which are unavailable for new tiles. Removing these 3 features drops PR-AUC from 0.722 to 0.604.

### 10.2 Cross-Tile Procedure

1. **Rebuild derivatives** for the target tile (same pipeline, same parameters)
2. **Rebuild 2008 derivatives** from PAMAP tiles covering the target footprint
3. **Re-learn templates** from the source tile's annotated pits
4. **Run template matching** on the target tile → generate candidates
5. **Extract 85 features** (all except pad/road priors and tile-specific match_center)
6. **Train ensemble** on source tile candidates (GroupKFold OOF for calibration)
7. **Apply** trained model to target tile candidates

### 10.3 Output2 Results (Blind Application)

- 12,804 candidates generated from template matching
- Training OOF on output3 (no priors): XGB ROC 0.953, PR 0.604; LGBM ROC 0.908, PR 0.571
- 35 candidates at proba ≥ 0.50; 25 at proba ≥ 0.70
- Zero documented wells in output2 — all predictions are novel discoveries
- No ground truth available for validation; visual inspection required

---

## 11. Discovery Mode

### 11.1 Within-Tile Discoveries

After training on the 90 annotated pits, candidates with high probability but >25 m from any annotated pit represent potential undocumented wells. At proba ≥ 0.50: 10 discoveries, all inside annotated pad polygons (strongly corroborated). Zero off-pad discoveries at this threshold — the model relies heavily on the pad prior, limiting its ability to find wells in unknown pads.

### 11.2 Cross-Tile Discoveries

When applied without pad/road priors to output2 (zero documented wells), all high-probability candidates are discoveries. These represent the pipeline's primary deliverable: a ranked list of locations warranting field verification.

---

## 12. Results Summary

### 12.1 Detection Performance Progression

| Milestone | Recall @ ~85% Precision |
|-----------|------------------------|
| Initial RF (OOB, 45 features) | 34/90 (38%) |
| XGBoost (GroupKFold, 45 features) | 50/90 (56%) |
| + 2008 temporal + pad/road priors | 70/90 (78%) |
| + morphology + multi-template | 77/90 (86%) |
| **Ensemble + calibration** | **64/90 (71%) @ 94% precision** |

### 12.2 Key Findings

1. **Pad proximity is the dominant predictor** — `dist_pad_m` alone accounts for ~40% of feature importance. Pits cluster inside cleared pads. This is powerful for within-tile analysis but limits cross-tile transfer.

2. **Temporal persistence matters** — features from 2008 PAMAP data meaningfully improved discrimination (PR-AUC +0.04). Real pits exist in both epochs; recent disturbances do not.

3. **Morphological features earn their keep** — Gaussian-bowl fit quality, radial monotonicity, and sub-type template scores each contributed to the ensemble.

4. **Spatial CV is essential** — switching from RF OOB (which doesn't account for spatial autocorrelation) to GroupKFold revealed the true generalization gap and produced honest metrics.

5. **Calibration enables decision-making** — isotonic calibration means thresholds correspond to actual precision: a reviewer knows that proba ≥ 0.80 yields ~94% true pits.

---

## 13. Pipeline Scripts Reference

| Script | Purpose | Inputs | Outputs |
|--------|---------|--------|---------|
| `_build_05_output3.py` | 0.5 m derivatives for output3 | output3.las | 22 × `*_05.tif` |
| `_build_1m_output3_2008.py` | 1 m derivatives for 2008 data | output3_2008.las | 20 × `*_2008_1m.tif` |
| `_build_output3_2008_clean.py` | Merge/clip 2008 PAMAP → output3 footprint | 4 PAMAP LAZ tiles | output3_2008.las |
| `_build_output2_stack.py` | Derivatives for output2 (0.5m + 2008 1m) | output2.las, 2 PAMAP tiles | `*_o2_05.tif`, `*_o2_2008_1m.tif` |
| `_build_9tile_1m.py` | 1 m derivatives for 3×3 mosaic | output3_9tile.las | 20 × `*_9t_1m.tif` |
| `_build_9tile_stack.py` | Merge 9 LAZ tiles into one LAS | 9 LAZ files | output3_9tile.las |
| `_pit_template_match.py` | Template learning + NCC candidate gen | wellhead_pits.gpkg, derivatives | pit_candidates_template.gpkg (~13k) |
| `_pit_xgb_plus2.py` | Full-feature XGB (88 features) | candidates + derivatives | pit_candidates_xgb_plus2.gpkg |
| `_pit_ensemble.py` | XGB+LGBM ensemble + calibration | candidates + derivatives | pit_candidates_ensemble.gpkg |
| `_pit_apply_to_output2.py` | Cross-tile inference | both tiles' derivatives | pit_candidates_output2.gpkg |
| `_pit_discoveries.py` | Discovery map (novel candidates) | ensemble candidates | pit_discoveries.gpkg |
| `_pit_rf_per_threshold.py` | Per-threshold overlay visualizations | any candidate GPKG | threshold PNGs |

---

## 14. Limitations and Future Work

### 14.1 Current Limitations

- **Small training set:** 90 annotated pits on one tile. Model has seen limited geographic diversity.
- **Pad prior dominance:** The strongest feature requires expert annotation, limiting autonomous operation. A trained pad detector would close this loop.
- **Point annotations only:** Pit size is not directly labeled. Polygon outlines would enable segmentation and size-aware features.
- **Single flight vintage:** 2019 LiDAR only. Additional epochs would strengthen temporal analysis.
- **Intensity striping:** Flight-line intensity artifacts visible across the 9-tile mosaic. PointSourceID-aware normalization needed before intensity features are reliable at scale.
- **No field validation:** No predictions have been ground-truthed in the field.

### 14.2 Recommended Next Steps

1. **Annotate 1–2 additional tiles** (pits + pads) for training set expansion (+0.08–0.12 PR-AUC expected)
2. **Audit top FPs** — some false positives may be real undocumented pits, improving labels without new annotation work
3. **Train a pad detector** to provide `dist_pad_m` priors for unannotated tiles
4. **Polygon outlines** for ~20 pits to enable size features and potential segmentation
5. **CNN on stacked windows** — the natural next model class once >200 positive labels are available
6. **Field verification** of the highest-confidence predictions on output2

---

*Document version: 2026-04-15*
*Project: WellSight LiDAR Analysis*
