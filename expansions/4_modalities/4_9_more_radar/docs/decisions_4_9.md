# 4.9 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review fix 4.9-01. lidar_weak is no longer chosen on the baseline score. That rule handed a same-information arm a gain of about +0.18 by regression to the mean. The stratum now comes from an external covariate set in prereg.lidar_weak. It keeps targets in the weak tail of the target covariate distribution, with all decoys. The covariate is unset, so lidar_weak is reported as undefined until the user sets it. made by the review-fix agent.
- 2026-11-06. Review fix 4.9-01. Exactly one primary row. prereg.primary_stratum is all. lidar_weak is secondary. The framework names lidar_weak as primary, but its definition was the flawed one. made by the review-fix agent, pending user decision.
- 2026-11-06. Review fix 4.9-01. The arm decision needs a null placebo. Success is downgraded to "inconclusive (placebo not null)" when the placebo lower bound is above 0. gain_net (arm gain minus placebo gain) is reported beside it. made by the review-fix agent.
- 2026-11-06. Review fix SH-01 in paired_gain_boot. Undefined draws are kept and counted (undefined_share). Above prereg.max_undefined_share (0) the interval is undefined and the decision is inconclusive. made by the review-fix agent.
- 2026-11-06. Review fix. paired_perm rank-transforms each arm over all rows before swapping. Raw scores on different scales were mixed inside one AUC. Each arm's AUC is unchanged by this. made by the review-fix agent.
- 2026-11-06. Review fix. S4 stamps the frozen rows (sar_rows_<target>_9t.csv.frozen.json, sha256 of the non-arm columns). S4 and S5 refuse on a mismatch. The held 9t pit rows were adopted because their whole-file hash matched the --rows-only provenance. made by the review-fix agent.

## Needs user decision
- Which external covariate defines lidar_weak (for example base:control:cover high, or a ground point density layer), which side is weak, and what share of targets it keeps.
- Whether lidar_weak returns to primary once that covariate is fixed, as the framework intends.
- Whether a declared share of undefined bootstrap draws may be tolerated (prereg.max_undefined_share). It is 0 now.


- 2026-11-05. Arm numbers in config_4_9.json (resolution, looks, acquisitions, registration, contrast) are placeholders tagged VERIFY. made by the build agent, change freely.
- 2026-11-05. Fill is footprint over resolution cell, capped at 1. Noise adds speckle averaged over cells and dates to clutter averaged over cells only. made by the build agent, change freely.
- 2026-11-05. Power simulation works on the probit of baseline mid-ranks, so it holds the baseline AUC exactly. made by the build agent, change freely.
- 2026-11-05. Eligibility uses rho 0.95 as the primary within-pair correlation. 0.90 and 0.98 are reported. made by the build agent, change freely.
- 2026-11-05. The S1 eligibility gain is configurable (g_for_power). It defaults to delta + 0.01 as written. That rule leaves power near or under 0.5 by construction. Lead to decide. made by the build agent, change freely.
- 2026-11-05. Placebo arm permutes the arm columns within block. made by the build agent, change freely.
- 2026-11-05. Scores are the mean out-of-fold probability over repeats. Repeat 0 is the deterministic GroupKFold. made by the build agent, change freely.
- 2026-11-05. Holm adjustment uses the bootstrap share of draws at or below zero over the exploratory arms. made by the build agent, change freely.
- 2026-11-05. Frozen rows come from the NISAR samples files with repeated decoys dropped by the dedupe key. 9t pits give 4,881 rows, 489 targets. made by the build agent, change freely.
