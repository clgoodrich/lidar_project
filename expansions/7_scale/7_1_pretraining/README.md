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

## Build status (2026-11-06)

Review fixes 7.1-01, 7.1-02 and the 7.2-01 G pattern were applied on 2026-11-06. Nothing was trained on real data.

**No audit exclusion on disk.** The P2 audit file `data/9t/results/splits/audit_blocks_9t_v1.csv` does not exist yet.
Every 7.1 product on disk ran with no audit exclusion and is exploratory.
That is the label subsets JSON `data/processed/ssl_label_subsets_9t.json`, rebuilt on 2026-11-06 with `--allow-no-audit`.
It now carries `audit_guard = "no audit exclusion, exploratory"`. Its subsets did not change (75 subsets, no empty fraction).
No fine-tune or curve run exists yet.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_ssl_runtime_bench_9t.py` | S0 runtime benchmark | yes | nothing. Not run by the build agent (GPU timing is a user step) |
| `src/_ssl_corpus_chips_us.py` | S1 corpus index and norm stats | no | corpus window list `data/raw/ssl_corpus_windows_us.csv`, Warren footprint and P2 audit-plus-buffer footprint in `data/raw/` |
| `src/_ssl_pretrain_objectives_us.py` | S2 pretraining A1, A2, A3 | no | chip index and norm stats from S1 |
| `src/_ssl_identity_probe_us.py` | QC 7 survey-identity probe | no | a pretrained checkpoint |
| `src/_ssl_label_subsets_9t.py` | S3 nested label subsets | yes with `--historical --allow-no-audit` (provisional, exploratory) | P1 future split and the frozen P2 audit file for the primary |
| `src/_ssl_finetune_pit_9t.py` | S3 fine-tune, S4 arm A4, S6 arm A5, `--predict-audit` | A0 yes with `--allow-no-audit` | A1 to A3 need S2 checkpoints. A4 needs 6.3 validated labels. A5 is not built. `--predict-audit` needs the frozen P2 audit |
| `src/_ssl_curve_score_9t.py` | S5 curves and primary test, S7 `--audit-once` | no | fine-tune outputs, the primary arm and G (user decisions). `--audit-once` also needs the frozen audit and `finetune.audit_model_fold` |
| `src/config_7_1.json` | assumed inputs and frozen parameters | yes | G, primary arm, audit model fold (user) |
| `src/test_7_1.py` | tests | yes | 10 passed |

What changed on 2026-11-06.
- The audit file is read only through `ek.require_audit`. A missing file stops subsets and fine-tune runs unless `--allow-no-audit`.
- Audit and buffer blocks leave train and inner validation. Audit blocks leave the held-out lists before prediction.
- Every fine-tune output carries an `audit_guard` column and the audit hash.
- `--audit-once` now scores the sealed audit blocks once from `--predict-audit` outputs. It writes `results/tables/ssl_audit_lock.json` before scoring. It refuses with no frozen audit.
- G comes from the config or the preregistration only. An unset G gives an inconclusive decision. G_raw is reported and never floored.
- Training windows are redrawn every epoch with child seeds. Validation windows stay fixed.
- Scoring takes cutoff and matching from `ek.policy_for("pit_floor")` through the 7.3 scorer (cutoff 0.35, block-local matching). Out-of-fold files are read strictly.
