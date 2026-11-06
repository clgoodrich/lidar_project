# 4.9 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Arm numbers in config_4_9.json (resolution, looks, acquisitions, registration, contrast) are placeholders tagged VERIFY. made by the build agent, change freely.
- 2026-11-05. Fill is footprint over resolution cell, capped at 1. Noise adds speckle averaged over cells and dates to clutter averaged over cells only. made by the build agent, change freely.
- 2026-11-05. Power simulation works on the probit of baseline mid-ranks, so it holds the baseline AUC exactly. made by the build agent, change freely.
- 2026-11-05. Eligibility uses rho 0.95 as the primary within-pair correlation. 0.90 and 0.98 are reported. made by the build agent, change freely.
- 2026-11-05. The S1 eligibility gain is configurable (g_for_power). It defaults to delta + 0.01 as written. That rule leaves power near or under 0.5 by construction. Lead to decide. made by the build agent, change freely.
- 2026-11-05. Placebo arm permutes the arm columns within block. made by the build agent, change freely.
- 2026-11-05. Scores are the mean out-of-fold probability over repeats. Repeat 0 is the deterministic GroupKFold. made by the build agent, change freely.
- 2026-11-05. Holm adjustment uses the bootstrap share of draws at or below zero over the exploratory arms. made by the build agent, change freely.
- 2026-11-05. Frozen rows come from the NISAR samples files with repeated decoys dropped by the dedupe key. 9t pits give 4,881 rows, 489 targets. made by the build agent, change freely.
