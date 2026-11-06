# 4.3. Vegetation stress

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05 at the user's request to stop deferring).
**Plan.** [docs/plan_mod_vegetation_stress.md](docs/plan_mod_vegetation_stress.md)
**Framework.** [docs/fw_4_3_vegetation_stress.md](docs/fw_4_3_vegetation_stress.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_3.md](docs/decisions_4_3.md)
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

Built by the build agent. Tests pass with `python -m pytest -q expansions/4_modalities/4_3_vegetation_stress/src/test_4_3.py -p no:cacheprovider` (4 passed). Paths and assumed schemas live in `src/config_4_3.json`. Generic helpers come from `../4_2_thermal/src/_thermal_shared_io.py`. Each script writes a run folder `results/<YYYYMMDD>_<short>_<hash7>/` with `_CONFIG.json`, `_RUN.md` and `_PROVENANCE.json`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_vegstress_shared_io.py` | library (indices, Hanley and McNeil SE) | yes | nothing |
| `src/_vegstress_label_audit_9t.py` | V0 label gate | partly | `--hm-only` runs now. DEP complaint and inspection records `data/raw/dep_complaints_inspections_9t.csv` (request R1) and the real DEP code lists are missing |
| `src/_vegstress_observability_9t.py` | V1 observability | yes | Leaf-off scenes. The held stacks give one usable leaf-on and one usable shoulder scene |
| `src/_vegstress_match_controls_9t.py` | matched controls (before V2) | no | Non-well disturbance layer `data/raw/nonpad_disturbance_9t.gpkg` |
| `src/_vegstress_extract_sites_9t.py` | V2 index extraction and stress anomaly | partly | Runs now with `--pads-only` (exploratory). Matched controls, red-edge and blue bands, more years for a same-season anomaly |
| `src/_vegstress_added_value_9t.py` | V3 Question A at K = 40 per km2 | no | Matched controls and the 3.0 block folds `data/raw/transfer_blocks.csv` |
| `src/_vegstress_leak_test_9t.py` | V4 Question B | no | A V0 gate verdict of success. It refuses to run otherwise |
| `src/test_4_3.py` | smoke tests | yes | nothing |

First runs. All numbers are from the JSON files named.
- `results/20261105_vegstress_labels_7f82a84/vegstress_label_counts_9t.json`. Hanley and McNeil check. At AUC 0.70 with 40 per class the SE is 0.058 and the lower bound is 0.585, above 0.5. Fourteen per class is the smallest equal n that clears 0.5 under simple random sampling. Lease clustering widens this.
- `results/20261105_vegstress_observe_4bb908c/vegstress_observability_9t.json`. 650 pads inside 9t. At 10 m the median pad holds 7 interior pixels and 3 open interior pixels, so the gate is inconclusive. At 20 m and 30 m the median is 0, a failure for those sensors. The median pad edge band is 61% under canopy over 2 m. The September stack has only 37% valid SCL pixels. No leaf-off scene is held.
- `results/20261105_vegstress_sites_30295c9/vegstress_by_site_9t.csv`. Exploratory pads-only NDVI and NDMI per pad and scene. No controls, so it is not a test.
