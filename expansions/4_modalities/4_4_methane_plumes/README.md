# 4.4. Methane plumes

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05 at the user's request to stop deferring).
**Plan.** [docs/plan_mod_methane_plumes.md](docs/plan_mod_methane_plumes.md)
**Framework.** [docs/fw_4_4_methane_plumes.md](docs/fw_4_4_methane_plumes.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_4_4.md](docs/decisions_4_4.md)
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

Defaults applied 2026-11-06 (user said "take defaults"). The tail extrapolation multiple stays null, so no extrapolation. `m3.max_undefined` is 0 and is passed to the cell bootstrap. M0 reran as `results/20261106_methane_gate_0268845/`. Gate verdicts are unchanged (mean failure, aggregation failure, tail inconclusive, CLOSE). Tests 10 passed.


Built by the build agent. Every script has a docstring, an argparse CLI and a `run()` function. Tests are in `src/test_4_4.py`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_methane_shared_io.py` | helper | yes | nothing |
| `src/config_4_4.json` | config | yes | VERIFY items. Kang et al. 2014 figures, Tanager DL, abandoned-well scenarios |
| `src/_methane_gate_limit_pa.py` | M0 gate and M1 verdict | yes, rerun 2026-11-06 after the review fixes | Per-well rates `data/raw/kang2014_per_well_rates.csv` for the tail step. Without it the tail gate is inconclusive |
| `src/_methane_plume_overlay_pa.py` | M2 overlay and observation opportunity | no | Plume list `data/raw/carbon_mapper_plumes_l2b.csv`, observations `data/raw/carbon_mapper_observations.csv`, facilities `data/raw/active_facilities_pa.gpkg` |
| `src/_methane_source_model_pa.py` | M3 sources, attribution rule, rate ratio | no | The M2 run. The rate ratio also needs the observations table |
| M4 other basins | M0 to M3 with `--basin` | no | Basin rows in `m4_basins`, that basin's measured rates and wells |
| `src/test_4_4.py` | smoke and regression tests | yes | nothing. 10 tests pass (2026-11-06) |

Output written so far.
- `expansions/4_modalities/4_4_methane_plumes/results/20261106_methane_gate_554201c/methane_gate_limit_pa.json`, `methane_gate_limit_pa.csv`, `methane_gate_ratio_bars_pa.png` (rerun 2026-11-06)
- `expansions/4_modalities/4_4_methane_plumes/results/20261105_methane_gate_ea551fb/methane_gate_limit_pa.json`, `methane_gate_limit_pa.csv`, `methane_gate_ratio_bars_pa.png`

M0 result from the config figures. The mean well emits 0.011 kg per hour. R is 8,000 to 16,000 at the stated Tanager limit and 800 at the best case. The mean gate fails. The most wells at distinct coordinates in one 30 m pixel is 4, so aggregation needs 800 wells and fails. The verdict is CLOSE for satellite screening of ordinary small wells. The tail gate is inconclusive until per-well rates are typed in, so M2 stays live for the tail only. Counting raw DEP records gives 41 wells in one pixel, because DEP stacks a lease on one placeholder point. Under that count aggregation is inconclusive.

Review fixes 2026-11-06. The tail gate returns `not identifiable by extrapolation` when the limit lies above the declared multiple of the largest measured rate. The multiple is a user decision and is null. Tail success needs at least one expected exceeding well at the lower bound. Undefined bootstrap draws are counted. M3 reports separation and an exact conditional interval. CLOSE still follows for ordinary small wells.

Run order. M0, then M2 when the catalogue is on disk, then M3.
