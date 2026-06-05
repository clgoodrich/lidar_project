"""Full-tile inference for the YOLOv8-seg pit model on 9t."""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "pit_08_yolo"
CKPT = OUTDIR / "best.pt"
PATCH = 256
OVERLAP = 64
SCORE_THRESH = 0.05  # YOLO scores conservatively; mirror Mask R-CNN's recall-heavy regime
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
    # Map YOLO class ids -> names (0=floor, 1=wall) and run per-class NMS.
    for d in detections:
        d["cls"] = {0: "floor", 1: "wall"}.get(d.get("cls_id", 0), "floor")
    kept: list[dict] = []
    for cls in set(d["cls"] for d in detections):
        grp = [d for d in detections if d["cls"] == cls]
        boxes_t = torch.tensor([d["bbox"] for d in grp], dtype=torch.float32)
        scores_t = torch.tensor([d["score"] for d in grp], dtype=torch.float32)
        keep_ix = nms(boxes_t, scores_t, NMS_IOU).tolist()
        kept.extend(grp[i] for i in keep_ix)
    detections = kept
    n_floor = sum(d["cls"] == "floor" for d in detections)
    n_wall = sum(d["cls"] == "wall" for d in detections)
    print(f"After per-class NMS: {len(detections)} (floor={n_floor} wall={n_wall})")

    ref_profile = ic.reference_profile()
    ic.stitch_prob_raster([d for d in detections if d["cls"] == "floor"],
                          ref_profile, OUTDIR / "pit_prob_floor.tif")
    ic.stitch_prob_raster([d for d in detections if d["cls"] == "wall"],
                          ref_profile, OUTDIR / "pit_prob_wall.tif")
    gpkg_path = OUTDIR / "instances.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    ic.detections_to_gpkg(detections, ref_profile, gpkg_path, layer="pits",
                          score_thresh=SCORE_THRESH)

    pit_set = ic.load_pit_set(with_walls=False)
    pred_gdf = gpd.read_file(gpkg_path, layer="pits") if gpkg_path.exists() else None
    if pred_gdf is not None and "cls" in pred_gdf.columns:
        pred_floor = pred_gdf[pred_gdf.cls == "floor"]
    else:
        pred_floor = pred_gdf
    df, metrics = ic.per_instance_metrics(pred_floor, pit_set, split="test")
    df.to_csv(OUTDIR / "test_per_pit.csv", index=False)
    metrics["n_detections_after_nms"] = len(detections)
    metrics["n_floor"] = n_floor
    metrics["n_wall"] = n_wall
    metrics["score_thresh"] = SCORE_THRESH
    metrics["nms_iou"] = NMS_IOU
    metrics["imgsz"] = IMGSZ
    ic.save_metrics(metrics, OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
