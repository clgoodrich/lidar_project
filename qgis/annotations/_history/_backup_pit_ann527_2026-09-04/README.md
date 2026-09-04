# Pre-Phase-4 snapshot — the 527-pit era

Taken 2026-09-04, immediately before `_build_pit_dataset_v2.py --force`
reassigned the 9t train/val/test split from 527 annotated pits to 712.

Everything here is what the deployed `pit_unet_cv5` and `pad_unet_cv5`
checkpoints were actually trained and scored against. Once the split is
reassigned those numbers are no longer reproducible from the live tree.

| file | what it is |
|---|---|
| `annotations_proj.gpkg` | the annotation file as of 2026-08-17, before `annotations_proj_v2.gpkg` was promoted |
| `pit_dataset_manifest.csv` | 527 rows, legacy `pit_id` / `plat_id` columns |
| `pit_blocks_9t.gpkg` | 144 blocks carrying the 527-era `split` |
| `labels_pit_9t_05.tif` | uint8 {0,1,2}, nodata=255, rasterized from the 527-pit annotation |
| `pad_dataset_manifest.csv`, `road_dataset_manifest.csv` | downstream of the pit split via `_build_pad_road_dataset.py` |
| `pit_cv5_fold_assignment_9t.csv`, `pad_cv5_fold_assignment_9t.csv` | which block landed in which fold |
| `pit_cv5_per_fold_9t.csv`, `pad_cv5_per_fold_9t.csv` | the per-fold scores those folds produced |

Why this exists: `docs/golden/NON_DETERMINISTIC.md:28-62` records a 2026-08-12
run that silently reassigned the split and cost the `pit_unet_cv5` fold
assignment. It was recovered from the E: mirror. The external backup is not
currently reliable, so this snapshot lives in the repo instead.

Reproduce nothing from here — it is a record, not an input.
