# Centroid matching, annotation expansion, and the pit retrain — 9t

**Date:** 2026-08-04
**Trigger:** a reviewer comment on the AGU abstract — *"I don't understand this
methodology or what you are trying to show with these sentences"* — pointed at
the sentences reporting pit and pad recall across a range of IoU thresholds.

Short answer up front. **The confusion was justified. We were reporting an
IoU-strictness sweep for a class of object the literature argues should not be
scored by IoU at all. Switching to the centroid criterion the comparable papers
use, expanding the annotation set, and retraining moved pit F1 from 0.716 to
0.809 and pad precision from 0.613 to 0.898. Most of the precision gain is a
corrected measurement, not a better model, and this document says which is
which.**

---

## 1. Why IoU was the wrong metric

[[literature_citations]] now carries both papers.

Fiorucci et al. 2022 (*Remote Sensing* 14(7):1694) is a paper whose entire
subject is that IoU is inadequate for small discrete archaeological objects. A
few pixels of boundary disagreement on a feature a few metres across swamps the
overlap ratio, so a correctly located object is scored a miss for an outline
nobody drew consistently. They propose centroid-based and pixel-based measures
instead.

Lidberg et al. 2024 (*Journal of Field Archaeology* 49(6):395–405) adopted it.
Their target — hunting pits, U-Net, national ALS, 0.5 m vs 1 m DEM, forested
Sweden — is the closest published analogue to our pits. Their evaluation section
reads:

> "A centroid-based approach described by Fiorucci and colleagues (2022) was
> used to calculate the number of true positive, false positive, and false
> negative predicted hunting pits. These numbers were then used to calculate
> recall, precision, and F1 score for each model."

No IoU anywhere. Their Table 1, comparing against every prior hunting-pit study,
has four columns: recall, precision, F1, point density.

| Study | Recall | Precision | F1 | pts/m² |
|---|---|---|---|---|
| Lidberg 2024 (U-Net, 0.5 m) | 70 | 85 | 0.76 | 1–2 |
| Trier & Pilø 2012 | 67–76 | — | — | 7 |
| Trier, Reksten & Løseth 2021 | 86 | 80 | 0.83 | 5–12 |
| Seitsonen & Ikäheimo 2021 | 98 | 47 | 0.64 | 5 |

**We had already been computing the right metric and reporting the wrong one.**
The `containment` column in `pit_cv5_per_fold_9t.csv` is defined as "predicted
floor centroid inside the annotated rim" — that is Fiorucci's criterion under
another name. [[benchmark_context_what_counts_as_good]] even wrote down the
consequence on 2026-07-27: *"The 0.754 is mostly a delineation score wearing a
detection score's clothes."* We diagnosed it and kept the metric anyway.

IoU stays for **roads**, where outline overlap is the right measure.

---

## 2. Annotation expansion

The user reviewed the model's unmatched detections in QGIS and found many were
real wells that had never been annotated.

| | Jun 10 | 12:35 | 12:59 (final) |
|---|---|---|---|
| `pit_inside` total | 426 | 527 | 559 |
| `pit_inside` in 9t | 426 | 471 | **503** |
| `pit_outside` in 9t | 428 | 469 | **506** |
| floors with no rim (9t) | — | 14 → 1 | **0** |
| rims with no floor (9t) | — | 4 → 0 | 4 |

97 brand-new polygons were added in the first pass, verified geometrically
(>1 m from any pre-existing polygon), not by count: **41 inside 9t, 56 in
`northcentral_b19/e1423n2235`** (the QL1 ANF block over McKean, bounds
697294–700748 / 4645706–4649109). The McKean 56 land in no 9t block and are
carried in the manifest as `unused` — they train nothing. A second pass added
32 more floors and 37 more rims inside 9t.

**The training set is 471 pits, not 503.** The label raster and manifest were
built at 12:35; the last 32 floors arrived at 12:59, after the retrain had
started. Any document quoting 503 as a training count is wrong.

---

## 3. The measurement correction, isolated

Before retraining anything, the **same 587 predictions from the June-10 models**
were re-scored against the growing annotation set. Nothing about the models
changed.

