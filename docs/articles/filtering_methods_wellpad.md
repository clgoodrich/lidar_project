# Algorithms for detecting anthropogenic features in LiDAR bare-earth DEMs

**No peer-reviewed method exists specifically for detecting abandoned well pads in LiDAR DEMs**, but a rich body of validated algorithms from LiDAR archaeology, karst geomorphology, and forest road mapping provides a near-complete toolkit for this task. The most transferable approaches combine terrain normalization (Local Relief Models, Sky-View Factor), morphometric segmentation (fill-difference, watershed, multiresolution), and object-level machine learning classification using shape descriptors—a pipeline that has achieved **90–97% detection accuracy** for geometrically analogous features like burial mounds, charcoal hearths, and sinkholes. The closest published work targeting well pads directly is a USGS/FWS government technical report using CNNs on LiDAR hillshade, which achieved 82% true-positive rates at Deep Fork NWR. This review consolidates over 30 validated algorithms across eight methodological families, organized by how they would compose into a well-pad detection pipeline.

---

## Terrain normalization strips topography to expose engineered surfaces

Automated detection of subtle anthropogenic features in rugged terrain requires first removing the large-scale topographic signal. Three foundational algorithms accomplish this, each with distinct strengths.

**The Local Relief Model (LRM)**, introduced by Hesse (2010) in *Archaeological Prospection*, remains the most widely adopted preprocessing step for automated detection pipelines. The algorithm applies a low-pass mean filter to the DEM (typically an 11-cell kernel at 1 m resolution), subtracts the smoothed surface from the original, then iteratively refines by extracting zero-contour lines, sampling original elevations along them, interpolating a "purged DEM," and computing the final difference. Applied across **35,751 km² in Baden-Württemberg**, LRM revealed 57,936 potential archaeological sites versus 3,726 previously known—a **15× improvement**. Its limitation is degraded performance on steep terrain where large elevation gradients overwhelm the mean filter.

**Sky-View Factor (SVF)**, formalized for archaeological LiDAR by Zakšek, Oštir, and Kokalj (2011) in *Remote Sensing*, computes the proportion of visible sky hemisphere at each DEM cell by measuring maximum horizon elevation angles along typically 16 radial directions within a specified search radius. Concave features (depressions, pits) appear dark; convex features (mounds, platforms) appear bright. The method is illumination-independent—a critical advantage over hillshading for automated processing. Štular et al. (2012) in *Journal of Archaeological Science* found SVF to be the **single best overall visualization** across terrain types for archaeological feature detection, alongside slope gradient.

**Topographic openness**, introduced by Yokoyama, Shirasawa, and Pike (2002) in *Photogrammetric Engineering & Remote Sensing*, extends the SVF concept by computing both positive openness (dominance/convexity) and negative openness (enclosure/concavity) across variable radial distances. Doneus (2013) demonstrated in *Remote Sensing* that openness produces more accurate feature delineation on steep terrain than LRM, precisely where LRM fails. The differential openness (positive minus negative, divided by two) maps ridges as bright and valleys as dark, forming the basis of the **Red Relief Image Map (RRIM)** by Chiba, Kaneta, and Suzuki (2008). Kokalj and Somrak (2019) unified these into the **Visualization for Archaeological Topography (VAT)** composite in the open-source Relief Visualization Toolbox, blending hillshading, slope, positive openness, and SVF into a single image.

For well pad detection, the typical preprocessing chain is: **Raw LiDAR → bare-earth DEM → LRM (flat/moderate terrain) or openness (steep terrain) → derivative rasters (slope, TPI, curvature) → feature extraction**. The LRM is particularly well-suited because well pads create exactly the kind of small-scale elevation anomaly (flat platform with surrounding cut-and-fill) that LRM was designed to isolate.

---

## Object-based segmentation outperforms pixel classification for compact features

Object-Based Image Analysis (OBIA) applied to LiDAR DEM derivatives has emerged as the dominant paradigm for detecting discrete anthropogenic landforms, consistently outperforming pixel-based classification for features with defined geometric properties.

**Sevara et al. (2016)** conducted the definitive comparison in *Journal of Archaeological Science: Reports*, testing pixel-based versus object-oriented classification for burial mound detection at Birka (Sweden) and Kreuttal (Austria). Using multiresolution segmentation (the Baatz-Schäpe algorithm) on openness-derived rasters, the OBIA approach produced **more robust and transferable results** than pixel-based thresholding. The segmentation generates objects whose shape descriptors—compactness, elongation, area, mean slope—become the classification features.

