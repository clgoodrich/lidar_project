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

## Build status (2026-11-06)

Review fixes 7.2-01 and 7.2-02 were applied on 2026-11-06. The replay was rerun on real 9t data.

**No audit exclusion.** The P2 audit file `data/9t/results/splits/audit_blocks_9t_v1.csv` does not exist yet.
Every 7.2 product on disk ran with no audit exclusion and is exploratory.
That covers the 2026-11-05 run and the 2026-11-06 rerun. The split JSON says so in `audit_source`.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_al_split_pool_stop_9t.py` | S0 split, item tables | yes with `--no-audit` (stamped exploratory) | P2 audit list. Extra discovery blocks `data/raw/discovery_blocks_extra.gpkg` (optional) |
| `src/_al_policies_select_9t.py` | S3 step 1 batch draw (R, U, D, H, B) with exact pi | yes | a round model hash for live use |
| `src/_al_replay_sim_9t.py` | S1 simulation replay | yes | nothing. Ran with the preregistered 10 seeds |
| `src/_al_review_round_9t.py` | S3 steps 2 and 3 blind package and ingestion | yes | reviewers (assumption 1) |
| `src/_al_review_timer_minutes.py` | effort timer (assumption 5) | yes | a 10-item trial with a reviewer |
| `src/_al_retrain_round_9t.py` | S2 and S3 step 4 labels, weights, retrain launch | inputs yes once `seed_label_blocks` is set, training no | `seed_label_blocks` (user) and `trainer_cmd` (P1 isolated pit trainer) |
| `src/_al_curve_score_9t.py` | S4 stop rule, S5 primary test, S6 discovery | yes on replay output | G (user) and live rounds for the real claim |
| `src/config_7_2.json` | assumed inputs and frozen parameters | yes | budget, batch, G, seed blocks, temperature, hybrid split (user) |
| `src/test_7_2.py` | tests | yes | 5 passed |

What changed on 2026-11-06.
- G comes from the config or the preregistration only. It is unset, so the decision is inconclusive. G_raw is reported and never floored.
- The stop rule is enforced. All curves are cut at the stop round before any estimate.
- The live retrain trains only on the policy's acquired labels plus declared seed blocks. Reviewer additions are kept per arm.
- Items are scored with `ek.policy_for("pit_floor")` through the 7.3 scorer 2. The cutoff moved from 0.10 to 0.35 and matching is block-local.
- The split reads the audit file through `ek.require_audit`.
- The replay no longer crashes when a policy's pool is exhausted.

Rerun numbers, old (2026-11-05) to new (2026-11-06).

| Quantity | 2026-11-05 | 2026-11-06 |
|---|---|---|
| Item cutoff | 0.10 | 0.35 (policy) |
| Pool items (C / W) | 1071 / 28 | 469 / 28 |
| Stopping-set candidates | 295 | 134 |
| Seeds | 3 | 10 |
| G used | 0.0 (floored) | unset |
| G_raw | -0.0043 | 0.0 |
| Stop round (enforced) | 2 (ignored) | 2 (enforced, 14 rounds run) |
| U minus R | 0.0 [-0.0001, 0.0079] | 0.0 [-0.0064, 0.0043] |
| Permutation p | 1.0 | 1.0 |
| Decision | inconclusive | inconclusive (G unset) |
| R and U recall at the read point | 0.479 and 0.479 | 0.926 and 0.926 |
| Pool recall (discovery) | 0.659 [0.590, 0.728] | 0.916 [0.884, 0.944] |

An intermediate run with 10 seeds on the old 0.10 items gave U minus R 0.0038 [0.0, 0.0094] and p 0.071.
The higher recall in the new run comes from the stricter cutoff. Fewer candidates fit inside K, so more of the truth falls in the top K.
The replay still cannot separate the policies.
Products are in `results/tables/` (split, items, oracle, stopping set, `al_replay_*`, `al_scoring_policy_9t.json`) and `results/figures/al_replay_curves_minutes_9t.png`.
