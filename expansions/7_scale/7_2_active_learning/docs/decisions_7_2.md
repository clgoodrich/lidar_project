# 7.2 decisions

Newest first. One line per decision, with the date and who made it.

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
