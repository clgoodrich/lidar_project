# 6.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. The partner is a declared hypothetical until one is named. The screening area falls back to the 9t block extent. Made by the build agent, change freely.
- 2026-11-05. Eligibility rule is ground density of at least 2.0 points per m2 per block and void fraction of at most 0.50. It is a chosen rule, not the QL2 definition. Made by the build agent, change freely.
- 2026-11-05. Scripts live in `src/` with the `_co2_` prefix, not in `notebooks/wellsight_v2/s7_analysis/` as the framework names them. Made by the build agent, change freely.
- 2026-11-05. Each package run writes to `data/9t/results/screening/<run_id>/` (fw_00 run folders), not to a flat folder. Made by the build agent, change freely.
- 2026-11-05. Records are the DEP export inside the screening area plus a 500 m buffer. The framework gives no buffer value. Made by the build agent, change freely.
- 2026-11-05. Candidates come only from the 5.6 well-level outputs. There is no fallback to the withdrawn leftover candidate file. Made by the build agent, change freely.
- 2026-11-05. When 5.6 proposals are absent the link flag is a record within 50 m, and the layer says so in `link_basis`. Made by the build agent, change freely.
- 2026-11-05. Banned phrases match whole words. The fixed limits sentences and reader questions are exempt from the audit. Made by the build agent, change freely.
- 2026-11-05. 6.4 reuses this pipeline through hooks. No hydrogen logic sits in the 6.1 scripts. Made by the build agent, change freely.
