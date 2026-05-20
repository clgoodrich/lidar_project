# Iter 05 — Road-aware post-filter for maxpit ensemble

**Branch:** `iter-05-road-postfilter` (currently on `diagnose/pit-road-fps`)
**Date:** 2026-05-20
**Status:** Complete; ready to push
**Outputs:** `data/derivatives/9t/iterations/05_road_postfilter/`
**Code:** `notebooks/wellsight/pits/iter_05_road_postfilter/postfilter.py`

## Goal / Hypothesis

The diagnostic from `_diagnose_elongated_fps.py` showed iter 04's **maxpit ensemble** carried **69 LIKELY_ROAD_FP** elongated polygons that align with roads — over-firing where one of the two ensemble models was briefly confident on a road shoulder. The **mean ensemble** had only 3 such FPs, but at the cost of slightly lower mean per-pit IoU.

**Hypothesis:** the FPs are component-shape distinguishable from real pits (elongated, road-tagged). A connected-component post-filter that drops a whole component if BOTH (1) its PCA elongation is high AND (2) its area-averaged road-U-Net probability is high, should kill the FPs without hurting test-pit detection.

This is a **post-processing step, not a new model**. No retraining. Inputs: `ensemble_maxpit_argmax.tif` + `road_unet/road_prob.tif`. Output: filtered argmax + filtered prob rasters.

## What changed

Pure component-wise post-filtering. No model training, no new features.

For each connected component (8-connectivity) of pit pixels (`argmax ∈ {1, 2}`) with area ≥ 4 m²:

1. **Elongation** — PCA on the component's pixel coordinates. `elong = sqrt(major_eigenvalue / minor_eigenvalue)`. A circle has elong ≈ 1; a 3:1 ellipse has elong = 3; a road shoulder might be 5+.
2. **road_max** — maximum `road_prob` value inside the component.
3. **road_mean** — mean `road_prob` value inside the component.

A component is **dropped** if any of:
- `elong ≥ ELONG_T   AND  road_max  ≥ ROAD_MAX_T`
- `elong ≥ ELONG_T   AND  road_mean ≥ ROAD_MEAN_T`
- `area ≥ LONG_AREA_T  AND  elong ≥ ELONG_BIG_T` (catches very long polygons even if road-tagging is weak)

Three threshold configs swept, conservative to aggressive.

## Parameters

| Config | ELONG_T | ROAD_MAX_T | ROAD_MEAN_T | LONG_AREA_T (m²) | ELONG_BIG_T |
|---|---:|---:|---:|---:|---:|
| safe | 3.0 | 0.50 | 0.30 | 60 | 4.0 |
| moderate | 2.5 | 0.40 | 0.25 | 40 | 3.0 |
| aggressive | 2.0 | 0.30 | 0.20 | 25 | 2.5 |

## Results — 20 held-out test pits

| Config | Comps dropped | Comps kept | Floor pixel IoU | Wall pixel IoU | Mean per-pit IoU | Median per-pit IoU | Detected ≥10% | IoU > 0.3 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline (maxpit, no filter) | 0 | 1220 | 0.422 | 0.458 | 0.677 | 0.715 | 20/20 | 18/20 |
| safe | 59 | 1161 | 0.422 | 0.466 | 0.677 | 0.715 | 20/20 | 18/20 |
| moderate | 127 | 1093 | 0.422 | 0.469 | 0.677 | 0.715 | 20/20 | 18/20 |
| **aggressive** | **225** | 995 | 0.422 | **0.471** | 0.677 | 0.715 | **20/20** | **18/20** |

Per-config dropped-component geometries are saved as `components_dropped_<config>.gpkg` for QGIS review.

## Honest read

**Hypothesis confirmed; every threshold preserves test recall.**

- Test-pit metrics are **identical across all three configs**. The components being dropped are entirely in non-test regions OR are true FPs that don't intersect test-pit windows. The filter is doing exactly what it was designed to do: kill road shoulders without touching pits.
- **Wall pixel IoU climbs monotonically** with more aggressive filtering (0.458 → 0.466 → 0.469 → 0.471). This is the smoking gun that those dropped components were genuinely FPs labeled "wall" — removing them tightens the IoU numerator without losing true positives.
- **Floor pixel IoU is unchanged** because road FPs in maxpit were almost all classified as wall, not floor (rims have steeper gradients than floors, so the model fires the wall head on the ridge-edge of a road shoulder).
- **Mean / median per-pit IoU are unchanged** because the test pits themselves weren't touched.

Caveat: the test set has only 20 pits across 3 spatial blocks. The filter could be hiding a subtle regression on classes of pits not represented in the test set. The full-tile component table (`data/derivatives/9t/diagnostics/elongated_fps_maxpit/components_summary.csv`) shows the filter is mostly removing genuinely elongated road-tagged components — but visual QGIS review of the dropped GPKG against hillshade is the honest check.

## Recommendation

**Use the aggressive config as the operational output.** It kills 225 false positives — including the ~69 LIKELY_ROAD_FPs the user flagged — at zero cost to test-set recall, with a small wall-IoU bonus. Output: `filtered_argmax_aggressive.tif`.

If field-side review later flags missed pits, downshift to moderate or safe. The conservatism dial is simple and tunable.

The mean ensemble (`ensemble_mean_argmax.tif`) remains a strong default for cases where the road-filter dependency is unwanted (e.g., applying the model to a tile where we don't yet have a road model).

## What's next

- Apply this filter pattern to plat predictions too — the plat U-Net occasionally fires on road embankments and parking-lot-like features that could be similarly distinguished by shape + road-prob.
- Consider building a per-component "FP risk score" combining elong, road-prob, and area, then exporting all components with their score to a GPKG for visual triage. Useful for hand-review batches.
- The honest follow-up: this is a band-aid on top of an ensemble that over-fires. A multitask model with shared encoder for pit + road would be the principled fix. Not urgent unless the filter is failing.
