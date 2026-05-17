from pptx import Presentation

prs = Presentation('WellSight_Presentation.pptx')

notes = {}

notes[0] = """TITLE SLIDE
- LiDAR = Light Detection And Ranging. Shoots laser pulses from a plane to map the ground surface.
- "Morphological characterization" = measuring the shape and size of terrain features.
- WellSight is the project name.
- All data is publicly available from USGS 3DEP (free government LiDAR program)."""

notes[1] = """THE PROBLEM (1/2)
- Drake Well, 1859, Titusville PA = first commercial US oil well.
- PA had no drilling regulations until 1984. For 125 years, anyone could drill and walk away.
- 350,000+ wells documented statewide. Real number is higher because many were never recorded.
- "Documented" does not mean "located." Many old records just say a township name, no coordinates.
- 2021 Infrastructure Act put $4.7 billion toward plugging orphaned wells nationwide."""

notes[2] = """THE PROBLEM (2/2)
- Abandoned well = no production for 12+ months and no equipment on site.
- Orphaned well = abandoned AND no owner can be found. Nobody is responsible for it.
- PA DEP (Dept. of Environmental Protection) is the state agency that tracks wells.
- Why care: orphaned wells leak methane, contaminate groundwater, and are physical hazards.
- LiDAR cannot tell you if a well is active or orphaned. That is a legal classification from DEP records, not something you can see in terrain."""

notes[3] = """WHAT DOES A WELL PIT LOOK LIKE?
- Photo: Scott Detrow / StateImpact PA, 2012. Shows an exposed pipe (the wellhead) in overgrown brush.
- The "pit" is NOT the drill hole. A wellbore is only 6-12 inches wide.
- The pit is the collapsed cellar: a workspace dug around the wellhead, ~10-15 feet across.
- Pre-1984 wells had unlined dirt cellars. After abandonment, the walls slowly slumped inward over decades.
- Result: a shallow bowl in the ground, hidden under leaves and brush. That is what we detect.
- 35,000+ orphaned wells estimated in PA. The hard part is finding them under forest canopy."""

notes[4] = """WHY LiDAR?
- Airborne LiDAR fires laser pulses from a plane. Some hit treetops, some reach the ground.
- "Ground classification" algorithms sort the returns: canopy vs. bare earth.
- Output: a 1-meter DEM (Digital Elevation Model) showing the ground surface under the trees.
- At 1m resolution, a 13m-wide pit spans ~13 pixels. Enough to measure its shape.
- Satellite photos only see treetops. The two images on this slide show the same spot: satellite (useless) vs. LiDAR hillshade (pits visible)."""

notes[5] = """STUDY AREA
- Venango County = historic center of PA oil (Oil City, Titusville).
- Appalachian Plateau: hilly terrain, steep stream valleys, dense second-growth hardwood forest.
- USGS 3DEP LiDAR collected 2019. About 4 laser ground returns per square meter.
- EPSG:6346 = the coordinate system (NAD83(2011) / UTM Zone 17N).
- Our main analysis tile is ~1.5 km x 1.5 km. Contains 1,109 DEP-documented wells."""

notes[6] = """THE DEP RECORDS PROBLEM
- PA DEP maintains the official database of all oil/gas wells.
- Key finding: only 31% of DEP coordinates land within 10m of a visible pit.
- Many DEP locations were digitized from old paper maps or placed at the nearest road intersection.
- Some DEP "orphan" wells show zero terrain signature:
  - Could be pre-1880s wells (no cellar to collapse).
  - Could be so far off-position we are looking in the wrong spot.
  - Could be properly plugged and graded (surface restored).
- This is why we could not use DEP locations as training labels. We had to annotate by hand on the LiDAR."""

