# Outline — Execution Roadmap for Terrain Anomaly Detection

This outline is derived from `CLAUDE.md`, which defines the feature-type catalog, derivative toolkit, and validation framework. CLAUDE.md is the specification; this document is the order in which we build it, and why.

---

## Guiding Principles (from CLAUDE.md)

1. **Eleven feature types, eleven output layers.** Pad scars, access roads, borehole collapses, cellar pits, waste pits, tank batteries, spoil piles, canopy disturbance, metallic signatures, drainage disruptions, and (toggled) absence-of-natural-features. Layers are never fused into a single likelihood score. They are analyzed separately so we can learn which feature types are actually detectable and under what conditions.
2. **Invert the labeling logic.** Well records are no longer per-point labels — they are a spatial prior that the feature layers are *validated against* via the association test. The 30–100+ m WPA coordinate error stops being a data quality problem and becomes an expected characteristic of the validation set.
3. **Work on a calibration subarea first.** ~5 km × 5 km in southern Venango or northern Butler County, selected by eye in GIS before any processing. All development, tuning, and first-pass validation happens inside this box. The full mosaic is only touched after detectors are stable.
4. **Each feature type is validated independently** with the same association test and the same positive/negative controls.

---

## What Already Exists (Reused, Not Rebuilt)

From the existing pipeline:

- Stage 1–3 code: LAZ → 1 m bare-earth DEM → mosaic in EPSG:26917
- Existing derivatives: TPI at 5/15/50 m, slope, plan curvature, local relief, roughness
- Merged well layer (`wells_with_features.shp`) with PADEP + USGS, spud dates via nearest-DEP-well join, NLCD land cover, terrain-context bins
- Characterization notebook with the violin plots, Mann-Whitney tables, and decade/land-cover slicing that justify the pivot
- The RF / XGB / FFN comparison framework — kept as the baseline the anomaly approach must beat

From CLAUDE.md, the following derivatives are **new** and must be built:

- Topographic openness (positive and negative) — Yokoyama 2002
- TPI gradient at 15 m scale
- Height Above Nearest Drainage (HAND)
- Ground return intensity raster (with range/scan-angle normalization check)
- Intensity anomaly (local z-score)
- Intensity–scan-angle relationship (where flight-line overlap allows it)
- Single-return fraction
- Canopy Height Model (CHM) from first-return minus bare-earth
- Canopy height anomaly (local z-score)
- Canopy density (fraction of returns above 2 m)
- Ground return point density — quality mask, not a detection feature
- Waveform derivatives (pulse width, echo ratio, rise time) — **conditional** on 3DEP point format 4/5/9/10. Check first; skip if discrete-return only.

---

## Phase 0 — Foundation

Nothing else works until these are in place. All of Phase 0 happens on the calibration subarea.

### 0.1 Select the calibration subarea
- Open the existing `full_dem.tif` and the wells layer in GIS.
- Find a ~5 × 5 km box in southern Venango or northern Butler County that contains:
  - ≥50 GPS-quality post-1990 DEP wells
  - ≥100 WPA-era wells
  - Deciduous forest as dominant NLCD class
  - Mixed Appalachian relief (ridges, hollows, stream valleys — not a floodplain, not a flat ridgetop)
- Save the bounding box as a project constant. Every subsequent step clips to this box.

### 0.2 Inventory the raw LiDAR over the subarea
- Identify which LAZ tiles intersect the subarea.
- **Check point format** on those tiles — this determines whether waveform derivatives are available. Record the answer up front so Phase 2 knows whether Feature Type I can use pulse width / echo ratio / rise time.
- Check whether intensity values in the tiles are range- and scan-angle-normalized by the 3DEP delivery, or whether we need to normalize them ourselves. Check the project metadata before writing normalization code.

### 0.3 Build the quality mask first
- Compute ground return point density over the subarea.
- Mark cells below a density floor as low-confidence. Every downstream detector consults this mask and either suppresses candidates in low-density cells or flags them for lower confidence scoring.
- This is done *before* any feature derivatives because we do not want to waste iteration cycles tuning thresholds against artifacts in interpolation-dominated cells.

### 0.4 Build the new terrain-only derivatives
Order matters — cheaper and more foundational first:

