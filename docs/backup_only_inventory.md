# Files on the backup but not in the local repo

Generated 2026-11-05 09:17 by `tools/backup_only_inventory.py`.
Mirror `H:/Colton/_BACKUPS/lidar_project_MIRROR` (tag T7). Local `C:\Users\colto\Documents\GitHub\lidar_project`.

Backups never delete (`robocopy /E /XO`). So anything moved, renamed or deleted locally
stays on the mirror. These files exist **only** on the backup. Do not delete the mirror
without reading this list first.

**1,794 files, 86.22 GB** across 64 folders (existence by relative path, not content).

Full list: `docs/_ledgers/backup_only_files_T7.csv` (columns relpath, size_bytes, mtime).

Two causes, not separated here. (1) Data deleted locally to free space on C:. For these the
mirror holds the only copy. (2) Files renamed or moved locally. They show here under the old
path and in the repo under the new one, so a second copy exists. `docs/MOVES.csv` maps old to new.
To tell them apart, check whether the file name appears elsewhere in the repo before deleting
anything from the mirror.

By top-level folder: `data/` 1,767 files (86.18 GB), `docs/` 26 files (0.04 GB), `tools/` 1 file.

## By folder (depth 3), largest first

| folder | files | size | oldest file | newest file |
|---|---|---|---|---|
| `data/9t/models` | 114 | 10.20 GB | 2026-05-05 | 2026-09-18 |
| `data/613590/derived` | 63 | 7.89 GB | 2026-06-12 | 2026-07-23 |
| `data/_source/lidar` | 10 | 7.10 GB | 2026-03-13 | 2026-08-13 |
| `data/9t/derived` | 76 | 3.61 GB | 2026-04-14 | 2026-08-18 |
| `data/_archive/parked` | 45 | 2.86 GB | 2026-06-17 | 2026-07-08 |
| `data/mckean/mkf` | 23 | 2.83 GB | 2026-06-12 | 2026-07-22 |
| `data/mckean/e1423n2238` | 28 | 2.50 GB | 2026-05-22 | 2026-07-09 |
| `data/_source/reference` | 27 | 2.09 GB | 2026-04-18 | 2026-04-18 |
| `data/mckean/mk5` | 29 | 2.08 GB | 2026-04-18 | 2026-07-09 |
| `data/westernpa_d20/613594` | 39 | 1.98 GB | 2026-05-20 | 2026-08-19 |
| `data/westernpa_d20/618599` | 39 | 1.97 GB | 2026-05-20 | 2026-08-19 |
| `data/westernpa_d20/609590` | 42 | 1.97 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/618594` | 40 | 1.97 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/609594` | 40 | 1.97 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/613599` | 40 | 1.96 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/604594` | 38 | 1.96 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/604590` | 41 | 1.96 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/609599` | 42 | 1.96 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/609603` | 40 | 1.96 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/618603` | 40 | 1.95 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/613603` | 42 | 1.95 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/604599` | 40 | 1.95 GB | 2026-05-20 | 2026-07-09 |
| `data/westernpa_d20/604603` | 38 | 1.94 GB | 2026-05-20 | 2026-07-09 |
| `data/9t/experiments` | 28 | 1.74 GB | 2026-05-15 | 2026-06-28 |
| `data/westernpa_d20/613590` | 31 | 1.38 GB | 2026-06-07 | 2026-07-29 |
| `data/westernpa_d20/618591` | 29 | 1.10 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/622594` | 28 | 1.10 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/622603` | 30 | 1.09 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/622599` | 28 | 1.09 GB | 2026-06-07 | 2026-07-09 |
| `data/northcentral_b19/e1423n2235` | 47 | 0.76 GB | 2026-05-22 | 2026-07-09 |
| `data/northcentral_b19/e1423n2238` | 35 | 0.76 GB | 2026-05-21 | 2026-07-09 |
| `data/westernpa_d20/622591` | 27 | 0.72 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/613608` | 28 | 0.55 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/618608` | 29 | 0.55 GB | 2026-06-07 | 2026-07-09 |
| `data/westernpa_d20/609608` | 28 | 0.54 GB | 2026-06-07 | 2026-07-09 |
| `data/northcentral_b19/e1426n2239` | 23 | 0.54 GB | 2026-05-21 | 2026-07-09 |
| `data/westernpa_d20/604608` | 28 | 0.54 GB | 2026-06-07 | 2026-07-09 |
| `data/northcentral_b19/e1426n2236` | 23 | 0.54 GB | 2026-05-21 | 2026-07-09 |
| `data/FOO/derived` | 23 | 0.46 GB | 2026-09-04 | 2026-09-05 |
| `data/FOO` | 22 | 0.46 GB | 2026-08-15 | 2026-08-18 |
| `data/grids/westernpa_03` | 18 | 0.40 GB | 2026-06-17 | 2026-07-08 |
| `data/grids/westernpa_01` | 19 | 0.39 GB | 2026-06-16 | 2026-07-08 |
| `data/grids/westernpa_02` | 19 | 0.39 GB | 2026-06-16 | 2026-07-08 |
| `data/grids/westernpa_04` | 18 | 0.39 GB | 2026-06-17 | 2026-07-08 |
| `data/westernpa_d20/622608` | 31 | 0.36 GB | 2026-06-07 | 2026-07-09 |
| `data/mckean/sw` | 42 | 0.32 GB | 2026-07-22 | 2026-07-22 |
| `data/_experiments/pit_1m_ensemble` | 3 | 0.31 GB | 2026-04-20 | 2026-04-20 |
| `data/_experiments/roads` | 15 | 0.24 GB | 2026-05-14 | 2026-05-14 |
| `data/_experiments/permian_sample` | 5 | 0.15 GB | 2026-06-09 | 2026-08-13 |
| `data/616593/derived` | 18 | 0.10 GB | 2026-04-18 | 2026-07-09 |
| `data/607594/derived` | 19 | 0.09 GB | 2026-04-18 | 2026-07-09 |
| `data/610594/derived` | 18 | 0.09 GB | 2026-04-18 | 2026-07-09 |
| `data/610605/derived` | 19 | 0.09 GB | 2026-04-18 | 2026-07-09 |
| `data/_archive/superseded` | 35 | 0.09 GB | 2026-06-07 | 2026-06-13 |
| `data/_experiments/pilot_A` | 16 | 0.09 GB | 2026-05-11 | 2026-05-11 |
| `data/_experiments/notebook_demo` | 3 | 0.06 GB | 2026-06-05 | 2026-06-05 |
| `data/_experiments/icp` | 6 | 0.06 GB | 2026-05-21 | 2026-05-21 |
| `docs/publication` | 1 | 0.03 GB | 2026-05-04 | 2026-05-04 |
| `docs/presentation_figures_30to45min` | 12 | 0.01 GB | 2026-09-17 | 2026-09-17 |
| `docs/presentation/figures_30to45min` | 8 | 0.00 GB | 2026-09-17 | 2026-09-17 |
| `docs/presentation` | 3 | 0.00 GB | 2026-09-17 | 2026-09-19 |
| `docs/presentation_figures_30to45min/__pycache__` | 1 | 0.00 GB | 2026-09-17 | 2026-09-17 |
| `docs` | 1 | 0.00 GB | 2026-09-17 | 2026-09-17 |
| `tools` | 1 | 0.00 GB | 2026-08-19 | 2026-08-19 |

## Largest 25 files

| file | size |
|---|---|
| `data/_source/lidar/westernpa/_merged_FOO.las` | 6.75 GB |
| `data/9t/models/_retired/03_multiscale_feats/features_pit_v2_9t_05.tif` | 1.82 GB |
| `data/mckean/mkf/derived/road_1m/features_mkf_road_1m.tif` | 0.70 GB |
| `data/613590/derived/05/rgb3_613590_05.tif` | 0.49 GB |
| `data/westernpa_d20/609590/derived/1m/features_609590_1m.tif` | 0.41 GB |
| `data/westernpa_d20/613594/derived/1m/features_613594_1m.tif` | 0.41 GB |
| `data/westernpa_d20/609594/derived/1m/features_609594_1m.tif` | 0.41 GB |
| `data/westernpa_d20/618594/derived/1m/features_618594_1m.tif` | 0.41 GB |
| `data/westernpa_d20/618599/derived/1m/features_618599_1m.tif` | 0.41 GB |
| `data/westernpa_d20/609599/derived/1m/features_609599_1m.tif` | 0.41 GB |
| `data/westernpa_d20/604594/derived/1m/features_604594_1m.tif` | 0.41 GB |
| `data/westernpa_d20/613599/derived/1m/features_613599_1m.tif` | 0.41 GB |
| `data/westernpa_d20/604590/derived/1m/features_604590_1m.tif` | 0.41 GB |
| `data/westernpa_d20/609603/derived/1m/features_609603_1m.tif` | 0.41 GB |
| `data/westernpa_d20/618603/derived/1m/features_618603_1m.tif` | 0.40 GB |
| `data/westernpa_d20/613603/derived/1m/features_613603_1m.tif` | 0.40 GB |
| `data/westernpa_d20/604599/derived/1m/features_604599_1m.tif` | 0.40 GB |
| `data/westernpa_d20/604603/derived/1m/features_604603_1m.tif` | 0.40 GB |
| `data/_archive/parked/permian_ramachandran/label_grids_permian_01/pad_unet_xfer/features_pad_permian_01_1m.tif` | 0.39 GB |
| `data/9t/experiments/exag3x/slope_9t_05_z3.tif` | 0.32 GB |
| `data/613590/derived/05/slope_613590_05.tif` | 0.32 GB |
| `data/613590/derived/05/dsm_613590_05.tif` | 0.32 GB |
| `data/613590/derived/05/profile_curv_613590_05.tif` | 0.28 GB |
| `data/613590/derived/05/slope_residual_12m_613590_05.tif` | 0.28 GB |
| `data/613590/derived/05/slope_residual_24m_613590_05.tif` | 0.28 GB |

## Refresh

```
python tools/backup_only_inventory.py --mirror H:/Colton/_BACKUPS/lidar_project_MIRROR --tag T7
```
Run it after every backup. The CSV is overwritten, so diff it in git to see what changed.
