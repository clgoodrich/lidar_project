"""Build WellSight_Paper_skeleton_v3.docx — section headers, figures, tables, captions only.
No body text. Ready for manual writing."""
from docx import Document
from docx.shared import Inches, Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pathlib import Path

doc = Document()
style = doc.styles['Normal']
style.font.name = 'Calibri'
style.font.size = Pt(11)
style.font.color.rgb = RGBColor(0, 0, 0)
for section in doc.sections:
    section.top_margin = Cm(2.54)
    section.bottom_margin = Cm(2.54)
    section.left_margin = Cm(2.54)
    section.right_margin = Cm(2.54)

for heading_level in range(1, 4):
    heading_style = doc.styles[f'Heading {heading_level}']
    heading_style.font.color.rgb = RGBColor(0, 0, 0)

DERIV = Path('data/derivatives')
ROOT = Path('.')
fig_num = [0]


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


def placeholder(text=None):
    pass


# ======== TITLE ========
p = doc.add_paragraph()
run = p.add_run('WellSight: Morphological Characterization of Orphaned Oil and Gas Well Pits Using Airborne LiDAR in Western Pennsylvania')
run.bold = True
run.font.size = Pt(18)

p = doc.add_paragraph()
run = p.add_run('Colton Goodrich')
run.bold = True
run.font.size = Pt(16)

p = doc.add_paragraph()
run = p.add_run('University of Houston \u2014 April 2026')
run.font.size = Pt(12)
doc.add_paragraph()

# ======== INTRODUCTION ========
doc.add_heading('Introduction', level=1)
placeholder()

add_fig(str(ROOT / 'Pennsylvania Map.png'),
        'Distribution of documented oil and gas wells across Pennsylvania.')

add_fig(str(ROOT / 'Pennsylvania Map Abandoned.png'),
        'Distribution of abandoned wells in Pennsylvania.')

placeholder()

add_fig(str(ROOT / 'region_with_trees.png'),
        'Satellite imagery of the study area. Dense canopy hides all terrain features.')

placeholder()

add_fig(str(ROOT / 'region_without_trees.png'),
        'LiDAR hillshade of the same area. With canopy removed, roads, pads, and pits are visible.')

placeholder()

# ======== DATA ========
doc.add_heading('Data', level=1)

doc.add_heading('Study Region', level=2)
placeholder()

add_fig(str(ROOT / 'Areas of Interest.png'),
        'Study area tile footprints (white rectangles) on satellite imagery of western Pennsylvania.')

placeholder()

doc.add_heading('LiDAR Datasets', level=2)
placeholder()

add_fig(str(ROOT / 'Pennsylvania AOI.png'),
        'Study area with official PA DEP well locations by status category overlaid on LiDAR hillshade.')

add_table(
    ['Tile', 'Epoch', 'Extent', 'Density', 'Resolution'],
    [['Venango 9-tile', '2019 3DEP', '4.5 km x 4.5 km', '~4 pts/m\u00b2', '1 m'],
     ['McKean mk5', '2019 3DEP', '6.5 km x 6.5 km', '~4 pts/m\u00b2', '1 m'],
     ['McKean mkf', '2019 3DEP', '10 km x 10 km', '~4 pts/m\u00b2', '1 m']],
    'Table 1: LiDAR datasets')

doc.add_heading('Ground Truth Annotations', level=2)
placeholder()

add_fig(str(ROOT / 'Manual Picks.png'),
        'Hillshade detail showing manual pit annotations (black stars) alongside official DEP well locations by status.')

add_fig(str(ROOT / 'close up errors.png'),
        'Same area without manual annotations, showing DEP coordinate offset from visible pit features.')

add_fig(str(ROOT / 'orphaned with no clear wells.png'),
        'DEP orphan records in an area with no clearly visible pit depressions.')

# ======== METHODOLOGY ========
doc.add_heading('Methodology', level=1)

doc.add_heading('Environment', level=2)
placeholder()

doc.add_heading('Terrain Derivative Generation', level=2)
placeholder()

add_table(
    ['Derivative', 'Scales', 'Method', 'What It Shows'],
    [['Local Relief Model (LRM)', '3m, 5m, 11m, 25m', 'Mean subtraction', 'Residual micro-topography'],
     ['Topographic Position Index', '5m, 15m, 25m', 'Annular mean diff.', 'Local elevation anomaly'],
     ['Topographic Openness (neg)', '25m search', 'Yokoyama et al.', 'Depression enclosure'],
     ['Slope', '3x3 window', "Horn's method", 'Surface gradient'],
     ['Roughness', '5m window', 'Elevation std. dev.', 'Surface irregularity'],
     ['Local Relief', '10m disk', 'Max minus min', 'Elevation range'],
     ['Ground Density', '1m cells', 'Point count', 'LiDAR return coverage'],
     ['CHM', '\u2014', 'DSM minus DEM', 'Canopy height']],
    'Table 2: Terrain derivative stack')

doc.add_heading('Template-Based Candidate Generation', level=2)
placeholder()

doc.add_heading('Feature Engineering', level=2)
placeholder()

doc.add_heading('Ensemble Classification', level=2)
placeholder()

doc.add_heading('Morphological Measurement', level=2)
placeholder()

doc.add_heading('Anomaly Detection', level=2)
placeholder()

# ======== RESULTS ========
doc.add_heading('Results', level=1)

doc.add_heading('Detection Performance', level=2)
placeholder()

