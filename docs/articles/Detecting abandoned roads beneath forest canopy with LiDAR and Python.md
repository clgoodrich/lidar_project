# Detecting abandoned roads beneath forest canopy with LiDAR and Python

Old logging and access roads in western Pennsylvania's Appalachian hardwoods leave persistent topographic signatures — subtle benches, cut slopes, and fill embankments — that remain detectable decades after abandonment. **A practical Python pipeline combining PDAL for ground classification, WhiteboxTools and RVT for terrain derivatives, and scikit-learn for machine-learning-based detection can identify these features at 86–90% accuracy** when applied to modern QL2 LiDAR data. The 2019–2020 USGS 3DEP dataset covering 20 western PA counties at ~2 points/m² provides sufficient density for 1-meter DTM generation, which is the critical resolution threshold for abandoned road detection. This report lays out every stage of that pipeline — from raw LAZ ingestion through vectorized road centerlines — with specific library calls, parameter recommendations, and quantification methods.

## The Python toolkit for LiDAR point cloud processing

The core stack for this workflow consists of five libraries, each handling a distinct role. **PDAL** (Point Data Abstraction Library) serves as the primary processing engine for reading LAS/LAZ files, performing ground classification, and generating DTMs. Install it via `conda install -c conda-forge pdal python-pdal`. PDAL supports both JSON-based pipeline construction and a newer Pythonic pipe-operator API:

```python
import pdal
pipeline = (
    pdal.Reader("input.laz")
    | pdal.Filter.assign(value=["Classification=0"])
    | pdal.Filter.outlier(method="statistical", mean_k=8, multiplier=3.0)
    | pdal.Filter.smrf(slope=0.2, window=18, threshold=0.45, scalar=1.25,
                       cell=1.0, returns="last, only")
    | pdal.Writer.gdal(filename="dtm.tif", where="Classification == 2",
                       output_type="idw", resolution=1.0, data_type="float32")
)
pipeline.execute()
```

**laspy** (v2.x, install with `pip install laspy[lazrs]`) provides direct numpy-backed access to LAS/LAZ point attributes — coordinates, classification, return number, intensity — and supports chunked reading for files too large to fit in memory. **WhiteboxTools** (`pip install whitebox`) contributes over 500 geomorphometric analysis tools written in Rust, covering terrain derivatives like slope, curvature, openness, hillshade, and a dedicated `embankment_mapping` tool directly relevant to road detection. The **Relief Visualization Toolbox** (RVT, `pip install rvt-py`) implements sky-view factor, openness, Simple Local Relief Model, and composite archaeological visualizations developed by Kokalj and colleagues at ZRC SAZU. **rasterio** handles all GeoTIFF I/O with proper CRS metadata.

For ground classification — the most consequential step for road detection — three algorithms dominate. **SMRF** (Simple Morphological Filter, `filters.smrf` in PDAL) is the recommended default; it performs morphological operations at progressively increasing window sizes and is less prone to degenerate behavior than alternatives. For western PA's moderate-to-steep Appalachian terrain under deciduous canopy, start with `slope=0.2`, `window=16–18`, `threshold=0.45`, `scalar=1.2`, and `returns="last, only"`. The **CSF** (Cloth Simulation Filter, `filters.csf` in PDAL or standalone via `pip install cloth-simulation-filter`) simulates a virtual cloth draping over an inverted point cloud — set `rigidness=1` or `2` for sloped terrain and `resolution=0.5–1.0`. **PMF** (Progressive Morphological Filter) is available but PDAL's documentation explicitly recommends SMRF over it for fewer edge cases.

A critical nuance for detecting subtle road features: **overly aggressive ground filtering erases the 10–30 cm elevation anomalies that define abandoned road benches**. Keep `threshold` at 0.3–0.5m rather than pushing lower, and use `returns="last, only"` to leverage canopy-penetrating last returns. Leaf-off acquisition — which the 2019–2020 western PA dataset used (winter collection) — dramatically improves ground point density under deciduous canopy.

