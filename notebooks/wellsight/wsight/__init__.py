"""WellSight shared library — consolidated models, datasets, training, inference,
and evaluation utilities for the pit / plat / road segmentation tasks.

This package is the canonical home for code that was previously duplicated across
the per-iteration scripts under `notebooks/wellsight/pits/iter_XX/`, the plat and
road trainers, and the annotation/feature-build helpers.

Public surface (the things actual scripts should import):

  Models & loss
    from wsight.models import UNet, make_smp_unet, load_segmentation_checkpoint
    from wsight.losses import FocalCE
    from wsight.metrics import per_class_iou, pixel_iou_in_mask

  Data
    from wsight.datasets import SegmentationTiles, RoadTiles, RoadPatchDataset

  Training
    from wsight.training import run_epoch, train_segmentation

  Inference
    from wsight.inference import (tta_predict_batch, sliding_window_predict,
                                  write_prob_raster, write_argmax_raster)
    from wsight.ensemble import (mean_ensemble, maxpit_ensemble,
                                 sliding_window_predict_pair)

  Evaluation
    from wsight.evaluation import (pit_test_eval, plat_test_eval,
                                   road_pixel_eval, road_line_ap)

  Pipelines (one-off scripts wrapped as importable functions)
    from wsight.feature_build import compute_curvature, compute_geomorphons, build_feature_stack
    from wsight.annotations_build import prep_annotations, build_pit_dataset, build_plat_road_dataset

  Project paths & constants
    from wsight.paths import (ROOT, DERIV, TILE_DIR, ANN_GPKG, PIT_LABELS,
                              PLAT_LABELS, ROAD_LABELS, BLOCKS_GPKG, PIT_MANIFEST,
                              FEATURES_7CH, FEATURES_STATS_7CH,
                              CHANNEL_ORDER_7CH, CHANNEL_ORDER_11CH, PROJECT_CRS)

Iteration history:
  Each `notebooks/wellsight/pits/iter_XX_*/` directory contains the thin runner for
  one iteration on top of this library. The runner sets parameters and calls into
  wsight.training / wsight.inference. The library itself is the same across all
  iterations -- it's what changed between them that gets documented per-iter.
"""

__version__ = "0.1.0"
