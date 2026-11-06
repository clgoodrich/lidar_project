# 4.1 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-06. Review fix 4.1-01. The outcome now crosses identity with the anomaly result. A confirmed well with no anomaly is `confirmed_well_missed`. A blank with a pick is `blank_with_pick`. Made by the review-fix agent, change freely.
- 2026-11-06. The pilot gate fails on any pick at a blank and on any confirmed well without an anomaly in a steel-casing stratum. Misses in early_era, unknown_date and dated_pre_steel are listed, not failed, because wood or pulled casing has no steel. Made by the review-fix agent, change freely.
- 2026-11-06. A historic record places a well in early_era only when its year_built_max (or source_date) is at or before 1930. A historic file with neither column is refused. Made by the review-fix agent, change freely.
- 2026-11-06. `dated_pre_steel` is now a valid pilot stratum. The site frame drops records with no permit and duplicate permits explicitly and counts them. The well rows are checked against the raw box count. A site_id collision across sources now raises. Made by the review-fix agent, change freely.
- 2026-11-06. S0 site frame rerun on 9t. Counts unchanged (1,068 wells, no duplicate or blank permits). Made by the review-fix agent.

- 2026-11-05. Scripts live in this expansion's `src/`, not in `notebooks/wellsight_v2/s5_eval/` as the framework proposed. Outputs go to this expansion's `results/<run_id>/`. Made by the build agent, change freely.
- 2026-11-05. Era year is the earlier of SPUD_DATE and PERMIT_DAT. Made by the build agent, change freely.
- 2026-11-05. A DEP date at or before 1930 with no independent historic date is its own stratum `dated_pre_steel`. It is not early era. Made by the build agent, change freely.
- 2026-11-05. Line noise is the robust sigma of the along-line second difference over the square root of 6. A residual MAD was inflated about 18 times by the anomaly in the synthetic test. Made by the build agent, change freely.
- 2026-11-05. A pick needs its 3 sigma patch on two or more lines, or a peak at 6 sigma or more. A bare 3 sigma cut gave false picks on a blank grid. Made by the build agent, change freely.
- 2026-11-05. The site anomaly is the nearest pick within 5 m of the wellhead, or of the site point when no wellhead was surveyed. Made by the build agent, change freely.
- 2026-11-05. The pilot gate is incomplete, not passed, when a repeat line, a test object or a confuser identity is missing. Made by the build agent, change freely.
- 2026-11-05. Casing forward model is a vertical monopole at the casing top with an assumed pole strength of 500 to 5000 nT m2. To be replaced by a measured value. Made by the build agent, change freely.