For DTM generation, **TIN interpolation preserves terrain breaklines** (road cuts, fill edges) better than IDW, which tends to smooth these features. PDAL's `filters.delaunay` → `filters.faceraster` → `writers.raster` chain produces high-quality TIN-based DTMs, while `scipy.interpolate.griddata` with `method='linear'` provides an equivalent pure-Python approach. Target **1.0m resolution** as the working default; 0.5m is feasible where ground point density exceeds 4 pts/m². Research by Sherba et al. (2014) demonstrated that road detection accuracy drops below 50% when ground point spacing exceeds 2m.

## Terrain derivatives that reveal roads hiding beneath trees

Not all terrain derivatives contribute equally to abandoned road detection. The most diagnostic products exploit a fundamental property: **roads create locally flat, linear features with abrupt slope breaks at cut banks and fill edges** that differ systematically from natural hillslope morphology.

**Local Relief Model (LRM)** is arguably the single most powerful derivative for this application. Introduced by Hesse (2010) for archaeological prospection, LRM removes large-scale topographic trends by subtracting a low-pass-filtered DTM from the original, isolating only micro-topographic anomalies. Sunken roads, benched roads, and embankments appear as clear positive/negative residuals regardless of hillslope position or aspect. The computation is straightforward:

```python
from scipy.ndimage import uniform_filter
import rasterio

with rasterio.open("dtm.tif") as src:
    dtm = src.read(1).astype(float)
    profile = src.profile

smoothed = uniform_filter(dtm, size=25)  # ~25m kernel at 1m resolution
lrm = dtm - smoothed

profile.update(dtype="float32")
with rasterio.open("lrm.tif", "w", **profile) as dst:
    dst.write(lrm.astype("float32"), 1)
```

WhiteboxTools provides this as `wbt.dev_from_mean_elev()`, and RVT offers `rvt.vis.slrm()` with configurable radius. Kernel size of **20–30 cells** (at 1m resolution) works well for road-width features; multi-scale analysis using kernels at 10m, 25m, and 50m captures roads of varying width and preservation state.

**Topographic openness** — both positive and negative — avoids the directional bias that plagues hillshading. Positive openness (mean zenith angle to horizon in 8+ directions) highlights convex forms like road crowns and embankments; negative openness highlights concave forms like ditches and sunken roads. Doneus (2013) demonstrated that openness produces consistent feature signatures regardless of slope position, making it ideal for automated detection where roads traverse diverse terrain. RVT computes both simultaneously:

```python
import rvt.vis
svf_result = rvt.vis.sky_view_factor(
    dem, resolution=1.0, compute_svf=True, compute_opns=True,
    svf_n_dir=16, svf_r_max=10
)
openness = svf_result["opns"]
svf = svf_result["svf"]
```

**Sky-View Factor** quantifies the fraction of visible sky at each cell, ranging from 0 (fully enclosed) to 1 (unobstructed). Road cuts appear as dark linear features; embankments appear lighter. Zakšek et al. (2011) established 16 search directions as optimal, with search radius controlling the scale of features detected.

**Slope** remains the most important single derivative for initial road visualization. Roads maintain gradients below 10° while surrounding Appalachian hillslopes typically exceed 15–25°. White et al. (2010) found 100% of forest roads visible in LiDAR-derived slope maps versus only 15% in orthophotos. **Profile curvature** and **maximal curvature** highlight the characteristic breaks-in-slope at road edges. WhiteboxTools computes all curvature variants:

```python
wbt = WhiteboxTools()
wbt.slope("dtm.tif", "slope.tif")
wbt.profile_curvature("dtm.tif", "prof_curv.tif")
wbt.maximal_curvature("dtm.tif", "max_curv.tif")
wbt.multidirectional_hillshade("dtm.tif", "multi_hs.tif")
wbt.dev_from_mean_elev("dtm.tif", "dev.tif", filterx=11, filtery=11)
```

For visual interpretation and training data creation, the **Red Relief Image Map** (RRIM) combines slope intensity with openness-derived brightness to produce direction-independent, information-dense composites. The **VAT** (Visualization for Archaeological Topography) blend developed by Kokalj and Somrak (2019) layers hillshading, slope, positive openness, and SVF using photographic blend modes — implemented in RVT as `rvt.vis.mstp()`.

