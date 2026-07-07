# WellSight — Programming & Generation Roadmap

*Written 2026-07-06. Scope: the PA orphaned-wells work (+ Permian transfer). The
Barlow/FINESST subproject has its own roadmap at `barlow/docs/ROADMAP.md`. Ordered by
dependency and by cost: cheap/no-GPU work first, training runs second, deployment third
— and nothing in Phase D runs until the user unpauses it.*

**Standing constraints:** 9t-only until the user says otherwise (task #24 explicitly
PAUSED); root-cause fixes in training, not post-hoc filters; thresholds tuned on val,
scored once on frozen test; every ≥100 MB output gitignored in the same change;
LEADERBOARD/iteration docs/analysis_log updated in the same pass as the results they
describe; commit+push after every major change.

**Where we are (2026-07-02 honest re-eval):** recall is solved (0.88–0.98 @IoU.3 across
all four instance models); precision is 3–6% everywhere — models emit 12–47× more
detections than GT instances. Road extraction F1 0.754 (val-tuned, test-frozen). Known-
well cross-ref: best model matches 521 of 1,069 DEP wells within 25 m. The next unit of
progress is precision, not recall.

---

## Phase A — Cheap wins: no GPU, hours not days

**A.1 Val-selected score-threshold sweep** (the lever LEADERBOARD names first). The
current operating points were never tuned (0.3 default; YOLO pit at conf 0.05 by
design). Re-threshold the SAVED `instances.gpkg` outputs — no re-inference needed:
sweep score cutoffs on val, freeze the argmax-F1 threshold, score test once, for all
four models (pit_07, pit_08, pad_05, pad_06).
*Output:* per-model P/R/F1-vs-threshold curves + a new LEADERBOARD block; iteration doc
`threshold_sweep.md`. *Acceptance:* honest deltas — if F1 stays <0.2, say so; the point
is to measure how much of the precision problem is thresholding vs real confusion.

**A.2 False-positive taxonomy.** Take the surviving FPs at the tuned thresholds and
hand-classify a sample (~100/model) in QGIS: what ARE they? (rock outcrops, stream
banks, modern structures, forestry artifacts, duplicate/fragmented detections of true
features…). This is the requirements document for Phase B's hard negatives — the
fix-in-training rule needs to know what to train against.
*Output:* `fp_taxonomy.md` with class counts + example chips; a `fp_review.gpkg` for
QGIS. *Depends:* A.1 (tuned thresholds first, so we classify real FPs, not noise).

**A.3 Duplicate-detection audit.** Precision is partly self-competition: 2,978–3,631
detections against 65 GT implies heavy overlap. Quantify same-model overlap (IoU
between detections) and cross-class overlap (pit-floor vs pit-wall double counts).
If duplicates dominate, the fix is in the model's NMS/head config at TRAINING/inference
config level (allowed), not a bolt-on merge filter.
*Output:* overlap histograms in the A.1 iteration doc.

## Phase B — Precision attack in training (GPU runs, justified by A)

**B.1 Hard-negative datasets.** Convert A.2's taxonomy into explicit negative examples
in the annotation sets — the proven pattern (drainage-as-negative fixed road FPs;
memory: fix-in-training-not-filters). Rebuild pit/pad datasets with the new negatives;
document counts in the dataset manifests.

**B.2 Retrain the champions.** Priority order by cross-ref value: pad Mask R-CNN
(best known-well matcher, worst precision 0.029) → pit Mask R-CNN → YOLOs only if the
Mask R-CNN gains transfer. Same 65/93 frozen test, same 1:1 metric — apples to apples
with the 07-02 tables.
*Acceptance:* precision moves or the run is written up as a negative result with the
FP taxonomy re-run on the new model (did the FP classes shift?).