| annotations | X (candidates) | Y (truth) | matched | precision | recall | F1 | unmatched |
|---|---|---|---|---|---|---|---|
| Jun 10 (426) | 587 | 423 | 385 | 0.656 | 0.910 | 0.762 | 202 |
| 12:35 (471) | 587 | 459 | 416 | 0.709 | 0.906 | 0.795 | 171 |
| 12:59 (503) | 587 | 496 | 451 | **0.768** | 0.909 | **0.833** | 136 |

**66 of the original 202 "false positives" were real wells.** Precision
+0.112 with no model change. Recall is flat because the model had already found
66 of the 73 newly annotated pits.

This is the number to quote when asked "what did the annotation work buy?" It is
a corrected measurement, not an improvement.

---

## 4. Pit retrain

`python notebooks/wellsight_v2/pits/_pit_unet_cv5.py --folds 5 --epochs 40`
— 54.8 min, GTX 1070 Ti. Fold checkpoints and probability rasters were deleted
first; the script reuses them when present and would otherwise have silently
returned the old models.

Pooled, F1-selected thresholds `[0.45, 0.5, 0.5, 0.55, 0.6]`:

| scored against | truth | preds | matched | precision | recall | F1 |
|---|---|---|---|---|---|---|
| 12:35 manifest rims | 469 | 658 | 439 | 0.667 | 0.936 | 0.779 |
| **current rims (fair)** | **506** | **658** | **471** | **0.716** | **0.931** | **0.809** |
| old models, current rims | 496 | 590 | 446 | 0.756 | 0.899 | 0.821 |

**Pit precision did not fall to 0.67.** That figure scored the retrained models
against the stale 12:35 rim set, so 32 detections landing on rims drawn at 12:59
counted as errors. On the current annotations it is **0.716**.

The remaining gap to the old models' 0.756 is a genuine recall-for-precision
trade: the retrained model saw 45 more pits and fires more (658 predictions vs
590), taking recall 0.899 → 0.931. F1 is nearly unchanged, 0.821 vs 0.809.

Backup of the June-10 state: `data/derivatives/tiles/9t/_backup_pit_ann426_2026-06-10/`
(manifest, blocks, label raster, full `pit_unet_cv5/`) and
`data/derivatives/annotations/_backup_2026-06-10/annotations_proj.gpkg`.

---

## 5. Matching-rule ablation

Script: `notebooks/wellsight_v2/eval/_match_rules_pit_pad_9t.py`.
Three rules were proposed by the user and tested cumulatively.

**PIT** (retrained models)

| rule | truth | preds | matched | precision | recall | F1 |
|---|---|---|---|---|---|---|
| 0 baseline (centroid, manifest only) | 469 | 658 | 439 | 0.667 | 0.936 | 0.779 |
| 1 + all annotations | 469 | 658 | 439 | 0.667 | 0.936 | 0.779 |
| 2 + bidirectional containment | 469 | 658 | 439 | 0.667 | 0.936 | 0.779 |
| 3 + size filter | 469 | 634 | 432 | 0.681 | 0.921 | 0.783 |

**PAD** (June-10 models, not retrained)

| rule | truth | preds | matched | precision | recall | F1 |
|---|---|---|---|---|---|---|
| 0 baseline | 650 | 984 | 603 | 0.613 | 0.928 | 0.738 |
| 1 + all annotations | 650 | 984 | 603 | 0.613 | 0.928 | 0.738 |
| **2 + bidirectional containment** | 650 | 984 | **613** | 0.623 | **0.943** | 0.750 |
| 3 + size filter | 650 | 932 | 609 | 0.653 | 0.937 | 0.770 |

**Rule 1 is a no-op.** It was added on the suspicion that annotations outside
the fold manifest were being ignored, which would have been a scoring defect.
Measured, there are none — every annotation inside a held-out footprint is in
the manifest. Recorded here so the suspicion is not re-raised.

