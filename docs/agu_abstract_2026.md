# AGU 2026 abstract — WellSight

v17, 2026-08-04. 1,809 characters / 279 words (AGU limit 2,000 characters).
191 characters spare.

**v17 trims 10% of the words** on request, 311 -> 279, with every number checked
to survive verbatim. Cuts were redundancy only: "heavy vegetation" (restated two
sentences later as "dense deciduous canopy"), "over this region", "a stack of",
"rather than overlap", and seven smaller ones. Median sentence 17 -> 15 words.

**v14-v16 replaced the metric.** The IoU-strictness sweep is gone. A reviewer
could not follow it, and the reason was not wording: IoU is the wrong criterion
for small discrete objects, per Fiorucci et al. 2022, and the closest published
analogue (Lidberg et al. 2024, hunting pits) uses centroid matching and reports
only recall/precision/F1. Both are in `literature/CITATIONS.md`. IoU is retained
for roads, where outline overlap is the right measure.

**Five numbers were wrong and are fixed in v16.** 471 training pits not 503
(503 is the current annotation count; no model has seen it); 93% not 94% pit
locate; 0.72 not 0.67 pit precision (0.67 scored the retrained models against a
stale rim set); 94% not 96% pad locate (0.96 credits confirmed pads by
construction); 735 not 1,220 road segments (`recall_clean` 0.982 applies to the
leakage-free subset — this one dates to v13).

**Scope moved out of the closing sentence.** "These results come from one survey
area" was a trailing caveat that also went stale the moment a second block
existed. The scope now rides inside the results sentence as "in the first survey
block", which stays true permanently, and the close states active work.

Provenance for every figure, and the pit/pad review asymmetry that explains the
0.72 vs 0.90 gap, is in `docs/iterations/centroid_matching_pit_pad_9t.md`.

Earlier versions are in git (`df30913`, `e8692a2`, `ee55d73`, `a0ba984`,
`a0e7e24`, `3c63c2e`, `c448a85`, `32548fd`, `9e231cf`, `712eb39`).

---

Orphan and abandoned wells are an ongoing problem across North America. During the 19th century, thousands of wells were drilled in western Pennsylvania, representing the North American oil boom. This boom was wild and reckless and poorly documented, leaving the hills and valleys riddled with dangerous wells leaking methane and brine into forests and streams. Locating them today takes countless hours on foot or reports from landowners and hikers. We present a lidar-based framework to detect their surface expressions. Airborne lidar resolves the ground beneath the dense deciduous canopy, revealing terrain optical imagery cannot capture. We process US Geological Survey 3D Elevation Program 2019 swaths into 0.5 and 1 meter models. From each we derive terrain channels including local relief models, topographic openness, and slope residuals. Older wells leave three recurring signs. These are graded pads marking the site, access roads, and shallow depressions. We segment all three with U-Nets trained on the same terrain stack, from 471 annotated pits and 650 pads. Scoring uses hand-drawn annotation withheld from training, plus detections checked by hand. Thresholds are selected on validation data and test scored once. Five-fold cross-validation scores every annotated feature in the first survey block by a model that never saw it. A detection counts when it contains the hand-drawn feature or sits inside it. The models locate 93 percent of pits and 94 percent of pads, at precision 0.72 and 0.90. Roads are scored by length, and the model recovers 98 percent of 735 withheld segments at a pixel IoU of 0.58. Hand-drawn negatives confirm the road model rejects drainage channels. We are extending this protocol to more blocks across Pennsylvania and field validation of undocumented candidates.

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

> **Superseded 2026-08-04 for pits and pads.** The rows below quote IoU-based
> scores from the pre-retrain models. Road rows still stand except the 1,220
> count, which should be 735. See `centroid_matching_pit_pad_9t.md`.

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

**Superseded 2026-08-04.** The pad CV finished, and both models were then
re-scored under centroid matching rather than IoU, so every number in this
section is on the retired metric. Current figures are in
`docs/iterations/centroid_matching_pit_pad_9t.md`.

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
