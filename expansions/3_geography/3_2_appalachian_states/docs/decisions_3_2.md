# 3.2 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates ny_alg, oh_wash, ky_lee, wv_ple (the four primary windows). Companion windows are descriptive, secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- 2026-11-06. Margin per window. User accepted the default 0.03 recall ("take defaults"). Change freely.
- 2026-11-06. Review fix pass (F02 F03 F08 inherited). Made by the review-fix agent, change freely.
  - 3.2 keeps no matcher of its own. Window scoring runs through the 3.1 stages and so through the 3.0 scorer.
  - The scoring reference is the 3.0 tables. The 3.3 S1 blocks CSV stays only for the projected-width design tool.
- 2026-11-05. Status harmonisation uses regex rules in `config_3_2.json`, first match wins. A recorded plug date outranks the status code. Original codes are kept. Made by the build agent, change freely.
- 2026-11-05. NY, OH and WV coordinates are taken as NAD83 until each data dictionary is read. KY uses the KGS NAD83 columns. Made by the build agent, change freely.
- 2026-11-05. A record belongs to a window by the catalogue lon/lat box. Made by the build agent, change freely.
- 2026-11-05. Union cover uses tile bounding boxes, an upper bound on true footprints. Made by the build agent, change freely.
- 2026-11-05. Windows have no internal adaptation role. Adaptation uses the companion window only (Q3). Test and audit split 80 to 20. Made by the build agent, change freely.
- 2026-11-05. N_min is a placeholder of 30 test blocks so the gate code runs. Made by the build agent, change freely.
- 2026-11-05. Per-window stages call the 3.1 scripts with this config instead of copies. The 3.1 blocks script clips blocks to the catalogue window box when the area names a window. Made by the build agent, change freely.
- 2026-11-05. The thinned arm keeps every point with one probability per tile, the same for all classes. Made by the build agent, change freely.
- 2026-11-05. The Ritchie window has a placeholder tile path. It is not in the rebuilt catalogue. Made by the build agent, change freely.
- 2026-11-05. Outputs stay in this expansion (`results/tables/`, `data/processed/`), not in `data/_source/reference/` or `data/<area>/`. Made by the build agent, change freely.

## Needs user decision
- None open. (2026-11-06)