notes[7] = """PIPELINE OVERVIEW
- 4 steps: Derivatives, Annotation, Template Matching, Classification.
- DEM = Digital Elevation Model (the bare ground surface).
- TPI = Topographic Position Index. Compares each pixel to its neighbors. Negative = lower than surroundings (depression).
- LRM = Local Relief Model. Subtracts the broad hillslope trend so only small bumps and dips remain. This was the most important layer.
- Openness = how much sky a point can see. Low openness = enclosed (in a pit).
- NCC = Normalized Cross-Correlation. A similarity score (-1 to +1) used to match our pit template across the landscape.
- Spatial CV = cross-validation with geographic separation so the model is tested on terrain it has never trained on."""

notes[8] = """STEP 1: TERRAIN DERIVATIVES
- All computed from the 1m DEM using Python (scipy.ndimage).
- LRM (Local Relief Model): subtracts a smoothed version of the DEM from itself.
  - What is left: just the local bumps and dips, with the overall hillslope removed.
  - Computed at 4 scales: 5m, 11m, 25m, 51m. Each highlights features of different sizes.
  - LRM was the single most important input for detecting pits.
- TPI (Topographic Position Index): pixel elevation minus average of a ring around it.
  - Negative TPI = the pixel sits lower than its surroundings (a depression).
  - Computed at 3 scales: 5m, 15m, 25.5m.
- Openness: how much sky is visible from each point (Yokoyama et al., 2002).
  - Negative openness highlights enclosed spots like pits. 25m search radius.
- Roughness: how variable the elevation is in an 11x11 pixel window.
- Hillshade: a shaded relief image for visualization. Not fed to the model.
- 11 terrain layers total from one DEM."""

notes[9] = """STEP 2: MANUAL ANNOTATION
- 861 pit center points picked by hand in QGIS (a GIS application).
- Picked on hillshade overlaid with LRM. Only annotated features with clear circular depression shape.
- "Conservative" = if it did not look obviously like a pit, we skipped it. Better to miss some than mislabel.
- DEP records were not reliable enough to use as labels (only 31% are near a visible pit).
- Single-operator bias: one person did all the picking. Could systematically miss certain pit shapes.
- Graphic: white stars = our manual picks. Orange dots = DEP well records. Note how many DEP dots are nowhere near a visible pit."""

notes[10] = """STEP 3: TEMPLATE MATCHING
- For each of our 861 pits, we cut out a 17m x 17m patch from 5 terrain layers.
- 540 patches survived quality filtering (the rest were at tile edges or had data gaps).
- Averaged all 540 patches pixel-by-pixel to get the "mean template" = what an average pit looks like.
- 5 channels: lrm_5 (LRM at 5m), lrm_11 (LRM at 11m), tpi_05 (TPI at 5m), openness_neg (negative openness), hillshade.
- Then slid this template across the entire tile using NCC (Normalized Cross-Correlation).
  - NCC score near +1 = "this spot looks like our template."
  - Every spot above a low threshold became a candidate.
  - Result: 628,332 candidates. Most are false positives. The classifier in Step 4 sorts them out.

THE GRAPHIC
- Top row = mean template per channel. Bottom row = median (less sensitive to outliers).
- Blue center in LRM/TPI = depression. Red/warm ring = higher ground around it.
- The pattern is symmetric because pits have no preferred compass direction."""

notes[11] = """STEP 4: CLASSIFICATION & RESULTS

WHAT WE DID
- 628,332 candidates from template matching. Most are not real pits.
- Measured 48 properties at each candidate (depth, shape, roughness, symmetry, etc.).
- Trained 3 machine learning models: XGBoost, LightGBM, HistGradientBoosting.
  - All are "gradient boosted trees" = chains of yes/no questions about terrain properties.
- Averaged their outputs into one probability score per candidate.
- Isotonic calibration makes the score meaningful: if it says 0.80, about 80% of candidates at that score really are pits.

PROBABILITY SCORE
- Every candidate gets a number from 0 to 1. Higher = more likely a real pit.
- Comes from averaging the 3 models, then calibrating against real outcomes.

THRESHOLD
- You pick a cutoff and throw away everything below it.
- 0.70 threshold: 507 candidates kept, 76.9% are real. (Wide net, more false alarms.)
- 0.80 threshold: 289 candidates kept, 85.5% are real. (Good balance.)
- 0.90 threshold: 118 candidates kept, 93.2% are real. (Tight filter, high confidence.)

ROC-AUC = 0.905
- "Report card" for the model across all possible thresholds at once.
- Pick one real pit and one random non-pit. ROC-AUC = probability the model scores the real pit higher.
- 0.5 = coin flip (useless). 1.0 = perfect. 0.905 = the model learned what a pit looks like.

PR-AUC = 0.212
- Harder metric that accounts for how rare pits are (only 1 in 270 candidates is real).
- Random guessing would score 0.0037. Ours is 0.212 = 57x better than random.
- Always lower than ROC-AUC when positives are rare. This is expected.

SPATIAL CROSS-VALIDATION
- Map split into zones with 500m gaps between training and testing areas.
- Prevents cheating: nearby terrain is similar, so without gaps the model scores would be inflated.

THE GRAPHIC
- Green circles = our hand-annotated pits (ground truth).
- Colored dots = model detections. Yellow = lower confidence (~0.6). Red = high confidence (~1.0).
- Overlap = correct detection."""

