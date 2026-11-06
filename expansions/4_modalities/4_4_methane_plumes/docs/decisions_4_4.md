# 4.4 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-06. Review fix 4.4-01. The tail gate refuses extrapolation. When the best-case limit lies beyond a declared multiple of the largest observed rate, the tail verdict is `not identifiable by extrapolation`. The multiple is `m0.tail_max_extrapolation_multiple`. It is null, so any limit above the largest observed rate is refused. Made by the review-fix agent, change freely.
- 2026-11-06. Tail success now needs the lower bound of the expected exceeding count to reach one well. The old check `lower bound > 0` was always true. Made by the review-fix agent, change freely.
- 2026-11-06. Tail bootstrap draws with a failed fit are counted (SH-01). Any undefined draw makes that interval undefined and the tail gate inconclusive. The share is reported as `undefined_share`. Made by the review-fix agent, change freely.
- 2026-11-06. M3 rate ratio. A resample where wells or controls have no source has no finite Poisson estimate (quasi-separation). Such draws are undefined, so the verdict is inconclusive. An exact conditional interval (Clopper-Pearson on the well share of counts, exposure-adjusted) is reported beside it. It ignores clustering by cell, so it does not set the verdict. Made by the review-fix agent, change freely.
- 2026-11-06. M0 rerun. The small-well verdict stays CLOSE. The mean and aggregation gates are unchanged. The tail stays inconclusive because per-well rates are not on file. Made by the review-fix agent.

## Needs user decision

- Tail extrapolation multiple (`m0.tail_max_extrapolation_multiple`). How far past the largest measured rate a fitted tail may be read. Null means no extrapolation. With Kang-like rates (largest about 0.09 kg/h) against the 9 kg/h best-case limit the multiple is about 100.
- Whether the exact conditional rate ratio may decide M3 when separation leaves the cell bootstrap undefined.


- 2026-11-05. Scripts live in this expansion's `src/`, not in `notebooks/wellsight_v2/s5_eval/`. Outputs go to `results/<run_id>/` here, not `data/9t/results/methane/`. Made by the build agent, change freely.
- 2026-11-05. Best-case factor 10 and closure ratio 100 are the framework's proposed defaults, kept in `config_4_4.json`. Made by the build agent, change freely.
- 2026-11-05. The mean and aggregation gates use the best-case limit. That errs toward PROCEED. Made by the build agent, change freely.
- 2026-11-05. Wells per footprint count distinct coordinates. DEP stacks whole leases on one point (41 records at one point in Venango). Raw records are a sensitivity row. Made by the build agent, change freely.
- 2026-11-05. The verdict is CLOSE only when the mean and aggregation gates both fail. Made by the build agent, change freely.
- 2026-11-05. The tail gate uses the largest abandoned-well scenario (970,000), so it errs toward PROCEED. Made by the build agent, change freely.
- 2026-11-05. The tail fits are a lognormal and a log-logistic. The log-logistic stands in for the heavy-tail alternative. Made by the build agent, change freely.
- 2026-11-05. Plumes without a source-location radius are rejected. The plume footprint is never used as that radius. Made by the build agent, change freely.
- 2026-11-05. Plumes join one source when their centres lie within the larger of their two radii. Made by the build agent, change freely.
- 2026-11-05. The rate ratio is a Poisson model fitted by hand (IRLS), because statsmodels is not installed. Offset is log usable overpasses per 5 km cell. Interval by cell bootstrap. Made by the build agent, change freely.
- 2026-11-05. Useful rate ratio 2.0 is a placeholder for the user decision. Made by the build agent, change freely.
