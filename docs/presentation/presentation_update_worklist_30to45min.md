# Outline: WellSight, 30-45 minute talk

Source deck: `docs/presentation/WellSight_Presentation.pptx`, 22 slides, last
written 2026-05-04. Nothing here has been applied to it. This is the plan.

Rewritten 2026-09-17 around a decision: **cut the deck at slide 7 and rebuild
everything after it.** The earlier keep / revise / rewrite structure assumed the
existing method slides would survive. They do not.

---

## 1. The decision

Slides 1-7 are the *problem*: what an orphaned well is, what a pit looks like,
why LiDAR, where we work, why the DEP records are not enough. That material is
still true and still good.

Slide 8 is where the deck starts saying "here's our method," and that method —
template matching into a 48-feature gradient-boosting ensemble — is not what the
project does any more.

**The classical branch is cut, not compressed.** It is a predecessor, not a
benchmark. The 0.905 ROC-AUC and the U-Net's threshold sweep were never measured
against each other: different metrics, different splits, no controlled
comparison. Presenting it as "the thing we beat" would overstate what was
actually run, and template matching is a weak enough comparator that beating it
invites the straw-man objection.

The headline does not need a comparator. *Search 4 hectares of 2,025 and find 126
of 127* is good in absolute terms.

**What survives of it is one sentence**, said in passing during the transition
into Act II:

> We started with template matching and a 48-feature gradient-boosting ensemble.
> It worked well enough to be worth annotating for, and badly enough that we
> needed shape, not just location.

If someone wants detail, the May deck still exists.

## 2. What is kept, cut, and rescued

**Kept, slides 1-7.** Two need work:

| Slide | Work |
|---|---|
| 6 Study Area | says the DEM is gridded at 1 m; most work since is 0.5 m. Add the locator map and the seven tiles |
| 7 DEP Records | add the bounty-era reporting-provenance finding from the 2022 to 2026 DEP diff |

**Rescued from after the cut.** These are measurements or methods that nothing
since invalidated. They move into the new body rather than being rebuilt:

| Old slide | Goes to | Note |
|---|---|---|
| 13 Measured Pit Morphology | Act II | 0.7 m deep, 13 m across, ~32 m3, above the 0.10 m noise floor. Measurements of the ground, not model output |
| 14 Annotation Quality Control | Act II | Mahalanobis method still stands. The "856 measured pits" count is stale, refresh it |
| 19-20 Appendix | Appendix | 3DEP collection parameters, literature-grounded parameters |

**Cut.** 8 Pipeline Overview, 9 Terrain Derivatives, 10 Manual Annotation,
11 Template Matching, 12 Classification, 15 Challenges, 16 Future Work,
17 Summary, and appendix 21-22 (the 48-feature set, which belongs to the cut
branch). Slides 9 and 10 cover topics that survive, but the new versions share
nothing with the old ones. 18 References gets extended.

## 3. Shape

| Act | Min | Slides | What it is |
|---|---|---|---|
| I. The problem | 6 | 7 | the kept slides 1-7 |
| II. From points to polygons | 11 | 12 | the annotation, the cost, the workflow |
| III. The models | 9 | 10 | pit, pad, road, and how they are trained |
| IV. What they find | 7 | 7 | the results, and how they are scored |
| V. Does it travel | 4 | 4 | out of domain, change detection, radar |
| VI. What went wrong | 3 | 3 | the corrections |
| VII. Where it goes | 2 | 3 | next, summary, contact |
| **Total** | **42** | **46** | plus appendix |

46 slides at 55 s is 42 minutes. Cut points marked **[cut]** take it to 30.

---

## 4. Act I — The problem (7 slides, kept)

Slides 1-7 as they stand, with the two revisions in section 2.

Transition line into Act II is the template-matching sentence from section 1.

## 5. Act II — From points to polygons (12 slides)

The spine of the talk. The May deck detected **points**: a scored x/y with a
confidence number. Everything since is **geometry**. A point is right or wrong. A
polygon can be right in the wrong place, the right place at the wrong size, or
one object split in two — which is why rim containment, centroid precision and
IoU had to be invented for this project.

Counts are live from `qgis/annotations/annotations_proj.gpkg` as of 2026-09-17.

1. **What a label was in May.** An x/y and a confidence. Name what it cannot
   answer.
2. **The schema.** Seven layers, 8,609 hand-digitized features.

   | layer | features | what it is |
   |---|---|---|
   | pad | 995 | disturbed footprint, carries n_pits / n_roads tallies |
   | pit_inside | 712 | floor |
   | pit_wall | 586 | rim |
   | pit_full | 723 | floor + rim, the whole depression |
   | roads | 3,690 | access traces |
   | not_roads | 112 | hand-drawn negatives |
   | drainage | 1,791 | segmented, with length, drop and class |

3. **Why floor, rim and full are three layers.** Floor is what you delineate, rim
   is what you locate against, full is the depression.
   Figure: `annotation_schema_one_pad_one_pit_9t_05.png`.
