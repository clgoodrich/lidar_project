# CLAUDE.md — Orphan Well Terrain Anomaly Detection

## What This Document Is

This is a feature detection guide for a coding agent building a LiDAR-based terrain anomaly detection pipeline targeting orphaned and abandoned oil and gas well sites in western Pennsylvania. The study area covers Appalachian dissected plateau terrain using 2019 USGS 3DEP LiDAR at 1-meter resolution.

Each section describes a **physically distinct feature type** that is associated with historic drilling operations. Each feature type produces its own independent output layer — a map of "here are locations where this specific type of feature was detected." The layers are **never combined into a single likelihood score.** They are viewed, analyzed, and validated separately so that we can understand which feature types are actually detectable and under what conditions.

The pipeline inverts the logic of the earlier (failed) classification phase. Instead of asking "what does the terrain look like at this recorded well coordinate," we ask "where in the terrain are there features consistent with well-site activity, and do those features cluster near well records at rates above chance?" This is robust to the 30–100+ meter coordinate uncertainty in the WPA-era well records because it does not require the recorded coordinate to land on the feature — only that the feature exists somewhere nearby.

**What this document does NOT contain:** Code, implementation details, classifier configurations, or performance benchmarks. It describes what to look for, what it looks like, how to find it, and why it matters. The coding agent decides how to build it.

---

## Study Area Subsetting

The full study area (~19,500 × 21,000 pixels) is too large for iterative development. All work begins on a calibration subarea of approximately 5 km × 5 km, selected to contain:

- At least 50 GPS-quality DEP wells (post-1990) for threshold calibration and validation
- At least 100 WPA-era wells for coordinate-uncertainty testing
- Deciduous forest as dominant land cover
- Representative Appalachian terrain (mixed slopes, stream valleys, ridge-and-hollow topography)

Southern Venango County or northern Butler County are recommended starting points. The exact bounding box should be selected by visual inspection in GIS before any processing begins.

---

## Terrain Derivatives: The Measurement Toolkit

Before describing individual feature types, here is the set of terrain measurements the pipeline should compute from the LiDAR data. Not every derivative is used by every feature type. Each feature type section specifies which derivatives it relies on.

### From the Bare-Earth DEM

These describe the shape of the ground surface.

**Topographic Position Index (TPI)** at three scales — 5m, 15m, and 50m radius. Measures how high or low a pixel is relative to its neighborhood. Negative values are depressions; positive values are local highs. The three scales separate borehole-size features (5m) from pad-size features (15m) from landscape-position features (50m). *Already computed in the existing pipeline.*

**Slope** in degrees. How steep the ground is at each pixel. *Already computed.*

**Plan Curvature.** The rate of change of slope — sensitive to edges, breaks in grade, and the margins of engineered features. *Already computed.*

**Local Relief.** The elevation range within a ~10m radius window. Flat engineered surfaces produce anomalously low relief in otherwise high-relief terrain. *Already computed.*

**Roughness.** Standard deviation of slope within an ~5m radius window. Engineered surfaces are smooth; natural hillslopes are rough. *Already computed.*

**Topographic Openness (positive and negative).** An angular visibility measure computed along eight directions from each pixel. Positive openness highlights ridges, berms, and raised features. Negative openness highlights channels, road cuts, and linear depressions. This is the single most effective derivative for detecting linear anthropogenic features in forested terrain. Based on Yokoyama et al. 2002. *New — not in the existing pipeline.*

**TPI Gradient.** The spatial gradient of the TPI surface at the 15m scale. Magnitude indicates how sharply the terrain transitions from depression to high point. Direction indicates which way the transition faces. This captures the asymmetric cut-and-fill geometry of pad scars that standard TPI averages away. *New.*

**Height Above Nearest Drainage (HAND).** The elevation difference between each pixel and the nearest stream channel. Stratifies the landscape by hydrologic position — wells preferentially occupy mid-slope positions, not ridgetops or valley bottoms. Used to condition detection thresholds on landscape context (a "flat" patch means different things on a floodplain versus a hillslope). PDAL and WhiteboxTools both support computing this. *New.*

### From the Raw Point Cloud (All Returns)

These describe the physical properties of the laser return signal and the vegetation structure above the ground. They require working with the full point cloud, not just ground-classified returns.

**Ground Return Intensity.** The strength of the reflected laser pulse at ground level, gridded to a raster. Different surface materials reflect the 1064nm laser wavelength differently. This enables material discrimination at each pixel. Requires range and scan-angle normalization before gridding if the 3DEP delivery does not include pre-normalized intensity (check the project metadata). *New.*

