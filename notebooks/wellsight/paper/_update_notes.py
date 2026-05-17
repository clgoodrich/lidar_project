from pptx import Presentation

PPTX = 'WellSight_Presentation.pptx'
prs = Presentation(PPTX)

# Slide 10: Step 4: Classification & Results
slide10 = prs.slides[10]
slide10.notes_slide.notes_text_frame.text = """STEP 4: CLASSIFICATION & RESULTS

WHAT WE DID
- We took all 628,000 candidate locations from template matching and asked: which ones are real pits?
- For each candidate, we measured 48 different things about the terrain around it (how deep, how round, how rough, etc.)
- We trained 3 different machine learning models to learn the difference between real pits and random terrain
- The 3 models vote together (like a panel of judges) to make a final decision — this is the "ensemble"

HOW WE TESTED IT
- We split the map into geographic zones so the model is always tested on areas it has never seen
- 500m separation between training and test zones prevents the model from "memorizing" nearby terrain
- This is called spatial cross-validation — it gives honest results, not inflated ones

WHAT THE NUMBERS MEAN
- ROC-AUC = 0.905: Think of this as "how good is the model at ranking real pits above false ones?" 0.5 = coin flip, 1.0 = perfect. 0.905 means it does a very good job separating real from fake.
- PR-AUC = 0.212: This looks low but it accounts for how rare pits are. Only 0.37% of candidates are real pits (about 1 in 270). In that context, 0.212 is actually strong.
- At the 0.80 threshold: the model keeps 289 candidates and 85.5% of them are real pits
- At the 0.90 threshold: only 118 candidates remain but 93.2% are real — very high confidence

THE THREE MODELS
- XGBoost, LightGBM, HistGradientBoosting — all are "gradient boosted trees"
- Think of each as a series of simple yes/no questions about the terrain that gradually zoom in on the answer
- Using 3 instead of 1 reduces the chance of any single model's quirks causing errors
- Isotonic calibration: converts raw model scores into actual probabilities (e.g., 0.80 really means ~80% chance)

THE GRAPHIC
- Green circles = pits we annotated by hand (ground truth)
- Colored dots = pits the model found on its own
- Dot color shows confidence: yellow = lower confidence (~0.6), red = high confidence (~1.0)
- Three 400m zoom windows from different parts of the tile
- Where green circles and red dots overlap = the model got it right
"""

# Slide 11: Measured Pit Morphology
slide11 = prs.slides[11]
slide11.notes_slide.notes_text_frame.text = """MEASURED PIT MORPHOLOGY

WHAT THIS SLIDE SHOWS
- We measured the physical shape of 856 real well pits using the 1-meter LiDAR elevation data
- These are actual measurements, not estimates or models — taken directly from the terrain surface
- The cross-section diagram is drawn at TRUE SCALE (no stretching or exaggeration)

WHAT A PIT LOOKS LIKE
- Imagine a shallow bowl pressed into the ground — about knee-deep and as wide as a small room
- Average depth: 0.724 meters (about 2.4 feet, roughly knee height)
- Average diameter: 12.6 meters (about 41 feet, roughly the width of a two-car garage)
- Average volume: 32.4 cubic meters (imagine filling it with water — about 8,500 gallons)
- Inner slope: about 10 degrees (very gentle — you could walk in and out easily)

WHY THE RIMS ARE UNEVEN
- The deepest rim point averages 1.63 m above the pit floor, but the shallowest side averages 0.72 m
- This is because soil erodes unevenly over 100+ years, and the original cellar walls were not perfectly uniform
- Rim symmetry std = 0.698 m means the rim height varies by about 2 feet around the circle
- This asymmetry is actually a useful signature — natural depressions tend to be more symmetric

WHAT IS A "COLLAPSED CELLAR"?
- These pits are NOT the drill hole itself (the wellbore is only 6-12 inches wide)
- A well cellar was a below-grade workspace dug around the wellhead, usually 10-15 feet across
- Workers used it to access valves, connections, and equipment below ground level
- After the well was abandoned, the cellar walls slowly collapsed inward over decades
- The result: a broad, shallow bowl — exactly what we detect in LiDAR

WHY THIS MATTERS FOR DETECTION
- At 0.7m deep, these pits are well above the LiDAR noise floor (about 5-10 cm)
- They are subtle but real — you could walk over one and barely notice it under leaf litter
- The aspect ratio (depth/diameter) is only 0.06 — extremely flat relative to width
- This is why single metrics like slope or curvature alone cannot find them — you need the full 48-feature profile
"""

# Slide 12: Annotation Quality Control
slide12 = prs.slides[12]
slide12.notes_slide.notes_text_frame.text = """ANNOTATION QUALITY CONTROL

WHAT THIS SLIDE SHOWS
- Before training our final model, we checked our own annotations for mistakes
- If bad labels go into training, the model learns the wrong patterns — garbage in, garbage out
- We used math to automatically flag annotations that "look weird" compared to the rest

HOW WE FOUND PROBLEMS
- We measured 11 physical properties for each of our 856 annotated pits (depth, width, slope, volume, etc.)
- Then we asked: which pits are statistical outliers — far from what a "typical" pit looks like?
- Mahalanobis distance is the main tool: it measures how far each pit is from the average pit across ALL dimensions at once
  - Think of it like asking "how weird is this pit compared to all the others?"
  - Score > 5.0 = very unusual, flagged for review
- We also ran 3 other outlier detection algorithms as a cross-check

WHAT WE FOUND
- 90 out of 856 pits (10.5%) were flagged as unusual
- We manually reviewed the top 30 worst offenders and found two categories:
  1. REAL MISTAKES (~half): mis-clicks where we accidentally marked a stream bank, a road edge, or flat ground instead of a pit
  2. UNUSUAL BUT REAL (~half): genuine pits that are just abnormally large, deep, or lopsided — these are fine to keep

COMMON MISTAKE TYPES
- Tiny radius (1-1.5 m): annotation placed on a single noisy pixel, not a real pit — 23 cases
- Extreme slope (>20 degrees): annotation on a steep hillside, not in a depression — 18 cases
- Negative/zero depth: the annotation point is not actually lower than its surroundings — 8 cases
- Extreme volume (>100 cubic meters): probably a borrow pit or natural feature, not a well cellar — 5 cases
- High rim asymmetry: pit is so lopsided it may be an erosion gully, not a circular cellar — 7 cases

WHY THIS STEP MATTERS
- Cleaning the training labels before model training improves the final detection accuracy
- It is standard practice in machine learning: audit your labels before trusting your model
- The 10.5% flag rate is actually reasonable — it means ~90% of our picks were solid
"""

prs.save(PPTX)
print("Updated notes for slides 10, 11, and 12. Saved.")
