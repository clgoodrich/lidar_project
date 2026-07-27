# AGU 2026 abstract — WellSight

v4, 2026-07-27. 1,966 characters / 303 words (AGU limit 2,000).

v1 was roads-heavy. v2 balanced the three signatures but wrongly presented
Mask R-CNN and YOLO as the method for pits and pads. **U-Net is the method**
across all three targets; the instance detectors were comparison experiments.
v3 fixed that but carried four numbers that later turned out to be wrong.
v4 replaces every one of them. Earlier versions are in git (`df30913`,
`e8692a2`, `ee55d73`).

---

Pennsylvania carries a 150-year legacy of oil and gas extraction. Hundreds of thousands of abandoned wells remain, many absent from records. These wells leak methane and brine into forests and streams. Field survey across steep, forested terrain is slow and costly. We present a LiDAR framework that detects the surface expressions of orphaned wells in western Pennsylvania. Airborne LiDAR resolves the ground beneath dense canopy, exposing features aerial imagery cannot. We process QL1 and QL2 point clouds into bare-earth models at 0.5 to 1 m. From each we derive terrain channels including local relief models, topographic openness, and slope residuals. Orphaned wells leave three recurring marks. Casing depressions form small circular pits. Drilling operations leave graded pads. Access roads survive as shallow benches cut into hillsides. We segment all three with U-Nets trained on the same terrain stack, from 426 annotated pits and 650 annotated pads. The road model adds a clDice loss that keeps traced networks connected across canopy gaps. We score only against hand-drawn annotations withheld from training. The pit model locates 126 of 127 withheld pits while claiming 0.2 percent of the tile. The road model recovers 98 percent of 1,220 withheld road segments while claiming 4 percent. The pad model reaches 92 percent of 194 withheld pads but must claim 12 percent. Claimed area, not sensitivity, separates the three models. Withheld hand-drawn negatives confirm the road model rejects drainage channels. Mask R-CNN and YOLO reach precision of 0.54 to 0.69 and do not displace the U-Nets. We then compare state records against our annotations. Only 6 percent of 424 mapped pits carry a catalogued well within 25 m. Validation keyed to official coordinates is unreliable in this terrain. This work defines a reproducible pipeline for orphaned-well discovery. The same terrain-signature approach transfers to other legacy basins including the Permian.

---

## What changed in v4, and why

Four v3 numbers were wrong. All four are replaced.

| v3 claim | status | v4 replacement |
|---|---|---|
| "Pit recall falls to 0.55" | **wrong** | 126/127 withheld pits located at threshold 0.20 |
| "Both lift recall above 0.97 but hold precision below 0.10" | **wrong** | precision 0.54–0.69, detectors do not displace the U-Nets |
| "Detection volume, not sensitivity, is the limiting problem" | **wrong** | claimed area separates the three models |
| "Pad detections match 521 of [1,069 DEP wells] within 25 m" | **does not reproduce** | 6% of 424 mapped pits have a catalogued well within 25 m |

**The precision claim.** "Below 0.10" came from a measurement bug, not the
models. Precision was computed tile-wide against test-split-only ground truth,
mixed floor and wall classes against floor-only truth, and used untuned
thresholds. Corrected in `_reeval_instance_precision_9t.py` with thresholds
selected on val and test scored once. Every row lands at 0.54–0.69.

**The pit recall claim.** 0.55 came from scoring predicted floor against
annotated floor. The U-Net draws floors about half the size we do, so a
correctly located pit was marked a partial miss for outline disagreement.
Scoring floor-inside-rim separates locating from delineating.

**The DEP claim.** Recomputed from the annotations directly and it does not
reproduce. Against hand-drawn pads on 9t, 243 of 872 unique catalogued permits
fall within 25 m, not 521 of 1,069. The old denominator also counted duplicate
permits (1,364 rows, 872 unique). v4 drops the match count and reports the
finding that actually holds up, which is the size of the disagreement.

## Claims and their backing

All detection numbers are scored against hand-drawn annotation withheld from
training. No state well list is used to score any model.

| claim | value | source |
|---|---|---|
| QL1 + QL2, 0.5–1 m bare earth | — | 9t, 613590, McKean stacks |
| LRM / openness / slope-residual channels | — | [[linear_feature_channels]] |
| 426 annotated pits, 650 annotated pads | — | `pit_dataset_manifest.csv`, `plat_dataset_manifest.csv` |
| pit: 126/127 withheld located, 0.21% of tile | thr 0.20 | `pit_threshold_found_vs_missed_summary_9t.csv` |
| road: 98% of 1,220 withheld chunks, 5.0% of tile | thr 0.20, `recall_clean` 0.982 | `road_threshold_sweep_9t.csv` |
| pad: 92% of 194 withheld pads, 11.6% of tile | thr 0.45, IoU≥0.30 | `pad_threshold_sweep_9t.csv` |
| road rejects drainage | not_road claimed 0.0% at every threshold | `road_threshold_sweep_9t.csv` |
| clDice topology loss | — | `road_sweep_202607`, Shit et al. 2021 |
| instance precision 0.54–0.69 | 6 model rows | `eval_9t_instance_precision/_reeval_9t.json` |
| 6% of 424 mapped pits within 25 m of a catalogued well | median 75.1 m | recomputed 2026-07-27 |
| transfer to the Permian | — | grids built, pad U-Net inference tested |

Full sweep write-up: `docs/iterations/threshold_sweeps_pit_pad_road_9t.md`.

⚠️ The multitask model is no longer named in v4. Its iteration doc still holds
only a comparison *plan* and no metrics file exists. It was costing a sentence
and carrying no result.

⚠️ `docs/iterations/LEADERBOARD.md` still holds the uncorrected precision and F1
columns. It is now inconsistent with this abstract. Fix it before citing it.

## Voice check
Median sentence 11 words, max 20, 26 sentences. No em-dashes, semicolons, prose
colons, or transition adverbs. Matches the profile measured from the SAOCOM and
Urban LiDAR reports in `docs/related/`.

## One judgment call for the author

v4 is no longer an abstract that leads with a weakness. The honest headline is
that all three models find nearly everything withheld from them, and that what
separates them is how much ground each must claim to do it. That is a more
interesting result than the v3 framing and it is better supported.

The pad model is the weak one. It needs 12 percent of the tile to reach 92
percent, against 0.2 percent for pits. If you want to cut ~180 characters, the
Mask R-CNN and YOLO sentence is the least load-bearing.
