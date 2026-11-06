# 5.4. Undocumented well density

**Status.** Plan only. Nothing here has been run. Tier B.
**Plan.** [docs/plan_task_undocumented_density.md](docs/plan_task_undocumented_density.md)
**Framework.** [docs/fw_5_4_undocumented_density.md](docs/fw_5_4_undocumented_density.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_4.md](docs/decisions_5_4.md)
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

Built by the build agent. The framework was rewritten to full depth the same day (151 lines). No density map is produced anywhere.

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_density_identifiability_terms_9t.py` | S0 term table | yes | nothing |
| `src/_density_distinct_wells_9t.py` | S1 distinct-well accounting | yes | nothing. It reads the 5.6 S0 output, which is built |
| `src/_density_sensitivity_grid_9t.py` | S2 sensitivity grid and figure | yes | nothing |
| `src/_density_field_bounds_9t.py` | S3 field bounds | no | `arm_b` and `arm_c` from 7.5 (field campaign) |
| 5.6 `src/_records_cohort_strata_9t.py` | S4 cohort link | yes, unstratified | DEP coordinate source (R1) |
| `src/_density_capture_recapture_9t.py` | S5 capture-recapture diagnostic | yes | nothing. Link precision q is an assumed grid until 5.6 adjudication |
| `src/test_5_4.py` | smoke test | yes | nothing |

Outputs so far.
- `results/tables/density_identifiability_terms_9t.csv`
- `results/tables/density_distinct_sites_9t.csv` and `density_accounting_9t.json`
- `results/tables/density_sensitivity_9t.csv` and `.json`, with `results/figures/density_sensitivity_9t.png`
- `results/tables/density_capture_recapture_9t.csv` and `.json`
