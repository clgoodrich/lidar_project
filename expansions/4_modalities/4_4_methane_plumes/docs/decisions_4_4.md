# 4.4 decisions

Newest first. One line per decision, with the date and who made it.


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
