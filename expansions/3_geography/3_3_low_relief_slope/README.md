# 3.3. Low-relief sensitivity

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_geo_low_relief_midwest.md](docs/plan_geo_low_relief_midwest.md)
**Framework.** [docs/fw_3_3_low_relief_slope.md](docs/fw_3_3_low_relief_slope.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_3.md](docs/decisions_3_3.md)
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

Built by the build agent. Step 1 (S1, S2, S5) ran on held data on the CPU in about two minutes.

| Script | Stage | Runnable now with held data | What is missing |
|---|---|---|---|
| `expansions/3_geography/3_3_low_relief_slope/src/_slope_recall_tercile_9t.py` | S1 slope stratification | yes. Run | margin Δ for the gate (user) |
| `expansions/3_geography/3_3_low_relief_slope/src/_slope_confound_logit_9t.py` | S2 confound checks | yes. Run | nothing |
| `expansions/3_geography/3_3_low_relief_slope/src/_slope_terrain_edit_9t.py` | S3 paired edits | build yes (`--no-score`). Scoring needs the GPU | P1 isolated checkpoints, P1 buffer, P2 audit list. `--allow-cv5` gives a provisional run |
| `expansions/3_geography/3_3_low_relief_slope/src/_slope_edit_seam_check_9t.py` | S4 seam checks | after S3 | an S3 run |
| `expansions/3_geography/3_3_low_relief_slope/src/_slope_area_gate_9t.py` | S5 area gate | yes. Run | margin Δ. The Illinois fetch is a user step |
| `expansions/3_geography/3_3_low_relief_slope/src/config_3_3.json` | config | yes | assumed P1 and P2 inputs are listed under `assumed` |
| `expansions/3_geography/3_3_low_relief_slope/src/test_3_3.py` | smoke test | yes. 6 passed | nothing |

**Outputs produced.** All in `expansions/3_geography/3_3_low_relief_slope/results/20261105_slope_recall_5886eff/`.
- `slope_recall_features_9t.csv`, `slope_recall_blocks_9t.csv`, `slope_recall_terciles_9t.csv`, `slope_recall_summary_9t.json`, `slope_recall_terciles_9t.png`
- `slope_confound_by_tercile_9t.csv`, `slope_confound_logit_9t.csv`, `slope_confound_summary_9t.json`
- `slope_area_gate_9t.json`
- `_CONFIG.json`, `_RUN.md`, `_PROVENANCE.json`

**Step 1 result.** Evidence level (a). Exploratory association. Original CV5 sampler, so 9t recall is optimistic.
- Pooled out-of-fold recall at 40 per km² is 0.909 (457 of 503 floors, 115 blocks, 95% block bootstrap 0.881 to 0.934). It reproduces the archival 0.909.
- Feature-level recall by slope tercile is 0.899 (low), 0.934 (middle) and 0.893 (high). Low minus high is +0.006 (−0.064 to +0.075).
- Block-level low minus high is +0.042 (−0.030 to +0.115).
- No margin is set, so the decision is no_margin_set. The area test stays gated.
- The 9t lowest tercile ends at 7.7 degrees. None of the 503 scored pits has a 25 m slope under 2 degrees. Step 1 says little about flat farmland.
- In the logistic fit, depth carries the clearest partial association (odds ratio 1.68 per SD). Measured depth rises with slope, so the two are entangled.
- The blocks CSV is the provisional 9t reference table for 3.1 and 3.2 scoring.
