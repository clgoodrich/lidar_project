# 04_models — a model is a bundle

One directory per training run: `<target>/<run>/`. Everything that answers
"how good is this model" lives together — the checkpoint, the dataset manifest,
the training log, the metrics, and the probability rasters that run produced.

Before Phase 4D that evidence was split three ways. The pit U-Net's checkpoint
was in `tiles/9t/pit_unet_cv5/`, its prob rasters were loose in `tiles/9t/`, and
its threshold sweep was in `eval_9t_pit_thresholds/`. Answering one question
meant opening four directories.

```
04_models/
├── pit/        unet_cv5/  unet_v2/
├── pad/        unet_cv5/
├── plat/       unet/
├── road/       unet_05/  unet_1m/  unet_1m_recall/
│               unet_1m_recall_relabeled20260806/
│               unet_1m_corrected/  unet_1m_corrected_r2/  sweep_202607/
├── drainage/   unet_1m/
├── multitask/  unet/
├── classifiers/road_classifier/
├── pretrained/ seed weights (yolov8s-seg.pt, yolo26n.pt)
└── _retired/   9,055 files: 01_tta_miou .. 06_dem_only, plat_01-04,
                road_01-04, pit_07_maskrcnn, pit_08_yolo, pad_05_maskrcnn,
                pad_06_yolo, and the road post-filter variants
```

## `_retired/` is superseded, not dead

Every run in there is beaten by `pit/unet_cv5`, `pad/unet_cv5` or
`road/unet_1m_*`. It is kept, whole and in one place, because
`docs/iterations/LEADERBOARD.md` cites its numbers throughout and six branches on
origin are named after those iterations. Moving it as a unit is deliberate —
scattering it would break the leaderboard's provenance.

## What is tracked

The record, not the bulk. Manifests, training logs, metrics JSON/CSV and
per-run READMEs are tracked. `*.pt`, `*.tif`, `*.npz`, `dataset/` and `run/` are
ignored — they are regenerable from the training script and the feature stack.

## Paths

Reach these from code with `path_for("models")`, never by spelling the
directory. `path_for("models_retired")` for `_retired/`, `path_for("pretrained")`
for the seed weights.
