# Detecting orphaned well pads in LiDAR: a Python pipeline guide

Pennsylvania's 165-year oil legacy has left an estimated **200,000–750,000 undocumented abandoned wells** scattered across its Appalachian forests — and LiDAR is the only remote sensing technology capable of finding many of them. DOE/NETL researchers at Oil Creek State Park demonstrated that bare-earth DEMs derived from airborne LiDAR can reveal well pad signatures invisible to optical imagery, magnetic surveys, and even ground observers, identifying 290 field locations of which 86% proved to be possible well sites. No automated, open-source Python pipeline for this detection task currently exists, which represents a clear research gap. The science, tools, and data are all mature enough for a proof-of-concept system that ingests raw .las files and outputs candidate well pad polygons with confidence scores.

---

## What abandoned well pads look like in LiDAR

The foundational research comes from NETL's Pittsburgh-based team (Natalie Pekney, James Sams, Matthew Reeder, Garret Veloski), who have systematically documented the terrain signatures that orphaned well sites leave in high-resolution DEMs across western Pennsylvania.

**Flat cleared platforms** are the primary signature. Well pads required cut-and-fill grading to create level working surfaces on Appalachian hillsides, producing anomalously flat benches (slope <3–5°) embedded in terrain with ambient slopes of 10–30°. These persist for decades because the compacted, graded surface resists erosion differently than surrounding natural terrain. In bare-earth hillshade renderings, they appear as distinctly artificial rectangular or circular platforms — typically 20–50 feet in diameter for pre-1955 pads, larger for modern unconventional sites.

**Wellhead collapse depressions** are the second key feature. Where wooden or iron well casings have deteriorated, soil subsides into the well void, creating circular depressions 1–3 meters wide that are "easily recognized" in sub-meter LiDAR-derived DTMs (Hammack et al., 2018; Reeder et al., 2023). These features are particularly important because they mark individual wellheads, not just pad areas, and are detectable only through LiDAR — not magnetic surveys (which miss wooden-cased wells entirely) or optical imagery (which cannot penetrate forest canopy).

Additional signatures include **perimeter berms** from containment structures (ring-like raised features in slope maps), **access road traces** visible as narrow linear low-slope features connecting pads to road networks, **surface roughness anomalies** where graded surfaces show standard deviation of elevation below 0.05–0.15m versus 0.5–2.0m for natural forested terrain, and **canopy height model gaps** where cleared areas show absent or early-succession vegetation. Brubaker et al. (2013, Penn State) confirmed that Pennsylvania's statewide PAMAP 1m LiDAR data has sufficient resolution for roughness-based analysis, finding that algorithm choice matters more than point density.

The USGS EROS / Fish & Wildlife Service took this further in 2022, successfully training **convolutional neural networks on 0.5m LiDAR-derived DEMs and hillshade maps** to detect abandoned wells on National Wildlife Refuges, using geomorphology and local relief as predictor variables. Their conclusion: these features are "distinguishable only with the terrain data sourced from lidar because of its ability to capture terrain conditions under vegetation."

---

## Western Pennsylvania has excellent free LiDAR coverage

The data bottleneck for this project does not exist. Western Pennsylvania has **full QL1/QL2 LiDAR coverage** through USGS 3DEP, collected during leaf-off conditions (optimal for bare-earth extraction).

The primary dataset is **PA_WesternPA_1_2019**, covering 31 counties across ~16,495 km² with **117.9 billion points at 7.14 points/m²** and 0.35m nominal point spacing — substantially exceeding the minimum density needed for well pad detection. It was collected November 2019 through March 2020 in LAZ (LAS 1.4) format. A companion QL2 dataset provides 2 pts/m² coverage. Additional QL1 data covers the Allegheny National Forest (April 2020), and a 2024 USGS/NRCS acquisition added 17 more counties.

