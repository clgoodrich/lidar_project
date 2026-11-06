# P2 Audit set and training history

**Problem.** A frozen audit set is needed before mining errors or adding negative classes. Existing blocks may already have shaped models, thresholds or decisions. They are not untouched by default.

**Why it matters.** A final test that was used for tuning gives a falsely good result.

**Evidence level produced.** None. It is infrastructure.

**Inputs.** Block files, saved splits (P1), training and calibration scripts, iteration docs.

**Architecture.**
1. `docs/iterations/audit_set_history.md` lists, per block, every model, threshold, calibration, negative-mining and selection step that used it. Include the models that supply context features.
2. Choose audit blocks only from blocks with no use. If too few remain, use a new area.
3. `data/9t/results/splits/audit_blocks_9t.csv` records the frozen audit blocks and a hash.
4. A guard in every trainer that refuses to read audit blocks.
5. Random audit sample for active learning is kept separate and never tuned on.

**Method outline.** Prospective final test blocks are excluded from all later training, calibration, negative mining and model selection. The strongest final evaluation is a new area.

**Acceptance test.** The history document is complete for every audit block and the guard passes in a test.

**Risks and unknowns.** History may be incomplete. Say so in the document.

**Depends on.** P1.

**Executor notes.** Do not view audit labels again after freezing.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Proceed, rescoped.

- Every 9t block trained or validated four of the five CV models. No untouched 9t block exists.
- Define 9t audit blocks as excluded from all new models. They support comparisons between new models. Absolute final claims need a new area.
- List the models that supply context features and every threshold or mining step that used each block.
- A buffer is derived from receptive field and an empirical correlogram, not set at 500 m.

**Downloads and requests.** None

## Review revision 2 (third review, 2026-11-04)
Inventory every use of each 9t block in model selection. Reserve a separate final area for absolute claims.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
