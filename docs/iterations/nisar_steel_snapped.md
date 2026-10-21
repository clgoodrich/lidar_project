# Steel test with wells snapped to lidar features, 9t

**Date:** 2026-10-21. **Status:** done. No signal, and the test has little power.
**Follows:** `docs/iterations/nisar_wells_steel_pads_slopes_9t.md`, section 1.

## Why
The first steel test used raw DEP April 2026 coordinates. DEP positions are unreliable. A miss could be a location error, not a missing signal.

## Method
- Each DEP well (active, plugged, abandoned or orphan) moves to the centroid of the nearest annotated pit (`pit_outside`) or pad (`plat`) within 40 m. Annotations are in `qgis/annotations/annotations_proj.gpkg`, drawn on the lidar.
- 419 of 1,219 wells snapped. Median move 13.3 m. 280 active, 139 plugged or abandoned. 231 on pads, 188 on pits.
- Same stack, steady-bright-target rule and brightness score as the first test (NASA-placed GSLC, D_A < 0.25, 6 dB above 250 m median).
- Comparisons: snapped vs the same wells at raw DEP positions, and snapped vs 532 control pits and pads with no DEP well within 40 m. Radius 15 m and 25 m. Fisher exact for hit rates, Mann-Whitney for brightness.

## Results
| Comparison (radius 15 m) | Wells | Hit rate | Other | Hit rate | p |
|---|---|---|---|---|---|
| Snapped vs controls, all | 419 | 0.7% | 532 | 0.9% | 1.0 |
| Snapped vs raw DEP, all | 419 | 0.7% | 419 | 1.0% | 1.0 |
| Active vs controls | 280 | 0.7% | 532 | 0.9% | 1.0 |
| Abandoned or plugged vs controls | 139 | 0.7% | 532 | 0.9% | 1.0 |

- Brightness medians are 3.6–3.8 dB for every group. No p below 0.05 at 15 m.
- At 25 m, pads with a well hit 0.4% against 2.6% for controls (p 0.048), and pits 4.3% against 2.6% (p 0.32). One of 20 comparisons, unadjusted, opposite directions. Treat as noise.
- Snapping did not raise the hit rate. The first test's null is not a location artefact.

## Power
The rule rarely fires. Only 6, 318 and 36 pixels qualify on tracks 026, 090 and 162. At a 0.7% hit rate, 419 wells give about 3 hits. This test cannot detect a modest enrichment. It rules out a strong one only.

## Interpretation
Moving wells onto lidar-verified features does not reveal a steel signal at 5 m with 10–15 dates. A weak effect would need more dates or a native-resolution method.

## Reproduce
`python notebooks/wellsight_v2/s5_eval/_nisar_steel_snapped_9t.py`

Outputs in `data/9t/results/nisar/`: `nisar_steel_snapped_comparisons_9t.csv`, `nisar_steel_snapped_summary_9t.json`, `nisar_steel_snapped_wells_9t.gpkg`.
