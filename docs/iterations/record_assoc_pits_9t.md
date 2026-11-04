# Record association against held-out detections, with a shifted-record null (9t)

> **WITHDRAWN as evidence (2026-11-04).** The input was wrong. The loader dropped every row with `dup_on_pit = 1`, which removed all 481 matched pit detections and kept only the 204 unmatched leftovers. The pad file is the unmatched leftover set. The one-to-one proposals are not global (197 rows, 153 unique detections). The numbers below describe unmatched candidates only. The conclusion that orphan records are not above chance does not stand. The corrected result may go either way. See `docs/plans/review_response_20261104.md` and `docs/plans/protocol_gates_and_metrics.md` section 4.

**Date:** 2026-11-04
**Script:** `notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py`
**Plan item:** 5.6 in `docs/iterations/expansion_options_methods.md`

## Goal
Test whether PA DEP well records sit closer to held-out pit and pad detections than chance. This is the first step toward proposing associations between records and terrain features. It does not correct coordinates.

## Inputs
- Pit detections. Out-of-fold held-out detections at cutoff 0.50, layers `matched` and `undecided` of `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg`. Second pieces of one pit (`dup_on_pit` = 1) are dropped. 204 detections remain.
- Pad candidates. `data/9t/results/pit/centroid_matching/pad_candidates_filtered_heldout_9t.shp`, 323 polygons.
- Records. `data/_source/reference/dep_wells/venango_wells_all.gpkg` (DEP export, April 2026), 1,068 wells inside tile 9t. By status. 171 orphan or abandoned, 271 plugged, 616 active (10 not drilled are unused).
- Coverage rule. Cross-validation scores only part of the tile. A record is kept only if it sits in a 250 m cell that holds a detection. Shifted records must also land in such a cell.

## Method
- Rate. Share of records with a detection within r metres, r = 10, 25, 50, 75, 100 (pits) and inside, 25, 50 m (pad polygons).
- Null. The record set is translated by 200 to 500 m in a random direction, 300 times (seed 20261104). It keeps the layout of the records and moves them against the detections. The 2.5 and 97.5 percentiles give the interval.
- Proposals. One-to-one assignment (Hungarian) on distance with a 100 m gate, at pit level only. Pad level allows many records per pad and makes no claim about the borehole position inside it.

## Results
Pit level. Rate and null mean (95% null interval).

| Records | n | 10 m | 25 m | 50 m | 100 m |
|---|---:|---|---|---|---|
| Orphan or abandoned | 90 | 0.000 vs 0.006 (0 to 0.035) | 0.044 vs 0.039 (0 to 0.104) | 0.189 vs 0.148 (0.054 to 0.255) | 0.489 vs 0.480 (0.291 to 0.673) |
| Plugged | 110 | 0.018 vs 0.008 (0 to 0.036) | 0.036 vs 0.047 (0 to 0.111) | 0.155 vs 0.176 (0.080 to 0.293) | 0.482 vs 0.528 (0.393 to 0.673) |
| Active | 278 | 0.040 vs 0.007 (0 to 0.023) | **0.140 vs 0.043 (0.014 to 0.088)** | 0.223 vs 0.162 (0.097 to 0.225) | 0.478 vs 0.501 (0.430 to 0.582) |

Pad level. Rate and null mean (95% null interval).

| Records | n | Inside polygon | Within 25 m | Within 50 m |
|---|---:|---|---|---|
| Orphan or abandoned | 126 | 0.056 vs 0.049 (0.010 to 0.104) | 0.198 vs 0.230 (0.117 to 0.358) | 0.429 vs 0.431 (0.271 to 0.588) |
| Plugged | 171 | **0.076 vs 0.033 (0 to 0.070)** | **0.275 vs 0.164 (0.096 to 0.239)** | 0.433 vs 0.339 (0.249 to 0.442) |
| Active | 372 | **0.116 vs 0.038 (0.013 to 0.068)** | 0.231 vs 0.190 (0.133 to 0.250) | 0.360 vs 0.385 (0.310 to 0.459) |

