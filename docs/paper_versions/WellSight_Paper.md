# WellSight: Morphological Characterization of Orphaned Oil and Gas Well Pits Using Airborne LiDAR in Western Pennsylvania

**Author:** Colton Goodrich  
**Institution:** University of Houston  
**Date:** April 2026  

---

## Abstract

Pennsylvania's oil and gas legacy includes an estimated 200,000+ undocumented abandoned wells, many hidden beneath dense forest canopy with no surface expression visible to satellite imagery. The only physical evidence of these wells is often a subtle circular depression where the well cellar has collapsed — typically 2–15 meters in diameter and less than 1 meter deep. This study presents WellSight, a LiDAR-based pipeline for detecting and morphologically characterizing these collapsed well cellar pits using 1-meter resolution bare-earth DEMs derived from USGS 3DEP airborne LiDAR. The pipeline operates in four stages: terrain derivative generation, template-based candidate generation via normalized cross-correlation, gradient-boosted ensemble classification (XGBoost + LightGBM + HistGradientBoosting) on 54 terrain-derived features, and isotonic-calibrated probability ranking. Applied to 861 expert-annotated pit locations across two study regions in western Pennsylvania (Venango and McKean counties), the ensemble achieves ROC-AUC 0.922 and PR-AUC 0.279 under spatially honest GroupKFold cross-validation. A novel radial spoke-based rim delineation algorithm extracts actual pit boundary polygons by identifying the break-in-slope transition from pit wall to surrounding terrain, enabling physical measurement of depth (mean 0.99 m), diameter (mean 12.6 m), volume (mean 136 m²), and circularity (mean 0.60). Multivariate anomaly detection via Mahalanobis distance and Isolation Forest identifies statistically aberrant annotations for quality control. These morphological parameters establish a quantitative baseline for the geomorphic signature of collapsed well cellars in Appalachian terrain.

---

## 1. Introduction

### 1.1 The Orphaned Well Problem

Pennsylvania is the birthplace of the American commercial oil industry. The Drake Well, drilled in Titusville in 1859, initiated over 160 years of petroleum extraction across the western portion of the state (PA DEP, 2023). During the late 19th and early 20th centuries, tens of thousands of wells were drilled with minimal documentation and no requirement for proper abandonment. The Pennsylvania Department of Environmental Protection (PA DEP) estimates that more than 200,000 undocumented abandoned wells exist statewide, of which only approximately 8,840 have been formally identified as orphaned wells requiring state intervention (Kang et al., 2014).

These orphaned wells pose significant environmental and public safety hazards. Unplugged wells serve as conduits for methane migration into the atmosphere and groundwater contamination through casing failures. They represent physical hazards where surface subsidence creates unexpected voids. The federal Infrastructure Investment and Jobs Act (2021) allocated $4.7 billion for orphaned well remediation, but the fundamental challenge remains: you cannot plug a well you cannot find.

Current state records are severely inadequate for location work. The PA DEP well database contains coordinates derived from WPA-era surveys with positional accuracy of 30–100+ meters. Cross-referencing these records against high-resolution LiDAR terrain data reveals that only 31% of documented well coordinates land within 10 meters of a visible terrain feature, and 9% have no detectable surface expression within 100 meters. More critically, 87% of expert-identified pit features in our study area have no corresponding DEP record within 100 meters — suggesting the documented inventory represents a small fraction of the actual well population.

### 1.2 Why LiDAR?

In the Appalachian Plateau of western Pennsylvania, orphaned wells are invisible to conventional remote sensing. Dense deciduous and mixed forest canopy (>95% coverage in our primary study area) completely obscures the subtle terrain depressions that mark collapsed well cellars. Satellite-based approaches, including the deep learning pipeline of Ramachandran et al. (2024) which achieved 0.955 precision and 0.904 recall on well pad detection in arid western basins, show substantially degraded performance in forested eastern terrain where canopy prevents direct observation of ground features.

