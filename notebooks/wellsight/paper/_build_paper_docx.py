"""Build WellSight_Paper.docx — figures inline, consistent 'we' voice."""
from docx import Document
from docx.shared import Inches, Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path
import re

doc = Document()
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

DERIV = Path('data/derivatives')
ROOT = Path('.')
fig_num = [0]


def add_body(text):
    p = doc.add_paragraph()
    parts = re.split(r'(\*\*.*?\*\*)', text)
    for part in parts:
        if part.startswith('**') and part.endswith('**'):
            p.add_run(part[2:-2]).bold = True
        else:
            p.add_run(part)
    return p


def add_fig(img_path, caption):
    fig_num[0] += 1
    if Path(img_path).exists():
        doc.add_picture(str(img_path), width=Inches(5.5))
        doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph()
    run = p.add_run(f'Figure {fig_num[0]}: {caption}')
    run.font.size = Pt(10)
    run.italic = True


def add_table(headers, rows, caption=None):
    if caption:
        p = doc.add_paragraph()
        p.add_run(caption).font.size = Pt(10)
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.style = 'Table Grid'
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        for r in cell.paragraphs[0].runs:
            r.bold = True
            r.font.size = Pt(10)
    for i, row in enumerate(rows):
        for j, val in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = str(val)
            for r in cell.paragraphs[0].runs:
                r.font.size = Pt(10)
    doc.add_paragraph()


# ======== TITLE ========
p = doc.add_paragraph()
run = p.add_run('WellSight: Morphological Characterization of Orphaned Oil and Gas Well Pits Using Airborne LiDAR in Western Pennsylvania')
run.bold = True
run.font.size = Pt(18)
p = doc.add_paragraph()
p.add_run('Colton Goodrich').bold = True
doc.paragraphs[-1].runs[0].font.size = Pt(16)
p = doc.add_paragraph()
p.add_run('University of Houston \u2014 April 2026').font.size = Pt(12)
doc.add_paragraph()

# ======== INTRODUCTION ========
doc.add_heading('Introduction', level=1)

add_body('Pennsylvania is where American oil started. The Drake Well went in at Titusville in 1859, and from that point forward the western half of the state was drilled relentlessly for over a century. The PA Department of Environmental Protection estimates more than 200,000 undocumented abandoned wells exist statewide, of which only about 8,840 have been formally identified as orphaned (Kang et al., 2014). The rest are out there somewhere under the trees, leaking methane, contaminating groundwater, and posing physical hazards where surface subsidence has created voids that nobody knows about.')

add_fig(str(ROOT / 'docs/figures/Pennsylvania Map.png'), 'Distribution of documented oil and gas wells across Pennsylvania.')
add_fig(str(ROOT / 'docs/figures/Pennsylvania Map Abandoned.png'), 'Distribution of abandoned wells in Pennsylvania.')

add_body('The federal Infrastructure Investment and Jobs Act (2021) allocated $4.7 billion for orphaned well remediation. The fundamental problem is obvious: you cannot plug a well you cannot find. The PA DEP well database has coordinates for some of these wells, but those coordinates come from WPA-era surveys with positional accuracy of 30 to 100+ meters. When we cross-referenced DEP records against high-resolution LiDAR terrain data, only 31% of documented coordinates landed within 10 meters of a visible terrain feature. Nine percent had no detectable surface expression within 100 meters at all. Going the other direction, 87% of the pit features we identified by eye in the LiDAR had no DEP record within 100 meters. The state database is severely incomplete.')

add_body('The challenge with finding these wells is that they are invisible from above. Western Pennsylvania is covered in dense deciduous forest\u2014over 95% canopy coverage in our primary study area. Satellite imagery shows nothing but trees (Figure 3). Satellite-based approaches like Ramachandran et al. (2024), which achieved excellent results in open western basins (0.955 precision, 0.904 recall on the Permian Basin), simply cannot see through Appalachian forest canopy.')

add_fig(str(ROOT / 'docs/figures/region_with_trees.png'), 'Satellite imagery of the study area. Dense canopy hides all terrain features.')

add_body('Airborne LiDAR can. The laser pulses penetrate the canopy and resolve the bare-earth surface beneath it. Figure 4 shows the same area rendered as a LiDAR hillshade with the trees removed. Suddenly everything is visible: the old roads, the cleared well pads, and\u2014critically\u2014the small circular depressions where well cellars have collapsed. These pits are typically 2 to 15 meters across and less than a meter deep. They are the only physical evidence that a well was ever there.')

