# Framework 7.2. Active learning with random-area discovery

**Tier A (full depth, 2026-11-05).** The user withdrew the deferral. The plan assumes the reviewers, areas and tooling in section 5 exist. Each assumption is tagged VERIFY.
**Evidence level.** (a). It labels drawn features. It does not confirm wells.
**Depends on.** P1 (isolated trainer, splits). P2 (audit files, guard, discovery sample S3). 6.3 (codebook, blind sheets, throughput). 3.0 scorer.
**Blocks.** Nothing. 7.5 may reuse the inclusion-probability bookkeeping.

## 1. Problem and objective
Reviewer time is the bottleneck. Choosing which items to label next may cut that time. Two traps exist. Candidate-only selection cannot find positives outside the proposal pool. Equal label count is not equal effort, because reviewing a candidate takes minutes and drawing a full block takes much longer.

**Question.** Does a selection policy reach a target recall at K = 40 per km² with fewer reviewer-minutes than random selection, when the pool includes random-area discovery windows?

**Hypotheses.**
- H1. Uncertainty selection beats random selection at equal cumulative reviewer-minutes by at least the useful gain G.
- H2. A hybrid policy (uncertainty plus random-area windows) beats pure candidate selection on discovery yield.
- H3. Label count and reviewer-minutes rank the policies differently. This tests the stated worry directly.

## 2. Scope
In. A simulation replay on existing labels. A live loop with reviewers. Learning curves with a random control. Inclusion-probability bookkeeping. A stopping rule.
Out. Tuning on the final audit set. Well confirmation. Road models (their loop exists in `_build_road_review_package.py`).

## 3. Definitions and estimand
- **Item.** One unit a reviewer handles. Type C is a model candidate polygon. Type W is a random discovery window (a 375 m block drawn at random and annotated in full for pits and pads).
- **Effort.** Measured reviewer-minutes per item, from a timer in the review tool. Never label count.
- **Pool.** Candidates in non-audit blocks plus the discovery frame (all non-audit, non-stopping-set blocks in the discovery areas).
- **Stopping set.** Fully annotated random blocks used only to monitor and stop. Disjoint from the pool and from the final audit sets. Frozen before round 0.
- **Final audit sets.** P2 S1 (comparative, 9t) and P2 S4 (absolute area). Scored once.
- **Round.** Select a batch, label, retrain on the diff, score the stopping set.
- **Inclusion probability pi_i.** Probability that item i was shown to the reviewer at the round it was selected, given the pool and the policy. It is recorded for every item.
- **Policies.**
  - R. Random candidates.
  - U. Uncertainty. Sample candidates with probability from a softmax of entropy of the mean probability (or margin to the cutoff), temperature fixed in the preregistration. Sampling, not top-k, so every pi_i is above 0.
  - D. Random discovery windows only.
  - H. Hybrid. 70% of the minute budget to U, 30% to D, fixed before running.
  - B. Diversity. U with a cluster cap on shared tiles.
- **Primary estimand.** Recall of annotated pit floors at K = 40 per km² on the stopping set, difference U minus R at cumulative reviewer-minutes B*, averaged over 3 or more selection seeds. B* is the midpoint of the total budget, named in the preregistration.
- **Discovery yield.** Validated new features per reviewer-hour found in D windows that the pool never proposed, Horvitz-Thompson weighted. It estimates how much the proposal pool misses.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Review package builders | `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py`, `_pit_corrections_diff.py`, `_build_road_review_package.py` | held |
| Isolated trainers | `notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py` (held), `_pit_unet_iso_cv5.py` (from P1) | held, proposed |
| Splits and audit files | `data/9t/results/splits/cv_splits_future_9t_v1.json`, `audit_blocks_9t_v1.csv`, `notebooks/wellsight_v2/_audit_guard.py` | from P1, P2 |
| Discovery sample | `docs/iterations/audit_set_history.md` section S3 (20 km² random, never tuned) | from P2 |
| Blind sheets and codebook | 6.3 `notebooks/wellsight_v2/s6_review/_confuser_sheets_9t.py`, `docs/iterations/confuser_codebook.md` | from 6.3, proposed |
| Existing labels | `qgis/annotations/annotations_proj.gpkg` (`pit_inside`, `pit_full`) | held |
| Lidar for new areas | `data/_source/reference/lidar_catalogue/lidar_win_download_list_us.csv` | listed |