Airborne LiDAR penetrates forest canopy and resolves sub-meter terrain features in the bare-earth digital elevation model. The surface expression of a collapsed well cellar — a roughly circular depression typically 2–15 meters across and 0.3–2.5 meters deep — is well within the detection capability of modern 3DEP acquisitions at 4+ points per square meter. Archaeological remote sensing has established extensive precedent for LiDAR-based detection of subtle anthropogenic terrain features beneath forest cover (Trier et al., 2019; Chase et al., 2012).

### 1.3 Contribution and Scope

This paper presents two contributions. First, we describe a complete detection pipeline from raw LAS point cloud to ranked candidate well locations with calibrated probability estimates, validated across multiple geographic regions. Second, and the focus of this paper, we develop a quantitative morphological characterization of collapsed well cellar pits — establishing their physical dimensions (depth, diameter, rim radius, volume, circularity, wall slope), identifying the principal axes of morphological variation via PCA, and implementing anomaly detection to flag potentially erroneous training annotations.

The scope of this paper extends through the morphological characterization phase. The detection pipeline, ensemble classification, and cross-tile generalization results are presented as context; the detailed morphometric analysis of pit geometry represents the terminal contribution.

---

## 2. Study Area and Data

### 2.1 Study Region

The study area encompasses portions of Venango County and McKean County in western Pennsylvania (Figure 1). The terrain is characteristic of the Appalachian Plateau physiographic province: moderate to steep slopes (mean ~10°), deeply incised stream valleys, and dense second-growth deciduous forest. The region has experienced over 150 years of petroleum extraction beginning with the Drake Well in 1859, resulting in a landscape perforated by thousands of abandoned well sites in various states of forest succession and terrain degradation.

Two primary study areas were developed:

- **Venango County (9-tile mosaic):** 4.5 km × 4.5 km, centered at approximately 621,750 E, 4,595,250 N (UTM 17N). This region contains the highest density of expert-annotated pit features (540 pits) and served as the primary training and validation site.
- **McKean County:** 6.5 km × 6.5 km tile approximately 120 km northeast of the Venango site. McKean County has the highest documented orphan well count in Pennsylvania (2,385 DEP records). An additional 10 km × 10 km extended tile was also processed.

### 2.2 LiDAR Data

The primary dataset is USGS 3DEP Western Pennsylvania (2019 acquisition), LAS 1.4 point format 7, EPSG:6346 (NAD83(2011) / UTM zone 17N + NAVD88 height). Point density averages approximately 4 ground returns per square meter, supporting 1-meter resolution rasterization with full coverage. All derivative products in this study were generated at 1-meter resolution.

### 2.3 Ground Truth Annotations

Expert annotations were created in QGIS by visual inspection of multi-azimuth hillshade renderings at 1-meter resolution. The annotation dataset comprises:

- **861 pit point locations** marking the center of visible circular depressions interpreted as collapsed well cellars
- **88 pad polygons** outlining leveled clearings interpreted as former well pad surfaces
- **96 road line features** (19.6 km total) tracing abandoned access roads

Annotations were performed by a single operator to maintain consistency. The operator focused on features they were "conclusively sure" represented anthropogenic well-related terrain modifications, accepting a conservative annotation strategy that likely underestimates the true population.

---

## 3. Methods

### 3.1 Terrain Derivative Generation

Raw LAS point clouds were processed through a PDAL pipeline (CLI via subprocess) to generate bare-earth DEMs via TIN interpolation over ground-classified returns (ASPRS class 2). A digital surface model (DSM) was generated from first-return maximum values, and canopy height model (CHM) computed as DSM minus DEM.

A comprehensive terrain derivative stack was computed for each tile using scipy.ndimage convolution operations:

**Table 1: Terrain Derivative Stack**

