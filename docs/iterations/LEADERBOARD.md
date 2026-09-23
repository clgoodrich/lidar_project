# 9t Iteration Leaderboard

Per-task metrics across iterations on the 9t tile.

> **UPDATE 2026-09-17 — the pit and pad CV5 tables are current again.** Both
> `_pit_unet_cv5.py` and `_pad_unet_cv5.py` have been re-run on ann712; see
> "Pits, 5-fold cross-validated — all 712 pits" and "Pads, 5-fold
> cross-validated — all 995 pads". Every OTHER pit and pad row on this page is
> still scored against ann527 or ann426 and the banner below still applies to it.
>
> **STALE — every pit and pad number below (2026-09-04).** The 9t annotation
> grew from 527 to 712 pit floors and the spatial-block train/val/test split was
> reassigned to match (`_build_pit_dataset_v2.py --force`). The pad and road
> manifests were rebuilt from that split. No checkpoint on this page was trained
> against it, so no pit or pad row here is a held-out number any more.
>
> The checkpoints that produced these rows are preserved at
> `data/9t/models/_retired/pit_09_unet_cv5_ann527_2026-09-04/` and
> `data/9t/models/_retired/pad_07_unet_cv5_ann527_2026-09-04/`, and the split
> they were scored against at
> `qgis/annotations/_history/_backup_pit_ann527_2026-09-04/`.
>
> Road rows are unaffected: the road models train on 1 m data from a separate
> manifest. Do not cite a pit or pad row until the ann712 retrain lands.

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
> Corrected in `notebooks/wellsight_v2/s5_eval/_reeval_instance_precision_9t.py`:
> predictions clipped to the scored extent, class-matched, thresholds selected on
> **val** and test scored **once** frozen. Source of truth is
> `data/derivatives/eval_9t_instance_precision/_reeval_9t.json`.
>
> **Real precision is 0.54–0.69 across all six rows, not 0.03–0.07.** Recall also
> moves, because the thresholds moved. The conclusion "detection volume is the
> limiting problem" was drawn from the bug and is withdrawn.

## Pits (65 test instances) — corrected 2026-07-27

**STALE (2026-09-04)** — scored against the ann527 split, superseded. See the banner at the top.


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

### Threshold-free ranking, pit and pad CV5, ann712 — 2026-09-23

**Use this table to compare models.** It needs no cutoff. Candidates are each fold's blobs at a proposal cutoff chosen for recall alone, leave-one-fold-out (on the other four folds' held-out blocks; inner val is not reproducible, see the write-up). They are ranked by score. AP is the area under the held-out precision-recall curve (VOC envelope). Brackets are the 95% block bootstrap. Full write-up: `docs/iterations/cv5_threshold_free_pr_and_calibration_pit_pad_9t.md`.

| Model | ranked AP @IoU 0.3 | per-fold sd | ranked AP @IoU 0.5 | recall ceiling @0.3 | recall at 10 FP/km² @0.3 |
|---|---|---|---|---|---|
| pit, vendor ground (`pit/unet_cv5`) | **0.818** [0.778–0.857] | 0.051 | 0.637 [0.580–0.697] | 0.946 | 0.903 |
| pit, SMRF ground (`pit/unet_cv5_smrf`) | **0.818** [0.780–0.856] | 0.038 | 0.495 [0.430–0.564] | 0.934 | 0.869 |
| pad, vendor ground (`pad/unet_cv5`) | **0.745** [0.703–0.789] | 0.035 | 0.582 [0.532–0.634] | 0.900 | 0.774 |

Numbers come from `data/9t/results/operating_point/pr_ap_froc_calibration_summary_cv5_pit_pitsmrf_pad_9t.json`. Precision counts unannotated real features as false, so every AP here is a lower bound. Do not compare these with the pixel-cutoff-sweep APs in the same JSON. Those mix outlining with ranking.

SMRF against vendor, paired: no difference at IoU 0.3. At IoU 0.5, SMRF is 0.143 lower, with all five folds negative (t −3.33).

Operating points for these models, and how today's pixel cutoffs compare with ranked cuts at the same effort: `docs/iterations/operating_point_policy_sweep_pit_pad_9t.md`.

### Pits, 5-fold cross-validated — all 712 pits, ann712, 2026-09-17

**Current.** `_pit_unet_cv5.py` re-run on the ann712 split, 57.3 min, five folds,
502 rims scored. Same architecture, loss, channels and schedule as the ann426 run
below — only the annotation and the split changed.

