# 6.3 Negative classes (confusers)

**Problem.** High-scoring detections include charcoal hearths, quarries, roads and other features that are not wells. Without labelled confusers the model cannot learn the difference.

**Why it matters.** It targets false positives at the root, in training, instead of with post-hoc filters.

**Evidence level produced.** (a) with class labels.

**Inputs.** Detections at the frozen cutoff. `docs/iterations/confuser_codebook.md` (draft written). The existing review package builder is a QGIS correction package with default "keep". It is not the blinded multi-class sheet needed here.

**Architecture.**
1. Sample builder `_confuser_sample.py` stratifies by score band and records inclusion probabilities. Writes `data/9t/results/confusers/confuser_sample_9t.csv`.
2. Contact-sheet builder `_confuser_sheets.py` makes neutral sheets with hillshade, slope and relief, no model score, no record. Output in `data/9t/results/confusers/sheets/`.
3. Label collection by two reviewers, then adjudication. Output `confuser_labels_9t.csv`.
4. Retraining with the new classes as negatives, with balanced sampling and random-negative controls.
5. A frozen audit subset from P2.

**Method outline.** Unmatched is not negative. Keep "possible well" and "uncertain". Evaluate feature recall as well as confuser reduction. Kappa alone is not the acceptance criterion.

**Acceptance test.** Confuser false positives fall with feature recall loss within the preregistered margin. One failed run does not retire the idea.

**Risks and unknowns.** Review time is about 2 hours per 20 candidates per reviewer.

**Depends on.** P1, P2, reviewers.

**Executor notes.** Do not mine errors from the audit set.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign, then pilot.

- Pooled blind labelling. Retrain baseline, confuser-negative and equal-count random-negative arms on the same non-audit blocks, at least 3 seeds each. Pool every arm's top-K audit detections, deduplicate, label once blind to arm, then score each arm.
- Define target morphology without model score or oil-field context. Keep possible-well and uncertain classes. Track what each arm suppresses.
- Pilot the codebook and measure real review throughput. The 30 reviewer-hours figure is an estimate.
- One failed run does not retire the idea.

**Downloads and requests.** R6.
