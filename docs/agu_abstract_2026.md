# AGU 2026 abstract — WellSight

v3, 2026-07-27. 1,994 characters / 303 words (AGU limit 2,000).

v1 was roads-heavy. v2 balanced the three signatures but wrongly presented
Mask R-CNN and YOLO as the method for pits and pads. **U-Net is the method**
across all three targets; the instance detectors were comparison experiments.
v3 fixes that. Earlier versions are in git (`df30913`, `e8692a2`).

---

Pennsylvania carries a 150-year legacy of oil and gas extraction. Hundreds of thousands of abandoned wells remain, many absent from records. These wells leak methane and brine into forests and streams. Field survey across steep, forested terrain is slow and costly. We present a LiDAR framework that detects the surface expressions of orphaned wells in western Pennsylvania. Airborne LiDAR resolves the ground beneath dense canopy, exposing features aerial imagery cannot. We process QL1 and QL2 point clouds into bare-earth models at 0.5 to 1 m. From each we derive terrain channels including local relief models, topographic openness, slope residuals, and Red Relief Image Maps. Orphaned wells leave three recurring marks. Casing depressions form small circular pits. Drilling operations leave graded pads. Access roads survive as shallow benches cut into hillsides. We segment all three with U-Nets trained on the same terrain stack, from 426 annotated pits and 650 annotated pads. A shared-encoder variant predicts all three targets in one pass. The road model adds a clDice loss that keeps traced networks connected across canopy gaps. We score every model with one-to-one matching and report precision alongside recall. Pad recall reaches 0.91 at an IoU of 0.3. Road pixel IoU reaches 0.58 at a line average precision of 0.999. Pit recall falls to 0.55, because semantic blobs do not commit boundaries between adjacent pits. We tested Mask R-CNN and YOLO as instance alternatives. Both lift recall above 0.97 but hold precision below 0.10. Detection volume, not sensitivity, is the limiting problem. We cross-reference detections against 1,069 wells catalogued by the Pennsylvania Department of Environmental Protection. Pad detections match 521 of them within 25 m, a lower bound on wells with surface expression. This work defines a reproducible, validated pipeline for orphaned-well discovery. The same terrain-signature approach transfers to other legacy basins including the Permian.

---

## What changed across versions

| | v1 | v2 | v3 |
|---|---|---|---|
| scope | roads-heavy | balanced | balanced |
| pits / pads | one clause each | own signature + metric | own signature + metric |
| stated method | U-Net (roads only) | **Mask R-CNN / YOLO (wrong)** | **U-Net across all three** |
| instance detectors | absent | presented as the method | presented as comparisons |
| multitask model | absent | absent | named, no numbers claimed |
| unsupported claim | "flag candidate wells missing from state records" | removed | removed |

**The v2 error, plainly.** v2 said "we treat pits and pads as instance
segmentation, training Mask R-CNN and YOLO." That inverted the project. The pit
and pad models are semantic U-Nets on the same terrain stack as the road model.
Mask R-CNN and YOLO were run afterwards to test whether instance architectures
did better. v3 states the U-Net result first and reports the detectors as the
comparison they were.

That change also improves the abstract. One architecture family across three
signatures is a cleaner claim than three unrelated detectors, and it makes the
shared-encoder multitask variant follow naturally.

## Claims and their backing

Numbers trace to `docs/iterations/LEADERBOARD.md`. Semantic-U-Net rows use the
instance metric (`_unet_instance_eval.py`, threshold selected on val, test scored
once frozen) so they are comparable to the detector rows.

| claim | value | source |
|---|---|---|
| QL1 + QL2, 0.5-1 m bare earth | — | 9t, 613590, McKean stacks |
| LRM / openness / slope-residual / RRIM channels | — | [[linear_feature_channels]], [[rrim_visualization]] |
| 426 annotated pits, 650 annotated pads | — | `pit_dataset_manifest.csv`, `plat_dataset_manifest.csv` |
| pad U-Net recall @ IoU 0.3 | 0.91 | `plat_unet` (instance metric) |
| pit U-Net recall @ IoU 0.3 | 0.55 | `pit_unet_v2` (instance metric) |
| road U-Net pixel IoU / line AP | 0.581 / 0.999 | `road_unet_1m_recall` |
| clDice topology loss | — | `road_sweep_202607`, Shit et al. 2021 |
| Mask R-CNN / YOLO recall > 0.97 | 0.97 pit, 0.98 pad | `pit_07_maskrcnn`, `pad_05_maskrcnn` |
| precision < 0.10 | 0.029-0.070 across all rows | every instance row |
| 1,069 DEP wells, 521 pad matches within 25 m | — | `known_well_validation/` |
| shared-encoder multitask variant | trained, **no metric quoted** | [[iter_07_multitask]] |
| transfer to the Permian | — | grids built, pad U-Net inference tested |

⚠️ The multitask model is named but no number is claimed for it. Its iteration
doc still holds only a comparison *plan*, and no metrics file was found. If you
want to cite a multitask result, score it first.

## Voice check
Median sentence 10.5 words, max 20. No em-dashes, semicolons, or prose colons.
Matches the profile measured from the SAOCOM and Urban LiDAR reports in
`docs/related/`.

## One judgment call for the author
The abstract reports pit recall 0.55 and precision below 0.10. Both are real and
both are weaknesses. I recommend keeping them. The pit number carries a genuine
methodological finding, that semantic blobs do not commit boundaries between
adjacent depressions, which is more interesting than a clean score. Cutting the
precision sentence and the matching sentence would free ~150 characters if you
would rather not lead with an open problem.