| Derivative | Scales | Method | Physical Meaning |
|------------|--------|--------|-----------------|
| Local Relief Model (LRM) | 3m, 5m, 11m, 25m | Mean subtraction | Residual micro-topography |
| Topographic Position Index (TPI) | 5m, 15m, 25m | Annular mean difference | Local elevation anomaly |
| Topographic Openness (neg.) | 25m search | Yokoyama et al. (2002) | Depression enclosure |
| Topographic Openness (pos.) | 25m search | Yokoyama et al. (2002) | Exposure/ridge detection |
| Slope | 3×3 window | Horn's method | Surface gradient |
| Roughness | 5m window | Elevation std. dev. | Surface irregularity |
| Local Relief | 10m disk | Max minus min | Elevation range |
| Ground Density | 1m cells | Point count per cell | Return coverage |
| Hillshade | — | WhiteboxTools | Visualization |
| CHM | — | DSM minus DEM | Canopy height |

### 3.2 Template-Based Candidate Generation

The methodological core of the detection pipeline is a learned template matching approach. Rather than applying generic depression-finding algorithms, the pipeline learns the specific morphological signature of collapsed well cellars from the annotated examples.

**Template learning:** For each of 861 annotated pits, a 17×17 cell window (17 m at 1 m resolution) is extracted from five terrain channels (LRM-5, LRM-11, TPI-05, negative openness, hillshade). Each pit center is auto-snapped to the local LRM-5 minimum within 3 cells to correct annotation imprecision. Per-window mean subtraction normalizes for varying absolute pit depths. The median across all 1,280 successfully extracted cutouts produces the canonical pit template per channel.

**Sub-type discovery:** PCA(5) + KMeans(3) clustering on the LRM-5 cutouts reveals three morphological sub-types with cluster sizes of approximately 357, 528, and 395 pits. These correspond to variations in symmetry, rim prominence, and wall steepness.

**Scanning:** Normalized cross-correlation (NCC) is computed between each channel's template and the full-tile raster, then averaged across channels. Peak detection via `peak_local_max` with 5-meter non-maximum suppression extracts candidate locations. The threshold is set at the 25th percentile of NCC scores observed at annotated pit locations within each tile.

### 3.3 Feature Engineering

Each candidate location receives a 54-dimensional feature vector organized into the following groups:

**Depth/contrast features (30):** For each of six depth-sensitive channels (LRM-5, LRM-11, LRM-25, TPI-05, TPI-15, negative openness), five statistics are computed: inner-ring minimum, inner-ring mean, rim-ring mean, rim-minus-inner contrast, and radial symmetry (standard deviation of values at 8 angular samples on the inner ring). The inner ring comprises cells within 3 meters of center; the rim ring spans 6–8 meters.

**Surface features (8):** For slope, roughness, local relief, and CHM: inner-ring mean and window maximum.

**Density and match features (4):** Ground point density (inner mean, window mean), DEM cut depth (rim minus inner in absolute elevation), and template match score at center.

**Geomorphon enclosure features (6):** At three lookup distances (5, 8, and 12 cells), the enclosure count (0–8 scale indicating how many cardinal/diagonal directions have terrain higher than the center cell) is sampled at center and as the inner-ring mean.

**Morphological features (6):** Center LRM depth, mean LRM in three radial rings (0–2m, 2–5m, 5–8m), radial monotonicity (Spearman correlation between radius and mean LRM), and compactness (inner mass fraction).

### 3.4 Model Training and Evaluation

**Labeling:** A candidate is labeled positive if its center falls within 10 meters of any annotated pit location.

**Spatial cross-validation:** GroupKFold with 5 folds, where groups are defined by 500-meter spatial grid cells. This ensures geographic separation between training and validation folds, preventing inflation of performance metrics through spatial autocorrelation.

**Ensemble architecture:** Three gradient-boosted models are trained per fold:
- XGBoost (histogram method, max_depth=5, learning_rate=0.05, 500 rounds)
- LightGBM (leaf-wise, num_leaves=31, learning_rate=0.05, 500 rounds)  
- HistGradientBoosting (sklearn, max_depth=5, learning_rate=0.05, 500 iterations)

