# 3.1. Warren, Forest and McKean transfer

**Status.** Built. Cheap stages ran on held data (inventory, roles, projected width, prereg draft). No target has been scored. Review fixes 2026-11-06. Tier A.
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

## Build status (2026-11-06)

Review fix pass (F02 F03 F08 F11 G-03 G-06 G-07 P1-03, minors). Tests. `python -m pytest -q -p no:cacheprovider expansions/3_geography/3_1_warren_forest_mckean/src/test_3_1.py` (21 passed).
- Scoring is the 3.0 reference scorer. `_geo_xfer_lib.py` keeps its function names and calls `_transfer_score_lib`. Cutoff 0.35 for pits, score-order matching, dedupe.
- Extraction runs once on a shared window over all scored blocks. A seam-crossing blob gives one candidate, equal to the whole-raster oracle.
- The scoring reference is the 3.0 tables (all 144 blocks, policy stamped). The scorer refuses a reference without a policy stamp or with a truth-only footprint.
- S7a writes `results/tables/<area>/xfer_infer_record_<task>_<area>.json`. S7b requires it. Its `provisional_cv5` flag and the reference lineage reach every output. A provisional side makes every decision "descriptive".
- S7b reads the preregistration's json block and checks the declared cutoff, IoU, dedupe, K and checkpoint.
- Low-density blocks enter the role draw, stratified apart. The stratum is scored or reported empty with its reason.
- The buffer is read with `ek.read_buffer(task)`. `assign_roles` refuses a buffer of 0.
- A LAS tile with no CRS raises. Feet or degree tile CRS raises.
- Warren roles redrawn with `--from-roles` (no LAS pass). Main-stratum roles and recheck blocks are unchanged. The 19 low-density blocks are now 14 test and 5 audit (was all ineligible).
- New area `il_cumberland` (assumed, not fetched) for the 3.3 area gate.

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
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_blocks_roles_warren.gpkg`, `xfer_audit_blocks_warren_v1.csv`, `xfer_blocks_roles_warren.json`. PROVISIONAL buffer (192 m). 112 blocks. Redrawn 2026-11-06. Main stratum 71 test and 22 audit. Low-density stratum 14 test and 5 audit. Adaptation dropped.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_projected_width_warren.csv` and `.json`. Against the provisional 9t reference.
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_recompute_check_9t.json`. Six channels recompute exactly. Slope differs (r 0.997).
- `expansions/3_geography/3_1_warren_forest_mckean/results/tables/warren/xfer_prereg_draft_warren.md`. Draft only, with blockers.

The Warren roles file uses a provisional buffer and the master seed. Redraw it with the preregistered seed and the P1 buffer before annotation.
