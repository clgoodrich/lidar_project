# wellsight_v2 — organised by pipeline stage

Reorganised 2026-08-12. Previously grouped by target (`pits/`, `plats/`,
`roads/`, `drainage/`), which meant every one of those folders held label-prep
AND training AND inference scripts. Now the folders follow the flow of work.

| Stage | Scripts | In → Out |
|---|---:|---|
| `s1_build/` | 10 | LAZ → DEM → terrain channels → feature stack |
| `s2_labels/` | 11 | hand annotations → label rasters + train/val/test splits |
| `s3_train/` | 13 | labels + features → `best.pt` |
| `s4_infer/` | 12 | `best.pt` + a new area → probability rasters → candidates |
| `s5_eval/` | 23 | predictions vs held-out truth → scores |
| `s6_review/` | 8 | review packages → human corrections → **back into s2** |
| `s7_analysis/` | 12 | morphology, change detection, science outputs |
| *(root)* | 3 | `_common.py`, `_dl.py`, `_instance_common.py` |

It is not a straight line: **s6 feeds back into s2**. That loop is the
active-learning cycle, and it is why `roads.shp` keeps growing.

## Two places the stages blur

**`s1_build/_build_derivatives.py` does LAZ→DEM *and* DEM→channels in one pass.**
PDAL merges the tiles, `writers.gdal` IDW makes the DEM, and openness / LRM / TPI
/ slope come off that DEM before it exits. Splitting it is a code change, not a
move.

**Several `s3_train/` scripts also run inference at the end.** `_pit_unet_cv5.py`,
`_pad_unet_cv5.py` and `_road_unet_1m_recall.py` train, then predict on a tile.
They live in `s3_train/` because training is their purpose; the inference tail is
a convenience, not a second entry point.

## Why the move was safe

Every script stayed at the same depth — `wellsight_v2/<stage>/<file>.py` — so all
167 `sys.path.insert(0, Path(__file__).resolve().parents[N])` calls resolve
exactly as before. Only 17 places named a directory literally, and each was
repointed by resolving *what it imports*, not by string substitution. Verified
after: 122 scripts compile, 117 intra-project imports resolve, 0 of 61 QGIS
layers broken.

Paths come from `config/paths.toml` via `_common.py`. Prefer
`path_for("annotations")` over hand-assembling `ROOT / "data" / ...`.
