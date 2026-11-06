# P2. Audit set and training history

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_prereq_audit_set.md](docs/plan_prereq_audit_set.md)
**Framework.** [docs/fw_p2_audit_set.md](docs/fw_p2_audit_set.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_p2.md](docs/decisions_p2.md)
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

Built by the build agent. Tests. `python -m pytest -q expansions/0_prerequisites/p2_audit_set/src/test_p2.py -p no:cacheprovider` (8 passed).
Nothing is frozen. Freezing an audit set is a user decision (`--freeze`). Dry runs wrote to `data/interim/` in this folder.

| Script | Stage | Runnable now with held data | Missing or pending |
|---|---|---|---|
| `src/_audit_exposure_ledger_9t.py` | S0 exposure ledger and `audit_set_history.md` | yes, ran as a dry run (144 blocks, 12 to 15 model uses each) | uses marked unknown need a person to fill `config_p2.json` |
| `src/_audit_draw_blocks_9t.py` | S1 draw, buffer, KS, split overlap. S5 freeze | dry run yes, ran (17 blocks). Freeze no | user decision to freeze. Needs the P1 S4 buffer |
| `src/_audit_guard_lib.py` | S2 guard and CLI check | yes | frozen audit file. Wiring into `_pad_unet_iso_cv5.py` and other trainers outside this folder is for the lead |
| `src/_audit_discovery_draw.py` | S3 discovery sample | no | assumed input. A block frame `data/<area>/results/transfer/<area>_blocks.gpkg` outside 9t |
| `src/_audit_reserve_warren.py` | S4 reserve Warren | no | assumed input. `data/warren/results/transfer/warren_blocks.gpkg` with a `role` column (from 3.1) |
| `src/config_p2.json` | settings and assumed inputs | yes | none |
| `src/test_p2.py` | tests, including training on an audit block must fail | yes | none |

Dry-run products, all in `expansions/0_prerequisites/p2_audit_set/data/interim/`.
`audit_blocks_9t_dryrun.csv`, `audit_draw_9t_dryrun.json`, `block_exposure_9t.csv`, `block_exposure_scripts_9t.csv`, `audit_set_history_dryrun.md`.
