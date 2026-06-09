# `wsight` — Consolidated Shared Library

The `wsight` Python package at `notebooks/wellsight/wsight/` is the canonical home for code that used to be duplicated across the pit / plat / road iteration scripts. Future iteration runners should import from `wsight` instead of re-defining the same model/loss/dataset classes per iteration folder.

## Why this exists

Before consolidation, each iteration folder (`pits/iter_01_tta_miou/`, `pits/iter_02_smp_pretrained/`, `plats/iter_01_tta_miou/`, etc.) contained its own copy of:

- A custom or SMP U-Net definition
- A focal-loss class
- A `PitTiles` / `PlatTiles` / `RoadTiles` dataset
- A `run_epoch` training loop
- An `infer_full` sliding-window inference function
- A `tta_predict_batch` helper
- A `test_eval` function

That's roughly 200–300 lines per iteration duplicated. When a bug appears in any of those (e.g., a TTA augmentation that didn't invert correctly), it has to be fixed in every iteration's runner — which won't happen in practice. Hence the consolidation.

The original per-iteration scripts are **kept as-is on their branches** (they're the reproducible record of what was run). Future iterations import from `wsight` instead.

## What's in the package

```
notebooks/wellsight/wsight/
├── __init__.py        package marker + public-surface docstring
├── paths.py           project paths, CRS, canonical channel orders
├── models.py          UNet (custom), make_smp_unet, load_segmentation_checkpoint
├── losses.py          FocalCE (multi-class with per-class alpha)
├── metrics.py         per_class_iou, pixel_iou_in_mask
├── datasets.py        SegmentationTiles, RoadTiles, RoadPatchDataset
├── training.py        run_epoch, train_segmentation
├── inference.py       tta_predict_batch, sliding_window_predict, write_*_raster
├── ensemble.py        sliding_window_predict_pair, mean_ensemble, maxpit_ensemble
└── evaluation.py      pit_test_eval, plat_test_eval, road_pixel_eval, road_line_ap
```

## Public surface (the things future runners should import)

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path('notebooks/wellsight').resolve()))

from wsight.paths import (
    PROJECT_CRS, DEM_PATH, FEATURES_7CH, FEATURES_STATS_7CH,
    PIT_LABELS, PLAT_LABELS, ROAD_LABELS, BLOCKS_GPKG,
    PIT_MANIFEST, PLAT_MANIFEST, ROAD_MANIFEST, ANN_GPKG,
    CHANNEL_ORDER_7CH, CHANNEL_ORDER_11CH, ITERATIONS_DIR,
)
from wsight.models import UNet, make_smp_unet, load_segmentation_checkpoint
from wsight.losses import FocalCE
from wsight.datasets import SegmentationTiles, RoadTiles, RoadPatchDataset
from wsight.training import train_segmentation
from wsight.inference import sliding_window_predict, write_prob_raster, write_argmax_raster
from wsight.ensemble import sliding_window_predict_pair, mean_ensemble, maxpit_ensemble
from wsight.evaluation import pit_test_eval, plat_test_eval, road_pixel_eval, road_line_ap
```

## Minimal iteration runner template

What a new iteration runner looks like with `wsight`:

```python
import sys, json, torch
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))  # to find wsight/
from torch.utils.data import DataLoader
import numpy as np, pandas as pd, rasterio, geopandas as gpd

from wsight.paths import (FEATURES_7CH, FEATURES_STATS_7CH, PIT_LABELS,
                          BLOCKS_GPKG, PIT_MANIFEST, ITERATIONS_DIR,
                          CHANNEL_ORDER_7CH, ANN_GPKG)
from wsight.models import UNet, load_segmentation_checkpoint
from wsight.losses import FocalCE
from wsight.datasets import SegmentationTiles
from wsight.training import train_segmentation
from wsight.inference import sliding_window_predict, write_argmax_raster, write_prob_raster
from wsight.evaluation import pit_test_eval

OUTDIR = ITERATIONS_DIR / "06_my_new_iter"; OUTDIR.mkdir(parents=True, exist_ok=True)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# Load stats + manifest
stats = json.loads(FEATURES_STATS_7CH.read_text())
mu = np.array([stats[c]["mean"] for c in CHANNEL_ORDER_7CH], dtype=np.float32)
sd = np.array([max(stats[c]["std"], 1e-6) for c in CHANNEL_ORDER_7CH], dtype=np.float32)
manifest = pd.read_csv(PIT_MANIFEST)
blocks = gpd.read_file(BLOCKS_GPKG, layer="blocks")
with rasterio.open(FEATURES_7CH) as r: tf = r.transform

