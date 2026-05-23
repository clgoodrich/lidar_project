"""Build WellSight presentation — matched to V9 paper. Pipeline walkthrough structure."""
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pathlib import Path

DERIV = Path('data/derivatives')
ROOT = Path('.')
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

DARK = RGBColor(0x1A, 0x1A, 0x2E)
ACCENT = RGBColor(0x00, 0x96, 0xC7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
LIGHT_GRAY = RGBColor(0xF0, 0xF0, 0xF0)
ORANGE = RGBColor(0xFF, 0x57, 0x22)
GREEN = RGBColor(0x4C, 0xAF, 0x50)
BLUE = RGBColor(0x21, 0x96, 0xF3)
GRAY = RGBColor(0xAA, 0xAA, 0xAA)

def add_bg(slide):
    slide.background.fill.solid()
    slide.background.fill.fore_color.rgb = DARK

def tb(slide, left, top, width, height, text, size=18, color=WHITE, bold=False,
       align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame; tf.word_wrap = True
    p = tf.paragraphs[0]; p.text = text
    p.font.size = Pt(size); p.font.color.rgb = color; p.font.bold = bold
    p.font.name = 'Calibri'; p.alignment = align
    return tf

def bullets(slide, left, top, width, height, items, size=18, color=WHITE):
    box = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = box.text_frame; tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = item; p.font.size = Pt(size); p.font.color.rgb = color
        p.font.name = 'Calibri'; p.space_after = Pt(8)

def img(slide, path, left, top, width=None, height=None):
    p = Path(path)
    if not p.exists():
        print(f"  SKIP: {p}"); return
    kw = {}
    if width: kw['width'] = Inches(width)
    if height: kw['height'] = Inches(height)
    slide.shapes.add_picture(str(p), Inches(left), Inches(top), **kw)

def tbl(slide, left, top, width, height, data):
    rows, cols = len(data), len(data[0])
    shape = slide.shapes.add_table(rows, cols, Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    t = shape.table
    for c in range(cols):
        cell = t.cell(0, c); cell.text = data[0][c]
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(14); p.font.bold = True; p.font.color.rgb = WHITE
            p.font.name = 'Calibri'; p.alignment = PP_ALIGN.CENTER
        cell.fill.solid(); cell.fill.fore_color.rgb = ACCENT
    for r in range(1, rows):
        for c in range(cols):
            cell = t.cell(r, c); cell.text = data[r][c]
            for p in cell.text_frame.paragraphs:
                p.font.size = Pt(13); p.font.color.rgb = RGBColor(0x33,0x33,0x33)
                p.font.name = 'Calibri'; p.alignment = PP_ALIGN.CENTER
            cell.fill.solid()
            cell.fill.fore_color.rgb = WHITE if r % 2 == 1 else LIGHT_GRAY

# ==== SLIDE 1: Title ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 1.5, 1.5, 10, 1.5, "WellSight", size=54, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
tb(s, 1.5, 3.0, 10, 1.2,
   "Morphological Characterization of Orphaned Oil and Gas\nWell Pits Using Airborne LiDAR in Western Pennsylvania",
   size=24, color=WHITE, align=PP_ALIGN.CENTER)
tb(s, 1.5, 5.0, 10, 0.5, "Colton Goodrich", size=20, color=WHITE, align=PP_ALIGN.CENTER)
tb(s, 1.5, 5.5, 10, 0.5, "University of Houston", size=16, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 2: The Problem ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "The Problem", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.3, 5.5, 5.0, [
    "First American oil wells drilled in PA in the mid-1800s",
    "200,000+ documented wells statewide",
    "2021 Infrastructure Act: $4.7B for remediation",
    "Biggest impediment: finding them in the first place",
    "Decades old, hidden under dense forest canopy",
    "DEP coordinates unreliable: 50-200 m error",
], size=18)
img(s, ROOT / 'docs/figures/Pennsylvania Map.png', 6.5, 1.2, width=6.3)

# ==== SLIDE 3: Why LiDAR? ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Why LiDAR?", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.3, 5.0, 3.5, [
    "Laser pulses penetrate the canopy",
    "Resolve bare-earth surface beneath the trees",
    "Roads, pads, and collapse pits become visible",
    "1 m resolution captures features >2 m diameter",
], size=18)
img(s, ROOT / 'docs/figures/region_with_trees.png', 6.0, 1.2, width=3.3)
img(s, ROOT / 'docs/figures/region_without_trees.png', 9.5, 1.2, width=3.3)
tb(s, 6.0, 5.2, 3.3, 0.4, "Satellite (canopy)", size=12, color=GRAY, align=PP_ALIGN.CENTER)
tb(s, 9.5, 5.2, 3.3, 0.4, "LiDAR hillshade (ground)", size=12, color=GRAY, align=PP_ALIGN.CENTER)
tb(s, 6.0, 5.7, 6.8, 0.4, "Same location — LiDAR sees through the trees",
   size=14, bold=True, color=ORANGE, align=PP_ALIGN.CENTER)

# ==== SLIDE 4: Study Area ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Study Area", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.2, 5.5, 4.5, [
    "Venango & McKean Counties, western Pennsylvania",
    "Appalachian Plateau: moderate to steep slopes,",
    "  deeply incised stream valleys, heavy deciduous",
    "  and mixed forest canopy",
    "150+ years of coal, oil, and gas extraction",
    "USGS 3DEP LiDAR (2018-2020), QL2 quality level",
    "  Leica ALS80 sensor, ~1,400-2,400 m AGL, ~4 pts/m²",
    "DEM gridded at 1 m from ground-classified points",
    "Study tiles cover 4.5 x 4.5 km each",
], size=16)
img(s, DERIV / 'study_area_map.png', 6.0, 1.0, width=3.5)
img(s, DERIV / 'study_area_hillshade.png', 9.7, 1.0, width=3.5)

