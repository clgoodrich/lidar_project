# WellSight Backlog — "things we said we'd revisit"

Live list of deferred ideas and open follow-ups. Check this before proposing new directions. Recreated 2026-06-03 (the prior file was missing from disk).

## Scan-angle ground cut (added 2026-09-18) — OPEN, and the biggest one here

The PA WesternPA 2019 D20 **March-2020 flight block** discards every at-ground
return beyond 18 degrees off nadir — roughly **1 M per tile**, measuring
0.065–0.067 m RMSE against neighbouring flight lines, inside the QL2 spec of
0.10 m. Details in
`docs/iterations/nonground_classification_and_scan_angle_cut.md`.

Scoped 2026-09-19 by measuring all 258 map squares: **165 of the 177 squares in
the March-2020 block** have the cut, every one of them at exactly 18 degrees,
costing the block 190,855,059 at-ground returns. The November-2019 Venango block (16 squares)
and the McKean April-2019 block (59) do not. It is one batch of flights, not a
county and not a convention.

- ~~**Run our own ground classification and compare.**~~ **DONE 2026-09-18** on
  two tiles — `docs/iterations/smrf_ground_reclassification.md`. SMRF recovers
  1.45–1.62 M points per tile and halves the DEM void rate (15.99% → 9.97%,
  12.36% → 6.27%) without moving ground the vendor already had (0.3% of covered
  cells differ by more than 10 cm). Pit depth unchanged.
- **Rebuild the feature stack on SMRF ground and re-score a model.** This is now
  the open question and the only one that decides whether any of this matters.
  Nothing so far shows detection improves; the whole case rests on the surface
  existing where it previously did not. Start with pit on `621594`, which is a 9t
  training tile, so the comparison lands against an existing leaderboard row.
- **Only 2 of the 177 affected squares are repaired.** Reprocessing the rest is a
  day of compute, not a research question — do not start it until the re-score
  above says it is worth doing.
- **Do NOT fix it by promoting flags.** The reference surface is built from
  class 2, so promoting points moves the surface and re-opens the question. One
  pass does not converge.
- **Vegetation structure is an unused channel.** Canopy p95 is 1.3–2.8 m lower
  over annotated pads and pits than the forest ring around them, same direction
  on 5 of 5 feature/tile combinations, pad effect Cliff's d −0.242 over 3,427
  cells. Built from points currently discarded. Candidate input channel — but
  nothing yet shows it adds anything the existing channels do not.
- **The spatial void claim is not general.** Voids stripe with swath geometry on
  four tiles and give r = −0.04 on 615591. Do not quote "DEM voids are swath
  stripes" without that caveat.
- **`data/9t/results/nonground_classification/` is misfiled.** Three of its four
  tiles are in the 613590 block, not 9t. The repo is area-major; this should move
  or be split. Cosmetic, but it will mislead someone.

## Ground classification (added 2026-09-18) — CLOSED, with one residual

The bridging hypothesis was tested and rejected on 2026-09-18
(`docs/iterations/ground_reclassification_pit_depth.md`). Class 2 is sound inside
our pits and no depth-derived channel is damped. Two things were deliberately left
open:

- **Pits bridged badly enough that we never annotated them are outside the test
  by construction.** The experiment measures 216 floors we drew; a depression
  erased from the DEM would never have been drawn. A way to probe this without
  circularity: rebuild a DEM from class 1 + class 2 over a whole tile, run the pit
  model on it, and look at candidates that appear ONLY in the reclassified
  version. Not obviously worth it given how small the surface change was, but it
  is the one gap the current result cannot close.
- **Scope is four tiles of PA WesternPA 2019 D20 (QL2).** Nothing here transfers
  to the McKean QL1 delivery or to any future acquisition. Re-run the same script
  on a new delivery before assuming its class 2 behaves the same way — it is one
  command and about 12 minutes.

## Phase 4 rollout leftovers (added 2026-09-04)

- **`_build_pad_road_dataset.py` has no argparse and no manifest guard.** It
  ignores `--help` and runs the full build. It regenerates
  `pad_dataset_manifest.csv`, `road_dataset_manifest.csv`,
  `labels_pad_9t_05.tif`, `labels_road_9t_05.tif` and `road_chunks_9t.gpkg`
  straight into `DERIV_9T` with no way to redirect, dry-run, or refuse. Same
  footgun `_build_pit_dataset_v2.py` just fixed. Give it the identical
  `--ann` / `--out-dir` / `--force` / `--dry-run` treatment.
- **The CV5 trainers reuse a checkpoint whenever `best.pt` exists and the epoch
  count is complete** (`_pit_unet_cv5.py:317`, same in `_pad_unet_cv5.py`). The
  comment justifies it as "a deterministic product of a fold that already ran",
  which holds only while the split is unchanged. When the split moves, the
  trainer silently keeps models trained on the old one. Worked around on
  2026-09-04 by moving the stale fold dirs into `_retired/` before retraining.
  Real fix: fingerprint the manifest (row count + hash) into `train_log.csv` and
  refuse to reuse a checkpoint whose fingerprint no longer matches.
