# P1 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- Freezing this file is still a user step.

## Decisions

- 2026-11-06. Buffer mode of the split. User accepted the default `window`. Train blocks keep their role and the sampler rejects windows within the buffer of held-out ground ("take defaults"). Change freely.
- 2026-11-06. Noise band of the range rule. User accepted the default 2 sigma of the tail lags ("take defaults"). Change freely.
- 2026-11-06. The P1 dry run was rerun in window mode. Train blocks per fold are pit 72, 71, 76, 74, 75 (was 23, 12, 24, 20, 22 in block mode) and pad 84, 82, 82, 82, 83 (was 32, 16, 15, 16, 20). The isolated sampler leaks 0 windows in every fold. The block-mode dry-run files moved to data/interim/dryrun/block_mode_20261106/. Made by the review-fix agent.

- 2026-11-06. Review fix P1-04. The buffer uses `range_m_upper_bound`, the first lag at 95% of the sill plus 2 sigma of the tail lags. A first lag at or above it gives the first lag as the bound with `range_below_first_lag`. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix P1-03. The pad buffer is derived from the historical per-fold pad rasters, each taken inside its own held-out blocks. Pad class 1, the same receptive field rule, patch 384. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix P1-02. The split writer applies the derived buffer per task and records the moved blocks per fold. The `buffer` role is never trained or scored and gets no CSV row. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix P1-01. The split CSV uses the JSON role words. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix P1-05. Exclusions must name an audit file and its sha256. A bare string is refused. Made by the review-fix agent, change freely.
- 2026-11-05. Scripts live in `src/` of this folder, not in `notebooks/wellsight_v2/`. The framework's deliverable script paths are superseded. Made by the build agent, change freely.
- 2026-11-05. The historical trainers are read through imports only. They were not edited. Made by the build agent, change freely.
- 2026-11-05. One split file holds both tasks (pit and pad) with a content hash over both. Made by the build agent, change freely.
- 2026-11-05. `--exclude-audit` removes P2 audit blocks from every role after the historical fold assignment. Folds are not reassigned, so held-out lists stay subsets of the historical ones. Made by the build agent, change freely.
- 2026-11-05. Buffer is receptive-field radius plus semivariogram range (framework formula). The protocol's patch-support variant (half patch plus range) is reported beside it. Made by the build agent, change freely.
- 2026-11-05. Semivariogram is exact over all pairs on a 5 m grid by FFT. Sill is the mean of the last quarter of lags. Range is the first lag at 95% of the sill. Made by the build agent, change freely.
- 2026-11-05. The receptive field is measured from input-gradient support of the real UNet, not derived by hand. Made by the build agent, change freely.
- 2026-11-05. Fold-local normalisation reads each of the 20,000 windows at 32 by 32 pixels (nearest) to bound the read cost. Window origins are saved with the statistics for the trace check. Made by the build agent, change freely.
- 2026-11-05. Validation windows must lie wholly inside inner-validation blocks. The sampler forbids held-out and train blocks for them. Made by the build agent, change freely.
- 2026-11-05. The leakage test forbids held-out and inner-validation blocks and counts positive-area overlap only. Shared edges are not leaks. Made by the build agent, change freely.
- 2026-11-05. The isolated out-of-fold mosaic is float32, not uint8. Made by the build agent, change freely.
- 2026-11-05. The NaN-position count in S0 (`--consistency`) is exploratory. It never becomes a recovered role. Made by the build agent, change freely.
