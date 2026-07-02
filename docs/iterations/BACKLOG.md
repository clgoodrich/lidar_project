# WellSight Backlog — "things we said we'd revisit"

Live list of deferred ideas and open follow-ups. Check this before proposing new directions. Recreated 2026-06-03 (the prior file was missing from disk).

## Methodology-audit findings (2026-07-01) — fix before trusting/publishing metrics

Full three-part audit in `analysis_log.md` (2026-07-01 methodology-evaluation entry). Ranked:

- **Post-proc tuning happens ON the test blocks.** `_road_optimize.py` / `_pit_optimize.py` coordinate-ascend F1 against `split=='test'` GT and report that same F1. Also the U-Net LEADERBOARD instance rows are "best of a {0.3,0.5,0.7} threshold sweep" on test. Fix: tune on val, freeze, report test once.
- **Split leakage at block boundaries.** Patches (128–256 m + jitter) read a global label raster, so train patches overlapping test blocks see test labels; Mask R-CNN/YOLO explicitly paint off-split instances into targets (`_pit_maskrcnn.py` "Full polygon set (not just split)"); road ~40 m chunks are split by midpoint so adjacent chunks of the same road straddle train/test. Fix: split-mask the label rasters or erode a patch-radius buffer at block edges; build instance targets from the split subset.
- **Instance metrics have no precision column and no 1:1 matching** (`per_instance_metrics`: best-IoU per GT, one prediction can match many GT, floor 0.1 IoU). With SCORE_THRESH 0.05 and 2–3k detections vs 79–110 GT, recall headlines are near-free. Fix: greedy 1:1 matching + precision/AP; run the long-promised score-threshold sweep.
- **GT-local eval windows hide FPs**: per-object IoU computed inside GT bbox ±6/±15 m; "Line AP" samples probs only along GT lines (it's class separability, not detection AP). Relabel and add full-region numbers.
- **U-Net trainers unseeded** (only samplers take seeds; no `set_determinism`, no loader generator) → reported numbers not reproducible run-to-run. Val patches are also re-jittered every epoch, so best-epoch selection is noisy.
- **Test n is tiny** (20 pits / 9 pads): report binomial CIs alongside recall; treat single-model deltas <2 test items as noise.
- **DEP-well 0.42 recall lacks a null model**: compute random-point matching rate at 25 m before citing it.
- **NISAR language overshoots**: "InSAR proven viable over PA" rests on one beta fall pair (coherence 0.50, n=1); keep the seasonal-viability framing as a hypothesis until the validated CONUS release (~Jul 2026) + a multi-pair stack.
- **Barlow builder**: pin EDI package revisions at fetch time (currently auto-newest → provenance drift); fix flow-accum nodata→0 leak (`np.clip` turns nodata into log1p(0)=0 valid values); document the vertical-datum assumption (all three epochs ellipsoidal — constant offsets are absorbed by the DoD median-bias correction, but say so); curvature is profile (WBT) vs Barlow's ArcGIS standard curvature — a deliberate, documented deviation to keep.

## High priority — directly limits current results

- **Grow the training label set (the #1 bottleneck).** 110 pit / 79 pad hand annotations is too thin for a 45.9 M-param Mask R-CNN — every run overfits by epoch 0–1. The PA DEP catalog has **1069 wells in the 9t tile alone** (<11% annotated). Seed semi-automated annotation: snap a candidate to the nearest LiDAR depression, human-confirm, to grow labels ~10×. Strongest lever on both recall and precision.
- **Pad over-prediction is unsolved.** pad_05 v2 (7-band) still emits ~2546 detections for ~79 real pads. The 7-band stack only cut FPs 22%. Next: (a) **score-threshold sweep** to find the precision/recall knee, (b) more data per above. Feature richness was NOT the fix.
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