- **`annotations_proj.gpkg` still uses the legacy layer names** `plat` and
  `pit_outside`. Reads work because `_common.read_layer()` resolves them through
  `LEGACY_LAYER_ALIASES`, so this is cosmetic, but the Phase 0 notebook was
  supposed to emit `pad` and `pit_full` and did not. Either finish the notebook
  rename or delete the aliases and accept the legacy names as canonical.
- **209 of 712 pit floors fall outside the 9t reference grid** and are marked
  `unused`, up from 56 of 527. Most recent annotation work is outside this tile.
  Worth confirming which area those pits belong to and whether they should be
  driving a second tile's dataset rather than sitting inert in the 9t manifest.
- **`docs/script_map.md` has no generator any more** -- only a stale
  `tools/__pycache__/map_scripts.cpython-313.pyc` remains. The file declares
  itself a historical record that is deliberately not rewritten, so this may be
  intentional; if so, say so in `tools/` rather than leaving an orphan `.pyc`.

## Methodology-audit findings (2026-07-01) — fix before trusting/publishing metrics

Full three-part audit in `analysis_log.md` (2026-07-01 methodology-evaluation entry). Ranked:

- ~~**Post-proc tuning happens ON the test blocks.**~~ **FIXED 2026-07-02**: `_road_optimize.py` / `_pit_optimize.py` and `_unet_instance_eval.py` now select on val, freeze, and score test once (pit post-proc test F1 0.155; road extraction test F1 0.754; both splits saved in the `*_postproc_best.json`).
- **Split leakage at block boundaries.** Patches (128–256 m + jitter) read a global label raster, so train patches overlapping test blocks see test labels; Mask R-CNN/YOLO explicitly paint off-split instances into targets (`_pit_maskrcnn.py` "Full polygon set (not just split)"); road ~40 m chunks are split by midpoint so adjacent chunks of the same road straddle train/test. Fix: split-mask the label rasters or erode a patch-radius buffer at block edges; build instance targets from the split subset.
- ~~**Instance metrics have no precision column and no 1:1 matching**~~ **FIXED 2026-07-02** (`per_instance_metrics` does greedy 1:1 + precision/F1; legacy loose recall kept as `recall_loose_*`). Result: precision is 3–6% on all four instance models. **Still open: the score-threshold sweep** — thresholds (0.3; YOLO pit 0.05) were never tuned. Cheap to do: re-threshold the saved `instances.gpkg` scores, select on val, freeze, rescore test — no GPU needed.
- **GT-local eval windows hide FPs**: per-object IoU computed inside GT bbox ±6/±15 m; "Line AP" samples probs only along GT lines (it's class separability, not detection AP). Relabel and add full-region numbers.
- **U-Net trainers unseeded** (only samplers take seeds; no `set_determinism`, no loader generator) → reported numbers not reproducible run-to-run. Val patches are also re-jittered every epoch, so best-epoch selection is noisy.
- ~~**Test n / dataset-era mixing**~~ **FIXED 2026-07-02**: all four instance evals re-run on the current 65/93 test split with same-era checkpoints (pad_05 Mask R-CNN retrained same day, best = ep 3); LEADERBOARD is now single-era with old numbers quarantined in a legacy block. Still open: report binomial CIs (n = 65/93 is still small).
- **DEP-well 0.42 recall lacks a null model**: compute random-point matching rate at 25 m before citing it.
- **NISAR language overshoots**: "InSAR proven viable over PA" rests on one beta fall pair (coherence 0.50, n=1); keep the seasonal-viability framing as a hypothesis until the validated CONUS release (~Jul 2026) + a multi-pair stack.
- **Barlow builder**: pin EDI package revisions at fetch time (currently auto-newest → provenance drift); fix flow-accum nodata→0 leak (`np.clip` turns nodata into log1p(0)=0 valid values); document the vertical-datum assumption (all three epochs ellipsoidal — constant offsets are absorbed by the DoD median-bias correction, but say so); curvature is profile (WBT) vs Barlow's ArcGIS standard curvature — a deliberate, documented deviation to keep.

## Pit/pad scoring + annotation (added 2026-08-04)

Full results in `docs/iterations/centroid_matching_pit_pad_9t.md`.

- **[DEFERRED 2026-08-04] Review the 187 unreviewed pit candidates.**
  `data/derivatives/eval_9t_centroid_matching/pit_candidates_filtered_heldout_9t.shp`.
  Pads went precision 0.623 -> 0.898 on a complete review; pits have had none, so
  the 0.72 vs 0.90 gap in the abstract is review effort, not model quality. User
  explicitly held this for another time.
- **Retrain the pad model.** Pads were never retrained. The 277 confirmed pads
  are scoring evidence only and are unused as training signal.
- **Rebuild pits on 503.** The retrain used the 12:35 label raster (471 in 9t);
  32 more floors and 37 rims arrived at 12:59, after it started.
- **`e1423n2235` (McKean) as a second block.** 56 annotated pits already sit
  there with a full 1 m derivative stack but no label raster or manifest, so they
  train nothing. This is the cheapest route to the held-out-TILE score that
  `benchmark_context_what_counts_as_good.md` ranks as the top methodology fix.
- **[METRIC] IoU is retired for pits and pads**, retained for roads. Centroid
  matching per Fiorucci et al. 2022 / Lidberg et al. 2024. Any older doc quoting
  pit/pad IoU recall is on the superseded metric.
- **Recall-from-verified-detections is circular** and must never be quoted.
  Precision may use confirmed detections; recall needs an independently drawn
  reference set. Applies to `well_head_pts_reprojected.gpkg` too — see the ICP
  circularity finding.
- 4 rims with no floor and 1 floor with no rim remain inside 9t.

## Road label coverage (added 2026-07-29) — HIGHEST PRIORITY for roads

Full results in `docs/iterations/road_bold_vs_faint.md`.

- **[PARTLY DONE 2026-07-30] The faint road class had ~zero labels.** The user
  added **159 lines / 15.55 km** to `roads.shp` inside 9t; faint exemplars
  present in the layer went 0/21 -> 18/21. The bold/faint cut now validates at
  **94.1% grouped CV** and the network splits 57.0% bold / 43.0% faint. Still
  open: the model remains blind to the class — exemplar-matched faint segments
  score **0.037** mean P(road) against 0.855 for bold. **Retrain the road model
  on the extended `roads.shp`** and re-measure; that is now the top road task.
- **[CRS ALERT 2026-07-31] Audit every read of `drainage.shp`.** It is stored in
  **EPSG:6346 with no `.prj`**, unlike `roads.shp`/`bold_roads.shp`/
  `faint_roads.shp` which are unprojected. The project-wide
  `set_crs(4326).to_crs(DST_CRS)` idiom therefore mangles it silently — length
  reads 0.00 km instead of 45.04 km, no exception. The road model uses drainage
  as a **negative class**, so any trainer applying that idiom placed its
  negatives at garbage coordinates. Also 986 of 2777 records have null geometry.
  Check `_road_unet*.py` and the drainage retrain before trusting those runs.
- **Inspect segment `f0058` at 622846.8, 4593369.5 (EPSG:6346).** Faint-labelled
  but sits inside the bold cluster on every trough metric (`opos` -3.43,
  `incision` 0.78 m > bold median 0.487) while scoring P_road 0.0007. Its only
  sibling on parent line 8 is flat (`opos` +0.08), so the line crosses something
  incised rather than following it. Likely a gully or ditch in the faint
  exemplar set. The `drainage.shp` test was inconclusive — nearest drainage
  annotation to any exemplar is 142 m, so that layer does not cover this ground.
- **Add 3 features to the bold/faint panel** (swept 2026-07-31, full table in
  `analysis_log.md`): `berm_min_m` (δ +0.964, beats `incision_depth_m`),
  `sgres19_zcontrast` (δ -0.963, raster never sampled), `raniso_zcontrast`
  (δ +0.862, replaces the quantised `roughness_11`). Low priority — all three
  correlate 0.72-0.86 with `opos_zcontrast`, so they add little to a
  single-feature cut. They matter only if the classifier goes multivariate,
  which at n = 79 labelled segments it should not yet.
- **Find a non-geometric channel.** Every feature that separates bold from faint
  is measuring the same trough. `intensity_ground` was the one surface-material
  candidate in `tiles/9t` and it fails (δ -0.200, p = 0.12). Nothing currently
  measures compaction, surface material, or vegetation regrowth. This is the
  actual limit on the panel, not the number of terrain derivatives.
- **`tread_flat_m` has a backwards sign** (bold rougher, 0.084 vs 0.035, δ
  +0.808). Suspect the |d| <= 2 m window catches the cut walls. Fix the window
  and retest before using.
- **Extend the faint labels beyond 9t.** 9t is one landscape, one survey, one
  annotator. Nothing here is known to transfer.
- **Every published road metric is bold-conditional.** The 0.754 extraction F1,
  [[road_unet_1m_recall]] recall figures, and the alpha tuning in
  [[road_recall_alpha_fix]] were scored against `roads.shp`, which contains only
  bold roads. Re-state the restriction or re-measure once faint labels exist.
- **The 613590 added roads are probably this class.** 373 lines / 37.68 km the
  user drew as model misses. Check their morphology against the faint profile
  before treating them as ordinary hard positives — if they are the faint class,
  they are the seed of the missing label set.
- **Resolve the pad confound.** All 8 bold exemplars touch an annotated pad
  (`dist_pad_m` = 0 vs 126 m for faint), so bold-vs-faint is entangled with
  pad-adjacent-vs-not. Label bold roads away from pads and faint roads at pads
  to break it.
- **[DONE 2026-07-30] Grow the exemplar set.** Superseded by matching exemplars
  to `roads.shp` segments: 79 matched segments (37 bold / 42 faint) instead of
  29 lines, which supports grouped cross-validation. AUC 0.990, CV 94.1%.
- **The 3 orphan faint exemplars.** 18 of 21 faint exemplars now match a
  `roads.shp` line; 3 remain 54.9-107.2 m from anything. Either they are a
  different feature type or they are still unannotated roads. Check them.
- **CHM is unusable as a median.** `chm_9t_05` is zero-inflated (tile median
  0.091 m, p99 25.8 m). Any analysis wanting canopy must use a cover fraction
  (CHM > 2 m) or a high percentile. Audit prior uses of CHM medians.

## Road expansion / drainage (added 2026-07-29)

Full results in `docs/iterations/drainage_review_613590.md`.

- **Fetch LAZ for the 10 unbuildable westernpa_d20 blocks.** 604608, 609608,
  613608, 618591, 618608, 622591, 622594, 622599, 622603, 622608 have DEMs on
  disk but no source LAZ, so `enumerate_blocks` skips them and no water mask
  (or any class-9 product) can be built. Water coverage is 15/15 of *buildable*
  blocks, not 25/25. This gates water masking on 40% of the Venango footprint.
- **Apply the water mask inside the road pipeline, not just as a diagnostic.**
  `water_banks` removes 22.2% of 613590's human-rejected road segments at zero
  cost to real roads. Decide whether it belongs as a `to_mask()` gate in
  `_road_optimize.py`, an extra U-Net input channel, or a training negative —
  the project's fix-in-training preference argues for the last.
- **Regenerate the 613590 road review from the corrected model + water mask.**
  55% of the current deletions are already fixed by `road_unet_1m_corrected`
  and 22% are water, so most remaining review effort is redundant. Write to a
  new `review_r2/` so in-progress edits survive.
- **Review the 613590 drainage package** (`review_drainage/`, 1,131 segments /
  30.60 km) and draw missed channels into `added_drainage_613590.gpkg`, then
  ingest as a corrections block mirroring `_build_road_corrections_613590.py`.
- **clDice drainage retrain.** The vectorized drainage is fragmented — many
  short disconnected stubs instead of connected downhill networks. Topology
  failure, not placement failure. clDice won the connectivity pole in
  [[road_sweep_202607]] and suits drainage better than roads (it was designed
  for tubular connected structures); the loss is already implemented in
  `_road_sweep_202607.py`. Deliberately NOT fixed by post-hoc bridging — an
  invented channel taught as a positive is worse than a gap drawn by hand.
- **Re-check other extraction params inherited across tasks.** The 100 m island
  filter cost drainage 27 points of completeness purely because it was carried
  over from roads. `_road_optimize.py`'s other stages (spur prune, min_px,
  hysteresis bounds) were tuned for roads too and are reused unaudited wherever
  a new linear feature is vectorized.