1. Topographic openness (positive and negative)
2. TPI gradient at 15 m scale
3. HAND (requires stream network extraction → hydrologic conditioning of the DEM → distance-to-drainage)

Each one is written as a standalone function that clips to the subarea, then scales to the mosaic later without changes. The scipy-nan-propagation fix from the existing Stage 3 code is preemptively applied to every moving-window operation.

### 0.5 Build the point-cloud-derived derivatives
These require the raw LAZ, not the bare-earth DEM:

1. Canopy Height Model (first-return surface − bare-earth DEM)
2. Canopy height anomaly (local z-score of CHM)
3. Canopy density (fraction of returns above 2 m per cell)
4. Ground return intensity raster (normalized if needed)
5. Intensity anomaly
6. Single-return fraction
7. Intensity–scan-angle relationship (only where flight lines overlap — not every cell will have this)
8. Waveform derivatives — **only if** point format check in 0.2 came back positive

### 0.6 Derivative sanity check
Before any feature detector runs, render every new derivative on a hillshade and spot-check by eye. Confirm:
- No all-NaN layers (regression test for the scipy-nan bug)
- No tile-seam artifacts
- Negative openness lights up roads and stream channels as expected
- CHM shows sensible tree heights in forested areas and near-zero in clearings
- Intensity raster has reasonable dynamic range and isn't dominated by saturation or sensor artifacts

---

## Phase 1 — Feature Detectors (Ordered by Expected Yield)

The feature types are implemented in a sequence designed to get an end-to-end validated detection loop working as early as possible, not to march through A–K alphabetically.

### Priority tier 1 — build these first
These are the highest-signal, lowest-ambiguity detectors. Getting any one of them working end-to-end (detection → association test → positive/negative controls) unblocks the validation framework for everything that follows.

**Feature Type B — Access Roads and Haul Trails.** CLAUDE.md explicitly calls this out as more detectable than pads: larger spatial footprint, strong negative-openness signal, and *connective* (a road fragment points toward the well it served). Negative openness is the single most effective derivative for linear anthropogenic features in forested terrain. Implementation: threshold negative openness, extract centerlines, filter by length / width / linearity, look for parallel positive-openness berms. First detector to build because it exercises the full derivative → candidate polygon → attribute table → validation pipeline with a feature that is genuinely likely to produce signal.

**Feature Type A — Pad Scars.** The canonical target. Compact patches of low slope + low roughness + low relief, embedded in steeper terrain, at mid-slope HAND values. Discriminators against floodplains (low HAND), ridge saddles (symmetric profiles), and strip mine benches (too large, too linear). Optional cut-bank curvature test on the uphill side for higher confidence.

### Priority tier 2 — build after tier 1 association test passes
These are morphologically plausible but individually lower-confidence. They benefit from being co-located with tier 1 candidates, so building them second means the co-location scoring from CLAUDE.md can be applied immediately.

**Feature Type C — Borehole Collapse Depressions.** Fine-scale negative TPI at 5 m, circular geometry, 1–5 m diameter, with an optional spoil-rim annulus test. The hardest part is the 1-meter DEM resolution floor — some true collapses will be below detection. Reported as a known-unknown.

**Feature Type D — Cellar Pits.** Same machinery as C but with a rectangularity filter instead of circularity. Lower confidence than C per CLAUDE.md because the angular-geometry test is harder than the circular one.

**Feature Type H — Canopy Disturbance Signatures.** CHM-based, forest-only, co-location-scored. Extremely useful as a *confirmatory* signal over tier 1 ground-level detections. Independent of the DEM-morphology detectors, so a canopy anomaly over a detected pad scar is strong mutual evidence.

### Priority tier 3 — build after tier 2 proves co-location scoring works
These are inherently contextual — they mean something only in relation to a nearby pad or road candidate.

**Feature Type E — Waste Pits.** Rectangular depressions at 15–50 m scale, located downslope of a pad scar candidate. Co-location with Feature A is the strongest discriminator.

**Feature Type F — Tank Battery Foundations and Containment Berms.** Annular positive-TPI features at 5–15 m diameter, ideally near a pad scar. Must be discriminated from charcoal hearth platforms, which are a known regional false positive.