# Build datasets (same shape for pit / plat / road)
train_ds = SegmentationTiles(
    FEATURES_7CH, PIT_LABELS,
    centroids=manifest[manifest.split == "train"][["centroid_x", "centroid_y"]].values,
    split_block_bounds=np.array([g.bounds for g in blocks[blocks.split == "train"].geometry]),
    transform=tf, mu=mu, sd=sd, patch=256, jitter_m=30, bg_per_pos=1, augment=True,
)
val_ds = SegmentationTiles(
    FEATURES_7CH, PIT_LABELS,
    centroids=manifest[manifest.split == "val"][["centroid_x", "centroid_y"]].values,
    split_block_bounds=np.array([g.bounds for g in blocks[blocks.split == "val"].geometry]),
    transform=tf, mu=mu, sd=sd, patch=256, jitter_m=30, bg_per_pos=1, augment=False,
)
train_loader = DataLoader(train_ds, batch_size=16, shuffle=True, num_workers=0, pin_memory=True)
val_loader = DataLoader(val_ds, batch_size=16, shuffle=False, num_workers=0, pin_memory=True)

# Model + loss + training
model = UNet(in_ch=7, n_classes=3, base=32).to(DEVICE)
loss_fn = FocalCE(alpha=(0.05, 0.475, 0.475), gamma=2.0).to(DEVICE)
opt = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=40)
scaler = torch.amp.GradScaler("cuda", enabled=DEVICE.type == "cuda")

train_segmentation(
    model, train_loader, val_loader,
    loss_fn=loss_fn, opt=opt, scheduler=sched, scaler=scaler, device=DEVICE,
    n_classes=3, epochs=40, miou_classes=[1, 2],
    ckpt_path=OUTDIR / "best.pt",
    ckpt_extras={"mu": mu, "sd": sd, "channels": CHANNEL_ORDER_7CH, "patch": 256},
    log_path=OUTDIR / "train_log.csv",
    label="iter 06",
)

# Inference + eval
model, mu, sd, meta = load_segmentation_checkpoint(OUTDIR / "best.pt", device=DEVICE)
prob = sliding_window_predict(model, FEATURES_7CH, mu, sd,
                              device=DEVICE, n_classes=3, patch=256, overlap=64,
                              batch=8, use_tta=True)
argmax = prob.argmax(0).astype("uint8")
write_prob_raster(prob[1], PIT_LABELS, OUTDIR / "pit_prob_floor.tif")
write_prob_raster(prob[2], PIT_LABELS, OUTDIR / "pit_prob_wall.tif")
write_argmax_raster(argmax, PIT_LABELS, OUTDIR / "pit_argmax.tif")
pit_test_eval(argmax, labels_path=PIT_LABELS, blocks_path=BLOCKS_GPKG,
              manifest_path=PIT_MANIFEST, annotations_gpkg=ANN_GPKG,
              out_dir=OUTDIR)
```

That's the entire runner. ~50 lines vs the ~250-line scripts each iteration shipped previously.

## What's NOT in wsight

The library deliberately doesn't try to abstract everything. These remain per-iteration concerns:

- **Iteration-specific hyperparameters** (epochs, lr, alpha values per task, jitter range, batch size). Different per task; live in the runner.
- **Feature stack construction.** Building the 7-channel and 11-channel TIFs is a one-off pipeline, not a per-iteration concern. See `docs/pipelines/feature_stack.md`.
- **Post-filter logic** (iter 05 family). These are specialized component-wise rules; they live in their own iteration folders.
- **Annotation preparation** (shapefile → rasterized labels). Also one-off; see `docs/pipelines/annotations.md` and `docs/pipelines/pit_dataset.md`.

## Migration plan for old iterations

The existing pit/plat/road iter folders are **not** being migrated. They're the reproducible record of what was run, and changing them would invalidate the leaderboard. New iterations should use `wsight`; old ones stay as-is.

If a bug is found in (say) the TTA function and it affects historical results, the right move is:
1. Document the bug in the affected iteration docs.
2. Fix it in `wsight`.
3. Re-run the affected iterations as new iters (`pit iter 01_v2`, etc.) — don't silently overwrite.

## Smoke test

```bash
python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('notebooks/wellsight').resolve()))
import wsight
from wsight import paths, models, losses, metrics, datasets, training, inference, ensemble, evaluation
print('wsight', wsight.__version__, 'imports OK')
"
```

Expected output: `wsight 0.1.0 imports OK`.