## 5. Assumed data
| # | Assumption | Tag | How to verify |
|---|---|---|---|
| 1 | Two reviewers and one adjudicator are available | VERIFY | User names them. 6.3 pilot confirms they finish |
| 2 | Reviewer budget is 60 hours in total across all policies (proposed) | VERIFY | User confirms. Replace with the pilot-measured rate |
| 3 | Throughput. Candidate review about 6 minutes each, block annotation unknown | VERIFY | Time one real block of full annotation and 20 candidates before extrapolating (protocol section 13) |
| 4 | At least 120 non-audit, non-pool blocks of discovery ground exist with lidar built into the 9t derivative stack. Sources are unused 9t blocks plus Warren non-reserved tiles plus one other D20 window | VERIFY | Count blocks after P2. Compute union coverage from tile geometry |
| 5 | The review tool logs per-item timestamps, with idle gaps over 5 minutes cut | VERIFY | Build `_review_timer.py` and test it on 10 items |
| 6 | A stopping set of 20 complete random blocks can be fully annotated | VERIFY | Check against the annotation time of assumption 3. Reduce to 15 if over 10% of budget |
| 7 | GPU is the held GTX 1070 Ti. A round is one fine-tune on the isolated trainer, with hours from the P1 S6 measurement | VERIFY | Wall-clock one full epoch |
| 8 | Reviewers have not seen model output on stopping or audit blocks | VERIFY | Written confirmation, logged in the audit history |

## 6. Prerequisites and decisions
P1 and P2 done. 6.3 pilot complete. User decisions. Total budget, batch size (default 60 candidates or the minute equivalent), selection score, temperature, hybrid split, G.

## 7. Procedure
**S0. Setup.** Script `notebooks/wellsight_v2/s6_review/_al_setup_9t.py` (proposed). Split non-audit blocks into pool, discovery frame and stopping set by seeded draw. Run the P2 guard. Write `data/9t/results/active/al_split_9t_v1.json` with hash. Record the master seed.

**S1. Simulation replay (no reviewers).**
- Script `notebooks/wellsight_v2/s6_review/_al_replay_9t.py` (proposed). Use existing 9t labels as the oracle. Each item gets a simulated cost (minutes from assumption 3). Run policies R, U, D, H, B over 10 selection seeds.
- Purpose. Choose the temperature, the batch size and the hybrid split, and find bugs. Not evidence for the live claim, because the oracle is the same annotator's drawn labels (level (a), exploratory).
- Output `data/9t/results/active/al_replay_curves_9t.csv`.
- Freeze every parameter in the preregistration after S1 and before S2.

**S2. Round 0.** Train the isolated model on existing labels outside the stopping set. Score the stopping set. Write `round_00/`.

**S3. Live loop.** Script `_al_select_9t.py` (proposed).
1. For each policy, draw the batch. Record item id, type, policy, round, pi_i, model version hash, selection seed.
2. Pool the batches across policies and deduplicate (centroid within 5 m, same window). Items are labelled once, blind to policy, using 6.3 sheets with no model score and no DEP record.
3. Reviewers label. The timer logs minutes. A shared item charges its measured minutes to every policy that selected it, so a policy that picks cheap items is credited fairly.
4. Retrain on the diff for each policy from a common starting checkpoint. Rejected candidates become hard negatives (as in the road loop). Score the stopping set.
5. Output `data/9t/results/active/<run_id>/round_<nn>/` with `batch_<policy>.gpkg`, `labels.csv`, `minutes.csv`, `stopping_score.csv`.
6. Repeat until the stopping rule fires.

**S4. Stopping rule.** Stop when the cumulative minutes reach the budget, or when stopping-set recall at K changes by under 0.01 for two rounds in the random control. The rule uses the stopping set only and is fixed in advance. The audit sets are not touched.

**S5. Final scoring.** The best preregistered policy and policy R are each scored once on the comparative audit set. Absolute claims use the absolute audit area.

**S6. Discovery accounting.** For D windows, list features the pool never proposed. Estimate pool recall with Horvitz-Thompson weights (section 8).