**Feature Type G — Spoil Piles.** Compact positive-TPI features near a pad scar, with asymmetric cross-section (steep pad-ward, gentle away).

**Feature Type J — Drainage Disruptions.** Flow-accumulation anomalies co-located with road or pad candidates. Inherently dependent on prior detections — it is a supporting indicator, not a primary feature. Only run on slopes > 10° per CLAUDE.md.

### Priority tier 4 — experimental / conditional
These depend on data properties that may or may not be present in our 3DEP delivery and should not block the core pipeline.

**Feature Type I — Metallic Surface Signatures.** Intensity anomaly + intensity–scan-angle correlation + single-return fraction under canopy + (optionally) waveform pulse width. Per CLAUDE.md, this is lower-confidence than morphometric features and is best used as a confirmatory indicator for pad/road candidates. Only worth the effort after the morphometric pipeline is stable.

**Feature Type K — Absence of Expected Natural Features.** Toggle-disabled by default. Implement the scaffolding, keep the flag off, do not use in primary results. Revisit only if the whole primary pipeline produces weak signal on mature-forested hillslopes and the "absence" signal is the only remaining lever.

---

## Phase 2 — Per-Feature Validation

Every feature type's output layer runs through the same validation framework from CLAUDE.md. Do not skip steps, and do not share results across feature types — each layer stands or falls on its own.

