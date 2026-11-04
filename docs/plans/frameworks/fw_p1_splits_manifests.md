# Framework P1. Reproducible splits and manifests

**Tier A.** Infrastructure. No scientific claim. Everything that trains or scores depends on it.
**Evidence level.** None.
**Depends on.** Nothing. Do first.
**Blocks.** P2, 3.0, 3.1, 5.1, 6.3, 7.1, 7.2, 7.3.

## 1. Problem and objective
Both cross-validation trainers rebuild their splits at run time, and the inner validation split is not reproducible. The saved manifest does not match what was trained. The original sampler can read held-out windows. Normalisation statistics are shared across folds.

**Objective.** Produce (a) a clear record of which split roles are recoverable, (b) a deterministic split generator, (c) an immutable split file, (d) an isolated pit trainer with every fix, (e) a derived spatial buffer, (f) tests that fail if any of this breaks.

**Hypotheses tested.** None. This is a defect fix. The check is that the fixed code behaves as specified.

## 2. Scope
In. Pit and pad CV trainers on tile 9t. The saved split exporter. The sampler.
Out. Retraining headline models (a later decision after S6). Road models (covered in 5.1).

## 3. Definitions
- **Held-out blocks (fold k).** Blocks assigned to fold k by `assign_folds`, which groups on block id and drops NaN. Deterministic and valid.
- **Inner validation blocks.** 20% of the remaining blocks, drawn per fold. Not reproducible historically.
- **Historical split.** What the saved checkpoints were trained on.
- **Future split.** A split saved to file before training.
- Block. A 375 m by 375 m grid cell of the 12 by 12 grid on 9t (`data/9t/derived/05/pit_blocks_9t.gpkg`, layer `blocks`, columns `block_id, ix, iy, n_pits, split`). 144 blocks, 115 hold pits.
- Rows with no block id. 209 of 712 pit rows and 345 of 995 pad rows are annotations off the tile.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Pit manifest | `data/9t/derived/05/pit_dataset_manifest.csv` | held, 712 rows |
| Pad manifest | `data/9t/derived/05/pad_dataset_manifest.csv` | held, 995 rows |
| Blocks | `data/9t/derived/05/pit_blocks_9t.gpkg` | held |
| Pit trainer | `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py` | held |
| Pad trainer | `notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py` | held |
| Isolated pad trainer | `notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py` | held, documented in `docs/iterations/nisar_checks_9t.md` section 7 |
| Sampler | `notebooks/wellsight_v2/_dl.py` lines 235 to 290 (`CenteredPatchSampler`) | held |
| Pit checkpoints | `data/9t/models/pit/unet_cv5/fold{0..4}/` | held, 5 each |
| Pad checkpoints | `data/9t/models/pad/unet_cv5/fold{0..4}/` | held |
| Training logs | `data/9t/models/pit/unet_cv5/_pit_cv5_ann712_train.log`, `data/9t/models/pad/unet_cv5/_pad_cv5_ann712_train.log` | held |
| Out-of-fold raster | `data/9t/models/pit/unet_cv5/pit_prob_floor_outoffold_9t_05.tif` | held |
| Existing split exporter | `notebooks/wellsight_v2/s3_train/_save_cv_split_manifests_9t.py` | held, held-out lists valid only |
| Manifest guard | `notebooks/wellsight_v2/s2_labels/_manifest_guard.py` | held, read it before writing a new guard |

## 5. Prerequisites and decisions
None. The seed policy (child seed = master + 1000 times fold) is already in the trainers and is kept.