- **Drainage labels exist for 9t only.** `drainage.shp` spans x 620,659–624,000;
  any block outside that runs the drainage class unsupervised (`gt_dist_m` is
  null for all 1,131 613590 segments). Consider per-region drainage labels or a
  hydrology-derived weak label (flow accumulation) as a substitute.
- **The road sweep tiebreak is still open.** `cldice` vs `boundary` through
  `_road_optimize.py` extraction vs the 0.754 test F1, per
  [[road_sweep_202607]]. Blocked on nothing — `_road_optimize.py` hardcodes
  `MODEL_DIR_NAME` and needs a `--model-dir` flag.
- **25 Venango blocks still carry June-8 road_prob rasters**, two model
  generations stale, and only 613590 has been vectorized. Re-inference is
  ~25 s/block (~11 min for all 25) once a champion is declared.

## From the pit 5-fold cross-validation (added 2026-07-27)

Full results in `docs/iterations/pit_unet_cv5_9t.md`.

- ~~**Every pit number rests on one 65-pit split.**~~ **FIXED 2026-07-27**: 5-fold CV scores all 426 pits, each by a model that never saw it. Pooled R@0.3 = 0.854 (F1-selected) / 0.920 (F2-selected). The single split was pessimistic, not optimistic.
- ~~**Do the same 5-fold treatment for pads.**~~ **DONE 2026-07-28**: all 650 pads scored, pooled R@0.3 0.917 (F1-sel, sd 0.021) / 0.920 (F2-sel), P 0.606. Single split (0.882/0.547) was pessimistic, same as pits. See [[pad_unet_cv5_9t]].
- **Score on 613590 as a genuinely held-out tile.** Every CV fold is still 9t — one landscape, one survey, one annotator. CV proves the number is *stable*, not that it *transfers*. This remains the single largest unquantified optimism in every pit and pad number we publish. Blocked on 613590 having zero hand annotations (annotations start at x≈619,503; the tile spans 613,500–618,000), so it needs annotation work first.
- **Precision is the ceiling, not recall.** Pit precision never exceeds 0.65 at any of the 16 thresholds swept, while recall reaches 0.94. Whatever is generating the extra polygons is where the next real gain is — not in recall tuning.
- **Recompute `feature_stats.json` per fold.** Currently 7 means + 7 sds from the original train blocks are reused across all folds, leaking 14 global numbers into each. Effect is small; disclosed in the write-up rather than fixed.
- **CV gives a spread, so use it.** Per-fold sd (0.035 under F2, 0.088 under F1) is now a real basis for saying whether a difference between two models is a result. Apply it before quoting any future 3-point improvement.

