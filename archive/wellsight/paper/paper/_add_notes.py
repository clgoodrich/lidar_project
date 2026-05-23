from pptx import Presentation

PPTX = 'WellSight_Presentation.pptx'
prs = Presentation(PPTX)
slides = prs.slides

notes = {}

notes[0] = """TITLE SLIDE
- Full title: "Morphological Characterization of Orphaned Oil and Gas Well Pits Using Airborne LiDAR in Western Pennsylvania"
- LiDAR = Light Detection And Ranging (active remote sensing using laser pulses)
- "Morphological characterization" = measuring the physical shape and dimensions of features
- Project name: WellSight
- This work uses publicly available USGS 3DEP data (no proprietary datasets)
"""

notes[1] = """THE PROBLEM - CONTEXT
- Drake Well (1859, Titusville PA) = first commercial oil well in the US
- PA had virtually no drilling regulations until the Oil and Gas Act of 1984
- 350,000+ documented wells statewide, but actual number likely much higher
- PA produced 77% of world oil output in the 1860s-70s
- "Documented" does not mean "located" - many records have only township-level coordinates
- Bipartisan Infrastructure Law (2021) allocated $4.7B specifically for orphaned well remediation
- Key distinction: documented does not equal locatable does not equal plugged
"""

notes[2] = """THE PROBLEM - DEFINITIONS
- Abandoned well: no production, extraction, or injection for 12+ months AND no equipment present
- Orphaned well: abandoned well where no responsible operator can be identified or located
- PA DEP = Pennsylvania Department of Environmental Protection (the regulatory agency)
- Why it matters: orphaned wells leak methane (potent greenhouse gas), contaminate groundwater, and pose physical hazards
- The legal/administrative classification (active vs abandoned vs orphaned) cannot be determined from remote sensing alone - it requires DEP records
"""

notes[3] = """WHAT DOES AN ORPHANED WELL PIT LOOK LIKE?
- Photo credit: Scott Detrow / StateImpact PA (2012)
- Shows exposed wellhead (the pipe) surrounded by overgrown brush
- The "pit" is the collapsed cellar - NOT the wellbore itself
- Well cellars: excavated below-grade workspace around the wellhead, standard practice from ~1880s onward
- After 100+ years of neglect, the cellar walls collapse inward creating a shallow bowl-shaped depression
- 35,000+ orphaned wells estimated in PA alone
- Infrastructure Act funding: $4.7B nationwide for plugging/remediation
- Biggest challenge: physically locating these features under dense Appalachian forest canopy
"""

notes[4] = """WHY LiDAR?
- LiDAR = Light Detection And Ranging
- Airborne LiDAR fires ~100,000+ laser pulses per second from aircraft
- Multiple returns per pulse: first return hits canopy, last return reaches ground
- Ground classification algorithms (e.g., SMRF, PMF) separate ground from vegetation returns
- Result: bare-earth Digital Elevation Model (DEM) beneath full canopy cover
- 1-meter resolution = each pixel represents 1m x 1m on the ground
- At 1m resolution, a 13m-diameter pit spans ~13 pixels (enough to characterize shape)
- Satellite imagery (optical) CANNOT penetrate canopy - you only see treetops
- The comparison images show the exact same location: satellite vs LiDAR hillshade
"""

notes[5] = """STUDY AREA
- Venango County: historic center of PA oil industry (Oil City, Titusville nearby)
- McKean County: northern PA, also heavily drilled
- Appalachian Plateau physiography: not mountains, but deeply dissected plateau
- Terrain: 300-600m elevation, slopes commonly 15-30 degrees, stream valleys 50-100m deep
- Forest: second-growth deciduous (oak, maple, beech) - original forest logged 1800s
- USGS 3DEP: the national LiDAR program (3D Elevation Program)
- Data collected 2019, ~4 ground returns per square meter average density
- CRS: EPSG:6346 = NAD83(2011) / UTM Zone 17N
- Tile extent: ~1.5 km x 1.5 km per processing tile
- 1,109 DEP-documented wells fall within our primary analysis tile
"""