**Witharana, Ouimet, and Johnson (2018)** applied Geographic OBIA specifically to flat, circular anthropogenic platforms in *GIScience & Remote Sensing*. Their target—**relict charcoal hearths** (~8–12 m diameter circular flat platforms) in forested southern New England—is geometrically near-identical to small well pads. The workflow applied multiresolution segmentation to DEM derivatives (slope, curvature, TPI, and a difference-from-smoothed-DEM map), then classified candidate objects using rule-based criteria on size, shape (compactness, roundness), and topographic properties (mean TPI, relative height). The method successfully extracted hearths matching field-verified locations under full forest canopy.

**Meyer, Pfeffer, and Jürgens (2019)** achieved approximately **90% hit rates** across three distinct monument types (burial mounds, ridge-and-furrow, motte-and-bailey castles) using eCognition OBIA on a "Difference Map" (essentially an LRM) in *Geosciences*. Their classification rules incorporated area thresholds, compactness indices, shape descriptors, and relative height above surrounding terrain. A valuable design choice was classifying features into multiple erosion-degree classes rather than binary detection, which preserved degraded features that might otherwise be missed.

**Davis, Sanger, and Lipo (2019)** scaled OBIA to **2,481 km²** in Beaufort County, South Carolina, combining multiresolution segmentation with template matching to detect earthen mounds and shell rings in *Southeastern Archaeology*. The approach identified **186 probable cultural features, 160+ previously undetected**, within a single week—work that would have required years of pedestrian survey. Davis's 2020 review in *Journal of Archaeological Science* subsequently catalogued 35+ publications using OBIA for archaeological LiDAR detection, identifying four dominant algorithms: multiresolution segmentation, inverse depression analysis, template matching, and combined approaches.

---

## Template matching detects features with known morphometric signatures

Cross-correlation of morphometric templates against DEM derivative rasters provides a direct, physics-interpretable detection method for features with predictable geometric profiles—circular pits, mound forms, or rectangular platforms.

The foundational work is **Trier and Pilø (2012)** in *Archaeological Prospection*, who designed circular pit templates (white center pixels at +1, dark rim pixels at −1, with gray transition) and convolved them against LiDAR DEMs via normalized cross-correlation to detect charcoal burning pits and pitfall traps in Oppland County, Norway. Peaks in the correlation surface above a threshold become candidate detections, which are then filtered by elongation, area, and depth. The method achieved **~10× faster field survey** and was subsequently adopted as standard procedure in Norwegian archaeological mapping.

**Schneider et al. (2015)** in *Archaeological Prospection* advanced this approach by evaluating template matching across multiple morphometric rasters—slope, profile curvature, plan curvature, TPI, and LRM—for detecting charcoal kiln sites (~10–18 m diameter circular platforms) near Cottbus, Germany. The critical finding: **combining multiple morphometric variables significantly reduced false detections** compared to any single variable. For kilns ≥10 m diameter, detection rates matched manual digitization. They validated on both synthetic DEMs (with added noise and irregular geometry) and real archaeological data.

**Stott, Kristiansen, and Sindbæk (2019)** demonstrated national-scale template matching in *Remote Sensing* by applying the **Hough circle transform** to a thresholded boolean edge array derived from the Danish national LiDAR DEM to detect Viking-age ring fortresses (120–240 m diameter). The initial pass detected **202,048 circular features** across all of Denmark. DBSCAN clustering, geometric filtering (eliminating features <90 m), and Random Forest classification reduced this to 199 candidates, from which **2 compelling new fortress sites** were identified. This pipeline—geometric detection at massive scale followed by ML-based refinement—is directly applicable to well pad detection.

**Toumazet et al. (2017)** addressed a limitation of classical template matching in *Journal of Archaeological Science: Reports*: its inability to detect complex, connected structures. By defining elementary structures through morphometric characteristics and then grouping them by spatial adjacency, the method detected 225 interconnected grazing structures over 0.5 km² in the French Massif Central—an approach relevant to detecting well pad complexes with associated access roads and berms.

---

## Depression detection algorithms extract candidate features from DEMs

Three established approaches extract topographic depressions (and by inversion, elevated platforms) from LiDAR DEMs, producing the candidate objects that downstream classifiers evaluate.

The **fill-difference method**, systematically evaluated by Doctor and Young (2013), fills all DEM depressions to their spill elevation, then subtracts the original DEM to produce a difference raster where non-zero pixels mark depression locations and depths. Connected components in this raster become individual depression polygons. The method requires DEM reconditioning (burning stream lines at road crossings to prevent false dams) and works best for larger depressions. For well pad detection, applying this method to an *inverted* DEM would extract elevated flat platforms.

The **TPI thresholding method**, also evaluated by Doctor and Young, computes the Topographic Position Index at an appropriate neighborhood scale and extracts pixels below a threshold (e.g., TPI ≤ −0.18 m) as a binary mask. Connected component labeling identifies individual candidate depressions, which are filtered by area, depth, and compactness. TPI is scale-dependent but avoids the artificial dam problem of fill-difference.