**Intensity Anomaly.** A local z-score of ground return intensity — how different is each pixel's intensity from its spatial neighborhood? Flags pixels whose reflectance is statistically unusual compared to surrounding terrain, regardless of absolute intensity value. *New.*

**Intensity–Scan Angle Relationship.** Where overlapping flight lines observe the same ground from different angles, the relationship between intensity and viewing angle reveals surface material properties. Diffuse surfaces (soil, vegetation) reflect equally in all directions — no angle dependence. Specular surfaces (metal, water, smooth rock) reflect strongly toward the sensor at near-vertical angles and weakly at oblique angles — strong angle dependence. This is essentially a per-pixel material fingerprint. *New.*

**Single-Return Fraction.** In forested areas, ground returns are normally the last of multiple returns per pulse (the laser penetrated the canopy layer by layer). A cluster of ground-level returns that are the *only* return from their pulse indicates either a canopy gap directly above or a surface so reflective that it captured all the pulse energy at once. Either is informative for well-site detection. *New.*

**Canopy Height Model (CHM).** The difference between a first-return surface model (treetop heights) and the bare-earth DEM. Gives tree height at every pixel. Anomalously low canopy height in a forested area flags disturbance, contamination, or maintained clearings. *New.*

**Canopy Height Anomaly.** A local z-score of the CHM. Identifies patches where vegetation height is anomalously low (or high) relative to the local forest context. More powerful than raw CHM because it normalizes for landscape-scale vegetation gradients. *New.*

**Canopy Density.** The fraction of returns from above 2m height versus total returns per grid cell. Captures horizontal canopy coverage, which differs from canopy height — a site might have short but dense regrowth (moderate CHM, high density) versus sparse contamination-stunted trees (moderate CHM, low density). *New.*

**Ground Return Point Density.** The number of ground-classified returns per grid cell. This is not a detection feature — it is a **quality mask.** Areas with very few ground returns have unreliable DEM values because the surface is interpolated rather than measured. All other derivatives are less trustworthy in low-density areas. The pipeline should flag (and optionally exclude) low-density cells from candidate feature generation. *New.*

**Waveform Derivatives (conditional — full waveform data only).** If the 3DEP point records include waveform packet data (point format 4, 5, 9, or 10), three additional derivatives become available:

- **Pulse Width (FWHM):** Hard, smooth surfaces (metal, rock) produce narrow return pulses. Rough, porous surfaces (soil, litter) produce broad return pulses. Compacted engineered surfaces (roads, graded pads) produce intermediate pulse widths.
- **Echo Ratio:** The fraction of return energy in the detected peak versus total waveform energy. Clean ground hits produce high echo ratio; partially occluded or mixed returns produce low echo ratio.
- **Rise Time:** Time from 10% to 90% of peak amplitude on the return pulse leading edge. Specular surfaces (metal) produce very fast rise times; rough diffuse surfaces produce slower ones.

If waveform data is not available (likely — most 3DEP area-wide collections are discrete-return), these three derivatives are skipped. The rest of the pipeline proceeds without them. Check the point format of the LAZ files before investing effort here.

---

## Feature Type Catalog

Each feature type below describes a physically real thing that exists (or once existed) at a well site, explains what it looks like in the LiDAR derivatives, and specifies what geometric or contextual properties distinguish it from natural terrain features and from other anthropogenic features (especially coal mining, which is everywhere in western PA).

Every feature type produces its own output layer. The output is a set of candidate locations (polygons or points) with attributes describing the detection confidence and the derivative values that triggered the detection.

---

### Feature Type A: Pad Scars

#### What it is in the real world

Every drilled well required a cleared, leveled pad for the derrick and equipment. For conventional wells in western PA, this meant cutting into a hillslope and pushing the spoil downhill to create a flat working area. Pad dimensions ranged from roughly 8×8 meters for early (1860s–1890s) cable-tool rigs to 20×30 meters for mid-twentieth-century rotary rigs.

The grading creates two distinct landforms that age differently:

- **The cut bank** on the uphill side, where the operator carved into the natural slope. This exposes bedrock or compacted subsoil, which erodes slowly. Cut banks remain steep and well-defined for decades to centuries.
- **The fill slope** on the downhill side, where the excavated material was pushed. This is unconsolidated spoil — it erodes faster, slumps under gravity, and develops a convex-to-concave profile over time.

Between the cut bank and the fill slope, the pad surface itself is compacted and graded flat. Even after 100+ years of abandonment and full reforestation, the compaction difference persists — the pad surface doesn't regrade to match the natural hillslope because the subsoil was mechanically compacted during construction.

