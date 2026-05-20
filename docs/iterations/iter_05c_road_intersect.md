# Iter 05c — Road-line-through-polygon filter (rejected experiment)

**Branch:** `iter-05c-road-intersect`
**Date:** 2026-05-20
**Status:** Complete; **rejected** — does not beat iter 05b moderate_buf5 and loses 2 test pits
**Outputs:** `data/derivatives/9t/iterations/05c_road_intersect/`
**Code:** `notebooks/wellsight/pits/iter_05c_road_intersect/postfilter_v3.py`

## Goal / Hypothesis

Iter 05 / 05b both use **buffered** roads — measure how much of the pit polygon falls inside a buffered union of road lines. Buffer width has to be tuned and trades safety against coverage.

**Hypothesis:** a more geometric formulation is cleaner — **directly intersect the road line with the polygon** and ask whether the line passes through. No buffer width to tune; a road that runs through a polygon is exactly what road-shoulder FPs look like, while a road near a pit only grazes the pit's edge.

Two new per-component fields:
- `intersect_len_m` — total length of road / not_road line within the component polygon.
- `cross_frac = intersect_len_m / eq_diam_m` — line length normalized by the polygon's equivalent diameter. Catches small components where any crossing is suspicious.

Drop a component if **either** `intersect_len_m ≥ MIN_THROUGH_M` or `cross_frac ≥ FRAC_T`. OR'd with the iter 05 probabilistic rules.

## What changed

`postfilter_v3.py`:
- Same component-stats loop as iter 05/05b, plus the geometric intersection over each component polygon vs each of the 134 road / not_road lines (via STRtree for fast candidate lookup).
- Filter rules add the two new line-based clauses.
- Writes an `all_components.gpkg` with every component + all attributes, for QGIS triage independent of the chosen filter config.

## Safety baseline

Sanity check against the truth labels: **how many of the 110 labeled pits have any road or not_road line passing through their polygon?** Answer: **1 / 110**. So the geometric ceiling for "drop everything with a line through it" is to lose at most 1 truth pit.

But that ceiling is measured against **truth polygons**, and the filter operates on **predicted polygons**, which are bigger and looser. Predicted pits extend beyond their truth boundary and catch road lines that don't actually touch the truth pit. That's the failure mode.

## Results — 20 held-out test pits

| Config | Comps dropped | Floor pixel IoU | Wall pixel IoU | Mean per-pit IoU | Median per-pit IoU | Detected ≥10% | IoU > 0.3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline (maxpit) | 0 | 0.422 | 0.458 | 0.677 | 0.715 | **20/20** | **18/20** |
| v3_safe | 72 | 0.383 | 0.432 | 0.600 | 0.676 | 18/20 ⚠ | 16/20 ⚠ |
| v3_moderate | 138 | 0.383 | 0.434 | 0.600 | 0.676 | 18/20 ⚠ | 16/20 ⚠ |
| v3_aggressive | 237 | 0.383 | 0.437 | 0.600 | 0.676 | 18/20 ⚠ | 16/20 ⚠ |
| v3_line_only | 13 | 0.383 | 0.424 | 0.600 | 0.676 | 18/20 ⚠ | 16/20 ⚠ |

Every config drops 20/20 detection to **18/20**, including `v3_line_only` which uses *nothing* but the line-intersect rule and only drops 13 components.

## Honest read — what went wrong

The geometric premise was tighter than the practical reality.

1. **Predicted polygons leak past truth boundaries.** Pit U-Net predictions slightly over-extend the labeled rim. Two of the 20 test pits have predicted components large enough to clip a nearby road centerline, even though the road doesn't actually touch the labeled pit. The line-intersect rule sees "road passes through predicted polygon" and drops the whole component, taking the real pit with it.

2. **The 13 components `v3_line_only` drops include 2 that overlap test pits.** That's why all four configs show identical test-set metrics — the carnage is from the line rule, not the probabilistic rules. The probabilistic rules drop additional FPs in the unlabeled regions of the tile, but every config pays the same fixed cost on the test set from the line rule.

3. **The geometric distinction "line passes through polygon vs grazes it" doesn't reliably separate FP-on-road from real-pit-near-road.** Real pits next to roads have predicted components that bulge toward the road; bumpy boundary noise can mean a road line clips the bulge by ~1 m. That clip is enough to trigger MIN_THROUGH_M = 1.0.

Tightening thresholds didn't help because the failure mode is on the polygon-boundary side, not the line-distance side. Even `min_through_m = 2.0 AND cross_frac = 0.8` (the most conservative v3_safe config) still loses 2 pits because the bulges are wider than 2 m.

## Verdict

Iter 05c is rejected. Iter 05b `moderate_buf5` remains the operational champion (20/20, floor IoU 0.434, wall IoU 0.480).

The line-intersect signal isn't useless — it's just that using it as an independent OR clause clips real pits. A version that uses it **only as a tiebreaker** (e.g., drop only if line passes through AND component is elongated AND road probability is moderate) might work; that's the proposed iter 05d.

## What's next

- **Iter 05d (combined rule)** — line-intersect AND elongation. The geometric signal is real for FPs that are unambiguously long-and-thin and unambiguously road-crossing. Compact pits near roads (which get clipped by the current 05c rules) don't satisfy the elongation requirement, so they survive.
- If iter 05d still regresses, the line-intersect concept should be retired — multitask training (shared encoder for pit + road) is the principled fix instead.
- The `all_components.gpkg` produced by this iter is still useful as a QGIS triage layer independent of the filter — every predicted pit component + its full attribute set in one file.
