# pit_07_maskrcnn

**Status:** v2 (7-band, floor+wall); checkpoint retrained 2026-06-11 on the rebuilt
426-pit dataset; re-evaluated 2026-07-02 on the current test split with 1:1 metrics.

**Current headline (2026-07-02 re-eval — 06-11 checkpoint, 65 test pits, greedy 1:1 matching).**
- R@0.3 **0.97**, P@0.3 0.053, F1@0.3 0.100; R@0.5 **0.85**; mean best IoU **0.631**.
- 2,978 detections after per-class NMS (1,190 floor / 1,788 wall) at score ≥ 0.3.
- Best pit recall + IoU of any model, but precision ~5% — over-detection is the open
  problem (score threshold never tuned; see LEADERBOARD "Reading the tables").
- Results below this line are the older 110-pit era (n_test 20, loose recall) —
  kept for the architecture/bug history; numbers not comparable.

**Goal.** First instance-segmentation baseline for pits on the 9t tile. UNet pipelines (`pit_unet_v2`, `multitask_unet`) treat pits as semantic classes and post-hoc clump pixels; this iteration asks the model to emit one detection per pit natively so we can rank candidates by per-instance score instead of by pixel cluster size.

**Architecture.** `torchvision.models.detection.maskrcnn_resnet50_fpn_v2`, COCO-pretrained, head replaced for `num_classes=2` (bg + pit). 45.9 M params.

**Inputs (v2 — full UNet stack).** The **7-band UNet feature stack** `features_pit_9t_05.tif` (`lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11`), z-scored with `feature_stats.json` — the identical inputs the UNet trained on. The backbone's first conv is widened 3→7: pretrained RGB weights copied into the first 3 slots, the extra 4 warm-started from the mean of the RGB weights, everything downstream keeps COCO pretraining. The detector input transform is set to identity (mean 0 / std 1) since patches are pre-normalised.

*(v1 used a 3-band composite `(hillshade, slope, lrm_25)` to keep the stock 3-channel pretrained conv. That discarded lrm_5/tpi/openness/roughness — the multi-scale texture cues — and is why early pad runs flooded flat ground. Superseded.)*

**Labels.** `annotations_proj.gpkg::pit_inside` (110 polygons, single class). Split per `pit_dataset_manifest.csv`: 74 train / 16 val / 20 test.

**Patch sampling.** 256x256 px (128 m at 0.5 m/px) centred on each train pit with ±30 m jitter, 4 patches per pit per epoch → 296 train patches. Validation is one deterministic patch per pit (16 patches).

**Training.** AdamW, lr 5e-4 (cosine to 0), weight decay 1e-4, batch 4, 30 epochs.

**Inference.** Sliding window with overlap 64 over the 9000x9000 tile (~2200 windows). Per-window detections with `score >= 0.3` collected in tile-pixel coordinates, then global NMS at IoU 0.4.

**Outputs (`data/derivatives/tiles/9t/iterations/pit_07_maskrcnn/`).**
- `best.pt` — checkpoint with `state_dict, epoch, patch, num_classes, rgb_path, val_loss, arch`.
- `train_log.csv` — `epoch, tr_loss, va_loss, lr, sec`.
- `pit_prob.tif` — max instance-score raster (analog of `pit_unet_v2/pit_prob_floor.tif`).
- `instances.gpkg::pits` — per-detection polygon + score.
- `test_per_pit.csv` — per-test-pit best IoU and matched flag.
- `test_metrics.json` — summary: `n_test_instances`, `recall_at_iou_{0.1, 0.3, 0.5}`, `mean_best_iou`, `median_best_iou`, `n_detections_after_nms`.

**1-epoch smoke result (sanity, not headline).** 2207 detections, recall@IoU0.3 = 1.0 (20/20 test pits), mean best IoU 0.57.

**v1 result (3-band composite, 30 ep, best ckpt = ep 1).**
- Recall@IoU 0.1 / 0.3 / 0.5: 1.00 / 1.00 / 0.85 on 20 test pits.
- Mean best IoU 0.632, median 0.675. 1385 detections after NMS.

**v2 result — HEADLINE (7-band stack + floor/wall classes, best ckpt = ep 1, inference 2026-06-03).**
- 3-class model (bg / floor / wall). Floor = `pit_inside`, wall = `pit_outside` (the rim), so detections capture the whole depression shape, not just the hole.
- Scored on floors (the "did we find the pit" question): **Recall@IoU 0.1 / 0.3 / 0.5 = 1.00 / 1.00 / 0.95** on 20 test pits. Mean best IoU **0.664**, median 0.678.
- 2027 detections after per-class NMS: **947 floor + 1080 wall**.
- vs v1: floor recall@0.5 **0.85 → 0.95**, mean IoU 0.632 → 0.664. The richer feature stack + wall supervision is a clear win over the 3-band composite.
- Precision still loose (947 floor dets vs 110 annotated pits tile-wide) — same thin-data overfit story; raise score threshold to trade recall for precision.
- Outputs: `pit_prob_floor.tif`, `pit_prob_wall.tif`, `instances.gpkg::pits` (with `cls` column).

**Overfitting note.** Train loss fell 0.56 → 0.07; val loss bottomed at ep 1 (0.41) then climbed to 0.82 by ep 29. 74 train pits with a 45.9 M-param backbone is not enough — pretraining did all the work. Possible mitigations for a follow-up iteration: smaller backbone, frozen FPN, much stronger aug, or early-stopping.

**Reproduce.**
```
python notebooks/wellsight/pits/_pit_maskrcnn.py --epochs 30 --batch 4 --lr 5e-4
python notebooks/wellsight/pits/_pit_maskrcnn_infer.py
```

**Compare to.** [[pit_unet_v2]] (semantic baseline), [[pit_08_yolo]] (other instance approach).
