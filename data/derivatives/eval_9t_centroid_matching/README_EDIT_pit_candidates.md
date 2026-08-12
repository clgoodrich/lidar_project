# Pit candidate review — 9t, threshold 0.50

`pit_candidates_undecided_thr0p50_9t.gpkg` layer **undecided** holds 207 held-out detections that match
no recorded pit. A pit counts as recorded if it appears in EITHER `pit_outside`
(rim) or `pit_inside` (floor): 106 are drawn as a floor with no rim and
138 as a rim with no floor, and all of them count. Each candidate is either a
false positive or a well nobody has drawn yet.

## How to review
1. Load `C:\Users\colto\Documents\GitHub\lidar_project\data\derivatives\tiles\9t\hillshade_9t_05.tif` as a basemap.
2. Load the `undecided` layer from `C:\Users\colto\Documents\GitHub\lidar_project\data\derivatives\eval_9t_centroid_matching\pit_candidates_undecided_thr0p50_9t.gpkg`.
3. Toggle editing. For each candidate set **status**:
   - `pit` — it is a real pit. Draw it into `pit_inside` / `pit_outside` as usual.
   - `not_pit` — it is not.
   - `unsure` — leave it out of the scoring either way.
4. Save edits.

## Reading the fields
- `score` — model confidence, 0.51 to 0.76. Sorted descending, so `cand_id` 1 is the most confident.
- `near_pit_m` — metres to the nearest recorded pit (rim or floor). A few metres
  usually means the model found a known pit but the blob centroid drifted outside
  it; tens of metres means it fired on something else.
- `dup_on_pit` — 1 means the blob centroid sits inside a pit you already drew,
  but a higher-scoring blob claimed that pit first, so this one is a second piece
  of the same pit rather than a new find. Filter `dup_on_pit = 0` to review only
  genuine candidates.
- `fold` — which CV fold model produced it. None of them trained on this block.

## Other layers (context, do not edit)
- `size_rejected` — 0 blobs smaller than any annotated floor
  (below 0.0 m2). Excluded from precision, kept here so nothing is hidden.
- `matched` — 481 predictions already paired with a recorded pit.
- `missed_pit` — 26 recorded pits the model did not find.

Rerun after annotating and the undecided list shrinks:
`python notebooks/wellsight_v2/eval/_build_undecided_pit_candidates_9t.py`
