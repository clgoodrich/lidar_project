# road_unet_1m_recall — recall-focused 1 m road U-Net

**Date:** 2026-06-14
**Goal:** Close the road gaps seen on out-of-domain block 613590 — the deployed
`road_unet_1m` (3-class) detected roads in the right places but *under-confidently*
(P(road) ≈ 0.5 on real roads), so at threshold 0.5 segments dropped out → gappy
network. Fix it **in training**, not with the post-filter.

## What we tried first (and rejected)

**Multi-block training** (`_road_unet_multiblock.py`, `road_unet_mb`): train across
the 6 `data_3x3` blocks carrying hand-drawn road (191 km) to add data/diversity.

- Spatial-block split: train {618594, 622591, 613603, 613608}, val {618591}, test {622594}.
- Result: **worse.** Overfit (best val road IoU at **ep 7** then degraded; 618594 alone
  was 84% of the training road), and *under-confident* on 613590 (mean P(road) 0.508 →
  fewer pixels clear threshold than the deployed model).
- Lesson: pulling in outside-9t annotations **diluted the trusted dense 9t core**. The
  data wasn't the bottleneck. (User's instinct to stay on the 9t core was correct.)

## What worked

`_road_unet_1m_recall.py` — identical clean **9t-only** data (roads + drainage clipped
to the 9t box, `labels_road_9t_1m.tif`), roughness_5 channel-7. Only changes:

| param | deployed | recall |
|---|---|---|
| road focal-α | 0.60 | **0.72** |
| drainage focal-α | 0.30 | 0.25 |
| bg focal-α | 0.10 | 0.10 |
| weight_decay | 1e-4 | **2e-4** |

Reproduce:
```
python notebooks/wellsight/roads/_road_unet_1m_recall.py --epochs 40
```

## Results

**9t held-out test** (best = ep 38, val road IoU 0.643):

| metric | deployed | recall |
|---|---|---|
| pixel IoU road | 0.581 | 0.581 |
| AP road-vs-drainage | 0.992 | 0.999 |
| mean P(road) on road | 0.757 | 0.778 |
| mean P(road) on drainage | 0.006 | 0.004 |

In-domain ≈ unchanged — as expected, the deployed model was already confident on 9t.

**Out-of-domain 613590** (the actual target — this is where it matters):

| metric | deployed | multi-block | recall |
|---|---|---|---|
| mean P(road) (≥0.3) | 0.565 | 0.461 | **0.663** |
| road ≥0.5 px | — | 425k | **731k** |
| cleaned network km | 155.2 | — | **169.3** |
| segments / bridges | 1021 / 102 | — | 1252 / 129 |
| TIGER recall | 0.501 | — | **0.523** |
| novel (candidate) km | 123.5 | — | **136.2** |

Visual: `road_unet_1m_recall/compare_613590_crop.png` and `_full.png` — lines that
were broken in the deployed model are continuous in the recall model, drainage stays dark.

## Interpretation

The α bump raised road confidence enough that the same correct-but-borderline detections
clear threshold → gaps close. Drainage suppression preserved (we had headroom: AP 0.997+).
Cleaned road network +14 km and +2.2 pts public-road (TIGER) recall on 613590.

The final vector network was produced by feeding the recall prob to the validated
`roads_opt` cleaner:
```
python notebooks/wellsight/build/_road_optimize.py --apply-block <613590 dir> \
  --apply-key 613590 --prob <recall road_prob> --drain <recall drainage_prob>
```
(`--prob`/`--drain` overrides added so the cleaner can run on any prob raster and derive
the drainage gate from a drainage prob when no argmax raster exists.)

## Post-processing extraction on 9t (added 2026-07-02, honest protocol)

`_road_optimize.py` was re-pointed at this model's probs (it had been reading the
superseded `road_unet_1m`) and re-tuned with **val-based selection**: the cleaning
config is optimized on the val blocks only, then frozen and scored **once** on the
test blocks (`road_unet_1m_recall/road_postproc_best.json` keeps both):

| split | completeness | correctness | F1 | GT km |
|---|---|---|---|---|
| val (selection) | 0.474 | 0.614 | 0.535 | 12.5 |
| **test (frozen)** | **0.695** | **0.824** | **0.754** | 22.5 |

Frozen config: `enhance=sato, thresh=otsu, skel=lee, spur=20, reconnect=lcp,
island=80, min_px=40`. Test > val here is not leakage — the val region simply has
about half the ground-truth road density (12.5 vs 22.5 km against the same 1,019
segment set), making it the harder region; selection never saw test.

## Footnote — "roughness channel bug" was a false alarm

At 1 m, `features_<key>_1m.tif` band 7 is *labeled* `roughness_11` but the data is
byte-identical to `roughness_5` (5×5 stdev). The model trained on roughness_5, so the
channel matched all along. No fix needed.

## Status

`road_unet_1m_recall/best.pt` is the **current** road model for the data_3x3 blocks.
Not yet re-inferred across all 25 blocks (deferred). `road_unet_mb` kept local only
(gitignored, regenerable).