**Wu et al. (2019)** introduced a **level-set method** in *Journal of the American Water Resources Association* that progressively "slices" the DEM at increasing elevation intervals, building a hierarchical tree of nested depressions with parent-child topology. Each depression is characterized by size, volume, mean/maximum depth, perimeter, elongation, eccentricity, orientation, and area-to-bounding-box ratio. This hierarchical approach, implemented in the open-source `lidar` Python package, enables scale-dependent classification—critical for distinguishing anthropogenic features from natural depressions at multiple scales.

**Kobal et al. (2015)** in *PLoS ONE* developed a water-flow simulation approach for multi-rank sinkhole delineation under forest canopy, classifying depressions by elongation ratio into circular (Re ≤ 1.21), elliptical, sub-elliptical, and elongated categories. Non-karst depressions were filtered by minimum depth (>2 m) and diameter (>10 m) thresholds.

---

## Machine learning on morphometric object properties achieves the highest validated accuracies

The most accurate published approaches combine geometric segmentation with ensemble classifiers trained on shape descriptors—precisely the architecture most suited to well pad detection.

**Niculiță (2020)** in *Sensors* provides the clearest end-to-end example. The pipeline: (1) identify local elevation maxima as peak seeds; (2) apply **watershed segmentation** on a local convexity raster to delineate objects; (3) extract shape descriptors (compactness, elongation, area, perimeter, roundness) and geomorphometric statistics (mean/std/min/max of slope, curvature, convexity) for each segment; (4) train a **Random Forest classifier** for binary classification (burial mound vs. not). On an external validation dataset in NE Romania, **93% of burial mound segments were correctly identified**, with 42 false positives requiring field checking. Latin Hypercube Sampling for negative examples and 10× class imbalance in training improved robustness.

**Guyot, Hubert-Moy, and Lorho (2018)** in *Remote Sensing* introduced **Multi-Scale Topographic Position (MSTP)**, computing topographic position at micro, meso, and macro scales from a 14 pts/m² LiDAR DTM and visualizing as an RGB composite. Random Forest trained on MSTP pixel signatures achieved **Cohen's kappa = 0.98** for Neolithic burial mound detection in the Carnac region of France, with <1% of pixels in the ambiguous 0.3–0.7 probability range. The model successfully transferred from open terrain (Kerlescan) to dense forest (Lann Granvillarec) and confirmed a **previously unknown Neolithic burial mound**.

**Zhu et al. (2020)** in *Journal of Hydrology* tested six ML methods on 10 morphometric features of 22,884 LiDAR-extracted depressions in Kentucky's Bluegrass karst region. Neural networks performed best (AUC = **0.950**), followed by Random Forests (0.947) and RUSBoost (0.942). Field validation confirmed **97.3% of probable sinkholes** (144 of 148 checked) as actual sinkholes. The 10 morphometric features—perimeter, area, compactness, mean depth, max depth, volume, mean slope, depth-to-area ratio, elongation, and orientation—constitute the standard feature vector for depression classification and are directly transferable to well pad detection.

---

## Forest road detection algorithms map the access infrastructure associated with well pads

Road detection under canopy is a mature subfield with multiple validated approaches, directly relevant because abandoned well pads nearly always have associated access roads.

**Sherba, Blesius, and Davis (2014)** in *Remote Sensing* achieved **86% overall accuracy** (90% with post-processing) for fully automated abandoned logging road detection using OBIA on slope rasters derived from 1 m LiDAR DEMs in Marin County, California. The method exploits the contrast between low-slope road surfaces and steep surrounding terrain: multiresolution segmentation of the slope raster identifies road seed objects, which are iteratively grown using slope thresholds. A critical finding was that **accuracy dropped below 50% when ground point spacing exceeded 2.0 m**, establishing minimum LiDAR density requirements.

**Ferraz, Mallet, and Chehata (2016)** in *ISPRS Journal of Photogrammetry and Remote Sensing* demonstrated the first fully automatic large-scale forest road detection across **1,425 km²** of the Vosges Mountains, using only DTM-derived slope maps. The three-step pipeline—Random Forest classification of road patches from morphological features, graph construction with stochastic geometry to fill canopy gaps, and graph pruning with OBIA characterization—achieved **82–90% true-positive road length** at <2 minutes per km². No intensity data was required.

**Clode et al. (2007)** in *Photogrammetric Engineering & Remote Sensing* introduced the **Phase Coded Disk (PCD)** convolution, a complex-valued disk kernel that simultaneously extracts road centerlines, widths, and directions from LiDAR data. Completeness reached 84–88%, with correctness of 75–80% in urban settings. **Passalacqua et al. (2010, 2012)** developed GeoNet, using **Perona-Malik nonlinear diffusion filtering** to preserve edges while removing noise, followed by geodesic path computation—an approach transferable from channel networks to any linear feature extraction from LiDAR DEMs.

