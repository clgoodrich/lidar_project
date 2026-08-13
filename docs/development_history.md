# WellSight Development History — Full Session Report

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

## Executive Summary

WellSight began as an exploratory effort to detect orphaned oil and gas wells in western Pennsylvania using airborne LiDAR data. Over the course of development, the project evolved from basic terrain visualization through template matching to a multi-model gradient-boosted ensemble, was applied across multiple geographic regions, and ultimately produced a pipeline capable of identifying candidate well pit locations from raw point cloud data with measurable precision and recall. This document traces that entire journey — what was tried, what worked, what failed, and what the results mean going forward.

---

## 1. Origins and Initial Setup

### Starting Point

The project started with two data files:
- `output2.las` — a 1.5 km × 1.5 km USGS 3DEP LiDAR tile from the 2019 Western PA flight (LAS 1.4, point format 7, ~9M points, EPSG:6346 / UTM 17N)
- `output_wells.csv` — 84 PA DEP orphaned well records with coordinates

The study area is in Venango County, Pennsylvania — the birthplace of the American oil industry (Drake Well, 1859). The terrain is Appalachian Plateau: moderate slopes, deeply incised stream valleys, and dense deciduous forest covering 150+ years of oil and gas extraction history.

### The Core Problem

Pennsylvania has an estimated 200,000+ undocumented abandoned oil and gas wells. The PA DEP has records for only ~8,840 orphaned wells statewide. These wells leak methane, contaminate groundwater, and pose physical hazards. Finding them is the first step toward remediation, but they're hidden under forest canopy and often the only surface evidence is a subtle circular depression where the well cellar collapsed — typically 1-5 meters across and less than a meter deep.

### Early Decisions

