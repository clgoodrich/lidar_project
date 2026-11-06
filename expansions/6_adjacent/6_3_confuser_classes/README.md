# 6.3. Confuser classes and negative-class training

**Status.** Plan only. Nothing here has been run. Tier A.
**Plan.** [docs/plan_adj_negative_classes.md](docs/plan_adj_negative_classes.md)
**Framework.** [docs/fw_6_3_confuser_classes.md](docs/fw_6_3_confuser_classes.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_6_3.md](docs/decisions_6_3.md)
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

Defaults pass (2026-11-06). The negative exclusion radius is 30 m (`train.neg_truth_exclusion_m`). It no longer follows jitter_m. Nothing on CPU depends on it, so nothing was rerun. Tests pass (11).

Tests. `python -m pytest -q expansions/6_adjacent/6_3_confuser_classes/src/test_6_3.py -p no:cacheprovider` gives 10 passed.
Review fixes on 2026-11-06. No negative centre may sit within 30 m of a truth pit (the window jitter). This holds for the confuser and the random arm. On 9t, 477 of 481 matched candidates and 13 of 207 undecided candidates lie that close, so they can never be negative centres. The split is read through `ek.read_split` (P1 JSON) or `ek.read_split_csv` (P1 CSV, legacy words mapped). Audit blocks are read through `ek.require_audit`. Training excludes audit and buffer blocks. Scoring uses audit blocks only. The burned confuser label raster is rebuilt when its base raster or polygons change (sha256 sidecar). The pooled score counts a hit only on truth inside the audit blocks, in the block of that truth.
Real-data check on 2026-11-06. The P1 exporter CSV `data/9t/results/splits/cv_split_blocks_pit_9t.csv` reads into 5 folds with canonical roles.
The trainer wrapper imports `_dl.py` and the `IsolatedSampler` of `_pad_unet_iso_cv5.py`. No file under `notebooks/` was edited. Nothing was trained.
The confusing class goes into training as a negative class, the way the road model learned drainage. It is not a post-hoc filter.

| Script | Stage | Runnable now | What is missing |
|---|---|---|---|
| `src/_confuser_common_9t.py` | shared (candidates, matching, top K, dedupe) | yes | nothing |
| `src/_confuser_sample_9t.py` | S0 pilot draw and S1 stratified sample | no | frozen P2 audit file `data/9t/results/splits/audit_blocks_9t_v1.csv`. `--allow-no-audit` draws an exploratory sample |
| `src/_confuser_sheets_9t.py` | S2 blind contact sheets and label file | no | S1 sample. Aerial chips optional |
| `src/_confuser_agreement_9t.py` | S0 pilot agreement, S3 adjudication | no | two reviewers' labels (user step) |
| `src/_confuser_unet_cv5_9t.py` | S4 three arms, 3 seeds, 5 folds | dry run no, train no | P1 split `data/9t/results/splits/cv_splits_future_pit_9t_v1.csv` or the JSON, frozen P2 audit file, S3 labels, GPU |
| `src/_confuser_pooled_score_9t.py` | S5 pooled blind scoring and gate | no | S4 probability rasters, pooled blind labels, margin delta |
| `src/_confuser_arms_figure_9t.py` | S6 figure | no | S5 output |
| `src/config_6_3.json` | inputs, codebook classes, arms, margins | yes | recall margin delta is a user decision |