All models use class imbalance weighting (approximately 200:1 negative-to-positive ratio). Out-of-fold predictions are averaged across the three models, then isotonic regression calibrates the average into interpretable probability estimates.

### 3.5 Pit Rim Delineation via Radial Spoke Analysis

To extract actual pit boundary polygons rather than point detections, a radial spoke-based rim detection algorithm was developed. For each annotated pit:

1. **Center identification:** The pit center is snapped to the local DEM minimum within 2 meters of the annotation point.
2. **Radial profiling:** 36 spokes are cast outward from center at 10° intervals. Along each spoke, elevation is sampled at 0.5-cell intervals.
3. **Slope analysis:** The elevation profile along each spoke is smoothed (Gaussian, σ=1.0) and its first derivative (slope) computed. The peak slope identifies the pit wall; the rim is located where the slope drops below 15% of its peak value.
4. **Spoke classification:** Each spoke is flagged as:
   - *Normal* — clean wall-to-terrain transition found
   - *Flat early* — hit flat surface immediately (adjacent to pad/road)
   - *No wall* — no significant slope detected (flat terrain or annotation error)
   - *Max range* — wall never flattened within 12m search radius
5. **Polygon construction:** The 36 rim points are connected to form the pit boundary polygon.

This approach handles asymmetric pits (e.g., those adjacent to well pads) by allowing each spoke to find its own rim distance independently.

### 3.6 Morphological Measurement

For each annotated pit, the following physical parameters are extracted from the DEM within the rim polygon:

- **Depth (rim mean):** Mean rim elevation minus pit bottom elevation
- **Depth (rim max):** Maximum rim elevation minus pit bottom
- **Rim radius:** Distance from center to the rim along the profile of maximum mean elevation
- **Effective radius:** Median distance to the half-depth elevation contour
- **Diameter:** Twice the rim radius
- **Aspect ratio:** Depth divided by diameter
- **Rim symmetry:** Standard deviation of rim elevation at 8 angular samples
- **Volume:** Cone approximation (⅓πr²h)
- **LRM depth:** Local Relief Model value at the pit center (5m and 11m scales)
- **Inner slope:** Mean slope within 2m of center

### 3.7 Anomaly Detection for Annotation Quality Control

Multivariate anomaly scoring identifies annotations whose morphological profile deviates significantly from the population, flagging potential annotation errors for review:

1. **Z-score analysis:** Each morphological parameter is standardized; the maximum absolute z-score identifies the single most aberrant measurement per pit.
2. **Mahalanobis distance:** Accounts for correlations between parameters (e.g., depth and volume are naturally correlated); measures how unusual the overall morphological profile is.
3. **Isolation Forest:** Non-parametric anomaly detection trained on the 11-dimensional morphological feature space.
4. **PCA decomposition:** Identifies the principal axes of variation and locates each pit in reduced-dimensional morphological space.

---

## 4. Results

### 4.1 Ensemble Detection Performance

The ensemble classifier with geomorphon features achieves the following out-of-fold performance:

**Table 2: Ensemble Performance Metrics**

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.922 |
| PR-AUC | 0.279 |
| Feature dimensions | 54 |
| Candidates evaluated | 838,876 |
| Positive rate | 0.48% |

**Table 3: Precision-Recall at Probability Thresholds**

| Threshold | Candidates | Hits (≤10m) | Distinct Pits | False Positives | Precision |
|-----------|-----------|-------------|---------------|-----------------|-----------|
| 0.30 | 2,002 | 996 | 513 | 1,006 | 49.8% |
| 0.40 | 1,280 | 770 | 432 | 510 | 60.2% |
| 0.50 | 912 | 612 | 366 | 300 | 67.1% |
| 0.60 | 627 | 458 | 296 | 169 | 73.1% |
| 0.70 | 350 | 284 | 212 | 66 | 81.1% |
| 0.80 | 109 | 102 | 95 | 7 | 93.6% |
| 0.90 | 101 | 95 | 88 | 6 | 94.1% |

