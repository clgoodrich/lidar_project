# 3.8. Alaska

**Status.** Plan only. Nothing here has been run. Tier A (full design, data assumed).
**Plan.** [docs/plan_geo_alaska.md](docs/plan_geo_alaska.md)
**Framework.** [docs/fw_3_8_alaska.md](docs/fw_3_8_alaska.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_8.md](docs/decisions_3_8.md)
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

Review repair (2026-11-06). Injection recovery now injects into the noisy stack before one inversion, so recovery error grows with noise. The end-of-season rate never mixes calendar months across years. The E2 gate reports undefined bootstrap draws. The synthetic self-test was rerun. Open user decisions are in `docs/decisions_3_8.md`.

Built by the build agent. The shared regional-transfer code is `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py`. Expansions 3.4 to 3.8 import it. Stage commands that every region shares are its subcommands. Assumed inputs and their schemas are in `src/config_3_8.json`. A missing assumed input stops a script with a message that names the input, its schema and the VERIFY step. Decisions are in `docs/decisions_3_8.md`. Run the tests with `python -m pytest -q expansions/3_geography/3_8_alaska/src/test_3_8.py -p no:cacheprovider`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_ak_wells_sites_ak1.py` | S0 inventory and sites | yes on held USGS rows (ran, 47 wells, 21 sites) | federal legacy list and AOGCC export (optional) |
| `src/_ak_observability_ak1.py` | S1 observability gate | no. Fill fraction runs once sites exist, the decision defers | site covariates, acquisition list, weather flags, `delta_mm_yr` |
| `src/_ak_insar_series_ak1.py` | S2 fetch plan and small-baseline series | no | acquisition list, interferogram manifest, matched controls |
| `src/_ak_reference_stability_ak1.py` | S3 reference stability and noise floor | no | S2 series with reference rows |
| `src/_ak_injection_recovery_ak1.py` | S4 injection-recovery | self-test yes (ran, `--synthetic`) | real interferogram stack |
| `src/_ak_site_matching_ak1.py` | S5a matched controls | no | site covariates, control candidates |
| `src/_ak_rate_difference_ak1.py` | S5b E2 and E3 | no | S2 series, S5a matches, `delta_mm_yr` (D-AK1) |
| `src/_ak_placebo_ak1.py` | S6 location-only baseline and placebo | no | S5b output, covariates |
| `src/_ak_active_layer_check_ak1.py` | S7 optional ground check | no | active-layer site table |
| `src/test_3_8.py` | smoke tests | yes. 6 passed |  |
| `src/config_3_8.json` | assumed inputs, schemas, prereg values |  | D-AK1 to D-AK4 are null |