In agricultural land, pad scars soften much faster because tillage redistributes the cut-and-fill geometry. But the compaction anomaly can still persist through decades of plowing as a subtle elevation difference.

#### What it looks like in LiDAR

- **Low slope** on the pad surface, embedded within steeper surrounding terrain
- **Low roughness** on the pad surface
- **Low local relief** on the pad surface
- **High curvature** at the cut bank (sharp concave break in slope) and at the fill edge (sharp convex break)
- **Asymmetric TPI:** negative on the uphill cut side, positive on the downhill fill side, with near-zero on the flat pad between them. Standard TPI at a single scale may average across this dipole and cancel to zero — the TPI gradient captures the asymmetry.
- **TPI gradient direction** aligned with local hillslope aspect, because the cut is always uphill and the fill is always downhill

#### What distinguishes it from natural features

- **Floodplain flats** are also low-slope, low-roughness, low-relief — but they occur at low HAND values (near stream level) and lack cut banks. Pad scars occur at mid-slope HAND values.
- **Ridge saddles** are flat but occur at high landscape positions with steep drops on both sides. Pad scars have asymmetric profiles (steep only on the uphill side).
- **Strip mine benches** are flat, engineered, and terraced — but they are typically much larger than well pads (hundreds of meters long) and occur in linear sequences along contour. Pad scars are compact, isolated features.

#### Detection approach

Identify contiguous patches of low slope + low roughness + low relief. Filter by size (plausible pad dimensions), shape (reasonably compact — not elongated like a road or mine bench), and landscape position (mid-slope, not valley floor or ridgetop). Optionally test for cut-bank curvature signature on the uphill side.

---

### Feature Type B: Access Roads and Haul Trails

#### What it is in the real world

Every well needed a road. In the 1860s–1890s, that meant a wagon trail cut into the hillside. In the 1900s–1950s, it meant a graded road for trucks. These roads are linear cut-and-fill features that follow contours or traverse ridges at controlled grades.

Abandoned roads are among the **most persistent** anthropogenic features in forested Appalachian terrain for three reasons:

1. Road beds are heavily compacted. The subgrade resists revegetation, doesn't infiltrate water normally, and holds its grade for decades.
2. Road cuts into hillslopes expose bedrock or hardpan that erodes at a much slower rate than the surrounding soil mantle.
3. Many abandoned well-access roads were also used for timber hauling, pipeline access, or general farm access, meaning they were maintained for years after the well was abandoned — extending their physical persistence.

Roads are typically 2–4 meters wide for single-track trails, 4–6 meters for two-track roads. They may extend hundreds of meters from a public road to the well pad, and they often connect multiple well pads in a network.

Roads are more useful for detection than pads for two reasons. First, they are spatially larger — a 3-meter-wide road running 200 meters is 600 m² of detectable feature versus a 15×15m pad at 225 m². Second, they are **connective** — detecting a road fragment gives you a vector to follow toward the well it served.

#### What it looks like in LiDAR

- **Linear feature of anomalously low slope** traversing otherwise steep hillslopes
- **Strong signal in negative openness** — the road cut sits below adjacent terrain, creating a linear channel visible in the negative openness raster
- **Parallel berms** in positive openness — upcast from road cut maintenance creates low ridges on one or both sides of the road bed
- **Low roughness** along the road bed versus surrounding terrain

#### What distinguishes it from natural features

- **Stream channels** are also linear concavities, but they have high flow accumulation values and V-shaped cross-sections. Road cuts have flat bottoms and occur at positions on the hillslope that don't align with natural drainage.
- **Natural benches** (structural geology) can produce linear low-slope features, but they lack the parallel berm signature and tend to be wider and less geometrically regular.
- **Pipeline corridors** look very similar to roads in LiDAR. In western PA, where pipeline and well infrastructure coexist, a detected linear feature could be either. This is acceptable — pipeline corridors are often co-located with well access roads, and both indicate industrial activity.

#### Detection approach

Apply a threshold to negative openness to identify linear concavities. Extract centerlines. Filter by length (> 30m), width (2–6m), and linearity (the feature should be more line-like than blob-like). Look for parallel positive-openness features (berms) flanking the detected concavity.

---

### Feature Type C: Borehole Collapse Depressions

#### What it is in the real world

When a well is abandoned, the steel casing remains in the ground. Over 40–80 years (depending on wall thickness and soil chemistry), the casing corrodes. As it loses structural integrity, the annular fill material — cement in later wells, packed clay or soil in earlier ones — loses support and subsides unevenly into the void. The surface expression is a small, roughly circular depression.

