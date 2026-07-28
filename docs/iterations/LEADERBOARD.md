# 9t Iteration Leaderboard

Per-task metrics across iterations on the 9t tile.

> **Read this first (2026-07-27).** Two things on this page were corrected today
> and the corrections are large.
> 1. **Every instance precision and F1 number changed.** The old 3–6% precision
>    was a measurement bug. Real values are 0.54–0.69. See the pit/pad tables.
> 2. **The DEP cross-reference section is not a model score** and its
>    "median nearest" column is not positional accuracy. Do not cite it.
>
> The current headline detection numbers are the **held-out threshold sweeps**,
> which score against hand-drawn annotation only.

**All instance rows re-scored
2026-07-02** against the test split of the 2026-06-10 dataset rebuild —
`pit_dataset_manifest.csv` (**65 test** of 426 pits: 298/63/65) and
`plat_dataset_manifest.csv` (**93 test** of 650 pads: 456/101/93) — with same-era
checkpoints (pit_07 / pit_08 / pad_06 trained 06-11; pad_05 retrained 07-02, best = ep 3).

**Metric protocol (2026-07-02).** `_instance_common.per_instance_metrics` now does
**greedy 1:1 matching** (predictions sorted by score; each prediction may match at most
one GT and vice versa) and reports **precision and F1** alongside recall. The legacy
loose recall (per-GT best-IoU, no assignment) is kept as `recall_loose_*` for
continuity. (The 07-02 note "loose ≈ 1:1 recall because detections are abundant"
rested on the inflated detection counts and no longer applies at tuned thresholds.)
Semantic-UNet rows use the identical metric via `_unet_instance_eval.py` (prob →
threshold → connected components → polygons), with the **threshold selected on val**
and test scored once frozen. Pre-07-02 numbers selected thresholds on test itself.

> ### ⚠️ Correction, 2026-07-27 — every precision and F1 number below changed
>
> The 2026-07-02 precision figures (3–6% across every model) were a **measurement
> bug, not a model result.** Three defects compounded:
> 1. **Extent mismatch.** Precision was `tp / n_pred` counting predictions across
>    the whole tile, against ground truth from the **test blocks only**. Every
>    correct prediction outside a test block scored as a false positive.
> 2. **Class mismatch.** Pit predictions included floor **and wall** polygons,
>    scored against floor-only ground truth.
> 3. **Untuned thresholds.** Score thresholds (0.3, YOLO pit 0.05) were never
>    selected, so detection volume was arbitrary.
>
> Corrected in `notebooks/wellsight_v2/eval/_reeval_instance_precision_9t.py`:
> predictions clipped to the scored extent, class-matched, thresholds selected on
> **val** and test scored **once** frozen. Source of truth is
> `data/derivatives/eval_9t_instance_precision/_reeval_9t.json`.
>
> **Real precision is 0.54–0.69 across all six rows, not 0.03–0.07.** Recall also
> moves, because the thresholds moved. The conclusion "detection volume is the
> limiting problem" was drawn from the bug and is withdrawn.

## Pits (65 test instances) — corrected 2026-07-27

Thresholds selected on val, test scored once. IoU τ = 0.3, greedy 1:1 matching.

| Iteration | Approach | thr (val) | val F1 | R@0.3 | P@0.3 | F1@0.3 |
|---|---|---|---|---|---|---|
| pit_unet_v2 (instance metric†) | UNet semantic, blobs→instances | 0.60 | 0.769 | 0.754 | 0.620 | 0.681 |
| **pit_07_maskrcnn (7-band)** | Mask R-CNN R50-FPN v2, floor+wall | 0.95 | 0.752 | **0.938** | 0.622 | **0.748** |
| pit_08_yolo | YOLOv8s-seg | 0.45 | 0.789 | 0.769 | **0.641** | 0.699 |
| pit_unet_v2 (native localized‡) | UNet semantic 3-class | — | — | 0.80‡ | — | — |
| pit post-proc extraction | UNet prob → tuned blob filter → centroids | — | — | 0.49 | 0.092 | 0.155 |

