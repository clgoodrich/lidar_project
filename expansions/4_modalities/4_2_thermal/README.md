# 4.2. Thermal

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05 at the user's request to stop deferring).
**Plan.** [docs/plan_mod_thermal.md](docs/plan_mod_thermal.md)
**Framework.** [docs/fw_4_2_thermal.md](docs/fw_4_2_thermal.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_2.md](docs/decisions_4_2.md)
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

Built by the build agent. Tests pass with `python -m pytest -q expansions/4_modalities/4_2_thermal/src/test_4_2.py -p no:cacheprovider` (5 passed). Paths and assumed schemas live in `src/config_4_2.json`. Each script writes a run folder `results/<YYYYMMDD>_<short>_<hash7>/` with `_CONFIG.json`, `_RUN.md` and `_PROVENANCE.json`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_thermal_shared_io.py` | library (also used by 4.3) | yes | nothing |
| `src/_thermal_gate_contrast_9t.py` | T0 mechanism verdict, T1 fill fraction and gate | partly | Fill fraction runs on held pads. Scene indexes `data/raw/scene_index_<sensor>_9t.csv`, tie points `data/raw/tiepoints_<sensor>_9t.csv` and a measured `proxy_dT_K` are missing, so the verdict stays inconclusive |
| `src/_thermal_match_clearings_9t.py` | matched clearings and forest controls (before T2) | no | Non-pad clearing layer `data/raw/nonpad_clearings_9t.gpkg` (layer name in the annotations not confirmed) |
| `src/_thermal_extract_samples_9t.py` | T2 pixel-weighted LST and covariates | no | LST scenes and scene index. Runs only if T1 is not a failure |
| `src/_thermal_contrast_model_9t.py` | T3 covariate-adjusted contrast and gate | no | T2 samples |
| `src/_thermal_added_value_9t.py` | T4 added value at K = 40 per km2 | no | T2 samples and the 3.0 block folds `data/raw/transfer_blocks.csv` |
| `src/test_4_2.py` | smoke tests | yes | nothing |
| none | T5 drone appendix | design only | Not scheduled by the framework |

First run. `results/20261105_thermal_gate_3c7e696/` holds the T1 fill fractions for the 650 pads inside the 9t CHM extent. Landsat TIRS at 100 m has median fill 0.13 and 2.3% of pads at f of 0.25 or more. ECOSTRESS at 70 m has median fill 0.24 and 46% of pads at 0.25 or more. A pad would need a true surface difference of about 7.6 K (Landsat) or 4.2 K (ECOSTRESS) for the median diluted contrast to reach delta_T of 1.0 K. T0 is open because two routes (gravel thermal inertia, soil moisture) carry an independent thermal term. Numbers are from `thermal_gate_summary_9t.json`.