A multi-scale approach is essential. Compute Topographic Position Index and LRM at **3–5 window sizes** (e.g., 5, 11, 21, 51 cells) and stack all derivatives into a multi-band raster for machine learning input. This captures both narrow single-lane logging roads and wider two-lane haul roads in a single feature set.

## From terrain maps to detected roads: classification algorithms

Three tiers of detection approaches exist, ranging from rapid semi-automated methods to research-frontier deep learning.

**Random Forest on terrain derivative stacks** represents the practical sweet spot. Ferraz, Mallet, and Chehata (2016) demonstrated this at scale: their fully automated pipeline classified morphological features from a 1m DTM using Random Forest, then constructed a graph over candidate regions and pruned it using elongation and width criteria. Applied across **1,425 km²** of French mountainous forest, it achieved >80% detection with 10–15% false positives and processed each square kilometer in under 2 minutes.

```python
from sklearn.ensemble import RandomForestClassifier
import numpy as np, rasterio

# Stack 8 derivative bands
derivative_files = ["slope.tif", "prof_curv.tif", "max_curv.tif",
    "openness_pos.tif", "openness_neg.tif", "slrm.tif",
    "tpi_5.tif", "tpi_15.tif"]
bands = []
for f in derivative_files:
    with rasterio.open(f) as src:
        bands.append(src.read(1))
X = np.stack(bands, axis=-1).reshape(-1, len(bands))

# Train on manually digitized road/non-road samples
rf = RandomForestClassifier(n_estimators=500, max_depth=20,
    min_samples_leaf=10, oob_score=True, n_jobs=-1)
rf.fit(X_train, y_train)
prediction = rf.predict_proba(X)[:, 1].reshape(bands[0].shape)
```

Feature importance rankings from the literature consistently show **slope** as the top predictor, followed by **LRM**, **SVF/openness**, and **profile curvature**. Training data preparation involves manually digitizing known road segments on LRM or multi-directional hillshade visualizations, buffering centerlines by estimated width (3–5m), and creating binary raster masks. Balance the training set — road pixels are a small minority — using stratified sampling or class weighting.

**Deep learning via U-Net** semantic segmentation offers higher accuracy when sufficient training data exists. Georges, Ngo, and Even (2023) and Salberg et al. (2017) applied CNNs to DTM-derived images for forest road extraction. Using `segmentation-models-pytorch`:

```python
import segmentation_models_pytorch as smp
model = smp.Unet(encoder_name="resnet34", encoder_weights=None,
    in_channels=8, classes=1, activation="sigmoid")
```

The input is tiled 256×256 patches from the terrain derivative stack; the output is a binary road probability mask. Training requires several hundred manually labeled patches, augmented with random rotation and flipping since roads appear at arbitrary orientations.

**Morphological and image-processing methods** require no training data and work well for semi-automated workflows. Ridge detection filters from scikit-image — `meijering`, `sato`, and `frangi` — applied to LRM or negative openness highlight linear tubular structures characteristic of roads. Gabor filter banks at 12–15 orientations capture linear features regardless of direction. Post-detection, **skeletonization** (`skimage.morphology.skeletonize`) reduces binary road masks to single-pixel-wide centerlines, and **connected component analysis** filters fragments by eccentricity (roads are elongated: eccentricity >0.9) and minimum area.

For connecting fragmented detections, **least-cost path analysis** using `skimage.graph.MCP_Geometric` traces optimal routes through a cost surface derived from inverted road probability — forcing paths to follow high-probability road corridors between known endpoints.

Sherba et al. (2014) achieved **86–90% accuracy** using object-based classification on slope models alone, demonstrating that even simpler approaches work when point density is adequate. Their study in Marin County, California found accuracy declined from 79% at 0.91m ground point spacing to below 50% at 2m spacing — underscoring the importance of point density over algorithmic sophistication. Buján et al. (2021) confirmed this density-accuracy relationship: 86% accuracy at 12 pts/m², 78% at 6 pts/m², 67% at 3 pts/m², and only 49% at 0.8 pts/m².

## LiDAR data covering western Pennsylvania's forests