add_fig(str(ROOT / 'docs/figures/region_without_trees.png'), 'LiDAR hillshade of the same area. With canopy removed, roads, pads, and pits are visible.')

add_body('This paper presents WellSight, a pipeline we developed to detect and characterize these collapsed well cellar pits from 1-meter resolution USGS 3DEP LiDAR data. The pipeline uses template matching to find candidates, a gradient-boosted ensemble to classify them, and isotonic calibration to produce probability-ranked output. Beyond detection, we measured the physical dimensions of 856 pits\u2014depth, diameter, volume, symmetry\u2014to establish what these features actually look like, and ran anomaly detection on the training labels to flag potentially bad annotations.')

# ======== DATA ========
doc.add_heading('Data', level=1)

doc.add_heading('Study Region', level=2)
add_body('The study area covers portions of Venango County and McKean County in western Pennsylvania. This is Appalachian Plateau terrain: moderate to steep slopes, deeply incised stream valleys, and dense second-growth deciduous forest everywhere. The region has been drilled for oil and gas since 1859 and the landscape is perforated with thousands of abandoned well sites in various states of decay.')

add_fig(str(ROOT / 'docs/figures/Areas of Interest.png'), 'Study area tile footprints (white rectangles) on satellite imagery of western Pennsylvania.')

add_body('We worked with two primary study areas. The first is a 4.5 km \u00d7 4.5 km mosaic in Venango County containing 540 annotated pits, which served as the main training and validation site. The second is a 6.5 km \u00d7 6.5 km tile in McKean County with 294 annotated pits, approximately 120 km to the northeast. McKean has the highest documented orphan well count in the state at 2,385 DEP records.')

doc.add_heading('LiDAR Datasets', level=2)
add_body('The primary data is USGS 3DEP Western Pennsylvania from 2019. LAS 1.4, point format 7, EPSG:6346 (NAD83(2011) / UTM zone 17N). Point density averages about 4 ground returns per square meter, which comfortably supports 1-meter resolution rasterization. All derivatives in this study were built at 1-meter resolution.')

add_fig(str(ROOT / 'docs/figures/Pennsylvania AOI.png'), 'Study area with official PA DEP well locations by status category overlaid on LiDAR hillshade.')

add_table(
    ['Tile', 'Epoch', 'Extent', 'Density', 'Resolution'],
    [['Venango 9-tile', '2019 3DEP', '4.5 km x 4.5 km', '~4 pts/m\u00b2', '1 m'],
     ['McKean mk5', '2019 3DEP', '6.5 km x 6.5 km', '~4 pts/m\u00b2', '1 m'],
     ['McKean mkf', '2019 3DEP', '10 km x 10 km', '~4 pts/m\u00b2', '1 m']],
    'Table 1: LiDAR datasets')

doc.add_heading('Ground Truth Annotations', level=2)
add_body('Expert annotations were created in QGIS by visually inspecting multi-azimuth hillshade renderings at 1-meter resolution. The annotation set contains 861 pit point locations marking the center of visible circular depressions, 88 pad polygons outlining what we interpreted as former well pad clearings, and 96 road line features (19.6 km total) tracing abandoned access roads.')

add_body('The annotation philosophy was conservative\u2014we only marked features we were conclusively sure were anthropogenic well-related terrain modifications. We annotated just the pit center point rather than tracing full polygon outlines, which was faster and sufficient for template learning. The tradeoff is losing explicit size information per pit; the model had to learn size implicitly from the window features.')

add_fig(str(ROOT / 'docs/figures/Manual Picks.png'), 'Hillshade detail showing manual pit annotations (black stars) alongside official DEP well locations by status.')

add_body('The mismatch between our annotations and the DEP records is immediately obvious in Figure 8\u2014many annotated pits have no DEP record, and many DEP coordinates land nowhere near a visible terrain feature. Figure 9 shows an area where DEP has orphan records but we could not identify any clear pit depressions in the hillshade.')

add_fig(str(ROOT / 'docs/figures/close up errors.png'), 'Same area without manual annotations, showing DEP coordinate offset from visible pit features.')
add_fig(str(ROOT / 'docs/figures/orphaned with no clear wells.png'), 'DEP orphan records in an area with no clearly visible pit depressions.')

