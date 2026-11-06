# P2 decisions

Newest first. One line per decision, with the date and who made it.

## Needs user decision

- Freezing this file is still a user step.

## Decisions

- 2026-11-06. Pad audit set. User accepted the default of a separate pad draw from the pad-bearing blocks, dry run only ("take defaults"). Change freely.
- 2026-11-06. `--task pad` draws 19 of 129 pad-bearing blocks at share 0.15, seed 20261104, buffer 150 m window mode. Config block `draw_9t_pad`. Two of the 19 are also in the pit dry-run audit set (84 and 137). Nothing is frozen. Made by the review-fix agent, change freely.

- 2026-11-06. Review fix P2-03. Window checks use the audit file's buffer. A smaller explicit buffer is refused. Made by the review-fix agent, change freely.
- 2026-11-06. Review fix P2-03. Held-out lists are checked against the audit set too. An audit id missing from the blocks layer is an error. Made by the review-fix agent, change freely.
- 2026-11-06. The 9t audit set is scoped to pits. Its draw frame is the pit-bearing blocks, and the header says so. A pad reader is refused. Pads may still exclude the blocks from training. Made by the review-fix agent, change freely.
- 2026-11-06. The Warren reservation reprojects output extents before the overlap test. Made by the review-fix agent, change freely.
- 2026-11-05. Scripts live in `src/` of this folder. The framework's `notebooks/wellsight_v2/_audit_guard.py` path is superseded by `src/_audit_guard_lib.py`. Made by the build agent, change freely.
- 2026-11-05. The minimum of 3 audit blocks applies to each density tercile and each slope tercile, not to each of the 9 joint strata. Nine strata at 3 each needs 27 blocks, above the 17 that 15% gives. Made by the build agent, change freely.
- 2026-11-05. Allocation across joint strata is proportional by largest remainder. Terciles use ranks, ties broken by block id. Made by the build agent, change freely.
- 2026-11-05. Default buffer mode is `window`. Training windows may not come within the buffer of an audit block, and neighbouring blocks stay in training. The framework's whole-block exclusion (`block` mode) leaves 30% of pit blocks at a 100 m buffer, so it is reported only. Made by the build agent, change freely.
- 2026-11-05. The frozen hash is read from a `.sha256` sidecar written at freeze time and, when the file is in git, from the committed blob at HEAD. A file with neither is refused. Made by the build agent, change freely.
- 2026-11-05. Audit and buffer rows share one CSV with a `role` column. Header comment lines carry seed, share, buffer and mode. Made by the build agent, change freely.
- 2026-11-05. Every block a model did not hold out counts as used by it. Unknown uses count as used. Made by the build agent, change freely.
- 2026-11-05. The 20 km2 discovery sample cannot come from 9t (20.25 km2 in total, all used). The script takes another area's block frame. Made by the build agent, change freely.
- 2026-11-05. The Warren reservation refuses if any probability raster or candidate layer under `data/warren/` overlaps a reserved block. Made by the build agent, change freely.
