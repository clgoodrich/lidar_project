# 3.3 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Proposal cutoff policy is the archival leave-one-fold-out rule (0.35 in every fold), not the fixed 0.10 in fw_00. Set `proposal_policy` to `fixed` to change it. Made by the build agent, change freely.
- 2026-11-05. Each fold is ranked on its own scores with a budget of round(40 x held-out km²). Made by the build agent, change freely.
- 2026-11-05. The scored footprint is the 115 pit-bearing held-out blocks. Blocks without pits have no fold and are not scored. Made by the build agent, change freely.
- 2026-11-05. Depth is the median 0.5 m DEM in a 5 m ring outside the floor minus the floor minimum. Void is the share of 0.5 m cells with no ground return within 5 m. Made by the build agent, change freely.
- 2026-11-05. The confound model is sklearn logistic regression without a penalty, with a block bootstrap. statsmodels is not installed. Made by the build agent, change freely.
- 2026-11-05. Edit channels are recomputed with the shared library. Slope uses Horn in numpy (r 0.997 to the WBT band). Edits are paired against a background recomputed the same way. Made by the build agent, change freely.
- 2026-11-05. The channel influence radius is 25 m x sqrt(2) plus 8 cells, by Euclidean distance. Made by the build agent, change freely.
- 2026-11-05. The seam check reports three statistics. The default rule is the framework text, which fails real pits by construction. Made by the build agent, change freely.
- 2026-11-05. Scored edit locations must sit in a block with a held-out fold. Made by the build agent, change freely.
- 2026-11-05. Outputs go to this expansion's `results/<run_id>/`, not `data/9t/results/terrain/`. Made by the build agent, change freely.
