# 7.2. Active learning

**Status.** Plan only. Nothing here has been run. Tier A (full depth, 2026-11-05).
**Plan.** [docs/plan_scale_active_learning.md](docs/plan_scale_active_learning.md)
**Framework.** [docs/fw_7_2_active_learning.md](docs/fw_7_2_active_learning.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_7_2.md](docs/decisions_7_2.md)
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

Built by the build agent. The replay ran once on real 9t data with 3 seeds and no P2 audit list. It is exploratory and is rerun after P2.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_al_split_pool_stop_9t.py` | S0 split, item tables | yes with `--no-audit` (stamped) | P2 audit list `data/9t/results/splits/audit_blocks_9t_v1.csv`. Extra discovery blocks `data/raw/discovery_blocks_extra.gpkg` (optional) |
| `src/_al_policies_select_9t.py` | S3 step 1 batch draw (R, U, D, H, B) with exact pi | yes | a round model hash for live use |
| `src/_al_replay_sim_9t.py` | S1 simulation replay | yes | nothing. Ran with 3 seeds. The prereg asks for 10 |
| `src/_al_review_round_9t.py` | S3 steps 2 and 3 blind package and ingestion | yes | reviewers (assumption 1) |
| `src/_al_review_timer_minutes.py` | effort timer (assumption 5) | yes | a 10-item trial with a reviewer |
| `src/_al_retrain_round_9t.py` | S2 and S3 step 4 labels, weights, retrain launch | inputs yes, training no | `trainer_cmd` in config (P1 isolated pit trainer) |
| `src/_al_curve_score_9t.py` | S4 stop rule, S5 primary test, S6 discovery | yes on replay output | live rounds for the real claim |
| `src/config_7_2.json` | assumed inputs and frozen parameters | yes | budget, batch, G, temperature, hybrid split (user) |
| `src/test_7_2.py` | smoke test | yes | 4 passed |

Products of the 2026-11-05 replay are in `results/tables/` (split, items, oracle, stopping set, `al_replay_*`) and `results/figures/al_replay_curves_minutes_9t.png`. The default logistic re-ranker barely separates the policies. Every policy ended near 0.47 stopping-set recall and the decision was inconclusive.
