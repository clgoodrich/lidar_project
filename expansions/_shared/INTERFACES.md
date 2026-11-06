# Shared interfaces between expansions

Written 2026-11-05 after the parallel build. One row per file that one expansion writes and another reads. Configs point at these paths. Change a path here and in every listed config together.

| Artifact | Canonical path | Written by | Read by | Status |
|---|---|---|---|---|
| Frozen split JSON | `data/9t/results/splits/cv_splits_future_9t_v1.json` | P1 `_split_future_write_9t.py` | 7.1 | dry run only, in `p1/data/interim/dryrun/` |
| Frozen split CSV (block_id, fold, role) | `data/9t/results/splits/cv_splits_future_<task>_9t_v1.csv` | P1 `_split_future_csv_9t.py` | 3.3, 5.2, 6.3 | after the JSON is written |
| Derived buffer | `data/9t/results/splits/buffer_derivation_9t.json` | P1 `_split_buffer_derive_9t.py` | 3.1, 3.2, 3.3 | dry run only. 100 m |
| Audit set | `data/9t/results/splits/audit_blocks_9t_v1.csv` (+ `.sha256`) | P2 `_audit_draw_blocks_9t.py --freeze` | 3.3, 4.2, 4.3, 5.1, 5.2, 6.3, 7.1, 7.2, 7.3, 7.5 | **user decision**. Dry-run draw of 17 blocks exists |
| Isolated checkpoints | `data/9t/models/<task>/unet_iso_cv5/fold{k}/best.pt` and `norm_stats_fold{k}.npz` | P1 `_pit_unet_iso_train_9t.py`, existing `_pad_unet_iso_cv5.py` | 3.1, 3.2, 3.3, 7.3 | pad exists at `pad/unet_cv5_iso/`. Pit needs GPU training (**user decision**) |
| Transfer policy checkpoint | `data/9t/models/pit/unet_iso_cv5/policy/best.pt` | not defined | 3.4, 3.5, 3.7 | **open**. P1 writes per-fold models. Name one in the preregistration or switch these configs to `fold{k}` |
| Reference block tables | `expansions/3_geography/3_0_transfer_protocol/results/tables/xfer_ref_block_tables_9t.json`, `xfer_ref_block_tables_pad_9t.json` | 3.0 `_transfer_ref_tables_9t.py` | 3.4 to 3.8 | written. Rerun pit after the isolated pit model |
| Full detector output | `expansions/5_tasks/5_6_record_association/data/processed/detector_output_{pit,pad}_full_9t.gpkg`. Key `det_id` | 5.6 `_records_full_detector_output_9t.py` | 5.4, 6.1, 6.4 | written (685 pit rows, 1005 pad rows) |
| Historic well marks | `expansions/4_modalities/4_6_historic_maps_aerials/.../historic_well_marks_9t.gpkg` | 4.6 S4 | 5.2 | needs digitiser sheets |
| Field arms | `expansions/7_scale/7_5_field_campaign/data/processed/arm_{b,c}*.csv` | 7.5 ingest | 5.4 S3 | needs field work |

Proposal cutoffs (fw_00 section 4, corrected 2026-11-05). Pit 0.35, pad 0.525. 0.10 is a sensitivity only.
CRS check. `expkit.assert_crs` accepts a compound CRS whose horizontal part is EPSG:6346.
