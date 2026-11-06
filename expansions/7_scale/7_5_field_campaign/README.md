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

## Build status (2026-11-06)

Built by the build agent on 2026-11-05. Review fixes on 2026-11-06 (F04, F05, F16, 7.5-01, 7.5-02, Arm B frame). No sample has been drawn. The draw needs a frame.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_field_sample_size_design.py` | S2 sample size and design check | yes, rerun 2026-11-06 | frame counts from the draw for the per-stratum check |
| `src/_field_sample_draw_frames.py` | S1 frames and draws for arms A, B, C | no | frozen P2 audit list or the reserved area `data/raw/field_reserved_area.gpkg`. Arm B frame is the 5.4 site table. Historic marks from 4.6 are optional |
| `src/_field_sheet_generate.py` | S3 blind sheets, entry and well templates, codebook, GPX | no | the drawn blind sample |
| `src/_field_results_ingest.py` | S5 validation, reconciliation, visit log, child well table | no | filled field and well records (partner) |
| `src/_field_analysis_bounds.py` | S4 sensitivity, S6 design-based bounds and gate | no | ingested results |
| `src/_field_density_export.py` | handoff to 5.4 S3 (arm B and arm C files) | no | ingested results |
| `src/config_7_5.json` | assumed frames, codes and design values | yes | partner, permissions, primary estimand, site count and target width (user) |
| `src/test_7_5.py` | tests, including an end-to-end run into 5.4 S3 | yes | 13 passed |

User defaults on 2026-11-06. Detector link 15 m and well merge 5 m are confirmed. Single-cluster strata merge with the adjacent stratum of the same arm before the draw (config `strata`).
The Arm B transfer of p to the whole footprint is accepted. The density export labels it as an assumption. No sample exists, so nothing was redrawn.

The target width 0.30 needs about 746 sites. At n = 182 the expected width is 0.407. See `docs/decisions_7_5.md`.
