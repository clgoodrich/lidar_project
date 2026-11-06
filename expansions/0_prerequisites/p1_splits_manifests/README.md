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

## Build status (2026-11-06)

Review fixes on 2026-11-06 (adversarial review P1-01 to P1-05, the P1 minors, consolidated F05).
Tests. `python -m pytest -q -p no:cacheprovider expansions/0_prerequisites/p1_splits_manifests/src/test_p1.py` (23 passed).
User defaults applied on 2026-11-06 ("take defaults"). Buffer mode `window` is now the default. The noise band stays 2 sigma.
The dry run was rerun in window mode. Train blocks per fold, pit 72, 71, 76, 74, 75 (block mode had 23, 12, 24, 20, 22).
Pad 84, 82, 82, 82, 83 (block mode had 32, 16, 15, 16, 20). Train blocks near held-out ground, pit 49, 59, 52, 54, 53 and pad 52, 66, 67, 66, 63.
The isolated sampler leaks 0 windows in every fold at 100 m (pit) and 150 m (pad). The norm trace passes. The gate passes.
The block-mode dry-run files moved to `data/interim/dryrun/block_mode_20261106/`.
Default outputs go to the framework paths under `data/9t/results/splits/`. The dry runs wrote to `data/interim/dryrun/` in this folder instead, so nothing outside this folder changed.

| Script | Stage | Runnable now with held data | Missing or pending |
|---|---|---|---|
| `src/_split_core_lib_9t.py` | library, now with the block buffer | yes | none |
| `src/_split_recover_roles_9t.py` | S0 recover roles | yes, ran (15 of 15 held-out lists from checkpoints equal the exporter) | none |
| `src/_split_determinism_check_9t.py` | S1 determinism | yes, ran (fixed code identical in every fold, historical pit code differed in folds 0, 2, 4) | none |
| `src/_split_future_write_9t.py` | S2 split file, buffer, verify, `--exclude-audit` | yes, reran 2026-11-06 in window mode and verified | committing or freezing the file is a user step |
| `src/_split_future_csv_9t.py` | S2 long CSV | yes, ran 2026-11-06 | none |
| `src/_pit_unet_iso_train_9t.py` | S3 isolated pit trainer, S6 `--measure-epoch` | dry run yes, reran at the derived 100 m. Training no | GPU hours (S6 user decision) |
| `src/_split_buffer_derive_9t.py` | S4 buffer per task | yes, reran (pit 100 m, pad 150 m) | none |
| `src/_split_sampler_leakage_9t.py` | S5 window leakage and norm trace | yes, reran at the derived buffers, 100,000 windows per fold | norm trace on real trained folds waits for S3 |
| `src/test_p1.py` | tests, including the F05 round trip | yes | none |

What changed on 2026-11-06.
- The split CSV writes the JSON role words `train`, `inner_val` and `held_out`. It refuses to replace a CSV with different content unless `--force` is given.
- The trainer and the leakage test take the derived buffer through `ek.read_buffer`. They stop if it is missing, unless `--buffer-m` is given.
- The split writer applies the buffer. In `block` mode, train blocks within the buffer of held-out ground move to role `buffer`. The 9t blocks are 375 m squares, so every such block touches held-out ground.
- Pit train blocks moved to `buffer` per fold 49, 59, 52, 54, 53. Train lists fall from 72, 71, 76, 74, 75 to 23, 12, 24, 20, 22.
- Pad train blocks moved per fold 52, 66, 67, 66, 63. Train lists fall from 84, 82, 82, 82, 83 to 32, 16, 15, 16, 20.
- The buffer JSON writes `buffer_m_by_task` and `task`. Pad is now derived from the historical per-fold rasters.
- The buffer uses a noise-robust range bound. Pit first lag sits at 94.89% of the sill, inside the noise band. The bound stays 37.5 m and the pit buffer stays 100 m. Pad range bound 87.5 m gives 150 m.
- `--verify` compares every field after a recompute. Exclusions are re-derived from the named audit file.
- The norm trace fails when a fold is missing.
- Leakage at the derived buffers. pit at 100.0 m. historical leaking windows per fold 25726, 28512, 24646, 30789, 32666. isolated 0, 0, 0, 0, 0, with 0, 0, 0, 0, 0 draws finding no clear window. pad at 150.0 m. historical 81771, 19713, 52838, 56115, 39879. isolated 0, 0, 0, 0, 0, with 0, 0, 0, 0, 0 draws finding no clear window. Norm trace pass True. Gate pass.

Dry-run products, all in `C:/Users/colto/Documents/GitHub/lidar_project/expansions/0_prerequisites/p1_splits_manifests/data/interim/dryrun/`.
`cv_splits_future_9t_v1.json`, `cv_splits_future_pit_9t_v1.csv`, `cv_splits_future_pad_9t_v1.csv`, `split_determinism_check_9t.json`, `cv_split_recovery_9t.csv`, `cv_split_recovery_9t.md`, `buffer_derivation_9t.json`, `residual_semivariogram_9t.png`, `residual_semivariogram_pad_9t.png`, `sampler_leakage_test_9t.json`, `leakage_full.log`, `pit_iso/fold{0..4}/norm_stats_fold{k}.npz`.
Run records are in `results/<run_id>/`.
