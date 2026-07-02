# 9t Iteration Leaderboard

Per-task metrics across iterations on the 9t tile. **All instance rows re-scored
2026-07-02** against the test split of the 2026-06-10 dataset rebuild —
`pit_dataset_manifest.csv` (**65 test** of 426 pits: 298/63/65) and
`plat_dataset_manifest.csv` (**93 test** of 650 pads: 456/101/93) — with same-era
checkpoints (pit_07 / pit_08 / pad_06 trained 06-11; pad_05 retrained 07-02, best = ep 3).

**Metric protocol (2026-07-02).** `_instance_common.per_instance_metrics` now does
**greedy 1:1 matching** (predictions sorted by score; each prediction may match at most
one GT and vice versa) and reports **precision and F1** alongside recall. The legacy
loose recall (per-GT best-IoU, no assignment) is kept as `recall_loose_*` for
continuity — on these models loose ≈ 1:1 recall because detections are abundant.
Semantic-UNet rows use the identical metric via `_unet_instance_eval.py` (prob →
threshold → connected components → polygons), with the **threshold selected on val**
and test scored once frozen. Pre-07-02 numbers selected thresholds on test itself.

## Pits (65 test instances)

| Iteration | Approach | R@0.3 | P@0.3 | F1@0.3 | R@0.5 | Mean IoU | # Det | Notes |
|---|---|---|---|---|---|---|---|---|
| pit_unet_v2 (instance metric†) | UNet semantic, blobs→instances | 0.55 | 0.033 | 0.062 | 0.32 | 0.314 | 1105 | thr 0.7 (val-chosen). Blobs don't commit object boundaries → collapses under instance metric. |
| pit_unet_v2 (native localized‡) | UNet semantic 3-class | 0.80‡ | — | — | — | 0.566‡ | — | UNet's own per-pit *local pixel* IoU — more forgiving (see ‡). |
| **pit_07_maskrcnn (7-band)** | Mask R-CNN R50-FPN v2, floor+wall | **0.97** | 0.053 | 0.100 | **0.85** | **0.631** | 2978 (1190 fl / 1788 wa) | Best recall + IoU. score≥0.3. |
| pit_08_yolo | YOLOv8s-seg | 0.92 | **0.054** | **0.102** | 0.69 | 0.572 | 3631 (1184 fl / 2447 wa) | conf 0.05 — detection volume inflated by design; BGR flip required at inference. |
| pit post-proc extraction | UNet prob → tuned blob filter → centroids | rec 0.49 | prec 0.092 | 0.155 | — | — | 349 | **Point-level metric** (6 m centroid tol), val-tuned, test-frozen — not row-comparable; see [[pit_optimize]]. |

## Pads (93 test instances)

| Iteration | Approach | R@0.3 | P@0.3 | F1@0.3 | R@0.5 | Mean IoU | # Det | Notes |
|---|---|---|---|---|---|---|---|---|
| plat_unet (instance metric†) | UNet semantic, blobs→instances | 0.91 | 0.070 | 0.129 | 0.76 | 0.595 | 1222 | thr 0.5 (val-chosen). Holds up far better than the pit UNet. |
| plat_unet (native localized‡) | UNet semantic binary | 0.78‡ | — | — | — | 0.473‡ | — | Per-plat local pixel IoU. |
| **pad_05_maskrcnn (7-band)** | Mask R-CNN R50-FPN v2 | **0.98** | 0.029 | 0.057 | **0.90** | **0.690** | 3075 | Retrained 2026-07-02 (best = ep 3, val 0.787). Recall/IoU king, worst precision. |
| pad_06_yolo | YOLOv8s-seg | 0.88 | **0.064** | **0.118** | 0.83 | 0.661 | 1255 | Best F1 — 2.5× fewer detections for −10 pts recall. |

**Reading the tables.** Precision is 3–6% across every instance model: they find nearly
every annotated feature but emit 12–47× more detections than there are GT instances.
The pre-07-02 leaderboard (recall-only, n_test 20/9) could not see this. Two levers,
in order: (1) **score-threshold sweep selected on val** — current thresholds (0.3;
YOLO pit 0.05) were never tuned; (2) the **active-learning loop** (reject-as-hard-negative
retraining), which attacks the root cause. Raw recall says Mask R-CNN; F1 says YOLO;
deployment says: tune the threshold first, then re-rank.

† **Instance metric (apples-to-apples).** UNet prob raster → threshold (val-selected) →
connected components → one scored polygon per blob → identical `per_instance_metrics`.
Script: `_unet_instance_eval.py`; sweep + frozen-test numbers in
`iterations/unet_instance_eval/SUMMARY.md`.

‡ **Native localized metric.** UNet's own `test_metrics.json`: per-pit IoU computed
*inside a small crop around each known pit* (pit-vs-bg pixel IoU). Never has to separate
instances or commit object boundaries, and only scored where a pit is already known to
be. Not comparable to the detector rows; shown to explain the gap.

## Roads (semantic — line-level metric on 9t test split)

Roads are a binary segmentation task, scored by **per-line average precision** (mean
P(road) along each test line, ranked vs `not_road` decoys) and pixel IoU. Not comparable
to the instance tables above. Test split per `road_dataset_manifest.csv`.