| Selection | thr chosen per fold | R@0.3 | P@0.3 | R@0.5 | containment |
|---|---|---|---|---|---|
| by F1 | 0.45, 0.50, 0.55, 0.60, 0.60 | **0.861** (sd 0.045) | 0.686 | 0.700 | 0.914 |
| by F2 | 0.35, 0.40, 0.40, 0.45, 0.45 | **0.928** (sd 0.023) | 0.633 | 0.823 | 0.956 |

Against the ann527 run it superseded (F1 rule): recall 0.890 → 0.861, precision
0.637 → **0.686**, containment 0.936 → 0.914. Under F2: recall 0.938 → 0.928,
precision 0.598 → **0.633**.

**Precision rose on every rule while recall moved slightly down.** The likely
reading is that some of what the ann527 model was charged for as false positives
were real pit floors that had not been annotated yet, and ann712 labelled them.
That is consistent with the direction and size of both moves but is not proved
here — confirming it means checking ann527 false positives against the 185 floors
ann712 added. Recorded as a hypothesis, not a finding.

**The pads did not reproduce it.** Pooled pad precision was flat, 0.606 -> 0.597.
If the mechanism were general, both tasks should have moved together. Either it
is pit-specific, or it is not the mechanism. See the pad section.

Per-fold spread also tightened, sd 0.088 → 0.045 under F1, which is what more
annotation should do.

Outputs: `data/9t/models/pit/unet_cv5/pit_cv5_per_fold_9t.csv`,
`pit_cv5_recovery_curve_9t.csv`, `pit_cv5_fold_assignment_9t.csv`.
Log: `data/9t/models/pit/unet_cv5/_pit_cv5_ann712_train.log`.

#### Same model on SMRF-recovered ground — no improvement (2026-09-19)

The row above is trained on the **vendor** ground surface, which withholds every
at-ground return beyond 18° off nadir. This arm rebuilds the 7-band stack from
ground we classify ourselves with SMRF, on the vendor stack's exact grid, and
retrains with the same labels, folds, inner-validation fold, architecture and
schedule. **Only the ground classification differs.**

| Selection | metric | vendor | SMRF | delta | folds better | paired t |
|---|---|---|---|---|---|---|
| by F1 | R@0.3 | 0.861 | 0.893 | +0.032 | 3/5 | +0.83 |
| by F1 | P@0.3 | 0.690 | 0.680 | −0.009 | 1/5 | −0.42 |
| by F1 | containment | 0.914 | 0.934 | +0.020 | 4/5 | +0.81 |
| by F2 | R@0.3 | 0.928 | 0.915 | −0.014 | 1/5 | −1.19 |
| by F2 | R@0.5 | 0.823 | 0.742 | −0.082 | 1/5 | −1.91 |
| by F2 | containment | 0.956 | 0.952 | −0.004 | 2/5 | −0.39 |

**No |t| reaches 2, and the two objectives disagree in sign on recall.** That is
a null. Recovering the withheld ground does not improve pit detection, and the
largest single effect is SMRF being slightly *worse* at IoU 0.5.

Why: only 26.8% of 1 m void cells are wide-angle-only; 68.1% hold near-nadir
returns and still have no ground because the canopy occluded it. SMRF closes
about a quarter of the holes. **Do not reprocess the remaining 175 map squares.**

Write-up: `docs/iterations/smrf_ground_retrain_pit_cv5.md`.
Outputs: `data/9t/models/pit/unet_cv5_smrf/pit_cv5_per_fold_9t.csv`.

### Pits, 5-fold cross-validated — all 426 pits, 2026-07-27

**SUPERSEDED by the ann712 table above.** Kept for the trend.

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

**STALE (2026-09-04)** — scored against the ann527 split, superseded. See the banner at the top.


| Iteration | Approach | thr (val) | val F1 | R@0.3 | P@0.3 | F1@0.3 |
|---|---|---|---|---|---|---|
| plat_unet (instance metric†) | UNet semantic, blobs→instances | 0.50 | 0.667 | **0.882** | 0.547 | 0.675 |
| pad_05_maskrcnn (7-band) | Mask R-CNN R50-FPN v2 | 0.95 | 0.675 | 0.828 | 0.538 | 0.653 |
| **pad_06_yolo** | YOLOv8s-seg | 0.80 | 0.699 | 0.667 | **0.689** | **0.678** |
| plat_unet (native localized‡) | UNet semantic binary | — | — | 0.78‡ | — | — |

### Pads, 5-fold cross-validated — all 995 pads, ann712, 2026-09-17

**Current.** `_pad_unet_cv5.py` re-run on the ann712 split, 159.9 min, five folds,
650 in-tile pads scored.