# ==== SLIDE 5: Pipeline Overview (roadmap) ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Pipeline Overview", size=36, bold=True, color=ACCENT)
steps = [
    ("Step 1\nTerrain\nDerivatives",
     ["DEM, slope, roughness,", "TPI, LRM, openness"], ACCENT),
    ("Step 2\nManual\nAnnotation",
     ["861 pits picked in", "QGIS on hillshade"], ORANGE),
    ("Step 3\nTemplate\nMatching",
     ["Mean pit template,", "NCC scan: 628k candidates"], BLUE),
    ("Step 4\nEnsemble\nClassification",
     ["48 features, 3 models,", "spatial CV, calibration"], GREEN),
]
for i, (title, items, color) in enumerate(steps):
    x = 0.3 + i * 3.2
    tb(s, x, 1.2, 3.0, 1.2, title, size=18, bold=True, color=color, align=PP_ALIGN.CENTER)
    bullets(s, x, 2.8, 3.0, 2.0, items, size=14, color=WHITE)
    # Draw a colored bar under each step
for i in range(3):
    tb(s, 3.1 + i * 3.2, 1.8, 0.5, 0.5, "→", size=28, bold=True,
       color=RGBColor(0x66,0x66,0x66), align=PP_ALIGN.CENTER)

tb(s, 0.5, 5.0, 12.3, 0.8,
   "The following slides walk through each step in detail",
   size=16, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 6: Step 1 — Terrain Derivatives ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 8, 0.8, "Step 1: Terrain Derivatives", size=36, bold=True, color=ACCENT)
