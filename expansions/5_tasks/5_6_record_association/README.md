# 5.6. Record association

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_task_record_association.md](docs/plan_task_record_association.md)
**Framework.** [docs/fw_5_6_record_association.md](docs/fw_5_6_record_association.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_6.md](docs/decisions_5_6.md)
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

Built by the build agent. All outputs stay inside this folder. Run from the repo root. The detector key is `det_id`. `cand_id` restarts per source layer.

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_task5_helpers.py` | shared library for all 5.x | library | nothing |
| `src/_records_assoc_core.py` | dedupe, rates, shifted null, excess, Hungarian, link PPV bounds | library | nothing |
| `src/_records_full_detector_output_9t.py` | S0 input contract | yes | nothing |
| `src/_records_assoc_v2_9t.py` | S1 to S3 association, three analyses, positive control, power | yes | nothing |
| `src/_records_cohort_strata_9t.py` | S4 cohorts | yes, unstratified | `coord_source` (DEP R1) for the coordinate-source split |
| `src/_records_link_ppv_sample_9t.py` | S1 step 6 adjudication sample and link PPV | draw yes, score no | `adjudication_filled` (blind adjudication, user-only) and `field_use_min_ppv` |
| `src/_records_other_states_assoc.py` | S5 other states | no | per-state `status_col` and `status_map`, a detector output and a footprint per state |
| `src/_records_gnss_validation_9t.py` | S6 independent validation | no | `gnss_points` (R1 GNSS or R2 NETL) |
| `src/test_5_6.py` | smoke test | yes | nothing |

Config `src/config_5_6.json` holds every path and the four open decisions. Outputs so far.
- `data/processed/detector_output_pit_full_9t.gpkg` and `data/processed/detector_output_pad_full_9t.gpkg`
- `results/tables/records_detector_row_counts_9t.csv`
- `results/20261105_recassoc_bbd1ba6/` is the default run. `results/20261105_recassoc_a1ced49/` is the retained-count null sensitivity.
- `results/tables/records_cohort_excess_9t.csv` and `.json`
- `data/interim/records_link_adjudication_sheet_9t.csv` holds 60 links, blind to score.
