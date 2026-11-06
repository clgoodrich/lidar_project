# 6.1. CO2 storage and geothermal screening

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05).
**Plan.** [docs/plan_adj_co2_geothermal.md](docs/plan_adj_co2_geothermal.md)
**Framework.** [docs/fw_6_1_co2_geothermal.md](docs/fw_6_1_co2_geothermal.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_1.md](docs/decisions_6_1.md)
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

Tests. `python -m pytest -q expansions/6_adjacent/6_1_co2_geothermal/src/test_6_1.py -p no:cacheprovider` gives 4 passed.
Real-data check. S1 ran on the held 9t rasters into a scratch folder. 121 of 144 blocks are eligible. The overall void fraction is 0.452.
The chain runner is `src/_co2_screen_run_9t.py`. 6.4 calls the same chain with the hydrogen profile.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_co2_screen_lib.py` | shared | yes | nothing |
| `src/_co2_eligible_mask_9t.py` | S1 eligibility and blind zones | yes | annotation status from 3.0 (optional) |
| `src/_co2_screen_layers_9t.py` | S2 layer package | no | 5.6 well-level candidates `detector_output_pit_full_9t.gpkg`. Proposals, partner files, 4.6 and 7.5 layers are optional |
| `src/_co2_screen_summary_9t.py` | S3 limits sheet and summary | no | S2 and S4 outputs |
| `src/_co2_screen_counts_9t.py` | S4 descriptive counts | no | S2 output |
| `src/_co2_claim_audit_9t.py` | S5 claim audit | no | S3 output |
| `src/_co2_reader_check_9t.py` | S5 reader check and Q1 gate | template yes, gate no | reader answers (user step, at least 5 readers) |
| `src/_co2_screen_map_9t.py` | deliverable map | no | S2 output |
| `src/_co2_screen_run_9t.py` | chain runner | no | 5.6 candidates |
| `src/config_6_1.json` | inputs, schemas, profile co2 | yes | S0 scope doc and partner are user steps |
