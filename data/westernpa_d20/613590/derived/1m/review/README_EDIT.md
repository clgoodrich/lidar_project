# Road review — 613590

Goal: correct the model's predicted roads so we can retrain on YOUR fixes.

## Layers to load (drag into QGIS, in this order)
1. `hillshade_613590_1m.tif`            (basemap)
2. `road_prob_613590_1m.tif`           (optional: model confidence heat-map)
3. `review/review_roads_613590.gpkg`    (the predicted roads — you edit this)
4. `review/added_roads_613590.gpkg`     (empty — you DRAW missed roads here)

## How to correct (flag, don't delete)
- Toggle editing (pencil icon) on `review_roads`.
- Select the bad segments (false roads, bogus links). Open the attribute table
  or Field Calculator and set **status = 'reject'** for them. DO NOT delete —
  the rejected geometry is used as a hard negative ("not a road") in training.
- Leave good segments as **status = 'keep'** (the default).
- If unsure, set **status = 'unsure'** and we'll exclude it from training.
- For roads the model MISSED: toggle editing on `added_roads`, draw the
  centerline(s). status auto = 'added'. Trace the road, not the exact width.
- Save edits (Ctrl+S) and toggle editing off when done.

## Tips
- Style `review_roads` by `status` (keep=green, reject=red) to track progress.
- Sort the attribute table by `mean_proad` ascending to review the model's
  least-confident segments first — those are the likeliest false positives.

Segments are ~40 m so you can flag a bad stretch without splitting lines.
