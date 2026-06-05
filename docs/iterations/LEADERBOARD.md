# 9t Iteration Leaderboard

Per-task metrics across iterations on the 9t tile. Numbers are computed against the test split of `pit_dataset_manifest.csv` (20 pits) and `plat_dataset_manifest.csv` (9 plats) unless noted.

For semantic UNet iterations the comparable quantity is **per-instance recall on the test split** (computed by `pit_unet_v2_infer.py` / similar). For instance models (Mask R-CNN, YOLO) it's the same per-instance recall computed from polygonised detections via `_instance_common.per_instance_metrics`.

## Pits (20 test instances)

| Iteration | Approach | Recall@0.1 | Recall@0.3 | Recall@0.5 | Mean IoU | # Detections | Notes |
|---|---|---|---|---|---|---|---|
| pit_unet_v2 (instance metric†) | UNet semantic, blobs→instances | — | 0.15 | 0.00 | 0.112 | 1205 | Best of thr sweep (0.7). Collapses under the instance metric — see †. |
| pit_unet_v2 (native localized‡) | UNet semantic 3-class | — | 0.80‡ | — | 0.566‡ | — | UNet's own per-pit *local pixel* IoU — more forgiving metric (see ‡) |
| pit_03_multiscale_feats | UNet + multiscale features | — | — | — | — | — | Not re-scored under instance metric |
| pit_04_ensemble_01_03 | UNet ensemble | — | — | — | — | — | — |
| pit_06_dem_only | UNet, DEM single channel | — | — | — | — | — | Rejected per recent experiment notes |
| pit_07_maskrcnn (v1, 3-band) | Mask R-CNN ResNet50-FPN v2 | 1.00 | 1.00 | 0.85 | 0.632 | 1385 | Old 3-band composite input |
| **pit_07_maskrcnn (v2, 7-band)** | Mask R-CNN, 7-band UNet stack, floor+wall | **1.00** | **1.00** | **0.95** | **0.664** | 2027 (947 floor / 1080 wall) | Floor recall scored. 7-band conv1-widened; best=ep1 |
| pit_08_yolo | YOLOv8s-seg | 0.90 | 0.85 | 0.75 | 0.541 | 728 | Required BGR channel flip at inference (training-time PIL→cv2 swap) |

† **Instance metric (apples-to-apples).** UNet prob raster thresholded → connected components → one polygon per blob → identical `per_instance_metrics` as the detectors. Best of a {0.3, 0.5, 0.7} threshold sweep. Script: `_unet_instance_eval.py`; outputs in `iterations/unet_instance_eval/`.

‡ **Native localized metric.** UNet's own `test_metrics.json`: per-pit IoU computed *inside a small crop around each known pit* (pit-vs-bg pixel IoU). Much more forgiving — it never has to separate instances or commit object boundaries, and is only scored where a pit is already known to be. Not comparable to the detector rows; shown only to explain the gap.

## Pads (9 test instances)

| Iteration | Approach | Recall@0.1 | Recall@0.3 | Recall@0.5 | Mean IoU | # Detections | Notes |
|---|---|---|---|---|---|---|---|
| plat_unet (instance metric†) | UNet semantic, blobs→instances | — | 0.78 | 0.44 | 0.449 | 1518 | Best of thr sweep (0.5). Holds up far better than pit UNet. |
| plat_unet (native localized‡) | UNet semantic binary | — | 0.78‡ | — | 0.473‡ | — | UNet's own per-plat local pixel IoU |
| plat_03_multiscale_feats | UNet + multiscale | — | — | — | — | — | Not re-scored under instance metric |
| plat_04_ensemble | UNet ensemble | — | — | — | — | — | — |
| pad_05_maskrcnn (v1, 3-band) | Mask R-CNN ResNet50-FPN v2 | 1.00 | 1.00 | 0.889 | 0.688 | 3250 | Old 3-band composite input |
| **pad_05_maskrcnn (v2, 7-band)** | Mask R-CNN, 7-band UNet stack | **1.00** | **1.00** | **0.889** | **0.631** | 2546 | best=ep0. 7-band cut FPs 3250→2546 but still over-predicts |
| pad_06_yolo | YOLOv8s-seg | 0.778 | 0.778 | 0.667 | 0.564 | 818 | Best precision/recall tradeoff in pad row |

†/‡ same metric definitions as the Pits table above. Full threshold sweep in `iterations/unet_instance_eval/SUMMARY.md`.

## Cross-reference vs PA DEP known wells (full catalog)

Beyond the hand-annotated test split, each model's detections were scored against the **full PA DEP Oil & Gas locations catalog** clipped to the 9t extent — **1069 catalogued wells** (vs only 110 hand-annotated pits / 79 plats). A well counts as "matched" if any detection centroid lands within 25 m. Outputs in `data/derivatives/9t/iterations/known_well_validation/`.

| Model | Detections | Wells matched (/1069) | Well recall | Median nearest (m) |
|---|---|---|---|---|
| pit_07_maskrcnn | 1385 | 327 | 0.31 | 47.9 |
| pit_08_yolo | 728 | 242 | 0.23 | 73.2 |
| pad_05_maskrcnn | 3277 | 454 | 0.42 | 31.2 |
| pad_06_yolo | 921 | 239 | 0.22 | 66.4 |

**Interpretation — do not read these as model failure.** The DEP catalog contains every recorded well regardless of whether it has any LiDAR-visible surface expression. Many are plugged/reclaimed, predate the 2019 lidar, sit under canopy, or never had a pit/pad. The models were trained on 110 hand-picked pits with clear depressions — a deliberately narrow signature. So:
- A well_recall of 0.42 (pad_05) means ~450 catalogued wells have a pad-like surface feature the model found — a *lower bound* on true wells with surface expression, not a fraction of detectable wells missed.
- The 110 annotations cover <11% of catalogued wells in this tile alone; the annotation set is the bottleneck, not the architecture.
- **Actionable next step:** the gap between 110 annotations and 1069 catalogued wells is the strongest argument in the backlog for "better/more training data". The DEP catalog could seed semi-automated annotation (snap to nearest depression, human-confirm) to 10x the label set.

## Sources

- Per-iteration `test_metrics.json` lives in `data/derivatives/9t/iterations/<iter>/test_metrics.json`.
- Per-instance breakdowns in `test_per_pit.csv` / `test_per_plat.csv`.
- Iteration writeups in `docs/iterations/<iter>.md`.

## How recall is computed for instance models

For each test polygon `g_test`, the predicted instance polygon with the largest IoU is matched (no greedy assignment yet — a single prediction may match multiple GT). Recall@τ counts test polygons whose best-matched IoU ≥ τ. This favours high-recall, low-precision models. Track `# Detections` alongside to see precision context.