The project adopted Python as the primary language with PDAL (CLI via subprocess, since Python bindings don't function in this environment), WhiteboxTools for hillshade/slope, and scipy/numpy for terrain derivatives. A documentation-first rule was established: project scope, data dictionary, and LAS inspection report were created before any processing code.

The LAS file was later renamed to `output3.las` when the project scope expanded, and the well dataset was updated to `output_wells_2.csv` (107 wells).

### The CLAUDE.md Confusion

An early friction point: the project instructions file (`CLAUDE.md`) loaded into the session context was different from the one on disk. The user had rewritten it as a comprehensive "WellSight LiDAR Analysis Agent" formation prompt, but the session was operating from an older version with different instructions (including references to a "5x5" analysis that didn't exist). This caused confusion about scope and approach until the user explicitly said to discard the session context and rely on the on-disk file. Lesson: always verify which instructions are actually active.

### Scope Creep and Course Corrections

Multiple times early on, the user had to rein in the scope. The agent was generating validation frameworks, multi-phase analysis plans, and documentation before any actual detection was done. Key user feedback:
- *"I feel we might be getting too far ahead. We're just doing the pad footprint itself, right?"*
- *"Yeah, we got too far ahead. Start just from having done preprocessing."*
- *"Ughhh see, this is frustrating. Because I can look at the hillshade and I can SEE the wells, I can SEE the old well pads, I can SEE the old roads. But I don't know how to accurately quantify it."*

This frustration — being able to visually identify features but lacking the tools to systematically detect them — drove the entire project forward.

---

## 2. Terrain Derivative Generation

### The 1m Stack

The first processing step was generating a raster derivative stack from the LiDAR point cloud. Initial derivatives were built at 1m resolution:
- **DEM** via PDAL TIN interpolation (Delaunay + faceraster) over ground-classified returns
- **DSM** from first-return maximum
- **CHM** (Canopy Height Model) = DSM − DEM
- **Hillshade** and **slope** via WhiteboxTools
- **Ground density** and **mean intensity** via laspy bincount

### Adding Terrain Analysis Channels

The derivative stack grew to include curvature and position indices computed in Python (scipy.ndimage):
- **Local Relief Model (LRM)** at 4 scales (5, 11, 25, 51 cell kernels) — highlights residual micro-topography after trend removal
- **Topographic Position Index (TPI)** at 3 radii (5m, 15m, 25.5m) — measures whether a point is higher or lower than its surroundings
- **Topographic openness** (Yokoyama et al., 2002) at 25m search distance — positive openness reveals ridges, negative reveals depressions
- **Roughness** (elevation standard deviation in 11-cell window)
- **Local relief** (max − min in 10m disk)

### PointSourceID Investigation

The user noticed weird linear artifacts in the num_returns_mean raster and asked: *"What's up with the weird linear artifacts?"* Investigation revealed these were flight-line overlaps: the tile had data from two flight lines (PointSourceID 637 and 640) with different scan angles and slightly different intensity calibrations. PSI-aware rasters were generated to diagnose the issue, and per-PSI normalization was investigated. Ultimately, the intensity/return-count channels proved uninformative for pit detection, so the flight-line issue became moot.

### The Stacking Question

The user asked a prescient question: *"If I had more lidar swaths from previous or other missions over that same area, would merging/stacking them be a good idea or bad?"* The answer was that stacking could increase point density and provide temporal change detection, but vertical/horizontal alignment between flights would be challenging. This led to the 2008 PAMAP integration attempt (see Section 7).

### Resolution Upgrade to 0.5m

With ~4 ground returns per m², the data supported 0.5m resolution (3000×3000 cells per tile). This doubled the spatial detail and made sub-metre pit features resolvable. The 0.5m stack became the primary working resolution for the output3 tile. All derivative naming adopted a `_05` suffix convention.

### Flight-Line Artifacts

Intensity and ground density rasters showed strong diagonal striping from overlapping flight lines (PointSourceID 637 vs 640). The scan angle in LAS 1.4 point format ≥6 is stored as int16 × 0.006°, not raw degrees — an early bug where "|angle|≤10" kept only 0.3% of points was traced to this unit confusion. PSI-aware normalization was investigated but ultimately the intensity channel proved uninformative for pit detection anyway.

---

## 3. Ground Truth Annotation

### Learning QGIS

The user was not familiar with QGIS. Directions were provided for loading layers, styling, and creating annotation layers. Key questions the user asked during annotation:
- *"Should I outline the pad perfectly, or outline it in a way that encapsulates it?"* — Answer: encapsulate it; the model needs the full extent, not surgical precision.
- *"Do the roads need to be interconnected?"* — Answer: no; individual segments are fine.

This matters for reproducibility: the annotations reflect a non-GIS-expert's best judgment of visible terrain features, not a surveyor's precise delineation.

### Expert Annotation in QGIS

The hillshade immediately revealed what the numbers couldn't: you could SEE the old well pads, roads, and pit depressions in the terrain. But quantifying what was visible required manual annotation.

Three layers were created in QGIS:
- **wellhead_pits.gpkg** — initially 90 point locations marking visible pit depressions (later expanded to 675)
- **pads_truth.gpkg** — 88 polygons outlining well pad clearings
- **roads_truth.gpkg** — 96 line features tracing abandoned access roads (19.6 km total)

### Annotation Philosophy

A key early decision: annotate just the pit center point, not the full polygon outline. This was faster (90 pits vs days of polygon tracing) and sufficient for template learning and classification. The tradeoff was losing explicit size information per pit — the model had to learn size implicitly from the window features.

The user's annotations focused on features they were "conclusively sure" were pits. Many documented DEP well coordinates were obviously wrong (off by 50-500m), so the expert annotations became the primary ground truth rather than the DEP records.

---

## 4. Initial Detection Approaches

### Pad Detection — The First Target (Abandoned)

The first detection target was well pads, not pits. The user's initial vision was finding the flat cleared areas where drilling rigs once stood. A rule-based pad detector was built iterating through versions v0.1 to v0.5 with increasingly complex filters:
- v0.1–v0.3: Simple thresholds on roughness < threshold, LRM < threshold, slope < 5 degrees
- v0.4–v0.5: Added area ≥ 80 m², compactness ≥ 0.45, rectangularity ≥ 0.70, aspect ratio ≥ 0.50

Results were consistently poor — the shapes were too irregular. The user's feedback was direct: *"I'm not gonna lie, I ain't seeing it. These shapes are waaay too irregular."* The approach tried different thresholds, multiplicative vs cubed scaling of parameters, but the fundamental problem was that 150-year-old well pads don't maintain regular geometric shapes under decades of forest regrowth. This was abandoned.

### Road Detection — The Linear Signature Discovery

During pad detection, linear features became obvious in the LRM and hillshade — old haul roads cutting through the forest. A dedicated road detector was built:
- **v0.1–v0.5:** Hand-tuned rules on LRM, slope, TPI
- **v0.6–v0.10:** Meijering ridge filter (`skimage.filters.meijering`) on negative LRM to enhance tubular/linear features
- **Final (v0.10):** Random Forest with 12 features including openness_pos (top feature, 0.21 importance), tpi_05 (0.12), lrm_25 (0.11). OOB accuracy 0.92.

Results: 29% road recall (5,609m of 19,315m length-weighted), 53% precision. 101 road segments detected, 15 "probable" and 86 "candidate." This was interesting but not the core objective — the user wanted wells, not roads.

### Blob Detection for Pits (03c)

An early pit detector used `skimage.feature.blob_log` on negative LRM at multiple scales (LRM_5 and LRM_11), followed by a Random Forest classifier on per-blob features (depth_lrm5, depth_lrm11, dem_cut_m, circularity_std, mean_slope, roughness, tpi, relief, intensity, radius, scale). OOB accuracy 0.92, top features: depth_lrm11 (0.23), depth_lrm5 (0.15), dem_cut_m (0.12).

It produced 48,449 raw blob candidates → 2,387 after proba ≥ 0.5, hitting 26/90 annotated pits (29% recall). This was a starting point but clearly insufficient.

### The User's Key Question

The user asked: *"Is it possible to use these [pit annotations] as some sort of training image through scipy or somesuch that we can generate a common morphology?"* This question led directly to the template matching approach that became the core of the pipeline. The user also asked whether they needed to go back to QGIS and fully outline each pit — the answer was no, points alone were sufficient for template learning.

---

## 5. Template Matching — The Breakthrough

### Learning the Pit Morphology

The key insight came from asking: can we learn what a pit looks like from the 90 annotated examples, then scan the entire tile for similar shapes?

**Template learning process:**
1. Reproject 90 pit points to UTM
2. Auto-snap each to the local LRM_5 minimum within 2m (corrects slight annotation imprecision)
3. Extract 31×31 cell windows (15.5m at 0.5m) from 6 channels
4. Subtract per-window mean (normalizes for varying pit depths)
5. Compute median across all 90 cutouts → the "canonical pit template"

The resulting template showed a clear central depression surrounded by a slight outer rim — the classic collapsed well cellar signature. This morphology was visible in LRM_5, LRM_11, TPI_05, and negative openness.

### Multi-Template Sub-Types

Clustering the 90 cutouts via PCA(5) + KMeans(3) revealed three morphological sub-types:
- **Type 0** (~20 pits) — small, weak outer rim
- **Type 1** (~40 pits) — the classic clean bowl
- **Type 2** (~30 pits) — asymmetric, with a spoil/berm mound on one side

Building a median template per cluster and matching with the best of three produced better NCC scores than a single template.

### Candidate Generation

Normalized cross-correlation (`skimage.feature.match_template`) was run on 4 channels (LRM_5, LRM_11, TPI_05, openness_neg), averaged, and peaks were extracted with `peak_local_max` (NMS radius 5m). The threshold was set at the 25th percentile of NCC scores at the 90 annotated pits.

**Result: ~13,000 candidates per 1.5km × 1.5km tile.** At this stage, 88/90 annotated pits were within the candidate set (98% recall), but precision was only 1.2% (163 positives in 13k candidates). Template matching alone cast a very wide net — ML was needed to separate real pits from look-alikes.

---

## 6. Machine Learning — Model Evolution

### v1: Random Forest Baseline

The first ML model was a Random Forest with 45 features (2019 derivatives only), using OOB scoring. Results looked promising: OOB accuracy 0.99, ROC-AUC 0.93, PR-AUC 0.44. At the best operating point, 34/90 pits recovered at 89% precision.

**Problem:** OOB scoring on bagged trees doesn't account for spatial autocorrelation. Nearby candidates share geographic context, so the OOB estimate was optimistic.

### v2: XGBoost with Spatial Cross-Validation

Switching to XGBoost with GroupKFold spatial CV (8 spatial clusters of pits, 5 folds) gave honest OOF predictions. Results: ROC-AUC 0.94, PR-AUC 0.48. At 88% precision, recall was 56% (50/90 pits) — significantly worse than the RF's optimistic 89%, but honest.

**Hard-negative mining was attempted:** up-weight the top 2% of FPs and retrain. It was tried for 2 rounds but **reduced PR-AUC both times**. The negatives were already well-separated; mining confused the model. This was abandoned.

### v3: Adding 2008 Temporal Data + Pad/Road Priors

Two new feature groups were introduced:
1. **2008 PAMAP data** — the same area from the 2006-2008 PAMAP LiDAR program, reprojected from PA State Plane North (EPSG:2271) to UTM 17N, Z converted from US survey feet to metres. Built at 1m resolution (the 2008 data was too sparse for 0.5m at ~0.6 pts/m²). Features: depth/rim/symmetry on LRM_5, LRM_11, TPI_15, openness_neg from the 2008 epoch.
2. **Pad/road priors** — binary `in_pad`, `dist_to_pad_m`, `dist_to_road_m` from the expert annotations.

**Stacking the 2008 and 2019 point clouds was tried first** (merging into one LAS, building derivatives on the combined cloud). This didn't work — there was a terrain-dependent vertical bias of +2m between the two epochs that couldn't be cleanly removed. A spatial high-pass filter was attempted but the user decided to abandon stacking and keep the datasets separate. The 2008 data was used purely as temporal-comparison features.

**Results: PR-AUC jumped from 0.48 to 0.68** — the single biggest improvement in the project. The temporal persistence feature (`both_depths`) and the pad proximity feature (`dist_pad_m`) were responsible. `dist_pad_m` became the #1 feature by importance (~25-30% of total gain).

### v4: Morphological Features + Multi-Template NCC

Two more feature groups:
1. **Gaussian-bowl morphology (11 features):** Treat negative LRM values as "bowl mass," compute center of mass, covariance eigenvalues (σ_major, σ_minor), aspect ratio, compactness, radial depth profile in 4 bins, Spearman radial monotonicity (ρ), and normalized fit residual.
2. **Multi-template NCC (4 features):** Per-subtype NCC score from the 3 learned templates + the maximum.

**PR-AUC: 0.68 → 0.72.** Modest gain. The morphological features earned their keep — `morph_depth`, `morph_radial_rho`, and `morph_fit_residual` all placed in the top 20 features. The multi-template scores were less impactful but contributed to ensemble diversity.

### v5: Ensemble + Isotonic Calibration (Final Best)

Three gradient-boosted models were trained with GroupKFold OOF:
- **XGBoost** — ROC 0.986, PR 0.716
- **LightGBM** — ROC 0.986, PR 0.712
- **HistGradientBoosting (sklearn)** — ROC 0.960, PR 0.608

HGB underperformed significantly and was dropped. The final ensemble averaged XGB + LGBM probabilities, then applied isotonic regression for calibration.

**Final: ROC-AUC 0.987, PR-AUC 0.722.** At proba ≥ 0.70: 76 candidates, 68/90 pits recovered (76% recall), 6 FPs (92% precision). At proba ≥ 0.90: 50 candidates, 48 pits, 1 FP (98% precision).

---

## 7. Cross-Tile Generalization

### The Prior Problem

The model's strongest feature (`dist_pad_m`) required expert-drawn pad polygons, which are unavailable for new tiles. Removing pad/road priors dropped PR-AUC from 0.722 to 0.604. This was the fundamental tension: the model worked well where it had annotations, but those annotations were exactly what you wouldn't have on a new tile.

### Output2 (Adjacent Tile)

The first cross-tile test: train on output3 (without priors), apply to the adjacent 1.5km tile (output2). Zero documented wells in output2. Result: 35 candidates at proba ≥ 0.50, 25 at ≥ 0.70. No ground truth to validate against — all predictions were discoveries by definition.

### Washington County / Sep Area (6km × 6km, Different Terrain)

A 16-tile mosaic from a different region (southwestern PA, Washington County) was processed. Land cover analysis revealed the problem: only 30% forest (vs 97% in the training area), with 28% agriculture and 11% developed land. The model, trained entirely on dense forest, was extrapolating on 70% of the landscape. Results: 101 candidates at proba ≥ 0.50, but precision was unknown.

### McKean County (120 km NE, Same Terrain Type)

McKean County — highest orphan well count in PA (2,385 documented) — was chosen as a geographically distant but ecologically similar test site. A 3×3 tile grid (later expanded to 5×5, 23 tiles) was processed. The tiles were in a different CRS (EPSG:6350, Conus Albers) requiring reprojection to UTM 17N.

Results were weaker than expected: at proba ≥ 0.70, only 51 candidates (vs hundreds of known wells in the area). The model trained on Venango morphology didn't fully generalize to McKean's terrain.

---

## 8. Scaling Up Training Data

### From 90 to 675 Pits

The user annotated pits across the full 9-tile Venango mosaic (538 pits) and the McKean tile (137 pits), bringing the total to 675 expert-annotated pit locations.

**Results with 675 pits:**
- **9-tile (Venango):** 248 pits recovered at proba ≥ 0.50 (75% precision), 104 at ≥ 0.70 (91% precision)
- **McKean:** Only 24 pits at proba ≥ 0.50 (38% precision), 1 at ≥ 0.70

The McKean performance was disappointing — the model trained predominantly on Venango pits (538/675) still couldn't reliably generalize to McKean morphology, despite both areas being forested Appalachian Plateau.

### Adding Land Cover Features

High-resolution (1m) land cover data was clipped for each study area from county-level datasets (2022 UVM classification: tree canopy, low vegetation, structures, impervious, roads, agriculture). Seven features were added: center class, and fraction of tree canopy, low vegetation, impervious, agriculture, canopy-over-infrastructure, and barren within a 15m window.

**Impact: minimal.** PR-AUC increased from 0.372 to 0.382. In densely forested areas, land cover has limited diversity — almost everything is class 3 (tree canopy). The main value was identifying the few candidates on impervious surfaces for rejection.

---

## 9. DEP Well Cross-Reference

### Snapping DEP Coordinates

The PA DEP oil and gas well shapefile (223,742 wells statewide, of which 27,392 are orphan/abandoned) was loaded and cross-referenced against annotated pits.

**Findings:**
- Only **31% of DEP wells land within 10m** of a visible LiDAR pit feature
- 62% within 25m — passable but not precise
- 9% (10 wells) have NO LiDAR feature within 100m — either wrong coordinates or fully remediated
- **87% of the 675 annotated pits have NO DEP well within 100m** — potentially undocumented wells
- Zero annotated pits are near detected active infrastructure

The DEP well database confirmed what was suspected: it's incomplete and imprecise for location work. The LiDAR-based approach finds features the state doesn't know about.

### High-Density Orphan Well Tiles

Two tiles with the highest DEP orphan well concentrations were identified:
- **Tile 616593** — 204 DEP orphan/abandoned wells, 7 km from training area
- **Tile 610594** — 163 DEP orphan/abandoned wells, 11 km west

Pipeline was run on both with DEP well overlay. Using raw scores (not calibrated — see Section 10), 616593 showed 87 candidates at raw ≥ 0.60, spatially correlating with the DEP well distribution. The model's predictions tended to cluster where DEP records existed, but also found locations without DEP records.

---

## 10. The Calibration Problem

### What Went Wrong

The isotonic calibration was fit on the training tile's OOF predictions, where the positive rate was ~1.2%. When applied to cross-tile predictions, the calibration compressed scores aggressively — the calibrated p99 on test tiles was only 0.12, meaning even the best candidates barely crossed the 0.50 threshold.

**The fix was simple:** use raw ensemble scores (`proba_raw`) instead of calibrated scores for cross-tile work. At raw ≥ 0.30, the model found meaningful numbers of candidates on all test tiles. The calibration remained useful for the training tile (where threshold semantics were validated) but was counterproductive for generalization.

This was a key lesson: **isotonic calibration is tile-specific.** Applying it cross-tile requires recalibration on the target domain, which requires labels — the thing you don't have.

---

## 11. Point Cloud Feature Analysis

### Eigenvalue-Based 3D Features

PDAL's `filters.covariancefeatures` was used to compute per-point 3D structural features from the 20 nearest ground-point neighbors:
- **Linearity** — how linear the local neighborhood is
- **Planarity** — how flat/planar
- **Scattering** — how scattered in 3D (sphericity)
- **Verticality** — how vertical the local surface normal is

### What Pits Actually Look Like in 3D

Comparing 101 pit locations against 2000 random ground locations:

**Genuinely distinctive (low overlap, strong signal):**

| Feature | Pit median | Random median | Overlap | p-value |
|---|---|---|---|---|
| **Scattering** | 0.063 | 0.028 | **32%** | 2e-32 |
| **Verticality std** | 0.083 | 0.029 | **21%** | 4e-35 |

**Marginally different (statistically significant but massively overlapping):**
- Planarity: 67% overlap
- Verticality mean: 74% overlap
- Linearity: 72% overlap
- Point density: 78% overlap

**Indistinguishable from background:**
- Intensity (92% overlap, p=0.2)
- Z-range (81% overlap, p=0.6)
- Return counts (86% overlap, p=0.2)
- Single return fraction (87% overlap, p=0.2)

### The Radial Scattering Ring

The user observed a ring pattern in the scattering visualization at pit locations — low scattering at the center, high on the walls, transitioning back to low. Radial profile analysis confirmed this:

| Distance from center | Scattering | Verticality | Elevation (relative) |
|---|---|---|---|
| 0.2 m (center) | 0.036 (low) | 0.076 (low) | 0.00 m |
| 1.2 m (inner wall) | 0.056 | 0.139 | +0.02 m |
| 2.8 m (outer wall) | 0.071 | 0.197 | +0.19 m |
| 4.5 m (rim) | 0.086 (peak) | 0.219 (peak) | +0.51 m |
| 6.0 m (beyond) | 0.076 (drops) | 0.192 (drops) | +0.60 m |

The scattering peaks at the **bowl walls** (3-5m from center), not the center or the surrounding terrain. This concentric gradient — rising from flat bottom through angled walls to rim, then falling back to flat — is the 3D point cloud signature of a collapsed well cellar. Random locations show flat profiles with no radial structure.

**For reporting:** Only scattering and verticality_std carry real pit-specific information from the raw point cloud. Everything else — intensity, return counts, scan angle — is within noise. The detection signal comes from terrain **shape**, not LiDAR **radiometry**.

---

## 12. Active Infrastructure Detection

### Structure Detection

An attempt was made to detect active well infrastructure (pumpjacks, tanks, wellheads) using a combination of:
- CHM (isolated above-ground objects in clearings)
- Reflective anomaly (intensity z-score × single-return fraction)
- Compact footprint (object smaller than a tree crown)

**Results:** 19 candidate structures detected on the McKean tile (2-10 m², 2-7m tall, bright, in clearings). Zero on the heavily forested output3 tile. The approach was very rough — it detected "bright compact structures in clearings" rather than confirmed pumpjacks — but provided a potential negative filter (candidates near active infrastructure are likely managed, not orphaned).

---

## 13. Bugs, Gotchas, and Technical Lessons

### Jupyter Notebook JSON Escaping

Writing notebooks directly via file write caused `\"` escapes to survive in metadata/strings, producing invalid JSON that Jupyter couldn't open. Fixed by building notebooks programmatically via `nbformat.v4.new_notebook()` in dedicated builder scripts (`_build_rf_nb.py`, `_build_pit_nb.py`, etc.).

### Scan Angle Unit Confusion (LAS 1.4)

In LAS 1.4 point format ≥ 6, `scan_angle` is stored as int16 × 0.006 degrees, not raw degrees. An initial filter of "|angle| ≤ 10" kept only 0.3% of points because the raw int16 values are in the hundreds/thousands. Fixed by multiplying by 0.006 before filtering.

### uniform_filter Returns Mean, Not Sum

Initial local z-score code treated `scipy.ndimage.uniform_filter` output as a sum, producing all-NaN results. The function returns the mean within the window. Fixed by rewriting with explicit mean formulas: `mean_valid = mean_a0 / frac_valid`.

### Vertical Alignment Between 2008 and 2019

First attempt at stacking the two epochs used a flat-area offset (−1.99m) derived from comparing DEMs in flat terrain. But the bias was terrain-dependent: flat areas showed +2m offset, ridges showed −2m. A spatial high-pass filter (200m uniform_filter smoothing subtracted from the raw diff) was applied, reducing the bias to p1/p50/p99 = −0.37/0.00/+0.48m. Ultimately the stacking approach was abandoned and the datasets were kept separate.

### Empty DataFrame KeyError

The pad detector's `detect()` function returned an empty DataFrame that was missing expected columns ('compactness', etc.). Fixed by padding empty returns with all expected columns.

### IndexError in Pit Detector Circularity

The circularity ring sampling in the pit detector (`safe_at`) pushed array offsets past the tile edge. Fixed by adding bounds checks.

### WhiteboxTools NoData Handling

WhiteboxTools hillshade/slope wrote NoData areas as actual int16 values (−9999) instead of flagging them as NoData in the GeoTIFF metadata. This caused QGIS to render NoData corners as solid black instead of transparent. Required post-processing: mask with the DEM's NaN pattern and rewrite as float32 with proper NoData flag.

### Windows File Locking

On Windows, rasterio holds file handles that prevent overwriting files that were recently read. Workaround: write to a temp file, close the original, then rename. Sometimes even this failed if QGIS had the file open — in those cases, writing to a new filename was the only option.

---

## 14. What Didn't Work (Approaches)

### Approaches Tried and Abandoned

1. **Pad detection (rule-based)** — shapes too irregular, rules too rigid. Abandoned early.
2. **Point cloud stacking (2019 + 2008)** — terrain-dependent vertical bias of +2m between epochs couldn't be cleanly removed. Spatial high-pass helped but user decided to keep datasets separate.
3. **Hard-negative mining** — up-weighting difficult FPs reduced PR-AUC. Abandoned after 2 rounds.
4. **HistGradientBoosting** — underperformed XGB and LGBM by ~0.10 PR-AUC. Dropped from ensemble.
5. **Isotonic calibration for cross-tile** — calibration fit on training OOF compressed scores too aggressively on new tiles. Raw scores work better cross-tile.
6. **Land cover as model feature** — minimal improvement (+0.01 PR-AUC) in forested areas.
7. **Kriging for point densification** — investigated but abandoned; TIN interpolation already uses all available information without adding any.

### Features That Proved Uninformative

- **LiDAR intensity** — no difference between pits and background (92% overlap)
- **Return counts / single-return fraction** — not a pit indicator
- **Scan angle** — not discriminative after proper unit conversion
- **Z-range (local)** — pits aren't distinguishable from natural terrain variability
- **Linearity (eigenvalue)** — no radial signature at pits; essentially flat profile

---

## 15. What Worked

### Key Technical Successes

1. **Template matching as candidate generation** — 98% recall at the candidate stage (88/90 pits in the candidate set). This set the recall ceiling for all downstream ML.

2. **Spatial cross-validation (GroupKFold)** — essential for honest evaluation. Exposed a 0.05 AUC gap that OOB missed. Every subsequent model improvement was validated honestly.

3. **2008 temporal features** — +0.04 PR-AUC. Real pits persist across decades; recent disturbances don't. The 2008 PAMAP data, despite being sparser and older, provided the single biggest feature-engineering improvement.

4. **Pad proximity priors** — the dominant feature (40% of importance). Pits cluster inside cleared well pads. This is powerful but limits autonomous operation.

5. **Morphological Gaussian-bowl fitting** — radial monotonicity (morph_radial_rho) and fit residual separate symmetric pits from asymmetric tree throws. Earned ~8% of feature importance.

6. **Ensemble averaging** — simple (XGB + LGBM) / 2 outperformed each model alone. No need for complex stacking.

7. **3D scattering signature** — the concentric ring pattern in eigenvalue-based scattering is a genuine physical signature of collapsed well cellars, independent of the raster-based features.

### Key Analytical Insights

1. **DEP well coordinates are unreliable** — only 31% land within 10m of visible features. 87% of annotated pits have no DEP record.

2. **The detection problem is shape, not reflectance** — intensity, return counts, and scan characteristics are uninformative. Only terrain geometry (LRM, TPI, openness) and 3D point structure (scattering, verticality) carry signal.

3. **Geographic generalization requires local training data** — a model trained on Venango performs poorly on McKean despite similar land cover. The diminishing returns curve suggests 150-300 pits across 2-3 tiles is the sweet spot.

4. **Calibration doesn't transfer** — isotonic calibration is tile-specific. Cross-tile work should use raw scores with empirical thresholds.

---

## 16. Current State and Outputs

### What Exists

**Derivative stacks built for:**
- Output3 (Venango) at 0.5m — 22 TIFs
- Output3 9-tile mosaic at 1m — 20 TIFs
- McKean 3×3 at 1m — 22 TIFs
- McKean 5×5 at 1m — 19 TIFs
- Output2 at 0.5m (derivatives deleted to save space)
- Sep area at 0.5m + 1m (derivatives deleted)
- Two standalone tiles (616593, 610594) at 1m

**Model outputs:**
- 21 candidate GPKGs across all model versions and regions (archived in `model_archive/`)
- Per-threshold overlay PNGs for all major runs
- DEP well cross-reference overlays for 616593, 610594, and McKean 5×5

**Annotations:**
- 675 expert pit points (538 Venango, 137 McKean)
- 88 pad polygons, 96 road lines

**Documentation:**
- Full methodology (`docs/methodology.md`)
- Abandoned well research compilation (`docs/abandoned_well_pit_research.md`)
- Radial profile analysis (`docs/pit_radial_profiles.png`)
- This development history
- Consolidated pipeline notebook (`notebooks/wellsight_pipeline.ipynb`)
- 29 versioned Python scripts + archive

### Performance Summary

| Metric | Best (training tile, with priors) | Cross-tile (no priors) |
|---|---|---|
| ROC-AUC | 0.987 | 0.950 |
| PR-AUC | 0.722 | 0.604 |
| Recall @ 90% precision | 76% | ~30-40% (estimated) |
| Recall @ 70% precision | 91% | ~50-60% (estimated) |

---

## 17. Potentially Useful Going Forward

### Near-Term Improvements

1. **Negative labeling** — Mark 20-30 obvious FPs (road ditches, tree throws) in QGIS and retrain with explicit hard negatives. Costs 30 minutes of annotation, potentially large precision improvement.

2. **Slope filter** — Simple post-hoc: reject candidates on slopes > 20-25°. Nobody drilled on a cliff. Free precision gain.

3. **Local linearity check** — Candidates with 8+ neighbors in a 25m line are road ditch detections. Quick heuristic filter before or after ML.

4. **Scattering/verticality_std as features** — Rasterize the PDAL eigenvalue features and add to the XGB model. The 21% overlap on verticality_std suggests meaningful discriminative power, especially for the road-ditch FP problem (road ditches have high linearity + low scattering, pits have low linearity + high scattering).

5. **Per-tile threshold calibration** — Instead of one isotonic calibration across all tiles, calibrate per-tile using the raw score distribution and a fixed percentile (e.g., top 0.5% of candidates = high confidence).

### Medium-Term Architecture

6. **Pad detector** — Train a CNN or XGB model to detect well pads from LRM/openness/CHM windows. This would replace expert pad annotations as a prior for pit detection, enabling autonomous cross-tile operation.

7. **CNN on stacked windows** — Once 300+ pits are annotated, a small CNN (3-5 conv layers) on the multi-channel 17×17 window stack could surpass the hand-crafted feature + XGB approach. Rotation augmentation is free (pits are rotationally symmetric).

8. **Multi-region joint training** — Train on Venango + McKean + one more region simultaneously, with a region indicator feature. Forces the model to learn region-invariant pit morphology.

### Long-Term Vision

9. **Statewide scanning** — Process all of western PA's 3DEP coverage tile-by-tile through the pipeline. With the current ~5 minute per-tile processing time, the entire oil region (~500 tiles) could be processed in ~40 hours of compute.

10. **Field verification** — The 35 high-confidence predictions on output2 (zero documented wells) and the 87 candidates on tile 616593 are actionable leads for field teams. Even a 50% confirmation rate would represent significant new well discoveries.

11. **Integration with remediation programs** — Ranked candidate lists with calibrated probability estimates could directly inform PA DEP's well plugging prioritization, focusing field resources on the highest-confidence undocumented locations.

---

## Appendix: Model Version Progression

| Version | Date | Change | PR-AUC | Key Learning |
|---|---|---|---|---|
| v1 RF | Apr 15 | Baseline RF, 45 features, OOB | 0.436 | OOB is optimistic |
| v2 XGB | Apr 15 | GroupKFold, honest eval | 0.478 | +0.04 from spatial CV honesty |
| v3 +2008+priors | Apr 15 | Temporal + pad/road features | 0.678 | **+0.20**, biggest jump |
| v4 +morph+tmpl | Apr 15 | Gaussian bowl + 3 templates | 0.716 | +0.04, diminishing returns |
| v5 ensemble | Apr 15 | XGB+LGBM avg + isotonic | 0.722 | Best single-tile model |
| v6 output2 | Apr 15 | Cross-tile, no priors | 0.604 | Prior removal costs 0.12 |
| v7 sep | Apr 16 | 6km×6km, different terrain | ~0.60 | Land cover matters |
| v8 McKean | Apr 17 | Cross-region, 120km away | ~0.50 | Different morphology |
| v9 675-pit | Apr 18 | 7.5× more training data | 0.372 | GroupKFold + mixed regions |
| v10 +LC | Apr 18 | Land cover features | 0.382 | Minimal gain in forest |
| v11 hotspots | Apr 18 | DEP-guided tile selection | — | Raw scores >> calibrated |

---

*Document version: 2026-04-18*
*Project: WellSight LiDAR Analysis*
*Total annotated pits: 675 across 2 regions*
*Total tiles processed: 30+ individual tiles across 4 study areas*
*Total candidate GPKGs: 21 archived versions*
