# 3.6. California

**Status.** Plan only. Nothing here has been run. Tier A (full design, data assumed).
**Plan.** [docs/plan_geo_california.md](docs/plan_geo_california.md)
**Framework.** [docs/fw_3_6_california.md](docs/fw_3_6_california.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_6.md](docs/decisions_3_6.md)
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

Defaults applied (2026-11-06, user said take defaults). Margin 0.03 recall. Void cap 0.5 (was 0.9). Holm over the one primary A0 pad on ca1. ca_la and class rows are reported, never gated. The provisional pad transfer model is the five-fold `pad/unet_cv5_iso` ensemble (fold_mean) with sha256 per fold.

Review repair (2026-11-06). Pad scoring uses the pad policy (cutoff 0.525) and the pad reference by task. The equipment rule is truth-free and compared at equal K over all candidates, so the union can lose. The pad transfer checkpoint is an explicit unset config key. Open user decisions are in `docs/decisions_3_6.md`.

Built by the build agent. The shared regional-transfer code is `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py`. Expansions 3.4 to 3.8 import it. Stage commands that every region shares are its subcommands. Assumed inputs and their schemas are in `src/config_3_6.json`. A missing assumed input stops a script with a message that names the input, its schema and the VERIFY step. Decisions are in `docs/decisions_3_6.md`. Run the tests with `python -m pytest -q expansions/3_geography/3_6_california/src/test_3_6.py -p no:cacheprovider`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_ca_wells_snapshot.py` | S0 verification and CalGEM snapshot | USGS part yes (ran). Stops at CalGEM | `data/_source/reference/wells_ca_calgem/calgem_wells_snapshot.csv` |
| `src/_ca_field_area_scores.py` | S1 field choice by criteria | LA cover yes (ran). Scoring no | `data/raw/ca_field_candidates.csv`, gap and developed caps |
| `(document) target definition` | S2 target definition | user step | written by a person before labelling |
| `src/_ca_label_packs.py` | S3 blind label packs and double-label draw | no | blocks, NAIP, hillshade, nDSM |
| `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py agree --exp 3.6` | S3 agreement (F1 at IoU 0.3, kappa) | no | two annotators' polygons |
| `expansions/3_geography/3_4_gulf_texas/src/_geo_transfer_core.py derive / infer --task pad --exp 3.6` | S4 derivatives and frozen pad inference | no | Kern or Ventura lidar, pad policy hash |
| `src/_ca_pad_recall_by_class.py` | S5 primary scoring by class with ceiling | no | pad probability raster, truth, 3.0 pad reference tables |
| `src/_ca_unmatched_sample.py` | S6 unmatched draw and summary | no | candidate table, filled label sheet |
| `src/_ca_status_by_pad.py` | S7 status join (descriptive) | no | frozen S5 result, CalGEM snapshot |
| `src/_ca_equipment_rule.py` | S8 equipment rule at equal K (exploratory) | no | nDSM, truth, candidates and score JSON from core `score --task pad` |
| `src/test_3_6.py` | smoke tests | yes. 6 passed |  |
| `src/config_3_6.json` | assumed inputs, schemas, prereg values |  | D-CA1 to D-CA4 are null |
