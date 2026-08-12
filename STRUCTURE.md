# Project structure

Reorganized **2026-06-09** (full data-tree restructure + root cleanup), then
**2026-08-12** (Phases 0–3, then Phase 4A/4B). The previous 2026-05-15 reorg is
superseded by this document. See `CLAUDE.md` for the agent operating
instructions (unchanged location at repo root).

## Where paths come from — read this before adding a file

`config/paths.toml` is the single source of truth. It carries the **full
role-based vocabulary** (`source`, `truth`, `derived`, `models`, `results`,
`experiments`, `archive`, …) as of Phase 4A. The names are final; the values
still point at the current tree because Phase 4D has not run.

```python
from _common import path_for
path_for("truth") / "roads.shp"        # correct
ROOT / "data" / "derivatives" / "annotations" / "roads.shp"   # Gate E failure
```

Adding a directory means adding a key here, not spelling it in a script.
`tools/verify_no_path_literals.py` enforces it against a 226-site baseline in
`docs/_ledgers/path_literals_baseline.json`. Those 226 are the pre-existing
sites, frozen; new ones fail the gate.

The eventual Phase 4D values are recorded as comments at the bottom of
`paths.toml`, so the move is a value change rather than an archaeology exercise.
Full plan: `docs/REORGANIZATION_PLAN_phase4_role_based.md`.

```
lidar_project/
├── CLAUDE.md                   Agent operating instructions
├── STRUCTURE.md                This file
├── .gitignore                  Policy: every >=100 MB output has a rule
├── .gitattributes
├── tools/backup_to_E.bat       Incremental robocopy mirror to
│                               E:\Colton\_BACKUPS\lidar_project_MIRROR.
│                               The old root-level backup_to_E.bat targeted
│                               E:\lidar_project, which never existed; it is
│                               retired to archive/retired_tools/. F: is gone
│                               as of 2026-08-12 and E: is the only backup.
├── pytest.ini
│
├── data/
│   ├── source_laz/             RAW input point clouds (LAZ, gitignored)
│   │   ├── westernpa/          USGS WesternPA 2019 D20 tiles (+ older_files, merge scratch)
│   │   └── mckean/             PA Northcentral B19 + NY SouthwestNY A17 tiles
│   ├── derivatives/            Built rasters/vectors. Loose top-level files are
│   │   │                       per-tile *.tif/*.png/*.gpkg (kept flat; referenced
│   │   │                       by exact filename across scripts).
│   │   ├── annotations/        Hand-curated ground truth (small, TRACKED)
│   │   ├── tiles/              Per-area raster derivative stacks
│   │   │   ├── 9t/             Venango Co. 0.5 m stack (DEM/slope/hillshade/LRM/...)
│   │   │   ├── 9t_1m/          9t at 1 m
│   │   │   ├── data_3x3/       Per-block 3x3 mosaics (westernpa_d20, northcentral_b19)
│   │   │   ├── oilcreek_22tile_05/   Oil Creek 22-tile 0.5 m stack (~10 GB)
│   │   │   ├── nec/sw_marcellus_1m, wc_coaloil_1m   1 m regional stacks
│   │   │   ├── extras/         Oil Creek water/2006 per-key outputs
│   │   │   └── mosaic_3x3[_mckean]/  3x3 hillshade discovery outputs
│   │   ├── inference/          Model prediction outputs
│   │   │   ├── mck/            (was mck_inference)
│   │   │   └── oilcreek/       (was oilcreek_inference)
│   │   ├── experiments/        Exploratory / one-off analysis stacks
│   │   │   ├── chm_age_proxy, icp, pilot_A, ramachandran_verifier,
│   │   │   ├── roads, candidates, notebook_demo, permian_sample
│   │   └── validation/         Accuracy assessment outputs
│   └── external/               Third-party downloads (mostly gitignored)
│       ├── usgs_3dep_pa_lidar/        PA LAZ tiles (+ downloadlist_7.txt)
│       ├── usgs_3dep_permian_tx/      TX/Permian Pilot A LAZ
│       ├── ramachandran_2024/         Zenodo bundle + NAIP chips
│       ├── well-pad-denver-permian/   Stanford ML Group eval repo
│       ├── OilGasLocations_*/, PA_LandCover/, tiger_roads/, oil_creek/,
│       ├── literature/, lidar/, legacy_data/
│
├── docs/
│   ├── _ledgers/               Move ledgers + tool-run records (17 CSV/JSON,
│   │                           moved out of docs/ 2026-08-12). MOVES.csv is the
│   │                           master; tools/apply_moves.py --undo reverses it.
│   ├── 01_project_scope.md .. 05_processing_pipeline.md   Documentation-first deliverables
│   ├── HOW_IT_WORKS.md, methodology.md, development_history.md
│   ├── analysis_log.md         Append-only running log (newest at top)
│   ├── _build_methodology_docx.py   -> docs/publication/WellSight_Methodology.docx
│   ├── articles/               Long-form research notes / pipeline guides
│   ├── iterations/             Per-iteration write-ups + LEADERBOARD.md + BACKLOG.md
│   ├── publication/            Paper drafts (md/docx), presentation, methodology docx
│   ├── papers/                 Reference PDFs (small; large books gitignored)
│   ├── figures/                Static figures (+ figures/debug/, figures/extracted/)
│   ├── handoff/                Cross-machine session-resume notes
│   └── related/                Adjacent work docs (SAOCOM InSAR, Urban LiDAR)
│
├── notebooks/
│   ├── 01..05_*.ipynb          Curated end-to-end pipeline notebooks
│   └── wellsight/              ACTIVE scripts only (import _common / _dl)
│       ├── _common.py          ROOT/DERIV/DERIV_9T/DST_CRS, run_pdal, raster I/O
│       ├── _dl.py              Shared DL building blocks
│       ├── annotations/ build/ fetch/ pits/ plats/ roads/ multitask/
│       │   analysis/ preprocessing/
│
├── models/
│   └── pretrained/             YOLO seed weights (yolov8s-seg.pt, yolo26n.pt)
│
├── qgis/
│   └── wellsight.qgz           QGIS project (was "qgis_lidar class.qgz")
│
├── personal/                   Non-project files (resume) — kept out of the tree
│
├── archive/                    Inactive/superseded material
│   ├── wellsight/              Pre-reorg scripts (dead refactors, baselines, runs)
│   └── derivatives/            2026-06-09: beck_9t, beck_mkf,
│                               inference_mck_e1423n2238_05, model_archive
│                               (heavy rasters gitignored; small records kept)
│
├── tests/                      pytest suite + fixtures
├── .claude/  .venv/  .idea/
```

