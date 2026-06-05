# WellSight — How It All Works (Plain-English Guide)

*A quick tour of what WellSight does and how, written so a smart 16-year-old can
follow it. No GIS degree required. Each section answers a question someone might
actually ask you.*

WellSight hunts for **old, abandoned oil & gas wells** in the forests of western
Pennsylvania. There are tens of thousands of them, drilled over the last 150
years, and many were never properly recorded or capped. They can leak methane.
The problem: they're hidden under trees, so you can't just look at a normal aerial
photo. WellSight uses **laser maps of the ground** to find the faint scars these
old well sites left in the dirt.

---

## 1. What is the raw data, and where did it come from?

We use two main ingredients.

### a) LiDAR point clouds (the laser map)
**What it is:** A plane flies over the area firing a laser straight down,
hundreds of thousands of pulses per second. Each pulse bounces off whatever it
hits (a leaf, a branch, the ground) and comes back. From the travel time, you get
the exact 3D position of that bounce. Do this across a whole county and you get a
**point cloud** — millions of tiny 3D dots that together form a 3D model of the
forest and the ground beneath it.

**Why it's special:** Some laser pulses slip through gaps in the leaves and hit
the actual dirt. So even under a thick tree canopy, we can reconstruct the shape
of the bare ground. A normal photo can't do that — it only sees the treetops.

