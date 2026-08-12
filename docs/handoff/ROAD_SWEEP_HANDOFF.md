# HANDOFF — Road U-Net top-5 optimization sweep (for Opus 4.8)

**Written:** 2026-07-20 by the prior session (Fable 5). **Status: not started — everything below is queued work.**
**User decisions already locked (do not re-ask):** train on **9t + 613590 corrections**; run the **top-5** sweep (~8 h GPU), not all ten; **include the 0.5 m variant** even though its output grid differs.

## Goal

Train **5 separate road U-Net variants**, one optimization each, and produce a
9t `road_prob.tif` for every variant in a fresh sweep folder, plus an
apples-to-apples leaderboard against the current best model. The user's aim is
"reliable, laser-accurate roads"; the known failure mode is **connectivity**
(gaps in real roads, false links), not raw pixel accuracy.

## Where things stand (context you need)

- **Current best model:** `data/derivatives/tiles/9t/road_unet_1m_corrected/best.pt`
  — 3-class (bg/road/drainage) U-Net, 1 m, fine-tuned 2026-07-20 from
  `road_unet_1m_recall/best.pt` on 9t + the user's 613590 QGIS corrections.
  9t val road IoU 0.636, 9t test pixel IoU 0.573, AP road-vs-drainage 0.999.
  Its 613590 rasters are deployed as the live block rasters
  (`.../613590/road_prob_613590_1m.tif`; champion preserved as `*_recall.tif`).
- **Training recipe that produced it** (reuse verbatim as the sweep base):
  `notebooks/wellsight_v2/s3_train/_road_unet_1m_corrected.py` — ConcatDataset of
  9t train patches + 613590 correction patches (28%/epoch, kept-cap 1200),
  FocalCE α=(0.10, 0.72, 0.25) γ=2.0, wd 2e-4, lr 2e-4, 15 ep, patch 256,
  batch 16, model selection on **9t val road IoU** (`score=iou[1]`).
- **Corrections data:** `data/derivatives/tiles/data_3x3/westernpa_d20/613590/corrections/`
  — corridor-supervised label raster (`labels_road_corr_613590_1m.tif`,
  **255=ignore over 93.8% of the block** — never paint unreviewed pixels as bg),
  `correction_centers_613590.csv` (kind: added/reject/kept × split),
  `correction_split_cells_613590.gpkg`, `correction_lines_613590.gpkg`.
  Split cells were seed-searched so added/reject km balance across
  train/val/test; train centers already eroded 158 m from cell edges.
- **Shared infra:** `notebooks/wellsight_v2/_dl.py` — `UNet` (4-level, base 32,
  7.76 M params), `FocalCE` (has `ignore=255` + all-ignore-patch guard),
  `CenteredPatchSampler`, `train_loop`, `predict_full_tile`. GPU: GTX 1070 Ti
  8 GB (batch 16 @ 256 px fits; AMP on).

## The 5 variants (train each as its own model dir)

Sweep root: `data/derivatives/tiles/9t/road_sweep_202607/<variant>/`
(each dir gets `best.pt`, `train_log.csv`, `road_prob.tif` for 9t,
`test_metrics.json`; 1 m variants also predict 613590 for the corrections eval).

1. **`cldice`** — add soft-clDice auxiliary loss (Shit et al. 2021: soft
   skeletonization via iterated min/max-pool, ~30 lines). Total loss =
   FocalCE + 0.3·(1 − clDice) computed on the road-class probability vs the
   road mask (respect ignore=255 by masking both). **Highest-priority variant**
   — directly attacks broken centerlines. Fine-tune from
   `road_unet_1m_corrected/best.pt`, 12 ep, lr 2e-4.
2. **`alpha078`** — FOCAL_ALPHA = (0.10, **0.78**, 0.25), nothing else changed.
   Fine-tune from corrected best, 12 ep. (History: 0.60→0.72 was the recall
   fix; this probes remaining headroom. Watch drainage IoU for bleed.)
3. **`boundary`** — boundary-weighted FocalCE: per-pixel weight 3× within 2 px
   of a road-class edge (compute weight map on the fly from the label patch:
   `road XOR erode(road)` dilated once). Sharpens width commitment. Fine-tune
   from corrected best, 12 ep.
4. **`orient`** — auxiliary orientation head (the literature's best-documented
   connectivity booster). Second 1×1-conv head off the final decoder feature
   (9 classes: 8 direction bins over 0–180° + "not road"); aux CE weight 0.3,
   supervised only where road=1. Orientation labels: rasterize local segment
   bearing (mod 180°, binned) from the 9t `roads` annotation layer +
   613590 correction lines; everywhere else 255=ignore. **Architecture changed
   → train from scratch** (30 ep, lr 1e-3, cosine — mirror how
   `_road_unet_1m_recall.py` trained). Most implementation work; do it last.
