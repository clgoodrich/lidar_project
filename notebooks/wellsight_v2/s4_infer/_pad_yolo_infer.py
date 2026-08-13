"""Full-tile inference for the YOLOv8-seg pad model on 9t."""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T, path_for  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = path_for("models_retired") / "pad_06_yolo"
CKPT = OUTDIR / "best.pt"
PATCH = 384
OVERLAP = 96
SCORE_THRESH = 0.3
NMS_IOU = 0.4
IMGSZ = 640


def main() -> int:
    from ultralytics import YOLO
    import torch
    from torchvision.ops import nms

    OUTDIR.mkdir(parents=True, exist_ok=True)
    model = YOLO(str(CKPT))
    rgb_path = ic.RGB3_PATH if ic.RGB3_PATH.exists() else ic.build_rgb3_stack()

    detections = ic.yolo_sliding_inference(model, rgb_path, PATCH, OVERLAP,
                                           score_thresh=SCORE_THRESH, imgsz=IMGSZ)
    print(f"Raw YOLO detections: {len(detections)}")
    for d in detections:
        d["cls"] = "pad"
    if detections:
        boxes_t = torch.tensor([d["bbox"] for d in detections], dtype=torch.float32)
        scores_t = torch.tensor([d["score"] for d in detections], dtype=torch.float32)
        keep_ix = nms(boxes_t, scores_t, NMS_IOU).tolist()
        detections = [detections[i] for i in keep_ix]
    print(f"After NMS: {len(detections)}")

    ref_profile = ic.reference_profile()
    ic.stitch_prob_raster(detections, ref_profile, OUTDIR / "pad_prob.tif")
    gpkg_path = OUTDIR / "instances.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    ic.detections_to_gpkg(detections, ref_profile, gpkg_path, layer="pads",
                          score_thresh=SCORE_THRESH)

    pad_set = ic.load_pad_set()
    pred_gdf = gpd.read_file(gpkg_path, layer="pads") if gpkg_path.exists() else None
    df, metrics = ic.per_instance_metrics(pred_gdf, pad_set, split="test")
    df.to_csv(OUTDIR / "test_per_pad.csv", index=False)
    metrics["n_detections_after_nms"] = len(detections)
    metrics["score_thresh"] = SCORE_THRESH
    metrics["nms_iou"] = NMS_IOU
    metrics["imgsz"] = IMGSZ
    ic.save_metrics(metrics, OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