# ======== METHODOLOGY ========
doc.add_heading('Methodology', level=1)

doc.add_heading('Environment', level=2)
add_body('The pipeline was implemented in Python 3.13. PDAL was used for all point cloud I/O and ground classification via JSON pipelines executed through subprocess. Terrain derivatives were computed using scipy.ndimage. Machine learning models were built with XGBoost, LightGBM, and scikit-learn. Vector and raster I/O used geopandas and rasterio respectively. Claude (Anthropic) was used as an assistant in code development and document preparation.')

doc.add_heading('Terrain Derivative Generation', level=2)
add_body('Raw LAS point clouds were processed through PDAL to generate bare-earth DEMs via TIN interpolation over ground-classified returns (ASPRS class 2). A DSM was built from first-return maximum values and CHM computed as DSM minus DEM. From the DEM we built a comprehensive terrain derivative stack using scipy.ndimage convolution operations. Table 2 lists the full set.')

add_table(
    ['Derivative', 'Scales', 'Method', 'What It Shows'],
    [['Local Relief Model (LRM)', '3m, 5m, 11m, 25m', 'Mean subtraction', 'Residual micro-topography after trend removal'],
     ['Topographic Position Index', '5m, 15m, 25m', 'Annular mean diff.', 'Whether a point is higher or lower than surroundings'],
     ['Topographic Openness (neg)', '25m search', 'Yokoyama et al.', 'How enclosed a point is by surrounding terrain'],
     ['Slope', '3x3 window', "Horn's method", 'Surface gradient'],
     ['Roughness', '5m window', 'Elevation std. dev.', 'How irregular the surface is locally'],
     ['Local Relief', '10m disk', 'Max minus min', 'Elevation range in local neighborhood'],
     ['Ground Density', '1m cells', 'Point count', 'LiDAR return coverage'],
     ['CHM', '\u2014', 'DSM minus DEM', 'Canopy height']],
    'Table 2: Terrain derivative stack')

add_body('The Local Relief Model turned out to be the most important channel for pit detection. LRM subtracts a local mean from each cell, removing the regional slope and leaving only the residual micro-topography. A pit shows up as a negative LRM anomaly\u2014the cell is lower than its immediate neighborhood. The problem is that the LRM signal at pit centers averages only -0.14 meters at the 5-meter scale, which is subtle.')

doc.add_heading('Template-Based Candidate Generation', level=2)
add_body('The key question that drove this approach was: can we learn what a pit looks like from the annotated examples, then scan the entire landscape for similar shapes? The answer turned out to be yes, and this was the methodological breakthrough of the project.')

add_body('For each of the 861 annotated pits, we extracted a 17\u00d717 cell window (17 m at 1 m resolution) from five terrain channels: LRM-5, LRM-11, TPI-05, negative openness, and hillshade. Each center was auto-snapped to the local LRM-5 minimum within 3 cells to correct for slight imprecision in our annotations. We then subtracted the per-window mean to normalize for varying absolute pit depths and took the median across all 1,280 successfully extracted cutouts. The result is a canonical pit template\u2014what a collapsed well cellar looks like on average.')

add_body('Clustering the cutouts via PCA(5) + KMeans(3) revealed three morphological sub-types corresponding to variations in symmetry, rim prominence, and wall steepness. Normalized cross-correlation (NCC) was computed between each template and the full-tile rasters, averaged across channels, and peaks extracted with 5-meter non-maximum suppression. This produced approximately 628,000 candidates across all tiles.')

doc.add_heading('Feature Engineering', level=2)
add_body('Each candidate gets a 48-dimensional feature vector. The bulk of the features (30) come from comparing an inner ring (within 3 m of center, representing the pit bottom) against a rim ring (6\u20138 m annulus, representing the surrounding terrain) across six depth-sensitive channels. For each channel we computed the inner minimum, inner mean, rim mean, the rim-minus-inner contrast, and a radial symmetry measure. Additional features include surface statistics from slope, roughness, relief, and CHM (8 features); ground density and template match score (4); and morphological descriptors including radial monotonicity and compactness (6).')

