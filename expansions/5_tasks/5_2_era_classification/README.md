# 5.2. Era classification

**Status.** Plan only. Nothing here has been run. Tier B.
**Plan.** [docs/plan_task_era_classification.md](docs/plan_task_era_classification.md)
**Framework.** [docs/fw_5_2_era_classification.md](docs/fw_5_2_era_classification.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_2.md](docs/decisions_5_2.md)
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

Scripts sit in `src/`. Paths come from `src/config_5_2.json`. Outputs stay inside this folder. Tests run with
`python -m pytest -q expansions/5_tasks/5_2_era_classification/src/test_5_2.py -p no:cacheprovider` (15 pass on 2026-11-06).

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_era_core_tools.py` | library (dates, intervals, AFT, overlap, sentinel guard) | n/a | nothing |
| `src/_era_date_audit_9t.py` | S0 date audit | yes, run 2026-11-05 | nothing |
| `src/_era_strata_wells_9t.py` | S1 strata | yes, run 2026-11-05 | 4.6 marks for the dated_map stratum |
| `src/_era_interval_labels_9t.py` | S2 interval labels and links | records-only yes (`--records-only`, exploratory) | 4.6 identity-resolved marks (`historic_marks`) |
| `src/_era_label_audit_sample_9t.py` | S3 blind label audit (`draw`, `score`) | draw yes once real labels exist | a second person to fill the sheet (`label_audit_filled`) |
| `src/_era_pair_features_9t.py` | S4 morphology and covariates | yes, run 2026-11-05 | land cover, oil-field boundary, flight year (assumed) |
| `src/_era_model_arms_9t.py` | S5 split, S6 models, S8 figures | gate check yes, model no | 4.6 labels with 20 or more wells in E1 and E2, P1 split file, P2 audit blocks. 2026-11-06 reads them with `ek.read_split_csv` and `ek.require_audit`, and reports the share of undefined AUC draws |
| `src/_era_sentinel_support_9t.py` | S7 sentinel support | yes on records-only labels | 4.6 labels for a meaningful comparison |
| `src/test_5_2.py` | smoke tests | yes | nothing |

Outputs from the 2026-11-05 runs are in `results/tables/` (`era_date_audit_9t.csv`, `era_date_audit_summary_9t.json`, `era_strata_wells_9t.csv`, `era_interval_labels_9t.csv`, `era_pad_morphology_9t.csv`, `era_features_pairs_9t.csv`, `era_sentinel_support_9t.csv`, `era_sentinel_support_summary_9t.json`, `era_model_summary_9t.json`) with run folders beside them.
The labels file holds records-only labels. Every one is E3. The model stops at the readiness gate, as it should.
