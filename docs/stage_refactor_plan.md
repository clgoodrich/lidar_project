# Stage refactor plan

Reorganizes `notebooks/wellsight_v2/` by pipeline stage. Depth is unchanged, so all 167 `parents[N]` sys.path calls keep working. Only literal directory names need repointing.

| Stage | Scripts | What it does |
|---|---:|---|
| `s1_build` | 10 | LAZ to DEM to channels to feature stack |
| `s2_labels` | 11 | annotations to label rasters and splits |
| `s3_train` | 13 | labels + features to best.pt |
| `s4_infer` | 12 | best.pt + new area to candidates |
| `s5_eval` | 23 | score against held-out truth |
| `s6_review` | 8 | review packages; corrections back to s2 |
| `s7_analysis` | 12 | morphology, change detection |
| _(root)_ | 3 | `_common.py`, `_dl.py`, `_instance_common.py` |

89 files move. 14 source rewrites.

## Needs a human look

One old directory fans out to several stages, so a single sys.path insert may need to become two:

- `notebooks/wellsight_v2/s4_infer/_pad_maskrcnn_infer.py` — MANUAL: fans out to s3_train,s4_infer