**Rule 2 helps pads, not pits.** +10 matches, recall 0.928 → 0.943. These are
blobs large enough to enclose a whole pad while their own centroid lands on
ground outside it. A predicted pit floor is always smaller than the rim it sits
in, so the enclosure case cannot arise for pits. The overlap-fraction leg of the
rule (`>= 0.5` of the smaller area) fires **never** — 0.5 and 0.3 give identical
results at every size cut, so the rule is pure containment either direction.

**Rule 3 must be applied in log space.** Pad areas are right-skewed enough that
a linear 3σ cut lands at **−839 m²** and excludes nothing. In log₁₀ space the
3σ cut is 283 m², just under the smallest annotated pad at 261 m².

Sweep of the size cut (`pad_match_rule_sweep_9t.csv`):

| n_sd | cut m² | preds | precision | recall | F1 | candidates |
|---|---|---|---|---|---|---|
| none | 0 | 984 | 0.623 | 0.943 | 0.750 | 371 |
| 3.0 | 283 | 932 | 0.653 | 0.937 | 0.770 | 323 |
| 2.0 | 468 | 893 | 0.672 | 0.923 | 0.778 | 293 |
| 1.5 | 602 | 859 | 0.689 | 0.911 | 0.785 | 267 |

F1 keeps rising below 3σ, and that is a trap. At 1.5σ the cut is 602 m², well
inside the annotated range, and 21 correct detections are discarded to buy it.
**3σ is the last cut justified by the data rather than by chasing F1.**

**The size filter was then dropped for pads anyway** — see §6. It would delete
confirmed pads.

---

## 6. Pad candidate review, and what it does to precision

All 381 unmatched pad predictions were reviewed in QGIS. **277 were confirmed as
real pads**, 104 rejected. The confirmed pads were deliberately **not** added to
`plat.shp` — they are scoring evidence, not annotation.

Under the bidirectional rule 6 of the 277 became ordinary matches, leaving 271
confirmed among 371 unmatched.

| basis | truth | preds | TP | precision | recall | F1 |
|---|---|---|---|---|---|---|
| annotation only | 650 | 984 | 613 | 0.623 | 0.943 | 0.750 |
| **+ confirmed detections** | 650 | 984 | **884** | **0.898** | — | — |
| + confirmed, truth grown | 921 | 984 | 884 | 0.898 | 0.960 | 0.928 |

**Report precision 0.898 and recall 0.943.** The 0.960 recall is circular: every
one of the 271 was confirmed *because* a detection was already sitting on it, so
they are found by construction. Recall needs a reference set assembled
independently of model output, which is what the 650 hand-drawn pads are.

This precision/recall split — verify detections for precision, use an
independent reference for recall — is the standard protocol in this literature.
It has one structural limit that must be stated whenever it is used: **reviewing
a model's own output can never discover what the model missed.**

**Six confirmed pads fall below the 283 m² size cut**, the smallest at 106 m²,
against a smallest annotated pad of 261 m². The size filter would delete real
pads. It is therefore **not applied** to the shipped pad numbers; the only floor
is the polygonizer's own 100 m² minimum.

Confirmed pads scored 0.57–0.80. Nothing above 0.80 — the model is never highly
confident about features it was never taught.

---

## 7. Verified numbers, and five corrections to the abstract

Every figure re-derived from source on 2026-08-04.

| claim | value | derivation |
|---|---|---|
| pits trained on | **471** | `pit_dataset_manifest.csv` 527 rows − 56 `unused` |
| pads trained on | 650 | `plat_dataset_manifest.csv` 456+101+93 |
| pit locate | **0.931** | 471 / 506 rims |
| pit precision | **0.716** | 471 / 658 predictions |
| pad locate | **0.943** | 613 / 650 annotated pads |
| pad precision | **0.898** | (613 + 271 confirmed) / 984 |
| road recall | **0.982** | `recall_clean` at thr 0.20, n = **735** |
| road pixel IoU | 0.5814 | `road_unet_1m_recall/test_metrics.json` |

Corrections applied to `docs/agu_abstract_2026.md`:

