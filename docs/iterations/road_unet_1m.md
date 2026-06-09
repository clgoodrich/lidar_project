# road_unet_1m

**Status:** trained + 9t test eval complete 2026-06-07. Built to run road detection
on the 1 m `data_3x3` blocks at *matched* resolution. **Now 3-class
(bg/road/drainage) with chunked road sampling** — see the "v2: drainage as a
trained class + road chunking" section below for the current recipe and metrics.
The original 2-class write-up is kept underneath for history.

## Why a 1 m model
The existing road U-Net ([[road_unet]], 0.5 m) was trained on `features_pit_9t_05.tif`. Applying it to the 1 m `data_3x3` blocks produced **33% "road" coverage** — massive false positives on terrain texture. Root cause is a **physical-scale mismatch**: only `roughness` was hand-matched between resolutions (`roughness_5`@1 m ≈ `roughness_11`@0.5 m, ~5 m window). The other channels feed the model at ~2× their trained physical scale on 1 m data:

| channel | window @0.5 m (trained) | window @1 m (blocks) |
|---|---|---|
| lrm_25 | 12.5 m | 25 m |
| tpi_05 | 2.5 m | 5 m |
| openness (L=25) | 12.5 m | 25 m |

Fix (chosen over regenerating all 25 blocks at 0.5 m): retrain the road model at 1 m so model and blocks match exactly. 1 m is adequate for landscape-scale roads and a 256 px patch now spans 256 m of context.

## Inputs
- **Features:** `features_pit_9t_1m.tif` — 7-band stack built by `_prep_road_1m.py` from the `9t_1m` derivative stack (`_build_derivatives.py`, same code/kernels as the blocks). Channel order: `lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_5` (roughness_5 replaces roughness_11). Z-scored via `feature_stats_1m.json` (train-block-only mean/std).
- **Labels:** `labels_road_9t_1m.tif` — roads buffered 1.5 m, rasterized on the 1 m grid (532,132 m² road).
- **9t_1m stack:** `_build_derivatives.py --tiles <9 WesternPA D20 tiles covering 619500,4593000,624000,4597500> --suffix 9t_1m`.
- **Roads provenance:** rebuilt from the latest hand-drawn `roads.shp` (97 → 1725 features; 171 land in the 9t blocks: train 123 / val 21 / test 27). See analysis log 2026-06-07.

---

## v2: drainage as a trained class + road chunking (2026-06-07, CURRENT)

The 2-class model fired on **drainage/waterways** (incised channels are linear
concave features that look like cut roads) and the post-hoc drainage filter
([[road_refine]]) was too aggressive and terrain-dependent. Root cause analysis
showed the model *could not* and *was not taught* to tell them apart:
- **No drainage negatives.** Label was binary road/bg; the `not_roads` layer
  (112 lines, ~7% on drainage) was never fed to the U-Net. Drainage just sat in
  "background", and FocalCE's heavy road weight pulled any concave line to road.
- **Roads aren't contaminated.** Only 0.7% of hand-drawn road lines run on a
  mapped stream — so it was a *training-setup* problem, not bad labels.

**Fix 1 — drainage as an explicit class.** Hand/filter-derived `drainage.shp`
(1791 channel segments, `klass='stream'`, xdrop 0.30–2.7 m; from the
cross-section filter, EPSG:6346) is now a 3rd label class. `_prep_road_1m.py`
rasterizes it as class 2 (drainage buffered 2.0 m, **road painted on top** so
culvert crossings stay road) → `labels_road_9t_1m.tif` is now `0=bg, 1=road,
2=drainage`. The model learns drainage as its own class, so it stops calling
channels road. This works in the **same 7 bands** — drainage is deeper/narrower
concavity than a road-cut (what `xdrop`/`tpi`/`openness` capture); the model just
needed the negative supervision to learn the boundary.

**Fix 2 — chunk the roads.** Roads were few long polylines (171 lines, median
126 m, up to 921 m); drainage came pre-chunked (~21 m). The U-Net sampler centers
**one** patch per line midpoint, so a 921 m road contributed a single training
patch and most of its length was never sampled — under-training roads and
over-exposing drainage (≈4:1), and making the 27-line eval meaningless.
`_build_plat_road_dataset.py` now chunks roads/not_roads to ~40 m
(`road_chunks_9t.gpkg` + chunk-level `road_dataset_manifest.csv`): **8385 road
chunks (635/95/130 train/val/test)**. Every ~40 m of road is its own patch center
and the eval scores comparable units.