notes[6] = """PIPELINE OVERVIEW
- 4-step process: Derivatives then Annotation then Template Matching then Classification
- Step 1 (Terrain Derivatives): computed from bare-earth DEM
  - DEM = Digital Elevation Model (bare earth surface)
  - TPI = Topographic Position Index (how a cell compares to neighbors)
  - LRM = Local Relief Model (removes regional trend, highlights micro-topography)
  - Openness = sky visibility at each point (concavities have low openness)
- Step 2: Human expert picks 861 pit centers in QGIS
- Step 3: Template matching generates 628,332 candidate locations
  - NCC = Normalized Cross-Correlation (pattern matching score)
- Step 4: Ensemble of 3 gradient-boosted models classifies candidates
  - Spatial CV = cross-validation with geographic separation to prevent data leakage
"""

notes[7] = """STEP 1: TERRAIN DERIVATIVES
- Generated from 1m bare-earth DEM via scipy.ndimage convolutions
- LRM (Local Relief Model): subtracts a large-kernel mean from the DEM
  - Removes hillslope trend, leaves only local anomalies (pits, mounds)
  - Computed at 4 scales: 5m, 11m, 25m, 51m kernel radius
  - LRM was the single most important feature for pit detection
- TPI (Topographic Position Index): difference between cell elevation and mean of surrounding ring
  - Computed at 3 scales: 5m, 15m, 25.5m
  - Negative TPI = depression (pit), Positive TPI = mound
- Openness: angular measure of sky visibility (Yokoyama et al., 2002)
  - Negative openness highlights concavities
  - 25m search radius
- Roughness: std dev of elevation in 11x11 window (Riley et al., 1999)
- Hillshade: shaded relief for visualization (not used as model feature)
- Total: 11 terrain derivative layers from a single DEM
"""

notes[8] = """STEP 2: MANUAL ANNOTATION
- 861 pit locations picked by single operator in QGIS
- Picked on multi-azimuth hillshade overlaid with LRM
- "Conservative" = only annotated features with clear circular depression morphology
- Not every pit is annotated - only high-confidence ones (minimizes false labels in training)
- DEP records often do not align with visible features:
  - Only 31% of DEP coordinates land within 10m of a visible pit
  - Positional uncertainty: ~100m for post-1950 wells, ~200m for pre-1950
- This is why we cannot just use DEP locations as training labels
- Single-operator bias is acknowledged as a limitation
- Graphic shows asterisk markers = manual picks overlaid on hillshade
"""

notes[9] = """STEP 3: TEMPLATE MATCHING
- Process: extract 17x17 m window centered on each annotated pit from 5 terrain channels
- 5 channels used: LRM 5m, LRM 11m, TPI 5m, negative openness, hillshade
- Stack all 540 valid cutouts (some excluded for >20% NoData at tile edges)
- Compute pixel-wise mean and median to create the "template"
- Mean shows the average pit shape; median is more robust to outliers
- RdBu_r colormap: red = positive (high), blue = negative (low)
  - In LRM: blue center = depression, red ring = relative high (rim)
  - In TPI: blue center = lower than surroundings
  - In openness (negative): blue center = enclosed/concave
- Template is then scanned across entire tile using NCC (Normalized Cross-Correlation)
- NCC threshold generates 628,332 candidate locations for classification
- Key insight: the template is rotationally symmetric (pits have no preferred orientation)
"""

notes[10] = """STEP 4: CLASSIFICATION AND RESULTS
- ROC-AUC = 0.905 (Area Under Receiver Operating Characteristic curve)
  - 1.0 = perfect, 0.5 = random; 0.905 is strong discriminative performance
- PR-AUC = 0.212 (Area Under Precision-Recall curve)
  - Looks low but reflects extreme class imbalance: only 0.37% of candidates are true pits
  - PR-AUC is the honest metric for needle-in-haystack problems
- Ensemble: 3 gradient-boosted models vote together
  - XGBoost (max_depth=5, learning_rate=0.05, 500 rounds)
  - LightGBM (31 leaves, same learning rate and rounds)
  - HistGradientBoosting (scikit-learn native implementation)
- Spatial CV: 500m grid separation between train/test folds
  - Prevents spatial autocorrelation from inflating scores
  - GroupKFold with 5 folds
- 48 features per candidate (inner ring vs rim ring comparisons across all derivatives)
- Isotonic calibration: maps raw ensemble scores to true probabilities
- Graphic: green circles = ground truth, colored dots = detections (yellow=0.6, red=1.0 probability)
"""