- ~~**CV inner-val draw is execution-order dependent.**~~ **FIXED 2026-07-28**: both CV scripts now seed per fold (`CV_SEED + 1000 * k`), so the draw no longer depends on which folds run. Held-out sets were never affected, so no published number is invalid. Pad folds 0–1 vs 2–4, and pit fold 4, were drawn under the old behaviour and are disclosed in their iteration docs.

## From the pit/pad/road threshold sweeps (added 2026-07-27)

Full results in `docs/iterations/threshold_sweeps_pit_pad_road_9t.md`.

- **The PAD model is now the highest-value target, not the pit model.** At its best operating point (0.45–0.50) it reaches 0.918 recall on 194 held-out pads while claiming **10–12% of the tile**. Pit hits 0.992 at 0.21% and road 0.982 at 4–5%. Pad also claims ~197.95 ha at 0.50 against roughly 110 ha of total annotated pad area, so it is over-claiming by ~2x.
- **Pad probability background is 4x the road model's** (tile mean 0.162 vs 0.039). Determine whether this is the focal-loss under-confidence issue from the refinement survey, or a genuine class-prior problem. It is what makes pad predictions merge into super-blobs below ~0.30.
- **Road chunk leakage is now quantified: 485/1220 held-out chunks (39.8%) share a parent road with train chunks.** `recall_clean` (735 clean chunks, 221 fully-held-out parent roads) is a reporting workaround, not a fix — the real fix is splitting by parent road, not by chunk. Measured cost of the leakage is ~1.5 points of recall, so this is a correctness/reporting issue rather than a result-changing one.
- **Single found/missed criteria are not safe across tasks.** The pit centroid-containment rule reported 0/194 pads found at threshold 0.05 purely from blob merging. Any new task needs its criteria checked at both ends of the sweep before the numbers are trusted.

