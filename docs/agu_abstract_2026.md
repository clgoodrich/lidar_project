# AGU 2026 abstract — WellSight

v2, 2026-07-27. 1,988 characters / 301 words (AGU limit 2,000).

v1 was roads-heavy. v2 gives equal weight to all three well signatures — pits,
pads, and roads. v1 is in git history (`df30913`).

---

Pennsylvania carries a 150-year legacy of oil and gas extraction. Hundreds of thousands of abandoned wells remain, and many are absent from official records. These orphaned wells leak methane and brine into forests and streams. Field survey across steep, forested terrain is slow and expensive. We present a LiDAR framework that detects the surface expressions of orphaned wells in western Pennsylvania. Airborne LiDAR resolves the ground beneath dense canopy, exposing features that aerial imagery cannot. We process QL1 and QL2 point clouds into bare-earth models at 0.5 to 1 m resolution. From each model we derive terrain channels including local relief models, topographic openness, slope residuals, and Red Relief Image Maps. Orphaned wells leave three recurring marks. Casing depressions form small circular pits. Drilling operations leave graded pads. Access roads survive as shallow benches cut into hillsides. We treat pits and pads as instance segmentation, training Mask R-CNN and YOLO on 426 annotated pits and 650 annotated pads. We treat roads as semantic segmentation and train a U-Net with a topology-preserving clDice loss. The loss keeps traced networks connected across canopy gaps that pixel-wise losses fragment. Every model is scored with one-to-one instance matching. We report precision alongside recall. Recall reaches 0.97 for pits and 0.98 for pads at an IoU of 0.3. Precision stays below 0.10, so detection volume rather than sensitivity is the limiting problem. We cross-reference detections against 1,069 wells catalogued by the Pennsylvania Department of Environmental Protection. The pad detector matches 521 of them within 25 m, a lower bound on wells with surface expression. We are testing directional metrics and ridge filters that separate engineered features from natural slope breaks. This work defines a reproducible, validated pipeline for orphaned-well discovery. The same terrain-signature approach transfers to other legacy basins including the Permian.

---

## What changed from v1

| | v1 | v2 |
|---|---|---|
| pit content | one clause in a list | its own signature, model, and metric |
| pad content | one clause in a list | its own signature, model, and metric |
| road content | 4 sentences incl. clDice detail | 2 sentences, clDice kept |
| results reported | roads only, qualitative | pits, pads, and the DEP cross-reference, quantitative |
| unsupported claim | "flag candidate wells missing from state records" | **removed** |

v1's closing result claim was not demonstrated — no validated list of
undocumented candidate wells exists. v2 replaces it with the DEP cross-reference,
which is measured and already in the leaderboard.

## Claims and their backing

Every number traces to `docs/iterations/LEADERBOARD.md` (instance rows re-scored
2026-07-02 on the 65-pit / 93-pad test split, one-to-one matching).

| claim | source |
|---|---|
| QL1 + QL2, 0.5–1 m bare earth | 9t, 613590, McKean stacks |
| LRM / openness / slope-residual / RRIM channels | [[linear_feature_channels]], [[rrim_visualization]] |
| 426 annotated pits, 650 annotated pads | `pit_dataset_manifest.csv`, `plat_dataset_manifest.csv` |
| Mask R-CNN + YOLO for pits and pads | pit_07/pit_08, pad_05/pad_06 |
| pit recall 0.97 @ IoU 0.3 | pit_07_maskrcnn |
| pad recall 0.98 @ IoU 0.3 | pad_05_maskrcnn |
| precision below 0.10 | 0.029–0.064 across all four instance models |
| U-Net + clDice for roads | `road_sweep_202607`, Shit et al. 2021 |
| 1,069 catalogued DEP wells, 521 pad matches within 25 m | `known_well_validation/` |
| directional metrics + ridge filters | built and QC'd, [[linear_feature_channels]] |
| transfer to the Permian | grids built, pad U-Net inference tested |

## Voice check
Median sentence 13.5 words. No em-dashes, semicolons, or prose colons. Matches
the profile measured from the SAOCOM and Urban LiDAR reports in `docs/related/`.

## One judgment call for the author
Reporting precision below 0.10 is honest and, in my view, a strength — it names
the real open problem rather than hiding it. If you would rather not lead with a
weakness at a conference, the alternative is to cut that sentence and the
one-to-one matching sentence, freeing ~180 characters. I recommend keeping them.
