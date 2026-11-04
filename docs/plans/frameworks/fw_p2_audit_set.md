# Framework P2. Audit set and training history

**Tier A.** Infrastructure.
**Evidence level.** None.
**Depends on.** P1.
**Blocks.** 3.0 final claims, 5.1, 6.3, 7.2, 7.3.

## 1. Problem and objective
A frozen audit set is needed before any error mining, negative-class training or active learning. Every 9t block was in the training or validation set of four of the five CV models, so no 9t block is untouched. A final test that was used for tuning gives a falsely good result.

**Objective.** (a) A complete history of what touched each 9t block. (b) A frozen comparative audit set on 9t. (c) A reserved independent area for absolute claims. (d) A guard that makes it impossible to train on audit blocks.

## 2. Scope
In. Tile 9t blocks. A new reserved area. Guard code in every trainer and miner.
Out. Labelling the reserved area (6.3, 3.1).

## 3. Definitions
- **Used by model k.** A block was in the training or inner-validation role of model k, or was used to choose its threshold, epoch or calibration.
- **Comparative audit set.** 9t blocks excluded from every model trained after the freeze. It supports comparisons between new models only. Models older than the freeze have seen them.
- **Absolute audit area.** An area no model has touched and that nobody has inspected for model output. Only this supports absolute claims.
- **Mining.** Any step that looks at model errors to choose what to train next.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Split recovery | `data/9t/results/splits/cv_split_recovery_9t.csv` | from P1 S0 |
| Future split file | `data/9t/results/splits/cv_splits_future_9t_v1.json` | from P1 S2 |
| Training and evaluation scripts | `notebooks/wellsight_v2/s3_train/`, `s5_eval/`, `s6_review/` | held |
| Iteration docs and logs | `docs/iterations/`, `docs/analysis_log.md`, `LEADERBOARD.md` | held |
| Review packages that exposed blocks to people | `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py` and outputs | held |
| Existing guard | `notebooks/wellsight_v2/s2_labels/_manifest_guard.py` | held, read first |

## 5. Prerequisites and decisions
P1 done. Choose the absolute audit area (see S4). The user names reviewers separately for labelling.

## 6. Procedure
**S0. Exposure inventory (documentation).**
- Document `docs/iterations/audit_set_history.md`. One table with a row per 9t block (144) and columns for each use.
  1. Model role per CV model and fold (held-out, inner-val, train). For historical inner roles write "unrecoverable, treated as used".
  2. Threshold and cutoff selection (which folds, which blocks).
  3. Calibration (Platt fits, `_cv5_pr_calibration_pit_pad_9t.py`).
  4. Negative mining and review packages shown to humans (`_build_pit_review_package.py`, `_pit_corrections_diff.py`, road review packages).
  5. Context-feature models (road models trained on 9t and 613590, `_road_unet_1m_recall.py`).
  6. Human inspection of model outputs on that block (QGIS reviews, figures, error analyses).
- Method. Grep every script for block ids and for `held_out_blocks`. Read iteration docs. Mark gaps as "unknown, treated as used".
- Output `data/9t/results/splits/block_exposure_9t.csv` (block_id, one column per use, count) and the document.
- Expected finding. Every block has at least four uses. Say so.

**S1. Comparative audit set on 9t.**
- Choose blocks for exclusion from all future models. Rule. Stratify by feature density tercile and by slope tercile, then draw by seed 20261104. Target 15% of pit-bearing blocks (about 17), at least 3 per stratum.
- Apply the derived buffer from P1 S4 around each audit block. Buffer blocks are excluded from training too, so no training window reaches an audit block.
- Output `data/9t/results/splits/audit_blocks_9t_v1.csv` with hash. Freeze by committing.
- State in the file header. This set supports comparisons between new models only.

**S2. Guard.**
- Module `notebooks/wellsight_v2/_audit_guard.py` (new). Function `assert_no_audit(block_ids_or_windows, audit_file)` raising on any intersection. Imports the audit file hash and refuses to run if the hash differs from the committed hash.
- Wire into `_pit_unet_iso_cv5.py`, `_pad_unet_iso_cv5.py`, context stage 2 (5.1), confuser retraining (6.3), and any miner. Add a test `_test_audit_guard_9t.py` that tries to train on an audit block and must fail.
- Reuse patterns from `_manifest_guard.py` where they fit.

**S3. Random audit sample for discovery (separate from S1).**
- A random-area sample for active learning (7.2). Draw 20 km² of non-training ground, never tuned on, kept apart from the final audit set. Document in `audit_set_history.md`.

**S4. Reserve an absolute audit area.**
- Candidate. Warren (same D20 survey, 7 tiles on disk) is the first choice because the data exist. The plan 3.1 uses part of it for transfer. The rest is reserved.
- Rules. No model output viewed for that area before preregistration. No annotation by anyone who has seen model output for it. The reserved blocks are listed in `data/warren/results/transfer/audit_blocks_warren_v1.csv` with a hash before any inference runs.
- If Warren is too small for adaptation, test and audit, drop the adaptation role (see 3.1) and keep the audit role.

**S5. Freeze and announce.**
- Commit the audit files. Add a line to `docs/analysis_log.md` with the hashes. Record the audit rule in the master plan.

## 7. Statistical analysis plan
None. Exact bookkeeping. The only inference is a check that the audit strata are not systematically different from the rest (compare feature density and slope distributions with a two-sample Kolmogorov-Smirnov test, report, do not gate).

## 8. Quality control
- Every 9t block appears in `block_exposure_9t.csv`. Count 144.
- Audit set and its buffer do not intersect any training list in the future split file.
- The guard test fails when it should.
- Hash of the audit file is read from the file, not typed.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | History complete, audit file frozen, guard test passes | Release 6.3, 5.1 and 3.0 final claims |
| Failure | Any audit block found in a training list | Fix, rerun, document |
| Inconclusive | Exposure history has unknowns | Treat unknowns as used. Say so. Prefer the absolute area |

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\audit_set_history.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\splits\block_exposure_9t.csv`, `audit_blocks_9t_v1.csv`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\warren\results\transfer\audit_blocks_warren_v1.csv`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\_audit_guard.py`, `_test_audit_guard_9t.py`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| History is incomplete | Mark unknown as used. State the limit |
| Audit blocks get seen informally (figures, maps) | Rule. No figure that shows model output on audit blocks until the final run. Log any exception |
| Too few blocks left for training after buffers | Reduce the audit share to 10%, never relax the buffer |
| Audit area reused for tuning | The guard refuses. The file hash is checked |

## 12. Resources
Inventory 8 to 12 hours (reading scripts and logs). Guard and tests 3 hours. No GPU.

## 13. Handoff and open questions
- The user decides whether Warren is the absolute audit area or a separate county is preferred.
- Who may view audit blocks. Name them.

## 14. Documentation updates
`audit_set_history.md`, `analysis_log.md`, master plan, README rule 7.
