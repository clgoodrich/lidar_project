# 4.7. Drone lidar density ladder

**Status.** Code built 2026-11-05 (see Build status). No result is on file. Tier A.
**Plan.** [docs/plan_mod_drone_lidar.md](docs/plan_mod_drone_lidar.md)
**Framework.** [docs/fw_4_7_drone_lidar.md](docs/fw_4_7_drone_lidar.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_7.md](docs/decisions_4_7.md)
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
Built by the build agent 2026-11-05. Review fixes 2026-11-06 (4.7-01, nested ladder). Assumed inputs and their schemas are in `src/config_4_7.json`. Nothing runs on real data until the NETL reply (R2). The request itself is a user step. Tests. `python -m pytest -q expansions/4_modalities/4_7_drone_lidar/src/test_4_7.py -p no:cacheprovider` (5 passed on 2026-11-06, synthetic LAS through the PDAL CLI).

| Script | Stage | Runnable now | Missing |
|---|---|---|---|
| `src/_drone_kit_4_7.py` | shared helpers (laspy counts, PDAL count rasters) | yes | nothing |
| `src/_drone_provenance_oc.py` | S1 provenance | no | NETL metadata JSON, clouds and site layer in `data/_source/drone_netl/` |
| `src/_drone_ingest_density_oc.py` | S2 density, void, canopy | yes on any EPSG:6346 LAS | NETL clouds |
| `src/_drone_thin_ladder_oc.py` | S3 thinning ladder | yes on any LAS with S2 output | NETL clouds. Since 2026-11-06 rungs are nested and every rung is reclassified by SMRF through the PDAL CLI |
| `src/_drone_rung_stack_oc.py` | S4 DEMs, full stack, inference | `--dem-only` yes. Full mode needs the GPU | NETL clouds. Frozen isolated pit model choice (P1) |
| `src/_drone_density_curve_oc.py` | S5 recall curve | no | S4 probability rasters. NETL site layer with hillside |
| `src/_drone_vs_airborne_oc.py` | S6 comparison | no | S5 curve. 3.0 scorer output for 9t airborne |
| `src/test_4_7.py` | smoke tests | yes | nothing |

Area folder is `data/oilcreek/` (the existing folder), not `data/oil_creek/` as the framework wrote. Thinned clouds are `*.las` and rung stacks sit under `data/**/derived/**`, so both are already git-ignored.
