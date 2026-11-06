# 5.2 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Outputs go to this expansion's `results/` and `data/` folders, not `data/9t/results/era/`. Made by the build agent, change freely.
- 2026-11-05. The 2022 orphan CSV has no spud field. The S0 cohort check compares sentinel shares inside the 2026 export by 2022-list membership. Made by the build agent, change freely.
- 2026-11-05. Stratum priority is dated_record, then dated_map, then sentinel, then undated_other. A labelled well takes its stratum from its label and keeps the record stratum in `record_stratum`. Made by the build agent, change freely.
- 2026-11-05. Position-only marks link to the nearest well within their stated error. They are kept with `link_flag = position_only` and left out of the primary. Made by the build agent, change freely.
- 2026-11-05. An interval that crosses the 1955 to 1956 boundary has no binary early label. It still enters the censored fit. Made by the build agent, change freely.
- 2026-11-05. Wells link to the nearest annotated pad within 30 m, the 4.6 nominal error. Made by the build agent, change freely.
- 2026-11-05. M0 uses easting, northing, their squares and their product as the smooth location term. Made by the build agent, change freely.
- 2026-11-05. The AFT uses a ridge penalty of 1.0 on standardised features. Missing features are filled with the training-fold median. Made by the build agent, change freely.
- 2026-11-05. The label-noise check reassigns a share p of intervals to random other wells and refits. p is 0.05, 0.10 and 0.20 until S3 gives an interval. Made by the build agent, change freely.
- 2026-11-05. Under 15 blocks the primary adds a paired block-swap permutation range. Made by the build agent, change freely.
- 2026-11-05. Support uses the 1st to 99th percentile of dated wells per feature and a 20-bin histogram overlap. Made by the build agent, change freely.
- 2026-11-05. `--provisional-folds` builds seeded block folds when the P1 split file is absent. Runs that use it are labelled exploratory. Made by the build agent, change freely.

## 2026-11-06 review fixes

- 2026-11-06. P1-01. The split CSV is read with `ek.read_split_csv`. P1 writes `val` and `heldout`. The reader maps them to `inner_val` and `held_out`. A split with no held-out rows stops the run.
- 2026-11-06. P2-01. The audit file is read only through `ek.require_audit`. Audit and buffer blocks both leave the model table. A missing file stops a confirmatory run. With `--provisional-folds` the run is labelled "no audit exclusion, exploratory".
- 2026-11-06. A bootstrap draw with one class has no AUC. It is kept and counted. The summary reports `undefined_share` for the primary, each arm, the permutation range and the label-noise check. No share is tolerated, so any undefined draw gives an inconclusive decision.

## Decisions

- 2026-11-06. model.max_undefined. User accepted the default 0 ("take defaults"). Change freely. A null value is now refused. Test test_max_undefined_is_decided_zero.

## Needs user decision

- None open.
