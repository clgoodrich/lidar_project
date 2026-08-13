"""Full-tile inference for the Mask R-CNN pad model on 9t.

Mirrors pit_maskrcnn_infer.py but with patch=384 and writes to pad_05_maskrcnn/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import geopandas as gpd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "s3_train"))
from _common import DERIV_9T, path_for  # noqa: E402
import _instance_common as ic  # noqa: E402
from _pit_maskrcnn import build_model, DEVICE  # noqa: E402
from _pit_maskrcnn_infer import run_inference, global_nms  # noqa: E402

OUTDIR = path_for("models_retired") / "pad_05_maskrcnn"
CKPT = OUTDIR / "best.pt"
PATCH = 384
OVERLAP = 96
SCORE_THRESH = 0.3
NMS_IOU = 0.4


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

    detections = run_inference(model, mu, sd, PATCH, OVERLAP, score_thresh=SCORE_THRESH)
    print(f"Raw detections: {len(detections)}")
    for d in detections:
        d["cls"] = "pad"
    detections = global_nms(detections, NMS_IOU)
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
    metrics["patch"] = PATCH
    ic.save_metrics(metrics, OUTDIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
