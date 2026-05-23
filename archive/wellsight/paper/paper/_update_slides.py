from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

PPTX = 'WellSight_Presentation.pptx'
prs = Presentation(PPTX)

# ============================================================
# 1. Replace graphics on slides 8, 13, 14, 15
# ============================================================
replacements = {
    8:  ('Manual Picks.png', Inches(5.0), Inches(1.3), Inches(4.8), Inches(5.8)),
    13: ('close up errors.png', Inches(5.0), Inches(1.3), Inches(4.8), Inches(5.8)),
    14: ('orphaned with no clear wells.png', Inches(5.0), Inches(1.3), Inches(4.8), Inches(5.8)),
    15: ('future_work_rims.png', Inches(5.0), Inches(1.3), Inches(4.8), Inches(5.8)),
}

for si, (img, left, top, w, h) in replacements.items():
    slide = prs.slides[si]
    for shape in list(slide.shapes):
        if shape.shape_type == 13:
            shape._element.getparent().remove(shape._element)
    slide.shapes.add_picture(img, left, top, w, h)
    print(f"Replaced graphic on slide {si}")

# ============================================================
# 2. Move DEP Records Problem (slide 13) to after Study Area (slide 5)
# ============================================================
sldIdLst = prs.slides._sldIdLst
sldId_elements = list(sldIdLst)
dep_sldId = sldId_elements[13]
sldIdLst.remove(dep_sldId)
sldIdLst.insert(6, dep_sldId)  # after slide 5 (Study Area), at index 6
print("Moved DEP Records Problem to position 6 (after Study Area)")

# ============================================================
# 3. Rewrite notes for Step 3, Step 4, Measured Pit Morphology
# ============================================================
# After the move, slide indices shift. Let me save first and reload to get correct indices.
prs.save(PPTX)
print("Saved after graphic replacements and slide move.")

prs = Presentation(PPTX)

# Verify new order
for i, slide in enumerate(prs.slides):
    title = ""
    for shape in slide.shapes:
        if shape.has_text_frame:
            txt = shape.text_frame.text.strip()
            if txt:
                title = txt[:50]
                break
    print(f"Slide {i}: {title}")

# Find slides by title
slide_map = {}
for i, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        if shape.has_text_frame:
            txt = shape.text_frame.text.strip()
            if txt:
                slide_map[i] = txt[:50]
                break

