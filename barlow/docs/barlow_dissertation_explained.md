# Barlow 2026 Dissertation — Explained Like You're 16

A walkthrough of Mary Camille Barlow's PhD dissertation, written so a curious teenager can follow it cover-to-cover.

**Citation:** Barlow, M. C. (2026). *A Comprehensive Spatial Analysis of Stream Boundary and Geomorphological Change Detection: McMurdo Dry Valleys, Antarctica.* PhD Dissertation, Department of Civil and Environmental Engineering, University of Houston. Committee chair: Dr. Craig L. Glennie. 240 pages.

---

## The one-sentence version

She trained an AI to outline the temporary streams that turn on each summer in an Antarctic desert, proved that free satellite elevation maps are accurate enough to trust, and used the outlines as a stencil to measure how the landscape has been quietly reshaping itself over two decades — turning what used to be a hand-mapped, one-stream-at-a-time job into a valley-wide climate-change monitor.

---

## Part 1 — The Setting

### What's the McMurdo Dry Valleys?

The **McMurdo Dry Valleys (MDVs)** are a strip of Antarctica that, weirdly, is **not** covered in ice. They're a *polar desert* — hyper-arid (almost no precipitation), bitter cold, mostly bare rock and gravel. They look like Mars. NASA literally uses them as a Mars analog.

Three major valleys plus a few smaller regions:
- **Taylor Valley** — the most-studied one, runs from inland glaciers down to the coast.
- **Wright Valley**
- **Victoria Valley** (plus Barwick)
- **Denton Hills** — a smaller upland area that turns out to be the most "active" in this study

The valleys were first explored scientifically by Captain Scott's *Discovery* expedition in 1903. For most of the last century they've been considered **the most geomorphologically stable place on Earth** — meaning the shape of the ground basically doesn't change.

### Why anyone cares

Two things have started happening in the last 20-ish years:

1. **Glacial melt is going up.** Even tiny shifts in solar absorption in this environment matter a lot because the system is *energy-limited* — it doesn't need more water, just slightly more heat, for ice to melt.
2. **Permafrost is degrading.** When permanently frozen ground starts to thaw, the soil it was holding together becomes mobile.

When these two combine, you get **ephemeral streams** — temporary rivers that flow only for a few weeks each summer when the glaciers melt. They flow, they pick up sediment, they reshape the channel, then they vanish until next year.

These streams are a big deal because they're the most sensitive measurable indicator of climate change in the most stable region on Earth. If the MDVs are speeding up, that's a canary-in-the-coal-mine signal for the whole continent.

### The problem Barlow is solving

Up to now, MDV scientists have studied streams **one at a time** — pick a single stream, survey it with ground equipment, come back in a few years, survey it again, repeat. That's:

- Slow
- Doesn't scale to all 100+ streams in the region
- Misses the **regional picture** (is the whole valley speeding up, or just one stream?)
- Only catches the streams someone already knew about

Barlow wants to do it **automatically, across all the valleys, over multiple time periods.** That requires three separate breakthroughs, which become the three big chapters of her dissertation.

---

## Part 2 — The Toolkit

Before getting into what she did, here are the four key tools used throughout:

### LiDAR (Light Detection and Ranging)

A plane (in this case operated by the National Center for Airborne Laser Mapping, NCALM) flies over the valleys and fires millions of laser pulses per second at the ground. The time each pulse takes to bounce back tells you the elevation of that spot to within a few centimeters. Result: a point cloud of millions of (x, y, z) measurements, which can be turned into a **Digital Elevation Model (DEM)** — basically a really detailed topographic map.

The MDVs have airborne lidar from **2001** and **2014**. Gold-standard accuracy.

### REMA (Reference Elevation Model of Antarctica)

A massive open dataset of satellite-derived elevation maps for all of Antarctica, made by the Polar Geospatial Center. It's built from **stereo satellite photos** — take two pictures of the same spot from slightly different angles, and trigonometry gives you the 3D shape (this is called *stereophotogrammetry* and is the same principle as your two eyes giving depth perception).

REMA covers **2021–2023** for parts of the MDVs. It's less accurate than lidar but is updated way more often and is free. Whether REMA is *accurate enough* for tiny stream-level changes is itself one of Barlow's research questions.

### U-Net

A type of neural network designed for **semantic segmentation** — taking an image and coloring in which pixels belong to which category. The "U" comes from its shape: it first shrinks the image down to extract high-level features (the "encoder" side), then expands it back to full resolution while preserving spatial detail (the "decoder" side), with shortcut connections across the U so the model doesn't lose fine details. Invented by Ronneberger et al. 2015 for medical imaging, now used everywhere.

