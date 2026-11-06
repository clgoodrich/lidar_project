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

## Build status (2026-11-05)

Tests. `python -m pytest -q expansions/6_adjacent/6_6_sar_viewshed/src/test_6_6.py -p no:cacheprovider` gives 10 passed. They include plane, wall, hill, pit, canopy block, nodata, edge and void cases, and 1,000 random sweep against brute-force pairs with zero disagreements outside half-cell tolerance.
Real-data checks. `gridcheck` passed on 9t (`results/tables/sar_grid_check_9t.json`). A 500 m O1 benchmark on 9t took 11.6 s and 179 MB peak (scratch run).
Not a well result. Keep it out of well reports.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_sar_viewshed_tool.py` | S1 engine and CLI, S3 benchmark, grid check | yes | nothing for O0 and O1. O2 k values are starting guesses |
| `src/_sar_viewshed_validate.py` | S4 sight-check validation | no | field sight checks `data/9t/source/sar_field/sight_checks_9t.csv` and acceptance level A |
| `src/_sar_walk_time_validate.py` | S5 GNSS walk test | no | GNSS tracks `data/9t/source/sar_field/walk_tracks_9t.csv` and the time tolerance |
| `src/config_6_6.json` | inputs, heights, opacity, cost, validation | yes | A and time tolerance are user decisions |