The **2019–2020 USGS QL2 Western Pennsylvania** dataset is the primary resource. Collected during leaf-off winter conditions across **20 counties** (~14,790 square miles) in three work units, it delivers a nominal pulse spacing of **0.71 meters (~2 pts/m²)** in classified LAS 1.4 format. Tiles are 1,500m × 1,500m in NAD83(2011) UTM Zone 17N coordinates with NAVD88 vertical datum. This dataset covers the Allegheny National Forest, numerous state forests, and game lands where abandoned roads are prevalent.

Access this data through multiple portals:

- **USGS LiDAR Explorer** (apps.nationalmap.gov/lidar-explorer/) — interactive map browser with tile-level selection and direct LAZ download
- **NOAA Digital Coast Data Access Viewer** (coast.noaa.gov/dataviewer/) — custom area selection with projection/format options
- **AWS Open Data** (registry.opendata.aws/usgs-lidar/) — bulk access in Entwine Point Tiles (EPT) format for streaming, plus raw LAZ via requester-pays S3
- **OpenTopography** (portal.opentopography.org/) — cloud-based processing with on-demand DEM generation, though access is currently limited to academic users

The older **PAMAP statewide dataset** (2006–2008) covers all of Pennsylvania at ~0.5 pts/m² (1.4m average spacing) in PA State Plane coordinates. Available through **PASDA** (pasda.psu.edu), this dataset's lower density places it near the detection threshold — adequate for manual visual interpretation of LRM and hillshade products but marginal for automated classification. Derived products (DEMs, contours) are freely downloadable; raw LAS tiles require bulk ordering from PA's State Data Center.

For the Allegheny County/Pittsburgh area specifically, higher-resolution 2015 and 2017 LiDAR collections are available through PASDA. The USDA Forest Service's FSGeodata Clearinghouse (data.fs.usda.gov/geodata/) provides existing road network shapefiles for the Allegheny National Forest that serve as validation data for newly detected abandoned roads.

## End-to-end pipeline from LAZ to road shapefiles

A complete proof-of-concept pipeline involves six stages, orchestrated through a configuration-driven Python project:

**Stage 1 — Ingest and QC**: Read LAZ tiles with PDAL, verify CRS (should be EPSG:26917 for western PA), compute point density statistics, and filter noise using `filters.elm` (Extended Local Minimum) followed by `filters.outlier`. Use `filters.splitter` to tile large areas into manageable 1,000m chunks with overlap buffers.

**Stage 2 — Ground classification**: Apply SMRF with parameters tuned for Appalachian forested terrain (`slope=0.2`, `window=16`, `threshold=0.45`, `scalar=1.2`, `returns="last, only"`). Visually inspect results on a few sample tiles using hillshade before batch-processing the full dataset. If SMRF produces unsatisfactory results on steep slopes, try CSF with `rigidness=1` and `resolution=0.5`.

**Stage 3 — DTM generation**: Interpolate ground points to a 1.0m GeoTIFF using PDAL's `filters.delaunay` → `filters.faceraster` → `writers.raster` chain for TIN interpolation, or `scipy.interpolate.griddata` with `method='linear'`. Fill remaining voids with nearest-neighbor interpolation or `gdal_fillnodata.py`.

**Stage 4 — Terrain derivatives**: Compute the feature stack using WhiteboxTools and RVT — slope, profile curvature, maximal curvature, positive/negative openness, SVF, SLRM at 10m and 25m kernels, TPI at 5m and 15m scales. Write all as co-registered GeoTIFFs, then stack into a single multi-band raster with rasterio.

**Stage 5 — Detection**: Train a Random Forest classifier on manually digitized road/non-road samples extracted from the feature stack. Apply to the full study area, threshold the probability output at 0.5, clean with morphological closing (fill gaps) and opening (remove noise), filter connected components by elongation, and skeletonize to extract centerlines.

**Stage 6 — Vectorize and export**: Convert skeleton raster to vector lines using `rasterio.features.shapes`, simplify with Douglas-Peucker (`tolerance=2.0` meters), and write to GeoJSON or shapefile via geopandas. Attach per-segment attributes: length, mean slope, mean width, canopy recovery ratio.