4. **What a pit actually is.** Rescued slide 13. A shallow bowl 0.7 m deep and
   13 m across, ~32 m3. The collapsed cellar, not the wellbore.
5. **No pad is a cluster of pits.** 995 pads hold 712 floors, and no pad in 9t
   carries more than two. Kills the intuition before it forms. **[cut]**
6. **The annotation cost.** 426 to 527 to 712 pit floors.
   Figures: `annotation_growth_pit_splits_426_527_712.png`,
   `annotation_growth_pad_splits_650_995_9t.png`.
7. **Project-wide against in-tile.** 712 floors and 995 pads annotated; 503 and
   650 of them inside the 9t training tile. One sentence, said once, so no number
   later in the talk is ambiguous.
8. **QC on hand labels.** Rescued slide 14, counts refreshed. Add `not_roads`:
   112 negatives you have to draw on purpose.
9. **The stage pipeline.** s1_build to s7_analysis, 87 scripts, what each stage
   owns. Figure: the pipeline diagram, **redrawn as one path** (see section 9).
10. **Polygons into label grids.** The {0,1,2} raster at nodata=255, and why that
    contract is rigid across the trainer, the loss and the inference script.
11. **The spatial-block split.** 12x12 grid, greedy fill by feature count, why
    balancing block count would be wrong.
    Figure: `spatial_block_split_grid_12x12_9t_ann712.png`.
12. **The review loop.** Generate, correct in QGIS, diff, retrain on the diff.
    Mechanism here; the road result it bought lands in Act III.

## 6. Act III — The models (10 slides)

1. **Why segmentation.** Motivation only, one slide.
2. **Architecture and inputs.** The 7-channel stack, patch size, FocalCE.
3. **Pit U-Net, qualitative.** `data/9t/models/pit/unet_v2/test_preds.png`.
4. **Pad U-Net, qualitative.** `data/9t/models/pad/unet/test_preds.png`.
5. **Road U-Net, the problem.** Why 2-class failed and what drainage did to it.
6. **Road U-Net, the fix.** 3-class with drainage as its own trained class, and
   focal-alpha 0.60 to 0.72. Held-out `not_road` is claimed at 0.0% at every
   threshold and P(drainage) falls to 0.005. Fix it in training, not in post.
7. **Road chunking.** ~40 m chunks, and why long roads broke the sampling.
8. **Active learning, closed.** 22 km of your corrections turned added-vs-reject
   AP from 0.245 to 0.443 with zero in-domain cost. 188 km folded back into
   `roads.shp`.
   Figure: `data/9t/models/road/unet_1m_corrected/compare_corrections_full.png`.
9. **5-fold cross-validation.** Why one split of 65 test pits was not enough, and
   why folds are recomputed from the manifest every time.
10. **Threshold selection.** Chosen on inner val under F1 and F2, both declared
    up front, then frozen and scored once. The opposite of cherry-picking.

## 7. Act IV — What they find (7 slides)

1. **How we score.** Recall, precision and containment in plain words, against
   hand-drawn annotation withheld from training. No DEP list, no TIGER.
2. **How much ground does it flag.** Panel a of
   `threshold_sweep_flagged_area_vs_recall_pit_pad_road_9t.png`.
3. **How much does it find.** Panel b. Pit at threshold 0.20 flags 4.33 ha of
   2,025 — 0.21% of the tile — and finds 126 of 127 withheld rims. **This is the
   headline of the talk.**
4. **Pit, cross-validated.** ann712, five folds, every pit scored by a model that
   never saw it. F1 rule: recall 0.861, precision 0.686, containment 0.914. F2
   rule: recall 0.928, precision 0.633, containment 0.956.
5. **Pad, cross-validated, and it is the weak one.** F1 rule: recall 0.888,
   precision 0.597, locate 0.923. It needs 55x the ground of the pit model to
   find fewer of its targets. Say so.
6. **Recall is stable, precision is the ceiling.** Precision never exceeds ~0.69
   at any threshold on either task. Name it as the open problem rather than
   letting someone else name it.
7. **What the annotation did to the numbers.** Retraining on ann712 moved pit
   precision 0.637 to 0.686 and recall 0.890 to 0.861. Pads did not reproduce it.
   Honest, and it sets up Act VI. **[cut]**

## 8. Act V — Does it travel (4 slides)

1. **613590 as the out-of-domain test.** Why a held-out tile is not a held-out
   region.
2. **Road transfer, with real ground truth.** Best model that never saw the tile
   scores 0.686 quality; ensemble max recovers 0.909 completeness. And the
   finding that beat every architecture change: **fixing the labels bought +0.146
   completeness at zero correctness cost.**
3. **ICP change detection.** 2006-2008 to 2019, the method and the null test that
   showed the apparent signal at wells was circular.
4. **NISAR.** GCOV usable over PA at 10 m, GUNW coherence 0.14 under canopy.
   L-band InSAR subsidence does not survive Pennsylvania forest.
   Figure: `nisar_gcov_hh_hv_clip_9t_10m_20260120.png`.

