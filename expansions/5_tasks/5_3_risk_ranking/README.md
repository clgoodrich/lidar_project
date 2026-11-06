# 5.3. Risk ranking

**Status.** Plan only. Nothing here has been run. Tier A (rewritten 2026-11-05).
**Plan.** [docs/plan_task_risk_ranking.md](docs/plan_task_risk_ranking.md)
**Framework.** [docs/fw_5_3_risk_ranking.md](docs/fw_5_3_risk_ranking.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_5_3.md](docs/decisions_5_3.md)
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

Defaults pass (2026-11-06). Candidate H stays unrankable. E min_coverage is 1.0. max_undefined is 0 in the config and a preregistration cannot loosen it. Every provenance file holds repo-relative paths. Tests pass (19).
Rerun on the new 5.6 output (768 pit rows). Sites 1354 to 1394. Candidate sites 296 to 336. A and D still rank nothing. B top 50 is still one tie of 169 records.

Review fixes 2026-11-06 (5.3-01, 5.3-02 and minors). Paths are repo-relative. Config is `src/config_5_3.json`. Tests are `src/test_5_3.py` (16 passed).

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_ranking_core.py` | library for S1 to S7 | n/a | nothing |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_io_9t.py` | shared loaders | n/a | nothing |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_data_audit_9t.py` | S0 audit | yes | 13 assumed layers are reported missing |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_exposure_layers_9t.py` | S1 sites and exposure | yes, partial | water wells, buildings, streams, wetlands, public supply, protected areas. E is roads only today |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_hazard_proxy_9t.py` | S2 hazard proxy | yes, partial | candidate H is unrankable until a rule for the missing plugging record is chosen |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_scenarios_9t.py` | S3 scenarios | yes, refuses A and D | E has one component, so A and D are unrankable. B and C rank with ties reported |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_sensitivity_9t.py` | S4 sensitivity | yes | any weight on E is unrankable until E is usable |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_rank_bootstrap_9t.py` | S5 rank stability | yes | stated positional error of DEP records (30 m assumed) |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_endpoint_check_9t.py` | S6 endpoint check | no | preregistration JSON, field flux table, decision user, N and delta_enrich |
| `expansions/5_tasks/5_3_risk_ranking/src/_risk_report_tables_9t.py` | S7 report tables | yes | endpoint result (Q1 not run) |

Run order. S0, S1, S2, S3, S4, S5, S7. S6 runs only after the preregistration is written and S3 is rerun under it.
Outputs go to `results/tables/`, `results/figures/`, `data/processed/` and run folders in `results/runs/`.
The framework names `data/9t/results/risk/` and `notebooks/wellsight_v2/s7_analysis/`. The build keeps everything inside this expansion folder.

The 2026-11-05 top 50 of A and B was an artefact. Candidate H averaged only the components a candidate had, so every candidate got the same H above every record. E was one 0/1 road column. Ties were then broken by row order. Since 2026-11-06 a missing component makes a site unrankable under the default rule. E with fewer than 2 components makes A and D unrankable. Ties share a rank and are reported. On 9t today A and D rank nothing. B ranks the 1058 records only, and its top 50 is one tie of 169 abandoned and orphan records. Every candidate row is conditional on the feature model.
