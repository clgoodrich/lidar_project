# 4.5. Multitemporal lidar at plugged wells

**Status.** Code built 2026-11-05 and fixed after review 2026-11-06. Exploratory runs exist (see Build status). Tier A.
**Plan.** [docs/plan_mod_multitemporal_lidar.md](docs/plan_mod_multitemporal_lidar.md)
**Framework.** [docs/fw_4_5_multitemporal_lidar.md](docs/fw_4_5_multitemporal_lidar.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_5.md](docs/decisions_4_5.md)
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

Built by the build agent 2026-11-05. Review fixes 2026-11-06 (4.5-01, 4.5-02). Every script has a docstring, an argparse CLI and a `run()` function. Tests are in `src/test_4_5.py`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_dod_shared_io.py` | helper and the feature flag rule | yes | nothing |
| `src/config_4_5.json` | config | yes | VERIFY items. Minimum eligible pads, delta_rate |
| `src/_dod_flight_windows_9t.py` | S0 flight-date bounds | yes, rerun 2026-11-06 with --full-scan | USGS metadata `data/raw/flight_windows_metadata.csv` (D1). Late tiles use the GPS full scan (2020-03-18) |
| `src/_dod_plug_eligibility_9t.py` | S1 eligibility and pad complexes | yes, rerun 2026-11-06 | Restoration records `data/raw/dep_restoration_records.csv` (R7, optional) |
| `src/_dod_controls_matched_9t.py` | S2 matched control pads | yes, rerun 2026-11-06 (exploratory). Seam distance is matched | Enough treated pads |
| `src/_dod_registration_check_9t.py` | registration QC | yes, run 2026-11-05 | nothing |
| `src/_dod_recovery_test_9t.py` | S3 recovery through the S4 point chain | yes. h = 0 reproduction run 2026-11-06. Full grid not run (one 2006 rebuild per height and area) | nothing |
| `src/_dod_plug_change_compare_9t.py` | S4 and S5 comparison and gate | yes, rerun 2026-11-06 (exploratory) | Enough treated pads |
| `src/test_4_5.py` | tests | yes | nothing. 11 tests pass (2026-11-06) |

Outputs written so far (all under `expansions/4_modalities/4_5_multitemporal_lidar/results/`).
- `20261105_dod_flight_d7d2d47/flight_windows_9t.csv`, `flight_windows_9t.json`
- `20261105_dod_elig_7f2c6cd/plug_eligible_wells_9t.csv`, `plug_eligible_pads_9t.csv`, `plug_eligible_counts_9t.json`
- `20261105_dod_reg_7a1a6d5/dod_registration_9t.json`
- `20261105_dod_ctrl_eade56b/change_controls_matched_9t.gpkg`, `change_controls_balance_9t.json`
- `20261105_dod_compare_dbfad3c/plug_change_by_pad_9t.csv`, `plug_change_compare_9t.json` (superseded)
- `20261106_dod_flight_4010f00/flight_windows_9t.csv`, `flight_windows_9t.json` (full GPS scan)
- `20261106_dod_elig_a97e91e/plug_eligible_wells_9t.csv`, `plug_eligible_pads_9t.csv`, `plug_eligible_counts_9t.json`
- `20261106_dod_ctrl_08f3b2d/change_controls_matched_9t.gpkg`, `change_controls_balance_9t.json` (seam matched)
- `20261106_dod_compare_00c8ada/plug_change_by_pad_9t.csv`, `plug_change_compare_9t.json`
- `20261106_dod_recov_694f2bc/change_recovery_9t.csv`, `change_recovery_curve_9t.csv`, `change_recovery_curve_9t.png`, `change_recovery_summary_9t.json` (h = 0 only)

What the runs show.
- The 2019 D20 tiles over 9t were flown 2020-03-18. A full GPS scan of all 9 tiles gives that day for every point. The project name is not the flight year. The old 2019-12-31 window end was wrong.
- The 2006 to 2008 tiles store GPS week time, so the points carry no date. Their headers say EPSG:32128 (metres) but the coordinates are US feet (EPSG:2271).
- 5 of 1,068 DEP wells in the 9t box were plugged strictly between the flights. 3 pads hold them. The preregistered minimum is 20, so S1 says STOP.
- The v2 DEMs agree on stable ground. Residual shift is 0.06 m and bias is 0.02 m. Registration passes.
- The exploratory comparison is inconclusive because n is below the minimum. Before the seam fix treated pads sat a median 36 m from a seam and controls 220 m. With seam matching the medians are 29 m and 42 m over the assessable sets. The rate difference moved from 0.67 [0.00, 1.00] on 3 sets to 0.75 [0.50, 1.00] on 2 sets.
- S3 at h = 0 reproduces the held S4 field exactly (RMS 0.000 m, 0 NaN mismatches). So S3 now runs the S4 chain. At h = 0, 3 of the 9 matched pads are flagged. Those are real pads, so this is not a pure false-alarm rate. The height grid is not run yet. Each height and area is one 2006 rebuild of about 30 minutes.

Run order. S0, S1, registration check, S2, S3, S4. Stop at S1 when it prints STOP, unless the run is labelled exploratory.