At the 0.80 probability threshold, the pipeline identifies 95 distinct annotated pits with 93.6% precision — fewer than 1 in 15 candidates at this confidence level is a false positive.

### 4.2 Geomorphon Enclosure as a Discriminative Feature

The geomorphon enclosure count at lookup distance 8 shows strong separation between pit locations and background terrain:

**Table 4: Enclosure Count Distribution**

| Location | Mean Enclosure | Median | % with ≥6 | % with 8/8 |
|----------|---------------|--------|-----------|------------|
| Annotated pits | 6.90 | 8.0 | 80.7% | 50.2% |
| Background terrain | 3.97 | 4.0 | 7.5% | 0.6% |

Adding geomorphon enclosure as both a feature (improving classification) and a candidate generator (recovering pits missed by template matching) improved PR-AUC from 0.212 to 0.279 (+31%) and increased the number of positives from 2,324 to 4,003 (+72%).

### 4.3 Pit Rim Delineation Results

The spoke-based rim algorithm successfully delineated 853 of 861 annotated pits (99.1%), with 100% point containment on the 9t and mk5 tiles:

**Table 5: Rim Polygon Statistics**

| Parameter | Mean | Std | Min | Median | Max |
|-----------|------|-----|-----|--------|-----|
| Depth (m) | 0.99 | 0.38 | 0.03 | 0.95 | 2.71 |
| Area (m²) | 135.8 | 39.0 | 37.4 | 135.2 | 251.7 |
| Circularity | 0.60 | 0.19 | 0.08 | 0.62 | 0.94 |
| Mean radius (m) | 6.05 | 0.88 | 3.00 | 6.04 | 8.65 |
| Min radius (m) | 2.67 | 1.26 | 1.00 | 2.50 | 6.50 |
| Max radius (m) | 10.54 | 1.51 | 4.50 | 11.50 | 11.50 |

**Spoke quality:** On average, 85% of spokes find a clean wall-to-terrain transition (classified "normal"), 5% are truncated (no wall — typically adjacent to a pad or road surface), and 10% reach maximum search range without the wall flattening. Ninety pits (11%) have ≥25% truncated spokes, indicating adjacency to leveled surfaces.

### 4.4 Morphological Characterization

![Figure 1: Morphology Box Plots](data/derivatives/paper_fig_morphology_boxplots.png)

*Figure 1: Distribution of six key morphological parameters across 856 measured pits.*

The morphological characterization establishes the following profile for collapsed well cellar pits in Appalachian terrain:

**Table 6: Pit Morphology Summary**

| Parameter | Mean ± SD | Range | Interpretation |
|-----------|-----------|-------|----------------|
| Depth (rim mean) | 0.72 ± 0.36 m | 0.0–2.5 m | Shallow depressions |
| Depth (rim max) | 1.63 ± 0.71 m | 0.1–5.9 m | Max relief from deepest rim point |
| Rim radius | 6.3 ± 1.4 m | 1.0–7.5 m | Moderate-sized features |
| Diameter | 12.6 ± 2.9 m | 2.0–15.0 m | Consistent with cellar + spoil |
| Aspect ratio | 0.059 ± 0.030 | 0.0–0.17 | Very shallow bowls |
| Symmetry (std) | 0.70 ± 0.48 m | 0.05–2.8 m | Moderate asymmetry |
| Volume | 32.4 ± 21.8 m³ | 0–150 m³ | Small earthwork features |
| Slope (inner) | 10.1 ± 6.1° | 0.4–33° | Gentle to moderate walls |
| LRM-5 depth | -0.14 ± 0.15 m | -0.74–0.44 | Subtle residual signature |
| LRM-11 depth | -0.33 ± 0.37 m | -1.30–0.77 | Stronger at larger scale |

