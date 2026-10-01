# Cross section along the test line, 9t

**Date:** 2026-10-01
**Status:** done. Made on request from a line the user drew in QGIS.
**Script:** `notebooks/wellsight_v2/s7_analysis/_cross_section_test_line_9t.py`

## Goal

Draw a cross section of the ground along one line, with the pads, pits and roads marked where the line crosses them.

## Inputs

| Input | Detail | Path |
|---|---|---|
| Line | One line, 111.3 m long, bearing 28° (SSW to NNE). Drawn in EPSG:4326 and reprojected to EPSG:6346. | `test_line_cross_section.gpkg` (repo root, user-owned, not committed) |
| Ground | 2019 lidar DEM, 1 m | `data/9t/derived/1m/dem_9t_1m.tif` |
| Surface top | 2019 lidar DSM, 1 m. Canopy, brush and structures. | `data/9t/derived/1m/dsm_9t_1m.tif` |
| Radar | NISAR summer 2026 mean, track 162, HH and HV, 5 m, as delivered | `data/9t/derived/nisar_gslc_5m/nisar_{hh,hv}_summer_2026_track162_9t_5m.tif` |
| Features | `plat` (pads), `pit_outside` (whole pit incl. rim), `pit_inside` (pit floor), `roads` (centrelines) | `qgis/annotations/annotations_proj.gpkg` |

## Method

- The line is sampled every 0.25 m.
- The DEM and DSM are read with bilinear interpolation. NISAR is read nearest-pixel, so its 5 m steps show.
- Each feature span is where the line enters and leaves the polygon.
- Roads are centrelines with no width. Each crossing is drawn as the centreline ±2.5 m. That width is an assumption.

## What the line crosses

| Feature | Distance along line (m) |
|---|---|
| Pit, incl. rim | 9.8 – 31.5 |
| Pit floor | 16.1 – 22.8 |
| Pad | 17.5 – 46.1 |
| Road centreline | 80.1 (drawn 77.6 – 82.6) |

- Ground rises 18.8 m along the line, from 427.6 to 446.4 m.
- The pit floor sits on a flat bench at about 432.3 m. The pad is a second bench at about 435.5 m, cut into the slope.
- The road shows as a small flat step at about 443 m.
- The radar varies by 10 dB or more from pixel to pixel along the line. It shows none of these features clearly.

## Local relief (LRM) version, added 2026-10-01

The user asked for the same line on the LRM.
- **LRM** is the DEM minus its moving average. It removes the hillslope and leaves the bumps and hollows.
- Inputs are `data/9t/derived/1m/lrm_25_9t_1m.tif` (25 m window) and `data/9t/derived/1m/lrm_11_9t_1m.tif` (11 m window), from `_build_derivatives.py`.

| Feature | LRM 25 m | LRM 11 m |
|---|---|---|
| Pit floor, lowest | −0.74 m | −0.51 m |
| Pad, range | −1.11 to +0.44 m | — |
| Road, range | −0.27 to −0.11 m | — |

- **The pit reads as a clear hollow.** Its downhill rim stands +1.2 m above the local mean at about 13 m.
- **The deepest low is not the pit.** It is −1.1 m at about 40 m, on the pad. That is the inside corner where the flat pad meets the uphill cut slope.
  - An LRM always dips at a concave break like this, and peaks at a convex one.
  - So a cut bench can look as deep as a pit on the LRM alone.
- **The road is a faint shallow trough,** about 0.2–0.3 m.
- The 11 m window gives smaller values everywhere. It follows narrower features and averages less of the bench edge in.

## Outputs

- Figure: `data/9t/results/cross_sections/figures/cross_section_test_line_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.png`
- LRM figure: `data/9t/results/cross_sections/figures/cross_section_test_line_lrm_11m_25m_with_pads_pits_roads_9t_1m.png`
- Profile table, one row per 0.25 m, with a zone column and both LRMs: `data/9t/results/cross_sections/cross_section_test_line_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.csv`
- The line in EPSG:6346: `data/9t/results/cross_sections/test_line_cross_section_epsg6346_9t.gpkg`

Colours are pad `#1F5FA8`, pit `#D97706` and road `#A31515`. The dataviz `validate_palette.js --mode light --pairs all` gives worst pair ΔE 21.1 for deuteranopia. Each feature also has its own row, hatch and label.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_cross_section_test_line_9t.py
```