## Pit U-Net refinements (added 2026-07-27)

Full survey with citations in `docs/iterations/pit_refinement_options.md`. Ordered cheapest-first; steps 1–4 need no retraining and score on the existing 127 held-out rims via `_heldout_rim_containment_9t.py`.

- **1. Diagnose fragmentation vs the 128 m patch grid** (~1 h, no retrain). Decides whether fragmented pit floors are an inference-stitching artifact or a model property. Do this before spending a day on a loss function.
- **2. Cosine/Hann patch feathering** (~2 h, no retrain). `_dl.py:445-449` blends overlapping patches with a uniform box mean, so one-sided-context edge predictions get the same weight as full-context centre predictions.
- **3. D4 test-time augmentation** (~2 h, no retrain). Wang et al. 2019. Nadir terrain rasters have no canonical orientation, so the equivariance assumption holds exactly. Targets both low confidence and fragmentation.
- **4. Temperature scaling on val** (~1 h, no retrain). Guo et al. 2017. Monotonic, so it cannot change recall at a re-tuned threshold — this is for honest reporting and threshold transfer between tiles, not for finding new pits.
- **5. Sky-view factor channel + redundancy check** (~2 h). Zakšek et al. 2011, motivated by Suh et al. 2021 (VAT best-performing on relict charcoal hearths, the closest published analogue to this project). **Must** correlate against `openness_pos` first — this is the same shape of claim that got RRIM rejected as a model input.
- **6. Focal + Tversky region term** (~1 d, retrain). Salehi et al. 2017 / Abraham & Khan 2019. `beta > alpha` buys recall and restores the incentive to saturate confident pixels that pure focal removes.
- **7. Boundary loss term** (~1 d, retrain). Kervadec et al. 2019. Pit floors are 0.14–0.21% of the tile, the imbalance regime it targets.
- **8. Betti-0 topology loss** (~3 d, retrain). Hu et al. 2019 + Stucki et al. 2024. The pit-shaped analogue of clDice — clDice is for tubular structures and is wrong for blobs. Encodes "one annotated pit is one component". Park until 1–4 are measured.

## High priority — directly limits current results