## 9. Act VI — What went wrong (3 slides)

The most valuable new material in the talk, and the part nobody else presents.
Factual and short.

1. **The precision measurement bug.** 3-6% was not a model result. Extent
   mismatch, class mismatch, untuned thresholds. Corrected to 0.54-0.69.
2. **The circular signals.** P_road as a feature, and the DoD signal at wells.
   Both looked like results. Neither was.
3. **The two CRS errors.** Wrong EPSG in the 2006-2008 LAZ headers, and
   `drainage.shp` in 6346 while everything else was 4326.

Act II slide 12 also covers failure. Split by kind: Act II takes the data and
pipeline failures, Act VI keeps the measurement failures. Twenty minutes apart,
so it does not read as repetition.

## 10. Act VII — Where it goes (3 slides)

1. **What is actually next.** Not the old slide 16, four of whose six items are
   done.
2. **Summary.** Write last, once the body is settled.
3. **Contact and data availability.** Outreach material is in the 2026-08-18 log
   entry.

---

## 11. Figures

Built, in `docs/presentation/figures_30to45min/`:

```
locator_study_areas_pa.png                                   Act I, slide 6
annotation_schema_one_pad_one_pit_9t_05.png                  Act II, 3
annotation_growth_pit_splits_426_527_712.png                 Act II, 6
annotation_growth_pad_splits_650_995_9t.png                  Act II, 6
spatial_block_split_grid_12x12_9t_ann712.png                 Act II, 11
threshold_sweep_flagged_area_vs_recall_pit_pad_road_9t.png   Act IV, 2 and 3
nisar_gcov_hh_hv_clip_9t_10m_20260120.png                    Act V, 4
```

`figure_notes_what_each_image_shows.md` in the same folder says what each one
shows and where its numbers come from. Rebuild all of them with
`python docs/presentation/figures_30to45min/_build_presentation_figures.py`.

**Now unused by the cut:**

- `pipeline_diagram_classical_and_unet_branches.png` — drawn with two branches,
  classical and deep learning. Needs **redrawing as one path** for Act II slide 9.
- `classical_vs_unet_pit_detection_same_scene_9t.png` — a good figure serving a
  slide that no longer exists. Kept on disk, not in the deck. Do not manufacture
  a reason to show it.

**Still to build:**

- Nothing blocking. Act III leans on existing figures beside the models.

Existing figures to pull in at build time, not copied into the deck folder:

```
data/9t/models/pit/unet_v2/test_preds.png
data/9t/models/pad/unet/test_preds.png
data/9t/models/road/unet_1m_corrected/compare_corrections_full.png
data/9t/models/road/unet_1m_corrected/compare_corrections_zoom.png
data/9t/models/road/sweep_202607/fig_sweep.png
data/9t/derived/05/rrim_simple_9t_05_preview.png
data/9t/derived/05/pit_traces_on_hillshade.png
data/9t/derived/05/pit_footprints_contact_sheet.png
data/613590/derived/inference_05/overlay_pit_pad_613590_05.png
data/613590/derived/05/tile_overview_613590_05.png
```

## 12. Blockers

**B1. CLOSED 2026-09-17.** Pit and pad CV5 retrained on ann712. Every number in
Act IV is current. See `docs/iterations/LEADERBOARD.md`.

**B2. CLOSED.** The counts are project-wide against in-tile:

| | annotated | train | val | test | in 9t, unassigned | outside 9t | **in 9t** |
|---|---|---|---|---|---|---|---|
| pit | 712 | 352 | 77 | 74 | 0 | 209 | **503** |
| pad | 995 | 401 | 69 | 114 | 66 | 345 | **650** |

"unused" in the manifest is two states: a null `block_id` means outside the tile,
but an in-tile row is also unused if the greedy fill left its block out of every
split. Pads have 66 of the second kind, pits none. Old slide 10's 861 predates
both counts and is cut with the slide.

**B3. Road numbers are safe.** Road models train on 1 m data from a separate
manifest; the ann712 change did not touch them.

**B4. No pad-content split on OTHER_DATA.** Only matters if the talk shows a new
pad result outside 9t. It does not.

**B5. `_dl.py:46` `DEFAULT_CHANNELS` ends in `roughness_11`, the 1 m stacks write
`roughness_5`.** A mislabel of the same band, not a missing band. Cosmetic for
the talk, real for the next retrain.

## 13. Order of work

1. Redraw the pipeline diagram as one path. Act II slide 9 depends on it.
2. Build Act II. It is the largest new block and the rest sizes around it.
3. Build Act IV. The numbers are all in hand.
4. Build Acts III, V and VI.
5. Revise kept slides 6 and 7.
6. Write Act VII last.
7. Time a read-through. Mark the cut points that land it at 30 minutes.

The deck builders in `archive/wellsight/paper/paper/` were written against the
May deck and open the `.pptx` by bare filename, so they expect to run from
`docs/presentation/`. Check they still run before relying on them. See
`docs/presentation/README.md`.