## Path conventions (IMPORTANT — keep code paths anchored)

All active scripts anchor to absolute constants in `notebooks/wellsight/_common.py`:

| Constant   | Value                                            |
|------------|--------------------------------------------------|
| `ROOT`     | repo root                                         |
| `DERIV`    | `ROOT/data/derivatives`                           |
| `DERIV_9T` | `ROOT/data/derivatives/tiles/9t`                  |
| `DST_CRS`  | `EPSG:6346` (NAD83(2011) / UTM 17N, canonical)    |

Per-area stacks are built under `DERIV/"tiles"/<key>` (the `--suffix` / region
key becomes the leaf). Source LAZ lives in `ROOT/data/source_laz/{westernpa,mckean}`.

```bash
cd C:/Users/colto/Documents/GitHub/lidar_project
python notebooks/wellsight/build/_build_derivatives.py --suffix 9t ...   # -> tiles/9t/
python notebooks/wellsight/build/_build_data_3x3_derivatives.py          # -> tiles/data_3x3/
```

## Tile / region keys

| Key  | Description                          | EPSG (raster) | Source LAZ project              |
|------|--------------------------------------|---------------|---------------------------------|
| 9t   | 4.5×4.5 km, Venango County PA        | 6346          | PA_WesternPA_2019_D20 (UTM 17N) |
| mk5  | 5×5 km subset of mkf                 | 6346          | PA_Northcentral_2019_B19 (Albers)|
| mkf  | 10×10 km, McKean County PA           | 6346          | PA_Northcentral_2019_B19 (Albers)|
| pilot_A | TX/NM/Permian LAZ bridge           | 26913/14      | USGS Permian subsets            |

## File size / `.gitignore` policy

Any output that may exceed **100 MB** must be covered by a `.gitignore` rule in
the same change. A blanket `data/derivatives/**/*.tif(.aux.xml)` covers all
derivative rasters at any depth; `archive/derivatives/**/*.{tif,gpkg,las,...}`
covers archived heavy data. Audit (output must be empty):

```bash
find . -type f -size +100M -not -path "./.git/*" -not -path "./.venv/*" | \
  while read f; do git check-ignore -q "$f" || echo "NOT IGNORED: $f"; done
```