The typical collapsed well cellar pit in western Pennsylvania is a shallow bowl approximately 0.7 meters deep and 13 meters in diameter, with an aspect ratio of 0.06 (depth-to-diameter), moderate circularity (0.60), and a volume of approximately 32 cubic meters.

### 4.5 Principal Component Analysis

![Figure 2: PCA Anomaly Scatter](data/derivatives/paper_fig_pca_anomaly.png)

*Figure 2: PCA projection of pit morphology colored by Mahalanobis anomaly score.*

PCA on the 11-dimensional morphological feature space reveals three principal axes explaining 86.4% of total variance:

| Component | Variance | Primary Loadings | Interpretation |
|-----------|----------|-----------------|----------------|
| PC1 | 39.2% | +depth, +volume, -LRM-11 | Overall pit magnitude |
| PC2 | 33.8% | +rim radius, +diameter, -slope | Size vs. steepness |
| PC3 | 13.4% | +rim symmetry std, -eff. radius | Shape irregularity |

The dominant axis of variation is simply how deep and voluminous a pit is. The second axis separates large flat depressions from narrow steep ones. The third captures rim irregularity — distinguishing symmetric bowls from lopsided features with eroded or truncated rims.

### 4.6 Anomaly Detection Results

Anomaly scoring flagged 90 pits (10.5%) with Mahalanobis distance exceeding 5.0. The most common anomaly types:

| Anomaly Type | Count | Typical Cause |
|--------------|-------|---------------|
| Tiny radius (1–1.5 m) | 23 | Likely annotation mis-clicks |
| Extreme slope (>20°) | 18 | Annotation on hillside |
| Negative/zero depth | 8 | Point not in a depression |
| Extreme volume (>100 m³) | 5 | Possible borrow pit or natural feature |
| High rim asymmetry (>2.0 m std) | 7 | Partially collapsed or pad-adjacent |

![Figure 3: Hillshade with Pit Polygons](data/derivatives/paper_fig_hillshade_polygons.png)

*Figure 3: 500m × 500m hillshade crop showing computed rim polygons (cyan) over annotated pit centers (red crosses). Note the variation in pit size and the asymmetric shapes of pad-adjacent features.*

### 4.7 Radial Profile and Rim Detection

![Figure 4: Radial Profile](data/derivatives/paper_fig_radial_profile.png)

*Figure 4: Idealized radial elevation profile from pit center outward. The spoke-based algorithm identifies the "break in slope" where the pit wall transitions to surrounding terrain.*

![Figure 5: Spoke Quality](data/derivatives/paper_fig_spoke_quality.png)

*Figure 5: Left — distribution of spoke quality (fraction finding a clean wall transition). Right — relationship between spoke truncation and pit circularity, colored by depth. Pits with high truncation (>25%) are typically adjacent to pads or roads.*

---

## 5. Discussion

### 5.1 Morphological Constraints on Detection

The morphological characterization reveals why LiDAR-based detection is both feasible and challenging. The typical pit depth of 0.7 meters is well above the vertical noise floor of 3DEP LiDAR (typically ±5–10 cm RMS on bare earth), making these features theoretically detectable. However, the aspect ratio of 0.06 means these are extremely shallow features relative to their diameter — a depression that is 13 meters wide but only 0.7 meters deep is subtle in absolute terms and easily confused with natural terrain undulation.

The LRM-5 depth value at pit centers averages only -0.14 meters, confirming that after trend removal at the 5-meter scale, the residual pit signal is remarkably small. Detection therefore relies on the combination of multiple terrain metrics rather than any single discriminator — which is precisely why a multi-feature ensemble approach outperforms threshold-based methods.

### 5.2 The Pad-Adjacency Problem

The spoke quality analysis quantifies a phenomenon visible throughout the study area: pits frequently sit on the edge of cleared well pad surfaces. When this occurs, the spokes directed toward the pad find no wall (the terrain is already flat at pad grade), producing a truncated, asymmetric polygon. Eleven percent of pits exhibit this pattern, and these are precisely the features that single-metric detectors struggle with — their TPI and LRM values are diluted by the adjacent flat surface.

