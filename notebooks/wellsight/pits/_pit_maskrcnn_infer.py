"""Full-tile inference for the Mask R-CNN pit model on 9t.

Slides a (PATCH x PATCH) window over the rgb3 composite with overlap,
collects per-instance detections, dedupes via NMS across the tile, and writes:

    pit_prob.tif         max-score float32 raster (compare to UNet pit_prob_floor)
    instances.gpkg       per-detection polygon + score
    test_metrics.json    per-pit recall vs annotations_proj.gpkg::pit_inside (test split)

Run:
    python notebooks/wellsight/pits/_pit_maskrcnn_infer.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import torch
from rasterio.windows import Window
from torchvision.ops import nms

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import DERIV_9T  # noqa: E402
import _instance_common as ic  # noqa: E402
from _pit_maskrcnn import build_model, DEVICE, PATCH  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "pit_07_maskrcnn"
CKPT = OUTDIR / "best.pt"
OVERLAP = 64
SCORE_THRESH = 0.3
NMS_IOU = 0.4


def sliding_windows(width: int, height: int, patch: int, overlap: int):
    step = patch - overlap
    xs = list(range(0, max(width - patch, 0) + 1, step))
    ys = list(range(0, max(height - patch, 0) + 1, step))
    if xs and xs[-1] != width - patch:
        xs.append(width - patch)
    if ys and ys[-1] != height - patch:
        ys.append(height - patch)
    if not xs:
        xs = [0]
    if not ys:
        ys = [0]
    for y in ys:
        for x in xs:
            yield Window(x, y, patch, patch)


@torch.no_grad()
def run_inference(model, mu, sd, patch: int, overlap: int,
                  score_thresh: float = SCORE_THRESH) -> list[dict]:
    """Slide window over the 7-band feature tile, return per-detection records
    in tile pixel coords.

    Each record: {score, cls_id, bbox (tile px), mask (h, w float32 in [0,1])}.
    Masks are pre-cropped to their bbox so downstream code doesn't need to know
    the originating patch window.
    """
    model.eval()
    W, H = ic.feature_tile_size()
    feat_arr = ic.load_feature_array(mu, sd)  # cached in-RAM stack
    detections: list[dict] = []
    windows = list(sliding_windows(W, H, patch, overlap))
    print(f"Sliding inference: {len(windows)} windows ({W}x{H}, patch={patch}, overlap={overlap})")
    for i, win in enumerate(windows):
        if i % 50 == 0:
            print(f"  window {i+1}/{len(windows)}")
        feat = ic.slice_feat_patch(feat_arr, win)
        img_t = torch.from_numpy(feat).to(DEVICE)
        outputs = model([img_t])[0]
        scores = outputs["scores"].cpu().numpy()
        boxes = outputs["boxes"].cpu().numpy()
        masks = outputs["masks"].cpu().numpy()[:, 0]  # (N, P, P) float [0,1]
        labels = outputs["labels"].cpu().numpy()      # 1=floor, 2=wall
        keep = scores >= score_thresh
        for s, bb, m, lb in zip(scores[keep], boxes[keep], masks[keep], labels[keep]):
            lx0, ly0 = max(int(round(bb[0])), 0), max(int(round(bb[1])), 0)
            lx1, ly1 = min(int(round(bb[2])), patch), min(int(round(bb[3])), patch)
            if lx1 <= lx0 or ly1 <= ly0:
                continue
            mask_crop = m[ly0:ly1, lx0:lx1].astype(np.float32)
            detections.append({
                "score": float(s),
                "cls_id": int(lb),  # task-agnostic; caller maps to a class name
                "bbox": (float(win.col_off + lx0), float(win.row_off + ly0),
                         float(win.col_off + lx1), float(win.row_off + ly1)),
                "mask": mask_crop,
            })
    return detections


def global_nms(detections: list[dict], iou_thresh: float = NMS_IOU) -> list[dict]:
    """Per-class NMS so floor and wall detections don't suppress each other."""
    if not detections:
        return []
    kept: list[dict] = []
    for cls in set(d.get("cls", "floor") for d in detections):
        grp = [d for d in detections if d.get("cls", "floor") == cls]
        boxes_t = torch.tensor([d["bbox"] for d in grp], dtype=torch.float32)
        scores_t = torch.tensor([d["score"] for d in grp], dtype=torch.float32)
        keep_ix = nms(boxes_t, scores_t, iou_thresh).tolist()
        kept.extend(grp[i] for i in keep_ix)
    return kept


def main() -> int:
    print(f"Device: {DEVICE}")
    OUTDIR.mkdir(parents=True, exist_ok=True)
    ck = torch.load(CKPT, map_location=DEVICE, weights_only=False)
    print(f"Loaded ep {ck['epoch']} (val_loss={ck['val_loss']:.3f}) arch={ck['arch']}")

    in_ch = ck.get("in_channels", 3)
    model = build_model(num_classes=ck["num_classes"], in_channels=in_ch).to(DEVICE)
    model.load_state_dict(ck["state_dict"])

    import numpy as np
    mu = np.asarray(ck["mu"], dtype=np.float32)
    sd = np.asarray(ck["sd"], dtype=np.float32)

    detections = run_inference(model, mu, sd, PATCH, OVERLAP)
    print(f"Raw detections (score>={SCORE_THRESH}): {len(detections)}")
    for d in detections:  # map model class ids -> names (1=floor, 2=wall)
        d["cls"] = {1: "floor", 2: "wall"}.get(d.get("cls_id", 1), "floor")
    detections = global_nms(detections, NMS_IOU)
    n_floor = sum(d.get("cls") == "floor" for d in detections)
    n_wall = sum(d.get("cls") == "wall" for d in detections)
    print(f"After per-class NMS: {len(detections)} (floor={n_floor} wall={n_wall})")

    ref_profile = ic.reference_profile()
    # Per-class probability rasters (matches pit_unet_v2 naming).
    floor_dets = [d for d in detections if d.get("cls") == "floor"]
    wall_dets = [d for d in detections if d.get("cls") == "wall"]
    ic.stitch_prob_raster(floor_dets, ref_profile, OUTDIR / "pit_prob_floor.tif")
    ic.stitch_prob_raster(wall_dets, ref_profile, OUTDIR / "pit_prob_wall.tif")

    gpkg_path = OUTDIR / "instances.gpkg"
    if gpkg_path.exists():
        gpkg_path.unlink()
    ic.detections_to_gpkg(detections, ref_profile, gpkg_path, layer="pits",
                          score_thresh=SCORE_THRESH)

    # Eval against floors only (the "did we find the pit" question).
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
    ic.save_metrics(metrics, OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