### ICP (Iterative Closest Point)

A math procedure that lines up two 3D datasets. It iteratively figures out how to slide and rotate one dataset so that every point on it sits as close as possible to its nearest neighbor on the other dataset. Barlow uses **Point-to-Plane ICP**, which is a slightly fancier variant that aligns points to local surfaces (planes) instead of to other individual points — better for terrain.

---

## Part 3 — Chapter 4: Teach a U-Net to draw streams in Taylor Valley (proof of concept)

This is the first big experiment. Just one valley, just lidar, just to prove the idea works.

### The hard part: there's no water in most of these streams

You can't just look for blue pixels in an aerial photo. These streams are dry most of the year. So the AI has to learn what a stream *channel* looks like in terms of the **shape of the ground** — the subtle banks, the inflection points where the wall meets the floor, the linear depressions, breaks in slope.

### What she fed the model

From the 2014 lidar, she derived four 1-meter-resolution rasters:
- **Elevation** (the DEM itself)
- **Slope** (steepness at every pixel)
- **Intensity** (how much laser light bounced back — different surfaces reflect differently)
- **Flow accumulation** (where water would go if it rained, computed using a multi-flow-direction algorithm in ArcGIS)

### The training data

She manually outlined streams in **217 small tiles** (300 × 300 m each) covering about **1% of Taylor Valley**. She picked tiles that include all kinds of stream shapes — straight, sinuous (snake-like), meandering (loopy), braided/multi-channel — plus tiles with no streams at all. Stream boundaries were drawn by looking for slope breaks, sediment-texture changes, dark "staining" from past flow, and linear patterns.

She split the 217 tiles **50/20/30** — 50% training, 20% validation, 30% test.

### The model

Off-the-shelf U-Net implementation (the open-source "Landcover Dronedeploy" tool by Pilkington 2019, PyTorch 1.1.0), with a pre-trained **ResNet-18** encoder. Trained on free Google Colab GPUs (Nvidia K80s/T4s/P4s/P100s) for **200 epochs**, batch size 16, learning rate 1e-5, weight decay 1e-4. Each model took 4–6 hours to train.

### Results

She tried each of the four input features alone, plus various combinations. The headline finding: **single features beat combinations.** Specifically, **elevation alone** and **slope alone** got the highest scores:

| Feature | Precision | Recall | F1 |
|---|---|---|---|
| Elevation | 0.94 ± 0.05 | 0.95 ± 0.04 | 0.94 ± 0.04 |
| Slope | 0.96 ± 0.03 | 0.93 ± 0.04 | 0.94 ± 0.04 |
| Intensity | 0.88 ± 0.08 | 0.94 ± 0.05 | 0.94 ± 0.05 |
| Flow accum | 0.89 ± 0.09 | 0.93 ± 0.07 | 0.93 ± 0.07 |

Combinations like elevation+slope scored *lower* (F1 ≈ 0.83) than either alone. Likely because adding redundant or partially noisy features confused the model rather than helped it.

The model worked best on **meandering streams** (lots of bank shape information), worst on **straight streams** (less to distinguish from background terrain), and best **near the coast** where stream channels are clearer. Performance dropped slightly inland, especially near bedrock outcrops, where the surrounding terrain has confusing inflection points that mimic stream banks.

### Predicting the whole valley

After training, she scanned the **entire Taylor Valley** by breaking it into **852 overlapping 1500 × 1500 m tiles** and running the model on each. Total prediction time: about **15 minutes**. Tile size mattered — smaller tiles caused the model to misclassify edges as streams.

---

## Part 4 — Chapter 5: Is satellite elevation data trustworthy enough?

Lidar is great but only available in 2001 and 2014. To extend the analysis forward in time, she needs the satellite REMA dataset. But REMA is built from photos taken from space — is it accurate enough to detect the tiny elevation changes (centimeters to a meter) that ephemeral streams cause?

### The alignment problem

Before you can compare two elevation maps, you have to **line them up perfectly**. Even tiny offsets — a few centimeters horizontally — will cause a steep slope to appear like a big elevation change just because pixels don't match up. She uses **Point-to-Plane ICP** to do this alignment.

### The unusual error distribution

