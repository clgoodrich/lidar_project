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

- **~~Grow the training label set~~ → USE the grown label set (updated 2026-07-01).** The old "110 pit / 79 pad" figure is stale: annotations now total **426 pits / 1,053 pads** (user annotation push). The 2026-06-10 dataset rebuild picked up all 426 pits + the 650 pads inside 9t (test split now 65 pits / 93 pads), and the U-Nets were retrained on it. Still outstanding: (a) **403 pads lie outside 9t** and are in NO dataset — they need per-region feature stacks; (b) ~~**~58 newest pads** postdate the last `annotations_proj.gpkg` regen (plat.shp 1053 vs gpkg 995) — re-run `_prep_annotations` + dataset rebuild~~ **RESOLVED 2026-07-19 (misdiagnosis):** the 58 are null-geometry rows in `plat.shp` (QGIS delete artifacts), not new pads — gpkg 995 = every pad with geometry, nothing stale. Optionally purge the null rows from the shapefile; (c) ~~the instance models' saved test metrics are stale~~ — DONE 2026-07-02, all four re-run on the 65/93 split (see LEADERBOARD).
- **Pad over-prediction is unsolved — and now quantified.** The 2026-07-02 re-eval puts pad_05 at P@0.3 = 0.029 (3,075 detections / 93 GT); pit models sit at ~5%. Next: (a) **score-threshold sweep selected on val** (re-threshold saved `instances.gpkg` — no GPU), (b) active-learning hard negatives. Feature richness was NOT the fix; more data alone wasn't either (9× pads did not move precision).
- **Oil Creek inference — blocked on `roughness_11`.** Derivatives built at 0.5 m but only `roughness_5` exists; need `roughness_11` → assemble `features_oilcreek_22tile_05.tif` (7 bands, canonical order) → run pit/pad inference. Also decide whether 9t-derived `mu`/`sd` transfer or must be recomputed per region. See [[oilcreek_derivatives_05]].

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
- **Purge the 58 null-geometry rows from `plat.shp`** next annotation pass.

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

- **ConvNet / ConvNeXt backbones** as alternatives to ResNet50-FPN for the detectors.
- **TerraScan** evaluation for point-cloud classification / feature extraction.
- **Overfit mitigations** for the thin-data regime: smaller backbone, frozen FPN, stronger augmentation, explicit early-stopping (we already know best ckpt = ep 0–1).
- **YOLO multi-channel support.** YOLO pit/pad models are still 3-band (rgb3); Mask R-CNN moved to the 7-band stack. Widen YOLO input to 7 bands for an apples-to-apples comparison.

## ICP / change detection

- **Per-swath / per-tile bias correction of the 2006-2008 DEM.** The 9t DoD shows
  along-track striping of ±0.22 m (row-mean std 0.094 m) plus mosaic-seam steps;
  these are the dominant systematic error and set the detection floor at ~0.4 m.
  Removing row+col means alone takes σ 0.183 → 0.154 m. See [[icp_change_9t]].
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

- **Full plat→pad rename** is partial: on-disk artifacts still use legacy `plat` names (GPKG layer `plat`, `plat_dataset_manifest.csv`, `plat_unet`). Code has back-compat aliases. Finish the rename when convenient.
- Keep `analysis_log.md`, per-iteration docs, and `LEADERBOARD.md` current each pass (see CLAUDE.md documentation-maintenance rule).