```yaml
# config.yaml
input:
  las_dir: "/data/western_pa_lidar/"
  epsg: 26917
ground:
  algorithm: "smrf"
  params: {slope: 0.2, window: 16, threshold: 0.45, scalar: 1.2}
dtm:
  resolution: 1.0
  method: "tin"
derivatives:
  slrm_kernels: [10, 25]
  tpi_radii: [5, 15]
detection:
  method: "random_forest"
  n_estimators: 500
  training_data: "training/roads.shp"
output:
  format: "geojson"
  min_road_length: 50  # meters
```

## Measuring what the roads left behind

Quantifying abandoned road characteristics requires extracting perpendicular cross-sections along detected centerlines and computing summary statistics within road footprint polygons.

**Width measurement** relies on identifying slope breaks in DTM cross-sections. At regular intervals (every 5–10m) along the centerline, extract a perpendicular elevation profile extending 15m in each direction. Road edges manifest as inflection points in the second derivative of elevation — the transition from the flat road bench to the steep cut slope or fill slope. Using `scipy.signal.find_peaks` on the absolute curvature of the cross-section identifies these transitions. Typical abandoned forest road widths range from **3–6m** (single-lane logging roads) to **8–12m** (two-lane haul roads).

**Cut-and-fill signatures** distinguish road types. Full-bench cuts show one steep face above the road on the uphill side with no fill below. Balanced cut-and-fill shows symmetric signatures. The cut depth — elevation difference between the extrapolated natural hillslope and the road bench — typically ranges from **0.5–3m** for forest roads. Fill material commonly extends 5–15m downslope.

**Vegetation recovery metrics** leverage the full point cloud, not just the DTM. Compare the Canopy Height Model (CHM = DSM minus DTM) within the road footprint against surrounding forest: a recovery ratio near 0 indicates bare or low-vegetation road surface; near 1.0 indicates full canopy closure. The ratio of ground returns to total returns within the road polygon provides another proxy — open roads show ratios of 0.5–0.9 while fully vegetated areas drop to 0.1–0.3. Use `rasterstats.zonal_stats` to efficiently compute these metrics over hundreds of road segments.

**Drainage impact assessment** uses flow accumulation analysis on the high-resolution DTM. Roads intercept subsurface flow and concentrate overland runoff, appearing as barriers or concentrators in WhiteboxTools' `d8_flow_accumulation` output. Road segments hydrologically connected to streams — identified by tracing flow paths from road surfaces to the nearest channel — carry the highest remediation priority. Madej (2001) documented that untreated abandoned roads produce **1,500–4,700 m³ of sediment per kilometer**, while treated roads reduce this to 10–550 m³/km depending on hillslope position.

A composite **Road Condition Score** integrating canopy recovery (0–10), surface roughness (0–10), drainage connectivity (0–10), and erosion risk based on gradient (0–10) enables systematic prioritization across hundreds of detected segments.

## Conclusion

The technical barriers to detecting abandoned roads beneath Appalachian forest canopy have largely dissolved. Modern QL2 LiDAR at 2 pts/m² — freely available for all of western Pennsylvania — provides sufficient ground point density for reliable 1m DTM generation. The combination of **LRM and topographic openness** exposes road features that are invisible in orthophotos and even in standard hillshade visualizations. A Random Forest classifier trained on a stack of 6–8 terrain derivatives achieves detection rates above 80% with modest manual effort for training data creation. The entire workflow — from LAZ file to attributed road centerline shapefile — runs in open-source Python using PDAL, WhiteboxTools, scikit-learn, and geopandas, with no commercial software dependencies.

Three practical insights emerge from the literature. First, **point density matters more than algorithmic sophistication** — invest effort in acquiring the best available LiDAR before optimizing classification parameters. Second, **LRM and openness outperform hillshade** for both manual interpretation and automated detection because they are direction-independent and remove large-scale topographic trends that mask subtle road features. Third, **cross-section analysis provides the most reliable road characterization**, enabling width measurement, cut/fill classification, and erosion risk assessment from a single DTM product. For western PA specifically, the 2019–2020 QL2 dataset combined with the Allegheny National Forest's known road network provides an ideal testbed for developing and validating a detection pipeline before scaling to broader areas.