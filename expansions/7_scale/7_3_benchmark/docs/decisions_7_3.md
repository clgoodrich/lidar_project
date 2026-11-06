# 7.3 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. The scorer imports no repo code so the release runs alone. The test checks it against expkit.recall_at_k. Made by the build agent, change freely.
- 2026-11-05. One tile per 375 m block instead of 256 m tiles. Block-aligned tiles keep each tile in one split. Made by the build agent, change freely.
- 2026-11-05. The release folder is this expansion's `data/processed/terrain_v1/`, which is already gitignored. `data/benchmark/terrain_v1/` needs a new `.gitignore` rule from the lead. Made by the build agent, change freely.
- 2026-11-05. A feature that touches any hidden-test or buffer block is dropped from every public label file. Made by the build agent, change freely.
- 2026-11-05. Each baseline block is clipped from the fold raster that held it out, read from that model's own split. Pit and pad folds differ. Made by the build agent, change freely.
- 2026-11-05. The scorer takes a cutoff per task. Both stay at 0.10 per fw_00. At 0.10 pad recall is 0.063 and at 0.3 it is 0.68 on the provisional dev test. The pad cutoff needs a user decision from the operating-point sweep, never from the dev test. Made by the build agent, change freely.
- 2026-11-05. Leaderboard ties use overlap of each entry's difference interval from the baseline. A pairwise paired test is a later upgrade. Made by the build agent, change freely.
