# 6.4. Hydrogen storage screening

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05).
**Plan.** [docs/plan_adj_hydrogen.md](docs/plan_adj_hydrogen.md)
**Framework.** [docs/fw_6_4_hydrogen.md](docs/fw_6_4_hydrogen.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_4.md](docs/decisions_6_4.md)
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

Tests. `python -m pytest -q expansions/6_adjacent/6_4_hydrogen/src/test_6_4.py -p no:cacheprovider` gives 6 passed.
6.4 is a profile of the 6.1 pipeline. It adds a record-only penetration flag, an optional monitoring layer and extra count rows through hooks. No 6.1 script holds hydrogen logic.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_h2_screen_run_9t.py` | S1 profile, S2 package, S3 reader check, S4 counts | no | 5.6 candidates (as 6.1) and `reservoir_seal_tops.csv` from the partner |
| `src/config_6_4.json` | hydrogen profile, inputs, limits 8 to 10, questions | yes | partner, field boundary and regime are user decisions |
