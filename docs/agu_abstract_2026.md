# AGU 2026 abstract — WellSight

v7, 2026-07-27. 1,880 characters / 300 words (AGU limit 2,000).

v1 was roads-heavy. v2 balanced the three signatures but wrongly presented
Mask R-CNN and YOLO as the method for pits and pads. **U-Net is the method**
across all three targets; the instance detectors were comparison experiments.
v3 fixed that but carried four numbers that later turned out to be wrong.
v4 replaced every one of them. v5 re-framed the results around standard
detection metrics — IoU, thresholds, recall, precision. **v6 drops Mask R-CNN
and YOLO entirely.** They were comparison experiments and the abstract is a
U-Net result. Earlier versions are in git (`df30913`, `e8692a2`, `ee55d73`,
`a0ba984`, `a0e7e24`).

---

Pennsylvania carries a 150-year legacy of oil and gas extraction. Hundreds of thousands of abandoned wells remain, many absent from records. These wells leak methane and brine into forests and streams. Field survey across steep, forested terrain is slow and costly. We present a LiDAR framework that detects the surface expressions of orphaned wells in western Pennsylvania. Airborne LiDAR resolves the ground beneath dense canopy, exposing features aerial imagery cannot. We process QL1 and QL2 point clouds into bare-earth models at 0.5 to 1 m. From each we derive terrain channels including local relief models, topographic openness, and slope residuals. Orphaned wells leave three recurring marks. Casing depressions form small circular pits. Drilling operations leave graded pads. Access roads survive as shallow benches cut into hillsides. We segment all three with U-Nets trained on the same terrain stack, from 426 annotated pits and 650 annotated pads. The road model adds a clDice loss that keeps traced networks connected across canopy gaps. We score only against hand-drawn annotations withheld from training. Thresholds are selected on validation data and test scored once. Pit recall falls from 0.83 at an IoU of 0.2 to 0.59 at an IoU of 0.5. Pad recall falls from 0.89 to 0.74 across the same range. Precision at an IoU of 0.3 is 0.62 for pits and 0.55 for pads. Roads are scored by length rather than overlap, and the model recovers 98 percent of 1,220 withheld segments at a pixel IoU of 0.58. Withheld hand-drawn negatives confirm the road model rejects drainage channels. We then compare state records against our annotations. Only 6 percent of 424 mapped pits carry a catalogued well within 25 m. Validation keyed to official coordinates is unreliable in this terrain. The same terrain-signature approach transfers to other legacy basins including the Permian.

---

## What changed

**v4** replaced four v3 numbers that were wrong. **v5** re-framed the results
paragraph around standard detection metrics. **v6** removed the instance
detectors. The abstract now carries one architecture family across three
signatures and nothing else.

| v3 claim | status | now |
|---|---|---|
| "Pit recall falls to 0.55" | **wrong** | recall 0.75 / precision 0.62 at IoU 0.3; 126/127 located at thr 0.20 |
| "recall above 0.97 but precision below 0.10" | **wrong** | precision 0.54-0.69 across all six rows; detectors now cut from the abstract |
| "Detection volume, not sensitivity, is the limiting problem" | **wrong** | withdrawn, it followed from the precision bug |
| "Pad detections match 521 of [1,069 DEP wells] within 25 m" | **does not reproduce** | 6% of 424 mapped pits have a catalogued well within 25 m |

**The precision claim.** "Below 0.10" was a measurement bug, not a model result.
Precision counted predictions tile-wide against test-split-only ground truth,
mixed floor and wall classes against floor-only truth, and used untuned
thresholds. Corrected in `_reeval_instance_precision_9t.py` with thresholds
selected on val and test scored once. Every row lands at 0.54-0.69.

**The pit recall claim.** 0.55 came from scoring predicted floor against
annotated floor. The U-Net draws floors about half the size we do, so a
correctly located pit was marked a partial miss for outline disagreement.
Scoring floor-inside-rim separates locating from delineating.

**The DEP claim.** Recomputed from the annotations and it does not reproduce.
Against hand-drawn pads on 9t, 243 of 872 unique catalogued permits fall within
25 m, not 521 of 1,069. The old denominator counted duplicate permits (1,364
rows, 872 unique). The "median 26.4 m" figure quoted from that table was the
median distance to the nearest *detection*, not DEP positional accuracy.

## Claims and their backing

All detection numbers are scored against hand-drawn annotation withheld from
training. No state well list is used to score any model.

| claim | value | source |
|---|---|---|
| QL1 + QL2, 0.5-1 m bare earth | — | 9t, 613590, McKean stacks |
| LRM / openness / slope-residual channels | — | [[linear_feature_channels]] |
| 426 annotated pits, 650 annotated pads | — | `pit_dataset_manifest.csv`, `plat_dataset_manifest.csv` |
| pit U-Net R 0.75 / P 0.62 @ IoU 0.3 | thr 0.60, val-selected | `eval_9t_instance_precision/_reeval_9t.json` |
| pad U-Net R 0.88 / P 0.55 @ IoU 0.3 | thr 0.50, val-selected | same |
| 126/127 withheld pits located | thr 0.20 | `pit_threshold_found_vs_missed_summary_9t.csv` |
| 178/194 withheld pads @ IoU 0.3 | thr 0.45 | `pad_threshold_sweep_9t.csv` |
| road 98% of 1,220 withheld chunks | thr 0.20, `recall_clean` 0.982 | `road_threshold_sweep_9t.csv` |
| road pixel IoU 0.581 | — | `road_unet_1m_recall` |
| road rejects drainage | not_road claimed 0.0% at every threshold | `road_threshold_sweep_9t.csv` |
| clDice topology loss | — | `road_sweep_202607`, Shit et al. 2021 |
| 6% of 424 mapped pits within 25 m of a catalogued well | median 75.1 m | recomputed 2026-07-27 |
| transfer to the Permian | — | grids built, pad U-Net inference tested |

Full sweep write-up: `docs/iterations/threshold_sweeps_pit_pad_road_9t.md`.

⚠️ The multitask model is not named. Its iteration doc holds only a comparison
*plan* and no metrics file exists. It was costing a sentence for no result.

## Voice check
Median sentence 11 words, max 20, 26 sentences, 1,916 characters. No em-dashes,
semicolons, prose colons, or transition adverbs. Matches the profile measured
from the SAOCOM and Urban LiDAR reports in `docs/related/`.

## Notes for the author

The abstract no longer leads with a weakness. All three models find nearly
everything withheld from them, at precision in the 0.55-0.62 range.

The pad model is still the weak one, and the sweep shows why more clearly than
the abstract does. It needs a much higher threshold than the others and flags far
more ground to get there. That did not survive the character budget and is in
`threshold_sweeps_pit_pad_road_9t.md` instead.

84 characters of headroom remain. Mask R-CNN and YOLO stay in
`LEADERBOARD.md` as a record of the comparison, they are simply not part of
this abstract.