1. **471 pits, not 503.** 503 is the current annotation count; no model has seen it.
2. **93% pits, not 94%.** 0.9308.
3. **0.72 pit precision, not 0.67.** 0.67 used the stale 12:35 rim set.
4. **94% pads, not 96%.** 0.960 credits confirmed pads by construction.
5. **735 road segments, not 1,220.** Inherited from v13. `recall_clean` 0.982
   applies to the 735-segment leakage-free subset; the 1,220 includes 485 chunks
   sharing a parent road with training. The full-set recall is 0.989.

---

## 8. Known asymmetry — do not read pit vs pad precision as a model comparison

Pad precision 0.898 includes a **complete** review of all 381 candidates. Pit
precision 0.716 includes **no** candidate review — 187 pit candidates are
unreviewed and deferred. Pads went 0.623 → 0.898 on review. The 0.72 / 0.90 gap
in the abstract is a difference in review effort, not in model quality.

---

## Outputs

All under `data/derivatives/eval_9t_centroid_matching/`:

| file | content |
|---|---|
| `centroid_matching_cv5_pit_pad_9t.csv` | centroid precision per fold, lenient + greedy 1:1 |
| `_centroid_matching_cv5_9t.json` | pooled summary |
| `centroid_precision_sweep_pit_cv5_9t.csv` | pit precision/recall vs threshold, centroid rule |
| `match_rule_ablation_pit_pad_9t.csv` | the §5 tables |
| `pad_match_rule_sweep_9t.csv` | size-cut sweep |
| `pad_precision_with_confirmed_candidates_9t.csv` | the §6 table |
| `rescore_same_preds_old_vs_new_annotations_thr0p50_9t.csv` | the §3 table |
| `pad_candidates_unmatched_heldout_9t.shp` | **user-reviewed, 277 confirmed — evidence, do not overwrite** |
| `pad_candidates_heldout_nosizefilter_9t.shp` | 371 candidates, `status` = confirmed / rejected_or_new |
| `pit_candidates_filtered_heldout_9t.shp` | 202 pit candidates, unreviewed |
| `pit_candidates_still_unmatched_thr0p50_9t.shp` | 171 pit candidates at flat thr 0.50 |
| `pad_missed_by_cv5_heldout_9t.shp` | 47 annotated pads the model missed (false negatives) |
| `pit_cv5_centroid_match_thr0p50_9t_05.gpkg` | matched/unmatched pred + rim layers, thr 0.50 |
| `pit_cv5_unmatched_map_thr0p50_9t_05.png` | overview + zoom panels |
| `new_pit_annotations_since_jun10_9t.shp` | the 41 new 9t pits |
| `new_pit_annotations_outside9t.gpkg` | the 56 McKean pits |
| `pit_floors_no_rim_9t.shp` | 1 remaining unpaired floor |

Retrained models: `data/derivatives/tiles/9t/pit_unet_cv5/`, log
`_pit_cv5_ann527_train.log`.

## Reproduce

```
python notebooks/wellsight_v2/annotations/_prep_annotations.py
python notebooks/wellsight_v2/annotations/_build_pit_dataset.py
python notebooks/wellsight_v2/pits/_pit_unet_cv5.py --folds 5 --epochs 40
python notebooks/wellsight_v2/eval/_cv5_centroid_precision_pit_pad_9t.py
python notebooks/wellsight_v2/eval/_match_rules_pit_pad_9t.py --n-sd 3.0
python notebooks/wellsight_v2/eval/_map_cv5_unmatched_pit_thr0p50_9t.py
```

`_pit_unet_cv5.py` reuses any existing `fold*/best.pt` and probability raster.
Delete `pit_unet_cv5/fold*/` before rerunning after a label change, or it
returns the old models with no warning.

## Deferred

- **Review the 187 pit candidates** so pit precision is measured like pad
  precision. Held for another time (2026-08-04).
- **Retrain the pad model.** Pads were never retrained; the 271 confirmations
  are unused as training signal.
- **Rebuild pits on 503.** The retrain used the 12:35 label raster (471).
- **The 56 McKean pits** are a second training/held-out block once
  `e1423n2235` gets a label raster and manifest.
- The 4 rims with no floor and 1 floor with no rim inside 9t.