**Where we got it:** Public LiDAR surveys from **USGS 3DEP** (the U.S.
government's national elevation-mapping program). The files are `.las`/`.laz`
(the standard point-cloud format). Each survey covers a "work unit" — a big
rectangular chunk of land. We work tile-by-tile (e.g. the tile we call "9t", and
the "Oil Creek" tiles).

**File format note:** Every point is tagged with a *class* (ground, vegetation,
building, water, etc.) following the **ASPRS** industry standard. We care a lot
about the points tagged "ground."

### b) Known well locations (the answer key)
**What it is:** `output_wells.csv` — a list of wells that are *already* known and
mapped, with their coordinates. This comes from the **Pennsylvania DEP**
(Department of Environmental Protection) oil & gas catalog.

**Why we need it:** It's our **ground truth / answer key**. If our detector lights
up exactly where a known well is, we know it works. We tune the system against
these known wells, *then* point it at unmapped areas to find new ones. We treat
this file as read-only and never overwrite it.

---

## 2. How do we turn 3D laser dots into a usable map?

A pile of millions of 3D dots is awkward to work with. We boil it down to flat
images (called **rasters** — basically grids of numbers, like a photo where each
pixel is a measurement instead of a color).

**Step 1 — Keep only the ground.** We filter the point cloud down to just the
points classified as "ground," throwing away trees and buildings. Tool: **PDAL**
(a point-cloud processing engine). *Quirk of our setup: PDAL's Python version
doesn't work here, so we write the instructions to a small text file and run
PDAL's command-line program directly.*

**Step 2 — Build a DEM (Digital Elevation Model).** We take those ground points
and grid them into an image where each pixel's value = the ground height there.
This is the **bare-earth terrain** with the forest digitally stripped away. Our
DEMs are at 1 meter and 0.5 meter per pixel.

That DEM is the foundation everything else is built on.

---

## 3. What actually goes *into* the models? (The "feature stack")

Here's the key idea: **a raw height map alone doesn't make well scars pop out.**
A well pad might be only a few centimeters different from the dirt around it. So
we run the DEM through a set of math filters that each **exaggerate a different
kind of terrain shape.** Think of them like Instagram filters, but instead of
making a photo prettier, each one makes a specific landform easier to see.

These are the filters we compute (using **WhiteboxTools** and **GDAL**, two
terrain-analysis toolkits):

| Filter | What it highlights (in plain terms) |
|---|---|
| **Slope** | How steep the ground is. Flat pads vs. natural hillsides. |
| **LRM** (Local Relief Model) | Removes the big hills and leaves only *small* bumps and dips — perfect for faint man-made scars. We make two versions (fine + coarse). |
| **TPI** (Topographic Position Index) | Whether a spot sits higher or lower than its neighbors — finds ridges and pits. |
| **Openness (positive & negative)** | How "exposed" vs. "tucked into a dip" a spot is. Great for spotting depressions and edges. |
| **Roughness** | How bumpy vs. smooth an area is. Old disturbed ground often has a different texture. |
| **Hillshade** | A fake "sun" shined across the terrain to cast shadows, so 3D shape is visible to the eye (mostly for *us* to look at). |

We stack these filtered images on top of each other into one multi-layer image —
the **7-band feature stack** (`features_*.tif`). When the model looks at one spot,
it sees all 7 measurements at once. That's a much richer description than a plain
photo.

> **If someone asks "what data inputs went into your model?"** → The answer is:
> *not* raw photos and *not* the raw laser points. It's this stack of 7
> terrain-shape layers, all derived from the bare-earth DEM:
> **LRM (fine), LRM (coarse), slope, TPI, openness-positive, openness-negative,
> and roughness.** Every model (UNet, Mask R-CNN, YOLO) eats this same stack.

**Why this stack and not, say, the tree canopy height?** We tried using canopy
(CHM, "how tall are the trees here"). We dropped it: tree cover is inconsistent —
some old wells are heavily overgrown, some aren't — so canopy adds noise instead
of signal. The terrain-shape filters above describe the *dirt itself*, which is
what actually carries the well scar, so they're far more reliable.

One more detail: before feeding the stack to a model, we **z-score normalize** it
(rescale every layer so it's centered at 0 with a standard spread). Neural nets
learn much better when their inputs are on a consistent scale.

---

## 4. How does the computer learn what a well looks like?

We can't tell a computer "find wells" in words. We **show it examples.**

**Step 1 — Hand-label examples.** In QGIS (a free map-editing program), a human
draws polygons around features we can see in the terrain filters:
- **Pits** — small depressions. We label two parts: the **floor** (the bottom of
  the dip) *and* the **wall** (the rim around it), so the model learns the whole
  shape, not just the hole.
- **Pads** — the flat cleared platforms where drilling equipment sat.
- (Roads/streams are handled separately — see section 6.)

These hand-drawn shapes live in an annotations file and are split into three
groups: **train** (the model studies these), **validation** (used to check it's
not cheating), and **test** (a locked-away set it never sees during training, used
for the final honest grade).

**Step 2 — Train the model.** We cut small square "patches" out of the feature
stack centered on each labeled example (with a little random shifting, called
*jitter*, so the model doesn't just memorize exact positions). The model looks at
a patch, guesses where the well feature is, gets told how wrong it was, and nudges
its internal numbers to do better. Repeat thousands of times.

We use a trick called **transfer learning**: the models start from weights
already trained on millions of everyday photos, so they begin knowing basic shape
and edge detection. We just retrain them to recognize *our* terrain features. (A
small engineering bit: those pretrained models expect 3-color input, but our stack
has 7 layers, so we "widen" the model's first layer to accept all 7.)

---

## 5. We use three different model types — why?

Different tools answer slightly different questions. We run them and compare.

| Model | Plain description | Question it answers |
|---|---|---|
| **U-Net** | Colors in *every pixel* with a label (this pixel is "pad," that one is "background"). Called **semantic segmentation**. | "Which areas are well-related?" Great for **long thin features** like roads/streams. |
| **Mask R-CNN** | Draws a separate outline around each **individual object**. Called **instance segmentation**. | "Here are pad #1, pad #2, pad #3…" as countable, separate things. |
| **YOLO (seg)** | Same idea as Mask R-CNN (separate objects) but built for **speed**. | A fast second opinion to cross-check Mask R-CNN. |

The reason for instance models (Mask R-CNN, YOLO) is that U-Net just paints
regions — it can't easily say "that's *two* wells, not one big blob." For
**counting and ranking individual candidate wells**, you want instance models.

**How we grade them (apples-to-apples):** For each model we ask the same question
on the locked-away **test set**: for each real well, did the model find it, and
how well did its outline overlap the true outline (a score called **IoU**,
intersection-over-union — how much the predicted shape and the real shape agree,
0 = no overlap, 1 = perfect)? Then **recall@IoU 0.5** means "what fraction of real
wells did we find with at least 50% shape agreement." Using the identical metric
on the identical test wells is what makes the comparison fair.

---

## 6. How are the streams/roads made? (A separate sub-pipeline)

Old wells were reached by **access roads**, and roads often follow or cross
streams. Mapping the natural drainage helps us tell a man-made road-scar from a
natural gully. The stream map is built straight from the DEM:

1. **Breach/fill the DEM.** Real terrain data has tiny fake dips that would trap
   water. We "breach" them so water can flow continuously downhill.
2. **Flow accumulation (D8).** Imagine dropping a raindrop on every pixel and
   letting it run downhill, always to the lowest neighbor. Count how many drops
   pass through each pixel. Pixels with lots of flow = stream channels.
3. **Threshold.** We keep only pixels where the accumulated flow is above a
   cutoff (we use **5000**, written `t5000`). Below that it's just a hillside;
   above it, it's a real channel.
4. **Road filtering by cross-section.** A natural stream cuts *down* into the land
   (V-shaped valley). A road is *flat or raised*. So we slice across each detected
   line and check its profile: if it dips like a valley, keep it as a stream; if
   it's flat, flag it as a likely road. This is the "**chunked kept xsec**"
   (cross-section) step you've heard mentioned.

---

## 7. How do we make sure the results are trustworthy?

A few habits baked into the project:

- **Coordinate systems (CRS) must match.** Every map has a coordinate system
  (ours is mostly NAD83 / UTM Zone 17N). If two layers use different ones,
  features land in the wrong place. We always check the CRS before combining
  anything.
- **Start small, then scale.** Before running an expensive process on a whole
  county, we test it on a small patch around a few *known* wells. If it works
  there, we scale up. This avoids wasting hours on a broken setup.
- **Candidates are never "confirmed."** Anything the model finds is labeled a
  **candidate** or **probable** well, with a confidence score and the distance to
  the nearest known well — never presented as a proven well.
- **Everything is written down.** Every experiment ("iteration") gets a markdown
  write-up and goes on a leaderboard, so we can always see what we tried and how
  well it did.

---

## 8. The whole thing in one breath

> A plane shoots lasers at the forest → we keep only the points that hit the
> *ground* → grid them into a bare-earth height map (**DEM**) → run terrain
> filters that exaggerate faint man-made scars → stack 7 of those filters into one
> image → show a neural network thousands of hand-labeled examples of pits and
> pads in that image → the trained network then outlines new candidate wells →
> we grade it against a locked-away set of known wells and only call the matches
> "candidates," never "confirmed."

That's WellSight.
