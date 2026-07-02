# WellSight Backlog — "things we said we'd revisit"

Live list of deferred ideas and open follow-ups. Check this before proposing new directions. Recreated 2026-06-03 (the prior file was missing from disk).

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

## High priority — directly limits current results

- **~~Grow the training label set~~ → USE the grown label set (updated 2026-07-01).** The old "110 pit / 79 pad" figure is stale: annotations now total **426 pits / 1,053 pads** (user annotation push). The 2026-06-10 dataset rebuild picked up all 426 pits + the 650 pads inside 9t (test split now 65 pits / 93 pads), and the U-Nets were retrained on it. Still outstanding: (a) **403 pads lie outside 9t** and are in NO dataset — they need per-region feature stacks; (b) **~58 newest pads** postdate the last `annotations_proj.gpkg` regen (plat.shp 1053 vs gpkg 995) — re-run `_prep_annotations` + dataset rebuild; (c) ~~the instance models' saved test metrics are stale~~ — DONE 2026-07-02, all four re-run on the 65/93 split (see LEADERBOARD).
- **Pad over-prediction is unsolved — and now quantified.** The 2026-07-02 re-eval puts pad_05 at P@0.3 = 0.029 (3,075 detections / 93 GT); pit models sit at ~5%. Next: (a) **score-threshold sweep selected on val** (re-threshold saved `instances.gpkg` — no GPU), (b) active-learning hard negatives. Feature richness was NOT the fix; more data alone wasn't either (9× pads did not move precision).
- **Oil Creek inference — blocked on `roughness_11`.** Derivatives built at 0.5 m but only `roughness_5` exists; need `roughness_11` → assemble `features_oilcreek_22tile_05.tif` (7 bands, canonical order) → run pit/pad inference. Also decide whether 9t-derived `mu`/`sd` transfer or must be recomputed per region. See [[oilcreek_derivatives_05]].

## Promotion candidates from diagnostics (2026-06-03)

- **Add `depth_in_sink` + `geomorphons` to the pit feature stack.** Validated as the strongest hand-crafted pit signals: depth-in-sink hits 90% of pit centroids (vs 1% background); geomorphons puts 106/110 pits in concave classes. See [[diagnostics_9t]]. **Before promoting:** recompute at 0.5 m and measure the full-tile false-positive rate (culverts, natural kettles) — they were only validated *at* known pits, not for precision.
- **Evaluate curvature (profile/plan) + `sar` for pad/road edges** — promising but not yet quantitatively validated; eyeball in QGIS first.
- ~~**Clean residual road false-positives (drainage/waterways).**~~ SUPERSEDED 2026-06-08 by the **in-model fix**: 3-class road U-Net (bg/road/drainage) trained with `drainage.shp` as an explicit class ([[road_unet_1m]] §v2). P(road) on drainage → 0.006. The post-hoc `_refine` drainage filter ([[road_refine]]) is retired (was too aggressive, terrain-dependent).
- **Vectorize per-block road rasters → line features (deferred).** `_refine_roads_data_3x3.py` can do this (skeletonize + `skan` + gap-bridging) but is retired for now; current pipeline uses the 3-class raster outputs (`road_prob`/`drainage_prob`/`road_argmax`) directly. Revisit when line features are needed for well cross-referencing. The stale `roads_<key>_1m.gpkg`/`road_clean_*` from the 2-class rollout are obsolete and can be deleted.
- **Cross-reference refined roads against well candidates.** Now that roads are vector lines, use proximity-to-road-remnant as a well-access signal in candidate scoring.
- **Per-region road model + refine check** — the 1 m road model and the drainage-refine params (`xdrop`/stream thresholds) were tuned on the 9t / Venango-area WesternPA D20 blocks. Spot-check a northcentral_b19 (mckean) block before trusting roads or the refine rule there.

## Model / architecture ideas (deferred)

- **ConvNet / ConvNeXt backbones** as alternatives to ResNet50-FPN for the detectors.
- **TerraScan** evaluation for point-cloud classification / feature extraction.
- **Overfit mitigations** for the thin-data regime: smaller backbone, frozen FPN, stronger augmentation, explicit early-stopping (we already know best ckpt = ep 0–1).
- **YOLO multi-channel support.** YOLO pit/pad models are still 3-band (rgb3); Mask R-CNN moved to the 7-band stack. Widen YOLO input to 7 bands for an apples-to-apples comparison.

## Data quality / coverage

- **Better / more LiDAR data** — broader, higher-density, or newer surveys; current tiles vary by survey (see provenance note in [[streams_9t_t5000]]).
- **Per-region normalization stats** — confirm whether 9t `mu`/`sd` generalize to other regions or each region needs its own `feature_stats.json`.

## Documentation / housekeeping

- **Full plat→pad rename** is partial: on-disk artifacts still use legacy `plat` names (GPKG layer `plat`, `plat_dataset_manifest.csv`, `plat_unet`). Code has back-compat aliases. Finish the rename when convenient.
- Keep `analysis_log.md`, per-iteration docs, and `LEADERBOARD.md` current each pass (see CLAUDE.md documentation-maintenance rule).