| Selection | thr chosen per fold | R@0.3 | P@0.3 | R@0.5 | locate |
|---|---|---|---|---|---|
| by F1 | 0.55, 0.55, 0.55, 0.60, 0.65 | **0.888** (sd 0.051) | 0.597 | 0.749 | 0.923 |
| by F2 | 0.50, 0.55, 0.55, 0.55, 0.55 | **0.912** (sd 0.022) | 0.587 | 0.774 | 0.917 |

**The pits' precision gain did NOT reproduce here.** Against the 650-pad run
below, under F1: recall 0.917 -> 0.888, precision 0.606 -> 0.597, locate
0.928 -> 0.923. Under F2: recall 0.920 -> 0.912, precision 0.591 -> 0.587.
Recall down slightly, precision flat.

Fold 0 alone had shown precision up (0.655), which is why an early reading of
this run looked like the pit pattern. Pooled over five folds it does not. The
"unannotated true positives" hypothesis recorded in the pit section is therefore
supported by the pits only, not by both tasks. Treat it as weaker than it looked.

Per-fold recall spread widened under F1, sd 0.021 -> 0.051, the opposite of what
the pits did.

Outputs: `data/9t/models/pad/unet_cv5/pad_cv5_per_fold_9t.csv`,
`pad_cv5_recovery_curve_9t.csv`, `pad_cv5_fold_assignment_9t.csv`.
Log: `data/9t/models/pad/unet_cv5/_pad_cv5_ann712_train.log`.

**Count note.** The pad manifest has 995 rows. 650 carry a `block_id` and are
in-tile; 345 have none and fall outside 9t. Of the 650 in-tile, 66 sit in blocks
the greedy fill left unassigned, so train/val/test is 401/69/114 = 584. CV5
recomputes folds from blocks and scores all 650. Pits have no unassigned rows:
503 in-tile, 209 outside.

### Pads, 5-fold cross-validated — all 650 pads, 2026-07-28

**SUPERSEDED by the ann712 table above.** Kept for the trend.

Same treatment as the pits. Parameters copied verbatim from `_plat_unet.py`, so
this measures the split and not a new model.

| Selection | thr chosen per fold | R@0.3 | P@0.3 | R@0.5 | locate |
|---|---|---|---|---|---|
| by F1 | 0.55, 0.60, 0.55, 0.60, 0.65 | **0.917** (sd 0.021) | 0.606 | 0.782 | 0.928 |
| by F2 | 0.55, 0.50, 0.55, 0.55, 0.55 | **0.920** (sd 0.025) | 0.591 | 0.788 | 0.909 |

**The single-split 0.882 / 0.547 was pessimistic**, same direction as the pits
but smaller in magnitude.

**Pads are the more stable model.** Per-fold recall sd is 0.021 against 0.088
for pits under the same rule. Pads have a median annotated area of 1,343 m²
against ~26 m² for a pit floor, so boundary disagreement barely moves a pad's
IoU and moves a pit's a lot.

F1 and F2 pooled recall differ by 0.003, and three of five folds selected the
same threshold under both. The operating point does not depend on which
objective you argue for.

`locate` is the pad analogue of pit rim-containment. Pads have no
inside/outside annotation pair, so it asks whether the annotated pad contains at
least one predicted centroid.

Full write-up: [[pad_unet_cv5_9t]].

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

### Roads on 613590 — out-of-domain, real ground truth (2026-08-06)

Full write-up in [[road_613590_out_of_domain_test]]. **This is the first road table on
this page scored against a tile no road model ever trained on.**

> **Quote only the `added` column.** The 613590 ground truth splits by `src`.
> `613590_review_r2` (138.23 km) is a previous road model's own output that the
> annotator vetted, and **every model below scores 0.96–1.00 completeness on it** —
> the subset cannot rank anything. `613590_added_r2` (48.87 km) was drawn from
> scratch on roads that model missed, so it is the only informative half, and it is
> adversarially hard by construction. Correctness is a **lower bound**: `roads.shp`
> covers 613590 only where the annotator worked.

Metric = Wiedemann et al. 1998 completeness / correctness / quality, buffer 5 m,
~40 m chunks, `correctness_px` measured on pixels. Best-quality threshold per model.

