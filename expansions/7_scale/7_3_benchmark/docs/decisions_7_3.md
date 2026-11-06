# 7.3 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review repair 7.3-01. The scorer, baselines and leaderboard take every scoring setting from `ek.policy_for(task)`. Pit is 0.35 and pad is 0.525. 0.10 runs only as `--mode sensitivity`. The config holds no cutoff. The export writes `scoring_policy.json` into the release and evaluate.py reads it in a fresh checkout. Made by the repair agent, follows fw_00 section 4.
- 2026-11-06. Review repair 7.3-02. A candidate matches only truth in its own block. Recall counts only truth inside the denominator. An undefined bootstrap draw makes the interval null. Matching is greedy in score order. IoU order is the sensitivity. Made by the repair agent, follows fw_00 section 4.
- 2026-11-06. Review repair F05. The export reads P1 with `ek.read_split` and P2 with `ek.require_audit`. P2 role audit is the hidden test. P2 role buffer is excluded from both sides. An unknown role or a missing audit file stops the export. Made by the repair agent.
- 2026-11-06. Release roles use the P1 pit folds (`split_task` in the config). The provisional release also used the pit split. Pad baselines stay out-of-fold through their own split file. Made by the repair agent, change freely.
- 2026-11-06. The scorer keeps the old keyword form of `evaluate` so 7.1 and 7.2 still run. That form stamps the policy as caller supplied. It never passes `ek.assert_same_policy` against the shared policy. Made by the repair agent, remove once 7.1 and 7.2 pass a policy.
- 2026-11-06. Every 7.3 output on disk ran with no audit exclusion. The P2 audit file does not exist. The release, card and README say so. Made by the repair agent.
- 2026-11-05. The scorer imports no repo code so the release runs alone. The test checks it against expkit.recall_at_k. Made by the build agent, change freely.
- 2026-11-05. One tile per 375 m block instead of 256 m tiles. Block-aligned tiles keep each tile in one split. Made by the build agent, change freely.
- 2026-11-05. The release folder is this expansion's `data/processed/terrain_v1/`, which is already gitignored. `data/benchmark/terrain_v1/` needs a new `.gitignore` rule from the lead. Made by the build agent, change freely.
- 2026-11-05. A feature that touches any hidden-test or buffer block is dropped from every public label file. Made by the build agent, change freely.
- 2026-11-05. Each baseline block is clipped from the fold raster that held it out, read from that model's own split. Pit and pad folds differ. Made by the build agent, change freely.
- 2026-11-05. The scorer takes a cutoff per task. Both stay at 0.10 per fw_00. At 0.10 pad recall is 0.063 and at 0.3 it is 0.68 on the provisional dev test. The pad cutoff needs a user decision from the operating-point sweep, never from the dev test. Made by the build agent, change freely.
- 2026-11-05. Leaderboard ties use overlap of each entry's difference interval from the baseline. A pairwise paired test is a later upgrade. Made by the build agent, change freely.

## Needs user decision

- Freeze the P1 future split and the P2 audit set. A real release needs both.
- Leaderboard margin and the H3 width target. Still open from 2026-11-05.
