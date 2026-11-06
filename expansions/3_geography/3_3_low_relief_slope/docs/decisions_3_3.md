# 3.3 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Scored footprint. User accepted the default all-block footprint (144 blocks, 29 pit-free) confirmed ("take defaults"). Change freely.
- 2026-11-06. Margin for the S1 and S5 gate. User accepted the default 0.03 recall ("take defaults"). Change freely.
- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates q1_slope_feature (one primary, so Holm equals the unadjusted rule), secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- 2026-11-06. Review fix pass (F02 F03 G-02 G-12 P1-01 P1-03 P2-01, minors). Made by the review-fix agent, change freely.
  - S1 scores through the 3.0 scorer. Proposal policy `policy_for` (0.35 in every fold) replaces `loo_max_recall`, which stays a sensitivity. The two agree on 9t.
  - S1 scores all 144 blocks (G-02). The 29 pit-free blocks join one fold each by the 3.0 round_robin rule. Block tercile cut points stay on pit-bearing blocks.
  - Rerun numbers. Terciles 0.899 / 0.934 / 0.893 to 0.935 / 0.940 / 0.946. Pooled 0.909 to 0.940. Without the fill the new code gives 0.899 / 0.934 / 0.899.
  - Splits are read with `ek.read_split_csv`. The audit is read with `ek.require_audit`. P2 is not frozen, so the rerun is labelled "no audit exclusion, exploratory".
  - The old S1 run recorded non-canonical P1 and P2 paths. Its `_RUN.md` now says so.
  - S3 donors (G-12) come only from pits held out in the scoring fold. A location with no fold is skipped and logged.
  - The S5 gate builds its commands from `config_3_1.json` areas and refuses an unknown area.
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

## Needs user decision
- None open. (2026-11-06)