add_table(
    ['Threshold', 'Candidates', 'Hits (\u226410m)', 'Pits Covered', 'False Pos.', 'Precision'],
    [['0.30', '771', '403', '325', '368', '52.3%'],
     ['0.40', '397', '272', '234', '125', '68.5%'],
     ['0.50', '336', '247', '213', '89', '73.5%'],
     ['0.70', '241', '190', '166', '51', '78.8%'],
     ['0.80', '76', '65', '60', '11', '85.5%'],
     ['0.90', '8', '8', '8', '0', '100.0%']],
    'Table 3: Precision-recall at probability thresholds')

placeholder()

doc.add_heading('Morphological Characterization', level=2)
placeholder()

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

add_fig(str(DERIV / 'paper_fig_morphology_boxplots.png'),
        'Distribution of key morphological parameters across 856 measured pits.')

placeholder()

doc.add_heading('Principal Component Analysis', level=2)
placeholder()

add_table(
    ['Component', 'Variance', 'Top Positive', 'Top Negative', 'Interpretation'],
    [['PC1', '39.2%', 'depth, volume', 'LRM-11', 'Pit magnitude'],
     ['PC2', '33.8%', 'rim_radius, diameter', 'slope', 'Size vs. steepness'],
     ['PC3', '13.4%', 'rim_symmetry_std', 'eff_radius', 'Shape irregularity']],
    'Table 5: Principal component loadings')

add_fig(str(DERIV / 'paper_fig_pca_anomaly.png'),
        'PCA projection of pit morphology colored by Mahalanobis anomaly score.')

doc.add_heading('Anomaly Detection', level=2)
placeholder()

add_table(
    ['Anomaly Type', 'Count', 'Typical Cause', 'Dominant Feature'],
    [['Tiny radius (1\u20131.5 m)', '23', 'Annotation mis-click', 'rim_radius (z < -3.3)'],
     ['Extreme slope (>20\u00b0)', '18', 'Point on hillside', 'slope (z > +3.5)'],
     ['Negative/zero depth', '8', 'Not in a depression', 'depth (z < -2.0)'],
     ['Extreme volume (>100 m\u00b3)', '5', 'Borrow pit or natural', 'volume (z > +5.0)'],
     ['High rim asymmetry', '7', 'Partially collapsed', 'rim_symmetry (z > +4.0)']],
    'Table 6: Anomaly types among flagged annotations')

placeholder()

add_fig(str(DERIV / 'paper_fig_morphology_table.png'),
        'Summary statistics for all measured morphological parameters.')

# ======== DISCUSSION ========
doc.add_heading('Discussion', level=1)

doc.add_heading('What the Numbers Mean', level=2)
placeholder()

doc.add_heading('The DEP Records Problem', level=2)
placeholder()

doc.add_heading('What Did Not Work', level=2)
placeholder()

doc.add_heading('Limitations', level=2)
placeholder()

# ======== FUTURE WORK ========
doc.add_heading('Future Work', level=1)

doc.add_heading('Geomorphon Enclosure Analysis', level=2)
placeholder('[Geomorphon enclosure count (0-8 scale) as both a classification feature and candidate generator. Preliminary testing showed mean enclosure 6.9/8 at pit locations vs 4.0 background, improving PR-AUC by 31%.]')

doc.add_heading('U-Net Semantic Segmentation', level=2)
placeholder('[Potential to replace the template match + ensemble pipeline with a U-Net operating directly on the multi-channel raster stack. With 861 labeled pits and rotational augmentation, the training set may be sufficient.]')

doc.add_heading('Land Cover and Canopy Characterization', level=2)
placeholder('[Use CHM and ground density to classify whether each pit is under canopy or in a clearing. Integrate land cover data to categorize pits by surrounding vegetation type. Assess whether detection performance varies with canopy cover.]')

doc.add_heading('Field Validation', level=2)
placeholder('[Ground-truth the highest-confidence predictions. Confirm that LiDAR-measured depths correspond to actual excavation depths. Verify that detected features are anthropogenic well cellars rather than natural depressions.]')

doc.add_heading('Annotation Quality Closure', level=2)
placeholder('[Remove confirmed annotation errors flagged by anomaly detection and retrain the ensemble to quantify the performance improvement from cleaner training labels.]')

# ======== CONCLUSION ========
doc.add_heading('Conclusion', level=1)
placeholder()

# ======== REFERENCES ========
doc.add_heading('References', level=1)

for ref in [
    'ASPRS. (2019). LAS specification 1.4-R15. American Society for Photogrammetry and Remote Sensing.',
    'Chase, A. F., et al. (2012). Airborne LiDAR, archaeology, and the ancient Maya landscape. Journal of Archaeological Science, 38(2), 387\u2013398.',
    'Jasiewicz, J., & Stepinski, T. F. (2013). Geomorphons. Geomorphology, 182, 147\u2013156.',
    'Kang, M., et al. (2014). Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania. PNAS, 111(51), 18173\u201318177.',
    'Pennsylvania DEP. (2023). Orphan and abandoned well plugging program.',
    'Ramachandran, N., et al. (2024). Deep learning for detecting and characterizing oil and gas well pads. Nature Communications, 15(1), 7036.',
    'Trier, \u00d8. D., et al. (2019). Using deep neural networks on airborne laser scanning data. Archaeological Prospection, 26(2), 165\u2013175.',
    'USGS. (2025). Lidar base specification (rev. A).',
    'Yokoyama, R., et al. (2002). Visualizing topography by openness. PE&RS, 68(3), 257\u2013265.',
]:
    p = doc.add_paragraph()
    p.add_run(ref)
    p.paragraph_format.left_indent = Cm(1.27)
    p.paragraph_format.first_line_indent = Cm(-1.27)

doc.save('WellSight_Paper_skeleton_v3.docx')
print('Saved: WellSight_Paper_skeleton_v3.docx')