# Step 3: Template Matching
for i, title in slide_map.items():
    if 'Template Matching' in title:
        ns = prs.slides[i].notes_slide
        ns.notes_text_frame.text = """STEP 3: TEMPLATE MATCHING

WHAT WE DID
- Took all 861 annotated pits and cut out a small 17m x 17m terrain patch around each one
- Did this across 5 different terrain layers (LRM at two scales, TPI, openness, hillshade)
- Averaged all 540 usable patches together to create the "average pit" — the template
- Then slid this template across the entire landscape asking "does this spot look like our average pit?"
- Every spot that scored above a threshold became a candidate — 628,332 total

WHAT IS NCC?
- NCC = Normalized Cross-Correlation
- It is a similarity score between -1 and +1
- +1 means "this spot looks exactly like our template"
- 0 means "no resemblance"
- We keep everything above a low threshold to cast a wide net — the classifier in Step 4 does the real filtering

THE GRAPHIC
- Top row: the mean (average) template across all 540 pits for each terrain channel
- Bottom row: the median template (less affected by outliers)
- Blue center in LRM/TPI = depression (the pit). Red ring = higher ground (the rim)
- The template is symmetric because pits have no preferred compass orientation
"""
        print(f"  Updated notes for slide {i} (Template Matching)")

    if 'Classification' in title:
        ns = prs.slides[i].notes_slide
        ns.notes_text_frame.text = """STEP 4: CLASSIFICATION & RESULTS

WHAT WE DID
- Started with 628,332 candidate locations from template matching
- Measured 48 terrain properties at each one (depth, shape, roughness, symmetry, etc.)
- Trained 3 machine learning models to learn "real pit" vs "not a pit"
- Combined their votes into one final score per candidate

THE THRESHOLD
- Each candidate gets a probability score from 0 to 1
- Higher = more confident it is a real pit
- At 0.70 threshold: 507 candidates remain, 76.9% are real pits
- At 0.80 threshold: 289 candidates remain, 85.5% are real pits
- At 0.90 threshold: 118 candidates remain, 93.2% are real pits
- You choose the threshold based on your tolerance for false positives vs missed detections

WHAT IS ROC-AUC? (0.905)
- Imagine picking one real pit and one random spot. ROC-AUC is the probability the model scores the real pit higher.
- 0.905 means: 90.5% of the time, the model correctly ranks a real pit above a non-pit
- 0.5 would be a coin flip. 1.0 would be perfect. 0.905 is very good.

WHAT IS PR-AUC? (0.212)
- Precision-Recall AUC measures performance when positives are extremely rare
- Only 0.37% of our candidates are real pits (about 1 in 270)
- A naive model that guessed randomly would get PR-AUC of 0.0037
- Our 0.212 is 57x better than random — strong for this level of imbalance
- PR-AUC is the harder, more honest metric

THE THREE MODELS
- XGBoost, LightGBM, HistGradientBoosting
- All are "gradient boosted decision trees" — they make predictions by chaining hundreds of simple yes/no questions
- Using 3 models instead of 1 reduces the chance of any single model's blind spots causing errors
- Isotonic calibration converts raw scores into real probabilities (so 0.80 really means ~80% chance)

SPATIAL CROSS-VALIDATION
- We split the map into zones with 500m gaps between training and testing areas
- This prevents cheating: nearby terrain is similar, so without gaps the model would score artificially high
- 5-fold: each area gets a turn as the test set

THE GRAPHIC
- Green circles = pits we annotated by hand (ground truth)
- Colored dots = pits the model found (yellow = ~0.6 confidence, red = ~1.0)
- Where they overlap = correct detection
"""
        print(f"  Updated notes for slide {i} (Classification)")

    if 'Measured Pit Morphology' in title:
        ns = prs.slides[i].notes_slide
        ns.notes_text_frame.text = """MEASURED PIT MORPHOLOGY

WHAT THIS SHOWS
- We measured the actual physical shape of 856 annotated well pits from the 1-meter LiDAR surface
- The cross-section is drawn at true scale — no vertical exaggeration

THE NUMBERS
- Depth: 0.72 m average (about 2.4 feet — roughly knee height)
- Diameter: 12.6 m average (about 41 feet — width of a two-car garage)
- Volume: 32.4 cubic meters (about 8,500 gallons if filled with water)
- Inner slope: about 10 degrees (gentle enough to walk in and out)
- Rims are uneven: one side averages 1.63 m above the floor, the other only 0.72 m
- This asymmetry comes from 100+ years of uneven soil erosion and root action

WHAT IS A "COLLAPSED CELLAR"?
- The pit is NOT the drill hole (a wellbore is only 6-12 inches wide)
- A well cellar was a below-grade pit dug around the wellhead so workers could access equipment
- Typically 10-15 feet across, unlined (just dirt walls) for pre-regulation wells
- After abandonment, the walls slowly slump inward over decades, creating the bowl shape we detect

WHY THIS MATTERS
- At 0.72 m deep, pits are well above the LiDAR noise floor (about 5-10 cm)
- They are subtle but real — you could walk over one and barely notice it under leaves
- The aspect ratio (depth / diameter) is only 0.06 — extremely flat
- This is why no single metric finds them; you need the full 48-feature ensemble

WHY ONLY OLD WELLS HAVE THIS
- Pre-regulation wells (before 1984) had dirt cellars with no plugging or reclamation requirements
- Modern wells have concrete cellars, engineered pads, and legal reclamation when decommissioned
- Nothing collapses on a properly closed modern well — our pipeline inherently targets historic-era wells
- This is ideal: those are the ones most likely to be undocumented and orphaned

ACTIVE WELLS ON COLLAPSED PITS
- Some wells classified as "Active" sit on collapsed pits — this is not a contradiction
- Stripper wells: wells drilled in the 1880s-1920s that still produce less than 1 barrel/day
- The pipe still produces but nobody maintains the surface — the cellar collapses around it
- Some operators report minimal production to avoid plugging costs ($30k-$100k+)
- A collapsed cellar tells you the infrastructure is OLD, not necessarily that the well is abandoned
"""
        print(f"  Updated notes for slide {i} (Morphology)")

prs.save(PPTX)
print("\nAll changes saved.")
