# 6.3 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Negative centres keep out of a declared radius around every truth pit. `train.neg_truth_exclusion_m` null means the 30 m window jitter. Random draws near truth are redrawn, so both arms keep equal counts. Review 6.3-01. Made by the fix agent, change freely.
- 2026-11-06. Audit reads go through `ek.require_audit`. Training and sampling exclude roles audit and buffer. The pooled score uses role audit only. A missing audit file stops the run unless `--allow-no-audit`, which labels the output exploratory. Made by the fix agent, change freely.
- 2026-11-06. The split is read through the P1 readers in expkit. Role buffer gets no row. Made by the fix agent, change freely.
- 2026-11-06. The class-mode label raster carries a JSON sidecar with the base raster sha256 and a polygon hash. Any change forces a re-burn. Made by the fix agent, change freely.
- 2026-11-06. Pooled recall counts hits only on truth whose centroid is in an audit block, in that truth's block. Truth elsewhere is still matched so it cannot be claimed twice. Made by the fix agent, change freely.
- 2026-11-05. Confuser mode defaults to `class`, a fourth output class like road drainage. Mode `bg` keeps confusers as background and changes sampling only. Made by the build agent, change freely.
- 2026-11-05. Only the confuser arm gets the extra class. Baseline and random arms keep the three pit classes. Made by the build agent, change freely.
- 2026-11-05. The random arm draws the same count of centres uniformly inside the same training blocks. Made by the build agent, change freely.
- 2026-11-05. Normalisation is fitted per fold on 200 isolated training windows. Made by the build agent, change freely.
- 2026-11-05. Audit blocks are scored with the mean of the five fold models, since no fold trained on them. Made by the build agent, change freely.
- 2026-11-05. Checkpoints and rasters go under the expansion `models/` folder (git-ignored), not `data/9t/models/pit/unet_confuser_cv5/`, because the build may not edit `.gitignore`. Made by the build agent, change freely.
- 2026-11-05. The useful confuser reduction defaults to 0 per km2 (the framework gate text). The recall margin delta has no default and the scorer refuses until it is set. Made by the build agent, change freely.
- 2026-11-05. The sample draws from the `undecided` and `matched` candidate layers. Unmatched is not negative. Made by the build agent, change freely.
- 2026-11-05. Per-block candidate extraction reads a 100 m padded window so a blob on a block edge is counted once. Made by the build agent, change freely.
- 2026-11-05. The trainer is a dry run unless `--train` is given. Made by the build agent, change freely.

## Needs user decision
- 2026-11-06. Confirm the negative exclusion radius. 30 m equals the window jitter. A larger radius removes more confuser labels near pits.