### 2.1 Association test (per feature type)
- Count candidate features within search radii of 50 m, 100 m, 150 m, 200 m of each well record.
- Compare against the same counts at an equal number of random locations drawn from the study area under a covariate-matched null (stratify on slope class, HAND bin, and NLCD class to avoid the detector's terrain preference dominating the test).
- Find the radius at which association is strongest. Expectation: GPS wells peak at short radii, WPA wells peak at longer radii consistent with their coordinate error.

### 2.2 Mandatory slicing
Run the association test separately for:
- GPS-quality wells vs WPA-era wells (the coordinate-accuracy gradient)
- Each NLCD land cover class (to find where this feature type is detectable)
- Each terrain-context class (flat / gentle / moderate / steep)
- Each drilling decade (temporal preservation)

A *gradient* across these slices is much more convincing than a single global p-value. The CLAUDE.md physical hypothesis predicts: forest > cropland, recent > WPA-era, moderate slope > flat or steep.

### 2.3 Positive and negative controls
- **Positive control:** GPS-quality DEP wells with known pad locations. If any feature type's detector cannot produce elevated candidate counts near these, the detector's thresholds are wrong — stop and retune before trusting any other result from that detector.
- **Negative control:** well coordinates offset by 500 m in a random direction. Should be indistinguishable from random placement. If it isn't, the null model is miscalibrated.

### 2.4 Go / no-go decision per feature type
After running 2.1–2.3:
- **Association real + controls pass** → detector is kept; its candidates feed into the ranked output.
- **Association weak or controls fail** → detector is documented as a failed detection attempt with the hypothesized reason (resolution floor, preservation failure, regional geology, etc.) and dropped from downstream use. A documented negative is a legitimate research finding and should appear in the writeup.

---

## Phase 3 — Output Product

Per CLAUDE.md, each feature type produces its own GeoPackage layer with:

- Polygon geometry for each candidate
- Feature type identifier (A–K)
- Area
- Mean derivative values contributing to the detection
- Geometric properties (compactness / elongation / rectangularity, per feature type)
- Nearest well distance
- NLCD class at centroid
- Slope class and HAND value at centroid

Layers are stored separately (separate files or separate layers in one GPKG) so they load and render independently in GIS. No fused score layer.

A companion CSV / markdown table summarizes, per feature type: candidate count, association-test p-value at the best radius, best radius, positive-control pass/fail, negative-control pass/fail, notes.

---

## Phase 4 — Scale to Full Mosaic

Only after the calibration subarea produces a stable set of validated detectors:

1. Run each kept detector across the full mosaic. Expect runtime to scale with area; the quality mask from 0.3 will suppress low-density tiles automatically.
2. Re-run the association test on the full-study-area well records with the full candidate set. Do not tune thresholds against the full-area result — thresholds are frozen at the subarea calibration values.
3. Re-run positive and negative controls at full scale.
4. If any detector degrades significantly between subarea and full-mosaic runs, that is a finding — it means that detector is sensitive to terrain or land-cover heterogeneity that the subarea did not represent. Document and adjust.

---

## Phase 5 — Transfer Experiment (Preserved from Earlier Plan)

The pivot does not change the transfer question, it changes *what* transfers. Instead of transferring a pixel-level classifier, we transfer:

1. **Detector parameters.** Are the openness / TPI-gradient / HAND thresholds stable in the transfer region, or do they need retuning for different soil types, relief amplitude, or vegetation regimes?
2. **Feature-type detectability.** Which of the A–K types survive the move? In sandy or wind-reworked terrain, pad scars may degrade faster but cellar pits may persist. The *ranking* of feature types by detectability is itself a scientific result.
3. **Association strength.** Does the wells-cluster-near-candidates effect reproduce in the transfer region for each feature type individually?

Each of these three can fail independently. A clean writeup reports all three.

---

## Phase 6 — Deliverables

- `notebooks/lidar_project_anomaly.ipynb`, modular, with sections mirroring Phase 0 → Phase 4 so the transfer region plugs in by swapping the input DEM and LAZ set
- Eleven per-feature GeoPackage layers (some possibly empty or flagged as failed detections)
- Per-feature validation table (counts, radii, p-values, control results)
- Figures per feature type: detector output on hillshade, association-test curves, per-slice association strength
- Comparison table: old point-based RF/XGB/FFN baseline vs the new per-feature-type association strengths on the same held-out area
- Methods writeup in notebook markdown that makes the pivot rationale explicit — the 57% accuracy is the *motivation*, not something to hide

---

## Immediate Next Actions

1. **Select the calibration subarea in GIS.** Everything else waits on this. Save the bounding box as a constant.
2. **Point-format check** on the LAZ tiles intersecting the subarea. Answer determines whether Feature Type I can use waveform derivatives or has to rely on intensity / single-return / angular dependence only.
3. **Intensity normalization check** — is the 3DEP delivery already range/scan-angle normalized? Record the answer.
4. **Create `notebooks/lidar_project_anomaly.ipynb`** with section stubs for Phases 0–4 and imports mirroring the existing notebooks.
5. **Implement Phase 0.3** (ground return density quality mask) first, before any derivatives.
6. **Implement Phase 0.4** starting with topographic openness — the single highest-value new derivative per CLAUDE.md.
7. **Implement Feature Type B** (access roads) as the first detector. Run its association test and controls end-to-end on the subarea before starting any other feature detector. This validates the whole detection → validation loop on a single signal before branching to ten more.

---

## Known Risks Going In

- **Point format may not support waveform derivatives.** Most area-wide 3DEP collections are discrete-return. Plan for the waveform path to be unavailable and make sure Feature Type I still has a defensible detection approach without pulse width / echo ratio / rise time.
- **Intensity normalization may not be applied in the delivery.** If we have to do range and scan-angle normalization ourselves, this is a non-trivial chunk of Phase 0.5 and should be budgeted as such, not discovered mid-build.
- **HAND computation requires a hydrologically conditioned DEM.** Coverage gaps in the mosaic will cause artifacts in the conditioning. The quality mask from 0.3 and the scipy-nan fix from the existing Stage 3 code both need to be respected.
- **Phase 2 null model is the most consequential methodological choice.** "Do wells cluster near candidates" is only as good as the null. Stratify on slope, HAND, and NLCD. Review at least one point-process reference (inhomogeneous K-function) before locking the test in.
- **Coal mining false positives are everywhere in western PA.** Strip mine benches, subsidence pits, culm banks, and haul roads all produce signals overlapping Feature Types A, B, E, and G. CLAUDE.md calls this out explicitly per feature type, and the subarea selection should ideally avoid the most heavily mined zones for the *calibration* step, even though mining overlap will reappear when scaling to the full mosaic.
- **Charcoal hearth platforms** are a known regional false positive for Feature Type F and are well-documented in the archaeological literature. Build the discriminator into F from day one rather than retrofitting it.
- **Block cross-validation still applies** at the candidate-feature level. Spatial autocorrelation does not disappear just because we are counting candidates instead of classifying pixels.
- **Feature Type K must stay off by default.** The toggle exists in CLAUDE.md for a reason. Do not enable it to pad results.
