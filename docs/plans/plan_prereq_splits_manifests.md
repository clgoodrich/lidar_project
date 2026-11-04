# P1 Reproducible splits and manifests

**Problem.** Both cross-validation trainers rebuild their splits at run time from a seed, and rows without a block id carry NaN. In a saved check, 209 of 712 pit rows and 345 of 995 pad rows had no block. The trainers never score them. The set difference over block ids also carries a NaN id.

**Why it matters.** Every transfer, context and retraining plan depends on a split that can be reproduced and audited.

**Evidence level produced.** None. It is infrastructure.

**Inputs.** `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py`, `_pad_unet_cv5.py`, the manifests in `data/9t/derived/05/`.

**Architecture.**
1. Fix the NaN handling in both trainers (drop rows with no block before building folds, and say how many).
2. Save explicit split files. A script `_save_cv_split_manifests_9t.py` exists and writes `data/9t/results/splits/`. Make the trainers read these files instead of rebuilding.
3. Spatial check. Held-out and other-fold features had a minimum separation of 6.8 m in two pit folds (3 and 4). Add a buffered option and a check that fails above a stated limit.
4. A hash of each split file recorded in the run provenance.

**Method outline.** One source of truth for splits. Trainers read, never rebuild.

**Acceptance test.** Two runs of any fold give identical train, val and held-out block lists. The check reports separation per fold.

**Risks and unknowns.** Changing the trainers may change reported numbers. Re-run the headline numbers and record any difference.

**Depends on.** None. Do first.

**Executor notes.** Do not retrain until this is done.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Proceed, rescoped.

- Root cause is NaN block ids landing at a changing position in `sorted(set(block_ids) - held)`. In four fresh processes the inner validation list changed in folds 0, 2 and 4. Dropping the NaN before the shuffle fixes future runs.
- The saved train and validation roles are not the trained ones. Label every split historical held-out (valid), historical inner (unrecoverable) or future (immutable file).
- Recover what the checkpoints stored (`checkpoint_extra["held_out_blocks"]`) and the training-log counts. Do not re-derive the inner split.
- Specify an isolated pit trainer from `_pad_unet_iso_cv5.py` (whole-window rejection against held-out and inner-validation blocks, fold-local normalisation).
- The 209 pit rows and 345 pad rows with no block id are annotations off the tile.
- Verify the Warren LAZ header CRS here (a reviewer reports NAD83(2011) UTM 17N plus NAVD88, against an older note).
- Acceptance. Identical block lists across 3 fresh processes. Hashes recorded.

**Downloads and requests.** None

## Review revision 2 (third review, 2026-11-04)
Historical inner roles stay unknown. Identical block lists alone do not certify no leakage. Add a window-level exclusion test and a check that every fitted preprocessing object came from training blocks only.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
