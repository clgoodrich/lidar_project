# AGU 2026 abstract — WellSight

v13, 2026-07-28. 1,993 characters / 322 words (AGU limit 2,000 characters).

**v13 makes the pad numbers cross-validated too.** The pad 5-fold run finished,
so both models are now scored the same way and the asymmetry flagged in v9 is
gone. Pad recall 0.88 to 0.92 at IoU 0.3, precision 0.55 to 0.61. The sentence
now reads "both models" and "every pit and pad". Paid for by dropping the second
"annotated" in "426 annotated pits and 650 pads".

**v11 added a closing sentence** on scope and next steps, paid for by four
redundancy trims. **v12 is the author's edit to that sentence**, naming the
scope as the rest of Pennsylvania rather than "new terrain". That is the
stronger claim, since it is bounded and checkable, and we already hold McKean
and Venango data outside 9t. It costs 13 characters.

⚠️ **Only 7 characters of headroom remain.** If AGU's counter normalises
whitespace or counts anything beyond the body, this goes over with no room to
react. The cheapest 12 characters back, at no loss of meaning, is
"the rest of Pennsylvania" to "Pennsylvania" — the western PA study area is
already established three sentences earlier.

**v10 is the author's rewrite.** He opened with the historical boom instead of
the statistics, cut the DEP-coordinate finding, cut the Permian transfer, and
cut the clDice sentence. Those are his calls and they stand. Two factual
corrections and a length fix were applied on top, listed under "Corrections
applied to the v10 draft" below.

v1 was roads-heavy. v2 balanced the three signatures but wrongly presented
Mask R-CNN and YOLO as the method for pits and pads. **U-Net is the method**
across all three targets; the instance detectors were comparison experiments.
v3 fixed that but carried four numbers that later turned out to be wrong.
v4 replaced every one of them. v5 re-framed the results around standard
detection metrics — IoU, thresholds, recall, precision. **v6 drops Mask R-CNN
and YOLO entirely.** They were comparison experiments and the abstract is a
U-Net result. **v9 replaces the pit numbers with 5-fold cross-validated ones**
covering all 426 pits instead of one 65-pit split. Earlier versions are in git
(`df30913`, `e8692a2`, `ee55d73`, `a0ba984`, `a0e7e24`, `3c63c2e`).

---

Orphan and abandoned wells are an ongoing problem across North America. During the 19th century, thousands of wells were drilled in western Pennsylvania, representing the North American oil boom. This boom was wild and reckless and poorly documented, leaving the hills and valleys riddled with potentially dangerous wells leaking methane and brine into forests and streams. Given the heavy vegetation in the area, locating these wells involves countless hours on foot or reliance on landowners or hikers. We present a lidar-based framework to detect the surface expressions of orphaned wells. Airborne lidar resolves the ground beneath the dense deciduous canopy, revealing terrain that optical imagery cannot capture. We process US Geological Survey 3D Elevation Program 2019 swaths over this region into 0.5 and 1 meter resolution models. For each model we derive a stack of terrain channels including local relief models, topographic openness, and slope residuals. Older wells leave three recurring signs. These are graded pads marking the site, access roads, and shallow depressions. We segment all three with U-Nets trained on the same terrain stack, from 426 annotated pits and 650 pads. We score only against hand-drawn annotations withheld from training. Thresholds are selected on validation data and test scored once. We cross-validate both models five ways, so every pit and pad is scored by a model that never saw it. Pit recall falls from 0.85 at an IoU of 0.3 to 0.61 at an IoU of 0.6. Pad recall falls from 0.92 to 0.62 across the same range. Precision at an IoU of 0.3 is 0.62 for pits and 0.61 for pads. Roads are scored by length rather than overlap, and the model recovers 98 percent of 1,220 withheld segments at a pixel IoU of 0.58. Withheld hand-drawn negatives confirm the road model rejects drainage channels. These results come from one survey area, and current work extends the framework to the rest of Pennsylvania and to field validation of undocumented candidates.

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
| pit U-Net R 0.85 / P 0.62 @ IoU 0.3 | 5-fold CV, all 426 pits, per-fold thr val-selected by F1 | `pit_unet_cv5/pit_cv5_per_fold_9t.csv` |
| pit U-Net R 0.61 @ IoU 0.6 | same five thresholds held fixed across IoU | `pit_unet_cv5/pit_cv5_iou_strictness_scale_9t.csv` |
| pit U-Net R 0.75 / P 0.62 @ IoU 0.3 | **superseded by the CV rows above**, single 65-pit split, thr 0.60 | `eval_9t_instance_precision/_reeval_9t.json` |
| pad U-Net R 0.92 / P 0.61 @ IoU 0.3 | 5-fold CV, all 650 pads, per-fold thr val-selected by F1 | `pad_unet_cv5/pad_cv5_per_fold_9t.csv` |
| pad U-Net R 0.62 @ IoU 0.6 | same five thresholds held fixed across IoU | `pad_unet_cv5/pad_cv5_iou_strictness_scale_9t.csv` |
| pad U-Net R 0.88 / P 0.55 @ IoU 0.3 | **superseded by the CV rows above**, single 93-pad split, thr 0.50 | same |
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

## The closing sentence

The v10 draft ended on the drainage-rejection result, which is a detail, not a
conclusion. v11 closes with:

> These results come from one survey area, and current work extends the
> framework to the rest of Pennsylvania and to field validation of undocumented candidates.

