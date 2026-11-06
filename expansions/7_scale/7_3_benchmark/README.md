# 7.3. Terrain-feature benchmark

**Status.** Plan only. Nothing here has been run. Tier A (full depth, 2026-11-05).
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

## Build status (2026-11-05)

Built by the build agent. A provisional release was exported on 2026-11-05 from the historical held-out lists with 4 tiles. It has no hidden test and is not for release. Its baselines used B = 200.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_bench_card_datasheet_9t.py` | S0 datasheet from saved files | yes | second-reviewer labels from 6.3 (section says not measured), licences (VERIFY) |
| `src/_bench_export_release_9t.py` | S1 export, manifest, `--verify` | yes with `--provisional-historical` | P1 future split and P2 audit list for a real release |
| `src/_bench_evaluate_recall_k.py` | S2 official scorer (`evaluate.py`) | yes | nothing |
| `src/_bench_baselines_score_9t.py` | S3 baselines on shipped dev clips | yes for pit_unet_cv5 and pad_unet_cv5_iso | P1 isolated pit model, unetpp_r34_imagenet fold rasters. Pad cutoff (user) |
| `src/_bench_validity_checks_9t.py` | S4 H1, H2, H3, label ceiling | no | unetpp and second-seed candidate files, test block count, margin (user), 6.3 labels |
| `src/_bench_fresh_checkout_test.py` | S5 fresh-checkout reproduction | yes | passed on the provisional release |
| `src/_bench_leaderboard_submit_9t.py` | S6 rules, submissions, leaderboard | rules and render yes | hidden-test labels (P2), margin (user) |
| `src/config_7_3.json` | assumed inputs | yes | |
| `src/test_7_3.py` | smoke test | yes | 3 passed |

The release sits in `data/processed/terrain_v1/` (gitignored). Provisional dev-test recall at 40 per km2 is 0.673 for pit_unet_cv5 and 0.063 for pad_unet_cv5_iso. The pad number reflects the 0.10 cutoff, which merges pad blobs. See the decisions log.
