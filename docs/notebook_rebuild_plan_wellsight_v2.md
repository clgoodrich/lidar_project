# Notebook rebuild plan — `notebooks/wellsight_v2`

Written 2026-09-11.

## What this is

You are re-deriving the WellSight pipeline by hand, one notebook per stage, in
`notebooks/wellsight_v2/s1_build/`. Each notebook reproduces one or more of the
existing `.py` scripts. This document is the running order: what to rebuild, in
what sequence, what each script actually does, and what it needs from the
notebook before it.

The order is not alphabetical and it is not the stage numbering. It follows the
**data dependency chain** — a notebook is listed only after everything it reads
has been written by an earlier notebook.

There are **90 scripts** in `notebooks/wellsight_v2/`. You do not rebuild all of
them. Section 5 lists the ones that are dead ends, one-off experiments, or
superseded, and says why each is skipped.

---

## 1. The three library modules — do NOT transcribe these

These are imported, not run. They have no `main()`. A notebook `import`s them the
same way a script does, via the `sys.path.insert` at the top of your cell 0.

| Full path | Lines | What it holds |
|---|---:|---|
| `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\_common.py` | 450 | `path_for()`, `read_layer()`, `normalize_ids()`, `run_pdal()`, the legacy-name alias tables |
| `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\_dl.py` | 470 | Dataset, patch sampler, `FocalLoss(ignore=255)`, U-Net blocks, the train loop |
| `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\_instance_common.py` | 758 | Instance-segmentation helpers (Mask R-CNN / YOLO shared code) |

`_dl.py` deserves one exception. When you reach Phase 6 you will want to *read*
`_dl.py:99` (the ignore index) and `_dl.py:133-134` (it reads `stats[c]["mean"]`
and `stats[c]["std"]` — this is why phase_3's stats dict must use the key `std`,
not `stan_dev`). You still import it rather than transcribe it.

---

## 2. Done so far

| Notebook | Full path | Replicates |
|---|---|---|
| phase_1 | `notebooks\wellsight_v2\s1_build\phase_1_derivative_generation.ipynb` | `s1_build\_build_derivatives.py` (404 lines) |
| phase_2 | `notebooks\wellsight_v2\s1_build\phase_2_prep_annotations.ipynb` | `s2_labels\_prep_annotations.py` (176 lines) |
| phase_3 | `notebooks\wellsight_v2\s1_build\phase_3_rasterization_training_prep.ipynb` | `s2_labels\_build_pit_dataset_v2.py` (379) + `s2_labels\_prep_road_1m.py` (150) |

