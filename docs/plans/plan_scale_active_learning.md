# 7.2 Active learning

**Problem.** Labelling is the bottleneck. Choosing which candidates to label next may cut effort.

**Why it matters.** It stretches scarce reviewer time.

**Evidence level produced.** (a). It labels features, not wells.

**Inputs.** Candidate pool, a reviewer interface (the QGIS correction package pattern exists), and an audit set from P2.

**Architecture.**
1. `_active_select.py` ranks unlabelled candidates by uncertainty or expected gain and writes batches to `data/<area>/results/active/batch_<n>.gpkg`.
2. A random audit sample kept separate and never used to tune.
3. Retrain on the diff after each batch, as in the road correction loop.
4. Comparison at equal review effort against random selection.
5. Validation data for stopping. The audit set is checked once.

**Method outline.** Distinguish feature labelling from well confirmation. Repeated checks of the audit set make it a tuning set, so do not do that.

**Acceptance test.** Learning curves for active and random selection at equal effort.

**Risks and unknowns.** Reviewer availability.

**Depends on.** P1, P2.

**Executor notes.** Never peek at the final audit set during the loop.
