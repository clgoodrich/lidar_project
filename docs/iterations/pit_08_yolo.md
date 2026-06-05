# pit_08_yolo

**Status:** trained + inference complete (after BGR-channel bug fix)

**Final result (100 ep YOLOv8s-seg, val Mask mAP50 = 0.765).**
- Recall@IoU 0.1 / 0.3 / 0.5: **0.90 / 0.85 / 0.75** on 20 test pits.
- Mean best IoU 0.541, median 0.619.
- 728 detections after NMS (vs Mask R-CNN's 1385) — about half the detection volume for similar recall, so better precision/recall tradeoff.

**Bug fixed during inference.** YOLO training writes PNGs via PIL (RGB pixel order) but ultralytics' dataloader reads them with cv2 (BGR), so the model effectively learned channel mapping (B=lrm, G=slope, R=hillshade). At inference I was passing numpy in RGB order, which ultralytics treats as BGR — meaning channels 0 and 2 ended up swapped. Symptom: 88 detections tile-wide, only 1 intersected any GT pit. Fix in `_instance_common.yolo_sliding_inference`: `img8 = img8[..., ::-1]` before `model.predict`. After fix: 728 detections, recall 0.85 at IoU 0.3.

**Goal.** Second instance-segmentation baseline for pits. Paired with [[pit_07_maskrcnn]] to compare two-stage (Mask R-CNN, anchor + ROI) vs single-stage (YOLOv8-seg, anchor-free) detectors on the same patches.

**Architecture.** Ultralytics YOLOv8s-seg, COCO-pretrained, fine-tuned at `imgsz=640`. ~11 M params (vs 45.9 M for Mask R-CNN) — should also be 5-10x faster at inference.

**Inputs.** Same 3-channel composite `rgb3_9t_05.tif`, rendered to uint8 PNG patches at `imgsz=640` (YOLO upscales the 256x256 source patches automatically).

**Labels.** Same 110-polygon `pit_inside` split (74/16/20). Exported as YOLO-seg `.txt` files (`<class> x1 y1 x2 y2 ...` with coords normalised to [0, 1]).

**Patch sampling.** 256x256 px centred on train pits, ±30 m jitter, 4 patches per pit → 296 train PNGs + 16 val PNGs. Patches and labels materialised under `iterations/pit_08_yolo/dataset/{images,labels}/{train,val}/`.

**Training.** Ultralytics defaults (SGD, lr 0.01 cosine, mosaic + mixup aug), `batch=16`, 100 epochs.

**Inference.** Sliding window 256 / overlap 64. Per-window YOLO predict with `conf=0.3` → tile-coord detections → global NMS at IoU 0.4.

**Outputs (`data/derivatives/9t/iterations/pit_08_yolo/`).**
- `best.pt` — Ultralytics checkpoint (copied from `run/weights/best.pt`).
- `train_log.csv` — Ultralytics `results.csv` (per-epoch losses + mAP).
- `pit_prob.tif` — max instance-score raster.
- `instances.gpkg::pits` — per-detection polygon + score.
- `test_per_pit.csv` / `test_metrics.json` — same schema as [[pit_07_maskrcnn]].
- `dataset/` — materialised PNG + YOLO label patches (gitignored, regenerable).

**Reproduce.**
```
python notebooks/wellsight/pits/_pit_yolo.py --epochs 100 --batch 16
python notebooks/wellsight/pits/_pit_yolo_infer.py
```
