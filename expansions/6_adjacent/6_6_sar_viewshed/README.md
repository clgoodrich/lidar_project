# 6.6. Search and rescue viewshed

**Status.** Plan only. Nothing here has been run. Tier A by instruction (user, 2026-11-05, stop deferring).
**Plan.** [docs/plan_adj_sar_viewshed.md](docs/plan_adj_sar_viewshed.md)
**Framework.** [docs/fw_6_6_sar_viewshed.md](docs/fw_6_6_sar_viewshed.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_6.md](docs/decisions_6_6.md)
**Shared rules.** [fw_00_common.md](../../_shared/fw_00_common.md) and [protocol_gates_and_metrics.md](../../../docs/plans/protocol_gates_and_metrics.md). The protocol wins on any conflict.

## Folders

| Folder | Holds | In git |
|---|---|---|
| `docs/` | plan, framework, decisions log | yes |
| `src/` | scripts for this expansion | yes |
| `data/raw/` | inputs as received. Never edited | no |
| `data/interim/` | intermediate products | no |
| `data/processed/` | model-ready inputs | no |
| `models/` | weights and checkpoints | no |
| `results/figures/` | small figures | yes |
| `results/tables/` | small tables and JSON | yes |

Products for a new study area go to `data/<area>/` as everywhere else, not here.
Scripts resolve paths with `path_for("expansions")` (key in `config/paths.toml`). Add the import path with
`sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "notebooks/wellsight_v2"))`.
Anything at or above 100 MB goes under an ignored folder. Every run gets an entry in `docs/analysis_log.md`.

## Build status (2026-11-06)

Tests. `python -m pytest -q expansions/6_adjacent/6_6_sar_viewshed/src/test_6_6.py -p no:cacheprovider` gives 20 passed. They include plane, wall, hill, pit, canopy block, nodata, edge and void cases, and 1,000 random sweep against brute-force pairs with zero disagreements outside half-cell tolerance.
Review fixes on 2026-11-06. Visibility has three states, visible, hidden and unknown. Unobserved terrain on a sightline (no surface value, a void cell, or O2 canopy with no CHM value) makes the call unknown unless a known obstacle already hides the target. A void target cell is unknown. The cumulative map keeps unknown cells apart and never counts them as seen by nobody. The walk test smooths each GNSS track and thins it by displacement, so 1 Hz fixes with 2 to 3 m error give the right length. The GNSS band in sight checks is two-sided. A pair whose call flips inside the band is ambiguous and not scored. Fine to coarse cell mapping for cost and route now uses cell centres.
Real-data rerun on 2026-11-06. 500 m viewshed from 621750, 4595250 on 9t, scratch runs. O0 visible cells 123,895 to 44. Unknown cells 0 to 1,540,127 (1,408,436 void targets that were masked before, plus 131,691 cells behind void). O1 visible cells 1,864 to 36. Unknown cells 0 to 1,410,893. Hidden pockets unchanged (16 for O0, 12 for O1). The observer stands in a void patch, so almost every ray starts across unobserved ground. Wall time 20 s for O0.
Real-data checks. `gridcheck` passed on 9t (`results/tables/sar_grid_check_9t.json`). A 500 m O1 benchmark on 9t took 11.6 s and 179 MB peak (scratch run).
Not a well result. Keep it out of well reports.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_sar_viewshed_tool.py` | S1 engine and CLI, S3 benchmark, grid check | yes | nothing for O0 and O1. O2 k values are starting guesses |
| `src/_sar_viewshed_validate.py` | S4 sight-check validation | no | field sight checks `data/9t/source/sar_field/sight_checks_9t.csv` and acceptance level A |
| `src/_sar_walk_time_validate.py` | S5 GNSS walk test | no | GNSS tracks `data/9t/source/sar_field/walk_tracks_9t.csv` and the time tolerance |
| `src/config_6_6.json` | inputs, heights, opacity, cost, validation | yes | A and time tolerance are user decisions |
