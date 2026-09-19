# The 9t area with the discarded ground put back — four pictures

**Date:** 2026-09-19
**Status:** figures done; effect on detection still untested
**Builds on:** [`smrf_ground_reclassification.md`](smrf_ground_reclassification.md),
[`nonground_classification_and_scan_angle_cut.md`](nonground_classification_and_scan_angle_cut.md)

## Goal

The two-tile SMRF run measured what putting the discarded wide-angle returns
back does. This draws it, over the whole 9t training area, so the shape of the
loss is visible rather than only tabulated:

1. the ground surface we were given, and where it rests on nothing
2. the same area showing only the ground that was thrown away
3. the two together
4. one 300 m slice, edge-on, before and after

## Inputs

| What | Path |
|---|---|
| Source tiles | `data/_source/lidar/westernpa/OTHER_DATA/` — the nine 9t squares |
| Script | `notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py` |
| Extent | 619500–624000 E, 4593000–4597500 N, EPSG:6346 |

Squares: `619593 619594 619596 621593 621594 621596 622593 622594 622596`.

## Method

Per square, one PDAL pass — `filters.ferry` parks the vendor label in
`VendorClass`, `filters.hag_nn`, `filters.outlier`, then `filters.smrf`
(`cell` 1.0, `slope` 0.35, `window` 18.0, `threshold` 0.5, `scalar` 1.25) — and
three surfaces are rasterised from that one file by `filters.expression`:

| surface | expression |
|---|---|
| vendor | `VendorClass == 2` |
| recovered only | `Classification == 2 && VendorClass != 2` |
| both | `Classification == 2 \|\| VendorClass == 2` |

"Both" is the **union**, not the SMRF answer. SMRF also drops a few hundred
points per square that the vendor called ground; this is a picture of adding
data, not of replacing it, so those stay in.

DEMs are Delaunay TIN + faceraster at 0.5 m — the Phase 1 method — on a grid
aligned to the 9t origin so the nine squares mosaic exactly.

### Two measurement decisions worth stating

**A TIN is not a coverage map.** Delaunay spans its own convex hull, so the DEM
has a value in every cell including straight across a hole — those values are
interpolation between two rims. The first version of this script measured voids
as raster nodata and got 0.0%, which is wrong. Voids are counted on the
**points**: cells the laser reached (any return) that hold no ground return.
That reproduces `_smrf_reclassify_ground.py` exactly on `621594` — 12.36% →
6.25%.

**Holes are speckle at 0.5 m and regions at 5 m.** A 0.5 m cell holds about one
ground return on average, so half of them come up empty by chance even over
open ground. A binary hole mask at display scale therefore shows almost nothing
(1.4% of 1.5 m blocks). The maps draw void *density* per 5 m block instead, as a
wash whose opacity is the value, and every gap statement in the section is made
at **1 m**, where a cell holds about four returns and an empty one means
something.

### The section line is chosen by the data

The 50 m window holding the most cells that the recovery actually **closes** —
no delivered ground, ground after — is found first; then every azimuth in
5-degree steps through the top 40 such windows is scored by how much of the line
is missing-then-supplied, and the best is kept. The line is also inset by half
its length from the tile edge, because the section is drawn from one square's
points and a line that runs off it has an empty half.

Two earlier versions of this picker were wrong and both are worth recording:
scoring by recovered-point density put the line inside the swath overlap, where
the vendor already had ground and the two panels came out identical; and a 6 m
corridor with a 1 m tolerance made every line "continuous end to end", because
at 4.8 points per square metre some vendor point is nearly always within a metre.

## Results

Over the 9t area, 51,470,048 cells of 0.5 m that the laser reached:

| | |
|---|---|
| no ground return, as delivered | **13.79%** |
| no ground return, with the discarded points back | **8.24%** |
| cells closed | **2,857,002** |
| discarded ground points added | **13,746,698** |

The section, 300 m at bearing 010° through square `621594`: **32%** of the line
has no ground beneath it as delivered, **2%** after.

The maps show what the numbers cannot: the loss is not spread evenly. It runs in
three hard vertical stripes across the whole 4.5 km, which are the edges of the
flight swaths, plus diffuse speckle under dense canopy. Map 3 shows the stripes
gone and the speckle remaining — the stripes were a processing rule, the speckle
is real occlusion that no reclassification can invent.

## Outputs

`docs/presentation/figures_30to45min/recovered_ground_9t/`

- `map_1_ground_as_delivered_9t_0p5m.png`
- `map_2_ground_thrown_away_9t_0p5m.png`
- `map_3_ground_both_together_9t_0p5m.png`
- `cross_section_before_after_621594_300m_az10_w2p0_slope0p35.png`

`data/9t/results/recovered_ground_9t/`

- `count_vendorground_9t_0p5m.tif` — ground returns per cell, as delivered
- `count_recoveredground_slope0p35_9t_0p5m.tif` — ground returns per cell, discarded
- `recovered_ground_9t_summary.json`
- `dem_vendorground_9t_0p5m.tif`, `dem_vendorplusrecovered_slope0p35_9t_0p5m.tif`
  — 146 MB each, gitignored (`.gitignore:158`), regenerate from the command below
- `_tiles/` — 27 per-square rasters, 1.2 GB, gitignored

## Colour

No figure here contains a red/green pair, per a standing instruction given
2026-09-19. Checked with the dataviz validator over **all** pairs, not just
adjacent ones:

| role | colour | |
|---|---|---|
| ground the survey delivered | `#1F5FA8` | |
| ground it threw away | `#D97706` | |
| no measurement at all | `#A31515` | also hatched, so never colour alone |

Worst pair ΔE 21.1 deuteranopia, 21.5 protanopia, 22.6 normal; every colour at
least 3:1 against the paper.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py \
    --workers 3 --slope 0.35
python notebooks/wellsight_v2/s7_analysis/_recovered_ground_maps_9t.py --skip-smrf
```

About 8 minutes for the nine SMRF passes at three at a time, then roughly 20
minutes of rasterising and drawing. `--skip-smrf` reuses the per-square rasters
and only redraws.

## What this does not show

Whether any of it improves pit, pad or road detection. The feature stack is still
built on vendor ground. That remains the open item in `BACKLOG.md`.
