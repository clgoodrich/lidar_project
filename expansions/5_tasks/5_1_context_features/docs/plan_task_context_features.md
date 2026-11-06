# 5.1 Context features (second-stage model)

**Problem.** The pit and pad models look at one patch at a time. Roads, pads and nearby pits give context that could help rank candidates. How much the model already uses context, and how much more it would gain, is unknown.

**Why it matters.** It could raise precision without new data.

**Evidence level produced.** (a).

**Inputs.** Out-of-fold probability rasters for pit, pad and road models. Checkpoint and split inventory (see P1). Missing road out-of-fold models would mean training new ones.

**Architecture.**
1. Context-reliance test `_context_reliance_pits_9t.py`. Edit the DEM around a pit (remove the pad and road context, and add sham edits), recompute every derivative from the edited DEM, and rescore. Include realistic terrain backgrounds and sample all pits, not only detected ones. Writes `data/9t/results/context/context_reliance_paired_9t.csv`.
2. Inventory `docs/iterations/context_upstream_inventory.md` listing every upstream checkpoint, its fold, and the split it used.
3. Stage-2 features `_context_stage2_9t.py`. Build features from out-of-fold maps (distance to road, pad score nearby, pit count nearby). Every upstream model used for outer fold k must have excluded fold k.
4. Stage-2 learner (gradient boosting or logistic). Evaluated by nested spatial folds.

**Method outline.** Report paired changes in score and rank. No half-score decision rule. Use ranking and recall at fixed K.

**Acceptance test.** Leakage audit passes. Stage-2 gain with a block-bootstrap interval for the difference.

**Risks and unknowns.** Eight hours is optimistic. Ordinary out-of-fold rasters alone do not guarantee leakage-free stacking.

**Depends on.** P1, P2.

**Executor notes.** Verify the road checkpoints before anything else.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign.

- Pit and pad folds balance on different counts, so existing checkpoints cannot be stacked. Assign one block-fold scheme to pit, pad and road and retrain upstream models. Every upstream model feeding outer fold k must exclude fold k.
- Budget runtime from measured epoch time. Backlog notes epoch time was under-reported 1.8 times.
- Annotation context bias. Context can raise agreement with how annotators searched without raising well discovery.
- Add sham edits, realistic backgrounds, derivatives recomputed from the edited DEM and all-pit sampling to the reliance test. No half-score rule.

**Downloads and requests.** None.

## Review revision 2 (third review, 2026-11-04)
One threshold δ_gain, based on downstream value, serves both success and failure. Specify common folds and all cross-fitting before retraining.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
