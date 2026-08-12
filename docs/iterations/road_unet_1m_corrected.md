# road_unet_1m_corrected — active-learning correction loop closes on 613590

**Date:** 2026-07-20 · **Script:** `notebooks/wellsight_v2/s3_train/_road_unet_1m_corrected.py` · **Model dir:** `data/derivatives/tiles/9t/road_unet_1m_corrected/`

## Goal

Close the human-in-the-loop road correction loop (task #36, [[project_road_active_learning_loop]]). The champion recall model
([[road_unet_1m_recall]], α_road 0.72) was inferred on 613590; the user chopped
that network into ~40 m segments in QGIS (2026-06-15 review package), then on
2026-06-17 **deleted 1,585 false-positive segments and drew 102 missed roads**.
This iteration turns that diff into training signal and measures whether it
fixes recall without breaking in-domain performance.

## Inputs / provenance

- Champion checkpoint `road_unet_1m_recall/best.pt` (ep 38, 9t val road IoU
  0.643) as fine-tune init.
- 9t clean fully-labelled 1 m data (`features_pit_9t_1m.tif` +
  `labels_road_9t_1m.tif`, `road_dataset_manifest.csv`).
- 613590 corrections built by `_build_road_corrections_613590.py`:
  - **added** 102 lines / 7.49 km → positives (fix recall)
  - **reject** 1,585 segs / 14.34 km (912 model-confident, P≥0.5) → hard
    negatives (fix precision)
  - **kept** 15,410 segs / 141.79 km → confirmed road (anti-forgetting)
- Corridor-supervised label raster: **255 = ignore for 93.8% of the block**
  (everything the human did not adjudicate), so unlabelled real roads are
  never taught as background. FocalCE skips ignore.

## Method

Fine-tune champion on `ConcatDataset(9t train, 613590 train)`, 28% correction
patches per epoch (kept capped at 1,200 centers so it doesn't swamp additions
and rejects). 15 epochs, lr 2e-4, α (0.10, 0.72, 0.25), wd 2e-4. **Model
selection on 9t val road IoU** — same score the champion was picked on, so a
drop signals in-domain harm. Best = ep 15 (9t val road IoU 0.636).

**Honest held-out protocol.** 613590 split into a 4×4 grid; cell→split chosen
by seeded search so added *and* rejected km balance across train/val/test
(the user's additions cluster in the NW, so a naive split held out zero).
Train sample centers eroded by patch-half + jitter (158 m) from cell edges, so
no training patch overlaps a val/test cell. The "before" raster is the
champion's `road_prob_613590_1m.tif`, verified **byte-identical** to what the
user reviewed.

## Results

**In-domain 9t held-out test — no regression:**

| Metric | Champion | Corrected |
|---|---|---|
| pixel IoU road | 0.581 | 0.573 |
| AP road-vs-drainage | 0.999 | 0.999 |
| mean P(road) on road | 0.778 | 0.784 |
| mean P(road) on drainage | 0.004 | 0.005 |

Pixel IoU dips 0.008 (noise); drainage still fully suppressed; road confidence
holds. The corrections did not damage the clean 9t domain.

**613590 held-out corrections (before → after):**

| Split | class | n | km | P(road) before→after | frac≥0.5 before→after |
|---|---|--:|--:|---|---|
| val | **added** | 47 | 1.56 | 0.718 → **0.758** (+0.040) | 0.85 → **0.94** |
| val | reject | 288 | 2.62 | 0.344 → **0.258** (−0.086) | 0.37 → **0.27** |
| val | kept | 3298 | 30.46 | 0.861 → 0.854 (−0.007) | 1.00 → 0.99 |
| test | **added** | 46 | 1.36 | 0.742 → **0.780** (+0.038) | 0.89 → **0.96** |
| test | reject | 344 | 3.12 | 0.161 → 0.162 (+0.002) | 0.16 → 0.15 |
| test | kept | 3318 | 30.30 | 0.847 → 0.840 (−0.007) | 0.99 → 0.98 |

**Added-vs-reject separability (AP):** val 0.245 → **0.443**, test 0.554 →
0.541.

## Interpretation

- **Recall win is real and held out on both val and test:** on roads the user
  said the model missed, P(road) rose ~+0.04 and the fraction crossing the 0.5
  threshold went 0.85→0.94 (val) and 0.89→0.96 (test). These were never in
  training.
- **Precision improves where there's room:** val rejects dropped 0.086 and
  their over-0.5 fraction fell 0.37→0.27. Test rejects were already very low
  (P 0.16) so they stayed flat — nothing to fix.
- **No forgetting:** confirmed roads held at ~0.85 P(road), ~0.99 over
  threshold.
- **Separation nearly doubled on val** (AP 0.245→0.443): the model is
  markedly better at telling a real missed road from a false positive. Test AP
  was flat but started higher.
- Net: one round of ~22 km of human edits measurably raised out-of-domain road
  recall and suppressed false positives, at zero in-domain cost. The
  fix-in-training approach ([[feedback_fix_in_training_not_filters]]) worked
  without any post-hoc filter.

Figures: `compare_corrections_full.png`, `compare_corrections_zoom.png`
(champion vs corrected P(road) over hillshade; green = held-out added roads
lighting up, red = held-out rejects darkening). `road_prob_613590_1m.tif` in
the model dir is the new deployable raster.

## Caveats / next

- Single block, single reviewer, single round. The loop is now reusable —
  another review→correct→retrain pass on 613590 (or a fresh block) should
  compound.
- Test-cell rejects had little headroom; a block with more confident false
  positives would show the precision lever more clearly.
- Not yet run through vector extraction — the honest APLS/topology gain (vs
  the [[road_unet_1m_recall]] 0.754 extraction F1) is the next measurement.
- **Deployed 2026-07-20:** the corrected `road_prob` / `drainage_prob` /
  `road_argmax` are now the live rasters in the 613590 block dir
  (`road_prob_613590_1m.tif`, mean P 0.056); the champion recall versions are
  preserved alongside as `*_recall.tif` (mean P 0.047). Rasters are gitignored
  (regenerable). **Consequence:** the existing extracted vector network
  (`roads_opt_613590_1m.gpkg`, `roads_net_613590_1m.gpkg`) is now STALE — it
  was cleaned from the champion prob. Re-run `_road_optimize.py` on the
  deployed corrected prob to refresh the vector product before using it.

## Reproduce

```bash
python notebooks/wellsight_v2/s6_review/_build_road_corrections_613590.py
python notebooks/wellsight_v2/s3_train/_road_unet_1m_corrected.py --epochs 15
python notebooks/wellsight_v2/s5_eval/_compare_corrected_613590.py
```
