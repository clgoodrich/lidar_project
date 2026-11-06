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

Defaults pass (2026-11-06). The held-out products are re-cut at the policy cutoffs, pit 0.35 and pad 0.525, by `src/_records_policy_recut_9t.py`. Dedupe stays at 2.0 m. S0 refuses a product cut at any other value. Run from the repo root. Tests pass (23).

Rerun on 9t. Pit rows 677 to 768. Pad rows 1005 to 996. The positive control passes (0.373 to 0.363). Orphan and abandoned at pit 50 m 0.043 to 0.015, interval still spans 0. Plugged at pit 50 m 0.039 to 0.084, lower bound now above 0. Re-cutting today's pit rasters at 0.50 gives 658 blobs, not the old 688. The old pit product predates the 2026-09-17 fold rasters.

Detector contract for 5.4, 6.1 and 6.4.
- Files `data/processed/detector_output_pit_full_9t.gpkg` (768 rows) and `data/processed/detector_output_pad_full_9t.gpkg` (996 rows).
- `det_id` is an int, unique across both files. Pits run 1 to 768. Pads run 1000001 to 1000996.
- `det_id` is a seeded random permutation. It encodes neither match status nor score. Seeds and policy are in `results/tables/records_detector_id_policy_9t.json` and `data/processed/_PROVENANCE_detector_output.json`.
- `kind` is pit or pad. `score` is the mean blob probability. Read `cx` and `cy` as `df["cx"]`, never `df.cx`.
- Membership reads predictions only. `source`, `novel`, `near_pit_m`, `dup_on_pit`, `matched_plat` and `iou` are evaluation columns.

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_task5_helpers.py` | shared library for all 5.x | library | nothing |
| `src/_records_assoc_core.py` | geometric dedupe, det_id, rates, toroidal null, excess, gated Hungarian, link PPV | library | nothing |
| `src/_records_policy_recut_9t.py` | S0 input. Re-cuts the held-out rasters at pit 0.35 and pad 0.525 | yes | nothing |
| `src/_records_full_detector_output_9t.py` | S0 input contract | yes | nothing |
| `src/_records_assoc_v2_9t.py` | S1 to S3 association, positive control, power | yes | nothing |
| `src/_records_cohort_strata_9t.py` | S4 cohorts | yes, unstratified | `coord_source` (DEP R1) |
| `src/_records_link_ppv_sample_9t.py` | adjudication sample and link PPV | draw yes, score no | `adjudication_filled` and `field_use_min_ppv` |
| `src/_records_other_states_assoc.py` | S5 other states | no | per-state status map, detector output and footprint |
| `src/_records_gnss_validation_9t.py` | S6 independent validation | no | `gnss_points` |
| `src/test_5_6.py` | regression tests | yes | nothing |

Outputs.
- `results/tables/records_detector_row_counts_9t.csv` and `results/tables/records_detector_id_policy_9t.json`
- `data/interim/records_pit_recut_policy_9t.gpkg` and `data/interim/records_pad_recut_policy_9t.gpkg` are the re-cut products.
- `results/20261106_recassoc_23e82bc/` is the default run (complete grid, torus null) at the policy cutoffs.
- `results/20261106_recassoc_74b4c0c/` is the old-rule sensitivity (truth-bearing footprint, reject and redraw).
- `results/20261106_recassoc_fdf2bb7/` and `results/20261106_recassoc_090ff28/` are the same two runs on the 0.50 products. Superseded.
- The 2026-11-05 run folders are superseded. They used the truth-dependent dedupe.
- `results/tables/records_cohort_excess_9t.csv` and `.json`
- `data/interim/records_link_adjudication_sheet_9t.csv` holds 60 links. It was redrawn from the default run.