Typical dimensions:

- 1–3 meters in diameter
- 0.3–1.5 meters deep (subsiding material reaches a natural angle of repose)
- Often slightly off-center from the original borehole, because corrosion is faster on the downhill side where water accumulates

A **spoil rim** frequently surrounds the depression. When the well was originally drilled, excavated material from the cellar pit was piled around the casing collar. This annular berm of compacted drilling waste persists longer than loose soil because of its composition. It creates a raised ring 0.2–0.5 meters high and 3–5 meters in diameter around the depression.

These features are more likely to survive over time than pad scars because vegetation cannot infill a physical void — leaf litter and sediment accumulate slowly, and the subsidence may be ongoing as the casing continues to deteriorate.

#### What it looks like in LiDAR

- **Localized negative TPI at 5m scale** — a small depression surrounded by higher ground
- **Approximately circular geometry** — distinguishes it from linear erosion features
- **Spoil rim visible as a ring of positive TPI** in a 3–8m annulus surrounding the depression
- **High curvature at the rim** — concentric pattern of positive curvature (convex outer rim edge) and negative curvature (concave inner rim edge)

#### What distinguishes it from natural features

- **Tree throws** (root-pit-and-mound topography) produce depressions of similar size but with an adjacent mound on one side (the root plate), creating an asymmetric signature. Borehole collapses are roughly symmetric.
- **Karst sinkholes** can look identical in cross-section but tend to be larger (5–20m), and western PA's geology produces fewer karst features than central PA's limestone belt. Still a potential false positive in areas with carbonate bedrock.
- **Animal burrows** (groundhog holes are common in PA) are too small (< 0.5m) to resolve in 1-meter LiDAR.
- **Coal mine subsidence** produces depressions but typically over larger areas (10–50m+) and in elongated patterns following the mine geometry.

#### Detection approach

Find local minima in TPI at the 5m scale. Filter by size (1–5m diameter), depth (> 0.2m below the local surface), and circularity. Bonus confidence if a ring of positive TPI exists in a surrounding annulus (spoil rim test). Exclude locations on mapped stream channels (high flow accumulation).

---

### Feature Type D: Cellar Pits

#### What it is in the real world

Many pre-1920 wells had a **cellar** — a rectangular or square pit dug around the wellhead to house the casing head, valves, and sometimes a pump jack foundation. Typical dimensions: 2×2 to 3×4 meters, 1–2 meters deep.

When the well was abandoned, the cellar was sometimes backfilled, sometimes not.

**Unfilled cellars are essentially permanent features.** They are too deep and steep-sided to fill naturally with leaf litter and sediment on any human timescale. There are documented open cellar pits from 1860s-era wells in Venango County that are still open voids 160 years later.

**Backfilled cellars** compact and subside over time, producing a subtle depression similar to a borehole collapse but larger and — critically — **rectangular or square** rather than circular.

#### What it looks like in LiDAR

- **Rectangular or square depression** in TPI at the 5m–15m scale
- **Steep, angular walls** visible as high curvature at the pit edges (sharper than natural depressions, which tend to have rounded profiles)
- **Flat bottom** if the pit is open (low slope within the depression)
- **Rectilinear geometry** — the key discriminator. Natural depressions are circular, elliptical, or irregular. Cellars are angular.

#### What distinguishes it from natural features

- **Tree throws** are asymmetric, not rectilinear.
- **Animal dens** are too small.
- **Foundation remnants from other structures** (farmhouses, barns) produce similar rectangular depressions but are typically larger (> 5m per side) and occur near road networks and other settlement features, not isolated on hillslopes.

#### Detection approach

Similar to borehole collapse detection but with a rectangularity filter instead of a circularity filter. The oriented bounding box of the detected depression should be a close fit (high fill ratio) and have roughly right-angle corners. This is a harder geometric discrimination than circularity — expect more false positives and consider this a lower-confidence feature type.

---

### Feature Type E: Earthen Impoundments and Waste Pits

#### What it is in the real world