tb(s, 10.5, 0.35, 2.5, 0.5, "1 / 4", size=16, color=GRAY, align=PP_ALIGN.RIGHT)
tbl(s, 0.5, 1.3, 12.3, 4.0, [
    ["Derivative", "Window", "What It Captures"],
    ["Slope", "3x3 (Horn)", "How steep the ground is at each cell"],
    ["Roughness", "11x11 std dev", "Surface texture: smooth pad vs rough forest floor"],
    ["TPI", "5 / 15 / 25 m radii", "Is this cell higher or lower than surroundings?"],
    ["LRM", "5, 11, 25, 51 cells", "Micro-relief after removing regional trend"],
    ["Openness", "25 m radius", "How enclosed or exposed a location is"],
    ["Hillshade", "az=315, alt=45", "Shaded relief for visual interpretation"],
])
tb(s, 0.5, 5.8, 12.3, 0.5,
   "LRM turned out to be the single most important derivative for pit detection",
   size=15, color=RGBColor(0xCC,0xCC,0xCC), align=PP_ALIGN.CENTER)

# ==== SLIDE 7: Step 2 — Manual Annotation ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 8, 0.8, "Step 2: Manual Annotation", size=36, bold=True, color=ACCENT)
tb(s, 10.5, 0.35, 2.5, 0.5, "2 / 4", size=16, color=GRAY, align=PP_ALIGN.RIGHT)
bullets(s, 0.5, 1.3, 5.5, 5.0, [
    "861 pits picked manually in QGIS on hillshade",
    "Conservative: only features we felt were defensible",
    "DEP records don't align with visible features —",
    "  many DEP dots have no visible pit, and many",
    "  pits have no DEP record",
    "This mismatch made our own annotations essential",
    "  (we could not train on DEP locations alone)",
], size=17)
img(s, ROOT / 'docs/figures/Manual Picks.png', 6.5, 1.0, width=6.3)

# ==== SLIDE 8: Step 3 — Template Matching ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 8, 0.8, "Step 3: Template Matching", size=36, bold=True, color=ACCENT)
tb(s, 10.5, 0.35, 2.5, 0.5, "3 / 4", size=16, color=GRAY, align=PP_ALIGN.RIGHT)
bullets(s, 0.5, 1.3, 5.0, 4.5, [
    "For each of 861 pits, extract a 17x17 m",
    "  window from 5 terrain channels",
    "Average all windows into a mean template",
    "Scan template across tiles using normalized",
    "  cross-correlation (NCC)",
    "~628,000 candidate locations generated",
    "Clustering reveals 3 morphological types",
], size=16)
img(s, DERIV / 'pit_1m_template_mean.png', 5.8, 1.0, width=7.0)
tb(s, 5.8, 5.4, 7.0, 0.5,
   "Mean (top) and median (bottom) pit template across 5 terrain channels",
   size=12, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 9: Step 4 — Ensemble Classification & Results ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 8, 0.8, "Step 4: Classification & Results", size=36, bold=True, color=ACCENT)
tb(s, 10.5, 0.35, 2.5, 0.5, "4 / 4", size=16, color=GRAY, align=PP_ALIGN.RIGHT)
tbl(s, 0.5, 1.3, 5.5, 4.0, [
    ["Threshold", "Precision", "Candidates"],
    ["0.50", "42.8%", "1,247"],
    ["0.60", "62.1%", "782"],
    ["0.70", "76.9%", "507"],
    ["0.80", "85.5%", "289"],
    ["0.90", "93.2%", "118"],
])
tb(s, 0.5, 5.5, 5.5, 1.2,
   "ROC-AUC: 0.905 | PR-AUC: 0.212\n"
   "Ensemble: XGBoost + LightGBM + HistGradientBoosting\n"
   "Spatial CV with 500 m grid separation\n"
   "48 features per candidate, isotonic calibration",
   size=14, color=RGBColor(0xCC,0xCC,0xCC))
img(s, DERIV / 'pit_detection_zoom_panels.png', 0.3, 4.5, width=12.7)
tb(s, 0.3, 7.0, 12.7, 0.4,
   "Green circles = our annotations | Orange/red dots = model detections | 400 m windows",
   size=13, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 10: What a Well Pit Looks Like ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "What a Well Pit Looks Like", size=36, bold=True, color=ACCENT)
