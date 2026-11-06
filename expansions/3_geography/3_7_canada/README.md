# 3.7. Canada

**Status.** Plan only. Nothing here has been run. Tier A (full design, data assumed).
**Plan.** [docs/plan_geo_canada.md](docs/plan_geo_canada.md)
**Framework.** [docs/fw_3_7_canada.md](docs/fw_3_7_canada.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_7.md](docs/decisions_3_7.md)
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

Defaults applied (2026-11-06, user said take defaults). Margin 0.03 recall per province. Void cap 0.5 (was 0.9). Holm over six primaries (pit and pad in ab1, bc1, on1). The provisional transfer model is the five-fold 9t ensemble for pit and pad (fold_mean) with sha256 per fold.

Review repair (2026-11-06). The shifted-set null uses a torus shift, so it is computable at 100 spread records (999 of 999 kept, 0 before). A thin null is reported as not computable. The transfer checkpoint is an explicit unset config key. Open user decisions are in `docs/decisions_3_7.md`.

Built by the build agent. The shared regional-transfer code is `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py`. Expansions 3.4 to 3.8 import it. Stage commands that every region shares are its subcommands. Assumed inputs and their schemas are in `src/config_3_7.json`. A missing assumed input stops a script with a message that names the input, its schema and the VERIFY step. Decisions are in `docs/decisions_3_7.md`. Run the tests with `python -m pytest -q expansions/3_geography/3_7_canada/src/test_3_7.py -p no:cacheprovider`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_can_inventory_rows.py` | S0 inventory pull, V0 and V1 ladder | no | provincial well and orphan lists under `data/_source/reference/wells_can/<p>/` |
| `src/_can_tile_probe.py` | S1 one tile per province | no | one tile per province under `data/_source/lidar/lidar_can/<p>/` |
| `src/_can_window_rank.py` | S2 window rule and S7 province ranking | no | `data/raw/can_province_criteria.csv` |
| `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py derive / infer / agree / score --exp 3.7` | S3 to S5 per province | no | windows set in the config, labels |
| `src/_can_record_assoc.py` | S6 record association with shifted-set null | no | S0 rows, truth, blocks, frozen score |
| `src/test_3_7.py` | smoke tests | yes. 4 passed |  |
| `src/config_3_7.json` | assumed sources per province |  | D-CA-N1 to D-CA-N4 are null |