Pre-regulation wells (before Pennsylvania's 1984 Oil and Gas Act, and realistically most wells before the 1970s) used open earthen pits for produced water, drilling mud, and crude oil storage. These were rectangular excavations, typically 5–15 meters on a side, 1–3 meters deep, often unlined. They were located downhill from the pad because gravity is free.

When abandoned, these pits accumulated water, sediment, and vegetation. The contamination legacy means the soil chemistry in and around the pit is different from the surrounding landscape — hydrocarbon residues, elevated salinity from produced water, and heavy metals from drilling mud. This affects vegetation growth (often stunted or dominated by different species) and potentially soil reflectance properties.

#### What it looks like in LiDAR

- **Rectangular flat-bottomed depression** in TPI at the 15m–50m scale, larger than cellar pits
- **Located downslope of a pad scar candidate** — the spatial relationship is diagnostic. An isolated rectangular depression could be many things; one within 30–50m downhill of a detected pad scar is strongly suggestive.
- **Vegetation anomaly** visible in the CHM: younger, shorter, or absent vegetation within the pit footprint compared to surrounding forest, due to contaminated soil
- **Potential intensity anomaly** if contaminated soil has different reflectance properties than surrounding soil (hydrocarbon contamination can suppress reflectance at 1064nm)

#### What distinguishes it from natural features

- **Farm ponds** are similar in size but typically circular or irregular, not rectangular, and are located in valley positions where water naturally collects.
- **Strip mine cuts** are larger and linear.
- **The spatial relationship to a pad scar** is the strongest discriminator. If a rectangular depression is found near a detected pad scar, on the downhill side, that's a well-site waste pit until proven otherwise.

#### Detection approach

Identify rectangular depressions at the 15m–50m scale. Score higher if the feature is within 50m downslope of a Feature Type A (pad scar) candidate. Check for anomalous CHM or canopy density within the depression footprint.

---

### Feature Type F: Tank Battery Foundations and Containment Berms

#### What it is in the real world

Storage tanks sat on prepared foundations — leveled earth pads or concrete/stone piers. The tanks are long gone (scrapped for metal value within years of abandonment), but the foundations persist as small flat platforms.

More detectable than the foundations themselves are the **containment berms** — low earthen rings built around tank footprints to contain spills. These are 0.3–0.5 meters high, 1–2 meters wide, forming a ring 5–10 meters in diameter. They are compacted earth and persist for decades to centuries.

Containment berms are nearly impossible to detect in aerial photography under forest canopy, but they are clearly visible in a high-quality bare-earth DEM.

#### What it looks like in LiDAR

- **Small, very flat circular or rectangular platform** — 3–5 meters across, slightly elevated above surrounding grade
- **Annular ring of positive TPI** at the 5m–15m scale (the containment berm)
- **Concentric curvature pattern** — positive curvature (convex) on the outer berm edge, negative curvature (concave) on the inner edge
- **Located near a pad scar candidate** — tank batteries were part of the well-site complex, typically within 20–50m of the wellhead

#### What distinguishes it from natural features

- **Spoil rings around borehole collapses** (Feature Type C) are similar but smaller (3–5m diameter versus 5–10m for tank berms).
- **Charcoal hearth platforms** — historic charcoal production in PA used circular platforms 8–12m in diameter. These are well-documented in the archaeological literature and are a known false positive for LiDAR-based feature detection. They lack the containment berm (raised ring) and tend to be slightly concave (hearth depression) rather than flat or convex.

#### Detection approach

Detect annular features in the TPI and curvature rasters — rings of positive TPI or concentric curvature patterns at 5–15m diameter. Filter by the presence of a flat or slightly elevated interior. Score higher if the feature is near a detected pad scar.

---

### Feature Type G: Spoil Piles and Drill Cuttings

#### What it is in the real world

Drilling produces rock cuttings that were piled adjacent to the pad. Pre-regulation practice was to dump them in the nearest convenient spot. These piles are:

- 1–3 meters tall, 5–15 meters across
- **Asymmetric in profile** — steep on the side facing the pad (short dump distance) and gentler on the far side (material rolled or slumped downhill)
- Partially revegetated but with distinct vegetation character due to the rock-dominated substrate (poor soil, different drainage, different nutrient availability)

Spoil piles are extremely persistent because the material is coarse rock fragments, not fine soil. They don't erode or regrade significantly over centuries.

#### What it looks like in LiDAR

- **Positive TPI anomaly** at the 5m–15m scale — a local high surrounded by lower terrain
- **High roughness** — the rock surface is irregular compared to soil
- **Asymmetric cross-section** visible in the TPI gradient (steep side toward the pad, gentle side away)
- **Located within 20–30m of a pad scar candidate**, on the downhill or cross-slope side

#### What distinguishes it from natural features

- **Rock outcrops** produce positive TPI and high roughness but are typically elongated along bedding planes rather than compact mounds.
- **Anthills and termite mounds** are too small (< 1m) for 1-meter LiDAR.
- **Coal mine waste (culm banks)** are similar but much larger (tens of meters high) and occur near mine portals, not in isolation on hillslopes.

#### Detection approach

Identify compact positive-TPI features at the 5m–15m scale. Filter by size and asymmetry of cross-section. Score higher if located near a detected pad scar.

---

### Feature Type H: Canopy Disturbance Signatures

#### What it is in the real world

When a well pad was cleared for drilling, the vegetation was removed over an area larger than the pad itself — typically extending 10–20m beyond the pad edge to accommodate equipment staging, material storage, and fire safety clearance. When the site was abandoned, this cleared area revegetated. But the regrowth differs from the surrounding undisturbed forest in several ways:

- **Even-aged stand** — all trees colonized the cleared area at roughly the same time, producing uniform canopy height. Undisturbed forest has mixed-age structure with variable canopy height.
- **Different species composition** — pioneer species (black cherry, red maple, tulip poplar in PA) colonize clearings faster than climax species (oak, hickory, beech). The canopy 60–100 years later still reflects this successional difference.
- **Lower canopy height** than surrounding old-growth or mature second-growth forest, because the regrowth has had less time to mature.
- **At sites with ongoing contamination** (leaking casings, seeping waste pits), vegetation may be stunted, absent, or dominated by contaminant-tolerant species. These create persistent canopy gaps.

#### What it looks like in LiDAR

- **Anomalously low CHM** relative to surrounding forest — a patch of 10–20m canopy in a landscape of 25–35m canopy
- **Low canopy height anomaly** (negative z-score) in the local-context-normalized CHM
- **Anomalous canopy density** — either low (contamination-related gaps) or unusually uniform (even-aged regrowth lacks the structural diversity of natural forest)
- **Spatial coincidence with ground-level features** — a canopy anomaly directly above a detected pad scar or road is strongly confirmatory

#### What distinguishes it from natural features

- **Natural canopy gaps** (individual treefalls, storm damage) are small (< 100 m²) and randomly distributed. Well-related canopy disturbance is larger (200–2000 m²) and spatially associated with ground-level features.
- **Recent timber harvest** produces large areas of low/absent canopy but these are typically much larger (hectares) and occur in geometric boundaries (property lines, timber sale boundaries).
- **Utility corridors** (power lines, maintained pipelines) create linear canopy gaps that persist indefinitely due to ongoing maintenance. Well-access roads also produce linear canopy effects but with older, taller vegetation (not maintained).

#### Detection approach

Identify patches of anomalously low CHM in forested areas (NLCD classes 41, 42, 43). Filter by size (plausible well-clearing footprint, 200–5000 m²). Score higher if spatially coincident with ground-level feature candidates (pad scars, roads). Ignore in non-forested areas (pasture, developed) where low CHM is the normal condition.

---

### Feature Type I: Metallic Surface Signatures

#### What it is in the real world

Abandoned well sites often have metallic debris: casing stubs, valve bodies, collapsed derrick members, pipe fittings, tank remnants, cable tool bits, and miscellaneous hardware. Most surface metal at sites abandoned 60–160 years ago is heavily corroded, but thick-walled items (casing heads, large valve bodies) may still have exposed metallic surfaces, and partially buried items may be protected from oxidation.

This feature type is **not about detecting the shape** of metal objects (they're generally too small to resolve in the DEM). It is about detecting the **material properties** of metal through how it interacts with the LiDAR pulse.

#### How metal interacts with the LiDAR pulse (and why it matters)

The 3DEP LiDAR systems operate at 1064nm (near-infrared). At this wavelength:

**Soil and rock** are **diffuse reflectors.** They scatter the incoming pulse in all directions roughly equally, regardless of the angle the laser hits them. The return signal is moderate in strength (20–40% reflectance for soil), produces a broad return pulse shape, and — critically — does not change significantly when viewed from different angles.

**Metal** is a **specular reflector.** It behaves like a mirror. The consequences are dramatically different from soil:

- At **near-vertical incidence** (pulse coming straight down), the reflection bounces directly back to the sensor. Return intensity is extremely high — potentially 3–10× higher than surrounding terrain — because nearly all reflected energy is concentrated in one direction rather than scattered.
- At **oblique incidence** (pulse coming from an angle), the reflection bounces *away* from the sensor. Return intensity drops dramatically or the pulse produces no detectable return at all.
- The return pulse shape is **narrow and sharp** (no volume scattering, no surface roughness at the laser wavelength), distinct from the broader, lower pulse shape from soil.
- Metal **always produces a single return** per pulse. There is no partial penetration, no multiple returns. In a forested area where ground returns are typically the last of 2–5 returns per pulse, a cluster of single-return points at ground level is anomalous.

**Corroded metal** is intermediate. Iron oxide (rust) at 1064nm is a moderate absorber, which means heavily corroded surfaces may actually have *lower* intensity than surrounding soil. The surface roughness of the corrosion layer partially diffuses the reflection, weakening the angle-dependent signature. A surface with mixed clean metal and rust produces a mixed signal — partly specular, partly diffuse.

#### What it looks like in LiDAR

- **Intensity anomaly:** individual pixels or small clusters with intensity values far outside the local distribution — either extremely high (clean metal at favorable angle) or extremely low (corroded metal or metal at unfavorable angle)
- **Intensity–scan angle correlation:** where overlapping flight lines image the same point from different angles, specular surfaces show strong angle-dependent intensity variation. Soil does not. A negative correlation between intensity and scan angle at a given location is a material fingerprint for specular reflectance.
- **Elevated single-return fraction under forest canopy:** clusters of ground-level points that are disproportionately the only return from their pulse, indicating a surface that reflected all the energy at once
- **Narrow pulse width** (if full waveform data is available): metal returns have distinctively low pulse width compared to soil returns

#### What distinguishes it from other features

- **Standing water** is also specular at 1064nm and produces similar intensity and angular signatures. Water occurs in topographic lows (depressions, channels); metal debris occurs on flat or elevated surfaces.
- **Exposed rock faces** can produce high-intensity returns but are diffuse, not specular — they lack the angle-dependent signature.
- **Sensor artifacts** (intensity spikes from multipath or near-range saturation) can mimic high-intensity anomalies but are typically isolated single points without spatial coherence. Genuine metal debris produces clusters.

#### Detection approach

Compute the intensity anomaly raster. Identify clusters of anomalous pixels (both high and low tails of the intensity distribution). Where overlapping flight line coverage exists, compute the intensity–scan angle relationship and flag locations with strong angular dependence. Compute single-return fraction at ground level and flag clusters with elevated values under forest canopy. Combine: a location with an intensity anomaly AND angular dependence AND elevated single-return fraction is a high-confidence metallic surface candidate.

#### Realistic expectations

Individual small objects (a single pipe fitting, a short length of cable) are generally below the detection threshold because their metallic surface area is a small fraction of the 1m² grid cell, and the intensity contribution is averaged with surrounding soil. Detection requires a **debris field** — multiple pieces of metal scattered across an area of at least 5–10 m². A collapsed derrick is the most detectable scenario; a single casing stub in dense vegetation is the least.

Corrosion after 60–160 years significantly degrades the specular signature. This feature type should be treated as **lower confidence** than morphometric features (pad scars, roads, depressions) and is most useful as a **confirmatory indicator** — if a metallic intensity signature spatially coincides with a pad scar or road candidate, that strengthens both detections.

---

### Feature Type J: Drainage Disruptions

#### What it is in the real world

Well pads disrupt natural drainage. The graded surface diverts water, the compacted soil prevents infiltration, and the cut-and-fill geometry creates new flow paths. Over decades, this produces:

- **Gullies** at the downhill edge of the fill slope, where concentrated runoff from the impervious pad surface incises into unconsolidated fill material
- **Headcuts** where diverted drainage meets natural channels at an unexpected elevation
- **Ponding areas** above the cut bank where the road or pad intercepts subsurface flow

These are secondary features — they result from the primary anthropogenic modification (the pad or road) interacting with natural hillslope hydrology over time. They are subtle, but they occur in predictable locations relative to the primary feature.

#### What it looks like in LiDAR

- **Anomalous flow accumulation** — concentrated flow at locations on the hillslope that don't align with the natural drainage network
- **Gully incisions** visible as narrow, high-curvature linear depressions at the downhill edge of flat areas (pad fill slopes)
- **Ponding indicators** — small flat areas with low HAND values uphill of road cuts or pad cut banks, where intercepted subsurface flow creates wet areas

#### What distinguishes it from natural features

- **Natural gullies** form where overland flow naturally concentrates — in convergent topography, at slope breaks, and in areas with erodible soils. Pad-edge gullies form at the artificial slope break created by the fill edge, in a location where the natural topography does not predict concentrated flow.
- **Headcuts in natural channels** occur at knickpoints in the stream profile. Anthropogenic headcuts occur where diverted flow enters a channel at an elevation above the natural stream grade.

#### Detection approach

Compute flow accumulation from the hydrologically conditioned DEM. Identify locations where flow accumulation is anomalously high for the local topographic context. Focus on flow anomalies that occur within 100m of a detected pad scar or road candidate and on slopes > 10° (flat-terrain drainage anomalies are common and not diagnostic). This feature type is inherently dependent on other detections and is best used as a supporting indicator, not a primary one.

---

### Feature Type K: Absence of Expected Natural Features (Toggle-Controlled)

> **This feature type is disabled by default.** It can be enabled via a pipeline configuration toggle. When disabled, it produces no output layer and does not influence any other feature type's detection.

#### What it is

This is an inversion of the other feature types. Instead of looking for anomalous *presence* of engineered features, it looks for anomalous *absence* of expected natural features at a location — specifically, the absence of natural surface roughness, natural drainage patterns, and natural vegetation structure in an area where these would normally be present given the terrain context.

The reasoning is that well-pad construction fundamentally alters the ground surface in ways that prevent the normal expression of natural geomorphic processes. A 100-year-old pad site may no longer have a clearly detectable cut-and-fill signature, but it may still lack the normal surface texture, drainage development, and vegetation heterogeneity that would have developed on a natural hillslope of the same gradient, aspect, and lithology.

#### What "absence" looks like

- **Anomalously low roughness** relative to what is predicted for the local slope context. Natural Appalachian hillslopes of 15–25° develop characteristic roughness from soil creep, tree throw, and weathering. A patch of the same slope with significantly lower roughness suggests a modified or engineered surface.
- **Anomalously uniform canopy** in an area where mixed-age, mixed-species forest would be expected. Even-aged regrowth produces canopy height uniformity that natural forest does not.
- **Subdued drainage development.** On natural slopes, the DEM shows fine-scale convergent flow paths and incipient channel heads. On compacted, engineered surfaces, drainage development is suppressed — the surface is "smoother" hydrologically than it should be.

#### Why this is toggleable

Absence of a feature is inherently less diagnostic than presence of a feature. Every "absence" detection is an argument from expectation — "this surface should be rougher / more varied / more dissected than it is." That expectation depends on a model of what "normal" looks like, and that model is only as good as the local reference data it's calibrated against. Errors in the reference model produce false positives.

Additionally, there are many non-well reasons a surface might be smoother or less developed than expected: landslide deposits, colluvial aprons, deep soil over weathered bedrock, agricultural history, and simply being on the young end of normal geomorphic variability.

This feature type is included because in some terrain contexts (steep, mature-forested hillslopes with well-developed drainage), the absence signal may be the *only* remaining signature of a well site where all primary features have been eroded or obscured. But it should not be used by default, and when enabled, its candidates should be interpreted with lower confidence than primary feature types.

#### Detection approach

For each pixel, compute the expected roughness, canopy variability, and drainage density based on its slope, aspect, HAND, and NLCD land cover class (using the calibration subarea's background distribution as the reference). Flag pixels that fall significantly below the expected values for their context. Cluster flagged pixels into patches and filter by size and landscape position.

---

## Spatial Association Validation

Each feature type's output layer is validated independently using the same statistical framework.

The test asks: **do candidate features of this type occur near documented well locations at a rate significantly above chance?**

The procedure compares the number of candidate features found within a search radius of well records against the number found within the same-sized search areas placed at random locations across the study area. If wells consistently have more nearby candidates than random locations, the feature type has a real spatial association with wells. If not, the feature type is either not detectable at this resolution, not preserved in this landscape, or the detection thresholds are poorly calibrated.

Search radii should be tested at 50m, 100m, 150m, and 200m to find the scale at which association is strongest.

The test should be run separately for:

- GPS-quality wells versus WPA-era wells (to quantify the impact of coordinate accuracy)
- Each land cover class (to identify where detection works best)
- Each terrain context class (flat, gentle, moderate, steep)
- Each drilling decade (to identify temporal trends in feature preservation)

**Positive control:** GPS-quality wells with known pad locations. If the pipeline cannot find elevated feature counts near these, something is wrong with the detection thresholds.

**Negative control:** Well coordinates offset by 500m in a random direction. These should produce results indistinguishable from random placement.

---

## Output Specification

Each feature type produces its own output layer as a GeoPackage containing:

- **Geometry:** polygon for each candidate feature (the contiguous patch of pixels that met the detection criteria)
- **Feature type:** which of the labeled feature types (A through K) this candidate represents
- **Area:** in square meters
- **Derivative values:** the mean value of each contributing derivative within the candidate polygon
- **Geometric properties:** compactness, elongation, rectangularity (as applicable to the feature type)
- **Nearest well distance:** distance to the nearest documented well record (for association analysis)
- **Land cover:** NLCD class at the candidate centroid
- **Terrain context:** slope class and HAND value at the candidate centroid

The layers are **separate files or separate layers within a single GeoPackage** so that each feature type can be loaded, visualized, and analyzed independently.