**Recipe:** `UNet(in_ch=7, n_classes=3, base=32)`, FocalCE(alpha=(0.10, 0.60,
0.30) = bg/road/drainage, gamma=2.0), AdamW lr 1e-3, 40 epochs, patch 256, jitter
30 m, overlap 64. Sampler policies: road + not_road + drainage chunk midpoints.
Score = road-class IoU. Eval per-chunk from `road_chunks_9t.gpkg`.

**Result — HEADLINE (9t test, 168 chunks):**
| Metric | 2-class | 3-class (no chunk) | **3-class + chunked (current)** |
|---|---|---|---|
| Pixel IoU (road) | 0.379 | 0.527 | **0.581** |
| Line AP (road vs not_road) | 0.962 (27 lines) | 0.963 | **0.992 (168 chunks)** |
| Line AP (road vs drainage) | — | 0.962 | **0.992** |
| Mean P(road) on road | ~0.654 | 0.676 | **0.757** |
| Mean P(road) on drainage | — | 0.005 | **0.006** |
| Drainage IoU (val) | — | 0.72 | **0.74** |

Drainage gets P(road)≈0.006 while real roads stay ≈0.76; road IoU and confidence
both rose vs the no-chunk 3-class. Pilot blocks (3-class chunked): 604603 (flat)
road 0.98% / drainage 1.36%; 609590 (steep) road 2.87% / drainage 1.19% — clean
visual separation (orange road grid/benches, cyan dendritic channels).
Inference (`_infer_roads_data_3x3.py`, `N_CLASSES=3`) writes `road_prob` (=P road),
`drainage_prob` (=P drainage), `road_argmax` (0/1/2) and a 2-colour overlay.
Backups: `best.pt.2class.BAK`, `best.pt.3class_nochunk.BAK`.

---

## v1 (history): 2-class architecture / recipe
Identical to [[road_unet]]: `UNet(in_ch=7, n_classes=2, base=32)`, FocalCE(alpha=(0.10,0.90), gamma=2.0), AdamW lr 1e-3, 40 epochs. Patch 256, jitter 30 m, overlap 64. Score = road-class IoU.

## Result — v1 2-class HEADLINE (9t test split)
| Metric | 0.5 m ([[road_unet]]) | **1 m (this)** |
|---|---|---|
| Pixel IoU (road) | 0.343 | **0.379** |
| Line AP (test, 31 lines) | 0.963 | 0.962 |
| Mean P(road) road / not_road | 0.565 / 0.125 | **0.654 / 0.133** |

The 1 m model is marginally better on its own test set and, crucially, generalizes correctly to the 1 m blocks: pilot block 604590 went from **33.2% → 4.06%** road pixels, with predictions tracing coherent road lines instead of terrain. Minor residual firing remains on the steepest incised slopes (candidate for the cross-section concavity filter, see [[BACKLOG]]).

## Outputs
- `data/derivatives/tiles/9t/road_unet_1m/`: `best.pt`, `train_log.csv`, `road_prob.tif`, `road_argmax.tif`, `test_metrics.json`, `test_per_line.csv`.
- Per-block inference (`_infer_roads_data_3x3.py`): `road_prob_<key>_1m.tif`, `road_argmax_<key>_1m.tif`, `road_overlay_<key>_1m.png`, `features_<key>_1m.tif` in each `data/derivatives/tiles/data_3x3/westernpa_d20/<key>/`.

## Reproduce
```
# 1) 9t derivative stack at 1 m
python notebooks/wellsight/build/_build_derivatives.py \
  --tiles "<9 tiles covering 619500,4593000,624000,4597500>" \
  --bbox 619500,4593000,624000,4597500 --suffix 9t_1m
# 2) stack + stats + labels at 1 m
python notebooks/wellsight/roads/_prep_road_1m.py
# 3) train + eval
python notebooks/wellsight/roads/_road_unet_1m.py
# 4) infer on all WesternPA blocks
python notebooks/wellsight/build/_infer_roads_data_3x3.py
```