Access is straightforward through multiple channels. The **USGS TNM Access API** (`https://tnmaccess.nationalmap.gov/api/v1/products`) supports programmatic queries by bounding box and dataset name. The same data is available as **Entwine Point Tiles on AWS S3** (`s3://usgs-lidar-public/PA_WesternPA_1_2019/ept.json`), which PDAL can stream directly without downloading full tiles — ideal for prototyping on specific areas of interest. **PASDA** (Penn State's geospatial clearinghouse at `pasda.psu.edu`) hosts the same data plus older PAMAP-era LiDAR and pre-computed DEMs, hillshades, and contours. **OpenTopography** federates the 3DEP data with subsetting and visualization capabilities, though access requires a `.edu` email or OT+ subscription. The Python library `py3dep` (part of HyRiver) provides the simplest programmatic access to pre-computed 3DEP DEMs:

```python
import py3dep
dem = py3dep.get_map("DEM", geometry, resolution=1, geo_crs="EPSG:4326", crs="EPSG:5070")
```

For raw point cloud work, PDAL's EPT reader streams data directly from AWS with spatial filtering, eliminating the need to download terabytes of tiles:

```python
pipeline = pdal.Reader.ept(
    filename="https://s3-us-west-2.amazonaws.com/usgs-lidar-public/PA_WesternPA_1_2019/ept.json",
    bounds="([-80.0,-79.5],[40.0,40.5])"
) | pdal.Writer("subset.laz")
```

---

## The Python toolchain for LiDAR terrain analysis

Five core libraries form the processing backbone, each handling a specific pipeline stage. **PDAL** (Point Data Abstraction Library) handles point cloud I/O, noise removal, ground classification, and initial rasterization through its Pythonic pipe-operator API. **laspy** provides direct NumPy-backed access to .las/.laz point attributes for custom analysis, with chunked reading for large files via `lazrs` backend. **WhiteboxTools** (480+ Rust-compiled geospatial tools with a Python frontend) excels at terrain derivative computation — slope, curvature, TPI, ruggedness index — using robust Florinsky (2016) algorithms. **rasterio** handles all GeoTIFF I/O and raster-to-vector conversion via `rasterio.features.shapes()`. **scipy.ndimage** provides the focal statistics engine (uniform_filter, generic_filter) for computing custom metrics like multi-scale TPI and surface roughness windows, while **scikit-learn** supplies the classifiers.

Ground classification is the critical first step. PDAL's **SMRF (Simple Morphological Filter)** is the recommended algorithm — faster than PMF and achieving 85.4% kappa with default parameters (90.02% optimized). For steep, forested Appalachian terrain, key parameter adjustments include increasing the slope tolerance to **0.2–0.25** (from default 0.15), expanding the maximum morphological window to **18–25m**, and setting the elevation threshold to **0.4–0.6m**. The filter should operate on last/only returns exclusively:

```python
pipeline = (
    pdal.Reader("raw.laz")
    | pdal.Filter.assign(value="Classification=0")
    | pdal.Filter.outlier(method="statistical", mean_k=12, multiplier=2.2)
    | pdal.Filter.elm()
    | pdal.Filter.smrf(slope=0.2, window=18, threshold=0.45, scalar=1.2, cell=1.0)
)
```

DTM generation from classified ground points works best via **Delaunay TIN interpolation** rather than simple IDW binning, which can produce striping artifacts. PDAL's `Filter.delaunay()` → `Filter.faceraster()` chain creates smooth, accurate DTMs. A **1.0m resolution** provides the optimal balance for detecting well pad features (20–60m scale) while keeping file sizes manageable. Void filling with scipy's `distance_transform_edt` handles gaps in canopy-dense areas.

For the Canopy Height Model, PDAL's `Filter.hag_delaunay()` computes height above ground per point, which is then gridded from first returns. The CHM reveals vegetation gaps that correlate with cleared well pads — even partially regrown sites show lower/younger vegetation than surrounding mature Appalachian forest.

---

## Algorithmic strategies from heuristics to deep learning

A tiered detection approach, moving from simple heuristics to machine learning refinement, provides the most practical path for a proof-of-concept.

**Tier 1: Rule-based candidate generation.** The first pass identifies anomalously flat areas by thresholding on slope (<5°) AND surface roughness (<0.15m in an 11×11 window), producing a binary mask of potential well pads. Morphological opening with a disk structuring element (radius 3 pixels) removes small noise features, followed by closing (radius 5 pixels) to fill gaps within pad footprints. Connected component labeling then isolates discrete patches, which are filtered by area (**2,000–20,000 m²**, corresponding to 0.5–5 acres) and shape compactness (>0.4, rejecting elongated features like roads). Multi-scale TPI at 50–100m windows helps exclude valley-floor flats (negative TPI) while retaining hillside platforms (positive TPI), since well pads preferentially occupy ridges and slopes rather than valley bottoms.

**Tier 2: Contextual filtering.** Genuine well pads almost always connect to an access road, which persists as a narrow (3–6m) linear low-slope feature in bare-earth DEMs. Skeletonization or Hough transform on the flatness mask can extract these linear features, and a proximity constraint (candidate within 50m of a linear feature) significantly reduces false positives. Overlaying NLCD land cover data excludes urban areas, active agriculture, and water bodies. Elevation context analysis rejects candidates on valley floors or within developed land parcels.

**Tier 3: ML-based scoring.** Each candidate object gets a feature vector: mean slope, slope standard deviation, mean roughness, area, compactness, elongation, mean TPI at 5 scales, mean CHM, distance to nearest road, and mean curvature. A **Random Forest classifier** (500+ trees, max_depth 15–25) trained on known well pad locations from PA DEP databases achieves roughly 89% accuracy based on analogous terrain classification benchmarks. **Isolation Forest** provides an unsupervised alternative, treating well pads as terrain anomalies with contamination set to 0.01–0.05. The USGS EROS team's CNN approach — feeding multi-channel terrain rasters (hillshade, slope, local relief, geomorphology) through a U-Net architecture — represents the state of the art but requires more training data.

Distinguishing well pads from look-alikes is the hardest sub-problem. Parking lots and building foundations tend to occur in valley floors with urban context; farm fields are typically larger (>5 acres) and on gentler terrain; natural meadows lack the sharp cut/fill boundary signatures visible in curvature maps. The **cut-and-fill signature** is uniquely diagnostic: well pads on slopes show an asymmetric TPI profile with a cut bank uphill and fill slope downhill that natural clearings lack. SkyTruth's experience training ML models for well pad detection confirmed that including "look-alike" negative examples (parking lots, farmland, housing developments) during training is essential for reducing false positives.

---

## Existing tools and Pennsylvania-specific detection efforts

**No complete open-source pipeline exists** for LiDAR-based well pad detection, but several components and datasets are available. The LANL/CATALOG program released a dataset of **120,948 aerial images of documented orphan wells** with segmentation masks on GitHub (`github.com/lanl/uow`), designed for training well detection models on NAIP imagery. Stanford's ML group published well pad detection code for satellite imagery (`github.com/stanfordmlgroup/well-pad-denver-permian`). The Alberta Wells Dataset from McGill/Mila provides 213,447 wells with PlanetScope imagery and U-Net/DETR benchmarks. None of these address LiDAR-based terrain analysis specifically — they focus on optical imagery.

The **CATALOG consortium** (Los Alamos, NETL, Lawrence Berkeley, Lawrence Livermore, Sandia; $40M+ under the Bipartisan Infrastructure Law) represents the largest coordinated federal effort. They deploy multi-sensor drones combining magnetometers, methane detectors, and LiDAR, and use machine learning to fuse noisy sensor streams. They've also developed U-Net models for extracting well symbols from historical USGS topographic maps, finding 1,301 potential undocumented wells across California and Oklahoma.

Pennsylvania specifically has seen intensive activity. The **NETL workflow** (Reeder et al., 2023, *The Leading Edge*) provides the definitive multi-source procedure: compile state/national well databases, overlay historical topographic maps, analyze LiDAR derivatives, rank candidate sites by confidence, and field-verify. PA DEP maintains a comprehensive **Oil and Gas Mapping Application** (`gis.dep.pa.gov/PaOilAndGasMapping/`) and has documented ~30,000 wells, but estimates 200,000–560,000 remain unaccounted for. The **EDF field campaign** (2024–2025) deployed drone magnetometers and methane sensors across northwestern PA (Clarion and McKean counties), identifying 250+ potential wells for verification, with a southwestern PA phase planned for 2025. A **$100 bounty program** run jointly by Oil Region Alliance, EDF, Penn State Extension, and PA DEP pays citizens for reporting previously unknown wells. PASDA provides downloadable shapefiles of both current (`dataset=1088`) and historical (`dataset=1137`) well locations — essential for training and validation.

---

## A proof-of-concept pipeline in six stages

The following architecture represents a minimal but functional system. Each stage maps to specific library calls and can be implemented incrementally.

**Stage 1 — Data acquisition and ingestion.** Use the TNM Access API or PDAL's EPT reader to pull raw LAZ tiles for the area of interest. For prototyping, stream a small subset (1–4 km²) from the AWS-hosted PA_WesternPA_1_2019 dataset. Verify coordinate reference system (NAD83 2011, PA State Plane South) and reproject to UTM Zone 17N for metric analysis via `pdal.Filter.reprojection`.

**Stage 2 — Ground classification and DTM generation.** Apply SMRF with Appalachian-tuned parameters (slope=0.2, window=18, threshold=0.45). Extract classified ground points and generate a 1m DTM via Delaunay TIN interpolation (`Filter.delaunay` → `Filter.faceraster`). Fill voids with distance-transform interpolation. Simultaneously generate a DSM from first-return maxima and compute the CHM by subtraction.

**Stage 3 — Terrain derivative computation.** Use WhiteboxTools for slope, profile/plan curvature, and terrain ruggedness index. Compute multi-scale TPI at 11m, 51m, and 101m windows using `scipy.ndimage.uniform_filter`. Calculate surface roughness as local standard deviation of elevation in 5×5 and 11×11 windows. Generate multi-azimuth hillshade for visualization.

**Stage 4 — Candidate detection.** Apply the tiered detection approach: threshold on slope and roughness, morphological cleanup, connected component labeling, and area/shape filtering. A key gotcha: the coordinate system must use metric units for area calculations to work correctly, and nodata values must be masked throughout to prevent false detections at tile boundaries.

**Stage 5 — Feature extraction and scoring.** For each candidate polygon, extract per-object statistics from all terrain layers. Run through a Random Forest or Isolation Forest for confidence scoring. Cross-reference against PA DEP known well locations to flag potential new discoveries versus already-documented sites.

**Stage 6 — Export.** Convert scored candidates to GeoDataFrame via `rasterio.features.shapes()` and export as GeoPackage or GeoJSON with attributes (area, confidence score, mean slope, TPI class, CHM status). Include CRS metadata for direct loading into QGIS or ArcGIS.

**Critical gotchas** to anticipate: SMRF ground classification can misclassify exposed rock faces as non-ground in steep terrain — validate visually on hillshade. Tile edge effects create artifacts in focal statistics — use buffered processing extents and clip to the true extent afterward. Memory management matters for large areas: process tiles individually using laspy's chunked reader rather than loading entire county datasets. The PA_WesternPA_1_2019 data uses US Survey Feet vertically — convert to meters before computing slope and curvature to get correct units. Finally, LiDAR collection date matters: leaf-off data (November–March) produces dramatically better bare-earth results than leaf-on, and the 2019–2020 western PA collection was specifically timed for this.

---

## Conclusion

The convergence of three factors makes this proof-of-concept both feasible and timely: Pennsylvania's high-quality 7+ pts/m² statewide LiDAR coverage is freely available and streamable from AWS; NETL's decade of field research has precisely characterized the terrain signatures that orphaned well pads leave in bare-earth DEMs; and the Python geospatial ecosystem (PDAL + WhiteboxTools + scikit-learn + rasterio) provides every processing capability needed. The key insight from the literature is that **LiDAR-based terrain analysis is the only viable approach for detecting pre-1955 wooden-cased wells in forested terrain** — magnetic surveys miss them, optical imagery cannot penetrate canopy, and state databases contain fewer than 40% of wells drilled before 1955. A pipeline that combines rule-based flatness detection with ML scoring on multi-scale terrain features, validated against NETL's Oil Creek State Park ground-truth data, would represent the first automated open-source tool for this specific application — directly supporting the $400M federal investment in Pennsylvania's orphaned well remediation.