add_body('The logic behind the inner-vs-rim comparison is straightforward: a real pit has a center that is lower than its rim. The contrast between those two zones, measured across multiple terrain derivatives at multiple scales, gives the model a rich description of how "pit-like" each candidate is.')

doc.add_heading('Ensemble Classification', level=2)
add_body('We trained three gradient-boosted models per fold under 5-fold GroupKFold spatial cross-validation: XGBoost (max_depth=5, learning_rate=0.05, 500 rounds), LightGBM (num_leaves=31, same learning rate and rounds), and HistGradientBoosting from scikit-learn. Groups were defined by 500-meter grid cells to ensure geographic separation between training and validation folds. This matters because nearby candidates share geographic context, and without spatial separation the cross-validation metrics are optimistic.')

add_body('All models used class imbalance weighting at roughly 80:1 negative-to-positive ratio. The out-of-fold predictions were averaged across the three models, then isotonic regression was applied to calibrate the average into probability estimates where the threshold values correspond to actual precision.')

doc.add_heading('Morphological Measurement', level=2)
add_body('For each annotated pit, we extracted physical parameters from the 1-meter DEM within a 7.5-meter search radius centered on the annotation point. The pit center was snapped to the local DEM minimum within 3 cells. We then sampled elevation in concentric annular rings at 0.5-meter radial increments outward from the snapped center. The rim was identified as the radial distance where mean elevation is highest.')

add_body('The measured parameters include depth from rim mean and rim max, rim radius, effective radius (the median distance to the half-depth contour), diameter, aspect ratio (depth divided by diameter), rim symmetry (standard deviation of rim elevation at 8 angular samples), volume via cone approximation, LRM depth at the 5m and 11m scales, and mean slope within 2 meters of center.')

doc.add_heading('Anomaly Detection', level=2)
add_body('We applied four complementary anomaly scoring methods to the morphological measurements to flag annotations that might be errors. Per-feature z-scores identify which single measurement is most unusual for each pit. Mahalanobis distance accounts for correlations between parameters\u2014so a pit that is deep AND large is not flagged, since those naturally go together, but one that is deep with a tiny radius is. Isolation Forest provides a non-parametric anomaly score. And PCA decomposition shows where each pit sits in reduced-dimensional morphological space.')

# ======== RESULTS ========
doc.add_heading('Results', level=1)

doc.add_heading('Detection Performance', level=2)
add_body('The ensemble achieves ROC-AUC 0.905 and PR-AUC 0.212 under spatially honest GroupKFold cross-validation on 628,332 candidates with 48 features and a 0.37% positive rate. Table 3 shows precision and recall at various probability thresholds.')

add_table(
    ['Threshold', 'Candidates', 'Hits (\u226410m)', 'Pits Covered', 'False Pos.', 'Precision'],
    [['0.30', '771', '403', '325', '368', '52.3%'],
     ['0.40', '397', '272', '234', '125', '68.5%'],
     ['0.50', '336', '247', '213', '89', '73.5%'],
     ['0.70', '241', '190', '166', '51', '78.8%'],
     ['0.80', '76', '65', '60', '11', '85.5%'],
     ['0.90', '8', '8', '8', '0', '100.0%']],
    'Table 3: Precision-recall at probability thresholds')

add_body('At the 0.80 threshold, the pipeline finds 60 distinct pits with 85.5% precision\u2014roughly 1 in 7 candidates at that confidence level is a false positive. At 0.90, all 8 candidates are true positives. These numbers are honest; the spatial CV ensures we are not leaking information between nearby candidates.')

add_body('That said, the recall numbers are not great. At the 0.50 threshold we are only recovering 213 of 861 annotated pits (25%). The bottleneck is the candidate generation stage\u2014template matching is not generating a candidate near many of the pits in the first place. The pits it misses are presumably too shallow, too asymmetric, or too different from the learned template to trigger a high NCC score.')

doc.add_heading('Morphological Characterization', level=2)
add_body('We successfully extracted morphological parameters for 856 of 861 annotated pits (5 fell outside available tile extents). Table 4 summarizes what collapsed well cellar pits actually look like in this terrain.')