- **~~Grow the training label set~~ → USE the grown label set (updated 2026-07-01).** The old "110 pit / 79 pad" figure is stale: annotations now total **426 pits / 1,053 pads** (user annotation push). The 2026-06-10 dataset rebuild picked up all 426 pits + the 650 pads inside 9t (test split now 65 pits / 93 pads), and the U-Nets were retrained on it. Still outstanding: (a) **403 pads lie outside 9t** and are in NO dataset — they need per-region feature stacks; (b) ~~**~58 newest pads** postdate the last `annotations_proj.gpkg` regen (pad.shp 1053 vs gpkg 995) — re-run `_prep_annotations` + dataset rebuild~~ **RESOLVED 2026-07-19 (misdiagnosis):** the 58 are null-geometry rows in `pad.shp` (QGIS delete artifacts), not new pads — gpkg 995 = every pad with geometry, nothing stale. Optionally purge the null rows from the shapefile; (c) ~~the instance models' saved test metrics are stale~~ — DONE 2026-07-02, all four re-run on the 65/93 split (see LEADERBOARD).
- **Pad over-prediction is unsolved — and now quantified.** The 2026-07-02 re-eval puts pad_05 at P@0.3 = 0.029 (3,075 detections / 93 GT); pit models sit at ~5%. Next: (a) **score-threshold sweep selected on val** (re-threshold saved `instances.gpkg` — no GPU), (b) active-learning hard negatives. Feature richness was NOT the fix; more data alone wasn't either (9× pads did not move precision).
- **Oil Creek inference — `roughness_11` blocker is now UNBLOCKED (2026-09-19).**
  Derivatives built at 0.5 m but `_build_derivatives.py` only writes
  `roughness_5`. `build_roughness_11()` in
  `notebooks/wellsight_v2/s7_analysis/_smrf_feature_stack_9t.py` generates the
  missing band from the DEM with the builder's own formula at WIN=11; verified
  against the vendor band at corr 0.996, mean |diff| 0.0013. Lift that function
  into `_build_derivatives.py` rather than copying it a third time. Then →
  assemble `features_oilcreek_22tile_05.tif` (7 bands, canonical order) → run
  pit/pad inference. Still open: whether 9t-derived `mu`/`sd` transfer or must be
  recomputed per region. See [[oilcreek_derivatives_05]].
  **Correction to the standing note:** `roughness_11` is a mislabel of
  `roughness_5` **at 1 m only**, where a 5-cell window spans the same ground as
  11 cells at 0.5 m. At 0.5 m the vendor band is a genuine 11×11 and the two are
  different surfaces (5×5 recomputation correlates 0.568, means 0.076 vs 0.151).
  Do not substitute one for the other at 0.5 m.

## Promotion candidates from diagnostics (2026-06-03)

- **Add `depth_in_sink` + `geomorphons` to the pit feature stack.** Validated as the strongest hand-crafted pit signals: depth-in-sink hits 90% of pit centroids (vs 1% background); geomorphons puts 106/110 pits in concave classes. See [[diagnostics_9t]]. **Before promoting:** recompute at 0.5 m and measure the full-tile false-positive rate (culverts, natural kettles) — they were only validated *at* known pits, not for precision.
- **Evaluate curvature (profile/plan) + `sar` for pad/road edges** — promising but not yet quantitatively validated; eyeball in QGIS first.
- ~~**Clean residual road false-positives (drainage/waterways).**~~ SUPERSEDED 2026-06-08 by the **in-model fix**: 3-class road U-Net (bg/road/drainage) trained with `drainage.shp` as an explicit class ([[road_unet_1m]] §v2). P(road) on drainage → 0.006. The post-hoc `_refine` drainage filter ([[road_refine]]) is retired (was too aggressive, terrain-dependent).
- **Vectorize per-block road rasters → line features (deferred).** `_refine_roads_data_3x3.py` can do this (skeletonize + `skan` + gap-bridging) but is retired for now; current pipeline uses the 3-class raster outputs (`road_prob`/`drainage_prob`/`road_argmax`) directly. Revisit when line features are needed for well cross-referencing. The stale `roads_<key>_1m.gpkg`/`road_clean_*` from the 2-class rollout are obsolete and can be deleted.
- **Cross-reference refined roads against well candidates.** Now that roads are vector lines, use proximity-to-road-remnant as a well-access signal in candidate scoring.
- **Per-region road model + refine check** — the 1 m road model and the drainage-refine params (`xdrop`/stream thresholds) were tuned on the 9t / Venango-area WesternPA D20 blocks. Spot-check a northcentral_b19 (mckean) block before trusting roads or the refine rule there.

## Well-age binning follow-ups (from [[well_age_morphology]], 2026-07-19)