**B.3 Class design experiments (from BACKLOG, only after B.2 baselines):** confusing-
class additions (e.g., stream-bank scarps as a named negative class for pits), and the
parked architecture items — ConvNeXt/U-Net backbone swap, multitask re-visit — each as
its own iteration doc with a go/no-go against B.2's numbers. Sample-size honesty rule:
74-pit-era overfitting (Mask R-CNN val-loss-up-at-epoch-1) says instance models need
the FULL 426/650 datasets; no small-subset experiments.

## Phase C — Road active-learning loop (task #36, waits on user input)

**C.1 User step (blocking):** correct the 613590 road predictions in QGIS (review
package already built by `_build_road_review_package.py`).
**C.2 Diff engine:** corrections vs predictions → accepted / rejected / added sets;
rejects become hard negatives, adds become positives (chunked ~40 m per the road-model
convention).
**C.3 Retrain** road U-Net (α 0.72 recall-focused config as the base) on 9t + the
correction diff; evaluate on the 9t test blocks AND on a fresh 613590 visual review —
did the specific corrected failure modes disappear?
**C.4 Iterate** until the user's review pass produces < an agreed number of corrections;
each cycle gets an iteration-doc entry (goal/diff-counts/result).

## Phase D — Deployment (PAUSED until user unpauses; listed so the order is ready)

**D.1** 613590 0.5 m derivative stack (SE tile already integrated at 1 m; 0.5 m stack is
the pending piece of task #24).
**D.2** Inference: tuned-threshold champions from B.2 + road model from C.
**D.3** Candidate-well fusion: pits + pads + road-proximity into scored candidate
locations, each carrying confidence, method, and distance-to-nearest-known-well —
the CLAUDE.md reporting contract (never "confirmed", always "candidate").
**D.4** Known-well cross-ref re-run (`_compare_known_wells.py`) + QC pass (CRS,
density gaps, cluster alerts) before ANY map/export leaves the repo.
**D.5** Rolling expansion to the neighboring blocks (622594/622599…) only after 613590
review converges.

## Phase E — Permian transfer (parallel-friendly, cheap until labeling)

**E.1** Zero-shot inventory: PA-trained pad/pit models on all four permian_* grids
(pad U-Net on permian_01 already ran — write up what it did/didn't see if not already
in an iteration doc).
**E.2** Ground-truth eval vs TX RRC orphan wells + Ramachandran/Stanford pads:
recall-at-distance tables, honest domain-gap statement.
**E.3** Decision gate: fine-tune with a small Permian label set vs train-from-scratch —
only after E.2 quantifies the gap. Labeling budget comes from the same annotation
workflow as WPA (label_grids/ convention, gpkg-per-grid naming).

## Phase F — Infrastructure & documentation debt (do opportunistically, not as a block)

**F.1** `STRUCTURE.md` refresh: it still names `notebooks/wellsight/` as active (it's
`wellsight_v2/`) and describes a blanket `data/derivatives/**` gitignore that
contradicts the targeted-rules policy — bring it in line with README/CLAUDE.md.
**F.2** Log hygiene: adopt targeted `.gitignore` rules or a `logs/` convention for the
untracked `_*.log` files accumulating at repo root/label_grids (currently 10+ untracked
logs in `git status`); decide keep/ignore per file with the user.
**F.3** Root-level images (`distorted_river.jpg`, `stream_bottom.jpg`): still awaiting
the user's verdict — track, move, or delete (user decision, standing item).
**F.4** Test suite: add regression tests for `per_instance_metrics` (greedy 1:1 +
precision) and the road-extraction eval harness — the two pieces of measurement code
every future claim depends on.
**F.5** Publication thread: `docs/publication/` methodology draft refresh once B/C
land — the honest-metrics story (recall solved → precision engineering) is itself a
paper-shaped narrative.

## Dependency spine (one line)

A.1 → A.2/A.3 → B.1 → B.2 → B.3; C.1 (user) → C.2 → C.3 → C.4; D.* frozen until
unpaused, then D.1→D.5 consuming B/C champions; E.1→E.2→E.3 anytime; F.* fills gaps
between GPU runs. Nothing trains before A says what to train against.
