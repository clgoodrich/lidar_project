# 7.4 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. The tool is `src/_agency_cli_candidates.py` with program name wells_cli, not `tools/wells_cli.py`. The build was scoped to this folder. Made by the build agent, change freely.
- 2026-11-05. Validity checks read tiles with laspy. Derivatives are built by the repo builder, which calls the PDAL CLI. Made by the build agent, change freely.
- 2026-11-05. Ground density is class-2 points over occupied 1 m cells. Void fraction is the share of 0.5 m cells inside occupied cells with no ground return. Made by the build agent, change freely.
- 2026-11-05. The frozen model per class is the mean of the five fold models (pit unet_cv5, pad unet_cv5_iso) until 3.0 and P1 name the final one. Made by the build agent, change freely.
- 2026-11-05. The output list is capped at 40 candidates per km2 of valid scored area by default. Made by the build agent, change freely.
- 2026-11-05. The 27 of 424 context line is parsed from `docs/iterations/LEADERBOARD.md` at run time. Made by the build agent, change freely.
- 2026-11-05. A checkpoint hash that differs from the manifest exits with code 3 and writes no candidates. Made by the build agent, change freely.
- 2026-11-05. KML holds one point per candidate in EPSG:4326 with the candidate label in the description. Made by the build agent, change freely.
- 2026-11-05. Local calibration is isotonic regression. Made by the build agent, change freely.
