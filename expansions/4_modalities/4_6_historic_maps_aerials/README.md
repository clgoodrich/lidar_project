# 4.6. Historic maps and aerials

**Status.** Code built 2026-11-05 (see Build status). No result is on file. Tier A.
**Plan.** [docs/plan_mod_historic_maps_aerials.md](docs/plan_mod_historic_maps_aerials.md)
**Framework.** [docs/fw_4_6_historic_maps_aerials.md](docs/fw_4_6_historic_maps_aerials.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_6.md](docs/decisions_4_6.md)
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
Built by the build agent 2026-11-05. Review fixes 2026-11-06 (4.6-01). Assumed inputs and their schemas are in `src/config_4_6.json`. Every script stops with the name of a missing input. Tests. `python -m pytest -q expansions/4_modalities/4_6_historic_maps_aerials/src/test_4_6.py -p no:cacheprovider` (8 passed on 2026-11-06).

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_hist_kit_4_6.py` | shared helpers | yes | nothing |
| `src/_hist_source_search_9t.py` | S0 source table | `--bbox-only` yes, table no | search log `data/raw/hist_sources_9t.csv` (manual search) |
| `src/_hist_topo_crop_9t.py` | S1 crop and renders | yes, on `data/_source/historic_topo_probe/oil_city_1922_62500.tif` | D5 sheets for more dates. Neatline bounds per sheet (VERIFY) |
| `src/_hist_aerial_probe_9t.py` | S2 aerial frames | no | D7 frame index `data/raw/aerial_frame_index_9t.csv` and scans |
| `src/_hist_georef_check_9t.py` | S3 accuracy | no | GCP and check point table `data/_source/historic_topo_probe/<source>_gcp.csv` |
| `src/_hist_marks_merge_9t.py` | S4 agreement and mark layer | no | two digitiser mark sheets in `data/raw/marks/`. Interval resamples pairs as units since 2026-11-06 |
| `src/_hist_marks_vs_records_9t.py` | S5 compare | no | S4 marks with one source date. Oil field footprint (falls back to a DEP hull). OOF pit probability mosaic for comparison 3. Records are filtered to wells spudded by the source date since 2026-11-06 |
| `src/_hist_source_verdicts_9t.py` | S6 verdicts | no | S1 to S4 products |
| `src/test_4_6.py` | smoke tests | yes | nothing |

Outputs that the framework places in `docs/iterations/` are written to `results/tables/*.md` first. The lead copies them when logging the pass.
