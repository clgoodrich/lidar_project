# P1 decisions

Newest first. One line per decision, with the date and who made it.

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
