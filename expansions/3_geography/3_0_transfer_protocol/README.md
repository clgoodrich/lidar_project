# 3.0. Transfer protocol

**Status.** Built and partly run on held 9t data (2026-11-05). Review fixes 2026-11-06. No target area has been scored. Tier A.
**Plan.** [docs/plan_geo_transfer_protocol.md](docs/plan_geo_transfer_protocol.md)
**Framework.** [docs/fw_3_0_transfer_protocol.md](docs/fw_3_0_transfer_protocol.md) (stages, gates, analysis plan, handoff)
**Decisions.** [docs/decisions_3_0.md](docs/decisions_3_0.md)
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

Review fix pass (F02 F08 F11 G-02 G-03 G-05 G-06, minors). Tests. `python -m pytest -q -p no:cacheprovider expansions/3_geography/3_0_transfer_protocol/src/test_3_0.py` (18 passed).
- One scoring policy. Cutoff, minimum area, IoU and match order come from `ek.policy_for(task)`. The policy dict and hash are stamped into every output. 3.1, 3.2 and 3.3 call this scorer.
- Dedupe was inactive before this pass (NaN versus None). It now drops second pieces.
- Edge blocks are blocks on the data boundary. Interior nodata counts toward the void fraction, capped by the preregistered `void_cap` or `void_cap_default` 0.5.
- Grid contract. Metric CRS with an EPSG:6346 horizontal part, full affine transform, shape.
- The reference tables now cover all 144 9t blocks. Pit-free and pad-free blocks are filled from the fold rasters, which never trained on them. Old to new pooled recall at K 40 (global / per fold). Pit 0.917 / 0.909 to 0.946 / 0.938. Pad 0.815 / 0.809 to 0.855 / 0.848.
- The decision report and the harness check the preregistration's cutoff, IoU, dedupe, K and checkpoint. An archival, historical or provisional reference gives verdict "descriptive". Both 9t references are provisional today.

| Script | Change 2026-11-06 |
|---|---|
| `src/_transfer_score_lib.py` | `policy`, `extract`, `score_tables`, grid checks, edge and void rule, `read_ref_tables`, `ref_block_counts`, `checkpoint_record`, `confirmatory_ok`, `prereg_policy`, `check_prereg_against` |
| `src/_transfer_score_run.py` | policy from `policy_for`, `--checkpoint-record`, numeric flag compare, prereg check |
| `src/_transfer_decision_report.py` | compatibility gate, tables JSON as reference, descriptive verdict |
| `src/_transfer_prereg_fill.py` | declares cutoff 0.35, IoU, dedupe, checkpoint. Refuses a non-primary policy without a reason |
| `src/_transfer_ref_tables_9t.py` | fills feature-free blocks, writes `policy` and `meta`, per-block `fold` |
| `src/config_3_0.json` | `sensitivity_cutoff`, `void_cap_default`, `zero_feature_fill`, model dirs, new prereg fields |

New outputs.
- `expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json` (rebuilt, 144 blocks)
- `expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_pad_9t.json` (rebuilt, 144 blocks)
- `expansions/3_geography/3_0_transfer_protocol/data/interim/pit_prob_oof_filled_9t.tif` and `pad_prob_oof_filled_9t.tif` (gitignored)
- Run records `expansions/3_geography/3_0_transfer_protocol/results/20261106_ref_tables_pit_4d0c29a/` and `20261106_ref_tables_pad_7e33a66/`

## Build status (2026-11-05)

Built by the build agent. Tests. `python -m pytest -q expansions/3_geography/3_0_transfer_protocol/src/test_3_0.py -p no:cacheprovider` (9 passed).
The synthetic test covers the framework QC case. Recall is 1.0 with all three features inside K and 0.667 with one outside.

| Script | Stage | Runnable now with held data | Missing or pending |
|---|---|---|---|
| `src/_transfer_score_lib.py` | S1 scoring core | yes | none |
| `src/_transfer_score_run.py` | S1 and S6 frozen harness (pit and pad) | yes, ran on the 9t pit mosaic and the pad isolated mosaic | target probability rasters and truth |
| `src/_transfer_archival_check_9t.py` | S2 archival check | yes, ran. Pit 0.781 at 30 and 0.909 at 40 rebuilt exactly. Pad also matches | none |
| `src/_transfer_baseline_repeat_9t.py` | S2 new baseline repeat and mosaic check | yes, ran. Pad isolated baseline repeats exactly. Pit mosaic gives 0.909 at cutoff 0.35 | isolated pit rasters (P1 S6) for the pit baseline |
| `src/_transfer_infer_area.py` | S3 inference wrapper | dry run only | GPU run after the preregistration. Target tiles and bbox (assumed input) |
| `src/_transfer_ci_width_9t.py` | S4 projected width | yes, ran on the archival pit pool | none |
| `src/_transfer_prereg_fill.py` | S5 preregistration filler | yes | the user's field values (margin, policy, areas) |
| `src/_transfer_decision_report.py` | decision report | no real target yet | a scored target run and a filled preregistration |
| `src/_transfer_ref_tables_9t.py` | reference block tables for 3.4 to 3.8 | yes, ran (pit 115 blocks, pad 129 blocks) | rerun on the isolated pit mosaic after P1 S6 |
| `src/config_3_0.json` | settings and assumed inputs | yes | none |
| `src/test_3_0.py` | tests | yes | none |

Results in `results/tables/`. `transfer_archival_check_9t.json`, `transfer_mosaic_check_pit_9t.json`, `transfer_baseline_repeat_pad_9t.json`, `projected_ci_width_pit_9t.csv`.
Scorer run folders from the build are in `data/interim/runs/` in this folder. The float32 pad mosaic `data/interim/pad_prob_oof_mosaic_9t.tif` is 242 MB and sits in the ignored data folder.