Proposals (one-to-one within 100 m). Orphan or abandoned 29 of 90 records, 14 within 50 m. Plugged 41 of 110, 16 within 50 m. Active 110 of 278, 56 within 50 m. The mean offset of those within 50 m is small against its error (orphan, east +0.2 m and north +2.4 m, standard error 7 m).

Files in `data/9t/results/records/`. `record_assoc_rates_9t.csv`, `record_pit_assoc_proposals_9t.csv`, `record_assoc_summary_9t.json`, `record_assoc_rates_9t.png`.

## Interpretation
- Orphan and abandoned records are not distinguishable from chance at any radius, for pits or pads. Active records exceed chance at small radii for pits and inside pad polygons. Plugged records exceed chance for pads only.
- One reading is that old records carry larger position error, so proximity fails at the radii tested. This was not tested. Nothing here measures record position error, because no independent coordinates are used.
- Power is low. There are 90 orphan or abandoned records in the covered cells and the null intervals are wide (about ±0.1 at 25 m). At 100 m about half of all records match a pit by chance, so proximity alone cannot justify an accepted association.
- A detection centroid is not a borehole. The proposals file lists candidate pairs. It is not a corrected coordinate set.
- Held-out detections cover only the scored blocks, and there are only 204 of them. A recorded orphan well with no detection may be a missed pit, a well with no pit, or a record in the wrong place.

## Revision 2026-11-04 (coverage repaired after outside review)
The first run kept only records in 250 m cells that held a detection. That conditions the sample on model output and drops scored places where the detector found nothing. The script now uses the scored footprint, the 115 pit-bearing 375 m blocks of `data/9t/derived/05/pit_blocks_9t.gpkg`. Observed and shifted records follow the same rule (inside the footprint and the tile). The whole record set is translated as one, which keeps its clustering. Primary radii are fixed in advance. Pits 50 m and pads inside the polygon. Other radii are sensitivity only. The tables above are the first run and are superseded by the numbers below.

Pit level, repaired. Rate against null mean (95% null interval).

| Records | n | 25 m | 50 m (primary) | 100 m |
|---|---:|---|---|---|
| Orphan or abandoned | 147 | 0.027 vs 0.022 (0 to 0.054) | 0.116 vs 0.086 (0.038 to 0.141) | 0.327 vs 0.302 (0.213 to 0.408) |
| Plugged | 220 | 0.023 vs 0.025 (0.003 to 0.050) | 0.077 vs 0.093 (0.046 to 0.133) | 0.273 vs 0.305 (0.237 to 0.359) |
| Active | 567 | **0.071 vs 0.023 (0.011 to 0.038)** | 0.111 vs 0.090 (0.067 to 0.114) | 0.277 vs 0.309 (0.269 to 0.345) |

Pad level, repaired, inside polygon (primary). Orphan or abandoned 0.041 vs 0.033 (0.007 to 0.070). Plugged 0.050 vs 0.022 (0 to 0.050), at the edge. Active **0.058 vs 0.021 (0.008 to 0.035)**.

The conclusion is unchanged. Orphan and abandoned records are inside the null at the primary radii. Active records exceed chance at small pit radii and inside pad polygons. The larger denominators (147, 220, 567) are records in scored blocks, including blocks with no detection. This is still a proximity test with no independent coordinates. A null result on 9t stops automatic snapping. It does not stop later association work.

## Not done
- Association against the full annotated pits and pads, which would raise power. The annotations are lidar-derived, so the result would measure agreement of records with drawn features.
- Independent coordinates (GNSS points, NETL sites) to test whether any proposal improves a position.
- A null that keeps the clustering of features (for example shifting within a block).

## Reproduce
`python notebooks/wellsight_v2/s5_eval/_record_assoc_pits_9t.py`