## 8. Statistical analysis plan
- **Primary.** Recall at K on the stopping set at B* reviewer-minutes, U minus R. Paired block bootstrap over stopping blocks (B = 2000) with the same resampled blocks for both arms, averaged over selection seeds. The stopping set has few blocks (about 20), so also report a permutation interval and say the bootstrap is unreliable below 15 blocks.
- **Margin.** G, the useful gain. Default derivation is the recall R gains over the last quarter of the budget. The policy must beat what plain extra labelling already buys. G is read from the R curve at B* before U is scored. The user may replace it with a minute value. It never comes from seed spread.
- **Decision.** Superiority. Success if the lower bound is above G. Failure if the upper bound is below G. Otherwise inconclusive.
- **Learning curves.** Recall at K versus cumulative minutes and versus label count, per policy, random control in every figure. Area between curves is exploratory.
- **Selection bias.** Items chosen by U are not a random sample of the pool, so a naive recall on labelled items is biased. Rules.
  - Evaluation never uses selected items. Evaluation uses the stopping set (random blocks, design-unbiased).
  - Training uses inverse-probability weights, w_i = 1 / pi_i, self-normalised and clipped at the 95th percentile, with the unclipped run as a sensitivity.
  - Discovery yield and pool recall use the Horvitz-Thompson estimator with pi from the D-window draw. Variance by block bootstrap.
  - Every pi_i is stored in `inclusion_log.csv`. Any item with pi_i of 0 is a bug.
- **Cost.** Report minutes per item by type with a bootstrap interval over items. Report the label-count ranking next to the minute ranking (H3).
- **Seeds and effective sample.** Selection seeds are nuisance. The stopping blocks are the sample.
- **Multiplicity.** One primary. Other contrasts exploratory.

## 9. Quality control and leakage checks
1. No stopping or audit block appears in any batch, training list or hard-negative list (guard run at each round).
2. Pool, discovery frame and stopping set are disjoint. Assert by block id and by buffered geometry.
3. Same config and seed reproduce the same batch.
4. Reviewers see no policy name, score or DEP point. Sheets are rebuilt from pooled ids.
5. A 10% random relabel by the other reviewer measures label agreement (percent and kappa, reported, not a criterion).
6. Normalisation statistics are fold-local to training blocks at every round.
7. Timer audit. Items under 10 seconds or over 30 minutes are flagged and reviewed.
8. Row counts and CRS asserted at every join. No duplicate item counted twice.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Primary lower bound above G | Adopt policy U for later loops. Score the audit set once |
| Failure | Primary upper bound below G | Use random selection plus discovery windows. Say whether the score or the loop failed |
| Inconclusive | Interval spans G | Report. Add seeds in replay, then budget. Do not move G |
| Discovery finding | Pool recall upper bound below the target | Proposal pool misses features. Add the missed class as a training item type |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s6_review\_al_setup_9t.py`, `_al_replay_9t.py`, `_al_select_9t.py`, `_review_timer.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_al_curve_score_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\active\` (split JSON, replay CSV, run folders, `inclusion_log.csv`, figure `al_curves_minutes_9t.png`)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\active_learning_9t.md`, `prereg_active_learning.md`

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Cold start, round 0 too weak to pick well | Replay shows the minimum round-0 size. Start R and U from the same checkpoint |
| Reviewers learn the pattern and speed up | Randomise item order across policies. Report minutes by round |
| Sampling bias hides positives outside the pool | D windows and pi_i weights |
| Stopping set reused for tuning | Guard and hash. Replace with a fresh set if exposed |
| Few stopping blocks make the interval wide | Projected-width check before labelling (`fw_00_common.md` section 4). Change the design if over twice the margin |
| Selection finds only hard noise (label validity) | Adjudicate, keep U share, report validated and unvalidated yields apart |
| Shared items hide cost differences | Charge measured minutes to each selecting policy |

## 13. Resources
Setup and replay 16 hours. Reviewer time 60 hours (proposed, VERIFY). GPU is rounds x policies x one fine-tune, with hours from the measured epoch time. Disk a few GB.

## 14. Handoff and open questions
- Budget, batch size, G, temperature, hybrid split.
- Reviewer names and the blindness confirmation.
- Where the new discovery blocks come from.

## 15. Documentation updates
`active_learning_9t.md`, `analysis_log.md`, `LEADERBOARD.md`, `BACKLOG.md`, `literature/CITATIONS.md` (uncertainty sampling and inverse-probability weighting sources), master plan.

## Review revision (2026-11-05)
Deferral withdrawn by the user. Written to full depth on assumed reviewers and areas. Nothing here has been run.
Source. `docs/plans/protocol_gates_and_metrics.md` section 12.