- **DEM-derived per-well era features** — pit depth (depth_in_sink at well point), pad cut/fill volume, road width at nearest road. 2-D outlines gave AUC 0.66 (1956–79 vs 1980–99); 3-D relief may carry more of the era signal.
- **Annotate a sentinel-1800-dense block** to power the historic-vs-modern morphology contrast — the annotated 9t footprint holds only 46 sentinel wells (20 pad-matched), all tests ns.
- **Purge the 58 null-geometry rows from `pad.shp`** next annotation pass.

## Linear-feature channel refinements (from lit review + agent bench diagnosis, 2026-07-23)

Context: `_build_extra_channels.py` added SavGol quadratic residual + top-hat cut/fill
channels after the agent's diagnosis that LRM unsharp mask is curvature-contaminated
(`DEM − focal_mean` leaks `(σ²/2)∇²z`). Confirmed on 613590_05 (see docs/iterations
write-up). Deferred refinements from that same advice:

- **Robust IRLS quadratic fit** — bisquare weights, 2–3 iterations, so the cutbank/fill
  lip don't drag the trend surface toward the feature being isolated. Incremental over
  the plain SavGol; matters most on narrow benches in tight windows.
- **Slope-normal residual frame** — on sustained >30° Appalachian sideslopes, fit a
  broad-window plane, rotate the neighborhood to hillslope-horizontal, measure residual
  perpendicular. Vertical residual under-reads bench depth by ~cos(θ) and smears the
  cut/fill pair. Makes one threshold work basin-wide instead of tuning by aspect. Heaviest
  piece (per-pixel plane fit + rotation) — the highest-value follow-up.
- **1D perpendicular-transect detector** — cast rays perpendicular to contours at ~2 m,
  robustly detrend each 1D profile, detect benches on the transect. Cheap, debuggable
  escape hatch; per-transect detections link into paths readily.
- **Feed winners into the road model** — test SavGol residual + `frangi_lrm` + `rough_aniso`
  (+ `ridge_orient`) as road-U-Net input channels vs the current 7. Prior separability test
  said bolt-on channels give diminishing returns, but those were elevation/derivative
  channels, not ridge/orientation — re-test.
- **Fix Sato cross-hatch artifact** — raise the min sigma so the small-scale Hessian stops
  picking up the QL2 scan-pattern / interpolation-grid weave.

## Model / architecture ideas (deferred)

- ~~**Does a bigger or pretrained network beat the plain U-Net?**~~ **ANSWERED
  2026-09-19, no** — `docs/iterations/arch_compare_1m_four_architectures.md`. Four
  architectures, same folds, same channels, same schedule, 1 m. Every rung of the
  ladder is inside the fold-to-fold noise: deeper encoder −0.031 pit / +0.013 pad,
  ImageNet pretraining +0.020 / +0.032, dense skips +0.013 / −0.004, against
  pooled sds of 0.018–0.035. A 26.1 M U-Net++ scores 0.561 where the 7.8 M plain
  U-Net scores 0.559. **Keep the plain U-Net.** Two follow-ups survive:
  - **Pretraining is the only rung worth re-testing.** Largest positive delta on
    both targets and the only one with the same sign on both, but still short of
    the noise on five folds. More seeds or more folds would settle it; nothing
    else in that table would.
  - **The comparison is segmentation IoU, not detection.** Whether any of these
    gaps move recall at IoU 0.3 is unmeasured, and the leaderboard speaks in
    detection terms. Scoring the 40 existing checkpoints held-out needs no
    training, only inference.
- **`roaddrain` has no architecture row.** `_arch_compare_9t_1m.py --target
  roaddrain --arch unet` ran 1 of 40 epochs on fold 0 and stopped. Nothing usable.
- **`_arch_compare_9t_1m.py` hides its own failures.** It writes
  `pooled_metrics.json` only when a single invocation finishes every requested
  fold, so a run that dies partway leaves no summary at all — that is how 37
  finished folds sat unscored. Its docstring also promises a per-fold
  `fold_metrics.json` it never writes. Fix the trainer, or keep using
  `s5_eval/_aggregate_arch_compare_1m.py`, which reads the folds directly.
- **ConvNet / ConvNeXt backbones** as alternatives to ResNet50-FPN for the detectors.
- **TerraScan** evaluation for point-cloud classification / feature extraction.
- **Overfit mitigations** for the thin-data regime: smaller backbone, frozen FPN, stronger augmentation, explicit early-stopping (we already know best ckpt = ep 0–1).
- **YOLO multi-channel support.** YOLO pit/pad models are still 3-band (rgb3); Mask R-CNN moved to the 7-band stack. Widen YOLO input to 7 bands for an apples-to-apples comparison.

## ICP / change detection

- **[DONE 2026-07-31] Rebuilt with one ICP solve.** Per-tile spread 0.103 →
  0.0576 m, robust sigma 0.1358 → 0.1119 m, reconstruct test now exact. Use
  `dod_9t_singleicp_2m.tif`. See [[icp_change_9t]] Part 3.
