# 3.1. Warren, Forest and McKean transfer

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_geo_warren_forest.md](docs/plan_geo_warren_forest.md)
**Framework.** [docs/fw_3_1_warren_forest_mckean.md](docs/fw_3_1_warren_forest_mckean.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_1.md](docs/decisions_3_1.md)
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

Built by the build agent. Every script has a docstring, an argparse CLI and a `Run` line. Paths resolve through `expansions/_shared/src/expkit.py` and `src/config_3_1.json`. 3.2 and 3.3 reuse `src/_geo_xfer_lib.py`.

| Script | Stage | Runnable now with held data | What is missing |
|---|---|---|---|
| `expansions/3_geography/3_1_warren_forest_mckean/src/_geo_xfer_lib.py` | shared library | yes | nothing |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_tile_inventory_wfm.py` | S0 inventory | yes. Run on Warren (7 tiles) and McKean (59 tiles) with `--ground` | flight dates (USGS metadata, manual). `mckean_full.las` is not at the documented F: path |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_blocks_roles_wfm.py` | S1 blocks and roles | yes with `--provisional-buffer`. Run on Warren | P1 derived buffer. Prereg seed |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_projected_width_wfm.py` | S2 projected width | yes. Run on Warren with no margin | margin Δ (user). P1 isolated reference table |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_build_derivs_wfm.py` | S3 0.5 m rebuild | yes, but expensive. Dry run and `--check-9t` run only | compute time. Time one block first with `--block-id` |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_annot_tools_wfm.py` | S4 timing, S6 package and agreement | `package` yes. `timing` and `agreement` need people | reviewers, blind truth GeoPackage |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_prereg_draft_wfm.py` | S5 preregistration draft | yes. Draft written with a blocker list | margin, P1 checkpoints, flight dates, reviewers |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_frozen_infer_wfm.py` | S7a frozen inference | after S3. `--allow-cv5` gives a provisional run | P1 isolated checkpoints, S3 stack |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_score_k40_wfm.py` | S7b scoring and sensitivities | no | blind truth (S6), committed prereg, S7a raster |
| `expansions/3_geography/3_1_warren_forest_mckean/src/_xfer_error_review_wfm.py` | S8 error review | no | an S7b run |
| `expansions/3_geography/3_1_warren_forest_mckean/src/config_3_1.json` | config | yes | assumed inputs are listed under `assumed` with schema and source |
| `expansions/3_geography/3_1_warren_forest_mckean/src/test_3_1.py` | smoke test | yes. 11 passed | nothing |

S9 (association) is a hand-off to 5.6 and has no code here.

**Outputs produced (cheap runs on held data).**
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_tile_inventory_warren.csv` and `.json`. 7 tiles, EPSG:6346 with NAVD88 Geoid12B, ground 2.42 points per m² (median), void 0.50.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/mckean/xfer_tile_inventory_mckean.csv` and `.json`. 59 B19 tiles in EPSG:6350, ground 3.41 points per m² (median), void 0.52.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_blocks_roles_warren.gpkg`, `xfer_audit_blocks_warren_v1.csv`, `xfer_blocks_roles_warren.json`. PROVISIONAL buffer (192 m). 112 blocks, 19 low-density, 71 test, 22 audit, adaptation dropped.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_projected_width_warren.csv` and `.json`. Against the provisional 9t reference.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_recompute_check_9t.json`. Six channels recompute exactly. Slope differs (r 0.997).
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_prereg_draft_warren.md`. Draft only, with blockers.

The Warren roles file uses a provisional buffer and the master seed. Redraw it with the preregistered seed and the P1 buffer before annotation.