The post-proc row is a **point-level metric** (6 m centroid tolerance), val-tuned
and test-frozen. It was not part of the 07-27 reeval and is not row-comparable.
See [[pit_optimize]].

### Pits, 5-fold cross-validated — all 426 pits, 2026-07-27

The rows above rest on one split of 65 test pits. This is the same architecture,
loss, channels and schedule, trained five times, each holding out a different
fifth of the tile. Every pit is scored by a model that never saw it. Thresholds
are selected on an inner val split under an objective named in advance.

| Selection | thr chosen per fold | R@0.3 | P@0.3 | R@0.5 | containment |
|---|---|---|---|---|---|
| by F1 | 0.40, 0.50, 0.50, 0.50, 0.55 | **0.854** (sd 0.088) | 0.617 | 0.711 | 0.899 |
| by F2 | 0.30, 0.30, 0.30, 0.35, 0.55 | **0.920** (sd 0.035) | 0.553 | 0.730 | 0.955 |

**The single-split 0.754 was pessimistic.** That split drew a hard fifth, and its
val-selected threshold of 0.60 sits past the point where recall falls away.
Cross-validated recall at IoU 0.3 is 0.854 under the same F1 rule.

Recall is stable (F2 per-fold spread 0.880–0.953). Precision is the weak number
and never exceeds 0.65 at any threshold. Every fold is still 9t, so this shows
the number is **stable**, not that it **transfers**.

Full write-up: [[pit_unet_cv5_9t]].

## Pads (93 test instances) — corrected 2026-07-27

| Iteration | Approach | thr (val) | val F1 | R@0.3 | P@0.3 | F1@0.3 |
|---|---|---|---|---|---|---|
| plat_unet (instance metric†) | UNet semantic, blobs→instances | 0.50 | 0.667 | **0.882** | 0.547 | 0.675 |
| pad_05_maskrcnn (7-band) | Mask R-CNN R50-FPN v2 | 0.95 | 0.675 | 0.828 | 0.538 | 0.653 |
| **pad_06_yolo** | YOLOv8s-seg | 0.80 | 0.699 | 0.667 | **0.689** | **0.678** |
| plat_unet (native localized‡) | UNet semantic binary | — | — | 0.78‡ | — | — |

**Reading the corrected tables.** The models are broadly comparable, and no
architecture dominates. Pit F1 spans 0.681–0.748, pad F1 spans 0.653–0.678. Mask
R-CNN buys recall (0.938 pit) at the cost of precision; YOLO does the reverse.
The semantic U-Nets sit between them on both tasks while being the only models
that also produce a probability surface.

**What this changes.** The 07-02 reading — "they find nearly everything but emit
12–47× too many detections, so cut detection volume" — was an artifact. The
detectors are **not** the recall-at-any-cost machines that table implied once
their thresholds are tuned. Threshold selection was the whole story, and it is
now done. The active-learning loop is still worth running, but it is no longer
attacking a 30× false-positive rate that never existed.

⚠️ **Columns dropped from these tables.** `R@0.5`, `Mean IoU` and `# Det` came
from the 07-02 run at the old, untuned thresholds. Detection counts in
particular are meaningless now — YOLO pit moved from conf 0.05 to 0.45. They were
removed rather than left in place looking current. The 07-02 values are in git
(`ee55d73` and earlier) if needed.

† **Instance metric (apples-to-apples).** UNet prob raster → threshold (val-selected) →
connected components → one scored polygon per blob → identical `per_instance_metrics`.
Script: `_unet_instance_eval.py`; sweep + frozen-test numbers in
`iterations/unet_instance_eval/SUMMARY.md`.

‡ **Native localized metric.** UNet's own `test_metrics.json`: per-pit IoU computed
*inside a small crop around each known pit* (pit-vs-bg pixel IoU). Never has to separate
instances or commit object boundaries, and only scored where a pit is already known to
be. Not comparable to the detector rows; shown to explain the gap.

## Held-out threshold sweeps (2026-07-27) — the headline numbers

One question asked identically of all three U-Nets. At each probability cutoff,
**how much ground does the model flag, and how many withheld hand-drawn
annotations does it find?** "Flagged area" is the total area of pixels above the
cutoff, as a share of the 2,025 ha tile. It is the search burden a field crew
would actually inherit.

