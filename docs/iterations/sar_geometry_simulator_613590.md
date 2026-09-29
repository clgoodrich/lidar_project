# SAR geometry simulator: layover, foreshortening and shadow on 613590 (2026-09-29)

## Goal
Build an interactive teaching tool. It shows where a side-looking radar gets layover, foreshortening and shadow on real lidar terrain. It also shows what the recorded image looks like. This is a side path, not a detection experiment.

## Inputs
- `data/613590/derived/1m/dem_613590_1m.tif`, EPSG:6346, 1 m bare-earth DEM.
- An 800 m window at row 3700, col 400. A 600 m relief scan put the steepest window of the six 1 m area DEMs at 613590 row 3840, col 560 (166.5 m relief).

## Why the peak is synthetic
Real PA terrain cannot show all three effects at once.
- In the 600 m window the slope 99th percentile is 37.1° and the max is 56.6°. Only 0.01% of cells exceed 50°.
- Shadow needs a back-slope steeper than 90° − θ. That is 50° at θ = 40°.
- So a made-up peak is added on top of the real DEM. It is a faceted pyramid, 260 m tall, with 62° faces over 100 m of run and a 22° apron. It is rotated 20° off the grid.
- All three effects then appear for any look direction when 28° < θ < 62°.
- The tool labels this scene "synthetic peak" everywhere. The real-only scene is the second option in the scene menu.

## Model
Far-field plane wave, flat Earth over 800 m. u is horizontal distance along the look direction.
- Slant range: r = u sin θ − z cos θ.
- Layover: dz/du > tan θ, so dr/du < 0.
- Passive layover: a lit cell whose r falls inside the range span of cells on the other side of it, with a tolerance of half a range bin.
- Shadow: a sweep from near range keeps the highest incoming ray. A cell below it is shadowed.
- Range compression K = (dr/du)/sin θ. K is 1 on flat ground and 0 at the layover limit. Cells with 0 < K < 0.5 (slider) are flagged as foreshortened.
- Backscatter per cell = cos(local incidence) × illuminated area. It is binned into slant-range bins with linear splitting. Optional gamma speckle.
- Image views: slant range as recorded, ground range projected to the scene median height, and terrain-geocoded with the DEM.

## Outputs
- `data/613590/derived/1m/clips/dem_real_sargeom_scene_800m_613590_1m.tif` is the real clip layer (gitignored under `data/**/clips/`, regenerable).
- `data/613590/derived/1m/clips/dem_synthetic_peak260m_face62deg_on_real_sargeom_scene_800m_613590_1m.tif` is the real clip plus the synthetic peak (gitignored, regenerable).
- `data/613590/results/sar_geometry/sar_geometry_simulator_layover_foreshortening_shadow_800m_613590_2m.html` is the self-contained tool, 0.9 MB, with both scenes embedded at 2 m.
- Published privately at https://claude.ai/artifact/LvXZH2uhAdbmdrVuosN5tU.

## Result
At the Sentinel-1-ascending-like default (heading 348°, right-looking, θ 40°), the synthetic scene is 1.5% layover, 5.1% passive layover, 4.9% shadow and 7.0% foreshortened (K < 0.5).

## Colour
The class colours are the repo's validated lost/found trio: layover `#D97706`, shadow `#A31515`, foreshortening `#1F5FA8`. `validate_palette.js --pairs all` on the light surface gives a worst pair of ΔE 21.1 deutan and 22.6 normal. On the dark surface the lightness band and contrast checks fail. So every class carries a text label, and passive layover also carries a hatch.

## Limits
There is no volume or canopy scattering, no antenna pattern, no Earth curvature and no incidence change across the swath. Preset headings and angles are approximate mid-swath values.

## Reproduce
```
python notebooks/wellsight_v2/s7_analysis/_build_sar_geometry_simulator_613590.py
```
The template is `notebooks/wellsight_v2/s7_analysis/_sar_geometry_simulator_template.html`.
