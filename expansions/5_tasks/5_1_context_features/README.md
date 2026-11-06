# 5.1. Context features (second-stage model)

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_task_context_features.md](docs/plan_task_context_features.md)
**Framework.** [docs/fw_5_1_context_features.md](docs/fw_5_1_context_features.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_1.md](docs/decisions_5_1.md)
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

Scripts live in `src/`. Paths come from `src/config_5_1.json`. Helpers come from `../5_6_record_association/src/_task5_helpers.py` and `expansions/_shared/src/expkit.py`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_context_upstream_inventory_9t.py` | S0 upstream inventory | yes | Nothing. Ran 2026-11-05 |
| `src/_context_shared_folds_9t.py` | S1 shared fold scheme | provisional only | P2 audit list `data/9t/results/splits/audit_blocks_9t_v1.csv`. `--allow-no-audit` writes a provisional file |
| `src/_context_reliance_edits_9t.py` | S2 reliance test (Q1) | edits only | P1 isolated pit checkpoints, the P1 split file and a `reliance.scorer_fn`. `reliance.derivative_fn` for the exact stack (fallback channels otherwise) |
| `src/_context_retrain_manifest_9t.py` | S3 retraining jobs | manifest yes, training no | Final S1 file, the P1 isolated pit trainer and a shared-fold road trainer. GPU time |
| `src/_context_stage2_features_9t.py` | S4 stage-2 features | provisional only | Shared-scheme pit, pad and road rasters from S3 (nested mode needs inner-fold models too) |
| `src/_context_leakage_audit_9t.py` | S6 leakage audit | yes | Passes only after S3. Fails on historical rasters by design |
| `src/_context_stage2_learner_9t.py` | S5 learner and S7 scoring | void test only | A passing S6 audit. `stage2.delta_gain` (user decision) |
| `src/test_5_1.py` | smoke tests | yes | Nothing |

Outputs from the 2026-11-05 build runs. All are pipeline tests on historical models. None is a result.
- `results/tables/context_upstream_inventory_9t.csv` and `.md`. Every upstream model is flagged must retrain.
- `results/tables/shared_folds_9t_provisional.json`. Provisional, no audit blocks.
- `results/tables/context_retrain_manifest_9t.json`. Provisional, 15 jobs.
- `data/processed/stage2_features_9t.parquet`, `data/processed/stage2_upstream_usage_9t.json`, `data/interim/stage2_candidates_9t.gpkg`.
- `results/tables/context_leakage_audit_9t.json`. Failed, as expected.
- `results/20261105_stage2_266941f/`. VOID run. It tests the code path only.
- `results/tables/context_reliance_paired_9t.csv`. 20 pits and 20 controls, edits only, no scores.
