# wellsight_v2 — the clean pipeline

A curated copy of the WellSight spine: **only** the scripts needed to (1) build
terrain derivatives from LiDAR, (2) train the models, and (3) run those models
back over the derivatives. The original `notebooks/wellsight/` is untouched and
still holds every experiment, one-off, and superseded version (~86 files); this
folder is the ~38 that actually carry the project.

Scripts find the shared libs (`_common.py`, `_dl.py`, `_instance_common.py`) via
a relative `parents[1]` path, so **keep the subfolder layout** — don't flatten.

## Shared libraries (root)
- `_common.py` — paths, CRS, PDAL helper (`run_pdal`), raster I/O.
- `_dl.py` — the deep-learning engine: `UNet`, `FocalCE`, patch sampler,
  training loop, `predict_full_tile`. Every U-Net trainer imports this.
- `_instance_common.py` — shared data helpers for the instance models (YOLO / Mask R-CNN).

## Stage 1 — Build derivatives (LiDAR → input channels + labels)
- `build/_build_3x3_hillshades.py` — LAZ tiles → 1 m DEM + hillshade per 3×3 block.
- `build/_build_derivatives.py` — the workhorse: DEM → full channel stack
  (lrm_25, lrm_5, slope, tpi, openness ±, roughness).
- `build/_build_data_3x3_derivatives.py` — runs the above over full 3×3 blocks.
- `build/_build_data_3x3_partial_westernpa.py` — same, but covers EVERY block
  (including partial edge blocks). Current region builder.
- `build/_build_contours_data_3x3.py` — per-block contour lines (optional product).
- `pits/_stack_features.py` — stack channels → `features_*.tif` (0.5 m) + stats.
- `roads/_prep_road_1m.py` — same at 1 m (roughness_5) + buffers roads → label raster.
- `annotations/` — turn hand-drawn shapefiles into training labels/splits:
  `_prep_annotations`, `_build_pit_dataset`, `_build_plat_road_dataset`,
  `_build_plat_split`, `_build_unified_split`, `_sanity_render`.

## Stage 2 — Train the models (features + labels → best.pt)
- `roads/_road_unet_1m_recall.py` — the active road model (3-class bg/road/drainage, α0.72).
- `pits/_pit_unet_v2.py`, `pits/_pit_maskrcnn.py`, `pits/_pit_yolo.py` — pit models.
- `plats/_plat_unet.py`, `plats/_pad_maskrcnn.py`, `plats/_pad_yolo.py` — plat/pad models.
- `multitask/_multitask_unet.py` — pit + road + plat in one network.

## Stage 3 — Inference + post-processing
- `build/_infer_roads_data_3x3.py` — slide the road model over a block → `road_prob.tif`.
- `build/_refine_roads_data_3x3.py` — region-level road refinement.
- `build/_road_optimize.py` — turn the road probability heatmap into clean
  vector lines (threshold → skeleton → vectorize → clean). `--apply` on any block.
- `build/_predict_on_tile.py` — generic U-Net inference (pit / plat / road).
- `build/_yolo_infer_tile.py`, `pits/_pit_*_infer.py`, `plats/_pad_*_infer.py` —
  instance-model inference.
- `build/_postfilter_tile_candidates.py` — filter raw candidate detections.

### Road active-learning loop (current focus)
1. `build/_build_road_review_package.py` — chop predicted roads into ~40 m
   segments with a `status` field → editable QGIS package.
2. *(human edits in QGIS: flag bad segments `reject`, draw missed roads.)*
3. `build/_road_corrections_diff.py` — diff edited vs. original → keep/reject/added
   labels to retrain on.
- `build/_road_methods_compare.py` — bake-off of competing extraction algorithms.

## What was intentionally left out
Superseded road models (`_road_unet`, `_road_unet_1m`, `_road_unet_multiblock`,
`_road_postfilter`, `_clean_road_network`), the rejected multi-block dataset, and
all one-off exploratory branches (water/streams, ICP change-maps, CHM age-proxy,
hillshade variants, cornrow filter, notebook builders, area-specific predictors,
and the `fetch/` download scripts). They remain in `notebooks/wellsight/`.