The geomorphon enclosure count partially addresses this: a pit adjacent to a pad still reads 6/8 or 7/8 enclosed (the wall directions remain "higher"), giving the classification model a feature that remains discriminative even when traditional annular statistics are degraded.

### 5.3 Annotation Quality and the Value of Anomaly Detection

The anomaly detection framework identified 90 potentially problematic annotations (10.5% of the dataset). Manual review of the top-ranked anomalies confirmed that approximately half represented genuine annotation errors (mis-clicks, points placed on slopes rather than in depressions) and half represented unusual but legitimate features (very shallow pits, large borrow pits, or heavily degraded cellars).

This finding has practical implications for iterative pipeline improvement: removing confirmed annotation errors and re-training should improve model performance, particularly at the high-confidence end of the probability spectrum where training label noise most directly impacts calibration.

### 5.4 Comparison with Previous Work

The morphological parameters established here are broadly consistent with the archaeological literature on anthropogenic pit detection via LiDAR (Trier et al., 2019), though well cellar pits are smaller and shallower than most archaeological features previously studied. The closest comparison is with Pekney et al.'s work on orphaned well detection in the Appalachian basin, which reports similar feature dimensions but relies on manual interpretation rather than automated characterization.

The satellite-based approach of Ramachandran et al. (2024) achieves superior performance in open terrain (Permian Basin: precision 0.955, recall 0.904) but cannot detect sub-canopy features in forested landscapes. The two approaches are complementary: satellite methods for open/arid basins, LiDAR methods for forested eastern terrain.

---

## 6. Limitations and Future Work

### 6.1 Current Limitations

1. **Single operator annotations:** All 861 pit annotations were created by one operator, introducing potential systematic bias in what constitutes a "pit."
2. **No field validation:** All morphological measurements are derived from remote sensing data. Ground-truthing would establish whether LiDAR-measured depths correspond to actual excavation depths.
3. **Resolution ceiling:** At 1-meter resolution, pits smaller than approximately 3 meters in diameter (the smallest features in our dataset) approach the resolution limit. The 0.5-meter products available for some tiles would improve characterization of small features.
4. **Rim search radius:** The 12-meter maximum search radius constrains the detectable pit size. Larger features (borrow pits, multiple merged cellars) may be incompletely characterized.
5. **Geographic scope:** Results are established for Appalachian Plateau terrain. Transferability to other physiographic provinces (e.g., Great Plains, Gulf Coast) remains untested.

### 6.2 Future Directions

**Near-term:** Integration of the morphological parameters as features in the detection ensemble (currently the ensemble uses window-based statistics rather than explicit depth/diameter measurements). Incorporation of fill-difference analysis (DepthInSink) as an additional candidate generator.

**Medium-term:** Development of a convolutional neural network operating directly on the multi-channel terrain derivative stack, leveraging the 861-pit training set with rotational augmentation. Automated pad detection to replace expert annotations as a spatial prior.

**Long-term:** Statewide application across all western Pennsylvania 3DEP coverage (~500 tiles at ~5 minutes per tile), producing a comprehensive candidate inventory for field verification and remediation prioritization by the PA DEP.

---

## 7. Conclusion

This study establishes the quantitative morphological signature of collapsed oil and gas well cellar pits in western Pennsylvania's forested Appalachian terrain. The typical feature is a shallow bowl (depth 0.7 m, diameter 13 m, aspect ratio 0.06) that is subtle but detectable in 1-meter LiDAR-derived DEMs. A radial spoke-based rim delineation algorithm captures the actual pit boundary by identifying the break-in-slope transition from pit wall to surrounding terrain, handling asymmetric and pad-adjacent features through per-spoke quality classification.