- **[CIRCULARITY 2026-07-31] `well_head_pts_reprojected.gpkg` is NOT a well
  list.** It is byte-identical to `wellhead_pits.gpkg` — 861 hand-digitised
  pits placed on the 2019 DEM. Any test that compares a 2019-derived product
  against these points is circular. It produced an apparent 14.63%-vs-4.08%
  DoD signal (p = 0.001 under a spatial null) that is fully explained by the
  2006-08 survey resolving only 72% of pit depth at 7x lower density. **Get a
  non-DEM-derived well list (DEP permit coordinates) before any further
  validation against "known wells".** Audit past work that used this layer as
  ground truth.
- **[STALE 2026-07-31] Part 2 outputs derive from the superseded DoD.**
  `change_class_9t_2m.tif`, `change_class_reliable_9t_2m.tif`,
  `dod_9t_nonerosional_2m.tif`, `change_patches_9t.gpkg`. The destripe/
  high-pass stack was tuned against blocky artifacts that no longer exist;
  re-derive on `dod_9t_singleicp_2m.tif` before trusting the 16 "reliable
  non-erosional patches".
- **Destriping is the only lever left on the 9t DoD.** Row-mean std 0.0786 m
  (3.7x the column-mean std); removing row+col means takes sigma 0.1119 →
  0.0877 m, a 22% gain.
- **[SUPERSEDED] Rebuild the 9t DoD — the shipped one fails its own
  reconstruct test.** `dem_diff_2m.tif` covers 99.97% of 9t while the
  `dem_new_2m.tif` it was supposedly built from covers 44.4%, and
  `diff − (new − old)` has mean |r| 0.24 m against a DoD σ of 0.14 m (not a
  shift — ±4 px scanned, dy=dx=0 optimal). The repo script is not the version
  that made the rasters (rasters 2026-05-21; `_icp_change_map.py` edited
  2026-05-22 `acce517`, 2026-05-23 `375f9f5`) and its `mosaic_3x3` input no
  longer exists. Rebuild reading `dem_9t_05.tif` as the 2019 side instead.
  Inputs are all on hand. See [[icp_change_9t]].
- **[CORRECTION 2026-07-31] The ±0.22 m "acquisition striping" is really
  per-tile ICP residual bias.** Median DoD per old-tile footprint: 002958
  −0.038, 002959 −0.057, 003111 +0.046, 003112 +0.044 m — 0.103 m spread vs a
  0.136 m pooled σ. Each tile was solved independently and the mosaic butts the
  biases together. Fix at the source: one ICP across the merged tile set, or
  remove per-tile vertical offsets on the overlaps before mosaicking. This also
  means Part 2's destripe/high-pass stack was tuned against the wrong artifact
  geometry, so the 16 "reliable non-erosional patches" are not trustworthy.
- **[CRS ALERT 2026-07-31] Never read the 2006-2008 LAZ without forcing
  EPSG:2271.** Their WKT is self-contradictory — ftUS false easting (1968500)
  and ftUS units, but stamped `AUTHORITY["EPSG",32128]` (the metre variant).
  PDAL's derived proj4 is the mangled hybrid `+x_0=600000 +units=us-ft`;
  trusting it lands the data ~417 km off. `_icp_change_map.py` already
  hard-codes 2271, so existing work is safe.
- **Six more 2006-2008 tiles are now on disk** (`002960, 003113, 003254-003257`
  in `F:\lidar_project\consolidated\lidar_all\`). None overlap 9t — they extend
  the change footprint north and east to X[616093..628618]
  Y[4592119..4601369]. Only useful if the change-detection line continues.
- **Vegetation / canopy masking** before differencing.
- **Decide whether recent-activity change detection is a project goal.** The
  2006→2019 pair provably cannot find historic orphaned wells (they predate both
  surveys; no significant DoD signal at 540 known wells). It *can* find new pads,
  regrading, plugging, and subsidence. If that is not a goal, this line stops.
- **Clean up the stale failed-run metadata** at
  `data/derivatives/experiments/icp/003111/_meta_icp_5m.json` (`converged: false`,
  fitness 39.4) — superseded, but misleading to anyone reading it directly.

## Data quality / coverage

- **Better / more LiDAR data** — broader, higher-density, or newer surveys; current tiles vary by survey (see provenance note in [[streams_9t_t5000]]).
- **Per-region normalization stats** — confirm whether 9t `mu`/`sd` generalize to other regions or each region needs its own `feature_stats.json`.

## Documentation / housekeeping

- **Full pad→pad rename** is partial: on-disk artifacts still use legacy `pad` names (GPKG layer `pad`, `pad_dataset_manifest.csv`, `pad_unet`). Code has back-compat aliases. Finish the rename when convenient.
- Keep `analysis_log.md`, per-iteration docs, and `LEADERBOARD.md` current each pass (see CLAUDE.md documentation-maintenance rule).
