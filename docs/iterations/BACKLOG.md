# WellSight Backlog — "things we said we'd revisit"

Live list of deferred ideas and open follow-ups. Check this before proposing new directions. Recreated 2026-06-03 (the prior file was missing from disk).

## High priority — directly limits current results

- **Grow the training label set (the #1 bottleneck).** 110 pit / 79 pad hand annotations is too thin for a 45.9 M-param Mask R-CNN — every run overfits by epoch 0–1. The PA DEP catalog has **1069 wells in the 9t tile alone** (<11% annotated). Seed semi-automated annotation: snap a candidate to the nearest LiDAR depression, human-confirm, to grow labels ~10×. Strongest lever on both recall and precision.
- **Pad over-prediction is unsolved.** pad_05 v2 (7-band) still emits ~2546 detections for ~79 real pads. The 7-band stack only cut FPs 22%. Next: (a) **score-threshold sweep** to find the precision/recall knee, (b) more data per above. Feature richness was NOT the fix.
- **Oil Creek inference — blocked on `roughness_11`.** Derivatives built at 0.5 m but only `roughness_5` exists; need `roughness_11` → assemble `features_oilcreek_22tile_05.tif` (7 bands, canonical order) → run pit/pad inference. Also decide whether 9t-derived `mu`/`sd` transfer or must be recomputed per region. See [[oilcreek_derivatives_05]].

## Promotion candidates from diagnostics (2026-06-03)

- **Add `depth_in_sink` + `geomorphons` to the pit feature stack.** Validated as the strongest hand-crafted pit signals: depth-in-sink hits 90% of pit centroids (vs 1% background); geomorphons puts 106/110 pits in concave classes. See [[diagnostics_9t]]. **Before promoting:** recompute at 0.5 m and measure the full-tile false-positive rate (culverts, natural kettles) — they were only validated *at* known pits, not for precision.
- **Evaluate curvature (profile/plan) + `sar` for pad/road edges** — promising but not yet quantitatively validated; eyeball in QGIS first.

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
