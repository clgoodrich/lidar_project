# 3.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Proposal cutoff is the frozen archival rule (0.35 on 9t), not the 0.10 in fw_00 section 4. At 0.10 fold 0 recall before any budget is 0.553, against 0.922 at the archival cutoff. Made by the build agent, change freely.
- 2026-11-05. Heavy rasters go to `data/processed/<area>/05/` in this expansion, not `data/<area>/derived/05/`, until the lead adds a `.gitignore` rule there. Made by the build agent, change freely.
- 2026-11-05. Small tables go to `results/tables/<area>/` in this expansion, not `data/<area>/results/transfer/`. Made by the build agent, change freely.
- 2026-11-05. The 9t reference is the 3.3 S1 rebuild of the CV5 out-of-fold recall (provisional, original sampler). Swap to the P1 isolated table when it exists. Made by the build agent, change freely.
- 2026-11-05. Matching is greedy one-to-one by IoU as fw_00 says. The CV5 code matches greedy by score. Made by the build agent, change freely.
- 2026-11-05. K is round(40 x km²) as in `ek.recall_at_k`. The archival sweep floors it per fold. Made by the build agent, change freely.
- 2026-11-05. A hit is credited to the block that holds the truth feature. Made by the build agent, change freely.
- 2026-11-05. Adaptation is one contiguous strip from a seeded side. It is dropped when the strip is under 7 km². Made by the build agent, change freely.
- 2026-11-05. `--provisional-buffer` uses 192 m (pad patch support). It is not a derived buffer. Made by the build agent, change freely.
- 2026-11-05. Density rule is the 9t block 5th percentile (1.91 ground points per m²). Blocks under it form a low-density stratum. Made by the build agent, change freely.
- 2026-11-05. Model policy is the mean probability of the five fold checkpoints. Made by the build agent, change freely.
- 2026-11-05. Rasters in another CRS are warped to EPSG:6346 on read with an alert. Warren 1 m slope is EPSG:26917. Made by the build agent, change freely.
- 2026-11-05. roughness_11 is the builder roughness formula with an 11-cell window at 0.5 m. It matches the 9t band exactly. Made by the build agent, change freely.
- 2026-11-05. The committed preregistration is expected at `docs/prereg_xfer_<area>.md` in this expansion. The scorer refuses to run without it. Made by the build agent, change freely.
