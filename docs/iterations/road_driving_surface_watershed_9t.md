# Road driving-surface polygons by seeded watershed, 9t

**Date:** 2026-10-01
**Status:** first full run done. Works on hillside roads. On flat ground it can only cap the width, not measure it.
**Script:** `notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py`

## Goal

Turn the road centrelines into polygons of the driving surface. The edges should come from the ground, not from an assumed width.
The user chose the driving surface only, meaning the tread between the fill shoulder and the toe of the cut bank. The cut and fill slopes are excluded.

## Why a watershed

The test-line cross sections showed a hillside road as a flat tread between two breaks in slope (`docs/iterations/cross_section_test_line_9t.md`, line 3).
- A marker-controlled watershed floods an "edge" raster from seeds and draws boundaries where the floods meet (Beucher & Meyer 1993; Vincent & Soille 1991).
- If the edge raster peaks at slope breaks, the boundary lands on them.

## Inputs

| Input | Path |
|---|---|
| 0.5 m DEM | `data/9t/derived/05/dem_9t_05.tif` |
| Road centrelines, 206 km in 9t | `qgis/annotations/annotations_proj.gpkg`, layer `roads` |
| User's test lines, used for QC | `test_line_cross_section.gpkg` |

## Method

| Step | Detail |
|---|---|
| Smooth | Gaussian σ = 1 px (0.5 m) on the DEM, then again on the slope |
| Edge raster | \|∇ slope\|, the change of slope per metre. It peaks on the shoulder and the cut-bank toe. |
| Road seeds | Centreline pixels, except any steeper than 25° |
| Background seeds | The ring 6 m from the centreline, plus every pixel steeper than 25°. A cut bank or fill slope is steeper than any drivable grade. |
| Mask | Within 6 m of a centreline. Nothing farther out can become road. |
| Clean-up | Holes ≤ 4 m² filled |
| Tiling | 2000 px tiles with a 40 px (20 m) halo |
| QC transects | Every 5 m across each centreline. Width is the road run through the centreline point. |

The **limit flag** marks a transect side whose run reached the 6 m ring.
- It means no break in slope was found on that side.
- The width there is a cap, not a measurement.

## Results, full 9t

| | Value |
|---|---|
| Road length | 206.1 km |
| Polygon area | 109.4 ha |
| Transects | 41,214 |
| No road at the centreline point | 94 (0.2%) |
| Width, median (10th–90th percentile) | 5.5 m (2.5 – 9.5 m) |
| Capped on one side | 15.4% |
| Capped on both sides | 1.9% |
| Median width with both edges found | 5.0 m |

Test-line crossings, with width measured along the test line (it may cross at an angle):

| Line | Centreline at | Polygon along line | Width | Reading |
|---|---|---|---|---|
| 1 | 80.1 m | 76.1 – 83.9 m | 7.8 m | Bend on flat ground. No break, so it is capped. |
| 2 | 97.7 m | 93.9 – 103.7 m | 9.8 m | Lumpy. A weak uphill edge. |
| 3 | 22.7 m | 20.1 – 25.4 m | 5.3 m | Matches the cross section: shoulder at about 20 m, cut-bank toe at about 25 m. |
| 4 | 42.9 m | 40.4 – 45.8 m | 5.4 m | Downhill edge on the shoulder. The uphill edge wanders where the cut is weak. |
| 4 | 188.4 m | 184.8 – 191.6 m | 6.9 m | Tight on both sides. Line 4 crosses at an angle. |
| 4 | 301.2 m | 296.5 – 303.9 m | 7.4 m | Downhill good. The uphill edge bulges. |

## Interpretation

- **On benched hillside roads it finds the driving surface.** Line 3 lands within about 0.5 m of both breaks read off the cross section.
- **The downhill edge is the more reliable one.** The fill slope is steep, so the 25° seeds pin the edge to the shoulder.
- **The uphill edge fails where the cut is low or rounded.** There the flood runs out to the 6 m ring.
- **On flat ground there is no break to find.** The polygon fills the corridor, and the transects flag it as capped.
- **The 2.5 m low tail** comes mostly from places where the centreline sits off the tread. A steep pixel then stops the flood early.
- **Canopy gap is narrower than the tread.** On line 3 the opening is about 3 m, against a 5.3 m tread. Branches overhang the tread edges.

## Limits

- No measured road widths exist for 9t, so only the test-line crossings check the edges.
- The 0.5 m DEM may be finer than the point density supports (BACKLOG "Grid resolution"). Slope breaks are softer than in the field.
- The 6 m ring and the 25° threshold are judgement calls and have not been tuned.
- Junctions and switchbacks overlap their neighbours' corridors. They come out as one blob.

## Outputs

- `data/9t/results/road/driving_surface/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05.gpkg`
  - layer `driving_surface`: the polygons
  - layer `transect_widths_every5m`: points with `width_m`, `hit_limit_left`, `hit_limit_right` and `hit_limit_any`
- `data/9t/derived/05/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05_mask.tif`: the 0.5 m road mask (gitignored, regenerable)
- `data/9t/results/road/driving_surface/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05_transect_widths_every5m.csv`
- `data/9t/results/road/driving_surface/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05_test_line_crossings.csv`
- `data/9t/results/road/driving_surface/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05_summary.json`
- `data/9t/results/road/driving_surface/figures/road_driving_surface_watershed_bg6m_slope25deg_full_9t_05_test_line_crossings_on_hillshade.png`
- The pilot run, `..._pilot_testlines_9t_05...`, is kept beside these. It covers only the test-line windows.

Figure colours:
- The polygon edge is `#A31515` solid, the centreline charcoal dashed, and the test line `#1F5FA8` dotted.
- The lost/found palette was checked with dataviz `validate_palette.js --mode light --pairs all`: worst pair ΔE 21.1 deutan.
- Line style differs too, so colour is never the only cue.

## Next steps (in BACKLOG)

1. Use the transect limit flags to drop capped edges or fall back to a fixed half-width there, rather than keeping the 6 m cap.
2. Add a cross-slope test for flat ground. The tread is crowned or rutted at the centimetre scale, which a 0.5 m DEM may not resolve.
3. Tune the ring distance and the slope threshold against hand-traced driving surfaces at 20–30 stations.

## Reproduce

```bash
python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py --pilot
python notebooks/wellsight_v2/s2_labels/_road_driving_surface_watershed_9t.py
```
