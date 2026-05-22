# Project structure

Reorganized 2026-05-15. See `Claude.md` for the agent operating instructions
(unchanged location at repo root).

```
lidar_project/
├── Claude.md                    Agent operating instructions
├── STRUCTURE.md                 This file
├── .gitignore                   See policy: all >=100 MB outputs covered
│
├── archive/                     Inactive/superseded files (see archive/README.md)
│   ├── notebooks_legacy/        Pre-reorg wellsight scripts (was notebooks/archive/)
│   ├── notebooks_root/          Early exploratory notebooks from notebooks/
│   ├── wellsight/pits/          _pit_unet.py v1, _pit_rim_polygons_spoke_v1.py
│   ├── docs/                    Old paper_versions/ and presentations/ archives
│   └── derivatives/             legacy_tiles, res_05, mk_legacy, old_experiments,
│                                old_pit_models, temp_pipeline, unscoped_rasters
│
├── data/
│   ├── derivatives/             Built rasters/vectors (DEMs, LRM, road/Beck outputs, etc.)
│   │   ├── beck_<tile>/         Beck 2015 replication outputs (rl, canopy, centerlines)
│   │   ├── roads/               Multi-channel road-extraction outputs
│   │   ├── pilot_A/             TX/Permian LiDAR bridge derivatives
│   │   ├── ramachandran_verifier/   EfficientNet-B3 verifier outputs
│   │   ├── annotations/         Hand-curated ground truth (small, tracked)
│   │   └── *.tif                Per-tile DEM/slope/CHM/LRM/intensity/density rasters
│   ├── external/                Third-party downloads (mostly gitignored)
│   │   ├── usgs_3dep_pa_lidar/  PA LAZ tiles for mkf/9t areas
│   │   ├── usgs_3dep_permian_tx/    TX/Permian Pilot A LAZ
│   │   ├── ramachandran_2024/   Zenodo bundle + NAIP chips
│   │   ├── well-pad-denver-permian/ Stanford ML Group eval repo
│   │   ├── OilGasLocations_*/   PA DEP statewide shapefile
│   │   ├── PA_LandCover/        Per-county NLCD 2022 GeoTIFFs
│   │   └── legacy_data/         Older root-level data dumps
│   └── files/                   (currently empty; original LAS workspace)
│
├── docs/
│   ├── 01_project_scope.md      Documentation-first deliverables (per Claude.md)
│   ├── 02_data_dictionary_wells.md
│   ├── 03_las_inspection_report.md
│   ├── 04_feature_detection_design_spec.md
│   ├── 05_processing_pipeline.md
│   ├── methodology.md
│   ├── development_history.md
│   ├── analysis_log.md
│   ├── abandoned_well_pit_research.md
│   ├── articles/                Long-form research notes / pipeline guides
│   ├── handoff/                 Session-resume MDs for cross-machine work
│   ├── papers/                  Reference PDFs (3DEP params, Beck 2015, etc.)
│   ├── paper_versions/          WellSight paper drafts (latest + archive/)
│   ├── presentations/           WellSight slide decks (latest + archive/)
│   ├── figures/                 Static figures used in paper/presentation
│   │   └── extracted/           Auto-extracted figure dumps
│   └── related/                 Adjacent work docs (SAOCOM InSAR, Urban LiDAR)
│
├── notebooks/
│   ├── *.ipynb                  Curated Jupyter notebooks
│   ├── wellsight/               Active scripts (organized by workflow stage)
│   │   ├── fetch/               Data acquisition (USGS 3DEP API, PA LAZ download)
│   │   ├── build/               Raster derivative builds from LAZ
│   │   ├── pits/                Pit-detection pipeline (template+XGB, U-Net, rim polygons)
│   │   ├── roads/               Road extraction (v3 multi-channel + Beck 2015 replication)
│   │   ├── pilotA/              TX/Permian LiDAR bridge experiment
│   │   ├── ramachandran/        Ramachandran 2024 verifier replication
│   │   ├── paper/               Paper/presentation generators
│   │   ├── runs/                Orchestration scripts (hotspots, retrain, etc.)
│   │   └── archive/             Superseded earlier versions
│   └── archive/                 Earlier root-level wellsight scripts (kept for reference)
│
├── .claude/                     Claude Code config / scheduled tasks / memory
├── .venv/                       Python virtual environment
└── .idea/                       JetBrains IDE settings
```

## Script-execution conventions

All Python scripts in `notebooks/wellsight/<subdir>/` are designed to be
invoked from the repo root with paths anchored to an absolute `ROOT` constant.
Either of these works:

```bash
cd C:/Users/colto/Documents/GitHub/lidar_project
python notebooks/wellsight/roads/_beck_road_replication.py --tile 9t
python notebooks/wellsight/build/_build_intensity_zscore.py --tile mkf
```

The active builds/road scripts are parameterized by `--tile {9t,mkf}`. The
older `_build_<region>_*.py` scripts hardcode a single area; check the file
header before running.

## Tile / region keys

| Key  | Description                                  | EPSG (raster) | LAZ project (source)            |
|------|----------------------------------------------|---------------|---------------------------------|
| 9t   | 4.5x4.5 km, Venango County PA                | 6346 (UTM 17N)| PA_WesternPA_2019_D20 (UTM 17N) |
| mk5  | 5x5 km subset of mkf                         | 6346          | PA_Northcentral_2019_B19 (Albers)|
| mkf  | 10x10 km, McKean County PA                   | 6346          | PA_Northcentral_2019_B19 (Albers)|
| mk   | Original McKean tile (earlier work)          | 6346          | (legacy)                        |
| pilot_A | TX/NM/Permian LAZ bridge experiment       | 26913/14 (UTM)| USGS PA pilot subsets           |

Source LAZ for `mkf/mk5` is **NAD83(2011) Conus Albers (EPSG:6350)** — build
scripts reproject to UTM 17N on the fly via PDAL `filters.reprojection`.

## File size / `.gitignore` policy

Per saved feedback (see `.claude/projects/.../memory/`): any output file
generated by a script that may exceed **100 MB** must be covered by a
`.gitignore` rule in the same change. Audit with:

```bash
find . -type f -size +100M -not -path "./.git/*" -not -path "./.venv/*" | \
  while read f; do
    git check-ignore -q "$f" || echo "NOT IGNORED: $f"
  done
```

Output should be empty.
