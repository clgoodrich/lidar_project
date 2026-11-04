# Framework 6.3. Confuser classes and negative-class training

**Tier A.** Addresses false positives in training instead of by filters.
**Evidence level.** (a) with class labels.
**Depends on.** P1 (isolated trainer), P2 (audit set), 3.0 scorer, reviewers.
**Blocks.** None, but informs 5.1 and 7.2.

## 1. Problem and objective
High-scoring detections include charcoal hearths, quarries, road cuts and other features. Without labelled confusers the model cannot learn the difference. Unmatched is not negative, because unmatched candidates may be real undocumented wells.

**Question.** Does training with adjudicated confuser negatives reduce labelled confuser detections at K = 40 per km² without losing drawn-feature recall, compared with an equal-count random-negative arm?

**Hypotheses.** H1a. Confuser detections per km² at K fall by at least a useful amount. H1b. Drawn-feature recall loss is within the margin Δ.

## 2. Scope
In. Codebook pilot, sampling, blind labelling, retraining in three arms with several seeds, pooled blind scoring.
Out. Treating unmatched candidates as negatives automatically. Well identity.

## 3. Definitions
- **Codebook.** `docs/iterations/confuser_codebook.md` classes P (well pit or pad feature), C (charcoal hearth or mill platform), Q (quarry or borrow pit), K (coal or mine feature), R (road cut, landing, log deck), H (hydrology), B (building or foundation), X (other known cause), U (uncertain). The positive class there uses access traces and oil-field setting. That lets context features raise agreement with how annotators searched. Redefine P by morphology alone, without model score, and keep "possible well" and "uncertain".
- **Arms.** Baseline, confuser negatives, random negatives (same count and same sampling procedure as confuser negatives).
- **Seeds.** At least 3 per arm.
- **Pooled labels.** The top-K detections of every arm in the audit blocks, deduplicated, labelled once blind to arm.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Candidates at 0.50 | `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg` | held |
| Review package builder (a QGIS correction package with default "keep") | `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py` | held, not the blinded multi-class sheet |
| Corrections diff | `s6_review/_pit_corrections_diff.py` | held |
| Isolated trainers | P1 | future |
| Audit blocks | P2 | future |
| Reviewers | user | not named |

## 5. Prerequisites and decisions
Two reviewers and an adjudicator. Margin Δ for recall loss. The codebook pilot's measured throughput sets the labelling budget.

## 6. Procedure
**S0. Codebook pilot.**
- Reviewer pair labels 40 candidates sampled across score bands. Measure minutes per candidate, share U, agreement (percent and kappa, kappa is not an acceptance criterion), and which classes need external evidence. Revise the codebook. Output `docs/iterations/confuser_codebook_pilot.md`. Replace the 30 reviewer-hour estimate with measured time.

**S1. Sampling.**
- Script `notebooks/wellsight_v2/s6_review/_confuser_sample_9t.py` (new). Draw candidates at the frozen cutoff from non-audit blocks, stratified by score band (five equal-count bands). Record inclusion probabilities. Output `data/9t/results/confusers/confuser_sample_9t.csv`.

**S2. Contact sheets.**
- Script `notebooks/wellsight_v2/s6_review/_confuser_sheets_9t.py` (new). One panel per candidate showing hillshade, slope, local relief and an aerial chip if available. No model score, no DEP record, no other reviewer's label. Fixed scale and orientation. Output `data/9t/results/confusers/sheets/*.png` and a label-entry file `confuser_labels_9t.csv` (candidate id, reviewer, class, confidence).

**S3. Blind labelling and adjudication.**
- Two reviewers independently. Adjudication by a third look. Remaining disagreements stay U. Freeze an audit subset before any error mining.

**S4. Training arms.**
- Copy the isolated pit trainer. Add a class or an ignore-mask mechanism for confuser polygons. Arms trained on identical non-audit blocks and identical splits.
  - Confuser arm. Adjudicated confuser polygons (classes C, Q, K, R, H, B, X) as an extra negative class, balanced sampling.
  - Random-negative arm. The same number of random negative windows from the same blocks.
  - Baseline. No extra negatives.
- Seeds. 3 per arm minimum (child seed = master + 1000 times fold + seed index).
- Output `data/9t/models/pit/unet_confuser_cv5/<arm>/seed<s>/fold<k>/`. Add `.gitignore` rules.

**S5. Pooled blind scoring.**
- For each arm and seed, take top-K detections in audit blocks. Pool across arms, deduplicate by centroid within 5 m. Label each pooled detection once, blind to arm (reviewers use the S2 sheets). Score each arm against the pooled labels.
- Metrics per arm. (i) Labelled confuser detections per km² at K. (ii) Drawn-feature recall at K. (iii) Number of P-labelled and U-labelled detections suppressed compared with baseline (to catch suppression of possible wells).

**S6. Report.**
- Figure. Confuser detections per km² and recall at K by arm, with seed spread (dots) and bootstrap interval. Blue baseline, orange confuser arm, grey random.

## 7. Statistical analysis plan
- Primary 1. Confuser-arm minus random-arm labelled-confuser detections per km² at K, block bootstrap over audit blocks, seed variation shown separately.
- Primary 2. Confuser-arm minus baseline drawn-feature recall at K, non-inferiority against Δ.
- Secondary. Suppression of U and P labels. Calibration. Retention of historic positives (4.6) if available.
- Seeds are not independent landscapes. The block is the resampling unit. Seeds describe training variance.

## 8. Quality control
- No audit block in any training list (guard).
- Labellers blind to arm and score. Log it.
- A random 10% re-labelled by another reviewer.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Reduction lower bound above 0 and recall-loss lower bound above minus Δ | Adopt the confuser arm for the next model |
| Failure | Reduction upper bound below 0, or recall-loss upper bound below minus Δ | Keep the finding. One failed run does not retire the idea |
| Inconclusive | Otherwise, including seed spread larger than the effect | Report and add seeds |

## 10. Deliverables
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s6_review\` and `s3_train\_pit_unet_confuser_cv5.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\confusers\`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\confuser_codebook_pilot.md`, `confuser_retrain_9t.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| New detections after retraining are unlabelled | Pooled blind labelling of all arms' detections |
| Seed variance exceeds the effect | At least 3 seeds. Report spread. Add seeds if inconclusive |
| Charcoal hearth class holds early well platforms | Track P and U suppression. Keep uncertain |
| Labels come from lidar morphology only | Add historical evidence (4.6) and field checks where available |
| Reviewer fatigue and drift | Measured throughput. Batches of 20. Calibration set repeated |

## 12. Resources
Pilot 6 reviewer-hours. Labelling 2 hours per 20 candidates per reviewer (pilot to confirm). Pooled labelling about 40 hours total for two reviewers. GPU 3 arms by 3 seeds by 5 folds, hours per run measured. Disk several GB.

## 13. Handoff and open questions
- Reviewer names. Margin Δ. Whether to treat K labels as classes or an ignore mask.

## 14. Documentation updates
Codebook revision, `confuser_retrain_9t.md`, `LEADERBOARD.md`, `analysis_log.md`, master plan.