bullets(s, 4.0, 1.3, 5.5, 2.5, [
    "A shallow bowl ~0.7 m deep and 13 m across",
    "Not the wellbore — the collapsed cellar",
    "  that surrounded the wellhead",
    "Depth well above LiDAR noise floor (0.10 m)",
    "Volume averages ~32 m³",
], size=16)
img(s, ROOT / 'docs/figures/wellspot.jpg', 0.3, 1.2, width=3.5)
tb(s, 0.3, 4.3, 3.5, 0.5,
   "Photo: Scott Detrow / StateImpact PA, 2012",
   size=10, color=GRAY, align=PP_ALIGN.CENTER)
img(s, ROOT / 'docs/figures/pit_profile_diagram.png', 4.0, 4.0, width=8.8)
tb(s, 4.0, 6.8, 8.8, 0.4,
   "Cross-section of average orphaned well pit",
   size=11, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 11: Annotation QA ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Annotation Quality Control", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.3, 5.5, 4.0, [
    "Applied 4 anomaly algorithms to 856 measured pits",
    "90 pits (10.5%) flagged with Mahalanobis > 5",
    "Manual review of top 30:",
    "  ~half genuine errors (mis-clicks, wrong spots)",
    "  ~half unusual but correct (deep cellars,",
    "   degraded pits in steep terrain)",
    "PCA: 3 components explain 86.4% of variance",
], size=16)
tbl(s, 6.3, 1.3, 6.5, 3.5, [
    ["Anomaly Type", "Count", "Typical Cause"],
    ["Tiny radius (1-1.5 m)", "23", "Annotation mis-click"],
    ["Extreme slope (>20°)", "18", "Point on hillside"],
    ["Negative/zero depth", "8", "Not in a depression"],
    ["Extreme volume (>100 m³)", "5", "Borrow pit or natural"],
])
tb(s, 6.3, 5.2, 6.5, 1.0,
   "Anomaly detection identifies annotations that warrant\n"
   "manual review before training the classifier on them",
   size=14, color=RGBColor(0xCC,0xCC,0xCC), align=PP_ALIGN.CENTER)

# ==== SLIDE 12: DEP Records Problem ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "The DEP Records Problem", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.3, 5.5, 4.5, [
    "DEP records are not just incomplete —",
    "  where they exist, they are unreliable",
    "Coordinates systematically offset from visible pits",
    "Some orphan records have no terrain signature at all",
    "Pre-1990 coords from plat maps: 50-200 m error",
    "This is why we could not train on DEP locations",
    "Visual annotation on hillshade was the only option",
], size=16)
img(s, ROOT / 'docs/figures/close up errors.png', 6.3, 1.0, width=6.5)
tb(s, 6.3, 5.8, 6.5, 0.4,
   "DEP well locations (dots) offset from visible pit features on hillshade",
   size=12, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 13: Challenges & Limitations ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Challenges & Limitations", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.5, 5.5, 5.0, [
    "All annotations by single operator — bias risk",
    "No field validation — entirely remote sensing",
    "No single metric works: LRM and TPI alone",
    "  overlap too much with natural depressions",
    "Pad detection with rule-based filters was unreliable",
    "1 m resolution at Nyquist limit for small pits",
    "Generalization to other regions untested",
], size=18)
img(s, ROOT / 'docs/figures/orphaned with no clear wells.png', 6.5, 1.2, width=6.3)
tb(s, 6.5, 5.8, 6.3, 0.5,
   "DEP-listed orphan wells with no visible terrain signature",
   size=12, color=GRAY, align=PP_ALIGN.CENTER)

# ==== SLIDE 14: Future Work ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Future Work", size=36, bold=True, color=ACCENT)
bullets(s, 0.5, 1.5, 5.8, 5.0, [
    "Geomorphon enclosure: preliminary +31% PR-AUC gain",
    "U-Net semantic segmentation on terrain patches",
    "Land cover & canopy height characterization",
    "Negative feature class (ponds, basements, etc.)",
    "Field validation with geotagged photos",
    "Expand to additional PA counties",
], size=18)
img(s, DERIV / 'paper_fig_hillshade_polygons.png', 6.5, 1.0, height=5.8)