Scored against hand-drawn annotation withheld from training. No DEP list, no
TIGER. Full write-up in [[threshold_sweeps_pit_pad_road_9t]].

| Task | Withheld | Best operating point | Flagged area | Recall there |
|---|---|---|---|---|
| Pit | 127 rims | thr 0.20 | 4.33 ha = **0.21%** | 126/127 = **0.992** |
| Road | 1,220 chunks, 43.07 km | thr 0.20 | 101.65 ha = **5.02%** | **0.982** (`recall_clean`) |
| Pad | 194 plats | thr 0.45 | 235.77 ha = **11.64%** | 178/194 = **0.918** |

**The pad model is the weak one, and flagged area is what shows it.** All three
have high recall. Only the pit model turns that recall into a short list. Pad
needs 55× more ground than pit to find fewer of its targets. At thr 0.50 it
flags 197.95 ha against roughly 110 ha of total annotated pad area on the tile,
so it is over-claiming by about 2×.

Three findings worth carrying forward:

- **The road model rejects drainage, confirmed on hand-drawn negatives.**
  Held-out `not_road` is claimed at **0.0% at every threshold**; held-out
  drainage falls 3.9% → 2.1% across the useful range. Direct evidence the
  3-class design worked.
- **Road recall is nearly threshold-free on 9t** — above 0.95 from 0.05 to 0.80.
- **Road numbers carry known leakage.** Roads split as ~40 m chunks, not whole
  objects, so 485/1,220 held-out chunks (39.8%) share a parent road with train
  chunks. `recall_clean` (735 chunks whose entire parent road was held out) is
  the comparable number. Cost is ~1.5 points.