add_table(
    ['Parameter', 'Mean \u00b1 SD', 'Min', 'Median', 'Max'],
    [['Depth \u2014 rim mean (m)', '0.72 \u00b1 0.36', '0.0', '0.68', '2.5'],
     ['Depth \u2014 rim max (m)', '1.63 \u00b1 0.71', '0.1', '1.50', '5.9'],
     ['Rim radius (m)', '6.3 \u00b1 1.4', '1.0', '7.0', '7.5'],
     ['Diameter (m)', '12.6 \u00b1 2.9', '2.0', '14.0', '15.0'],
     ['Aspect ratio', '0.059 \u00b1 0.030', '0.0', '0.055', '0.17'],
     ['Rim symmetry std (m)', '0.70 \u00b1 0.48', '0.05', '0.56', '2.8'],
     ['Volume (m\u00b3)', '32.4 \u00b1 21.8', '0', '28.6', '150'],
     ['Slope \u2014 inner (\u00b0)', '10.1 \u00b1 6.1', '0.4', '8.4', '33'],
     ['LRM-5 depth (m)', '\u20130.14 \u00b1 0.15', '\u20130.74', '\u20130.13', '0.44'],
     ['LRM-11 depth (m)', '\u20130.33 \u00b1 0.37', '\u20131.30', '\u20130.37', '0.77']],
    'Table 4: Pit morphology descriptive statistics (n=856)')

add_body('The typical pit is a shallow bowl about 0.7 meters deep and 13 meters across. The aspect ratio of 0.06 tells the story\u2014these are extremely flat features relative to their diameter. A 13-meter-wide depression that is only 0.7 meters deep does not jump out at you in a DEM. The LRM-5 value at the center averages only -0.14 meters, which confirms that after trend removal at the 5-meter scale, the residual signal is remarkably subtle.')

add_fig(str(DERIV / 'paper_fig_morphology_boxplots.png'), 'Distribution of key morphological parameters across 856 measured pits.')

add_body('Volume averages about 32 cubic meters, estimated using a simple cone approximation. Rim symmetry standard deviation averages 0.70 meters, indicating these are roughly circular but not perfect\u2014many have an asymmetric profile, often because one side borders a flat well pad surface.')

doc.add_heading('Principal Component Analysis', level=2)
add_body('PCA on the 11-dimensional morphological space reveals three principal axes that explain 86.4% of the total variance. PC1 (39.2%) is simply how deep and voluminous the pit is\u2014depth, volume, and LRM-11 all load together. PC2 (33.8%) separates large flat depressions from narrow steep ones, with rim radius and diameter loading positively against slope. PC3 (13.4%) captures rim irregularity, driven mainly by the rim symmetry standard deviation.')

add_table(
    ['Component', 'Variance', 'Top Positive', 'Top Negative', 'Interpretation'],
    [['PC1', '39.2%', 'depth, volume', 'LRM-11', 'Pit magnitude'],
     ['PC2', '33.8%', 'rim_radius, diameter', 'slope', 'Size vs. steepness'],
     ['PC3', '13.4%', 'rim_symmetry_std', 'eff_radius', 'Shape irregularity']],
    'Table 5: Principal component loadings')

add_fig(str(DERIV / 'paper_fig_pca_anomaly.png'), 'PCA projection of pit morphology colored by Mahalanobis anomaly score. Labeled points are the five most anomalous annotations.')

doc.add_heading('Anomaly Detection', level=2)
add_body('The anomaly scoring flagged 90 pits (10.5%) with Mahalanobis distance exceeding 5.0. Table 6 breaks down the most common reasons.')

add_table(
    ['Anomaly Type', 'Count', 'Typical Cause', 'Dominant Feature'],
    [['Tiny radius (1\u20131.5 m)', '23', 'Annotation mis-click', 'rim_radius (z < -3.3)'],
     ['Extreme slope (>20\u00b0)', '18', 'Point on hillside', 'slope (z > +3.5)'],
     ['Negative/zero depth', '8', 'Not in a depression', 'depth (z < -2.0)'],
     ['Extreme volume (>100 m\u00b3)', '5', 'Borrow pit or natural', 'volume (z > +5.0)'],
     ['High rim asymmetry', '7', 'Partially collapsed', 'rim_symmetry (z > +4.0)']],
    'Table 6: Anomaly types among flagged annotations')

add_body('The top-ranked anomaly (FID 450, Mahalanobis = 11.1) has a rim radius of only 1.0 meter and inner slope of 13.5 degrees. That is consistent with a mis-click on a slope rather than an actual pit center. The second-ranked (FID 197, Mahalanobis = 10.9) has the deepest LRM-5 value in the entire dataset at -0.74 meters, which suggests it might be a natural karst or stream feature rather than an anthropogenic well cellar.')