# ==== SLIDE 15: Summary ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 1.0, 0.8, 11, 1.0, "Summary", size=40, bold=True, color=ACCENT, align=PP_ALIGN.CENTER)
bullets(s, 1.5, 2.0, 10, 4.5, [
    "Typical pit: 0.7 m deep, 13 m across — subtle but detectable",
    "No single metric works; ensemble of 48 features is required",
    "85.5% precision at 0.80 probability threshold",
    "Anomaly detection flags 10.5% of annotations for review",
    "DEP records are unreliable — visual annotation is essential",
    "Next: field validation, geomorphons, deep learning",
], size=22, color=WHITE)
tb(s, 1.0, 6.5, 11, 0.5,
   "Colton Goodrich | University of Houston | WellSight Project",
   size=16, color=RGBColor(0x77,0x77,0x77), align=PP_ALIGN.CENTER)

# ==== APPENDIX: 3DEP Collection Parameters ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Appendix: USGS 3DEP Collection Parameters",
   size=30, bold=True, color=ACCENT)
tbl(s, 0.5, 1.2, 5.8, 5.5, [
    ["Parameter", "Value"],
    ["Sensor", "Leica ALS80 (most common)"],
    ["Laser", "Nd:YAG 1064 nm (near-IR)"],
    ["Pulse rate", "200-400 kHz (QL2 typical)"],
    ["Flight altitude", "1,400-2,400 m AGL"],
    ["Airspeed", "100-130 knots"],
    ["Swath width", "750-1,500 m"],
    ["Swath overlap", "30-60%"],
    ["Footprint diameter", "0.25-0.50 m at typical AGL"],
    ["Beam divergence", "0.22-0.30 mrad"],
    ["Platform", "Fixed-wing (e.g. Cessna Caravan)"],
])
tbl(s, 6.8, 1.2, 6.0, 5.5, [
    ["QL2 Specification", "Requirement"],
    ["Nominal pulse spacing", "≤ 0.71 m"],
    ["Aggregate density", "≥ 2.0 pts/m²"],
    ["DEM cell size", "1.0 m"],
    ["Vertical accuracy (NVA)", "RMSE ≤ 0.10 m"],
    ["Relative accuracy", "RMSD ≤ 0.06 m (smooth)"],
    ["Returns per pulse", "≥ 3 discrete"],
    ["Season", "Leaf-off preferred"],
    ["Snow", "Snow-free required"],
    ["Format", "LAS 1.4, point format 6-10"],
    ["Our measured density", "~4 pts/m² (2x QL2 min)"],
])

# ==== APPENDIX: Literature Parameters ====
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 12, 0.8, "Appendix: Literature-Grounded Parameters",
   size=30, bold=True, color=ACCENT)
tbl(s, 0.8, 1.2, 11.7, 5.5, [
    ["Parameter", "Value", "Source"],
    ["DEM resolution", "1 m", "Hesse (2010), Doneus (2013)"],
    ["TPI radii", "5 / 15 / 25.5 m", "Weiss (2001), De Reu et al. (2013)"],
    ["LRM windows", "5-51 cells", "Hesse (2010), Bofinger et al. (2006)"],
    ["Roughness kernel", "11x11", "Riley et al. (1999)"],
    ["Openness radius", "25 m", "Yokoyama et al. (2002)"],
    ["Slope threshold", "8 deg", "Drohan & Brittingham (2012)"],
    ["Min pad area", "100 m2", "Hammack et al. (2014, NETL)"],
    ["Blob sigma range", "0.8-5.0", "Hammack et al. (2014, NETL)"],
    ["Positional uncert.", "100 m", "Kang et al. (2014, NETL/DOE)"],
])

out = 'WellSight_Presentation.pptx'
prs.save(out)
print(f"Saved: {out} ({len(prs.slides)} slides)")
