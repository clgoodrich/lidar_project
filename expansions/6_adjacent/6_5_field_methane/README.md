# 6.5. Field methane screening

**Status.** Plan only. Nothing here has been run. Tier B.
**Plan.** [docs/plan_adj_field_methane.md](docs/plan_adj_field_methane.md)
**Framework.** [docs/fw_6_5_field_methane.md](docs/fw_6_5_field_methane.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_5.md](docs/decisions_6_5.md)
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

Tests. `python -m pytest -q expansions/6_adjacent/6_5_field_methane/src/test_6_5.py -p no:cacheprovider` gives 5 passed.
Review fix 6.5-01 on 2026-11-06. Unit and instrument errors now invalidate the visit with a reason. A ppm_m row on the point sampler, an instrument not in the registry, point and path instruments in one visit, or mixed units in one visit each set `valid` to False. The worked example sheet has no such rows, so its tables are unchanged.
The framework was brought to full depth (`docs/fw_6_5_field_methane.md`, 144 lines). The draft protocol is `docs/methane_field_protocol.md`.
The synthetic worked example is `results/tables/methane_example_sheet.csv`. The chain runs on it and the claim audit passes.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_methane_sheet_check.py` | S1 sheet check and visit validity | yes on the example | real crew sheets from 7.5 |
| `src/_methane_field_table.py` | S2 per visit and per site tables, worked example | yes on the example | real crew sheets, 7.5 site list for strata |
| `src/_methane_claim_audit.py` | S3 claim audit | yes on the example | nothing |
| `src/config_6_5.json` | instrument registry, protocol values, schema | yes | instrument, DL and stop threshold are VERIFY items |
| `docs/methane_field_protocol.md` | S0 protocol draft | yes | partner and safety reviewer approval |
