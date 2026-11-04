# P1 Reproducible splits and manifests

**Problem.** Both cross-validation trainers rebuild their splits at run time from a seed, and rows without a block id carry NaN. In a saved check, 209 of 712 pit rows and 345 of 995 pad rows had no block. The trainers never score them. The set difference over block ids also carries a NaN id.

**Why it matters.** Every transfer, context and retraining plan depends on a split that can be reproduced and audited.

**Evidence level produced.** None. It is infrastructure.

**Inputs.** `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py`, `_pad_unet_cv5.py`, the manifests in `data/9t/derived/05/`.

**Architecture.**
1. Fix the NaN handling in both trainers (drop rows with no block before building folds, and say how many).
2. Save explicit split files. A script `_save_cv_split_manifests_9t.py` exists and writes `data/9t/results/splits/`. Make the trainers read these files instead of rebuilding.
3. Spatial check. Held-out and other-fold features had a minimum separation of 6.8 m in one pit fold. Add a buffered option and a check that fails above a stated limit.
4. A hash of each split file recorded in the run provenance.

**Method outline.** One source of truth for splits. Trainers read, never rebuild.

**Acceptance test.** Two runs of any fold give identical train, val and held-out block lists. The check reports separation per fold.

**Risks and unknowns.** Changing the trainers may change reported numbers. Re-run the headline numbers and record any difference.

**Depends on.** None. Do first.

**Executor notes.** Do not retrain until this is done.