add_body('We reviewed the top 30 flagged annotations manually. About half were genuine errors\u2014points placed on slopes, obvious mis-clicks, or locations with no measurable depression. The other half were unusual but legitimate: very deep cellars, heavily degraded pits, or features that had partially merged with adjacent terrain modifications. This kind of feedback loop is valuable. Removing the confirmed errors and retraining should improve model performance, particularly at the high-confidence end where label noise hits hardest.')

add_fig(str(DERIV / 'paper_fig_morphology_table.png'), 'Summary statistics for all measured morphological parameters.')

# ======== DISCUSSION ========
doc.add_heading('Discussion', level=1)

doc.add_heading('What the Numbers Mean', level=2)
add_body('The morphological characterization tells us why this detection problem is both feasible and hard. A depth of 0.7 meters is well above the vertical noise floor of 3DEP LiDAR (typically \u00b15\u201310 cm RMS on bare earth), so these features are theoretically detectable. But the aspect ratio of 0.06 means they are absurdly shallow relative to their diameter. A 13-meter-wide depression that is only 0.7 meters deep does not look like a crater\u2014it looks like a gentle dip in the terrain that could be natural.')

add_body('This is why no single metric works for detection. The LRM value alone is too subtle. The TPI alone overlaps too much with natural depressions. The template match score alone generates too many false positives. It takes the combination of all these metrics, fed through a gradient-boosted ensemble, to reliably separate real pits from look-alikes. And even then we are only recovering about a quarter of annotated pits at the 50% confidence threshold.')

doc.add_heading('The DEP Records Problem', level=2)
add_body('The cross-reference between our annotations and the PA DEP database drives home a point that is easy to understate: the official records are not just incomplete, they are unreliable for precise location work. Only 31% of DEP coordinates land within 10 meters of a visible feature. 87% of the features we identified have no DEP record at all within 100 meters. These are not minor discrepancies\u2014they mean the state database cannot be used as ground truth for a detection algorithm, and any field team relying solely on DEP coordinates would miss the vast majority of actual well sites.')

doc.add_heading('What Did Not Work', level=2)
add_body('Several approaches were tried and abandoned during development. Pad detection using rule-based shape filters never worked\u2014the shapes are too irregular after 150 years of forest regrowth. Hard-negative mining (up-weighting difficult false positives) reduced performance both times it was tried. LiDAR intensity, return counts, and scan angle characteristics proved completely uninformative for pit detection\u2014the signal is terrain shape, not LiDAR radiometry. HistGradientBoosting underperformed XGBoost and LightGBM by a significant margin on early runs and was only included in the final ensemble for diversity.')

doc.add_heading('Limitations', level=2)
add_body('All 861 annotations were created by a single operator, which introduces potential systematic bias in what constitutes a pit. No field validation has been performed\u2014everything here is measured from remote sensing data and we have no way of confirming whether our LiDAR-derived depths correspond to actual excavation depths. The 1-meter resolution constrains characterization of pits smaller than about 3 meters in diameter. The 7.5-meter search radius may cut off larger features. And geographic transferability to terrain types outside the Appalachian Plateau is completely untested.')

# ======== CONCLUSION ========
doc.add_heading('Conclusion', level=1)

add_body('This study establishes what collapsed oil and gas well cellar pits look like in western Pennsylvania. The typical feature is a shallow bowl about 0.7 meters deep and 13 meters across (aspect ratio 0.06) that is subtle but detectable in 1-meter LiDAR DEMs. PCA shows the main axis of variation is simply pit magnitude\u2014how deep and how big\u2014with secondary axes capturing the size-versus-steepness tradeoff and rim irregularity.')

add_body('The detection pipeline achieves 85.5% precision at the 0.80 probability threshold, demonstrating that these features can be systematically identified despite their shallow profiles. The anomaly detection framework flagged 10.5% of annotations as statistically unusual, and manual review confirmed about half of those were actual errors. Removing them should improve subsequent model iterations.')

add_body('The core finding is simple: collapsed well cellars have a measurable, consistent terrain signature that persists under forest canopy. It can be quantified from publicly available LiDAR data. The morphological database delivered with this study provides a foundation for future algorithm development and field verification prioritization.')