Open item on phase_1: the bbox snap fix (commit `a53567d`) is in, but
`data\OTHER_DATA\derived\` has not been rebuilt against it yet.

Open item on phase_3: `data\OTHER_DATA\derived\labels_road_OTHER_DATA_1m.tif`
holds 0 road pixels from the inverted-filter bug and will not be overwritten,
because the notebook now writes `labels_road_OTHER_DATA.tif` without the `_1m`.
Delete the stale one.

---

## 3. The remaining core path

Eleven notebooks. This is the minimum chain that goes LAZ to trained model to
scored candidates. Build them in this order.

### Phase 4 — pad and road datasets

**Source:** `notebooks\wellsight_v2\s2_labels\_build_pad_road_dataset.py` (189 lines)
**Plus:** `notebooks\wellsight_v2\s2_labels\_build_pad_split.py` (88 lines)

Reads `pit_blocks_9t.gpkg` — the block grid phase_3 wrote — and pushes that same
split out to pads and roads, so pads, roads and pits are never scored on a block
another head trained on.

Writes, into the area's `derived/` directory:

- `labels_pad_<area>_05.tif` — uint8, 0=bg, 1=pad
- `labels_road_<area>_05.tif` — uint8, 0=bg, 1=road, roads buffered 1.5 m
- `pad_dataset_manifest.csv` — one row per pad polygon
- `road_dataset_manifest.csv` — one row per road line-chunk
- `road_classifier_samples.csv` — one row per sample point, 4 m stride

Three things here that phase_3 did not have:

1. **`chunk_line()`** — a polyline longer than 40 m is cut into ~40 m pieces,
   densified to ~5 m vertices. Without it the U-Net only ever centers a patch on
   a road's midpoint, and evaluation compares a 2 km road against a 30 m one as
   if they were the same unit.
2. **`assign_split()`** — points look up *their* block. That inverts phase_3,
   where blocks were assigned a split. Anything falling in no block returns the
   literal string `"unused"`, matching phase_3's pit manifest.
3. **Three manifests at three granularities** — polygon, line-chunk, point — all
   keyed back to the one block grid.

Fold `_build_pad_split.py` into the same notebook. It is 88 lines and reads the
pad manifest this notebook just wrote.

Do this one next.

### Phase 5 — the unified split and the guard

**Sources:**
- `notebooks\wellsight_v2\s2_labels\_build_unified_split.py` (91 lines)
- `notebooks\wellsight_v2\s2_labels\_manifest_guard.py` (65 lines)
- `notebooks\wellsight_v2\s2_labels\_sanity_render.py` (81 lines)

`_build_unified_split.py` produces one split that the multitask U-Net (pit + road
+ pad heads) can use for all three heads at once. It exists because three
independent splits leak: a block that is train for pits and test for roads shows
the multitask net its own test data.

`_manifest_guard.py` is the smallest and most important file in the repo for your
purposes. It refuses to overwrite a manifest when the annotation count has grown,
because reassigning the split silently invalidates every deployed checkpoint.
That has already happened once — the incident is recorded at
`docs\golden\NON_DETERMINISTIC.md:28-62`. Transcribe it and call it from phase_4
and phase_5 before any write.

`_sanity_render.py` renders a grid of sample pits with the label overlay. Cheap,
and it is how you catch a rasterization that is one cell off before you spend 90
minutes training on it.

### Phase 6 — train the pit U-Net

**Source:** `notebooks\wellsight_v2\s3_train\_pit_unet_cv5.py` (463 lines)

The first notebook that consumes everything the s2 notebooks wrote. 5-fold
cross-validation, folds recomputed from the manifest each run.

Two hazards, both already bitten this project:

- **Line 317 reuses any complete `best.pt` it finds.** Re-running after a split
  change silently keeps the old model. Move the checkpoint directory aside; do
  not rely on the script noticing.
- Folds come from the manifest. Change the manifest and every existing fold score
  becomes meaningless. See the `ann527` to `ann712` note in
  `docs\iterations\LEADERBOARD.md`.

Environment: `C:\Users\colto\miniconda3\python.exe` has torch 2.7.1+cu118 and
sees the GTX 1070 Ti. The repo `.venv` has no torch. Roughly 90 minutes per run.

### Phase 7 — train the pad U-Net

**Source:** `notebooks\wellsight_v2\s3_train\_pad_unet_cv5.py` (449 lines)

Structurally the sibling of phase_6, so the transcription is mostly mechanical
once phase_6 works. Same reuse hazard, same runtime.

Optional companion: `s3_train\_pad_unet.py` (220 lines) is the single-split
version. Skip it unless you want the faster iteration loop.

### Phase 8 — train the road U-Net

**Source:** `notebooks\wellsight_v2\s3_train\_road_unet_1m_recall.py` (210 lines)

This is the road model actually in use. It runs at 1 m, three classes,
bg/road/drainage, and it trains on 9t only — multi-block training was tried and
made it worse.

The one parameter that matters: road focal-alpha is 0.72, not 0.60. That single
bump is what closed the road gaps on 613590. Do not round it off.

Sibling worth knowing about but not transcribing yet:
`s3_train\_drainage_unet_1m.py` (208 lines), the drainage-focused variant.

### Phase 9 — inference

**Source:** `notebooks\wellsight_v2\s4_infer\_predict_on_tile.py` (203 lines)

Runs a trained pit / road / pad U-Net across a tile's derivative stack and writes
probability rasters. This is the generic entry point; use it rather than the
per-model ones.

Two things to carry over:

- Normalization at inference must use the *training* `feature_stats`. Regenerating
  the stats shifts every input by ~2% and nothing errors.
- If you go near the YOLO path: PIL writes PNGs as RGB, ultralytics' cv2 loader
  re-reads them as BGR. Numpy arrays fed at inference must be BGR-flipped.

### Phase 10 — candidates from probabilities

**Source:** `notebooks\wellsight_v2\s4_infer\_postfilter_tile_candidates.py` (132 lines)

Threshold, clean, and polygonize the raw probability rasters into candidate
polygons. Short and self-contained.

### Phase 11 — threshold products

**Sources:**
- `notebooks\wellsight_v2\s5_eval\_threshold_common.py` (225 lines) — shared, transcribe first
- `notebooks\wellsight_v2\s5_eval\_pit_threshold_products_9t.py` (289 lines)
- `notebooks\wellsight_v2\s5_eval\_pad_threshold_products_9t.py` (282 lines)
- `notebooks\wellsight_v2\s5_eval\_road_threshold_products_9t.py` (297 lines)

For each probability cutoff: what it claims, and what it misses. The pit one is
deliberately built so the *missed* pits are findable in QGIS, not just counted.
Do `_threshold_common.py` first; the three product scripts are thin on top of it.

### Phase 12 — honest scoring

**Sources:**
- `notebooks\wellsight_v2\s5_eval\_heldout_rim_containment_9t.py` (309 lines)
- `notebooks\wellsight_v2\s5_eval\_cv5_centroid_precision_pit_pad_9t.py` (283 lines)
- `notebooks\wellsight_v2\s5_eval\_pit_cv5_tau_scale.py` (109 lines)
- `notebooks\wellsight_v2\s5_eval\_pad_cv5_tau_scale.py` (108 lines)

Rim containment asks the right question for pits: did the predicted floor land
inside the hand-drawn rim? Centroid precision is the counterpart — of what the
model claimed, how much was real. The two `tau_scale` scripts sweep IoU
strictness so a headline number cannot hide behind a lenient match threshold.

Anything that lands here goes on `docs\iterations\LEADERBOARD.md` in the same
pass. That is a standing repo rule, not a suggestion.

### Phase 13 — the review loop

**Sources:**
- `notebooks\wellsight_v2\s6_review\_build_pit_review_package.py` (186 lines)
- `notebooks\wellsight_v2\s6_review\_build_road_review_package.py` (152 lines)
- `notebooks\wellsight_v2\s6_review\_pit_corrections_diff.py` (109 lines)
- `notebooks\wellsight_v2\s6_review\_road_corrections_diff.py` (104 lines)

This is the only place the pipeline loops backward. A review package goes to
QGIS, you correct it by hand, the diff turns your rejections into hard negatives,
and those feed back into s2. It is why `roads.shp` keeps growing.

Build each package script and its matching diff script together — separately they
each do half a job.

### Phase 14 — science outputs

**Sources (pick by what you need, not in order):**
- `notebooks\wellsight_v2\s7_analysis\_well_age_morphology.py` (269 lines) — does surface geometry encode drilling era?
- `notebooks\wellsight_v2\s7_analysis\_pad_morphology_bins.py` (363 lines) — unsupervised pad bins, 9t + McKean
- `notebooks\wellsight_v2\s7_analysis\_icp_change_9t_rebuild.py` (392 lines) — 2006-08 to 2019 DoD, one ICP solve
- `notebooks\wellsight_v2\s7_analysis\_icp_change_classify_9t.py` (499 lines) — destripe, segment, split erosional from not
- `notebooks\wellsight_v2\s7_analysis\_export_well_age_qgis.py` (189 lines) — the QGIS-ready export

These are outputs, not infrastructure. Nothing downstream depends on them, so
they can wait until the core path runs end to end.

---

## 4. Optional side branches

Real, working, but not on the critical path. Rebuild if you need the capability.

| Script (under `notebooks\wellsight_v2\`) | Lines | Why you might want it |
|---|---:|---|
| `s1_build\_build_extra_channels.py` | 415 | experimental linear-feature channels for roads |
| `s1_build\_make_rrim.py` | 149 | Red Relief Image Map, the best single visual for pits |
| `s1_build\_build_3x3_hillshades.py` | 182 | 1 m DEM + hillshade per 3x3 mosaic |
| `s1_build\_build_data_3x3_derivatives.py` | 148 | full stack per 3x3 block, region scale |
| `s1_build\_build_data_3x3_partial_westernpa.py` | 147 | groups every WesternPA D20 tile into a block |
| `s2_labels\_build_label_grids.py` | 409 | builds the 2x2 grids you annotate in the first place |
| `s2_labels\_build_orient_labels.py` | 102 | per-pixel road-orientation labels |
| `s2_labels\_rebuild_labels_road_9t_1m.py` | 115 | safe road-label-only rebuild, does not touch the feature stack |
| `s3_train\_multitask_unet.py` | 477 | pit + road + pad in one net |
| `s3_train\_road_unet_1m_corrected.py` | 360 | fine-tune on human corrections, the active-learning trainer |
| `s3_train\_drainage_unet_1m.py` | 208 | drainage-focused road variant |
| `s4_infer\_infer_roads_data_3x3.py` | 179 | road inference across a whole region |
| `s4_infer\_refine_roads_data_3x3.py` | 480 | raw road raster to connected centerlines |
| `s4_infer\_road_infer.py` | 78 | load any road `best.pt`, predict a tile |
| `s3_train\_pad_unet.py` | 220 | single-split pad U-Net, faster to iterate than the 5-fold version |
| `s5_eval\_heldout_overlap_9t.py` | 255 | overlap against held-out hand drawings |
| `s5_eval\_score_road_pred_vs_roads_shp_613590.py` | 247 | the 613590 road score |
| `s5_eval\_build_undecided_pit_candidates_9t.py` | 377 | detections matching no annotation — the undecided set |
| `s5_eval\_match_rules_pit_pad_9t.py` | 242 | fixes a matching defect, tests two relaxations |
| `s5_eval\_map_cv5_unmatched_pit_thr0p50_9t.py` | 243 | maps the CV5 pit predictions at 0.50 that match no annotation |
| `s5_eval\_uncounted_well_recovery_9t.py` | 264 | DEP positional reliability, **not** a model score |
| `s6_review\_build_drainage_review_package.py` | 403 | drainage correction packages |
| `s6_review\_calibrate_drainage_extraction_9t.py` | 140 | calibrates the drainage vectorizer on 9t |
| `s7_analysis\_road_morphology_bins.py` | 592 | unsupervised bins for hand-drawn roads |
| `s7_analysis\_classify_9t_roads_bold_faint.py` | 460 | splits 9t roads into bold and faint |
| `s7_analysis\_bold_vs_faint_roads.py` | 427 | supervised contrast of the two exemplar sets |
| `s7_analysis\_well_provenance_flags.py` | 207 | bounty-era reporting-provenance proxy |
| `s7_analysis\_photo_source_locations.py` | 171 | georeferences the field-photo sweep |
| `s7_analysis\_score_bold_faint_exemplar_segments.py` | 140 | per-segment exemplar scoring |
| `s7_analysis\_icp_change_9t.py` | 188 | superseded by `_icp_change_9t_rebuild.py` |

---

## 5. Do not rebuild

| Script | Why skip |
|---|---|
| `s2_labels\_build_pit_dataset.py` (167) | v1. `_build_pit_dataset_v2.py` replaced it and phase_3 already covers v2. |
| `s3_train\_pit_maskrcnn.py` (253) | Mask R-CNN overfits 9t — best val loss at epoch 1, then climbs. 74 pits is too few for a 45.9 M-param net. |
| `s3_train\_pad_maskrcnn.py` (141) | same failure mode |
| `s3_train\_pit_yolo.py` (90) | YOLO branch, superseded by the U-Nets |
| `s3_train\_pad_yolo.py` (73) | same |
| `s3_train\_pit_unet_v2.py` (109) | superseded by `_pit_unet_cv5.py` |
| `s3_train\_road_sweep_202607.py` (616) | a finished one-off sweep; its conclusion is in `docs\road_unet_sweep_explained.md` |
| `s4_infer\_pit_maskrcnn_infer.py` (171) | inference tail for an abandoned branch |
| `s4_infer\_pad_maskrcnn_infer.py` (70) | same |
| `s4_infer\_pit_yolo_infer.py` (79) | same |
| `s4_infer\_pad_yolo_infer.py` (64) | same |
| `s4_infer\_yolo_infer_tile.py` (133) | same |
| `s4_infer\_pit_unet_v2_infer.py` (184) | pairs with the superseded `_pit_unet_v2.py` |
| `s4_infer\_pad_unet_infer_grid.py` (152) | narrow one-off: PA-trained pad model onto a label_grids tile |
| `s5_eval\_pit_optimize.py` (379) | pre-U-Net morphological post-processing tuning; historical |
| `s5_eval\_road_optimize.py` (629) | same |
| `s5_eval\_road_methods_compare.py` (150) | a finished bake-off |
| `s5_eval\_road_sweep_aggregate.py` (134) | aggregates the finished sweep |
| `s5_eval\_reeval_instance_precision_9t.py` (393) | scores the abandoned instance branch |
| `s5_eval\_plot_iou_strictness_scale_9t.py` (90) | plotting only; the `tau_scale` scripts compute the numbers |
| `s5_eval\_export_pit_floor_threshold_tifs.py` (113) | subsumed by the phase_11 threshold products |
| `s5_eval\_compare_corrected_613590.py` (108) | a one-off before/after visual |
| `s5_eval\_style_heldout_gpkg.py` (117) | attaches QML styling; cosmetic |
| `s6_review\_build_road_corrections_613590.py` (305) | 613590-specific, already run |
| `s6_review\_overlay_drainage_review_613590.py` (96) | same |
| `s2_labels\_merge_review_added_roads_613590_into_roads_shp.py` (191) | same, and it mutates the master annotation file |

---

## 6. Rules that apply to every notebook you write

From `CLAUDE.md`, and from mistakes already made in this repo.

1. **Full paths.** Every output cell prints the complete path of what it wrote.
2. **Descriptive filenames.** The name carries what it shows, the parameter that
   defines it, and the area. Use `0p20` style for decimals. `pit_prob.tif` is not
   a filename; `pit_unet_floor_mask_thr0p20_9t_05.tif` is.
3. **Anything 100 MB or larger needs a `.gitignore` rule in the same change.**
   Audit after any cell that writes rasters:
   ```bash
   find . -type f -size +100M -not -path './.git/*' | while read f; do \
     [ -z "$(git check-ignore "$f")" ] && echo "LEAKING: $f"; done
   ```
   Note the trap that already caught this project: rasters written at the *area
   root* rather than under `derived/` were ~36 MB each, so the 100 MB audit never
   flagged them and 464 MB nearly entered history.
4. **PDAL Python bindings do not work here.** Write a pipeline dict to a temp JSON
   and call the PDAL CLI through `subprocess.run`. `_common.run_pdal()` does this.
5. **Cells must be idempotent.** Re-running a merge onto an already-merged frame
   is what produced `n_pits_x` / `n_pits_y`. Prefer
   `df.col.map(other.col.value_counts()).fillna(0).astype(int)` over
   `groupby` to `merge` to `fillna`.
6. **`rasterize()` returns all zeros for an empty shape list.** It does not raise.
   A label raster of 9,000,000 zeros looks exactly like a successful run.
7. **A LAS header `min`/`max` is the extreme *point*, not the tile edge.** This is
   what put half of phase_1's channels on a grid 1 cm off from the other half.
   The snap fix is in as of commit `a53567d`.
8. **`output_wells.csv` is read-only ground truth.** Work from copies.
9. **Never present an unvalidated detection as a confirmed well.** Candidate or
   probable, with a confidence score, the method, and the distance to the nearest
   known well.
10. **Documentation moves with the work, not after it.** `docs\analysis_log.md`
    gets an entry each pass, newest at top. `docs\iterations\LEADERBOARD.md` gets
    every model result. `docs\iterations\BACKLOG.md` is the live deferred list —
    check it before starting something new.

---

## 7. Summary

| Group | Scripts |
|---|---:|
| Already rebuilt (phases 1-3) | 4 |
| Core path remaining (phases 4-14) | 27, across 11 notebooks |
| Optional side branches (section 4) | 30 |
| Skip (section 5) | 26 |
| Libraries — import, do not transcribe | 3 |
| **Total in `notebooks\wellsight_v2\`** | **90** |

Every script is in exactly one group.

Next action: **phase_4**, from
`C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s2_labels\_build_pad_road_dataset.py`.
