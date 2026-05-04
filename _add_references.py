from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

PPTX = 'WellSight_Presentation.pptx'
prs = Presentation(PPTX)

BG = RGBColor(0x1a, 0x1a, 0x2e)
ACCENT = RGBColor(0x00, 0x96, 0xC7)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
GRAY = RGBColor(0xCC, 0xCC, 0xCC)

references = [
    "ASPRS. (2019). LAS specification 1.4-R15. American Society for Photogrammetry and Remote Sensing.",
    "Bofinger, J., Kurz, S., & Schmidt, S. (2006). Aerial survey and systematic evaluation of LiDAR data. In From Space to Place, BAR International Series 1568, 71-76.",
    "Chase, A. F., et al. (2012). Airborne LiDAR, archaeology, and the ancient Maya landscape at Caracol, Belize. Journal of Archaeological Science, 38(2), 387-398.",
    "De Reu, J., et al. (2013). Application of the topographic position index to heterogeneous landscapes. Geomorphology, 186, 39-49.",
    "Doneus, M. (2013). Openness as visualization technique for interpretative mapping of airborne LiDAR. Remote Sensing, 5(12), 6427-6442.",
    "Drohan, P. J., & Brittingham, M. (2012). Topographic and soil constraints to shale-gas development in the northcentral Appalachians. Environmental Management, 49(5), 1061-1075.",
    "Grohmann, C. H., Smith, M. J., & Riccomini, C. (2011). Multiscale analysis of topographic surface roughness in the Midland Valley, Scotland. IEEE Transactions on Geoscience and Remote Sensing, 49(4), 1200-1213.",
    "Hammack, R. W., et al. (2014). An evaluation of fracture growth, gas/fluid migration, and groundwater impacts. NETL Technical Report, DOE/NETL-2014/1660.",
    "Hesse, R. (2010). LiDAR-derived local relief models: A new tool for archaeological prospection. Archaeological Prospection, 17(2), 67-72.",
    "Jasiewicz, J., & Stepinski, T. F. (2013). Geomorphons: a pattern recognition approach to classification and mapping of landforms. Geomorphology, 182, 147-156.",
    "Kang, M., et al. (2014). Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania. PNAS, 111(51), 18173-18177.",
    "Pennsylvania DEP. (2023). Orphan and abandoned well plugging program. PA DEP Bureau of Oil and Gas Planning and Program Management.",
    "Ramachandran, N., et al. (2024). Deep learning for detecting and characterizing oil and gas well pads in satellite imagery. Nature Communications, 15(1), 7036.",
    "Riley, S. J., DeGloria, S. D., & Elliot, R. (1999). A terrain ruggedness index. Intermountain Journal of Sciences, 5(1-4), 23-27.",
    "Trier, O. D., Cowley, D. C., & Waldeland, A. U. (2019). Using deep neural networks on airborne laser scanning data. Archaeological Prospection, 26(2), 165-175.",
    "USGS. (2025). Lidar base specification (rev. A). U.S. Geological Survey.",
    "Weiss, A. D. (2001). Topographic position and landforms analysis. ESRI Users Conference, San Diego.",
    "White, B., et al. (2010). Ridge detection for transportation. Pattern Recognition, 43(5), 1270-1279.",
    "Yokoyama, R., Shirasawa, M., & Pike, R. J. (2002). Visualizing topography by openness. Photogrammetric Engineering and Remote Sensing, 68(3), 257-265.",
]

# Create the references slide
blank = None
for layout in prs.slide_layouts:
    if 'blank' in layout.name.lower():
        blank = layout
        break
if blank is None:
    blank = prs.slide_layouts[6]

slide = prs.slides.add_slide(blank)
bg = slide.background
fill = bg.fill
fill.solid()
fill.fore_color.rgb = BG

# Title
txBox = slide.shapes.add_textbox(Inches(0.4), Inches(0.2), Inches(9), Inches(0.5))
p = txBox.text_frame.paragraphs[0]
run = p.add_run()
run.text = "References"
run.font.size = Pt(28)
run.font.bold = True
run.font.color.rgb = ACCENT

# References text box - two columns via two text boxes
mid = len(references) // 2 + 1  # split roughly in half
left_refs = references[:mid]
right_refs = references[mid:]

def add_ref_column(slide, refs, left, top, width, height):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True

    for i, ref in enumerate(refs):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.space_after = Pt(4)
        p.space_before = Pt(0)
        run = p.add_run()
        run.text = ref
        run.font.size = Pt(8)
        run.font.color.rgb = GRAY

add_ref_column(slide, left_refs, Inches(0.3), Inches(0.8), Inches(4.6), Inches(6.5))
add_ref_column(slide, right_refs, Inches(5.1), Inches(0.8), Inches(4.6), Inches(6.5))

# Move to just before the appendix slides
sldIdLst = prs.slides._sldIdLst
sldId_elements = list(sldIdLst)
new_sldId = sldId_elements[-1]
sldIdLst.remove(new_sldId)
# Insert after Summary (slide 16), before first appendix (slide 17)
sldIdLst.insert(17, new_sldId)

prs.save(PPTX)

# Also update morphology notes with the cellar collapse context
prs2 = Presentation(PPTX)
slide11 = prs2.slides[11]
current = slide11.notes_slide.notes_text_frame.text

addition = """

WHY ONLY HISTORIC WELLS SHOW THIS SIGNATURE
- The collapsed cellar signature is specific to pre-regulation wells (roughly pre-1984 in PA)
- Early well cellars were earthen (just a hole in the ground) with no lining or reinforcement
- When the well was walked away from, there was no plugging requirement and no reclamation
- Over 50-150 years, the cellar walls slowly slump inward, creating the bowl we detect
- Modern wells (post-1984) have concrete-lined cellars, engineered pads, and legal plugging/reclamation requirements
- When a modern well is decommissioned, the cellar is filled, the pad is graded, and vegetation is replanted
- There is nothing left to collapse — so modern plugged wells leave NO pit signature
- This means our pipeline is inherently tuned to detect historic-era wells (1880s-1970s)
- This is actually ideal: those are exactly the wells most likely to be undocumented and orphaned
"""

slide11.notes_slide.notes_text_frame.text = current + addition
prs2.save(PPTX)

# Verify
prs3 = Presentation(PPTX)
for i, slide in enumerate(prs3.slides):
    title = ""
    for shape in slide.shapes:
        if shape.has_text_frame:
            txt = shape.text_frame.text.strip()
            if txt:
                title = txt[:50]
                break
    if i >= 15:
        print(f"Slide {i}: {title}")
print(f"Total: {len(prs3.slides)}")