5. **`res05`** — same arch/loss as the corrected baseline but at **0.5 m**:
   features `data/derivatives/tiles/9t/features_pit_9t_05.tif` (7 bands; note
   channel 7 is **roughness_11** at 0.5 m — use `_dl.DEFAULT_CHANNELS`, stats
   `feature_stats.json`, NOT the 1 m variants), labels
   `labels_road_9t_05.tif`. **9t-only training** — the 613590 corrections
   cannot apply because 613590 has no 0.5 m stack (task #24 is PAUSED per the
   user; do NOT build it). Train from scratch 30 ep. Flag the recipe asymmetry
   honestly in its leaderboard row. Output `road_prob.tif` is a 0.5 m grid —
   that's accepted (user confirmed).

## Evaluation protocol (identical for every variant, nothing tuned on test)

- **9t held-out test:** pixel IoU (road), line AP road-vs-not_road and
  road-vs-drainage, mean P(road) on road/drainage test chunks — reuse
  `evaluate_test`/`evaluate_9t` from the existing road trainers (the 0.5 m
  variant scores on its own grid; the functions read label/blocks/chunks that
  exist at both resolutions).
- **613590 held-out corrections (1 m variants only):** reuse
  `evaluate_corrections()` from `_road_unet_1m_corrected.py` — before raster is
  the champion recall prob (`road_unet_1m_recall/road_prob_613590_1m.tif`),
  report P(road) on added/reject/kept for val AND test cells + added-vs-reject AP.
- **Baseline rows:** `road_unet_1m_recall` and `road_unet_1m_corrected`
  (existing numbers — do not retrain).

## Hard-won gotchas (violate these and the sweep is garbage)

- **Seed everything first.** The 2026-07-01 methodology audit flagged the U-Net
  trainers as unseeded → run-to-run noise swamps small deltas.
  `torch.manual_seed`, `np`, DataLoader `generator=`, and
  `torch.use_deterministic_algorithms(True, warn_only=True)` in the sweep
  driver. Without this you cannot rank 5 variants honestly.
- **Live logs:** run with `python -u` and `num_workers=2` (the 07-20 run had
  empty logs for 90 min — Python block-buffers through pipes — and
  num_workers=0 made the dataloader the bottleneck; ~6 min/epoch).
- **255=ignore is load-bearing** in the corrections raster; FocalCE already
  skips it and has the all-ignore-patch guard (in `_dl.py`). Any new loss term
  (clDice, boundary) must mask ignore too.
- Model selection stays on **9t val road IoU** for every variant (same score
  the baselines used) — never on 613590 test cells.
- **Do not** add a blanket gitignore for the sweep tifs — the existing
  `data/derivatives/**/*.tif` rule (`.gitignore:164`) already covers them.
  (Note: CLAUDE.md's warning against that blanket rule is stale; the rule is
  deliberate, see the .gitignore comment. Flagged to user 2026-07-20.)
- ≥100 MB outputs: the 0.5 m 9t prob (~80K×9K … actually 9000² float32 ≈
  324 MB) **is over 100 MB** — already ignored by the blanket rule; verify with
  `git check-ignore` anyway per CLAUDE.md audit rule.
- Runtime: fine-tunes ~1.2 h each, scratch ~3 h each on the 1070 Ti →
  ~8 h total. Run sequentially in one background queue (`run_in_background`),
  monitor via the train_log.csv files, not stdout.

## Deliverables checklist (per project docs rules — enforce all)

1. 5 model dirs under `road_sweep_202607/` each with 9t `road_prob.tif`.
2. `docs/iterations/road_sweep_202607.md` — goal, per-variant params, results
   table (9t test + 613590 corrections), interpretation, reproduce commands.
3. LEADERBOARD.md roads section: one row per variant.
4. `docs/analysis_log.md` newest-at-top entry.
5. Commit + push after major steps (user rule: push on major changes; stage
   selectively; branch is `pit-iter-06-dem-only`).
6. Report to user: winner, effect sizes, and whether clDice/orient justify the
   full-10 sweep or the 0.5 m rebuild for 613590.

## Open items NOT in scope here

- Vector extraction / APLS on the winner (next phase; `_road_optimize.py` is
  the tool, its 613590 vector product is currently stale vs the deployed
  corrected raster — noted in `docs/iterations/road_unet_1m_corrected.md`).
- The remaining 5 of the original 10 tweaks (dilated bottleneck, base-width,
  dropout, oversampling, augmentation) — deferred by user choice.
- McKean bounty-era temporal diff (blocked on obtaining a dated pre-2025
  McKean orphan snapshot).
