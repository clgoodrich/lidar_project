# How to build the talk

Two halves, because building a deck and explaining a project are different jobs.

**Part 1** is mechanics: how this deck is actually made, and how to add to it.
**Part 2** is the narrative: what to say about the process, stage by stage.

The slide list lives in `presentation_update_worklist_30to45min.md`. This file
does not repeat it.

---

# Part 1 — Mechanics

## What the deck is

`docs/presentation/WellSight_Presentation.pptx`, 22 slides, 13.33 x 7.5 inches
(16:9 widescreen). `python-pptx` 1.0.2 is installed.

Every slide is built on **layout 6, "Blank"**, with text boxes positioned by hand
in inches. The eleven PowerPoint layouts exist but are not used. That matters: if
you add a slide in PowerPoint using a normal layout, it will not match the others.

## The builder

`archive/wellsight/paper/paper/_build_presentation.py` builds the whole deck from
scratch. Its helpers:

```python
add_bg(slide)                                   dark background rectangle
tb(slide, left, top, w, h, text, size, color, bold, align)   one text box
bullets(slide, left, top, w, h, items, size, color)          a bullet list
img(slide, path, left, top, width, height)                   an image
tbl(slide, left, top, w, h, data)                            a table
```

Each slide is three lines:

```python
s = prs.slides.add_slide(prs.slide_layouts[6]); add_bg(s)
tb(s, 0.5, 0.3, 8.0, 0.8, "Slide Title", size=32, bold=True)
bullets(s, 0.5, 1.5, 12.0, 4.5, ["point one", "point two"])
```

**It ends with `prs.save('WellSight_Presentation.pptx')` — it overwrites, it does
not merge.** Re-running it destroys anything you edited in PowerPoint. Back up
the deck before running it, or change the output filename.

Three sibling scripts patch an existing deck instead of rebuilding:
`_update_slides.py`, `_modify_pptx_slides.py`, `_add_notes.py`. All of them open
`WellSight_Presentation.pptx` **by bare filename**, so they must be run from the
directory holding the deck — now `docs/presentation/`.

None of these have been run since May. Check they still run before relying on
them.

## Which route to take

**Rebuild from the script** if you want the 39 new slides to match the existing
ones visually, and you are comfortable writing slide content as Python. This
keeps everything reproducible and lets you regenerate after a number changes.

**Edit in PowerPoint** if you want to move fast and do not care about
regenerating. Given this is a talk, not a deliverable that gets rebuilt monthly,
this is a legitimate choice.

**Do not do both.** The builder overwrites.

Recommendation: rebuild the seven kept slides plus the new ones in a *new* script
(`_build_presentation_v2.py`, writing a new filename), leaving the May deck
untouched as the fallback. Copy the helpers, keep the palette.

## The palette, and a clash you need to resolve

The deck is dark:

```python
DARK   = #1A1A2E    background
ACCENT = #0096C7    headings
WHITE  = #FFFFFF    body
ORANGE = #FF5722    GREEN = #4CAF50    BLUE = #2196F3    GRAY = #AAAAAA
```

**The nine figures in `figures_30to45min/` are light** — they are drawn on
`#fcfcfb` with dark ink, because they were built to be readable on paper and on a
light slide. Dropping them onto the dark deck gives you bright white rectangles
on a near-black background. It looks like a mistake, and at projector contrast it
is genuinely hard to look at.

Three ways out, pick one before building slides:

1. **Go light.** Rebuild the deck on a light background. The figures then fit,
   and light decks project better in a bright room. Most work.
2. **Regenerate the figures dark.** `_build_presentation_figures.py` sets its
   palette in one block at the top — `SURFACE`, `INK`, `INK2`, `GRID`. Swapping
   those to dark values and re-running gets you dark figures. The categorical
   series colours would need re-validating against the new surface.
3. **Put each figure on a white card** with generous padding, so it reads as a
   deliberate panel rather than a hole. Least work, looks fine, slightly dated.

## Figures

```
docs/presentation/figures_30to45min/
    _build_presentation_figures.py      rebuilds all nine
    figure_notes_what_each_image_shows.md   what each shows and where numbers come from
    _manifest.json
```

Rebuild with:

```
python docs/presentation/figures_30to45min/_build_presentation_figures.py
```

Everything is read from data on disk, so if a number changes, re-run and the
figure updates. Two exceptions noted in the file: the pipeline diagram is a
schematic, and the two classical AUC values are carried over by hand.

Figures that already exist elsewhere — road corrections, RRIM previews, tile
overviews — are listed in the worklist under "Assets". Reference them at their
existing paths; do not copy them into this folder or you create duplicates with
no clear original.

---

# Part 2 — Explaining the process

This is the part that is hard to write from an outline, because it is not a list
of facts. It is the sequence of *why* that makes the facts land.

## The spine

The talk is one argument in five moves:

1. There are tens of thousands of undocumented wells, and the records are bad.
2. LiDAR sees through the canopy to the ground scar.
3. Finding the scar is not the hard part. Knowing which scars are real, and
   proving it, is.