# ======== REFERENCES ========
doc.add_heading('References', level=1)

for ref in [
    'ASPRS. (2019). LAS specification 1.4-R15. American Society for Photogrammetry and Remote Sensing.',
    'Chase, A. F., Chase, D. Z., Weishampel, J. F., Drake, J. B., Shrestha, R. L., Slatton, K. C., Awe, J. J., & Carter, W. E. (2012). Airborne LiDAR, archaeology, and the ancient Maya landscape at Caracol, Belize. Journal of Archaeological Science, 38(2), 387\u2013398.',
    'Jasiewicz, J., & Stepinski, T. F. (2013). Geomorphons \u2014 a pattern recognition approach to classification and mapping of landforms. Geomorphology, 182, 147\u2013156.',
    'Kang, M., Kanno, C. M., Reid, M. C., Zhang, X., Mauzerall, D. L., Celia, M. A., Chen, Y., & Onstott, T. C. (2014). Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania. PNAS, 111(51), 18173\u201318177.',
    'Pennsylvania Department of Environmental Protection. (2023). Orphan and abandoned well plugging program. PA DEP Bureau of Oil and Gas Planning and Program Management.',
    'Ramachandran, N., Irvin, J., Omara, M., Gautam, R., Meisenhelder, K., Rostami, E., Sheng, H., Ng, A. Y., & Jackson, R. B. (2024). Deep learning for detecting and characterizing oil and gas well pads in satellite imagery. Nature Communications, 15(1), 7036.',
    'Trier, \u00d8. D., Cowley, D. C., & Waldeland, A. U. (2019). Using deep neural networks on airborne laser scanning data. Archaeological Prospection, 26(2), 165\u2013175.',
    'USGS. (2025). Lidar base specification (rev. A). U.S. Geological Survey.',
    'Yokoyama, R., Shirasawa, M., & Pike, R. J. (2002). Visualizing topography by openness. Photogrammetric Engineering and Remote Sensing, 68(3), 257\u2013265.',
]:
    p = doc.add_paragraph()
    p.add_run(ref)
    p.paragraph_format.left_indent = Cm(1.27)
    p.paragraph_format.first_line_indent = Cm(-1.27)

# ======== APPENDIX ========
doc.add_page_break()
doc.add_heading('Appendix A: Complete Feature Set', level=1)

add_body('Table A1 lists all 48 features extracted at each candidate location. Features are grouped by category. The inner ring covers cells within 3 meters of the candidate center (the pit bottom zone). The rim ring covers cells 6 to 8 meters from center (the surrounding terrain). Depth/contrast features are computed on six terrain derivative channels; surface features on four channels.')

