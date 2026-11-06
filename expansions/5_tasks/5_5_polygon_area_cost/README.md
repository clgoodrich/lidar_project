# 5.5. Polygon area and cost

**Status.** Plan only. Nothing here has been run. Tier B.
**Plan.** [docs/plan_task_polygon_area_cost.md](docs/plan_task_polygon_area_cost.md)
**Framework.** [docs/fw_5_5_polygon_area_cost.md](docs/fw_5_5_polygon_area_cost.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_5.md](docs/decisions_5_5.md)
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

Built by the build agent. All outputs stay inside this folder. Area is evidence level (a).

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_padarea_geometry_tools.py` | shared geometry and decision helpers | library | nothing |
| `src/_padarea_by_pad_9t.py` | S1 per-pad area and tile decomposition | yes | nothing |
| `src/_padarea_redraw_sample_9t.py` | S2 reviewer redraws | draw yes, score no | `redraws` (two blind reviewer layers, user-only) |
| `src/_padarea_survey_ingest_9t.py` | S3 survey ingest | no | `survey` (GNSS or drone outlines) |
| `src/_padarea_agreement_9t.py` | S4 agreement and S5 calibration arm | drawn reference yes, survey no | `survey` and the S3 output |
| `src/_padarea_cost_mc_9t.py` | S6 Monte Carlo and S7 decision | break-even f yes, Monte Carlo no | `cost_table` (agency table with a separable area term) |
| `src/test_5_5.py` | smoke test | yes | nothing |

S0 is the protocol document. It is a writing task for the lead and the reviewers. Outputs so far.
- `results/tables/pad_area_by_pad_9t.csv` and `pad_area_tile_decomposition_9t.json`
- `data/interim/pad_redraw_sample_sheet_9t.csv` holds 30 pads.
- `results/tables/pad_area_agreement_drawn_9t.csv` and `pad_area_agreement_summary_drawn_9t.json`
- `results/tables/pad_cost_error_summary_drawn_9t.json` holds break-even f only.
