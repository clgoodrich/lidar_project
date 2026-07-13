# lidar_project

Terrain-only feature detection from airborne LiDAR — two research efforts sharing one
toolchain (Python + PDAL + GDAL/WhiteboxTools + PyTorch):

1. **WellSight** — finding orphaned/abandoned oil & gas wells in western Pennsylvania
   (and testing transfer to the Permian Basin, TX) from bare-earth LiDAR derivatives.
2. **Barlow / FINESST** (`barlow/`) — reproducing and extending Mary C. Barlow's 2026
   dissertation on Antarctic Dry Valley stream-channel change, toward a NASA FINESST
   proposal (attribution of geomorphic change to climate drivers).

Both projects share the same core idea: **surface features leave signatures in ground
shape alone** — no imagery, no color, no vegetation signal needed.

---

## 1. WellSight — PA orphaned wells

Pennsylvania has hundreds of thousands of undocumented orphaned wells from 150+ years
of extraction. WellSight detects their surface evidence — **pits (dug wells), pads/plats
(drilling platforms), access roads** — in USGS 3DEP LiDAR, validated against PA DEP
known-well records.

**Pipeline:** LAZ tiles → PDAL ground filtering → 0.5 m / 1 m derivative stacks
(DEM, slope, hillshade, local relief, roughness, flow accumulation …) → hand-annotated
ground truth (QGIS) → semantic U-Nets + instance models (Mask R-CNN, YOLOv8-seg) →
per-instance evaluation → active-learning correction loop.

**State of play** (honest 1:1 protocol, 2026-07-02 — see
[`docs/iterations/LEADERBOARD.md`](docs/iterations/LEADERBOARD.md)):

| Task | Best recall | Best F1 | The story |
|---|---|---|---|
| Pits (65 test) | 0.97 @IoU.3 (Mask R-CNN) | 0.102 (YOLO) | Recall is solved; precision (3–6%) is the frontier — models over-detect 12–47× |
| Pads (93 test) | 0.98 @IoU.3 (Mask R-CNN) | 0.118 (YOLO) | Same shape: find everything, cry wolf often |
| Roads | — | 0.754 (extraction F1) | 3-class U-Net (bg/road/drainage) + graph-based cleaning arsenal |

Known-well cross-reference: up to **521 detections matched to 1,069 PA DEP wells**
within 25 m (pad Mask R-CNN). Next levers: val-selected score thresholds and the
reject-as-hard-negative retraining loop.

**Study areas:** `9t` (Venango Co., 4.5×4.5 km, the training/eval core), `613590` and
neighbors (deployment blocks), McKean Co., Oil Creek — plus four `permian_*` grids
(TX) for cross-domain transfer against Stanford/Ramachandran pad datasets and TX RRC
orphan-well ground truth.

## 2. Barlow / FINESST — Antarctic stream change

Self-contained under [`barlow/`](barlow/README.md). Independently reproduces the
dissertation's measurement engine from public data (2001 ATM lidar → 2014/15 NCALM
lidar → REMA satellite DEMs: co-registration, DEM-of-Difference, NMAD/LOD95
thresholding, per-stream sediment rates) and adds the FINESST science: **attribution
of channel change to melt drivers**.

Headline preliminary result: per-stream specific sediment rate vs mean gauged
discharge, **r = +0.95 (p = 0.003), ρ = +0.94** (n = 6, lidar epoch) — leave-one-out
stable and invariant to channel-mask choice (verified inside the author's own detected
channel outlines). Proposal drafts, figures, and the full data manifest live in
`barlow/docs/`.

---

## Repository layout

```
CLAUDE.md            Agent operating instructions (documentation + data rules)
STRUCTURE.md         Full directory map + path conventions (tile keys, CRS)
data/
  source_laz/        Raw LAZ point clouds (gitignored)
  derivatives/       Built raster/vector stacks; annotations/ is tracked ground truth
  external/          Third-party downloads (DEP/RRC wells, Ramachandran, land cover…)
notebooks/
  wellsight_v2/      ACTIVE WellSight code (_common.py: ROOT/DERIV/CRS + run_pdal)
    build/ pits/ plats/ roads/ drainage/ multitask/ annotations/
label_grids/         Per-grid annotation workspaces (WPA + Permian)
barlow/              FINESST subproject (build/ scripts + docs/, own README)
docs/
  analysis_log.md    Append-only run log, newest at top — the project's memory
  iterations/        Per-experiment write-ups + LEADERBOARD.md + BACKLOG.md
  01..05_*.md        Scope, data dictionary, LAS inspection, design spec, pipeline
  publication/       Paper/methodology drafts
models/, qgis/, tests/, archive/
```

`STRUCTURE.md` has the full tree, tile/region keys, and path conventions.

## Documentation system (enforced)

- Every experiment gets a write-up in `docs/iterations/<name>.md` (goal, params,
  results, interpretation, reproduce command).
- `docs/iterations/LEADERBOARD.md` — all model results, apples-to-apples.
- `docs/iterations/BACKLOG.md` — the live "revisit later" list.
- `docs/analysis_log.md` — every processing decision and run result, append-only.

## Environment

Windows 11 + Python 3.13 (repo `.venv`), miniconda GDAL/OGR on PATH. Key libraries:
rasterio, geopandas/pyogrio, numpy/scipy, laspy, PyTorch + torchvision, ultralytics,
whitebox. **PDAL is CLI-only** — pipelines are written as JSON and executed via
`subprocess` (`run_pdal` in `notebooks/wellsight_v2/_common.py`); the Python bindings
are not used. QGIS for annotation and review.

Canonical CRS: **EPSG:6346** (NAD83(2011) / UTM 17N) for PA rasters; **EPSG:3294**
for the Antarctic work. Always verify CRS from source headers before spatial ops.

## Data policy

- **No file ≥ 100 MB enters git history.** Every heavy output gets a `.gitignore`
  rule in the same change that creates it (audit script in `STRUCTURE.md`).
- Heavy regenerable data lives **in-repo but gitignored** (moved back from the
  external drive 2026-07-13 so the project is self-contained on `C:`): Barlow
  data in `barlow_data/`, LiDAR tiles/derivatives under `data/`.
- `output_wells.csv` (DEP ground truth) is **read-only** — work from copies.
- Author-private data (e.g. `barlow/Shapefiles/`, shared by the dissertation author)
  is gitignored and must never be pushed.
- All remote-sensing inputs are public (USGS 3DEP, OpenTopography, PGC REMA, EDI/LTER,
  Copernicus ERA5); candidate wells are always labeled *candidate*, never confirmed.

## Reproducing

Each subsystem documents its own reproduce commands:

- WellSight derivative stacks: `notebooks/wellsight_v2/build/` (see `STRUCTURE.md`
  path conventions and `docs/05_processing_pipeline.md`).
- Model training/eval: the relevant `docs/iterations/<name>.md` carries the exact
  command for every number on the leaderboard.
- Barlow: `barlow/docs/barlow_data_manifest.md` is a complete fetch-everything recipe
  (two scripts, all public sources).

Tests: `pytest` from the repo root (`pytest.ini`).