notes[11] = """MEASURED PIT MORPHOLOGY
- These are MEASURED statistics from 856 annotated pits (5 excluded at tile boundary)
- NOT theoretical - derived from actual 1m DEM measurements using radial sampling
- Key measurements:
  - Mean depth (rim to floor): 0.724 m
  - Maximum rim height: 1.629 m (rims are asymmetric - one side higher)
  - Diameter: ~12.6 m (effective radius ~6.3 m)
  - Volume: ~32.4 cubic meters average
  - Inner slope: ~10 degrees (gentle bowl, not steep-walled)
  - Rim symmetry std: 0.698 m (rims are irregular, not perfectly circular)
  - Aspect ratio (depth/diameter): ~0.06 (very shallow relative to width)
- Cross-section shows TRUE SCALE (no vertical exaggeration)
- The "collapsed cellar" explanation: these are NOT drill holes, they are infrastructure collapses
- Depth (0.7m) is well above LiDAR vertical noise floor (~0.05-0.10m RMS)
- Well cellars became standard practice ~1880s as wellhead equipment grew more complex
"""

notes[12] = """ANNOTATION QUALITY CONTROL
- Applied anomaly detection to our own training labels before final model training
- 4 algorithms used: Mahalanobis distance, Isolation Forest, Local Outlier Factor, statistical z-scores
- Mahalanobis distance: measures how many standard deviations a point is from the multivariate mean
  - Threshold: > 5.0 flagged as anomalous
- 90 of 856 pits (10.5%) flagged for manual review
- Manual review of top 30 anomalies found:
  - ~half were genuine annotation errors (mis-clicks, stream channel features, not pits)
  - ~half were real but unusual pits (very large, very deep, highly asymmetric)
- Purpose: clean the training set before final model fitting
- This step improves model quality by removing mislabeled examples
- PCA on 11-dimensional morphology space: 3 components explain 86.4% of variance
  - PC1 (39.2%): depth and volume (how big is it)
  - PC2 (33.8%): size vs shape (flat and wide vs deep and narrow)
  - PC3 (13.4%): rim asymmetry
"""

notes[13] = """THE DEP RECORDS PROBLEM
- PA DEP = Pennsylvania Department of Environmental Protection
- DEP maintains the official database of all oil/gas wells in PA
- Key finding: only 31% of DEP coordinates are within 10m of a visible pit feature
- Many DEP locations are systematically offset:
  - Placed at road intersection or property corner rather than actual well location
  - Digitized from old paper maps with limited spatial accuracy
- Some orphan-listed wells show NO terrain signature at all:
  - Could be pre-cellar era wells (1860s-70s) that left no surface mark
  - Could be positional error so large we are looking in the wrong place
  - Could be wells that were properly plugged and graded (no remaining depression)
- 20 DEP orphan wells in our tile; most are 1970s T.R. Potts lease oil wells
- Implication: DEP records CANNOT be used as reliable ground truth for training
  - This is exactly WHY manual annotation on LiDAR derivatives was necessary
"""

notes[14] = """CHALLENGES AND LIMITATIONS
- Single operator bias: all 861 annotations picked by one person
  - Could systematically miss certain pit types or over-pick others
  - Mitigation: anomaly detection QC step catches some systematic errors
- No field validation: everything measured from remote sensing
  - Cannot confirm these are actually well pits without site visits
  - Some could be natural sinkholes, tree throws, or other circular depressions
- No single metric works alone:
  - LRM catches depth but also flags stream channels
  - TPI catches relative position but also flags every small hollow
  - Ensemble of 48 features required to separate pits from terrain noise
- Canopy interference: even with LiDAR, dense canopy reduces ground point density
  - Fewer ground returns = noisier DEM = harder to detect subtle features
- Temporal mismatch: LiDAR collected 2019, wells drilled 1860s-1970s
  - 50-150 years of erosion, vegetation growth, and land use change since abandonment
"""