| Iteration | Approach | Res | Pixel IoU (road) | Line AP | P(road) road / drainage | Notes |
|---|---|---|---|---|---|---|
| road_unet | UNet binary, FocalCE | 0.5 m | 0.343 | 0.963 | 0.565 / — | Retrained 2026-06-07 on latest roads (171 in-tile lines). Over-fires on 1 m blocks (33% px). |
| road_unet_1m (2-class) | UNet binary, FocalCE, roughness_5 | 1 m | 0.379 | 0.962 | 0.654 / — | Matches the 1 m blocks but fires on drainage; needed an aggressive post-filter. |
| road_unet_1m (3-class) | UNet bg/road/drainage | 1 m | 0.527 | 0.963 | 0.676 / 0.005 | Drainage as a trained class (from `drainage.shp`) → P(road) on channels →0.005. |
| road_unet_1m (3-class + chunked) | UNet bg/road/drainage, roads chunked ~40 m | 1 m | 0.581 | 0.992 | 0.757 / 0.006 | Roads chunked so every ~40 m is a patch center; eval over 168 chunks (was 27 lopsided lines). Drainage handled in-model — no post-filter needed. See [[road_unet_1m]]. |
| road_unet_mb (3-class, 6 blocks) | UNet bg/road/drainage, 191 km multi-block | 1 m | 0.223‖ | 0.997 | 0.508 / 0.011 | **Rejected.** Trained across 6 data_3x3 blocks to add data. Overfit (best val ep7; 618594 = 84% of road) and came out *under-confident* on out-of-domain 613590 (P 0.46). Diluting the dense 9t core hurt. ‖IoU is on held-out block 622594, not 9t. |
| **road_unet_1m_recall (3-class, α0.72)** | UNet bg/road/drainage, road focal-α 0.60→0.72, wd 2e-4 | 1 m | **0.581** | **0.999** | **0.778 / 0.004** | **Current.** Same clean 9t data; in-domain ≈ chunked row, but the point is *out-of-domain recall*: on 613590 mean P(road) 0.57→0.66, road≥0.5 px ~1.7×, cleaned network 155→**169 km**, TIGER recall 0.501→**0.523**. Fixed gappy roads via class weighting, not more data. See [[road_unet_1m_recall]]. |

**Vector extraction (2026-07-02, honest protocol):** `_road_optimize.py` cleaning
config tuned on **val** blocks only (best val F1 0.535), frozen, then scored once on
test: **F1 0.754** (completeness 0.695 / correctness 0.824, 22.5 km GT). Test > val
because the val region has ~half the road density — selection never saw test.
Config + both splits in `road_unet_1m_recall/road_postproc_best.json`.

## Cross-reference vs PA DEP known wells (full catalog)

Beyond the annotated test split, each model's detections were scored against the **full
PA DEP Oil & Gas locations catalog** clipped to the 9t extent — **1,069 catalogued
wells**. (The hand-annotation set is now 426 pits / 1,053 pads repo-wide, 426 + 650
inside 9t.) A well counts as "matched" if any detection centroid lands within 25 m.
Re-run 2026-07-02 on the fresh detections; outputs in
`data/derivatives/tiles/9t/iterations/known_well_validation/`.

| Model | Detections | Wells matched (/1069) | Well recall | Median nearest (m) |
|---|---|---|---|---|
| pit_07_maskrcnn | 2979 | 373 | 0.35 | 42.0 |
| pit_08_yolo | 3602 | 397 | 0.37 | 35.1 |
| pad_05_maskrcnn | 3127 | 521 | 0.49 | 26.4 |
| pad_06_yolo | 1291 | 337 | 0.32 | 48.3 |

**Interpretation — do not read these as model failure.** The DEP catalog contains every
recorded well regardless of whether it has any LiDAR-visible surface expression. Many are
plugged/reclaimed, predate the 2019 lidar, sit under canopy, or never had a pit/pad. So:
- A well recall of 0.49 (pad_05) means ~520 catalogued wells have a pad-like surface
  feature the model found — a *lower bound* on wells with surface expression, not a
  fraction of detectable wells missed.
- The annotations cover a minority of catalogued wells in this tile; the label set is
  still the bottleneck, not the architecture.
- **Actionable next step:** the DEP catalog could seed semi-automated annotation (snap
  to nearest depression, human-confirm) to grow the label set further.

## Sources

- Per-iteration `test_metrics.json` lives in `data/derivatives/tiles/9t/iterations/<iter>/test_metrics.json`.
- Per-instance breakdowns in `test_per_pit.csv` / `test_per_plat.csv`.
- Iteration writeups in `docs/iterations/<iter>.md`.

## How instance metrics are computed

Predictions and GT are matched **greedily 1:1**: candidate (GT, pred) pairs with
IoU ≥ τ are taken in descending prediction-score order; each GT and each prediction can
be used once. Recall@τ = matched GT / n GT; Precision@τ = matched preds / n preds;
F1 harmonic. `recall_loose_*` (per-GT best IoU, no assignment — the pre-07-02 headline
number) is retained in every `test_metrics.json` for continuity.

<details><summary>Legacy results (pre-2026-06-10 dataset: 110 pits / 79 pads, n_test 20 / 9, loose recall only — not comparable to the tables above)</summary>

| Model | R@0.1 | R@0.3 | R@0.5 | Mean IoU | # Det |
|---|---|---|---|---|---|
| pit_07_maskrcnn v1 (3-band) | 1.00 | 1.00 | 0.85 | 0.632 | 1385 |
| pit_07_maskrcnn v2 (7-band) | 1.00 | 1.00 | 0.95 | 0.664 | 2027 |
| pit_08_yolo | 0.90 | 0.85 | 0.75 | 0.541 | 728 |
| pad_05_maskrcnn v1 (3-band) | 1.00 | 1.00 | 0.889 | 0.688 | 3250 |
| pad_05_maskrcnn v2 (7-band) | 1.00 | 1.00 | 0.889 | 0.631 | 2546 |
| pad_06_yolo | 0.778 | 0.778 | 0.667 | 0.564 | 818 |

Known-well cross-reference at that era: pit_07 327, pit_08 242, pad_05 454, pad_06 239
of 1069 matched.
</details>
