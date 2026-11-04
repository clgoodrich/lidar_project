# Framework 7.2. Active learning

**Tier B.**
**Evidence level.** (a). It labels features, not wells.
**Depends on.** P1, P2, reviewers, 6.3 labels.

## 1. Problem and objective
Labelling is the bottleneck. Choosing which candidates to label next may cut effort. Candidate-only sampling cannot find positives outside the proposal pool, and equal label count is not equal effort.

**Question.** Does uncertainty-based selection reach a target recall at K with fewer reviewer-hours than random selection?

**Hypothesis.** Active selection improves recall at K per reviewer-hour over random selection.

## 2. Scope
In. Selection loop, retraining on corrections, comparison at equal effort, random-area discovery, stopping rule.
Out. Final audit set tuning.

## 3. Definitions
- **Effort.** Reviewer-minutes (measured), not label count.
- **Pool.** Candidates in non-audit blocks. Plus random-area discovery windows to find positives the model misses.
- **Stopping set.** A validation set used only to stop. Separate from the final audit set, which is checked once.
- **Round.** Select batch, label, retrain, evaluate on the stopping set.

## 4. Inputs
Candidate layers, review package pattern (`s6_review/_build_pit_review_package.py`, `_pit_corrections_diff.py`, road loop `_build_road_review_package.py`), isolated trainer, audit sets.

## 5. Prerequisites and decisions
Reviewers. Batch size (default 60 candidates). Selection score (entropy of the probability, or margin to the cutoff). Stopping rule.

## 6. Procedure
1. **Setup.** Split non-audit blocks into pool and stopping blocks (P2 guard). Record the selection seed.
2. **Round 0.** Train on the existing labels with the isolated trainer.
3. **Selection.** Script `s6_review/_active_select_9t.py` (new). Score pool candidates and select a batch by uncertainty plus a diversity rule (no two within 50 m). In every round add 20% random candidates and one random-area window of 0.25 km² for discovery (reviewers mark every feature in the window).
4. **Labelling.** Review package with neutral sheets (6.3 S2). Record minutes per batch.
5. **Retrain** on the diff (corrections become training signal, rejects become hard negatives only if adjudicated confusers).
6. **Evaluate** each round on the stopping set at K = 40 per km². Plot recall versus cumulative reviewer-hours for active and random arms.
7. **Stop** when the stopping-set gain falls under a preregistered level for two rounds. Score the final audit set once.

## 7. Statistical analysis plan
Primary. Area under the recall-versus-effort curve, active minus random, block bootstrap over stopping blocks and repeated random runs (at least 3). Training variance across seeds is reported separately.

## 8. Quality control
No peeking at the audit set. Effort measured, not assumed. Random-area discovery logged.

## 9. Gates
Success when the interval of the area-under-curve difference is above 0. Failure when it is below. Inconclusive otherwise.

## 10. Deliverables
Scripts, `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\active\`, `docs\iterations\active_learning_9t.md`.

## 11. Failure modes
Selection bias. Reviewer drift. Small pools. Discovery windows too few to catch missed positives.

## 12. Resources
Reviewer time dominates. GPU per round (retrain).

## 13. Handoff
Reviewers.

## 14. Documentation updates
Doc, `LEADERBOARD.md`, `analysis_log.md`, master plan.
