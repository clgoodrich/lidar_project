# Drainage review — 613590

Goal: give the road model local drainage labels. It is a 3-class model
(bg / road / drainage), but its only drainage training data (`drainage.shp`)
sits at x 620,659-624,000 and this block spans x 613,500-618,000. **No overlap.**
So drainage here is predicted with zero local supervision.

## Layers to load (drag into QGIS, in this order)
1. `hillshade_613590_1m.tif`                       (basemap)
2. `drainage_prob_613590_1m.tif`                   (model drainage confidence)
3. `review_drainage/road_rejects_613590.gpkg`      (magenta dashed — read the note below)
4. `review_drainage/review_drainage_613590.gpkg`   (predicted drainage — you edit this)
5. `review_drainage/added_drainage_613590.gpkg`    (empty — you DRAW missed drainage here)

## The magenta layer is the point of this package
`road_rejects_613590.gpkg` holds the 0 road segments you deleted during the
road review (0.0 km). The model scored them P(road) nan and
P(drainage) nan — it was confident they were roads and had no idea they
might be water. Some of them are almost certainly stream channels.

**Where a magenta line is actually drainage, trace it into `added_drainage`.**
That upgrades it from a generic "not a road" negative into a labelled drainage
positive, which is a much stronger training signal and the fix that made the
3-class model work on 9t in the first place.

## How to correct
- **Wrong drainage** (blue lines that are not channels): toggle editing on
  `review_drainage` and **delete** them. Rejects are recovered by comparing
  against `review_drainage_613590_ORIGINAL.gpkg`, so deleting is safe and is the
  workflow the corrections builder expects.
- **Unsure**: set `status = 'unsure'` and it is excluded from training.
- **Missed drainage**: draw the centreline in `added_drainage`. Trace the
  channel thalweg, not the bank-to-bank width.
- Save edits (Ctrl+S) and toggle editing off when done.

## Tips
- Sort `review_drainage` by `mean_pdrain` ascending to hit the least-confident
  predictions first — the likeliest false positives.
- `mean_proad` is on the same table. A segment high in **both** is a genuine
  model confusion and is worth adjudicating carefully.
- You do not need full coverage. Partial labels are fine — the corrections
  builder marks unadjudicated ground as `ignore` and never teaches it as
  background.

Segments are ~40 m so you can flag a bad stretch without splitting lines.
