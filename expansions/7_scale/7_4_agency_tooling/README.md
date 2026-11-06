# 7.4. Agency tooling

**Status.** Plan only. Nothing here has been run. Tier A by instruction (user, 2026-11-05, stop deferring).
**Plan.** [docs/plan_scale_agency_tooling.md](docs/plan_scale_agency_tooling.md)
**Framework.** [docs/fw_7_4_agency_tooling.md](docs/fw_7_4_agency_tooling.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_7_4.md](docs/decisions_7_4.md)
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

Built by the build agent. The tool lives in `src/` with the program name `wells_cli`. The framework proposed `tools/wells_cli.py`, which is outside this expansion's write scope. One CPU run on a single 9t block (block 6, 750 x 750 px) finished in about 30 s.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_agency_cli_candidates.py` | check-env, version, manifest, validate, run, calibrate, report | yes | final frozen model from 3.0 and P1, `requirements_lock.txt`, wheelhouse or container |
| `src/_agency_las_validity.py` | section 7 refuse and warn checks | yes | thresholds fixed from 3.1 (proposed values in config) |
| `src/_agency_export_formats.py` | GPKG, CSV, KML export with the candidate schema | yes | nothing |
| `src/_agency_trust_calibrate.py` | trust statement, isotonic calibration (T7) | yes | 3.0 and 3.1 result files (statement says evaluated on 9t only), 50 to 100 agency labels |
| `src/_agency_fixture_las_build.py` | T1 fixtures and check | yes | 10 of 10 fixtures behave as expected, zero silent passes |
| `src/config_7_4.json` | assumed inputs and thresholds | yes | named agency user and decision |
| `src/test_7_4.py` | smoke test (T1, T4, T8 parts) | yes | 4 passed |

Tests still open. T0 on a clean machine, T2 against a 3.0 reference run, T3 on a held-out area, T5 kill and resume, T6 with a non-author. The model manifest is `results/tables/model_manifest_7_4.json`.
