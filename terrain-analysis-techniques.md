# Terrain Analysis Techniques for Orphaned Well Detection

## WellSight Project — Morphological Detection Reference

**Purpose:** This document catalogs terrain analysis techniques applicable to detecting orphaned and abandoned oil and gas well sites in LiDAR-derived bare-earth DEMs. The target features are negative-relief geomorphic anomalies — collapsed well cellars and associated depressions — visible in 1-meter resolution USGS 3DEP data as small, roughly circular pits resembling shallow craters with no central peak.

**Study Area:** Appalachian dissected plateau (Venango County, western Pennsylvania)  
**Primary Data:** USGS 3DEP 2019 LiDAR, 1-meter resolution bare-earth DEMs  
**Secondary Data:** PAMAP 2008 LiDAR

---

## Table of Contents

1. [Fill-Difference Method (Depression Inventory)](#1-fill-difference-method-depression-inventory)
2. [Geomorphons (Jasiewicz & Stepinski, 2013)](#2-geomorphons-jasiewicz--stepinski-2013)
   - [Handling Partially-Enclosed and Asymmetric Pits](#21-handling-partially-enclosed-and-asymmetric-pits)
   - [The Flatness Threshold](#22-the-flatness-threshold)
   - [Raw Ternary Patterns and the Enclosure Count Metric](#23-raw-ternary-patterns-and-the-enclosure-count-metric)
   - [Extracting the Enclosure Count](#24-extracting-the-enclosure-count)
3. [Multi-Scale Topographic Position Index (TPI)](#3-multi-scale-topographic-position-index-tpi)
4. [Differential Curvature Analysis](#4-differential-curvature-analysis)
5. [Template Matching / Matched Filtering](#5-template-matching--matched-filtering)
6. [Integrated Pipeline Architecture](#6-integrated-pipeline-architecture)
7. [Terrain-Specific Considerations: The Dissected Plateau Problem](#7-terrain-specific-considerations-the-dissected-plateau-problem)
8. [Tool Recommendations](#8-tool-recommendations)
9. [References](#9-references)

---

## 1. Fill-Difference Method (Depression Inventory)

### Concept

This is the most conceptually straightforward technique and should serve as the first pass in any detection pipeline. The idea originates from computational hydrology.

Every DEM contains natural and artificial depressions — cells or clusters of cells that are lower than all their neighbors. Hydrological routing algorithms need to "fill" these depressions to create continuous flow paths. The standard operation is called **pit filling** (or depression filling), implemented in tools like GDAL, WhiteboxTools, SAGA, and GRASS GIS.

### Procedure

1. Take the original bare-earth DEM.
2. Run a hydrological fill operation on it. This raises every depression up to its **lowest pour point** — the point where water would spill out of the depression.
3. Subtract the original DEM from the filled DEM.

The result is a **residual depth raster**. Every cell with a value greater than zero was part of a depression, and the value tells you how deep that depression was. Everything else is zero.

### What This Produces

An instant, exhaustive inventory of every closed depression in the landscape. Well cellar pits appear as clusters of positive-value cells.

### Discriminating Metrics per Depression

Once depressions are identified, the following shape metrics can be extracted for each feature to filter well-related depressions from natural or irrelevant features:

- **Depth:** Maximum residual value within the depression.
- **Area:** Count of cells × cell area (m²).
- **Depth-to-Diameter Ratio:** The single most powerful discriminator. A well cellar collapse has a characteristic ratio that differs from tree-throw pits, karst sinkholes, or road drainage ditches. For a typical ~1–3 meter diameter, ~0.3–1.0 meter deep cellar pit, the expected depth-to-diameter ratio falls roughly in the **0.15–0.5 range**.
- **Circularity Index:** Calculated as `(4π × Area) / Perimeter²`. A perfect circle = 1.0. Well cellar pits should score high on this metric. Tree-throw pits tend to be elongated (low circularity), and drainage features are linear (very low circularity).
- **Wall Slope Angle:** Mean slope of the cells at the depression boundary. A collapsed cellar typically has steeper walls than a natural swale.

### Key Advantage

The detection step is completely **parameter-free** — it is just subtraction. All the intelligence goes into the filtering step afterward, where thresholds are set on the shape metrics above. If there is a closed depression in the DEM, this method finds it.

### Recommended Tool

WhiteboxTools provides `FillDepressions` and `DepthInSink`, which perform this operation in one step. It runs as a standalone command-line binary, integrating cleanly with subprocess-based PDAL workflows.

---

## 2. Geomorphons (Jasiewicz & Stepinski, 2013)

### Concept

Geomorphons classify every cell in a DEM into one of **10 fundamental landform types** based on the pattern of relative elevation differences in 8 cardinal and diagonal directions. For each direction, the algorithm looks outward from the cell and classifies the neighbor as either *higher*, *lower*, or *at the same level* (within a flatness threshold). This produces a ternary pattern (3⁸ = 6,561 possible combinations), which collapses into 10 morphologically meaningful classes:

| Class | Description | Relevance to Well Detection |
|-------|-------------|----------------------------|
| **Pit** | All neighbors higher | Primary target — fully enclosed depressions |
| **Depression** | Most neighbors higher, 1–2 level | Secondary target — pad-adjacent pits |
| **Hollow** | Concave, open on one side | Tertiary target — hillslope pits, eroded rims |
| **Valley** | Linear low feature | Drainage channels, roads — generally not targets |
| **Flat** | All neighbors at same level | Plains, plateaus, pad scars |
| **Shoulder** | Convex break in slope | — |
| **Ridge** | Linear high feature | — |
| **Peak** | All neighbors lower | — |
| **Spur** | Promontory | — |
| **Slope** | Consistent gradient | — |

### Critical Parameter: Lookup Distance

The **lookup distance** controls how far outward from each cell the algorithm searches before making the higher/lower/same determination. This controls the *scale* of features detected:

- **Small lookup distance** (5–10 cells = 5–10 meters at 1m resolution): Catches small cellar pits.
- **Large lookup distance** (50–100 cells): Catches landscape-scale valleys and ridges; ignores small pits.

For ~1–3 meter diameter pits in 1-meter DEM data, a lookup distance of **5–15 cells** is the recommended starting range. Running the algorithm at multiple scales and identifying cells classified as "pit" consistently across scales provides a strong signal that the feature is morphologically robust rather than DEM noise.

### Recommended Tools

- WhiteboxTools: `Geomorphons` (built-in)
- GRASS GIS: `r.geomorphon`

Both are command-line accessible.

### Reference

Jasiewicz, J. & Stepinski, T.F. (2013). *Geomorphons — a pattern recognition approach to classification and mapping of landforms.* Geomorphology, 182, 147–156.

---

### 2.1 Handling Partially-Enclosed and Asymmetric Pits

#### The Problem with Strict "Pit" Classification

The "pit" geomorphon requires **all 8 look directions** to return "higher." This is the most restrictive pattern in the entire classification system. Real-world well cellar depressions routinely violate this requirement:

- **Pit adjacent to a pad scar:** The directions toward the pad register as "level," not "higher," because the pad is a flat, graded surface at roughly the same elevation as the pit rim, or even lower.
- **Pit next to a road cut:** The road grade may be lower than the pit rim on that side, so one or two directions register as "lower."
- **Pit on a hillslope:** Even without any anthropogenic neighbor, the uphill directions are higher and the downhill directions may be level or lower. The pit is real, but the ambient slope gradient breaks the all-directions-higher requirement.
- **Asymmetric erosion or infill:** One side of the rim has slumped or been partially filled, so it no longer stands above the pit floor in that direction.

If only the strict "pit" class is extracted, the result is biased toward the most pristine, isolated, symmetrical depressions — which are likely natural tree-throw pits or karst features rather than anthropogenic well sites that have been disturbed by a century of activity.

#### Solution: Extract Pit + Depression + Hollow

The practical approach is to extract all three partially-enclosed classes as the candidate set:

- **Pit** (8/8 directions higher) — fully enclosed, isolated craters
- **Depression** (6–7/8 directions higher) — pad-adjacent or rim-degraded pits
- **Hollow** (concave, open on one side) — hillslope pits, drainage-eroded features

This casts a wider net, increasing false positives, but downstream shape filtering and the ML pipeline handle that separation.

---

### 2.2 The Flatness Threshold

The geomorphon algorithm includes a **flatness threshold** parameter (`t` or `threshold_angle` depending on implementation). This controls how the algorithm decides whether a neighboring direction is "higher," "lower," or "the same."

For each of the 8 look directions, the algorithm computes the **zenith angle** and **nadir angle** between the center cell and the first significant elevation change along that direction. If the angle is less than the flatness threshold, the direction is classified as "level" rather than "higher" or "lower."

#### Impact on Detection

- **Low flatness threshold (e.g., 1°):** Very sensitive to even tiny elevation differences. A pit rim that is only 10–15 cm above the surrounding pad still registers as "higher." This pushes more partial pits into the "pit" or "depression" class — but also makes classification noisy on rough terrain.
- **High flatness threshold (e.g., 5°):** More tolerant of small elevation differences, absorbing them into "level." Subtle pit rims get ignored and the pit merges into the surrounding flat. Cleaner on rough terrain but misses shallow, degraded features.

#### Recommended Starting Parameters

For 1-meter DEMs with sub-meter-deep cellar pits, start with a flatness threshold around **1.0–2.0 degrees**. Bracket the parameter by running at 0.5°, 1.0°, 2.0°, and 3.0° to compare candidate counts and spatial patterns against known annotated sites.

---

### 2.3 Raw Ternary Patterns and the Enclosure Count Metric

#### Beyond the 10-Class Simplification

The 10-class geomorphon map is a simplification. The raw output of the algorithm is a **ternary code** — 8 digits, each being +1 (higher), 0 (level), or -1 (lower). Rather than collapsing this into named classes, a more powerful approach for the ML pipeline is to extract the **enclosure count**: the number of "higher" directions for each cell.

| Higher Directions | Interpretation |
|-------------------|---------------|
| 8 / 8 | Classic pit — fully enclosed |
| 7 / 8 | One side open — pad-adjacent pit |
| 6 / 8 | Two sides open — corner of a pad, or hillslope pit |
| 5 / 8 | Marginally enclosed — transitional to hollow/valley |
| ≤ 4 / 8 | Unlikely to be a pit-like feature |

This count becomes a **continuous enclosure metric** (0–8) that feeds into the XGBoost/LightGBM ensemble as a feature rather than serving as a hard binary filter. The model can then learn that, for example, 6+ higher directions combined with high circularity and appropriate depth-to-diameter ratio is a strong well-pit signal — even though the geomorphon classification would have labeled the feature a "depression" or "hollow" rather than a "pit."

This is a more natural fit for the existing ML architecture than treating geomorphons as a standalone binary detector.

---

### 2.4 Extracting the Enclosure Count

WhiteboxTools does not directly output the per-direction ternary values. However, the core geomorphon logic can be implemented directly in Python with NumPy. The algorithm is straightforward:

**For each cell, for each of the 8 directions:**

1. Walk outward cell-by-cell up to the lookup distance.
2. Track the maximum upward angle (zenith) and maximum downward angle (nadir) seen along that ray.
3. If zenith > flatness threshold → that direction is **"higher."**
4. If nadir > flatness threshold → that direction is **"lower."**
5. Otherwise → **"level."**

Count the "higher" directions. That is the enclosure metric.

**Computational cost:** O(cells × 8 × lookup_distance). On a 1-meter DEM tile, this is very manageable with no exotic dependencies — just array indexing and trigonometry.

---

## 3. Multi-Scale Topographic Position Index (TPI)

### Concept

For each cell, TPI computes the difference between that cell's elevation and the **mean elevation of cells within an annular (donut-shaped) neighborhood** around it.

- **Negative TPI** = cell is lower than its surroundings = depression
- **Positive TPI** = cell is higher than its surroundings = mound/ridge
- **TPI near zero** = cell is at the same elevation as its surroundings = flat or mid-slope

### Annulus Parameters

The annulus is defined by an inner radius and an outer radius. The inner radius excludes the immediate neighbors (comparing against the "rim" of the feature rather than the feature itself), and the outer radius controls how far out the comparison extends.

For cellar pits, recommended starting parameters:

- **Inner radius:** 0–1 meters (or even 0)
- **Outer radius:** 2–5 meters (matching the expected rim-to-rim diameter of a cellar depression)

### Multi-Scale Analysis

Run TPI at several outer radii (e.g., 2m, 3m, 5m, 8m) and look for cells that are consistently negative across scales. A real pit is a pit at every reasonable scale; a random low point in noisy terrain may only appear at one scale. This filtering rejects noise and scale-dependent artifacts.

### How TPI Complements Fill-Difference

Fill-difference is binary — it finds depressions and reports their depth. TPI provides a **continuous measure of how anomalous** a cell is relative to its local context. This is valuable as a feature in the ML pipeline, capturing the "crater-ness" of the terrain in a single continuous value.

---

## 4. Differential Curvature Analysis

### Concept

Curvature measures how the surface bends at each point, computed from the second derivatives of the elevation surface. The most relevant metric for well pit detection is **mean curvature** (sometimes called total curvature or the Laplacian of elevation) — the average of the two principal curvatures at each point.

- **Positive mean curvature** (in the convention used by most GIS tools): surface is concave, converging, bowl-shaped — **target features.**
- **Negative mean curvature:** surface is convex, diverging, dome-shaped.

### Morphological Signature

A well cellar pit shows up as a patch of strongly positive mean curvature surrounded by a ring of weakly negative curvature (the rim). This is the differential geometry signature of a shallow crater with no central peak.

### Noise Sensitivity

Curvature is computed from second derivatives, which amplify noise. On a 1-meter DEM, mitigation options include:

- **Pre-smoothing:** Apply a Gaussian filter (σ = 1–2 cells) before computing curvature.
- **Larger computation window:** Use a 5×5 or 7×7 polynomial fit rather than the default 3×3.

Both approaches trade spatial precision for noise reduction. For 1–3 meter features, a **5×5 window at 1m resolution** is a good starting point.

### Recommended Tool

WhiteboxTools' `MeanCurvature` is the recommended implementation. SAGA GIS also has robust curvature tools. GDAL's `gdaldem` does not compute curvature directly.

---

## 5. Template Matching / Matched Filtering

### Target Morphology

The "crater with no central peak" target feature is a **truncated inverted cone** or **parabolic bowl** in cross-section. The synthetic template for matched filtering should be:

- Radially symmetric
- Depression depth at center (deepest point)
- Monotonically increasing elevation from center to rim
- No central peak
- Sharp break in slope at the rim (transition from pit wall to surrounding terrain)

### Free Parameters

The key template parameters are:

- **Diameter:** Expected rim-to-rim extent
- **Depth:** Expected center-to-rim relief
- **Wall profile shape:** Linear/conical vs. parabolic vs. U-shaped

If these are not known a priori, matching can be run at multiple template sizes and the best-fit scale taken per candidate location.

---

## 6. Integrated Pipeline Architecture

The most effective detection pipeline layers these techniques rather than choosing a single one:

| Stage | Technique | Function |
|-------|-----------|----------|
| 1 | **Fill-Difference** | Initial depression inventory (fast, exhaustive, zero false negatives for true depressions) |
| 2 | **Shape Filtering** | Apply circularity, depth-to-diameter ratio, and area constraints on the depression inventory to reject non-pit features |
| 3 | **Geomorphons (Enclosure Count)** | Independent morphological confirmation that the candidate is pit-like at the appropriate scale; continuous 0–8 metric for ML |
| 4 | **TPI + Curvature** | Continuous-valued features per candidate for the XGBoost/LightGBM ensemble (adds 3–5 high-value features to the existing 88-feature set) |
| 5 | **Template Matching** | Correlation score as an additional ML feature, or as a standalone candidate generator |

Stages 1–2 produce a clean candidate set before the ML stage begins. Stage 3 provides independent morphological validation. Stages 4–5 enrich the feature space for supervised classification.

---

## 7. Terrain-Specific Considerations: The Dissected Plateau Problem

Venango County's terrain presents deeply incised stream valleys and steep hillslopes. This creates a significant population of **false-positive depressions** from DEM artifacts along stream channels and at slope breaks. The fill-difference method will flag these.

### Mitigation: Shape Filtering

The circularity index rejects most of these, as stream-channel artifacts are elongated and linear rather than circular.

### Mitigation: Slope Position Filter

Well cellar pits are overwhelmingly found on relatively flat terrain — ridge tops, benches, valley floors — rather than on steep hillslopes. Adding a **local slope constraint** to candidate filtering dramatically reduces false positives from terrain artifacts:

**Recommended constraint:** Mean slope within a 10-meter radius < 15°.

This single filter eliminates the majority of false positives arising from the dissected portions of the landscape without discarding any plausible well-site locations.

---

## 8. Tool Recommendations

| Tool | Functions | Integration Notes |
|------|-----------|-------------------|
| **WhiteboxTools** | `FillDepressions`, `DepthInSink`, `Geomorphons`, `MeanCurvature`, TPI via `DEViation from Mean Elevation` | Standalone CLI binary; subprocess-compatible with existing PDAL workflow |
| **GRASS GIS** | `r.geomorphon`, `r.slope.aspect`, `r.neighbors` | CLI accessible; strong raster analysis |
| **SAGA GIS** | Curvature, TPI, morphometric analysis | CLI accessible; comprehensive terrain tools |
| **GDAL** | `gdaldem` (slope, aspect, hillshade); no native curvature | Already in most LiDAR workflows |
| **NumPy (custom)** | Enclosure count metric, custom TPI, template matching | Direct integration with existing Python/ML pipeline |

---

## 9. References

- Jasiewicz, J. & Stepinski, T.F. (2013). Geomorphons — a pattern recognition approach to classification and mapping of landforms. *Geomorphology*, 182, 147–156.
- Pingel, T.J., Clarke, K.C., & McBride, W.A. (2013). An improved simple morphological filter for the terrain classification of airborne LIDAR data. *ISPRS Journal of Photogrammetry and Remote Sensing*, 77, 21–30.
- Zhang, W., Qi, J., Wan, P., Wang, H., Xie, D., Wang, X., & Yan, G. (2016). An easy-to-use airborne LiDAR data filtering method based on cloth simulation. *Remote Sensing*, 8(6), 501.
- Chambers, D. (2017). *[Reference for WPA-era well documentation in Pennsylvania]*
- ASPRS (2019). LAS Specification 1.4-R15.
- USGS (2025). Lidar Base Specification, rev. A.
- Ramachandran, S., et al. (n.d.). Deep learning pipeline for orphaned well detection. *Nature Communications.*
