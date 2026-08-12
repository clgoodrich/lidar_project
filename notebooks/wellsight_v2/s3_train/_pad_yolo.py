"""Plat (pad) instance segmentation with YOLOv8-seg on 9t.

Mirrors _pit_yolo.py: patch=384, jitter=40 m, class "pad".

Outputs under data/derivatives/tiles/9t/iterations/pad_06_yolo/.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "pad_06_yolo"
DATASET = OUTDIR / "dataset"
PATCH = 384
JITTER_M = 40.0
PATCHES_PER_INST = 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch", type=int, default=8)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--model", type=str, default="models/pretrained/yolov8s-seg.pt")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 3
        ppi = 2
    else:
        ppi = PATCHES_PER_INST

    from ultralytics import YOLO
    OUTDIR.mkdir(parents=True, exist_ok=True)
    rgb_path = ic.build_rgb3_stack()
    pad_set = ic.load_pad_set()

    if not (DATASET / "data.yaml").exists() or args.smoke:
        if DATASET.exists():
            shutil.rmtree(DATASET)
        data_yaml = ic.export_yolo_dataset(
            pad_set, rgb_path, DATASET, PATCH, JITTER_M, ppi,
            class_name="pad", seed=42,
        )
        print(f"Exported dataset -> {DATASET}")
    else:
        data_yaml = DATASET / "data.yaml"

    model = YOLO(args.model)
    model.train(
        data=str(data_yaml), epochs=args.epochs, imgsz=args.imgsz,
        batch=args.batch, project=str(OUTDIR), name="run",
        exist_ok=True, plots=True, verbose=True,
        workers=2,  # Windows: 8 default workers + crashed-run zombies -> RAM OOM
    )
    run_dir = OUTDIR / "run"
    best_src = run_dir / "weights" / "best.pt"
    if best_src.exists():
        shutil.copy(best_src, OUTDIR / "best.pt")
    results_csv = run_dir / "results.csv"
    if results_csv.exists():
        shutil.copy(results_csv, OUTDIR / "train_log.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