add_table(
    ['#', 'Feature Name', 'Category', 'Description'],
    [
        ['1',  'lrm_5_inner_min',       'Depth/contrast', 'Minimum LRM-5 value in the inner ring'],
        ['2',  'lrm_5_inner_mean',      'Depth/contrast', 'Mean LRM-5 value in the inner ring'],
        ['3',  'lrm_5_rim_mean',        'Depth/contrast', 'Mean LRM-5 value in the rim ring'],
        ['4',  'lrm_5_rim_minus',       'Depth/contrast', 'Rim mean minus inner minimum (LRM-5)'],
        ['5',  'lrm_5_sym',             'Depth/contrast', 'Radial symmetry std. dev. on LRM-5'],
        ['6',  'lrm_11_inner_min',      'Depth/contrast', 'Minimum LRM-11 value in the inner ring'],
        ['7',  'lrm_11_inner_mean',     'Depth/contrast', 'Mean LRM-11 value in the inner ring'],
        ['8',  'lrm_11_rim_mean',       'Depth/contrast', 'Mean LRM-11 value in the rim ring'],
        ['9',  'lrm_11_rim_minus',      'Depth/contrast', 'Rim mean minus inner minimum (LRM-11)'],
        ['10', 'lrm_11_sym',            'Depth/contrast', 'Radial symmetry std. dev. on LRM-11'],
        ['11', 'lrm_25_inner_min',      'Depth/contrast', 'Minimum LRM-25 value in the inner ring'],
        ['12', 'lrm_25_inner_mean',     'Depth/contrast', 'Mean LRM-25 value in the inner ring'],
        ['13', 'lrm_25_rim_mean',       'Depth/contrast', 'Mean LRM-25 value in the rim ring'],
        ['14', 'lrm_25_rim_minus',      'Depth/contrast', 'Rim mean minus inner minimum (LRM-25)'],
        ['15', 'lrm_25_sym',            'Depth/contrast', 'Radial symmetry std. dev. on LRM-25'],
        ['16', 'tpi_05_inner_min',      'Depth/contrast', 'Minimum TPI-5 value in the inner ring'],
        ['17', 'tpi_05_inner_mean',     'Depth/contrast', 'Mean TPI-5 value in the inner ring'],
        ['18', 'tpi_05_rim_mean',       'Depth/contrast', 'Mean TPI-5 value in the rim ring'],
        ['19', 'tpi_05_rim_minus',      'Depth/contrast', 'Rim mean minus inner minimum (TPI-5)'],
        ['20', 'tpi_05_sym',            'Depth/contrast', 'Radial symmetry std. dev. on TPI-5'],
        ['21', 'tpi_15_inner_min',      'Depth/contrast', 'Minimum TPI-15 value in the inner ring'],
        ['22', 'tpi_15_inner_mean',     'Depth/contrast', 'Mean TPI-15 value in the inner ring'],
        ['23', 'tpi_15_rim_mean',       'Depth/contrast', 'Mean TPI-15 value in the rim ring'],
        ['24', 'tpi_15_rim_minus',      'Depth/contrast', 'Rim mean minus inner minimum (TPI-15)'],
        ['25', 'tpi_15_sym',            'Depth/contrast', 'Radial symmetry std. dev. on TPI-15'],
        ['26', 'openness_neg_inner_min','Depth/contrast', 'Minimum negative openness in the inner ring'],
        ['27', 'openness_neg_inner_mean','Depth/contrast','Mean negative openness in the inner ring'],
        ['28', 'openness_neg_rim_mean', 'Depth/contrast', 'Mean negative openness in the rim ring'],
        ['29', 'openness_neg_rim_minus','Depth/contrast', 'Rim mean minus inner minimum (neg. openness)'],
        ['30', 'openness_neg_sym',      'Depth/contrast', 'Radial symmetry std. dev. on neg. openness'],
        ['31', 'slope_inner_mean',      'Surface',        'Mean slope in the inner ring'],
        ['32', 'slope_window_max',      'Surface',        'Maximum slope in the 17x17 m window'],
        ['33', 'roughness_5_inner_mean','Surface',        'Mean roughness in the inner ring'],
        ['34', 'roughness_5_window_max','Surface',        'Maximum roughness in the window'],
        ['35', 'local_relief_10_inner_mean','Surface',    'Mean local relief (10 m) in the inner ring'],
        ['36', 'local_relief_10_window_max','Surface',    'Maximum local relief (10 m) in the window'],
        ['37', 'chm_inner_mean',        'Surface',        'Mean canopy height in the inner ring'],
        ['38', 'chm_window_max',        'Surface',        'Maximum canopy height in the window'],
        ['39', 'density_inner_mean',    'Density/match',  'Mean ground point density in the inner ring'],
        ['40', 'density_window_mean',   'Density/match',  'Mean ground point density in the window'],
        ['41', 'dem_cut_m',             'Density/match',  'DEM rim-minus-inner contrast (raw elevation)'],
        ['42', 'match_score_center',    'Density/match',  'NCC template match score at center pixel'],
        ['43', 'morph_center_depth',    'Morphology',     'LRM-5 value at the center pixel'],
        ['44', 'morph_ring_r0_2',       'Morphology',     'Mean LRM-5 in the 0–2 m band'],
        ['45', 'morph_ring_r2_5',       'Morphology',     'Mean LRM-5 in the 2–5 m band'],
        ['46', 'morph_ring_r5_8',       'Morphology',     'Mean LRM-5 in the 5–8 m band'],
        ['47', 'morph_radial_monotonicity','Morphology',  'Spearman correlation of ring means vs. distance'],
        ['48', 'morph_compactness',     'Morphology',     'Fraction of total LRM signal in the inner ring'],
    ],
    'Table A1: Complete 48-feature set used by the ensemble classifier')

doc.save('WellSight_Paper_v6.docx')
print('Saved: WellSight_Paper_v6.docx')