notes[12] = """MEASURED PIT MORPHOLOGY

WHAT THIS SHOWS
- Actual measurements of 856 annotated pits from the 1m LiDAR surface. Not estimates.
- Cross-section is true scale (no vertical stretching).

THE SHAPE
- depth_from_rim_mean_m = 0.72 m (about 2.4 feet, knee height).
- diameter_m = 12.6 m (about 41 feet, width of a two-car garage).
- volume_approx_m3 = 32.4 cubic meters (about 8,500 gallons).
- slope_inner_deg = about 10 degrees (gentle bowl, easy to walk through).
- Rims are uneven: depth_from_rim_max_m = 1.63 m on one side, 0.72 m on the other.
- rim_symmetry_std_m = 0.70 m. The rim height varies by about 2 feet around the circle.
- aspect_ratio = depth / diameter = 0.06. Extremely shallow relative to width.

WHAT IS A COLLAPSED CELLAR?
- NOT the drill hole (wellbore = 6-12 inches wide).
- A well cellar was a pit dug around the wellhead for equipment access, typically 10-15 ft across.
- Pre-1984 wells: dirt walls, no lining. After abandonment the walls slumped inward over decades.
- Modern wells: concrete cellars, legal reclamation. Nothing collapses. No pit signature.
- Our pipeline inherently detects historic-era wells (1880s-1970s). Those are the ones most likely to be orphaned.

ACTIVE WELLS ON COLLAPSED PITS
- "Stripper wells": 1880s-1920s wells still producing <1 barrel/day. Legally "active."
- The pipe still works but nobody maintains the surface. The cellar collapses around it.
- A collapsed cellar means the surface is old and unmaintained, NOT necessarily that the well is abandoned."""

notes[13] = """ANNOTATION QUALITY CONTROL
- Before training the final model, we checked our own annotations for mistakes.
- Measured 11 physical properties for each of our 856 pits (depth, width, slope, volume, etc.).
- Used Mahalanobis distance to flag outliers: "how different is this pit from the average pit, considering all 11 properties at once?"
  - mahalanobis > 5.0 = flagged as unusual. 90 pits (10.5%) flagged.
- Manually reviewed the top 30:
  - About half were real mistakes (annotated a stream bank or flat ground instead of a pit).
  - About half were real pits that happen to be unusually large, deep, or lopsided.
- Common mistakes found:
  - rim_radius_m too small (1-1.5 m): mis-click, not a real pit. 23 cases.
  - slope_inner_deg too high (>20 degrees): annotation on a hillside, not a depression. 18 cases.
  - depth_from_rim_mean_m near zero: the point is not lower than its surroundings. 8 cases.
  - volume_approx_m3 too high (>100): probably a borrow pit or natural feature. 5 cases.
- Cleaning labels before model training improves final detection accuracy. Standard practice in ML."""

