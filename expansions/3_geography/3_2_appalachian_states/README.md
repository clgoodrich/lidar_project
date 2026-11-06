# 3.2. Ohio, West Virginia, New York, Kentucky

**Status.** Plan only. Nothing here has been run. Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded or scored.
**Plan.** [docs/plan_geo_appalachian_states.md](docs/plan_geo_appalachian_states.md)
**Framework.** [docs/fw_3_2_appalachian_states.md](docs/fw_3_2_appalachian_states.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_2.md](docs/decisions_3_2.md)
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