4. Here is the machinery we built, and here is what it actually scores.
5. Here is where it broke, and what that taught us.

Move 5 is the one nobody else does. Do not cut it.

## Stage by stage — what to say

**Terrain derivatives.** A bare-earth elevation model is a grid of heights, and a
0.7 m depression is invisible in it. The derivatives make the depression
visible — local relief subtracts the broad landscape and leaves the small stuff,
openness measures how enclosed a point is, slope and roughness describe texture.
Seven of these become the seven channels the model reads. **The point to make:**
we are not showing the model a photograph. We are showing it seven different
measurements of shape at the same place.

**Annotation.** Every label is hand-drawn in QGIS. 8,609 features across seven
layers. **The point to make:** this is the expensive part, not the training. And
the layers are deliberate — a pit floor, a rim, the whole depression, the pad
footprint, the access road, the drainage that looks like a road but is not.

**Why polygons instead of points.** The earlier system detected locations. A
point is right or wrong. A polygon can be right in the wrong place, the right
place at the wrong size, or one object split in two. That is why the metrics got
complicated — and why the numbers are more honest.

**The spatial split.** The model learns from square windows of ground that wobble
about 30 m. So a window centred on a training pit can overlap the pit next door.
If that neighbour is a test pit, the score is inflated. Cutting the tile into 144
blocks and assigning whole blocks puts a wall between training and testing.
**The point to make:** this is the difference between a number you can defend and
a number that flatters you.

**Balancing on features, not blocks.** Pits cluster on pads, so blocks hold wildly
different counts. Handing 70% of the blocks to training could give you 40% of the
pits. The fill counts features as it goes.

**Training.** Same architecture for all four targets, different label raster and
different class weights. The road and drainage models are the same model with the
weights flipped — whichever class you want found gets the high weight, and the
other becomes a hard negative.

**Why drainage is its own class.** The road model kept firing on stream channels.
Rather than filter them out afterwards, drainage was made a class the model has
to name. Held-out drainage probability on road pixels fell to 0.005. **The point
to make:** fix it in training, not in post-processing.

**Cross-validation.** Train five times, each holding out a different fifth. Every
feature gets scored by a model that never saw it. It costs five times the compute
and it is the reason a single unlucky split cannot embarrass you.

**Thresholds.** A probability raster is not an answer until you pick a cutoff.
The cutoff is chosen on a validation split under a rule declared in advance —
F1 or F2 — then frozen and scored once. **The point to make:** picking the
threshold after seeing the test result is the most common way to fool yourself,
and it is invisible in a results table.

**The review loop.** The model proposes, you correct in QGIS, the corrections
become new training data. 22 km of your edits moved out-of-domain performance
measurably with zero in-domain cost. **The point to make:** the human is in the
loop by design, not because the model is not good enough yet.

## Numbers you can quote, and where they come from

| claim | number | source |
|---|---|---|
| annotation | 8,609 features, 712 pit floors, 995 pads | `annotations_proj.gpkg` |
| in-tile | 503 pits, 650 pads inside 9t | manifests |
| pit search reduction | 4.33 ha of 2,025 = 0.21%, finds 126/127 | `pit_threshold_found_vs_missed_summary_9t.csv` |
| pit cross-validated | recall 0.861, precision 0.686, containment 0.914 | `LEADERBOARD.md`, ann712 |
| pad cross-validated | recall 0.888, precision 0.597, locate 0.923 | `LEADERBOARD.md`, ann712 |
| road | pixel IoU 0.581, line AP 0.999 | `LEADERBOARD.md` |
| drainage separation | AP drainage-vs-road 0.990 | `drainage/unet_1m/test_metrics.json` |
| drainage rejection | P(drainage) on road pixels 0.005 | `LEADERBOARD.md` |
| label fix vs architecture | +0.146 completeness at zero correctness cost | `LEADERBOARD.md`, 613590 |
| active learning | added-vs-reject AP 0.245 to 0.443 | `road_unet_1m_corrected` |
| precision bug | 3-6% was wrong, real is 0.54-0.69 | `LEADERBOARD.md` correction box |

## What not to claim

- **Do not present candidates as wells.** They are candidate or probable
  locations with a confidence and a detection method. Pennsylvania DEP
  terminology, always.
- **Do not quote the DEP cross-reference as a model score.** Its "median nearest"
  column is not positional accuracy. The leaderboard says so explicitly.
- **Do not say the classical approach was beaten.** It was superseded. The two
  were never measured against each other on the same split with the same metric.
- **Do not imply the 9t numbers transfer.** Every fold is still 9t. They show the
  number is *stable*, not that it *travels*. 613590 is the only out-of-domain
  evidence.
- **Do not quote a pit or pad number without the annotation version.** The split
  was reassigned when the annotation grew; ann426, ann527 and ann712 numbers are
  not interchangeable.

## Rehearsal

Time a read-through out loud before trimming. 46 slides at 55 seconds is 42
minutes, and people always run long on the material they know best — which here
is Act II.

The cut points are marked in the worklist. Cutting is easier than rewriting, so
build the full version first.
