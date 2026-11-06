# P1. Reproducible splits and manifests

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_prereq_splits_manifests.md](docs/plan_prereq_splits_manifests.md)
**Framework.** [docs/fw_p1_splits_manifests.md](docs/fw_p1_splits_manifests.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_p1.md](docs/decisions_p1.md)
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

Built by the build agent. Tests. `python -m pytest -q expansions/0_prerequisites/p1_splits_manifests/src/test_p1.py -p no:cacheprovider` (9 passed).
Default outputs go to the framework paths under `data/9t/results/splits/`. The build dry runs wrote to `data/interim/dryrun/` in this folder instead, so nothing outside this folder changed.

| Script | Stage | Runnable now with held data | Missing or pending |
|---|---|---|---|
| `src/_split_core_lib_9t.py` | library | yes | none |
| `src/_split_recover_roles_9t.py` | S0 recover roles | yes, ran (15 of 15 held-out lists from checkpoints equal the exporter) | none |
| `src/_split_determinism_check_9t.py` | S1 determinism | yes, ran (fixed code identical in every fold, historical pit code differed in folds 0, 2, 4) | none |
| `src/_split_future_write_9t.py` | S2 split file, verify, `--exclude-audit` | yes, ran to interim and verified | committing `cv_splits_future_9t_v1.json` is a user step. `--exclude-audit` needs a frozen P2 file |
| `src/_pit_unet_iso_train_9t.py` | S3 isolated pit trainer, S6 `--measure-epoch` | dry run yes, ran. Training no | GPU hours (S6 user decision) |
| `src/_split_buffer_derive_9t.py` | S4 buffer | yes, ran (receptive field 188 px, range 37.5 m, buffer 100 m) | none |
| `src/_split_sampler_leakage_9t.py` | S5 window leakage and norm trace | yes, ran at 100,000 windows per fold | norm trace on real trained folds waits for S3 |
| `src/test_p1.py` | tests | yes | none |

Dry-run products, all in `expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/`.
`cv_splits_future_9t_v1.json`, `split_determinism_check_9t.json`, `cv_split_recovery_9t.csv`, `cv_split_recovery_9t.md`, `buffer_derivation_9t.json`, `residual_semivariogram_9t.png`, `sampler_leakage_test_9t.json`, `pit_iso/fold{0..4}/norm_stats_fold{k}.npz`.
Run records are in `results/<run_id>/`.
