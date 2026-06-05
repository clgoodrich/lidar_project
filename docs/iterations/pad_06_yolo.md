# pad_06_yolo

**Status:** trained + inference complete

**Final result (100 ep YOLOv8s-seg, val Mask mAP50 = 0.467).**
- Recall@IoU 0.1 / 0.3 / 0.5: **0.778 / 0.778 / 0.667** on 9 test plats.
- Mean best IoU 0.564, median 0.698.
- 818 detections after NMS at conf 0.3 (lowering to conf 0.05 added 1165 detections but identical recall — the extras don't beat existing high-score matches).

**Compared to pad_05_maskrcnn** (1.00/1.00/0.89, 3250 dets): YOLO ~25 pp lower recall but 4x fewer detections — much better precision regime, would need raised score thresh on Mask R-CNN to be apples-to-apples.

**Training was fast** (16 min for 100 epochs) — far fewer training patches than pits (204 vs 296) plus larger patch (384 -> batch 8). Inherited the BGR-flip fix from [[pit_08_yolo]] automatically via `_instance_common.yolo_sliding_inference`.

**Goal.** Plat counterpart to [[pit_08_yolo]]. Single-stage instance segmentation for pads.

**Architecture.** YOLOv8s-seg, COCO-pretrained, `imgsz=640`.

**Inputs.** `rgb3_9t_05.tif` -> uint8 PNG patches at 384x384 source resolution.

**Labels.** 79-polygon `plat` split (51/16/9). YOLO-seg `.txt` per patch.

**Patch sampling.** 384x384, jitter ±40 m, 4 patches per plat -> 204 train PNGs.

**Training.** Ultralytics defaults, `batch=8` (larger patch), 100 epochs.

**Inference.** Sliding window 384 / overlap 96, conf 0.3, NMS IoU 0.4.

**Outputs (`data/derivatives/9t/iterations/pad_06_yolo/`).**
- `best.pt`, `train_log.csv`, `plat_prob.tif`, `instances.gpkg::plats`, `test_per_plat.csv`, `test_metrics.json`.

**Reproduce.**
```
python notebooks/wellsight/plats/_plat_yolo.py --epochs 100 --batch 8
python notebooks/wellsight/plats/_plat_yolo_infer.py
```
