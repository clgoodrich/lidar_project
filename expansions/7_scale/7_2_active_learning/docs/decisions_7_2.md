# 7.2 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review fix 7.2-01. G comes from the config or the preregistration and is set before scoring. It is never chosen from the replay and never floored. An unset G gives an inconclusive decision. G_raw is always reported as a diagnostic. This replaces the 2026-11-05 floor decision below. Made by the review-fix agent.
- 2026-11-06. Review fix 7.2-02. The live retrain raster starts as ignore everywhere. Base labels are copied only in the declared seed blocks (`seed_label_blocks`). A null seed set refuses the retrain. Made by the review-fix agent.
- 2026-11-06. A discovery window a policy acquired is background inside its block, plus the features drawn there. Made by the review-fix agent, change freely.
- 2026-11-06. Added reviewer features count for a policy only when their centroid lies in a window that policy acquired in that round. Other additions train no arm and are counted in the manifest as unattributed. Made by the review-fix agent, change freely.
- 2026-11-06. The stop rule is enforced. Curves, scores and inclusion logs are cut at the stop round before any estimate. When the loop stops before B*, the primary is read at the stop round and flagged `stopped_before_B_star`. Made by the review-fix agent, change freely.
- 2026-11-06. The replay reran with the preregistered 10 seeds (default from `replay.seeds`). Made by the review-fix agent.
- 2026-11-06. Items are rescored with `sc.load_policy("pit_floor")` from the 7.3 scorer 2 (F02). The cutoff moved from 0.10 to 0.35 and matching is block-local. Stopping-set files carry `truth_block_id` and are read with `strict=True`. The policy is saved as `results/tables/al_scoring_policy_9t.json`. Made by the review-fix agent.
- 2026-11-06. The replay stops a policy when its pool is exhausted. The smaller 0.35 pool exposed a crash on an empty draw. Made by the review-fix agent.
- 2026-11-06. The split reads the audit file through `ek.require_audit` (P2-01). `--no-audit` now only allows a missing file. The split is then stamped "no audit exclusion, exploratory". Made by the review-fix agent.

## Needs user decision

- G, the useful gain for U against R. Set it in `config_7_2.json` or the preregistration JSON before scoring. Until then the decision is inconclusive.
- `seed_label_blocks`. Which blocks give base labels to every arm in the live retrain. `[]` means acquired labels only. Null refuses.
- Whether reviewer additions outside any window should be shared across arms, given to the arms whose candidates sit in the same block, or dropped. They are dropped for now.
- Whether an early stop before B* should read the primary at the stop round (current code) or void it.


- 2026-11-05. Every policy draws by Poisson sampling with pi = min(1, c w) and c set so expected minutes meet the batch budget. pi is exact for Horvitz-Thompson and inverse-probability weights. Made by the build agent, change freely.
- 2026-11-05. Policy B divides the U weight by the square root of the tile's candidate count. A hard cap would break exact pi. Made by the build agent, change freely.
- 2026-11-05. Pool blocks give candidate items, discovery blocks give window items, stopping blocks give neither. Made by the build agent, change freely.
- 2026-11-05. The split covers only blocks with an out-of-fold pit raster (115 blocks). Made by the build agent, change freely.
- 2026-11-05. The replay pool comes from the historical pit unet_cv5 out-of-fold rasters until the P1 isolated model exists. Made by the build agent, change freely.
- 2026-11-05. The replay learner is a logistic re-ranker on logit score, log area and circularity. It cannot learn from discovery windows. The live loop retrains the U-Net. Made by the build agent, change freely.
- 2026-11-05. The timer caps any single start-to-stop interval at 5 minutes. Made by the build agent, change freely.
- 2026-11-05. A derived G below 0 is floored at 0. Replay and live G files carry different prefixes so a replay G is never reused live. Made by the build agent, change freely.
- 2026-11-05. The review package reuses the QML and README of `_build_pit_review_package.py` and calls `_pit_corrections_diff.py` by subprocess. It shows no score and no policy. Made by the build agent, change freely.
- 2026-11-05. `trainer_cmd` stays null until the P1 isolated pit trainer exists. Made by the build agent, change freely.
