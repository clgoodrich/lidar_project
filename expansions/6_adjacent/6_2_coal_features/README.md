# 6.2. Coal and mine features

**Status.** Plan only. Nothing here has been run. Tier A by instruction (user, 2026-11-05, stop deferring).
**Plan.** [docs/plan_adj_coal_features.md](docs/plan_adj_coal_features.md)
**Framework.** [docs/fw_6_2_coal_features.md](docs/fw_6_2_coal_features.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_2.md](docs/decisions_6_2.md)
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

Tests. `python -m pytest -q expansions/6_adjacent/6_2_coal_features/src/test_6_2.py -p no:cacheprovider` gives 4 passed.
The study reuses the 6.3 code. `config_6_2.json` has the same shape as `config_6_3.json`, so the 6.3 sheet, agreement and pooled-score scripts take it with `--config`.
Nothing runs on real data yet. The coal area has no lidar, derivatives or DEP mine layers on disk.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_coal_common.py` | shared (mine layers, type map, tolerances, blocks) | yes | nothing |
| `src/_coal_inventory_sample_coal.py` | S0 audit draw and chips | no | DEP mine layers under `data/greene/source/dep_mine_features/`, coal blocks and derivatives |
| `src/_coal_inventory_audit_coal.py` | S0 audit summary and readiness gate | no | reviewer-filled `coal_audit_records.csv` |
| `src/_coal_candidates_coal.py` | S1 blocks, derivative and inference commands, candidates | no | coal lidar tiles, then pit and pad probability rasters |
| `src/_coal_label_sheets_coal.py` | S2 audit freeze, sample, blind sheets | no | S1 candidates and mine layers |
| `src/_coal_confusion_coal.py` | S3 confusion matrix (Q2 primary) | no | S2 adjudicated labels |
| `src/_coal_unet_cv5_coal.py` | S4 mine model, S6 well model with mine negatives | dry run only after labels | adjudicated polygons, saved split, GPU for `--train` |
| `src/_coal_reverse_confusion_9t.py` | S5 reverse confusion on 9t | no | S4 checkpoints and their 9t rasters |
| `src/config_6_2.json` | inputs, classes, tolerances, gates | yes | coal area choice and margin delta are user decisions |
