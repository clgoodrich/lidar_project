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

## Build status (2026-11-06)

Review fix pass. Run from the repo root. Tests pass (20).

Detector contract for 5.4, 6.1 and 6.4.
- Files `data/processed/detector_output_pit_full_9t.gpkg` (677 rows) and `data/processed/detector_output_pad_full_9t.gpkg` (1005 rows).
- `det_id` is an int, unique across both files. Pits run 1 to 677. Pads run 1000001 to 1001005.
- `det_id` is a seeded random permutation. It encodes neither match status nor score. Seeds and policy are in `results/tables/records_detector_id_policy_9t.json` and `data/processed/_PROVENANCE_detector_output.json`.
- `kind` is pit or pad. `score` is the mean blob probability. Read `cx` and `cy` as `df["cx"]`, never `df.cx`.
- Membership reads predictions only. `source`, `novel`, `near_pit_m`, `dup_on_pit`, `matched_plat` and `iou` are evaluation columns.

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_task5_helpers.py` | shared library for all 5.x | library | nothing |
| `src/_records_assoc_core.py` | geometric dedupe, det_id, rates, toroidal null, excess, gated Hungarian, link PPV | library | nothing |
| `src/_records_full_detector_output_9t.py` | S0 input contract | yes | nothing |
| `src/_records_assoc_v2_9t.py` | S1 to S3 association, positive control, power | yes | nothing |
| `src/_records_cohort_strata_9t.py` | S4 cohorts | yes, unstratified | `coord_source` (DEP R1) |
| `src/_records_link_ppv_sample_9t.py` | adjudication sample and link PPV | draw yes, score no | `adjudication_filled` and `field_use_min_ppv` |
| `src/_records_other_states_assoc.py` | S5 other states | no | per-state status map, detector output and footprint |
| `src/_records_gnss_validation_9t.py` | S6 independent validation | no | `gnss_points` |
| `src/test_5_6.py` | regression tests | yes | nothing |

Outputs.
- `results/tables/records_detector_row_counts_9t.csv` and `results/tables/records_detector_id_policy_9t.json`
- `results/20261106_recassoc_fdf2bb7/` is the default run (complete grid, torus null).
- `results/20261106_recassoc_090ff28/` is the old-rule sensitivity (truth-bearing footprint, reject and redraw).
- The 2026-11-05 run folders are superseded. They used the truth-dependent dedupe.
- `results/tables/records_cohort_excess_9t.csv` and `.json`
- `data/interim/records_link_adjudication_sheet_9t.csv` holds 60 links. It was redrawn from the default run.
