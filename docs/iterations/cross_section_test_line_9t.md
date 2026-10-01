# Cross sections along the test lines, 9t

**Date:** 2026-10-01
**Status:** done. Made on request from a line the user drew in QGIS.
**Script:** `notebooks/wellsight_v2/s7_analysis/_cross_section_test_line1_9t.py`

## Goal

Draw a cross section of the ground along one line, with the pads, pits and roads marked where the line crosses them.

## Inputs

| Input | Detail | Path |
|---|---|---|
| Lines | One feature per line in layer `test_line`. Line 1 is 111.3 m long, bearing 28° (SSW to NNE). Drawn in EPSG:4326 and reprojected to EPSG:6346. | `test_line_cross_section.gpkg` (repo root, user-owned, not committed) |
| Ground | 2019 lidar DEM, 1 m | `data/9t/derived/1m/dem_9t_1m.tif` |
| Surface top | 2019 lidar DSM, 1 m. Canopy, brush and structures. | `data/9t/derived/1m/dsm_9t_1m.tif` |
| Radar | NISAR summer 2026 mean, track 162, HH and HV, 5 m, as delivered | `data/9t/derived/nisar_gslc_5m/nisar_{hh,hv}_summer_2026_track162_9t_5m.tif` |
| Features | `plat` (pads), `pit_outside` (whole pit incl. rim), `pit_inside` (pit floor), `roads` (centrelines) | `qgis/annotations/annotations_proj.gpkg` |

## Method

- The line is sampled every 0.25 m.
- The DEM and DSM are read with bilinear interpolation. NISAR is read nearest-pixel, so its 5 m steps show.
- Each feature span is where the line enters and leaves the polygon.
- Roads are centrelines with no width. Each crossing is drawn as the centreline ±2.5 m. That width is an assumption.

## Line 1: what it crosses

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

## True-scale version, added 2026-10-01

The user asked for the cross section with no vertical or horizontal exaggeration.
- Both data panels are drawn 1 m across to 1 m up. Each axes box is sized in inches from its data range, so the ratio is exact.
- The grid is 5 m squares in the elevation panel. The LRM panel uses a 1 m grid.
- At true scale the 19 m rise over 111 m reads as a gentle slope. The pad and pit benches are only small steps.
- The LRM's ±1.2 m is nearly flat at true scale. The exaggerated figures above are needed to read it.

## Line 2, added 2026-10-01

The user drew a second line in the same gpkg. It is 178.7 m long, bearing 41° (SW to NE).
The script now runs once per feature. Before this it merged every feature into one line, which would have joined the two lines into a single zig-zag profile.

| Feature | Distance along line (m) | Pit floor LRM 25 m | Max height above ground on the floor |
|---|---|---|---|
| Pad 1 | 4.1 – 25.1 | | |
| Pit 1, incl. rim | 20.8 – 36.6, floor 23.6 – 30.7 | −0.56 m | 14.7 m (tree canopy) |
| Road centreline | 97.7 | | |
| Pad 2 | 130.8 – 159.0 | | |
| Pit 2, incl. rim | 135.3 – 149.1, floor 139.6 – 144.9 | −0.79 m | 5.6 m (brush) |

- **Pit 2 is the clearest pit seen on either line.** It is a 0.8 m hollow with a +0.47 m rim on its downhill side.
- **Pit 1 is shallower and lies under 15 m trees.** Its floor is −0.56 m and its edges are softer.
- **The road is a faint −0.2 m trough** again.
- **No cut-bench low on these pads.** Line 2 runs more along the slope, so there is no strong inside corner like the −1.1 m one on line 1.

## Line 3, added 2026-10-01

A third line, 41.9 m long, bearing 204° (NNE to SSW). It crosses one road centreline at 22.7 m and no pads or pits.

- **The road shows a full cut-and-fill profile.**
  - The downhill edge is a raised fill shoulder, +0.48 m on the LRM at about 20 m.
  - The tread is nearly flat at about 427.8 m.
  - The uphill toe is a −0.40 m low at about 25 m, where the cut slope meets the tread. That is where a ditch would run.
- **The canopy gap marks the open tread.** The DSM drops to the ground from about 20.7 to 23.8 m, so the opening is about 3 m wide.
  - The assumed ±2.5 m road band (20.2 – 25.2 m) covers the tread, the shoulder and the toe.
- This is the same concave-corner effect as on line 1's pad. A road cut toe can look like a 0.4 m linear hollow on the LRM.

## Outputs

- Figure: `data/9t/results/cross_sections/figures/cross_section_test_line1_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.png`
- Each figure below exists for `line1`, `line2` and `line3`. Line 1's files were renamed from `cross_section_test_line_...` with `git mv`.
- True-scale figure: `data/9t/results/cross_sections/figures/cross_section_test_line1_true_scale_1to1_dem_dsm_lrm_with_pads_pits_roads_9t_1m.png`
- LRM figure: `data/9t/results/cross_sections/figures/cross_section_test_line1_lrm_11m_25m_with_pads_pits_roads_9t_1m.png`
- Profile table, one row per 0.25 m, with a zone column and both LRMs: `data/9t/results/cross_sections/cross_section_test_line1_dem_dsm_nisar_summer2026_t162_with_pads_pits_roads_9t_1m.csv`
- The line in EPSG:6346: `data/9t/results/cross_sections/test_lines_cross_section_epsg6346_9t.gpkg`

Colours are pad `#1F5FA8`, pit `#D97706` and road `#A31515`. The dataviz `validate_palette.js --mode light --pairs all` gives worst pair ΔE 21.1 for deuteranopia. Each feature also has its own row, hatch and label.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_cross_section_test_line1_9t.py
```