| Model | Trained on 613590? | thr | added completeness | correctness_px | quality |
|---|---|---|---|---|---|
| corrected_r2 | **YES — saw these lines** | 0.70 | 0.919 | 0.842 | 0.784 |
| **sweep_orient** | no | 0.40 | 0.811 | 0.816 | **0.686** |
| **sweep_ENSEMBLE_mean** | no | 0.30 | 0.820 | 0.804 | 0.684 |
| **sweep_ENSEMBLE_max** | no | 0.70 | 0.808 | 0.812 | 0.681 |
| sweep_boundary | no | 0.50 | 0.777 | 0.837 | 0.674 |
| sweep_alpha078 | no | 0.50 | 0.782 | 0.829 | 0.674 |
| corrected_r1 | **YES — corridor labels** | 0.50 | 0.788 | 0.822 | 0.674 |
| sweep_cldice_sg3 | no | 0.50 | 0.777 | 0.825 | 0.667 |
| **road_unet_1m_recall_relabeled20260806** | no | 0.40 | 0.788 | 0.802 | 0.660 |
| sweep_cldice | no | 0.30 | 0.761 | 0.827 | 0.657 |
| road_unet_1m_recall (Jun 14) | no | 0.30 | 0.691 | 0.784 | 0.581 |
| sweep_cldice_mkf | no | 0.70 | 0.640 | 0.615 | 0.457 |

**The label fix, isolated.** Same recipe, same hyperparameters, same 9t-only data —
only the label raster changed (+19 km of previously-unlabelled road, mostly faint):

| | thr | added completeness | correctness_px | quality | mean P(road) on added |
|---|---|---|---|---|---|
| road_unet_1m_recall (Jun 14, stale labels) | 0.50 | 0.613 | 0.835 | 0.547 | 0.432 |
| road_unet_1m_recall_relabeled20260806 | 0.50 | **0.759** | 0.828 | **0.655** | **0.549** |

+0.146 completeness at zero correctness cost. Recovering mislabelled road bought more
than any architecture change in the 2026-07 sweep. **Every sweep variant above was
trained on the same stale labels** and should be re-run.

> **That "more than any architecture change" claim was tested directly on
> 2026-09-19 and it holds for pit, not for pad.** See the section below.

## Architecture comparison, 1 m — four networks on identical folds (2026-09-19)

Same folds, same 7 channels, same FocalCE, same 40 epochs / batch 8 / lr 1e-3.
Each rung of the ladder changes exactly one thing. The score is **validation IoU
of the target class at each fold's best epoch**, with the held-out fold excluded
from its own epoch selection (inner val is fold `(k+1) % 5`).

**These are segmentation IoU at 1 m. They are NOT the held-out detection recall
used everywhere else on this page, which is computed at 0.5 m. Do not compare a
number in this table to a number in any other table here.**

| target | architecture | params | folds | IoU | sd | min–max |
|---|---|---|---|---|---|---|
| pit | U-Net (plain) | 7.8 M | 5 | 0.559 | 0.020 | 0.529–0.589 |
| pit | ResNet-34, scratch | 24.4 M | 5 | 0.528 | 0.025 | 0.491–0.560 |
| pit | ResNet-34, ImageNet | 24.4 M | 5 | 0.548 | 0.015 | 0.524–0.565 |
| pit | U-Net++, R34 ImageNet | 26.1 M | 5 | **0.561** | 0.020 | 0.533–0.590 |
| pad | U-Net (plain) | 7.8 M | 5 | 0.555 | 0.020 | 0.524–0.584 |
| pad | ResNet-34, scratch | 24.4 M | 5 | 0.567 | 0.028 | 0.528–0.604 |
| pad | ResNet-34, ImageNet | 24.4 M | 5 | 0.599 | 0.018 | 0.576–0.627 |
| pad | U-Net++, R34 ImageNet | 26.1 M | 5 | **0.608** | 0.019 | 0.587–0.636 |

End to end, plain U-Net → full stack: **pit +0.002 (+0.1 sd, within noise)**,
**pad +0.054 (+1.9 sd, suggestive)**. No individual rung clears its own noise on
either target.

**Pit: architecture is not the constraint.** 3.3× the parameters and ImageNet
initialisation buy 0.002 IoU against a fold sd of 0.020. **Pad: there is
something here** — every `unetpp_r34_imagenet` fold beats every plain U-Net fold
but one, which is worth more than the sd arithmetic alone suggests. It needs more
seeds before it is a finding.

`roaddrain` has **no row**: that arm ran 1 of 40 epochs on one fold and stopped.

Write-up: `docs/iterations/arch_compare_1m_four_architectures.md`.
Numbers: `data/9t/results/arch_compare_1m/arch_compare_summary_9t_1m.csv`.

Max recovery: `sweep_ENSEMBLE_max` at thr 0.30 → **0.909** completeness / 0.651 correctness.

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
