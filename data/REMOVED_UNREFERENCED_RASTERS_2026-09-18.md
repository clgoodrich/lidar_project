# Removed unreferenced rasters — 2026-09-18

**If a `.tif` you expected is missing from `data/`, read this before rebuilding
anything.** It is probably not lost and probably not a broken pipeline.

On 2026-09-18, 1,788 derived raster files totalling **83.40 GB** were deleted
from the working tree to reclaim space on C:, which was down to 36.8 GB free
while a 150 GB repository and active model training shared the disk. Free space
afterwards: 118 GB.

Nothing unique was destroyed. Every removed file was verified byte-size-identical
on **both** backup drives before deletion, and all of it is regenerable from the
source LAZ.

## What was removed

Two passes, both limited to `.tif` files with **zero references** in
`docs/reference_index.csv` — meaning no script, notebook or document names the
path.

| pass | scope | rasters | sidecars | size |
|---|---|---|---|---|
| 1 | everything unreferenced except `data/westernpa_d20/` | 829 | 81 | 46.91 GB |
| 2 | `data/westernpa_d20/` | 825 | 53 | 36.49 GB |

By area, roughly: `westernpa_d20` 36.5 GB, `9t` 15.5 GB (8.9 of it under
`models/_retired/`), `613590` 10.4 GB, `mckean` 7.8 GB, `_archive` 2.9 GB,
`northcentral_b19` 2.6 GB, `_source` 2.1 GB, `OTHER_DATA` 1.8 GB.

Mostly feature stacks (`features_*.tif`), probability rasters (`*_prob*.tif`),
hillshades, and per-tile terrain derivatives.

## What was NOT removed

- Anything tracked by git. The delete script skipped tracked paths outright;
  `git status` showed zero deletions afterwards.
- Anything with one or more references in `docs/reference_index.csv`.
- Non-raster products. Each `data/westernpa_d20/<tile>/derived/1m/` still holds
  its `_PROVENANCE.json`, contour and water GeoPackages, and preview PNGs, so
  what was built there is still documented.
- `.tif.aux.xml` sidecars whose raster survived.

## Where to get a file back

Both mirrors hold the complete pre-deletion tree at the same relative path:

```
E:\Colton\_BACKUPS\lidar_project_MIRROR\<relative path>
F:\Colton\_BACKUPS\lidar_project_MIRROR\<relative path>
```

So `data/613590/derived/inference_05/features_613590_05.tif` is at
`E:\Colton\_BACKUPS\lidar_project_MIRROR\data\613590\derived\inference_05\features_613590_05.tif`.

Restoring is a copy, not a hunt. Copy it back rather than working from the
mirror — the mirror is a backup, not a working directory, and the next backup
run will not reconcile edits made inside it.

There is also the frozen `F:\Colton\_BACKUPS\lidar_project_SNAPSHOT_prereorg_2026-08-12`,
but it predates the repository reorganisation, so its paths are the old layout.

## The full list

Every deletion is logged in `docs/MOVES.csv` under phase `delete-regenerable`,
one row per file with its byte size and the reason. To see exactly what went:

```bash
grep ",delete-regenerable," docs/MOVES.csv | cut -d, -f3
```

## Rebuilding instead of restoring

These are derived products. If restoring is inconvenient, regenerate:

- Terrain derivatives and feature stacks:
  `notebooks/wellsight_v2/s1_build/_build_derivatives.py`,
  `_build_extra_channels.py`, `_make_rrim.py`
- Probability rasters: re-run inference from the checkpoint that produced them,
  `notebooks/wellsight_v2/s4_infer/`. Retired model directories keep their
  `best.pt` beside where the raster used to be.

Regenerating is not free — a single 1 m feature stack is ~400 MB and a 0.5 m one
over 1 GB — so check the mirrors first.

## Standing caution

"Unreferenced" means no path literal points at the file. It does **not** prove
nothing used it: a script that globs a directory, or a QGIS project that loads a
layer, leaves no reference the index can see. If something downstream breaks and
the cause is a missing raster, that is a gap in this reasoning, not a
justification after the fact. Restore from a mirror and say so in
`docs/analysis_log.md`.
