# SMRF ground reclassification — closing the holes the 18° cut left

**Date:** 2026-09-18
**Status:** done for two tiles; model impact still untested
**Follows:** [`nonground_classification_and_scan_angle_cut.md`](nonground_classification_and_scan_angle_cut.md)

## Goal

The delivered ground class stops dead at 18° off nadir, and about a million
at-ground returns per tile sit unassigned beyond it. Those returns measure
0.065–0.067 m RMSE against neighbouring flight lines, inside the USGS QL2 bar of
0.10 m, so they are good data that was thrown away.

This run asks two questions and no others:

1. If we classify ground ourselves with no angle rule, how many of the empty DEM
   cells fill in?
2. Where the vendor already had ground, does our surface agree with theirs?

It does **not** ask whether detection improves. That is the next thing and it is
still open.

## Inputs

| What | Path |
|---|---|
| Source tiles | `data/_source/lidar/westernpa/OTHER_DATA/` — squares `616591`, `621594` |
| Script | `notebooks/wellsight_v2/s7_analysis/_smrf_reclassify_ground.py` |
| Pit polygons for the depth check | `data/9t/derived/05/` pit dataset manifest |

Square `621594` is a 9t training tile. Square `616591` is not — it sits in the
613590 block. Both are in the PA WesternPA 2019 D20 March-2020 flight block, the
one with the cut.

## Method

PDAL CLI via `subprocess` with a pipeline JSON, per CLAUDE.md — the Python
bindings do not work here.

```
filters.ferry     Classification => VendorClass    keep both labels on the point
filters.hag_nn    count 8, allow_extrapolation
filters.outlier   statistical, mean_k 8, multiplier 3.0
filters.smrf      cell 1.0, slope 0.35, window 18.0, threshold 0.5, scalar 1.25,
                  ignore Classification[7:7]
writers.las       extra_dims VendorClass, HeightAboveGround
```

`filters.ferry` is the part that makes the comparison honest. It copies the
vendor's label into a separate dimension before SMRF overwrites `Classification`,
so every point carries both answers and the cross-tab is per point, not per
raster cell.

DEMs at 0.5 m by the Phase 1 method — `filters.delaunay` → `filters.faceraster`
→ `writers.raster`, not `writers.gdal` IDW — so the two surfaces are built
identically and only the input class differs.

**Slope sweep.** SMRF's `slope` was swept 0.15 / 0.25 / 0.35 / 0.50 / 0.70 on
`616591` before picking one. Recovered points move by 0.9% across that whole
range (1,443,045 → 1,456,380) and agreement with the vendor moves by 0.06%, so
the result does not hinge on the choice. `0.35` was taken as the middle of a flat
curve. Each run is ~95 s.

## Results

| | `616591` | `621594` |
|---|---|---|
| points | 9,466,172 | 8,956,340 |
| vendor ground | 5,838,895 | 6,051,709 |
| SMRF ground | 7,290,294 | 7,665,937 |
| **recovered** (class 1 → ground) | **1,451,879** | **1,615,359** |
| dropped (vendor ground → not) | 480 | 1,131 |
| agreement, per point | 84.7% | 82.0% |
| of the recovered, beyond 18° | 73.0% | 75.5% |
| median scan angle of the recovered | 18.50° | 18.74° |
| median height above ground, recovered | 0.005 m | 0.005 m |

**DEM voids, 0.5 m cells inside the tile footprint**

| | `616591` | `621594` |
|---|---|---|
| cells | 5,538,952 | 5,531,754 |
| empty with vendor ground | 885,464 — **15.99%** | 683,738 — **12.36%** |
| empty with SMRF ground | 552,385 — **9.97%** | 346,578 — **6.27%** |
| cells closed | 333,468 | 338,068 |

**Where the surface moved.** `ground_cell_status_<tile>_0p5m.tif` labels every
cell 0 = the vendor already had ground there, 1 = closed by SMRF, 2 = still
empty. Splitting the elevation difference by that label is the whole safety
check:

| cell class | 95th-percentile \|dz\| | share over 10 cm |
|---|---|---|
| 0 — vendor already had ground | 0.013 m / 0.010 m | **0.37% / 0.26%** |
| 1 — closed by SMRF | 0.491 m / 0.529 m | 28.3% / 22.6% |
| 2 — still empty | 0.100 m / 0.215 m | 5.0% / 7.7% |

The movement is confined to cells that were previously being guessed. Where the
vendor had real ground, the two surfaces sit on top of each other — 0.3% of cells
differ by more than 10 cm, and the median difference over the whole tile is
0.000 m. That is the result that matters: we did not rebuild the terrain, we
filled the holes in it.

**Pit depth did not change.** 61 and 98 pits measured. Median depth 0.880 →
0.899 m and 0.774 → 0.800 m; the median per-pit change is 0.0005 m and 0.002 m.
Three pits on `621594` deepened by more than 10 cm, none on `616591`. The pits
were already resolved; this run does not make them deeper, it makes the ground
*around* them exist.

## Interpretation

The angle cut cost us about a sixth of the ground surface on one tile and an
eighth on the other, and roughly three quarters of what SMRF recovers sits beyond
18°, which is the cut being undone rather than a general reclassification. The
recovered points have a median height above ground of 5 mm, so they are on the
ground, not near it.

Halving the void rate is real but it is not zero. 6–10% of cells still have no
ground return under them — genuinely occluded ground under dense canopy, which no
reclassification can invent.

## Reproduce

```
python notebooks/wellsight_v2/s7_analysis/_smrf_reclassify_ground.py \
    --tiles 616591 621594 --slope 0.35
python notebooks/wellsight_v2/s7_analysis/_smrf_reclassify_ground.py \
    --tiles 616591 --sweep
```

## Outputs

`data/9t/results/smrf_ground/`

- `dem_vendorground_616591_0p5m.tif`, `dem_vendorground_621594_0p5m.tif`
- `dem_smrfground_slope0p35_616591_0p5m.tif`, `dem_smrfground_slope0p35_621594_0p5m.tif`
- `ground_cell_status_616591_0p5m.tif`, `ground_cell_status_621594_0p5m.tif`
- `smrf_vs_vendor_616591.csv`, `smrf_vs_vendor_621594.csv`
- `smrf_slope_sweep_616591.csv`
- `pit_depth_vendor_vs_smrf_616591.csv`, `pit_depth_vendor_vs_smrf_621594.csv`

The four `dem_*.tif` are 36 MB each and are gitignored (`.gitignore:154`); they
regenerate from the command above. The status rasters and CSVs are tracked.

`docs/presentation/figures_30to45min/smrf_ground/`

- `smrf_vs_vendor_ground_616591_slope0p35.png`
- `smrf_vs_vendor_ground_621594_slope0p35.png`

## What this does not show

Whether any of it improves pit, pad, or road detection. The feature stack is
still built on vendor ground. Rebuilding it on SMRF ground and re-scoring a model
is the open item in `BACKLOG.md`.

## Citations

Pingel, Clarke & McBride (2013), the SMRF paper, is recorded in
`literature/CITATIONS.md`.
