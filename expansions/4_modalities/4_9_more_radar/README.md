# 4.9. More radar

**Status.** Code built 2026-11-05 (see Build status). No result is on file. Tier B.
**Plan.** [docs/plan_mod_more_radar.md](docs/plan_mod_more_radar.md)
**Framework.** [docs/fw_4_9_more_radar.md](docs/fw_4_9_more_radar.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_9.md](docs/decisions_4_9.md)
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

Defaults applied 2026-11-06 (user said "take defaults"). lidar_weak is the lowest tercile of targets on ground point density, read from `data/9t/derived/1m/ground_density_9t_1m.tif` at each row point. It is the primary stratum once that layer is held and the stratum forms, else the primary falls back to all. The layer is held. max_undefined_share stays 0. With one primary, Holm is m = 1. No S1 or S5 result is on file, so nothing reran. Tests 12 passed.

Review fixes for 4.9-01 and the 4.9 minors. Tests 11 passed.

| Script | Change |
|---|---|
| `src/_sar_kit_4_9.py` | `lidar_weak_mask` from an external covariate. `paired_gain_boot` counts undefined draws. `paired_perm` on within-arm ranks. Frozen-row stamp and check |
| `src/_sar_power_baseline_9t.py` | S1 strata from the covariate or the ground density layer. lidar_weak skipped when neither is on the rows |
| `src/_sar_new_score_9t.py` | S5 strata from the covariate or the ground density layer. One primary row (lidar_weak when formed, else all). Placebo must be null. undefined_share column |
| `src/_sar_new_features_9t.py` | S4 refuses to overwrite frozen rows that changed. `--adopt-frozen` |
| `src/config_4_9.json` | `prereg.lidar_weak` (ground density, lowest tercile), `primary_stratum`, `max_undefined_share` |

No S1 or S5 result was on file, so nothing was rerun. The held 9t pit rows were stamped as frozen.

## Build status (2026-11-05)
Built by the build agent. Arm specifications are assumptions in `src/config_4_9.json` (all VERIFY). Tests. `python -m pytest -q expansions/4_modalities/4_9_more_radar/src/test_4_9.py -p no:cacheprovider` (5 passed).

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_sar_kit_4_9.py` | AUC, paired block bootstrap, permutation, Holm | yes | nothing |
| `src/_sar_observability_9t.py` | S0 observability | yes, on assumed arm numbers | catalogue table `data/raw/sar_catalogue_9t.csv`. S3 residuals |
| `src/_sar_power_baseline_9t.py` | S1 headroom and power | yes. Default uses the held 613590 rows. 9t rows after the next line | nothing for 613590 |
| `src/_sar_new_score_9t.py --baseline-only` | 9t per-row baseline for S1 | yes (reproduces AUC 0.9735 against the saved 0.973) | nothing |
| `src/_sar_fetch_new_9t.py` | S2 fetch | dry run yes | approved manifest `data/raw/sar_fetch_manifest.csv`. User cost approval |
| `src/_sar_registration_9t.py` | S3 registration | no | permanent scatterer table `data/raw/sar_scatterers_9t.csv` |
| `src/_sar_new_features_9t.py` | S4 rows and features | `--rows-only` yes (4,881 pit rows, 489 targets). Features no | geocoded stacks `data/9t/derived/sar_new/<arm>/` |
| `src/_sar_new_score_9t.py` | S5 gain | no | S4 arm columns. 613590 rows with the same columns for the held-out test |
| `src/_sar_new_gain_figure_9t.py` | S6 figure | no | S5 table |
| `src/test_4_9.py` | smoke tests | yes | nothing |
