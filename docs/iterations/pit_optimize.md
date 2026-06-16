# Iteration: `_pit_optimize.py` — pit candidate extraction (road pattern → pits)

**Date:** 2026-06-16
**Script:** `notebooks/wellsight_v2/build/_pit_optimize.py`
**Status:** working end-to-end on 9t; precision low (expected) → feeds active-learning loop

## Goal
Port the road post-processing pattern to pits. Roads are linear (skeleton →
centerlines, via `_road_optimize.py`); pits are 2-D depressions, so the analog is
**threshold → connected components → shape filter → polygonize → centroid**, where
the centroid is a candidate well location. Same CLI/harness shape as the road script
(`optimize` mode tunes against GT; `--apply-block` runs the winner on any block).

## Inputs / provenance
- **Prob:** `data/derivatives/tiles/9t/pit_unet_v2/pit_prob_floor.tif` (+ `pit_argmax.tif`),
  from the retrained `_pit_unet_v2` (3-class bg/floor/wall, 0.5 m).
- **Ground truth:** `annotations_proj.gpkg` layer `pit_inside` (floor polygons);
  65 fall in the 9t `split=='test'` blocks (`pit_blocks_9t.gpkg`).
- **CRS:** EPSG:6346 throughout.

## Method
- **Stages:** `enhance` (none|gauss) → `to_mask` (global|otsu|hysteresis, optional
  argmax==floor gate, close+fill+remove-small) → `blobs` (label, polygonize, filter by
  area_min/max m², circularity ≥, eccentricity ≤).
- **Match (object-level):** greedy nearest centroid within **TOL = 6 m**;
  precision/recall/F1 over candidate count.
- **Optimize:** coordinate-ascent, 2 passes over
  {enhance, thresh, floor_gate, t, area_min, area_max, circ_min, ecc_max, min_px}.

## Results (9t test region, all blobs, no confidence gate)
| metric | value |
|---|---|
| **F1** | **0.195** |
| recall | 0.85 |
| precision | 0.11 |
| candidates | ~500 (vs 65 GT) |

Best config: `enhance=gauss, thresh=hysteresis(0.4/0.6), floor_gate=off,
area 9–1500 m², circ≥0.45, ecc≤0.88, min_px=12` →
`pit_unet_v2/pit_postproc_best.json`.

## Interpretation
The extractor is correct and runs clean; raw **precision is low because the floor prob
over-detects** (small dataset, leaky blobs — the same root cause as the instance-model
overfit). High recall + low precision is exactly the right starting point for the
**active-learning loop**: surface many candidates → human rejects junk in QGIS → rejects
become hard negatives → retrain. The `--apply` confidence gate
(`0.6·mean_pfloor + 0.4·shape`) trims FPs before review, and candidates carry
`confidence` + `dist_well_m` (nearest known well) per the QC rule.

## Reproduce
```bash
# optimize on 9t (writes pit_postproc_best.json; ~5 min, loads the 240 MB floor prob)
python notebooks/wellsight_v2/build/_pit_optimize.py

# apply to a block's floor prob -> pits_opt_<key>_1m.gpkg (pits_all / pits_clean / pit_points)
python notebooks/wellsight_v2/build/_pit_optimize.py \
    --apply-block data/derivatives/tiles/data_3x3/westernpa_d20/613590 \
    --apply-key 613590 --prob <pit_prob_floor.tif> --wells output_wells.csv
```

## Next
1. Pit review-package + corrections-diff (polygon analogs of `_build_road_review_package.py`
   / `_road_corrections_diff.py`).
2. Retrain `_pit_unet_v2` on corrected 613590 pits (rejects → hard negatives).
3. Add a confidence-gated variant to the optimize harness so F1 reflects the deployed gate.

See [[project_road_active_learning_loop]], `_road_optimize.py`.
