# Shared interfaces between expansions

Written 2026-11-05 after the parallel build. Revised 2026-11-06 after the two code reviews (`docs/plans/expansion_adversarial_review_20261106.md`, `docs/plans/expansion_consolidated_review_20261106.md`). One row per file that one expansion writes and another reads. Configs point at these paths. Change a path here and in every listed config together.

## Read these files only through the shared readers

Every consumer reads a handoff through `expansions/_shared/src/expkit.py`. A plain `pd.read_csv` or `json.load` on these files was the cause of most review blockers.

| File | Reader | What it guarantees |
|---|---|---|
| Split JSON | `ek.read_split(task, path)` | hash check, roles `train`, `inner_val`, `held_out` |
| Split CSV | `ek.read_split_csv(path)` | roles canonicalised to the JSON names |
| Buffer JSON | `ek.read_buffer(task, path)` | metres per task, raises if absent, never 0 by default |
| Audit CSV | `ek.require_audit(path)`, `ek.audit_ids(df, roles)` | `#` header, sha256 sidecar, refuses if missing unless the caller labels its output exploratory |

## Handoffs

| Artifact | Canonical path | Written by | Read by | Status |
|---|---|---|---|---|
| Frozen split JSON | `data/9t/results/splits/cv_splits_future_9t_v1.json` | P1 `_split_future_write_9t.py` | 3.3, 5.2, 6.3, 7.1, 7.3 | dry run only, in `p1/data/interim/dryrun/`. Mode `window` (user default 2026-11-06). Train blocks keep their role and the sampler rejects windows within the buffer of held-out ground. 71 to 76 pit train blocks per fold |
| Frozen split CSV (block_id, fold, role) | `data/9t/results/splits/cv_splits_future_<task>_9t_v1.csv` | P1 `_split_future_csv_9t.py` | 3.3, 5.2, 6.3 | roles `train`, `inner_val`, `held_out`. `buffer` blocks get no row |
| Derived buffer | `data/9t/results/splits/buffer_derivation_9t.json` | P1 `_split_buffer_derive_9t.py` | P1 trainer, 3.1, 3.2, 3.3 | dry run only. `buffer_m_by_task` pit 100 m, pad 150 m |
| Audit set | `data/9t/results/splits/audit_blocks_9t_v1.csv` (+ `.sha256`) | P2 `_audit_draw_blocks_9t.py --freeze` | 3.3, 4.2, 4.3, 5.1, 5.2, 6.3, 7.1, 7.2, 7.3, 7.5 | **user decision** to freeze. Dry-run pit draw of 17 blocks (`tasks=pit`). Separate dry-run pad draw of 19 of 129 pad blocks in `p2/data/interim/audit_blocks_pad_9t_dryrun.csv` (`tasks=pad`) |
| Isolated checkpoints | `data/9t/models/<task>/unet_iso_cv5/fold{k}/best.pt` and `norm_stats_fold{k}.npz` | P1 `_pit_unet_iso_train_9t.py`, existing `_pad_unet_iso_cv5.py` | 3.1, 3.2, 3.3, 7.3 | pad exists at `pad/unet_cv5_iso/`. Pit needs GPU training (**user decision**) |
| Transfer checkpoint | config key `transfer_checkpoint` in 3.4, 3.5, 3.6, 3.7 | 3.x configs `model.<task>` | 3.4 to 3.7 | provisional (user default 2026-11-06). Five-fold ensembles `pit/unet_cv5` and `pad/unet_cv5_iso`, fold mean, sha256 per fold. Fine-tuning needs `init_checkpoint` (**user decision**) |
| Reference block tables | `expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json`, `xfer_ref_block_tables_pad_9t.json` | 3.0 `_transfer_ref_tables_9t.py` | 3.4 to 3.8 | rewritten 2026-11-06 on all 144 pit and pad blocks. Carries `policy`, `meta` and per-block `fold`. Provisional (historical models) |
| Full detector output | `expansions/5_tasks/5_6_record_association/data/processed/detector_output_{pit,pad}_full_9t.gpkg` | 5.6 `_records_full_detector_output_9t.py` | 5.4, 6.1, 6.4 | rewritten 2026-11-06 from the policy re-cut (pit 0.35, pad 0.525, `5.6/src/_records_policy_recut_9t.py`). 768 pit, 996 pad. `det_id` unique across both files (pit 1 to 768, pad 1000001 to 1000996), a seeded permutation that encodes neither score nor match. Key sites as `kind:det_id`. Deduplication uses predictions only |
| Historic well marks | `expansions/4_modalities/4_6_historic_maps_aerials/.../historic_well_marks_9t.gpkg` | 4.6 S4 | 5.2 | needs digitiser sheets |
| Field arms | `expansions/7_scale/7_5_field_campaign/data/processed/arm_b_candidate_outcomes.csv`, `arm_c_search_outcomes.csv`, `arm_c_search_areas.csv`, `arm_c_well_links.csv` | 7.5 `_field_density_export.py` | 5.4 S3 | writer and schema built and tested end to end. Needs field work |

## Scoring policy

`ek.policy_for(task, mode)` is the one policy for every scorer (3.0, the regional core in 3.4, 3.1, 3.2, 7.3). Primary cutoffs are pit 0.35 and pad 0.525, minimum area 4 m², IoU 0.3, greedy matching in score order, blob score the mean probability, K 40 per km². Mode `sensitivity` gives cutoff 0.10 and IoU-order matching. Every output stamps the policy and its hash. `ek.assert_same_policy` stops a comparison between a reference and a target scored differently. A parity test in 3.4 runs one fixture through the 3.0 scorer and the regional core and requires identical candidates, matches and recall. On the 9t pit mosaic both give 0.9165 on the old 115-block footprint.

## Bootstrap

`ek.block_bootstrap` and `ek.bootstrap_diff` keep undefined draws. By default any undefined draw makes the interval undefined, and `ek.decide` returns inconclusive. A caller may tolerate a declared share with `max_undefined` and must report `ek.undefined_share(draws)`.

CRS check. `expkit.assert_crs` accepts a compound CRS whose horizontal part is EPSG:6346. Scorers also require metre units and an identical affine transform.
