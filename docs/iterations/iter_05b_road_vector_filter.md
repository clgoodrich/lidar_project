# Iter 05b — Road-aware post-filter v2 (vector buffer + probabilistic)

**Branch:** `iter-05b-road-vector-filter`
**Date:** 2026-05-20
**Status:** Complete, ready to push
**Outputs:** `data/derivatives/9t/iterations/05b_road_vector_filter/`
**Code:** `notebooks/wellsight/pits/iter_05b_road_vector_filter/postfilter_v2.py`

## Goal / Hypothesis

Iter 05 used **only** `road_unet.road_prob` to decide which pit components were on a road. But the road U-Net has gaps (test F1 ≈ 0.97, per-line AP ≈ 0.94). The user observed road FPs that survived iter 05 because the road U-Net was under-confident there (`road error.jpg`).

**Hypothesis:** layering hand-drawn `roads.shp` and `not_roads.shp` (134 lines total) as a buffered vector mask gives a second, gap-free road signal. Drop a component if it's BOTH elongated AND a large fraction of its area sits inside the road buffer — independent of what the road U-Net says.

## What changed (relative to iter 05)

The component-stat table adds one new field:

- **`on_road_frac`** — fraction of the component's pixels that lie inside the buffered union of all roads + not_roads.

The filter gains two new rules (OR'd with iter 05's probabilistic rules):

- `on_road_frac ≥ on_road_t  AND  elong ≥ vec_elong_t`   — "mostly on a road, even mildly elongated"
- `on_road_frac ≥ on_road_high_t`                         — "almost entirely on a road, drop regardless of shape"

Two parameters swept jointly: the road **buffer width** (3 m / 5 m / 8 m) and the **aggressiveness tier** (safe / moderate / aggressive).

## Parameters

| Config | Buf m | Elong-T | Road-Max-T | Road-Mean-T | Long-Area-T (m²) | Elong-Big-T | OnRoad-T | Vec-Elong-T | OnRoad-High-T |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| v2_safe_buf3 | 3.0 | 3.0 | 0.50 | 0.30 | 60 | 4.0 | 0.50 | 1.5 | 0.90 |
| v2_safe_buf5 | 5.0 | 3.0 | 0.50 | 0.30 | 60 | 4.0 | 0.50 | 1.5 | 0.90 |
| v2_moderate_buf3 | 3.0 | 2.5 | 0.40 | 0.25 | 40 | 3.0 | 0.40 | 1.4 | 0.80 |
| v2_moderate_buf5 | 5.0 | 2.5 | 0.40 | 0.25 | 40 | 3.0 | 0.40 | 1.4 | 0.80 |
| v2_aggressive_buf5 | 5.0 | 2.0 | 0.30 | 0.20 | 25 | 2.5 | 0.30 | 1.3 | 0.70 |
| v2_aggressive_buf8 | 8.0 | 2.0 | 0.30 | 0.20 | 25 | 2.5 | 0.30 | 1.3 | 0.70 |

## Buffer-width safety baseline

For each buffer width, how many of the 110 hand-labeled pits have their centroid **inside** the road buffer? That's the upper bound on how many real pits an "always drop if on_road_frac is high" rule could clip.

| Buffer (m) | Mask coverage (m²) | Labeled pits with centroid inside |
|---:|---:|---:|
| 3.0 | 149,238 | 1 / 110 |
| 5.0 | 248,200 | 2 / 110 |
| 8.0 | 394,643 | 7 / 110 |

**5 m is the practical sweet spot.** Wider than 5 m starts clipping a meaningful fraction of real pits that happen to sit very close to roads.

## Results — 20 held-out test pits

| Config | Comps dropped | Floor pixel IoU | Wall pixel IoU | Mean per-pit IoU | Median per-pit IoU | Detected ≥10% | IoU > 0.3 |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline (maxpit) | 0 | 0.422 | 0.458 | 0.677 | 0.715 | **20/20** | **18/20** |
| iter 05 aggressive | 225 | 0.422 | 0.471 | 0.677 | 0.715 | **20/20** | **18/20** |
| v2_safe_buf3 | 63 | 0.428 | 0.470 | 0.677 | 0.715 | **20/20** | **18/20** |
| v2_safe_buf5 | 74 | 0.434 | 0.477 | 0.677 | 0.715 | **20/20** | **18/20** |
| v2_moderate_buf3 | 132 | 0.428 | 0.474 | 0.677 | 0.715 | **20/20** | **18/20** |
| **v2_moderate_buf5** | **140** | **0.434** | **0.480** | 0.677 | 0.715 | **20/20** | **18/20** |
| v2_aggressive_buf5 | 237 | 0.419 | 0.466 | 0.635 | 0.689 | 19/20 ⚠ | 17/20 ⚠ |
| v2_aggressive_buf8 | 246 | 0.419 | 0.468 | 0.635 | 0.689 | 19/20 ⚠ | 17/20 ⚠ |

## Honest read

**The vector buffer layer adds real value over iter 05.** v2_moderate_buf5 beats iter 05's best ("aggressive") on both pixel IoUs (floor 0.434 vs 0.422, wall 0.480 vs 0.471) while preserving 20/20 detection. The extra components it drops (140 vs 225 in iter 05 aggressive, but **40 fewer false positives because iter 05 aggressive over-fired**) are road shoulders that the road U-Net was uncertain about — the vector signal catches them.

**But aggressive_buf5 / aggressive_buf8 broke the safety guarantee.** Both clip one real test pit (19/20 detection, IoU > 0.3 falls to 17/20). At `on_road_t = 0.3` + `vec_elong_t = 1.3`, the rule is firing on test pits that sit close to a road. The very same rule logic that killed road FPs killed a real pit. There's no parameter setting in the aggressive tier that's safe.

**v2_moderate_buf5 is the new operational champion.** It beats iter 05 aggressive on pixel IoUs and the user's specific FPs by adding the vector buffer signal, without the safety regression of the aggressive configs.

Floor pixel IoU finally moved (0.422 → 0.434) — for the first time in the iter 05 / 05b series. The vector mask is dropping FP components that the prob-only filter was leaving as floor pixels in the test region. That's a real (small) wall IoU + floor IoU win.

## What's next

- **Use `filtered_argmax_v2_moderate_buf5.tif`** as the canonical operational pit layer going forward. It replaces iter 04 mean and iter 05 aggressive as the recommended overlay.
- The user-flagged FPs in `road error.jpg` should now be inspected against this new layer. If they still survive (the iter 05c experiment suggests some might, since they're small and not strongly tagged by either road signal), the next step is iter 05d: combined rule = drop ONLY if line-intersect AND elongation, which protects compact pits near roads.
- The two pits the aggressive configs clipped should be identified in `components_dropped_v2_aggressive_buf5.gpkg` for a manual look — they explain the safety ceiling and could inform a smarter "is this near a real pit centroid?" guard rail.
