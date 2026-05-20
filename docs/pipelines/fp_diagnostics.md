# False-Positive Diagnostic Pipeline

How to characterize the false positives in any pit-prediction argmax raster and decide whether to post-filter.

## Why this exists

In QGIS, the user observed clusters of elongated parallel polygons in the pit predictions that aren't pits — they sit alongside roads and look like ditches or road shoulders. The diagnostic was built to (a) confirm those polygons are concentrated in the maxpit ensemble (not the mean), (b) quantify how many there are, and (c) supply a categorical / shape-based signal that downstream filters can act on.

## Script

`notebooks/wellsight/pits/_diagnose_elongated_fps.py`

Inputs (paths hardcoded at top of script; edit them to point at any other pit-argmax raster):

| Path | Meaning |
|---|---|
| `data/derivatives/9t/iterations/04_ensemble_01_03/ensemble_maxpit_argmax.tif` | The pit predictions under investigation |
| `data/derivatives/9t/iterations/04_ensemble_01_03/ensemble_maxpit_prob_floor.tif` | Floor-class probability raster |
| `data/derivatives/9t/iterations/04_ensemble_01_03/ensemble_maxpit_prob_wall.tif` | Wall-class probability raster |
| `data/derivatives/9t/road_unet/road_prob.tif` | Road-U-Net's binary road probability (used as the cross-feature) |
| `data/derivatives/9t/hillshade_9t_05.tif`, `data/derivatives/9t/lrm_25_9t_05.tif` | Visualization rasters for the render grids |
| `data/derivatives/annotations/annotations_proj.gpkg` `pit_inside` layer | Truth labels for "this component overlaps a real pit" |

Outputs (under `data/derivatives/9t/diagnostics/elongated_fps_maxpit/`):

| File | What |
|---|---|
| `components_summary.gpkg` | One polygon per connected component (≥ 4 m²) of predicted pit pixels, with all attributes + classification |
| `components_summary.csv` | Same table, no geometry — for quick statistics |
| `classification_counts.json` | Count of components per class |
| `histograms.png` | Area, elongation, road-prob distributions; scatter of elongation vs road-prob coloured by labeled-pit overlap |
| `fp_render_road.png` | Top 12 LIKELY_ROAD_FP samples — hillshade + pit pred + LRM + road-prob overlay |
| `fp_render_elong_other.png` | Top 8 elongated components NOT tagged road-like (potentially interesting) |
| `fp_render_compact.png` | Top 8 compact other FPs (could be unlabeled pits) |

## Per-component features

| Field | Definition |
|---|---|
| `area_m2` | pixel count × 0.25 m² |
| `bbox_h_px`, `bbox_w_px` | Bounding-box height / width in pixels |
| `aspect_ratio_bbox` | `max(h, w) / min(h, w)`. Sensitive to orientation but cheap. |
| `eccentricity` | `sqrt(1 - λ_min / λ_max)` of the pixel-coordinate covariance (range 0–1, 0 = circle, 1 = line) |
| `elongation_pca` | `sqrt(λ_max / λ_min)`. **Primary shape metric.** Circle ≈ 1; 3:1 ellipse = 3; long thin road shoulder = 5+. |
| `solidity_bbox` | `area_px / (bbox_h × bbox_w)`. Crude proxy for "fills its bounding box" — pits should be high, road shoulders moderate. |
| `road_prob_max` | Maximum `road_prob` inside the component |
| `road_prob_mean` | Mean `road_prob` inside the component |
| `pit_prob_max` | Maximum of (floor, wall) prob inside the component |
| `overlaps_labeled_pit` | Boolean — does the component intersect any `pit_inside` polygon? |

## Classification rules

A component is labeled:

| Class | Rule |
|---|---|
| TRUE_PIT_LABELED | `overlaps_labeled_pit == True` |
| LIKELY_ROAD_FP | `(elongation > 3 OR aspect_ratio_bbox > 4) AND (road_max > 0.5 OR road_mean > 0.25)` |
| ELONGATED_OTHER | elongated but not road-tagged — worth manual inspection |
| ROAD_LIKE_COMPACT | road-tagged but not elongated — small road segments or culverts |
| COMPACT_OTHER_FP | neither elongated nor road-tagged, doesn't overlap a labeled pit — most are candidate unlabeled pits but some are FPs |

These categorical labels then drive the post-filter (`notebooks/wellsight/pits/iter_05_road_postfilter/postfilter.py`).

## Counts as of 2026-05-20

Run against `iterations/04_ensemble_01_03/ensemble_maxpit_argmax.tif`:

| Class | Count |
|---|---:|
| TRUE_PIT_LABELED | 107 |
| LIKELY_ROAD_FP | **69** |
| ELONGATED_OTHER | 47 |
| ROAD_LIKE_COMPACT | 435 |
| COMPACT_OTHER_FP | 562 |
| **TOTAL components ≥ 4 m²** | **1220** |

For reference, the same diagnostic against `ensemble_mean_argmax.tif` produced **3** LIKELY_ROAD_FP and 12 ELONGATED_OTHER — confirming the road FPs are a maxpit-specific artifact.

## How to use this on a new pit prediction layer

1. Open `_diagnose_elongated_fps.py`, change `PIT_ARGMAX` / `PIT_PROB_*` constants to point at the new layer.
2. Optionally change `OUTDIR` to a fresh folder.
3. Run. Look at `histograms.png` first — the elongation distribution tail and the elongation-vs-road-prob scatter tell you immediately whether road-shoulder FPs are a problem on this new layer.
4. If yes, follow up with `iter_05_road_postfilter/postfilter.py` (point its constants at the same input).
5. If no, the diagnostic still gives you a per-component table for visual triage in QGIS via `components_summary.gpkg`.