**Why this one.** It does two jobs in one sentence. The first clause states the
limitation that every number on this page shares, which is that 9t is one
landscape, one survey, one canopy condition, one annotator. Cross-validation
proved our numbers are *stable*. It did not prove they *transfer*. Saying so
first is what makes the second clause credible rather than promotional.

The second clause names the two things that would actually settle it. Scoring on
terrain we have not annotated tests transfer. Field validation tests whether a
detected signature is a well at all, which no amount of held-out annotation can
answer, because our ground truth is our own interpretation of the same terrain
the model sees.

**What it deliberately does not claim.** No count of undocumented wells found.
No accuracy figure for a region we have not scored. No completion date. Every
one of those would be a promise the results do not support.

**Paid for by four trims**, since v10 had 13 characters spare and the sentence
needs 146.

| cut | saved | why it was safe |
|---|---|---|
| "These channels enhance the local signatures that mark well site expressions." | 77 | asserts a purpose without adding content. The next sentences show what the channels are for. |
| "in many regions of North America" to "across North America" | 11 | same meaning, fewer words |
| "the hills and valleys **of western Pennsylvania**" | 23 | the location is named in the sentence immediately before |
| "**Older well drilling in the region** leaves three recurring signs" to "Older wells leave" | 23 | same claim |
| "swaths **collected** over this region" | 10 | the verb is implied |

Final 1,984 characters, 16 spare.

## Corrections applied to the v10 draft

The draft came in at **2,049 characters, 49 over the AGU limit**, so something
had to go regardless.

**Two factual corrections.**

| draft said | problem | now |
|---|---|---|
| "into 1 meter resolution models" | the pit and pad stacks are **0.5 m** (`features_pit_9t_05.tif`). Only the road model is 1 m. Every pit and pad number in the results comes from 0.5 m data. | "into 0.5 and 1 meter resolution models" |
| channels include "red relief image maps" | **RRIM is not a model input.** The training stack is exactly 7 bands: `lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11`. RRIM is a visualization product. `diff_openness` is documented as the Chiba RRIM base in `_build_extra_channels.py` but is not in `DEFAULT_CHANNELS`. | phrase removed |

The RRIM claim is the dangerous one. It is checkable, and a reviewer who checks
it finds the channel list does not contain it.

**Verified and left alone.** 3DEP 2019 is right for 9t (~4 pts/m², 2019 D20,
`docs/methodology.md`). 426 pits and 650 pads match the manifests.

**Typos fixed.** poorely, methan, forets, presend, framewor, conduceed. Also
"Western Pennsylvania" lowercased to match the other two uses.

**Four wording edits, all minor.**

1. "resolves the ground into the dense deciduous canopy" reads backwards. Now
   "beneath the dense deciduous canopy".
2. "terrain that optical imagery is unable to process" — imagery does not
   process. Now "terrain that optical imagery cannot capture".
3. "swaths conduceed over this region" — surveys are flown or collected, not
   conducted. Now "collected".
4. "Graded pads marking the location of the site, access roads, and shallow
   depressions" was a sentence fragment. Now "These are graded pads marking the
   site, access roads, and shallow depressions."

**Length trims** to get from 2,049 under 2,000. Dropped the third
"in western Pennsylvania" (already said twice) and shortened "These channels are
used to enhance" to "These channels enhance". Final 1,987, 13 characters spare.

**Voice note.** This draft runs longer sentences than v8 did — median 17 words
against 11, max 30 against 24. That is a deliberate change of register, from
clipped declaratives to narrative. Not corrected.

## The pit numbers are now cross-validated

v8 quoted pit recall 0.75 at IoU 0.3, from one split of 65 test pits. That
split drew a hard fifth of the tile, and its val-selected threshold of 0.60
sits past the point where recall falls away.

Five models were trained, each holding out a different fifth. All 426 pits are
scored, each by a model that never saw it. Thresholds are selected on an inner
val split under an objective named before scoring, and held fixed across every
IoU.

| IoU required | v8 (single split) | v9 (5-fold CV) |
|---|---|---|
| 0.30 | 0.754 | **0.854** |
| 0.40 | 0.662 | 0.805 |
| 0.50 | 0.585 | 0.711 |
| 0.60 | 0.446 | **0.606** |

Precision at IoU 0.3 is 0.617, which still rounds to the 0.62 already in the
abstract. Per-fold recall at IoU 0.3 spans 0.736 to 0.954.

**The pad numbers are still single-split.** A pad CV is running. Until it
finishes, the pad sentence carries an optimism the pit sentence no longer does,
and the two are not scored the same way. Full write-up in
`docs/iterations/pit_unet_cv5_9t.md`.

## Voice check
Median sentence 11 words, max 24, 26 sentences, 1,976 characters. No em-dashes,
semicolons, prose colons, or transition adverbs. Matches the profile measured
from the SAOCOM and Urban LiDAR reports in `docs/related/`. The 24-word maximum
is the pre-existing roads sentence, unchanged in this version.

## Notes for the author

The abstract no longer leads with a weakness. All three models find nearly
everything withheld from them, at precision in the 0.55-0.62 range.

The pad model is still the weak one, and the sweep shows why more clearly than
the abstract does. It needs a much higher threshold than the others and flags far
more ground to get there. That did not survive the character budget and is in
`threshold_sweeps_pit_pad_road_9t.md` instead.

24 characters of headroom remain, down from 84. The cross-validation sentence
spent the rest. Anything further added has to displace something. Mask R-CNN
and YOLO stay in
`LEADERBOARD.md` as a record of the comparison, they are simply not part of
this abstract.