notes[15] = """FUTURE WORK
- Geomorphon enclosure: landform classification method (Jasiewicz and Stepinski, 2013)
  - Classifies each cell into 1 of 10 landform types based on openness patterns
  - Preliminary test showed +31% improvement in PR-AUC (0.212 to 0.279)
- U-Net: deep learning semantic segmentation on terrain image patches
  - Would learn spatial patterns directly from raster data
  - Requires GPU training infrastructure and more training labels
- Land cover and canopy height integration:
  - CHM (Canopy Height Model = DSM minus DEM) indicates vegetation density
  - Areas with dense canopy may need adjusted detection thresholds
- Improved negative sampling strategy:
  - Currently random negatives; stratified hard-negative mining could improve discrimination
  - Sample more negatives from "pit-like but not pit" terrain (stream junctions, tree throws)
- Field validation: ground-truth a subset of high-confidence detections
  - Would establish true real-world precision
  - PA DEP may have interest in co-funding site visits for remediation prioritization
"""

notes[16] = """SUMMARY
- Main findings:
  - Typical orphaned well pit: 0.7m deep, 13m diameter, 32 cubic meters volume
  - Subtle but detectable in 1m LiDAR (depth well above noise floor)
  - No single terrain metric is sufficient - ensemble of 48 features required
  - 85.5% precision at 0.80 probability threshold (289 candidates retained)
  - 93.2% precision at 0.90 threshold (118 candidates)
- ROC-AUC 0.905 demonstrates the approach works well
- PR-AUC 0.212 reflects the needle-in-haystack nature of the problem (0.37% positive rate)
- DEP records unreliable for precise location work - LiDAR-based detection fills a real gap
- Scalable: the pipeline can process any 3DEP tile in PA without modification
- Practical impact: accelerates remediation by narrowing field search areas from square kilometers to specific coordinates
"""

notes[17] = """APPENDIX: USGS 3DEP COLLECTION PARAMETERS
- 3DEP = 3D Elevation Program (USGS national LiDAR initiative)
- Goal: complete LiDAR coverage of the US (largely achieved by 2023)
- Western PA collection year: 2019
- LAS version 1.4, Point Format 7 (includes RGB and NIR channels if available)
- Point density: ~4 ground returns per square meter (after classification)
- Total point density: ~8-12 returns per square meter (including vegetation)
- Vertical accuracy: ~10 cm RMSE on open terrain
- Horizontal accuracy: ~50 cm
- Classification: ASPRS standard codes
  - Class 2 = Ground
  - Class 1 = Unclassified (default)
  - Class 6 = Building
  - Class 7 = Noise
- CRS: EPSG:6346 = NAD83(2011) / UTM Zone 17N
- Data freely available from USGS via The National Map or OpenTopography
- ASPRS = American Society for Photogrammetry and Remote Sensing
"""

notes[18] = """APPENDIX: LITERATURE-GROUNDED PARAMETERS
- Every parameter in the pipeline is justified by published research
- Key citations:
  - LRM: Hesse (2010), Bofinger et al. (2006) - archaeological feature detection in forested terrain
  - TPI scales: Weiss (2001), De Reu et al. (2013) - landform classification
  - Openness: Yokoyama et al. (2002), Doneus (2013) - concavity detection
  - Roughness: Riley et al. (1999), Grohmann et al. (2011) - terrain texture quantification
  - Pad slope threshold 8 degrees: Drohan and Brittingham (2012, Environmental Management 49:1061)
  - Pad minimum area 100 sq m: Hammack et al. (2014, NETL)
  - Pit blob max sigma 5.0: Hammack et al. (2014) - reserve pit dimensions from NETL study
  - Positional uncertainty 100m/200m: Kang et al. (2014, NETL/DOE)
- NETL = National Energy Technology Laboratory (US Department of Energy)
- Parameters adjusted in v0.6 audit: pad slope (5 to 8 deg), pad area (80 to 100 sq m), blob max_sigma (3.5 to 5.0)
- Literature supports using LRM and openness as primary features for subtle terrain anomalies
"""

for i, slide in enumerate(slides):
    if i in notes:
        ns = slide.notes_slide
        tf = ns.notes_text_frame
        tf.text = notes[i].strip()

prs.save(PPTX)
print(f"Added speaker notes to {len(notes)} slides. Saved.")
