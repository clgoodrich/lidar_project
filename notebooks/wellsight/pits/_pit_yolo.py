"""Pit instance segmentation with YOLOv8-seg on 9t.

Exports the same train/val pit patches used by pit_maskrcnn as PNG + YOLO-seg
.txt labels, then fine-tunes a COCO-pretrained YOLOv8s-seg checkpoint.

Outputs under data/derivatives/tiles/9t/iterations/pit_08_yolo/:
    best.pt              copy of ultralytics best.pt
    train_log.csv        per-epoch metrics (mirrored from ultralytics results.csv)
    dataset/             materialised images + labels + data.yaml

Run:
    python notebooks/wellsight/pits/_pit_yolo.py --epochs 100
    python notebooks/wellsight/pits/_pit_yolo.py --smoke
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from _common import DERIV_9T  # noqa: E402
import _instance_common as ic  # noqa: E402

OUTDIR = DERIV_9T / "iterations" / "pit_08_yolo"
DATASET = OUTDIR / "dataset"
PATCH = 256
JITTER_M = 30.0
PATCHES_PER_INST = 4


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--model", type=str, default="models/pretrained/yolov8s-seg.pt")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()
    if args.smoke:
        args.epochs = 3
        ppi = 2
    else:
        ppi = PATCHES_PER_INST

    from ultralytics import YOLO  # heavy import - keep local

    OUTDIR.mkdir(parents=True, exist_ok=True)
    rgb_path = ic.build_rgb3_stack()
    pit_set = ic.load_pit_set(with_walls=True)  # 2-class: floor (0) + wall (1)

    if not (DATASET / "data.yaml").exists() or args.smoke:
        if DATASET.exists():
            shutil.rmtree(DATASET)
        data_yaml = ic.export_yolo_dataset(
            pit_set, rgb_path, DATASET, PATCH, JITTER_M, ppi,
            class_name=["floor", "wall"], seed=42,
        )
        print(f"Exported dataset -> {DATASET}")
    else:
        data_yaml = DATASET / "data.yaml"

    model = YOLO(args.model)
    results = model.train(
        data=str(data_yaml),
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project=str(OUTDIR),
        name="run",
        exist_ok=True,
        plots=True,
        verbose=True,
    )

    # Copy ultralytics best.pt + results.csv to the iteration root.
    run_dir = OUTDIR / "run"
    best_src = run_dir / "weights" / "best.pt"
    if best_src.exists():
        shutil.copy(best_src, OUTDIR / "best.pt")
        print(f"copied {best_src} -> {OUTDIR / 'best.pt'}")
    results_csv = run_dir / "results.csv"
    if results_csv.exists():
        shutil.copy(results_csv, OUTDIR / "train_log.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
