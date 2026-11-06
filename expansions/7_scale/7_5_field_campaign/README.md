# 7.5. Field campaign

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_scale_field_campaign.md](docs/plan_scale_field_campaign.md)
**Framework.** [docs/fw_7_5_field_campaign.md](docs/fw_7_5_field_campaign.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_7_5.md](docs/decisions_7_5.md)
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

Built by the build agent. No sample has been drawn. The draw needs a frame.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_field_sample_size_design.py` | S2 sample size and design check | yes | frame counts from the draw for the per-stratum check |
| `src/_field_sample_draw_frames.py` | S1 frames and draws for arms A, B, C | no | P2 audit list or the reserved area `data/raw/field_reserved_area.gpkg`, frozen candidates `data/raw/candidates_frozen_k40.csv` (arm B), historic marks from 4.6 (optional) |
| `src/_field_sheet_generate.py` | S3 blind sheets, entry template, codebook, GPX | no | the drawn blind sample |
| `src/_field_results_ingest.py` | S5 validation, reconciliation, visit log | no | filled field records (partner) |
| `src/_field_analysis_bounds.py` | S4 sensitivity, S6 bounds and gate | no | ingested results |
| `src/config_7_5.json` | assumed frames, codes and design values | yes | partner, permissions, primary estimand, target width (user) |
| `src/test_7_5.py` | smoke test | yes | 2 passed |
