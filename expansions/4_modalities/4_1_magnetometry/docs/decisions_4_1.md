# 4.1 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Scripts live in this expansion's `src/`, not in `notebooks/wellsight_v2/s5_eval/` as the framework proposed. Outputs go to this expansion's `results/<run_id>/`. Made by the build agent, change freely.
- 2026-11-05. Era year is the earlier of SPUD_DATE and PERMIT_DAT. Made by the build agent, change freely.
- 2026-11-05. A DEP date at or before 1930 with no independent historic date is its own stratum `dated_pre_steel`. It is not early era. Made by the build agent, change freely.
- 2026-11-05. Line noise is the robust sigma of the along-line second difference over the square root of 6. A residual MAD was inflated about 18 times by the anomaly in the synthetic test. Made by the build agent, change freely.
- 2026-11-05. A pick needs its 3 sigma patch on two or more lines, or a peak at 6 sigma or more. A bare 3 sigma cut gave false picks on a blank grid. Made by the build agent, change freely.
- 2026-11-05. The site anomaly is the nearest pick within 5 m of the wellhead, or of the site point when no wellhead was surveyed. Made by the build agent, change freely.
- 2026-11-05. The pilot gate is incomplete, not passed, when a repeat line, a test object or a confuser identity is missing. Made by the build agent, change freely.
- 2026-11-05. Casing forward model is a vertical monopole at the casing top with an assumed pole strength of 500 to 5000 nT m2. To be replaced by a measured value. Made by the build agent, change freely.