After alignment, she subtracts one DEM from the other and looks at the leftover differences in *stable terrain* (places we know didn't actually change). Normally, statisticians assume these residual errors follow a **Gaussian (bell-curve)** distribution. Barlow tested both Gaussian and **Laplacian** distributions and found:

> **The Laplacian fits better.** A Laplacian distribution is pointier in the middle and has fatter tails — meaning most errors are very small but you get more big outliers than a Gaussian would predict.

This matters because if you use standard deviation (which assumes Gaussian), the outliers will inflate your uncertainty estimate and you'll think the data is noisier than it really is for most pixels. Instead, she uses:

### NMAD — Normalized Median Absolute Deviation

NMAD is the median of how far each value is from the overall median, multiplied by a constant (~1.4826) so that for Gaussian-distributed data it equals the standard deviation. The key property: **NMAD is robust to outliers.** A few huge errors don't blow up your uncertainty estimate.

### Results

After ICP alignment, the REMA-vs-lidar residuals in stable terrain have NMAD values mostly in the **sub-meter** range. Specific findings:

- **Inside stream channels**, uncertainty is slightly higher than on stable terrain — makes sense, that's where the ground really does change.
- **Steep slopes** and certain **aspect (slope-direction) ranges** have higher errors — partly because tiny horizontal misalignments become big vertical errors on steep ground, partly because shadowed slopes face away from sunlight and produce noisier stereo matches.

The verdict: **REMA is good enough for stream-corridor change detection in the MDVs, as long as you mask out steep / problem aspects and use NMAD-based uncertainty.**

---

## Part 5 — Chapter 6: Scale the U-Net up to the whole MDV system

Chapter 4 only covered Taylor Valley with one lidar dataset. Chapter 6 extends the approach to:

- **All four major valleys** (Taylor, Wright, Victoria/Barwick, Denton Hills)
- **Three time periods**: 2001 (lidar), 2014 (lidar), and 2021–2023 (REMA satellite)

This requires training a more general U-Net that works across different sensors and terrain types.

### Key differences from Chapter 4

- More features used: in addition to elevation, slope, intensity, and flow accumulation, she also adds **aspect** (slope direction) and **curvature** (convex vs. concave).
- Bigger and more diverse training set.
- Post-processing to clean up predictions into polygons and connect fragmented detections.

### Attribute importance

The big takeaway from this chapter is that across all valleys and sensors:

> **Elevation, slope, and aspect are the three most informative features for stream boundary detection.**

Flow accumulation and intensity help less when generalizing across valleys (probably because flow accumulation depends on having a good DEM in the first place, and lidar intensity isn't available in satellite data anyway).

### The deliverable

She produces **multi-valley stream-boundary polygon datasets** for 2001, 2014, and 2021–2023 — the first time this has existed at this scale for the MDVs. Previously, the best public maps were **stream centerlines** from the LTER program; her polygons are *outlines* of the channels themselves, way more useful for measuring change.

---

## Part 6 — Chapter 7: Two decades of change

Now she has the tools. Time to measure what's actually been happening.

### The pipeline

For each pair of time periods (2001–2014, 2014–2021/23):

1. Use the U-Net-derived stream polygons to create a **mask** — analysis only happens inside stream channels, not on the stable hillsides between them.
2. Subtract the older DEM from the newer one inside the mask. This is called a **DEM of Difference (DoD)**. Positive = deposition (sediment piled up). Negative = erosion (ground was scraped away).
3. Apply a **Level of Detection (LOD)** threshold — only changes bigger than `LOD95 = 1.96 × NMAD` count as real. Anything smaller is in the noise and gets thrown out.
4. Sum up volumes per stream and convert to **rates** (cubic meters per year).
5. Compute both:
   - **Gross rate** = total magnitude of change (erosion + deposition added together) — how *busy* the stream is.
   - **Net rate** = erosion minus deposition — whether the stream is, on balance, removing or adding sediment.

She also normalizes by **active channel area** so big streams aren't unfairly compared to little ones, and scales to **per decade** to make numbers human-readable.

### LOD95 values across streams

After the per-stream uncertainty analysis:
- **2001–2014 (lidar–lidar):** NMAD 0.07–0.46 m, LOD95 0.15–0.92 m
- **2014–2021/23 (lidar–REMA):** NMAD 0.19–0.53 m, LOD95 0.37–1.04 m

So you can detect ~15–90 cm changes between lidar epochs and ~37–104 cm changes when satellite data is involved.

### Headline results — 2001 to 2014

**The standout stream:** **Ward Stream** (in Denton Hills) had a **gross sediment flux of 78,713 m³/year** — dominated almost entirely by erosion (77,598 m³/yr eroded, only 1,116 m³/yr deposited). Net rate: **−76,482 m³/yr** (very strongly erosional).

Other very active streams:
- **Garwood**: 62,637 m³/yr gross, balanced net
- **Marshall**: 34,915 m³/yr gross, −26,071 net (erosion)
- **Wright**: 26,625 m³/yr gross, +13,417 net (deposition)
- **Onyx**: heavy deposition, +20,021 m³/yr deposition

**Regional patterns:**

- **Denton Hills** → strongest erosion per unit area in the entire MDVs. This is the geomorphic hotspot.
- **Taylor Valley** → split personality. Coastal reaches **deposit** sediment (the stream loses energy as it spreads out near the lakes/coast). Inland reaches **erode**. The Lake Bonney region is heterogeneous with strong erosion on the southern cliffs.
- **Wright Valley** → mostly balanced or mildly depositional along the valley floor, with some erosion on southern walls.
- **Victoria/Barwick Valleys** → mostly depositional, except Packard Stream.

### 2014 to 2021–2023

Only parts of Taylor Valley had high-quality REMA coverage in this window, so this analysis is more limited (38 streams instead of 116). Pattern is broadly similar — most streams depositional, a few coastal channels showing net erosion.

### The really interesting bit: acceleration

For the streams in Taylor Valley where she has *three* time periods (2001, 2014, 2021–23), she can compute **acceleration** — is the rate of change *itself* speeding up or slowing down?

Acceleration formula:
```
a = (R(t2) − R(t1)) / (t_mid_2 − t_mid_1)
```

where R is the geomorphic rate in each interval. Units are m³/yr².

Findings: **localized geomorphic acceleration** in parts of Taylor Valley. Not every stream is speeding up, but some clearly are. This is exactly the "MDVs as early-warning canary" signal the climate-science community has been looking for.

---

## Part 7 — Chapter 8: What it means and what's next

### Contributions in summary

1. **First-ever U-Net-based stream-boundary detector** that uses only terrain attributes (no RGB / water-color signal needed), so it works in dry-most-of-the-year channels.
2. **First multi-valley, multi-epoch stream-polygon dataset** for the MDVs (2001, 2014, 2021–23).
3. **Validation of REMA satellite DEMs** for stream-corridor change detection, with Laplacian-error modeling and NMAD-based uncertainty.
4. **First valley-wide quantification of fluvial geomorphic change** in the MDVs across two decades, with per-stream rates and acceleration estimates.

### Limitations she calls out honestly

- The model struggles where stream banks aren't clearly distinguishable from underlying bedrock or strata patterns.
- Coverage of REMA in the 2021–23 epoch is uneven across the MDVs — can't do the three-epoch acceleration analysis everywhere.
- "Stream existence" is decided manually using a combination of LTER centerlines and visible water/ice evidence — there may be small streams nobody knew about.
- Training labels were drawn by hand and the model can only be as good as the labeler.

### Future work she suggests

- **Long-term monitoring** — keep applying the pipeline as new REMA epochs come out.
- **UAV (drone) lidar** for ultra-high-resolution work in sensitive sites.
- **Glacier-feature segmentation** — preliminary tests showed the model can also pick up supraglacial streams and crevasses; could be extended into a glacier-monitoring tool.
- **Climate variable correlation** — pair geomorphic acceleration with temperature, solar radiation, and energy balance data to predict where rapid change will happen next.
- **Generalize the model** — train on globally diverse stream examples so it works outside the MDVs (similar polar deserts, ephemeral channels in arid regions on Earth or even Mars).

### Why anyone outside Antarctica should care

The MDVs are one of the most data-poor and access-restricted study areas on the planet. The methods Barlow develops — **AI-based feature detection from elevation alone + rigorous satellite-DEM uncertainty modeling + multi-epoch change detection inside masked corridors** — transfer to:

- Other polar regions (Arctic, Greenland, Tibetan Plateau)
- High-altitude mountain catchments
- Arid-region ephemeral channels (which most river-mapping AIs ignore because they assume water is present)
- Planetary science (Mars rover landing-site selection, channel mapping)

In short: she didn't just write a thesis about Antarctic streams. She wrote a thesis about **how to study any temporary water system that you can't fly out to easily.**

---

## In one breath, again

> Polar deserts in Antarctica are starting to wake up after a century of stability. The most sensitive sign is the temporary streams that turn on each summer. Barlow taught an AI to outline those streams using only the shape of the ground (no water-color clues needed), proved that free satellite elevation data is accurate enough to detect their tiny changes, then used both to measure how much sediment has been moving across four whole valleys over twenty years — finding that Denton Hills is the hotspot, Taylor Valley is split between erosion inland and deposition coastward, and some places are clearly speeding up. The result is the first ever valley-wide automated climate-change monitor for one of Earth's most stable landscapes.
