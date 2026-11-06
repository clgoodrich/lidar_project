# 3.4. Gulf Coast and Texas

**Status.** Plan only. Nothing here has been run. Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded or scored.
**Plan.** [docs/plan_geo_gulf_east_texas.md](docs/plan_geo_gulf_east_texas.md)
**Framework.** [docs/fw_3_4_gulf_texas.md](docs/fw_3_4_gulf_texas.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_4.md](docs/decisions_3_4.md)
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

Defaults applied (2026-11-06, user said take defaults). Margin and delta_gain 0.03 recall. Void cap 0.5 (was 0.9). Holm over A0 pit on la_caddo and tx_east. Everything else is reported, never gated. max_undefined 0. The provisional transfer model is the five-fold 9t ensemble (pit `pit/unet_cv5`, pad `pad/unet_cv5_iso`, fold_mean) with sha256 per fold in `model.<task>`. `infer` now averages the folds and writes an inference record. Fine-tuning still refuses because no fold is named as `init_checkpoint`.

Review repair (2026-11-06). The core now scores under `ek.policy_for(task)` only (pit 0.35, pad 0.525, score-order matching, 3.0 dedupe) and stamps the policy into outputs. The K budget and denominator use the actual scored support. Truth ids may be any unique value, including 0. Only denominator truth can be a hit. Pooled ties sort by numeric id then draw. Areas need metre CRS and full-affine grid matches. Partial checkpoint loads need an allow-list. The transfer checkpoint is an explicit unset config key. A parity test runs one fixture through the 3.0 scorer and this core. On the 9t pit mosaic the core gives recall 0.9165 at K 40, equal to the 3.0 scorer (old core 0.5785). On the 3.0 filled raster it gives 0.9463, equal to the current 3.0 reference tables. Result `results/tables/xfer_core_parity_recall_9t.json`. Open user decisions are listed in `docs/decisions_3_4.md`.

Built by the build agent. The shared regional-transfer code is `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py`. Expansions 3.4 to 3.8 import it. Stage commands that every region shares are its subcommands. Assumed inputs and their schemas are in `src/config_3_4.json`. A missing assumed input stops a script with a message that names the input, its schema and the VERIFY step. Decisions are in `docs/decisions_3_4.md`. Run the tests with `python -m pytest -q expansions/3_geography/3_4_gulf_texas/src/test_3_4.py -p no:cacheprovider`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_geo_transfer_core.py` | shared core for 3.4 to 3.8 (config, registry, blocks, density, candidates, scoring, agreement, training sampler, CLI) | yes | nothing. Subcommands need their inputs |
| `src/_geo_transfer_core.py cover --exp 3.4` | S1 support. Union cover from catalogue tile boxes | yes (ran) | nothing. Tile boxes give an upper bound |
| `src/_gulf_rrc_orphans_tx.py` | S0 RRC fetch, schema, reliability | yes on the held Permian sample (ran, 3,328 rows). Layer 2 needs `--execute` | `data/raw/rrc_layer2_url.txt`. Real field names (edit `RRC_COLMAP`) |
| `src/_gulf_window_choice_tx.py` | S1 East Texas rule and window boxes | yes (ran). No county passes yet | `data/raw/east_tx_lidar_listing.csv` (paged listing for Gregg, Rusk, Smith, Upshur) |
| `src/_geo_transfer_core.py density --exp 3.4 --area <a>` | S2 ground density, void, water share | no | lidar tiles under `data/_source/lidar/lidar_us_windows/<project>/` |
| `src/_gulf_observable_depth_audit.py` | S3 observability Q0 | 9t reference yes (ran, 503 pit floors). Target no | target 0.5 m DEM (core `derive`), NLCD 2021, `prereg.observability_floor` |
| `src/_gulf_wetland_strata.py` | S4 water mask, strata, roles | no | S2 table, NLCD 2021, NWI polygons, hydro-flattened water polygons |
| `src/_geo_transfer_core.py width / prereg --exp 3.4` | S5 projected width and prereg draft | prereg yes. Width no | 3.0 reference block tables |
| `src/_geo_transfer_core.py derive / agree --exp 3.4` | S6 derivatives and label agreement | dry run yes | lidar tiles. Two annotators' polygons |
| `src/_geo_transfer_core.py infer / score --exp 3.4 --task pit` | S7 A0, and S8 C0 with `--contrast` | no | target feature stack, truth polygons with class |
| `src/_gulf_relief_norm_channels.py` | S9a relief-normalised channels | no | adaptation-window DEM and feature stack |
| `src/_gulf_pit_adapt_train.py` | S9b A1 fine-tune (GPU) | no | S9a stack, adaptation label raster, `model.pit.init_checkpoint` (user decision) |
| `src/_geo_transfer_core.py score --strata-filter wet_stratum=dry,mixed` | S10 A2 wetland exclusion | no | as S7 |
| `src/_gulf_transfer_tables.py` | S10 and S11 tables, error review, RRC hand-off | partly. The hand-off runs once S0 output exists | score JSONs from S7 to S10 |
| `src/test_3_4.py` | smoke tests (core plus 3.4) | yes. 10 passed |  |
| `src/config_3_4.json` | assumed inputs, schemas, prereg values |  | margin and delta_gain 0.03 (defaults). Floors are null |
