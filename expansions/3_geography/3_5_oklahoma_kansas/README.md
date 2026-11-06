# 3.5. Oklahoma and Kansas

**Status.** Plan only. Nothing here has been run. Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded, trained or scored.
**Plan.** [docs/plan_geo_oklahoma_kansas.md](docs/plan_geo_oklahoma_kansas.md)
**Framework.** [docs/fw_3_5_oklahoma_kansas.md](docs/fw_3_5_oklahoma_kansas.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_5.md](docs/decisions_3_5.md)
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

Defaults applied (2026-11-06, user said take defaults). Margin and delta_gain 0.03 recall. Void cap 0.5 (was 0.9). Holm over the F1 minus L1 gain for pit and pad on Oklahoma. Other contrasts and Kansas are reported, never gated. L0 uses the provisional five-fold 9t pit ensemble with hashes checked. L2 still refuses until `model.pit.init_checkpoint` names a fold.

Review repair (2026-11-06). Arms are scored per class with the class policy (pits 0.35, pads 0.525). L0 is scored on pits only. L2 fine-tuning declares its re-initialised head. The gain figure shows negative gains. The transfer checkpoint is an explicit unset config key, so L0 and L2 refuse until it is set. Open user decisions are in `docs/decisions_3_5.md`.

Built by the build agent. The shared regional-transfer code is `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py`. Expansions 3.4 to 3.8 import it. Stage commands that every region shares are its subcommands. Assumed inputs and their schemas are in `src/config_3_5.json`. A missing assumed input stops a script with a message that names the input, its schema and the VERIFY step. Decisions are in `docs/decisions_3_5.md`. Run the tests with `python -m pytest -q expansions/3_geography/3_5_oklahoma_kansas/src/test_3_5.py -p no:cacheprovider`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_okks_registry_wells.py` | registry loader and S11 hand-off rows | yes (ran, 9 windows) | nothing |
| `src/_okks_optical_coverage.py` | S0 coverage and dates, S1 NAIP fetch with `--fetch --execute` | no | `data/raw/naip_tile_index_okks.csv`, `data/raw/lidar_flight_dates_okks.csv` |
| `src/_okks_label_budget_9t.py` | S2 label-budget curve on 9t | plan yes (ran). Training is GPU | nothing for the plan |
| `src/_okks_coreg_optical.py` | S3 per-block co-registration | no | 0.5 m slope (core `derive`), NAIP on the lidar grid (S4 `--resample-only`) |
| `src/_okks_optical_stack.py` | S4 optical and fusion stacks | no | NAIP tiles, lidar stack, S3 shifts |
| `src/_okks_blocks_roles.py` | S5 roles by slope tercile, common footprint | no | 0.5 m slope per window, S0 coverage |
| `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py width --exp 3.5` | S6 projected width | no | 3.0 reference tables |
| `src/_okks_truth_adjudicate.py` | S7 adjudicate the two blind passes | no | pass L and pass O label files |
| `src/_okks_modality_train.py` | S8 arms L1, O1, F1, L2 with trial ledger (GPU) | plan yes | stacks, labels, `prereg.gpu_hour_cap_per_arm` |
| `src/_okks_modality_compare.py` | S9 paired scoring and S10 strata | no | arm probability rasters (`--infer`), truth, `prereg.delta_gain` |
| `src/test_3_5.py` | smoke tests | yes. 6 passed |  |
| `src/config_3_5.json` | assumed inputs, schemas, prereg values |  | user decisions are null |
