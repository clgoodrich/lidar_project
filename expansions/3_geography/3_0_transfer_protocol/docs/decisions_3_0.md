# 3.0 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Scripts live in `src/` of this folder. The framework's `notebooks/wellsight_v2/s4_infer` and `s5_eval` paths are superseded. Made by the build agent, change freely.
- 2026-11-05. The harness proposal cutoff is the sweep's, per task (pit 0.35, pad 0.525, the median of 0.50 to 0.55). The protocol asks for the sweep's proposal extraction. fw_00's 0.10 merges blobs and drops 9t pit recall at K 40 from 0.909 to 0.575. 0.10 stays a sensitivity. Made by the build agent, change freely.
- 2026-11-05. Matching pairs are taken in score order, as in the code that made the 9t reference. fw_00's "greedy by IoU" is the `--order iou` sensitivity. Made by the build agent, change freely.
- 2026-11-05. The dedupe rule reads truth, so it is a scoring rule, not a deployment rule. `--dedupe none` turns it off. Made by the build agent, change freely.
- 2026-11-05. Hits are credited to the block of the truth feature. Candidates and truth join blocks by centroid. Made by the build agent, change freely.
- 2026-11-05. The 9t reference uses `k_rule per_group` (budget floored per fold area, as the sweep). Targets use one global K. Made by the build agent, change freely.
- 2026-11-05. An edge block is any block with a cell outside valid raster data. Edge blocks are dropped by default. Made by the build agent, change freely.
- 2026-11-05. Under 15 blocks the extra interval is a sign-flip interval on block residuals about the pooled ratio. Made by the build agent, change freely.
- 2026-11-05. Output files carry the area in their names (`transfer_score_<area>.json`) to follow the filename rule. Made by the build agent, change freely.
- 2026-11-05. The preregistration embeds a `json prereg` block. The harness reads it and refuses any flag that disagrees. Made by the build agent, change freely.
- 2026-11-05. The projected width resamples the 115 archival pit blocks without fold strata. Made by the build agent, change freely.
- 2026-11-05. Pad truth is layer `pad`, which `read_layer` maps to `plat`. Made by the build agent, change freely.
- 2026-11-05. The void raster is 1 where the 0.5 m ground density is zero. Made by the build agent, change freely.