---

## The well pad detection gap and the closest published work

**No peer-reviewed journal paper describes a validated algorithm specifically for detecting abandoned oil and gas well pads from LiDAR.** This represents a clear research gap, though relevant work is emerging.

The most directly relevant published work is **Sesnie et al. (2021–2022)**, a series of USGS/FWS technical reports (not peer-reviewed journals) documenting CNN-based detection of abandoned well infrastructure from LiDAR-derived terrain data at Deep Fork NWR, Oklahoma. Using 0.5 m bare-earth DEMs from USGS 3DEP (QL1, >8 returns/m²), the approach trained convolutional neural networks on hillshade, geomorphology, and local relief layers. Of 39 CNN-detected sites, **82% contained well infrastructure evidence**; of 18 novel detections not in training data, the true-positive rate was 66.7%. The work is part of the USFWS BIL/IIJA orphan well remediation program and exploits the fact that well pad construction creates persistent terrain modifications detectable through LiDAR even when fully overgrown.

**Ramachandran et al. (2024)** in *Nature Communications* achieved **95.5% precision and 90.4% recall** for well pad detection, but used high-resolution satellite imagery rather than LiDAR—effective for active pads but unable to detect overgrown abandoned sites. **Stengel et al. (2024)** in *Remote Sensing* demonstrated LiDAR-based detection of abandoned uranium mine features (pits, waste piles, platforms) in South Texas using bare-earth slope, topographic texture, and flow analysis—a methodologically analogous approach transferable to well pads.

---

## Connected component analysis and blob detection form the extraction backbone

Nearly every automated pipeline reviewed uses some variant of connected component analysis on thresholded morphometric rasters as the fundamental feature extraction step, followed by geometric filtering.

The standard workflow: (1) compute a morphometric raster (TPI, slope, LRM, curvature, or flatness index); (2) apply a threshold to create a binary mask; (3) optionally apply morphological operations—**erosion followed by dilation (opening)** to remove small noise fragments while preserving target-sized features, or **dilation followed by erosion (closing)** to fill small gaps; (4) label connected components; (5) compute geometric properties of each component; (6) filter by area, compactness, elongation, depth, and other descriptors.

**Žutautas (2018)** demonstrated this pipeline explicitly for charcoal kiln detection: contrast split segmentation on TPI created a binary mask, morphological opening cleaned it, and the **Hough circle transform** detected circular shapes within the cleaned raster. Doctor and Young (2013) applied the same logic to sinkholes using TPI thresholding with connected component labeling, filtering candidates by area, depth (≥0.18 m), and compactness. Cahalan and Milewski (2019) extended this in *Remote Sensing* by first generating a logistic regression probability surface from 16 morphometric indices, thresholding at an optimized cutoff (0.13), and contouring connected regions as sinkhole boundaries.

The geometric filters applied post-extraction are consistent across the literature. Area constraints eliminate features too small or too large for the target. **Compactness** (4π × area / perimeter²) distinguishes compact features from elongated artifacts. Elongation (major/minor axis ratio) separates circular/square platforms from linear features like roads or ditches. Depth-to-area ratio discriminates natural depressions from engineered features. Mean internal slope identifies flat-bottomed anthropogenic surfaces against rough natural terrain.

---

## Conclusion: a composite pipeline for well pad detection

The literature converges on a four-stage architecture directly applicable to abandoned well pad detection. **Stage 1**: terrain normalization via LRM (moderate terrain) or openness (steep terrain), producing derivative rasters that isolate small-scale anomalies from regional topography. **Stage 2**: candidate extraction through either fill-difference on an inverted DEM (to detect raised platforms) or TPI/flatness thresholding with connected component labeling, supplemented by morphological opening to suppress noise. **Stage 3**: morphometric characterization of each candidate—computing area, compactness, elongation, internal slope variance, depth/height relative to surroundings, and symmetry. **Stage 4**: classification via Random Forest or gradient boosting trained on these object-level descriptors, following the Niculiță (2020) and Zhu et al. (2020) paradigm that achieves 93–97% accuracy on analogous features.

The critical insight from this review is that well pads are geometrically simpler and more distinctive than most features these algorithms were designed to detect. Burial mounds erode over millennia; charcoal hearths degrade; sinkholes vary wildly in form. A well pad—a **compact, flat, rectangular or circular engineered surface** with characteristic cut-and-fill margins and an associated linear access road—presents a cleaner morphometric signature. The absence of a dedicated published method is a gap in the literature, not a gap in available methodology. Every algorithmic component needed to build a high-accuracy well pad detector has been independently validated on harder problems.