# 4.8. Leaf-off optical imagery

**Status.** Code built 2026-11-05 (see Build status). No result is on file. Tier B.
**Plan.** [docs/plan_mod_leafoff_optical.md](docs/plan_mod_leafoff_optical.md)
**Framework.** [docs/fw_4_8_leafoff_optical.md](docs/fw_4_8_leafoff_optical.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_8.md](docs/decisions_4_8.md)
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
Built by the build agent. The framework was brought to full depth the same day. Assumed inputs and their schemas are in `src/config_4_8.json`. Tests. `python -m pytest -q expansions/4_modalities/4_8_leafoff_optical/src/test_4_8.py -p no:cacheprovider` (2 passed, offline).

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_leafoff_kit_4_8.py` | fetchers, image measures, status rules | yes | nothing |
| `src/_leafoff_coverage_table_9t.py` | S0 coverage | yes (known sources only) | program search log `data/raw/leafoff_programs.csv`. PEMA flight dates. Warren bbox |
| `src/_leafoff_feature_sample_9t.py` | S1 sample | yes | seed and cutoff confirmed by the user before running |
| `src/_leafoff_chip_status_9t.py` | S2 chips, S4 visible ground | yes with network (PASDA, NAIP). Offline needs a local mosaic | PEMA flight dates, or every PEMA chip is "undated" |
| `src/_leafoff_georeg_offset_9t.py` | S3 registration | template yes. Summary no | a person clicking 10 intersections per source in QGIS |
| `src/_leafoff_review_gate_9t.py` | S5 agreement and gate | gate yes after S2. Agreement no | two reviewer sheets in `data/raw/reviews/` |
| `src/test_4_8.py` | smoke tests | yes | nothing |