## 6. Procedure
**S0. Recover what can be recovered.**
- Script `notebooks/wellsight_v2/s3_train/_recover_cv_splits_9t.py` (new). For each fold of each model, load the checkpoint on CPU and read `checkpoint_extra["held_out_blocks"]`. Parse the training log for per-fold counts of training and validation blocks and pits. Compare the held-out list with the saved held-out list from the exporter.
- Output `data/9t/results/splits/cv_split_recovery_9t.csv` with columns `model, fold, role, recoverable, source, n_blocks, n_pits`. Roles are `held_out` (recoverable from checkpoint), `inner_val` and `train` (unrecoverable unless a checkpoint stored them).
- Output `docs/iterations/cv_split_recovery_9t.md`. State plainly that inner roles are unrecoverable and that every non-held-out block counts as used by model k for audit purposes.
- Check. Every held-out list from checkpoints equals the exporter's list.

**S1. Reproduce the nondeterminism once, in a test.**
- Script `notebooks/wellsight_v2/s3_train/_check_split_determinism_9t.py` (new). It launches three fresh Python processes that each compute the inner validation lists for all folds with the historical code, and the same with the fixed code. It hashes the lists and compares.
- Expected. Historical code differs across processes in folds 0, 2 and 4 (seen on 2026-11-04). Fixed code is identical in all three.
- Output `data/9t/results/splits/split_determinism_check_9t.json`.

**S2. The fix in a generator, not in the historical trainers.**
- Script `notebooks/wellsight_v2/s3_train/_make_cv_splits_9t.py` (new). Algorithm.
  1. Read the manifest. Drop rows with NaN block id and count them.
  2. Cast block ids to int.
  3. Compute held-out folds with the historical `assign_folds`, same seed 20260727, so held-out lists do not change.
  4. For each fold k, `rest = sorted(int(b) for b in blocks if b not in held_k)`. Draw inner validation with `np.random.default_rng(20260727 + 1000 * k).permutation(rest)` and the same 20% rule.
  5. Write one JSON with explicit lists per fold and role, the seed, the dropped row counts and the SHA-256 of the manifest.
- Output `data/9t/results/splits/cv_splits_future_9t_v1.json`. Immutable once committed. A new version gets a new file.
- Leave the historical trainers unchanged. Add a header comment pointing to `cv_split_recovery_9t.md` and warning that their inner split is not reproducible.

**S3. Isolated pit trainer.**
- Script `notebooks/wellsight_v2/s3_train/_pit_unet_iso_cv5.py` (new), copied from `_pad_unet_iso_cv5.py` and adapted to pits. Changes from `_pit_unet_cv5.py`.
  1. Read splits from `cv_splits_future_9t_v1.json`. Never rebuild them.
  2. Window rejection. Draw a centre as before. Build the window rectangle (256 px at 0.5 m is 128 m, plus label support). Reject the draw if the rectangle intersects any held-out or inner-validation block polygon. Use a spatial index over those polygons. Count rejections per epoch and log them.
  3. Background draws use the same rule.
  4. Fold-local normalisation. Compute mean and standard deviation per channel from training windows only (a fixed-size random sample of 20,000 training windows). Save as `norm_stats_fold{k}.npz` next to the checkpoint. The historical code computes 14 numbers once over the original training blocks.
  5. Validation sampler uses only inner-validation windows that lie wholly inside inner-validation blocks.
  6. Best-epoch and cutoff selection on inner validation only. The held-out fold is scored once.
- Outputs under `data/9t/models/pit/unet_iso_cv5/fold{k}/`. Output raster `pit_prob_floor_outoffold_iso_9t_05.tif`.
- Do not train until S4 passes and the user agrees to the GPU hours (S6).

**S4. Derive the buffer.**
- Script `notebooks/wellsight_v2/s5_eval/_residual_correlogram_9t.py` (new). Compute out-of-fold residual `p - y` per pixel for the floor class at 0.5 m on a 5 m subsample. Estimate the empirical semivariogram in 25 m lags to 2,000 m. The range is the lag where the semivariogram reaches 95% of the sill.
- Receptive field. Compute from the U-Net depth and kernel sizes in `_dl.py` (class `UNet`). State it in metres.
- Buffer formula. `buffer = receptive_field_radius + correlogram_range`. Round up to 25 m.
- Output `data/9t/results/splits/buffer_derivation_9t.json` and a figure `data/9t/results/splits/residual_semivariogram_9t.png`.
- Also compute, per fold, minimum distance from held-out features to any other-fold feature and the share within 40 m. This exists in `cv_split_check_9t.json` (6.8 m minimum in pit folds 3 and 4).