notes[14] = """CHALLENGES & LIMITATIONS
- Single operator bias: one person picked all 861 annotations. Could miss certain pit shapes.
- No field validation: everything is measured from LiDAR, not confirmed on the ground.
  - Some detections could be natural sinkholes, tree throws, or stream features.
- No single terrain metric works alone:
  - LRM catches depth but also flags stream channels.
  - TPI catches depressions but flags every small hollow.
  - Need all 48 features working together to separate pits from noise.
- Canopy: dense tree cover reduces ground point density, making the DEM noisier.
- Time gap: LiDAR was collected in 2019, wells were drilled 1860s-1970s. 50-150 years of erosion and vegetation growth."""

notes[15] = """FUTURE WORK
- Geomorphon enclosure (Jasiewicz & Stepinski, 2013): classifies terrain into 10 landform types.
  - Preliminary test: PR-AUC improved from 0.212 to 0.279 (+31%).
- U-Net: deep learning that looks at terrain image patches directly instead of hand-picked features.
- Canopy height model (CHM = DSM minus DEM): could flag areas where dense canopy obscures pits.
- Better negative sampling: instead of random negatives, sample from "looks like a pit but is not" terrain.
- Field validation: visit high-confidence detections on the ground to measure real-world accuracy."""

notes[16] = """SUMMARY
- Typical pit: 0.72 m deep, 12.6 m across, 32 cubic meters. Subtle but detectable.
- No single metric works. Ensemble of 48 features across 3 models required.
- ROC-AUC 0.905 = the model reliably distinguishes pits from non-pits.
- At 0.80 threshold: 289 candidates, 85.5% precision.
- At 0.90 threshold: 118 candidates, 93.2% precision.
- DEP records are unreliable for precise location. LiDAR-based detection fills that gap.
- Pipeline can process any USGS 3DEP tile in PA without modification.

ANTICIPATED QUESTION: "How do you know if it is abandoned vs active?"
- We do not. The pipeline detects terrain shape, not well status.
- Status (active/abandoned/orphaned) is a legal classification from DEP, not a physical property.
- The value is finding pits with NO DEP record at all. Those are likely undocumented orphaned wells.

ANTICIPATED QUESTION: "Active wells on collapsed pits?"
- Stripper wells: 1880s-1920s wells still producing <1 barrel/day. Cellar collapses but pipe still works.
- Collapsed cellar = old and unmaintained surface, not necessarily abandoned."""

notes[18] = """APPENDIX: USGS 3DEP COLLECTION PARAMETERS
- 3DEP = 3D Elevation Program. USGS national LiDAR initiative.
- Western PA data collected 2019.
- LAS 1.4, Point Format 7. CRS: EPSG:6346 (NAD83(2011) / UTM Zone 17N).
- ~4 ground returns per square meter. ~8-12 total returns including vegetation.
- Vertical accuracy: ~10 cm RMSE on open terrain. Horizontal: ~50 cm.
- ASPRS classification: Class 2 = Ground, Class 1 = Unclassified.
- Free data from USGS via The National Map or OpenTopography.
- ASPRS = American Society for Photogrammetry and Remote Sensing."""

notes[19] = """APPENDIX: LITERATURE-GROUNDED PARAMETERS
- Every pipeline parameter is backed by a published citation.
- LRM: Hesse (2010), Bofinger et al. (2006) — archaeological feature detection.
- TPI: Weiss (2001), De Reu et al. (2013) — landform classification.
- Openness: Yokoyama et al. (2002), Doneus (2013) — concavity detection.
- Roughness: Riley et al. (1999) — terrain texture.
- Pad slope 8 degrees: Drohan & Brittingham (2012).
- Pad area 100 sq m: Hammack et al. (2014, NETL).
- Pit blob sigma 5.0: Hammack et al. (2014).
- Positional uncertainty 100m/200m: Kang et al. (2014, NETL/DOE).
- NETL = National Energy Technology Laboratory (US Dept. of Energy)."""

for i, text in notes.items():
    slide = prs.slides[i]
    ns = slide.notes_slide
    ns.notes_text_frame.text = text.strip()

prs.save('WellSight_Presentation.pptx')
print(f"Rewrote notes on {len(notes)} slides. Saved.")