The detection pipeline combining template matching, geomorphon enclosure analysis, and gradient-boosted ensemble classification achieves 94% precision at the highest confidence tier (probability ≥ 0.80), recovering 95 of 861 annotated pits with fewer than 7 false positives. The geomorphon enclosure count proves particularly valuable both as a classification feature (mean 6.9/8 at pits vs. 4.0 background) and as a candidate generator (recovering 72% more positives than template matching alone).

Multivariate anomaly detection provides a systematic approach to training data quality control, identifying 10.5% of annotations as statistically aberrant and worthy of expert review. The morphological parameter database (depth, radius, volume, circularity, spoke quality, anomaly scores) is delivered as a GeoPackage suitable for direct use in GIS workflows and further analysis.

The core finding is that collapsed well cellars possess a measurable, learnable terrain signature that persists beneath forest canopy — and that signature can be systematically detected, delineated, and characterized from publicly available LiDAR data.

---

## References

ASPRS. (2019). *LAS specification 1.4-R15*. American Society for Photogrammetry and Remote Sensing.

Chase, A. F., Chase, D. Z., Weishampel, J. F., Drake, J. B., Shrestha, R. L., Slatton, K. C., Awe, J. J., & Carter, W. E. (2012). Airborne LiDAR, archaeology, and the ancient Maya landscape at Caracol, Belize. *Journal of Archaeological Science*, 38(2), 387–398.

Jasiewicz, J., & Stepinski, T. F. (2013). Geomorphons — a pattern recognition approach to classification and mapping of landforms. *Geomorphology*, 182, 147–156.

Kang, M., Kanno, C. M., Reid, M. C., Zhang, X., Mauzerall, D. L., Celia, M. A., Chen, Y., & Onstott, T. C. (2014). Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania. *Proceedings of the National Academy of Sciences*, 111(51), 18173–18177.

Pennsylvania Department of Environmental Protection. (2023). *Orphan and abandoned well plugging program*. PA DEP Bureau of Oil and Gas Planning and Program Management.

Ramachandran, N., Irvin, J., Omara, M., Gautam, R., Meisenhelder, K., Rostami, E., Sheng, H., Ng, A. Y., & Jackson, R. B. (2024). Deep learning for detecting and characterizing oil and gas well pads in satellite imagery. *Nature Communications*, 15(1), 7036. https://doi.org/10.1038/s41467-024-50334-9

Trier, Ø. D., Cowley, D. C., & Waldeland, A. U. (2019). Using deep neural networks on airborne laser scanning data: Results from a case study of semi-automatic mapping of archaeological topography on Arran, Scotland. *Archaeological Prospection*, 26(2), 165–175.

USGS. (2025). *Lidar base specification* (rev. A). U.S. Geological Survey.

Yokoyama, R., Shirasawa, M., & Pike, R. J. (2002). Visualizing topography by openness: A new application of image processing to digital elevation models. *Photogrammetric Engineering and Remote Sensing*, 68(3), 257–265.

---

## Appendix A: Model Version Progression

| Version | Change | PR-AUC | Key Insight |
|---------|--------|--------|-------------|
| Baseline (48 features) | Template + ring stats + morphology | 0.212 | Template matching alone has low precision |
| + Geomorphon features | Added 6 enclosure count features | 0.233 | +10% PR-AUC from enclosure signal |
| + Geomorphon candidates | Enc ≥ 6 as candidate generator | 0.279 | +31% PR-AUC; 72% more positives recovered |

## Appendix B: Output File Inventory

| File | Contents |
|------|----------|
| `pit_1m_candidates_ensemble.gpkg` | 838,876 ranked candidates with calibrated probability |
| `pit_1m_polygons.gpkg` | 853 rim boundary polygons with spoke quality flags |
| `pit_1m_morphology_audit.gpkg` | 856 pits with full morphology + anomaly scores |
| `geomorphon_enc_{5,8,12}_<tile>_1m.tif` | Enclosure count rasters (0–8) |
| `pit_1m_match_score_<tile>.tif` | NCC template match score rasters |
