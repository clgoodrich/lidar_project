# 7.1. Self-supervised pretraining

**Status.** Plan only. Nothing here has been run. Tier A (full depth, 2026-11-05).
**Plan.** [docs/plan_scale_pretraining.md](docs/plan_scale_pretraining.md)
**Framework.** [docs/fw_7_1_pretraining.md](docs/fw_7_1_pretraining.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_7_1.md](docs/decisions_7_1.md)
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

Built by the build agent. Nothing was trained. The smoke test runs one CPU batch per objective.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_ssl_runtime_bench_9t.py` | S0 runtime benchmark | yes | nothing. Not run by the build agent (GPU timing is a user step) |
| `src/_ssl_corpus_chips_us.py` | S1 corpus index and norm stats | no | corpus window list `data/raw/ssl_corpus_windows_us.csv`, Warren footprint and P2 audit-plus-buffer footprint in `data/raw/` |
| `src/_ssl_pretrain_objectives_us.py` | S2 pretraining A1, A2, A3 | no | chip index and norm stats from S1 |
| `src/_ssl_identity_probe_us.py` | QC 7 survey-identity probe | no | a pretrained checkpoint |
| `src/_ssl_label_subsets_9t.py` | S3 nested label subsets | yes with `--historical` (provisional) | P1 future split `data/9t/results/splits/cv_splits_future_9t_v1.json` for the primary |
| `src/_ssl_finetune_pit_9t.py` | S3 fine-tune, S4 arm A4, S6 arm A5 | A0 yes on the provisional split | A1 to A3 need S2 checkpoints. A4 needs 6.3 validated labels. A5 is not built. P2 audit list |
| `src/_ssl_curve_score_9t.py` | S5 curves and primary test, S7 audit once | no | fine-tune outputs and the primary arm (user decision) |
| `src/config_7_1.json` | assumed inputs and frozen parameters | yes | |
| `src/test_7_1.py` | smoke test | yes | 3 passed |
