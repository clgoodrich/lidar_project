# 7.4 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. The builder receives a comma list of the admitted tiles, never a folder glob (7.4-01). Made by the review-fix agent, change freely.
- 2026-11-06. A `--features` stack must match the declared CRS. The declared CRS is `--crs`, else EPSG:6346. Both must be projected in metres (7.4-02). Made by the review-fix agent, change freely.
- 2026-11-06. `--lidar` tiles must already be in the builder output CRS (EPSG:6346). The tool does not reproject them. Made by the review-fix agent, change freely.
- 2026-11-06. Tiles in feet are refused. Framework section 6 asks for explicit conversion. That needs reprojection in the builder path, which is not wired. Made by the review-fix agent, change freely.
- 2026-11-06. A CRS record that cannot be parsed is a refusal. `--crs` is never used to replace it. Made by the review-fix agent, change freely.
- 2026-11-06. Known wells are checked before prediction. A missing coordinate, a vector file with no CRS, or x/y that look like degrees exit 2. lon/lat columns need `--known-wells-crs`. Made by the review-fix agent, change freely.
- 2026-11-06. `--calibration` may be given once per class. A file is matched by its model hash. A file that matches no model is refused. Made by the review-fix agent, change freely.
- 2026-11-06. `--model both` refuses a single `--k-per-km2` and needs `--k-per-km2-pit` and `--k-per-km2-pad`. The provenance records each budget and their sum. See Needs user decision. Made by the review-fix agent, change freely.
- 2026-11-05. The tool is `src/_agency_cli_candidates.py` with program name wells_cli, not `tools/wells_cli.py`. The build was scoped to this folder. Made by the build agent, change freely.
- 2026-11-05. Validity checks read tiles with laspy. Derivatives are built by the repo builder, which calls the PDAL CLI. Made by the build agent, change freely.
- 2026-11-05. Ground density is class-2 points over occupied 1 m cells. Void fraction is the share of 0.5 m cells inside occupied cells with no ground return. Made by the build agent, change freely.
- 2026-11-05. The frozen model per class is the mean of the five fold models (pit unet_cv5, pad unet_cv5_iso) until 3.0 and P1 name the final one. Made by the build agent, change freely.
- 2026-11-05. The output list is capped at 40 candidates per km2 of valid scored area by default. Made by the build agent, change freely.
- 2026-11-05. The 27 of 424 context line is parsed from `docs/iterations/LEADERBOARD.md` at run time. Made by the build agent, change freely.
- 2026-11-05. A checkpoint hash that differs from the manifest exits with code 3 and writes no candidates. Made by the build agent, change freely.
- 2026-11-05. KML holds one point per candidate in EPSG:4326 with the candidate label in the description. Made by the build agent, change freely.
- 2026-11-05. Local calibration is isotonic regression. Made by the build agent, change freely.

## Needs user decision

- 2026-11-06. Is the review budget K one total for pits and pads together, or one budget per class? The framework says only that K "caps the output list". The transfer evidence reports recall at 40 per km2 for each class on its own. A shared total also needs a rule to merge two score scales into one list. Until this is decided, `--model both` needs explicit per-class budgets.
