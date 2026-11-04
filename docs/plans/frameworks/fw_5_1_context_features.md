# Framework 5.1. Context features (second-stage model)

**Tier A.**
**Evidence level.** (a).
**Depends on.** P1, P2, a shared fold scheme, 3.0 scorer.
**Blocks.** Nothing.

## 1. Problem and objective
The pit and pad models see one patch at a time. Roads, pads and neighbouring pits give context that could improve ranking. Two things are unknown. How much the existing models already use context, and how much a second stage would add.

**Q1. Context reliance.** Does the pit score depend on the surrounding pad and road context?
**Q2. Context gain.** Does a second-stage model built on out-of-fold maps raise recall at K = 40 per km² over the first stage?

**Hypotheses.** Q1. Removing context changes pit scores (paired difference in score and rank), relative to sham edits. Q2. Stage 2 recall at K minus stage 1 recall at K is above 0 by at least the useful gain.

## 2. Scope
In. Reliance test with edits, shared fold scheme, retraining pad and road models as needed, stage-2 features and learner, leakage audit.
Out. Claims that context finds more wells. Annotation context bias is a caveat.

## 3. Definitions
- **Outer fold k.** Held-out blocks for the final stage-2 score.
- **Upstream model.** Pit, pad or road model whose output feeds stage 2.
- **Leakage-free stacking.** For outer fold k, every upstream model used to build both stage-2 training and test inputs excluded fold k's blocks from its own training and selection.
- **Shared fold scheme.** One block-to-fold assignment used by pit, pad and road models. Today pit and pad folds are balanced on different counts, so they differ.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Pit and pad out-of-fold rasters | `data/9t/models/pit/unet_cv5/`, `.../pad/unet_cv5/` | held, different fold schemes |
| Road models | `_road_unet_1m_recall.py`, `road_unet_1m_recall` outputs (trained on 9t and 613590) | held, split scheme unknown |
| Isolated trainers | P1 | future |
| Audit set | P2 | future |
| Feature stacks | `data/9t/derived/05/features_pit_9t_05.tif` | held |
| Context feature code | `s1_build/_build_extra_channels.py` | held |

## 5. Prerequisites and decisions
One block-fold scheme for all upstream models. GPU hours for retraining pad and road models (measure epoch time first, the backlog says it was under-reported by 1.8 times).

## 6. Procedure
**S0. Upstream inventory.**
- Document `docs/iterations/context_upstream_inventory.md`. For each upstream model list checkpoint path and hash, training blocks, held-out blocks, scheme and whether the held-out lists can be reproduced. Mark any model whose fold scheme differs from the chosen one as "must retrain".

**S1. Shared fold scheme.**
- Script `notebooks/wellsight_v2/s3_train/_make_shared_folds_9t.py` (new). Assign each block to one outer fold, balanced on pit count and pad count jointly (greedy deficit on both), seed 20261104, excluding audit blocks. Save `data/9t/results/splits/shared_folds_9t_v1.json`. All upstream retraining reads it.

**S2. Reliance test (Q1).**
- Script `notebooks/wellsight_v2/s5_eval/_context_reliance_9t.py` (new). For a random sample of 300 annotated pits (all pits, not only detected ones) and 300 matched controls.
  1. Edit the DEM around the pit. Variants. (a) remove the pad (flatten to the local plane outside a 12 m radius), (b) remove the access road, (c) both, (d) sham edits of equal area in the surrounding terrain.
  2. Recompute every derivative from the edited DEM with realistic terrain backgrounds. Never alter derivative layers directly.
  3. Rescore with the isolated pit model. Record the score at the pit and the rank among candidates in the scene.
- Output `data/9t/results/context/context_reliance_paired_9t.csv`.
- No half-score rule.

**S3. Retrain upstream models on the shared scheme.**
- Pit and pad with the isolated trainers (P1). Road by copying `_road_unet_1m_recall.py` and reading the shared folds. Store under `data/9t/models/<model>/unet_shared_cv5/`. Add `.gitignore`.

**S4. Stage-2 features.**
- Script `notebooks/wellsight_v2/s5_eval/_context_stage2_9t.py` (new). From out-of-fold maps (each from the model that excluded that block) build per-candidate features. Distance to nearest road probability above 0.5, pad probability within 25, 50 and 100 m, number of other pit candidates within 50 and 100 m, local slope, and the first-stage score. Output `data/9t/results/context/stage2_features_9t.parquet`.

**S5. Stage-2 learner.**
- Gradient boosting (small trees, depth 3, 200 estimators) and logistic regression. Nested spatial folds. Inner folds choose hyperparameters. Outer folds are the shared scheme. Train on candidates from outer-training blocks, label = matched to annotated feature. Output `data/9t/results/context/stage2_scores_9t.csv`.

**S6. Leakage audit.**
- For every outer fold k list the upstream models used to build stage-2 inputs. Assert each excluded fold k blocks. Write `context_leakage_audit_9t.json`. Fail the run if any model is missing the assertion.

**S7. Scoring.**
- Re-rank candidates by stage-2 score. Score with `_transfer_score.py` at K = 40 per km². Compare with stage 1.

## 7. Statistical analysis plan
- Q1 primary. Paired score change (original minus context-removed) for real pits minus the same for shams, median and block bootstrap interval. Rank change likewise.
- Q2 primary. Recall at K, stage 2 minus stage 1, paired block bootstrap over outer-fold blocks. Superiority against the smallest useful gain (user, per experiment).
- Secondary. Calibration, feature importance (permutation importance by block resampling), gain by block feature density.

## 8. Quality control
- Leakage audit passes.
- Stage-2 features computed with the same code on training and test blocks.
- No audit block in any list.
- Check that stage 2 does not simply learn annotation habits. Add a sensitivity that removes road distance and nearby-pit counts.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Gain lower bound above the useful gain | Adopt stage 2. Test in 3.1 |
| Failure | Upper bound below the useful gain | Keep stage 1 |
| Inconclusive | Otherwise | Report |
| Leakage audit failure | Any | Void the run |

## 10. Deliverables
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s3_train\` and `s5_eval\` as named
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\context\`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\context_upstream_inventory.md`, `context_reliance_9t.md`, `context_stage2_9t.md`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Road checkpoints missing out-of-fold models | Retrain. Budget GPU time from measured epochs |
| Stage 2 learns annotator search habits | Ablation, caveat, field check |
| Small candidate counts per fold | Logistic regression baseline, strong regularisation |
| Edits not realistic | Realistic backgrounds, recompute derivatives, sham controls |

## 12. Resources
Inventory 6 hours. Edits and reliance 12 hours. Retraining GPU unknown until measured (3 models by 5 folds). Stage 2 8 hours. Disk several GB.

## 13. Handoff and open questions
- Useful gain threshold. Whether roads should be retrained or dropped.

## 14. Documentation updates
`context_*` docs, `LEADERBOARD.md`, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
One threshold δ_gain, based on downstream value, serves both success and failure. Specify common folds and all cross-fitting before retraining.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
