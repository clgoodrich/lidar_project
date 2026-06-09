# pad_05_maskrcnn

**Status:** v2 (7-band) trained + inference complete 2026-06-03 — best ckpt = epoch 0. Same overfitting pattern as pit_07.

**v1 result (3-band composite, 30 ep, best ckpt = ep 1).**
- Recall@IoU 0.1 / 0.3 / 0.5: 1.00 / 1.00 / 0.889 on 9 test plats. Mean IoU 0.688.
- 3250 detections after NMS — heavy over-prediction.

**v2 result — HEADLINE (7-band stack, best ckpt = ep 0, inference 2026-06-03).**
- Recall@IoU 0.1 / 0.3 / 0.5: **1.00 / 1.00 / 0.889** on 9 test plats. Mean best IoU **0.631**, median 0.590.
- **2546 detections** after NMS (vs 79 actual plats tile-wide).
- vs v1: detections **3250 → 2546** (−22% FPs) but recall unchanged and mean IoU slipped 0.688 → 0.631. **The 7-band stack did NOT solve the pad over-prediction.** Diagnosis revised: the bottleneck is *data quantity* (51 train plats) + a permissive score threshold (0.3), not feature richness. Next steps: score-threshold sweep + grow the label set (see [[BACKLOG]]).
- Output: `pad_prob.tif`, `instances.gpkg::plats`.

**Note on the v2 rebuild.** The first v2 inference attempt (2026-06-03) crashed with `KeyError: 'mu'` — `best.pt` on disk was still the v1 3-band checkpoint (had `rgb_path`, no `mu`/`in_channels`). The 7-band rebuild had only completed for *pits*. Pad was then retrained for 6 epochs on the 7-band stack (best=ep0, ~61 s/epoch uncontended) and re-inferred successfully.

**Overfitting note.** Same shape as [[pit_07_maskrcnn]]: train loss falls fast, val loss bottoms at ep 0–1 then climbs. 51 train plats is even thinner than pits (74). Same mitigations apply.

**Goal.** Instance-segmentation baseline for plats (pads). UNet pipelines (`plat_unet`, `multitask_unet`) treat plat as a semantic class; this iteration emits one detection per pad so we can score and rank individual pads.

**Architecture.** Same as [[pit_07_maskrcnn]]: `maskrcnn_resnet50_fpn_v2`, COCO-pretrained, `num_classes=2`.

**Inputs (v2 — full UNet stack).** The **7-band UNet feature stack** `features_pit_9t_05.tif` (`lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11`), z-scored via `feature_stats.json` — same inputs the UNet used, via first-conv widening (3→7, warm-started). This replaces the v1 3-band composite, which was feature-poor for pads (a pad is flat + low-relief, indistinguishable from natural flat ground in `(hillshade, slope, lrm_25)`) and produced the false-positive haze. Pure DEM-derivative — **no CHM**, so canopy/overgrowth variability is irrelevant.

**Labels.** `annotations_proj.gpkg::plat` (79 polygons, single class). Split per `plat_dataset_manifest.csv`: 51 train / 16 val / 9 test.

**Patch sampling.** 384x384 px (192 m) centred on each train plat with ±40 m jitter, 4 patches per plat → 204 train patches. Larger patch than pits because plats are 30-80 m across and need surrounding context to distinguish a pad scar from natural clearings.

**Training.** AdamW lr 5e-4 (cosine), wd 1e-4, batch 2 (constrained by 384x384 input). v1: 30 epochs; v2: 6 epochs (best is always ep 0–1, so 30 was wasteful).

**Inference.** Sliding window 384 / overlap 96 over 9000x9000 tile, score >= 0.3, NMS IoU 0.4.

**Outputs (`data/derivatives/tiles/9t/iterations/pad_05_maskrcnn/`).**
- `best.pt`, `train_log.csv`, `pad_prob.tif`, `instances.gpkg::plats`, `test_per_plat.csv`, `test_metrics.json`.

**Reproduce.**
```
python notebooks/wellsight/plats/_pad_maskrcnn.py --epochs 6 --batch 2 --lr 5e-4
python notebooks/wellsight/plats/_pad_maskrcnn_infer.py
```

**Compare to.** [[plat_unet]] (semantic baseline), [[pad_06_yolo]] (other instance approach).