⚠️ **A single found/missed rule does not transfer across tasks.** Applying the
pit criterion (a prediction's centroid must lie inside the annotation) to pads
reported **0/194 found at threshold 0.05**, the cutoff flagging 58% of the tile.
Pad predictions merge into tile-spanning blobs at low cutoffs, and a blob's
centroid lies inside no individual pad. Pads are now scored on three criteria
that fail in opposite directions, with IoU ≥ 0.30 as the headline.

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
| **road_unet_1m_recall (3-class, α0.72)** | UNet bg/road/drainage, road focal-α 0.60→0.72, wd 2e-4 | 1 m | **0.581** | **0.999** | **0.778 / 0.004** | Same clean 9t data; in-domain ≈ chunked row, but the point is *out-of-domain recall*: on 613590 mean P(road) 0.57→0.66, road≥0.5 px ~1.7×, cleaned network 155→**169 km**, TIGER recall 0.501→**0.523**. Fixed gappy roads via class weighting, not more data. See [[road_unet_1m_recall]]. |
| road_unet_1m_corrected (α0.72 + 613590 human corrections) | Fine-tune of recall model on 9t + corridor-supervised 613590 review diff | 1 m | 0.573 | 0.999 | 0.784 / 0.005 | **Active-learning loop closed (2026-07-20).** In-domain 9t held flat (IoU −0.008, noise). The gain is on **613590 held-out corrections**: mean P(road) on human-added missed roads 0.72→**0.76** (val), 0.74→**0.78** (test), frac≥0.5 up 0.85→0.94 / 0.89→0.96; false-positive rejects 0.34→**0.26** (val); added-vs-reject AP 0.245→**0.443** (val). 22 km of human edits → out-of-domain recall up, precision up, zero in-domain cost. See [[road_unet_1m_corrected]]. |

### Sweep road_sweep_202607 (2026-07-21) — 5 one-change variants vs corrected, seeded/frozen-val

Same 9t+corrections recipe, one knob each. Two poles emerged — no runaway winner. Full table + interpretation in [[road_sweep_202607]]. Held-out cols are 613590 val+test correction cells.

| Variant | Change | 9t val IoU | 9t pixIoU | P(road) / P(drain) | 613590 added≥0.5 / add-v-rej AP | Verdict |
|---|---|---|---|---|---|---|
| cldice | +soft-clDice topology loss | 0.593 | 0.558 | **0.885** / 0.006 | **0.957** / 0.470 | **Connectivity pole** — best gap-filling & missed-road recovery; low pixIoU is a metric artifact (topology≠pixels). Front-runner pending APLS. |
| boundary | 3× road-edge weight | **0.668** | **0.601** | 0.742 / **0.004** | 0.913 / 0.530 | **Precision pole** — best pixIoU & cleanest drainage, but fills less. |
| alpha078 | road α 0.72→0.78 | 0.639 | 0.580 | 0.790 / 0.005 | 0.935 / 0.553 | ≈ no-op; α headroom already spent. |
| orient | +orientation aux head (scratch) | 0.636 | 0.577 | 0.739 / **0.030** | 0.826 / **0.660** | Best add-v-rej separation but **drainage bled 6×**; deploy-disqualifying as-is. |
| res05 | 0.5 m (9t-only, scratch) | 0.502‖ | 0.486‖ | 0.707 / 0.027 | — | Inconclusive; ‖0.5 m grid not pixIoU-comparable, likely undertrained. Re-run w/ road-physics channels. |
| cldice_sg3† | cldice + 3 linear-feature channels (savgol_resid, profile_curv, rough_aniso) | 0.594 | 0.550 | 0.889 / **0.005** | **0.978** / **0.486** | Modest gain on the axis that matters — best missed-road recovery (0.957→0.978) and add-v-rej AP (0.470→0.486), P(road) up, drainage cleanest. Cost: pixIoU −0.008 and reject confidence up (more FPs). **Small deltas, single seed — promising, not conclusive.** |

†Added 2026-07-23 (not part of the 2026-07-21 five-variant sweep). Identical recipe to `cldice`
(same seed, batch 16, 12 ep, corrected init transferred via a 7→10 expanded first conv, 3 new
filters zero-init) — the ONLY difference is the three appended channels. See [[linear_feature_channels]].

**Decision:** run cldice + boundary through `_road_optimize.py` → compare APLS/completeness vs the 0.754 F1; promote the winner then. clDice+boundary combined is the natural full-10 first entry.

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

> ### ⚠️ Correction, 2026-07-27 — this whole section is not a model score
>
> Two problems, and the second is worse than the first.
>
> **1. The denominator double-counts.** `uncounted_wells_9t.gpkg` holds 1,364
> rows but only **872 unique `PERMIT_NUM`**. "1,069 catalogued wells" and the
> match counts below are inflated by duplicate permits.
>
> **2. "Median nearest (m)" is not a positional-accuracy measure**, and it has
> been read as one. It is the distance from a catalogued well to the nearest
> **model detection** — a model that emits more detections drives it down for
> free. It says nothing about how well DEP coordinates locate real wells.
>
> Recomputed 2026-07-27 against **hand-drawn annotation** instead of detections:
>
> | measurement | value |
> |---|---|
> | annotated pits with a catalogued well within 25 m | **27 of 424 (6.4%)** |
> | median distance, annotated pit → nearest catalogued well | **75.1 m** |
> | unique catalogued permits within 25 m of an annotated pad | 243 of 872 (27.9%) |
> | median distance, catalogued well → nearest annotated pad | 50.2 m |
>
> So the earlier "pad detections match 521 of 1,069 wells within 25 m" does not
> reproduce, and the "median 26.4 m" figure has been quoted elsewhere as if it
> were DEP positional accuracy. It is not. **Do not cite this table.** The
> AGU abstract (v4) now reports the annotation-based numbers instead.

| Model | Detections | Wells matched (/1069, inflated) | Well recall | Median nearest detection (m) |
|---|---|---|---|---|
| pit_07_maskrcnn | 2979 | 373 | 0.35 | 42.0 |
| pit_08_yolo | 3602 | 397 | 0.37 | 35.1 |
| pad_05_maskrcnn | 3127 | 521 | 0.49 | 26.4 |
| pad_06_yolo | 1291 | 337 | 0.32 | 48.3 |

*(Retained for provenance only. Detection counts are at the old untuned
thresholds, and the denominator is wrong.)*

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
