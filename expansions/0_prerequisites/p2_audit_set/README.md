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

## Build status (2026-11-06)

Review fixes on 2026-11-06 (adversarial review P2-03, the P2 minors, consolidated F05).
Tests. `python -m pytest -q -p no:cacheprovider expansions/0_prerequisites/p2_audit_set/src/test_p2.py` (13 passed).
The P1 round-trip test reads a P2-written audit CSV through `ek.read_audit` in a fresh process (`test_p1.py`).
Nothing is frozen. Freezing an audit set is a user decision (`--freeze`). Dry runs wrote to `data/interim/` in this folder.

| Script | Stage | Runnable now with held data | Missing or pending |
|---|---|---|---|
| `src/_audit_exposure_ledger_9t.py` | S0 exposure ledger and `audit_set_history.md` | yes, ran as a dry run (144 blocks, 12 to 15 model uses each) | uses marked unknown need a person to fill `config_p2.json` |
| `src/_audit_draw_blocks_9t.py` | S1 draw, buffer, KS, split overlap. S5 freeze | dry run yes, reran 2026-11-06 (same 17 blocks). Freeze no | user decision to freeze. Reads the pit buffer with `ek.read_buffer("pit")` |
| `src/_audit_guard_lib.py` | S2 guard and CLI check | yes | frozen audit file. Wiring into trainers outside this folder is for the lead |
| `src/_audit_discovery_draw.py` | S3 discovery sample | no | assumed input. A block frame `data/<area>/results/transfer/<area>_blocks.gpkg` outside 9t |
| `src/_audit_reserve_warren.py` | S4 reserve Warren | no | assumed input. `data/warren/results/transfer/warren_blocks.gpkg` with a `role` column (from 3.1) |
| `src/config_p2.json` | settings and assumed inputs | yes | none |
| `src/test_p2.py` | tests, including training on an audit block must fail | yes | none |

What changed on 2026-11-06.
- The window guard dilates the audit blocks by the file's `buffer_m`. A window 1 m from audit ground fails at 100 m.
- An audit id with no polygon in the blocks layer raises. It no longer passes.
- `check_split_file` also checks `held_out`. Audit blocks must not reach calibration or scoring folds.
- `committed_hash` returns None when git is missing.
- The audit CSV header now says `frame=pit_bearing_blocks tasks=pit`. `load_audit(path, task="pad")` refuses it.
- The Warren reservation reprojects each output extent to the block CRS. An extent without a CRS counts as seen.
- The split-overlap QC in the draw counts held-out lists too.

Dry-run products, all in `C:/Users/colto/Documents/GitHub/lidar_project/expansions/0_prerequisites/p2_audit_set/data/interim/`.
`audit_blocks_9t_dryrun.csv`, `audit_draw_9t_dryrun.json`, `block_exposure_9t.csv`, `block_exposure_scripts_9t.csv`, `audit_set_history_dryrun.md`.
Run records are in `results/<run_id>/`. The 2026-11-06 draw rerun is `results/20261106_audit_draw_dry_4965009/`.

