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
The radar is a point source on its flight track, off to one side of the scene. u is horizontal distance along the look direction, measured from the scene centre.
- Orbit placement (v2, 2026-09-29). Incidence θ at the ground and platform altitude H set the geometry on a spherical Earth (R = 6371 km). The look angle at the sensor is γ = asin(R sin θ / (R + H)). The Earth-central angle is β = θ − γ. The ground distance from the nadir track is Rβ. The slant range is R0 = R sin β / sin γ.
- Local frame. The radar sits at u = −R0 sin θ and height z_c + R0 cos θ, where z_c is the scene median height. The scene centre then sees θ at range R0. The ground is treated as flat across the 800 m scene.
- Slant range: r = |radar − cell|. Wavefronts are circles around the radar. θ drifts across the scene, by about 0.04° for Sentinel-1 and by about 17° for a 1.5 km airborne platform.
- Layover: dr/du < 0 along the terrain.
- Passive layover: a lit cell whose r falls inside the range span of cells on the other side of it, with a tolerance of half a range bin.
- Shadow: a cell is hidden when a nearer cell has a smaller depression angle from the radar.
- Range compression K = (dr/du)/sin θ_local. K is 1 on flat ground and 0 at the layover limit. Cells with 0 < K < 0.5 (slider) are flagged as foreshortened.
- Backscatter per cell = cos(local incidence) × illuminated area. It is binned into slant-range bins with linear splitting. Optional gamma speckle.
- Image views: slant range as recorded, ground range projected to the scene median height, and terrain-geocoded with the DEM.
- Flight track display (v2). The map and the north-up image views mark the track on the sensor-side edge with its distance. If the track falls inside the map, it is drawn at its true position. The slant view draws the track beside the near-range edge. The profile names the radar's across-track, slant and vertical distances. Two new panels show the track, the illustrative swath and the scene in plan view, and the cross-track geometry to scale.
- v1 used a plane wave at θ with no platform position. It had no flight track.

## Outputs
- `data/613590/derived/1m/clips/dem_real_sargeom_scene_800m_613590_1m.tif` is the real clip layer (gitignored under `data/**/clips/`, regenerable).
- `data/613590/derived/1m/clips/dem_synthetic_peak260m_face62deg_on_real_sargeom_scene_800m_613590_1m.tif` is the real clip plus the synthetic peak (gitignored, regenerable).
- `data/613590/results/sar_geometry/sar_geometry_simulator_layover_foreshortening_shadow_800m_613590_2m.html` is the self-contained tool, 0.9 MB, with both scenes embedded at 2 m.
- Published privately at https://claude.ai/artifact/LvXZH2uhAdbmdrVuosN5tU.

## Result
At the Sentinel-1-ascending-like default (heading 348°, right-looking, θ 40°), the synthetic scene is 1.5% layover, 5.1% passive layover, 4.9% shadow and 7.0% foreshortened (K < 0.5).

## Colour
The flight track is teal `#009AA0`. With the three class colours and `--pairs all` on the light surface, its worst pair is ΔE 15.7 protan against `#D97706`, and 17.9 normal against `#1F5FA8`. It also carries a dashed line, chevrons and a text label.

The class colours are the repo's validated lost/found trio: layover `#D97706`, shadow `#A31515`, foreshortening `#1F5FA8`. `validate_palette.js --pairs all` on the light surface gives a worst pair of ΔE 21.1 deutan and 22.6 normal. On the dark surface the lightness band and contrast checks fail. So every class carries a text label, and passive layover also carries a hatch.

## Limits
There is no volume or canopy scattering, no antenna pattern, no Earth curvature and no incidence change across the swath. Preset headings and angles are approximate mid-swath values.

## Reproduce
```
python notebooks/wellsight_v2/s7_analysis/_build_sar_geometry_simulator_613590.py
```
The template is `notebooks/wellsight_v2/s7_analysis/_sar_geometry_simulator_template.html`.
