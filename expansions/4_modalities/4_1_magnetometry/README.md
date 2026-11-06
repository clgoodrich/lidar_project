# 4.1. Magnetometry pilot

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_mod_magnetometry.md](docs/plan_mod_magnetometry.md)
**Framework.** [docs/fw_4_1_magnetometry.md](docs/fw_4_1_magnetometry.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_1.md](docs/decisions_4_1.md)
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

Built by the build agent. Every script has a docstring, an argparse CLI and a `run()` function. Tests are in `src/test_4_1.py`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_mag_shared_io.py` | helper | yes | nothing |
| `src/config_4_1.json` | config | yes | VERIFY items. Pole strength range, IGRF angles, gate thresholds |
| `src/_mag_site_frame_9t.py` | S0 site frame | yes, run 2026-11-05 | Historic-map dates (4.6), confusers and blanks CSV, chosen `pilot_sites.csv` |
| `src/_mag_survey_design.py` | S1 line plan and detection depth | yes, demo run 2026-11-05 | Measured pole strength for a cut casing |
| `src/_mag_anomaly_process.py` | S3 processing and picks | no | Field data. `data/raw/<site>/mag_lines.csv` and `mag_base.csv`, or `mag_grid.tif` |
| `src/_mag_pick_well_match.py` | S4 report, pilot gate, S5 feed forward | no | S3 output, `pilot_sites.csv`, `wellheads_gnss.csv`, `site_identity.csv` |
| `src/test_4_1.py` | smoke test | yes | nothing. 6 tests pass |

Outputs written so far.
- `expansions/4_modalities/4_1_magnetometry/results/20261105_magframe_28f0cc3/mag_site_frame_9t.csv` and `mag_site_frame_counts_9t.json`
- `expansions/4_modalities/4_1_magnetometry/results/20261105_magdesign_f11f115/mag_survey_lines_demo.gpkg`, `mag_survey_design_demo.json`, `mag_detect_depth_demo.csv`

Run order. S0 frame, then S1 design per chosen site, then S3 per site after fieldwork, then S4.