**S5. Leakage unit tests.**
- Script `notebooks/wellsight_v2/s3_train/_test_iso_sampler_9t.py` (new). Draw 100,000 windows from the isolated sampler for each fold. Assert zero intersect held-out or inner-validation blocks. Assert the historical sampler fails the same test (it should report a non-zero count, which measures the original leakage). Write both counts.
- Output `data/9t/results/splits/sampler_leakage_test_9t.json`.

**S6. Retraining decision (a gate, not a stage).**
- Measure epoch time for one fold with the isolated trainer. Estimate GPU hours for 5 folds at 40 epochs. Write them in the resource table.
- Decide with the user. If yes, train all five folds and compare with the historical pit model at K = 40 per km² with a paired block bootstrap. This measures the optimism of the original sampler for pits. The pad comparison already exists (reviewer-cited F2 recall 0.912 to 0.891, not yet re-read).
- Output `docs/iterations/pit_iso_vs_original_9t.md` and a row in `LEADERBOARD.md`.

## 7. Statistical analysis plan
- S0 to S5 have no inference. They are exact checks.
- S6 primary. Recall at K = 40 per km², isolated minus original, paired block bootstrap over the 115 pit blocks. Report the interval. Margin none (a measurement of optimism, not a pass test).
- Secondary. Calibration (Brier, log loss, ECE) for each. Fold-to-fold spread.

## 8. Quality control
- Held-out lists in the new split file equal the historical exporter lists in every fold.
- No block id appears in two roles within a fold. Union of roles equals the set of 115 pit-bearing blocks (pit) or 129 pad blocks (pad).
- Normalisation statistics differ between folds. If they are identical, the fold-local code did not run.
- Hash of the split file recorded in every later run.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Three fresh processes give identical lists with the fixed generator. Sampler test shows zero leakage. | Mark P1 done. Release P2 and 3.0 |
| Failure | Any difference across processes or any non-zero leakage | Fix and rerun. No other process starts |
| Inconclusive | Not applicable | |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s3_train\_recover_cv_splits_9t.py`, `_check_split_determinism_9t.py`, `_make_cv_splits_9t.py`, `_pit_unet_iso_cv5.py`, `_test_iso_sampler_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_residual_correlogram_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\splits\` with `cv_split_recovery_9t.csv`, `split_determinism_check_9t.json`, `cv_splits_future_9t_v1.json`, `buffer_derivation_9t.json`, `residual_semivariogram_9t.png`, `sampler_leakage_test_9t.json`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\cv_split_recovery_9t.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\_provenance.py`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Checkpoints do not store `held_out_blocks` | Fall back to the exporter's held-out lists, which are deterministic, and say so |
| Fixed generator changes held-out lists | Keep `assign_folds` and its seed untouched. Assert equality |
| Isolated trainer rejects too many windows and starves training | Log the rejection rate. If above 30%, widen the training sample by drawing more candidates per epoch, not by relaxing the rule |
| Fold-local normalisation changes results materially | That is a finding. Report it |
| Changing trainers changes headline numbers | Keep historical numbers labelled historical. New numbers get new rows |

## 12. Resources
Setup and tests 6 to 8 hours. GPU for S6 is unknown until measured. Disk under 5 GB for new models (checkpoints and rasters, add `.gitignore` rules).

## 13. Handoff and open questions
- Confirm checkpoint file names inside `fold{k}/` before S0.
- Confirm where `_pad_unet_iso_cv5.py` writes its output.
- User decision at S6 on GPU hours.

## 14. Documentation updates
`docs/iterations/cv_split_recovery_9t.md`, `analysis_log.md`, `BACKLOG.md` (remove the NaN item), `LEADERBOARD.md` (S6 rows), master plan status.
