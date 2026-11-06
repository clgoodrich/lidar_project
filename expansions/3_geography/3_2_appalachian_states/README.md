# 3.2. Ohio, West Virginia, New York, Kentucky

**Status.** Built. Desk stages ran on held data (inventory, harmonisation, coverage). Nothing was downloaded or scored. Review fixes 2026-11-06. Tier B.
**Plan.** [docs/plan_geo_appalachian_states.md](docs/plan_geo_appalachian_states.md)
**Framework.** [docs/fw_3_2_appalachian_states.md](docs/fw_3_2_appalachian_states.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_2.md](docs/decisions_3_2.md)
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

Defaults applied (2026-11-06, user said take defaults). Margin 0.03 recall per window. Holm over the four primary windows (ny_alg, oh_wash, ky_lee, wv_ple). Companions are never gated. The state table takes the Holm verdict from `results/tables/xfer_holm_family_appal.json` when it exists. max_undefined 0.

Review fix pass (F02 F03 F08 inherited from 3.1). Tests. `python -m pytest -q -p no:cacheprovider expansions/3_geography/3_2_appalachian_states/src/test_3_2.py` (9 passed).
- Window scoring runs through the 3.1 stages, which now call the 3.0 reference scorer. There is no 3.2 matcher.
- `config_3_2.json` reference now names the 3.0 tables. The 3.3 S1 blocks CSV feeds only design tools.
- The adaptation arm (S11) scores both arms through the same policy. An old 0.10 cutoff is refused.

## Build status (2026-11-05)

Built by the build agent. Per-window stages reuse the 3.1 scripts through `src/_appal_window_stage_runner.py` with `src/config_3_2.json`. Nothing was downloaded.

| Script | Stage | Runnable now with held data | What is missing |
|---|---|---|---|
| `expansions/3_geography/3_2_appalachian_states/src/_appal_wells_loaders.py` | loaders for S0 and S1 | yes | data dictionaries to VERIFY status maps and datums |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_wells_inventory.py` | S0 desk inventory | yes. Run | nothing |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_wells_harmonise.py` | S1 status and datum | yes. Run | status definitions from each source |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_window_cover_union.py` | S2 coverage and query audit | yes. Run | nothing (cover is a bbox upper bound) |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_density_void_windows.py` | S3 ground density and void | no | window tiles under `data/_source/lidar/lidar_us_windows/<project>/` (fetch one tile first) |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_window_stage_runner.py` | S4 to S10 per window | no | S3 inventory per window, then as for each 3.1 stage |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_thin_density_arm.py` | S9 thinned sensitivity arm | no | window tiles and the S3 inventory |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_adapt_finetune.py` | S11 adaptation (Q3, conditional, GPU) | no | a failed primary score, the companion zero-shot score, the P1 checkpoint, truth |
| `expansions/3_geography/3_2_appalachian_states/src/_appal_state_table.py` | S12 state table and 5.6 hand-off | yes. Run (no window scored yet) | score runs |
| `expansions/3_geography/3_2_appalachian_states/src/config_3_2.json` | config | yes | Ritchie window and project, N_min |
| `expansions/3_geography/3_2_appalachian_states/src/test_3_2.py` | smoke test | yes. 8 passed | nothing |

**Outputs produced (cheap runs on held data).**
- `expansions/3_geography/3_2_appalachian_states/results/tables/state_inventory_appal.csv` and `.json`. Seven sources, hashes, counts, raw status codes.
- `expansions/3_geography/3_2_appalachian_states/data/processed/wells_status_harmonised_appal.csv.gz` (24 MB, gitignored). 704,152 records.
- `expansions/3_geography/3_2_appalachian_states/results/tables/wells_harmonise_counts_appal.csv` and `wells_harmonise_summary_appal.json`.
- `expansions/3_geography/3_2_appalachian_states/results/tables/lidar_win_union_cover_appal.csv` and `lidar_win_query_audit_appal.csv`.
- `expansions/3_geography/3_2_appalachian_states/results/tables/xfer_density_void_windows_appal.csv` (every window is missing its tiles).
- `expansions/3_geography/3_2_appalachian_states/results/tables/state_transfer_table_appal.csv`.
- `expansions/3_geography/3_2_appalachian_states/data/processed/wells_window_handoff_appal.csv.gz` (23,400 records inside windows, for 5.6, gitignored).

**Findings from the desk runs.**
- Union cover from tile boxes is below the catalogue cover. Allegany 0.84, Ohio Washington 0.88, Ohio Monroe 0.88. These three fail a 0.95 cover share.
- The windows are 31 to 34 km², not 25 km².
- The Kentucky Lee and Powell windows sit about 1.1 km apart. The companion is not well separated from the primary.
- The Pleasants window crosses the Ohio River. It holds 85 Ohio ODNR records.
- The Kentucky NAD27 to NAD83 shift has a median of 7.6 m and a 95th percentile of 15.6 m. A few records have broken NAD27 values.
- The 2026 national orphan list gives Kentucky coordinates generated from Carter coordinate data. Position quality is low.
