# 6.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. The score cutoff is per kind and equals ek.policy_for (pit 0.35, pad 0.525). It follows the 5.6 re-cut the user accepted ("take defaults"). The old single 0.50 re-imposed 0.50 on pits. Test test_cutoff_is_per_kind_policy. Made by the review-fix agent, change freely.
- 2026-11-06. The contract fixture runs the real 5.6 S0 writer. Only the pre-contract legacy fixture stays hand built, since no producer writes that shape now. Made by the review-fix agent, change freely.
- 2026-11-06. Full chain on 9t with the re-cut 5.6 output. Sites 1,690 to 1,764. Blind-zone sites 243 to 255. Within K 681. Claim audit 0 hits.
- 2026-11-06. Candidate sites are keyed by kind plus det_id (`site_uid`, for example `pad:17`). det_id alone is never the key. A file with a kind column must match the file it came from. Review 6.1-01. Made by the fix agent, change freely.
- 2026-11-06. 6.1 reads no 5.6 proposal file. 5.6 writes proposals into dated run folders and `proposals_56_9t.csv` had no producer. The link flag is a record within 50 m. Made by the fix agent, change freely.
- 2026-11-06. K is spent only inside the scored footprint. Blind-zone candidates get no rank and are never within K. Made by the fix agent, change freely.
- 2026-11-06. The DEP export has no depth. `TOTAL_MAXI` is empty in all 20,108 rows of `venango_wells_all.gpkg`. The counts sheet says no depth in records when the count is 0. Made by the fix agent, change freely.
- 2026-11-05. The partner is a declared hypothetical until one is named. The screening area falls back to the 9t block extent. Made by the build agent, change freely.
- 2026-11-05. Eligibility rule is ground density of at least 2.0 points per m2 per block and void fraction of at most 0.50. It is a chosen rule, not the QL2 definition. Made by the build agent, change freely.
- 2026-11-05. Scripts live in `src/` with the `_co2_` prefix, not in `notebooks/wellsight_v2/s7_analysis/` as the framework names them. Made by the build agent, change freely.
- 2026-11-05. Each package run writes to `data/9t/results/screening/<run_id>/` (fw_00 run folders), not to a flat folder. Made by the build agent, change freely.
- 2026-11-05. Records are the DEP export inside the screening area plus a 500 m buffer. The framework gives no buffer value. Made by the build agent, change freely.
- 2026-11-05. Candidates come only from the 5.6 well-level outputs. There is no fallback to the withdrawn leftover candidate file. Made by the build agent, change freely.
- 2026-11-05. When 5.6 proposals are absent the link flag is a record within 50 m, and the layer says so in `link_basis`. Made by the build agent, change freely.
- 2026-11-05. Banned phrases match whole words. The fixed limits sentences and reader questions are exempt from the audit. Made by the build agent, change freely.
- 2026-11-05. 6.4 reuses this pipeline through hooks. No hydrogen logic sits in the 6.1 scripts. Made by the build agent, change freely.
