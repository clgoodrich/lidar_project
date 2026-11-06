# 7.3. Terrain-feature benchmark

**Status.** Built. A provisional release ran on 2026-11-05 and was rescored on 2026-11-06. Tier A (full depth).
**Plan.** [docs/plan_scale_benchmark.md](docs/plan_scale_benchmark.md)
**Framework.** [docs/fw_7_3_benchmark.md](docs/fw_7_3_benchmark.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_7_3.md](docs/decisions_7_3.md)
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

Review repair on 2026-11-06 (findings 7.3-01, 7.3-02, F02, F05). The provisional release was exported again and its baselines were rescored.

**No audit exclusion.** Every 7.3 output on disk ran with no audit exclusion. The P2 audit file `data/9t/results/splits/audit_blocks_9t_v1.csv` does not exist. The release is provisional. It uses the historical held-out lists. It has no hidden test. Its numbers are exploratory and not for release.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_bench_card_datasheet_9t.py` | S0 datasheet from saved files | yes | second-reviewer labels from 6.3 (section says not measured), licences (VERIFY) |
| `src/_bench_export_release_9t.py` | S1 export, manifest, `--verify` | yes with `--provisional-historical` | frozen P1 future split and frozen P2 audit set for a real release. Reads them with `ek.read_split` and `ek.require_audit` |
| `src/_bench_evaluate_recall_k.py` | S2 official scorer (`evaluate.py`) | yes | nothing. Needs `--task`. Policy from `ek.policy_for` or the release `scoring_policy.json` |
| `src/_bench_baselines_score_9t.py` | S3 baselines on shipped dev clips | yes for pit_unet_cv5 and pad_unet_cv5_iso | P1 isolated pit model, unetpp_r34_imagenet fold rasters |
| `src/_bench_validity_checks_9t.py` | S4 H1, H2, H3, label ceiling | no | unetpp and second-seed candidate files, test block count, margin (user), 6.3 labels |
| `src/_bench_fresh_checkout_test.py` | S5 fresh-checkout reproduction | yes | passed on the rescored provisional release (2026-11-06) |
| `src/_bench_leaderboard_submit_9t.py` | S6 rules, submissions, leaderboard | rules and render yes | hidden-test labels (P2), margin (user). Submit now needs `--task` and the baseline score JSON |
| `src/config_7_3.json` | assumed inputs | yes | |
| `src/test_7_3.py` | tests | yes | 10 passed. P1 and P2 inputs come from the real producers |

The release sits in `data/processed/terrain_v1/` (gitignored). Dev-test recall at 40 per km2, B = 200, primary policy fw00_s4_20261105, within-block matching.

| Baseline | Before (cutoff 0.10, cross-block) | After (pit 0.35, pad 0.525, within block) |
|---|---|---|
| pit_unet_cv5 | 0.673 (0.496 to 0.764) | 0.911 (0.816 to 0.968), 92 of 101 |
| pad_unet_cv5_iso | 0.063 (0.025 to 0.115) | 0.730 (0.643 to 0.823), 81 of 111 |

The pit number agrees with the 3.0 reproduction of 0.909. The old pad number came from the 0.10 cutoff, which merges pad blobs.
