# 5.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Stage-2 candidates are re-extracted from the pit OOF raster at cutoff 0.10, 4 m2 floor, 4-connectivity, score = mean probability. The sweep object table has no coordinates. Made by the build agent, change freely.
- 2026-11-05. Candidates match annotated floors (`pit_inside`) greedily by IoU 0.3, one to one. Duplicates take budget and score nothing. Made by the build agent, change freely.
- 2026-11-05. Default stacking mode is nested. Training rows in fold j for outer fold k read a model that excluded k and j. Made by the build agent, change freely.
- 2026-11-05. Shared folds balance by minimax of pit share and pad share. Empty blocks spread by block count. Seed 20261104. Made by the build agent, change freely.
- 2026-11-05. Inner validation in each retraining job is fold (k + 1) mod K. Made by the build agent, change freely.
- 2026-11-05. The primary arm is gradient boosting. Logistic and the ablation arm are secondary. Made by the build agent, change freely.
- 2026-11-05. Recall at K is pooled over outer folds. Scored area is the block count times 0.140625 km2. Made by the build agent, change freely.
- 2026-11-05. Any model not trained with an isolated trainer is flagged must retrain, even when its scheme matches. Made by the build agent, change freely.
- 2026-11-05. Road corridor is 3 m each side of the line within 60 m of the unit. Sham offsets are 20 to 60 m so shams stay in the scene. Made by the build agent, change freely.
- 2026-11-05. Reliance controls are random points in pit blocks at least 30 m from any floor, matched on slope tercile. Made by the build agent, change freely.
- 2026-11-05. Upstream outputs go under this expansion's `models/` and `data/`, not `data/9t/`, because the build may only write inside its folder. Made by the build agent, change freely.
