# Sentinel-1 small-metal detection, first experiment (9t and 613590)

Run 2026-11-13. The "first experiment" of the SAR small-metal methodology note (user, 2026-11-12): CFAR on the stack mean intensity, then amplitude dispersion, scored against known wells.

## Data

- OPERA CSLC-S1 V1, VV, Sentinel-1A track 77 ascending. 32 dates at 12 days, 2025-04-03 to 2026-04-10.
- Windows only (UTM 17N E 613300-624200, N 4589800-4597700, about 86 km2 of valid ground, covers 9t and 613590). Fetched by `_s1_cslc_window_fetch_9t.py --range 2025-04-01 2026-04-15 T077` into `data/_source/s1_cslc_windows/` (git-ignored).
- Wells. PA DEP `venango_wells_all.gpkg` (2026-04 export). 3,412 inside the valid window and outside the water buffer. Active 1,581, plugged 936, abandoned or orphan lists 806, never drilled 89.

## Method and deviations from the note

- CFAR on mean intensity. Resolution cell 1 x 2.2 pixels (about 4.5 m x 22 m). Guard 3 x 3 cells (3 x 7 px), background 15 x 15 cells (15 x 33 px).
- Threshold. Mean of 32 dates is Gamma-distributed. Estimated looks 12.4 (not 32: dates are partly correlated and the forest is textured). T = 2.97 (4.7 dB) at P_fa 1e-6. Thresholds 3 to 10 dB also swept.
- Candidates are peaks of connected regions above T, refined by a 3-point parabola.
- Steadiness. D_A = std(A) / mean(A) over 32 dates. Candidate kept as steady when D_A < 0.25.
- Hit. A candidate inside a 10 m x 20 m ellipse around the well. Baselines are 20,000 random points and one local decoy per well (150 to 600 m away, 30 m from any well).
- **No 2x oversampling.** The geocoded CSLC spectrum already fills the band in both axes, with or without the azimuth carrier removed. Zero-padding cannot recover pixel-fence loss here. That needs radar-geometry IW SLCs (4 to 8 GB per scene).
- **No calibration.** One track and geometry, and both tests are ratios.
- **Water masked.** Pixels below 0.15 x the median intensity (1.4%), buffered 30 m (3.0%). The first run had no mask, and dark river water in the background ring made the banks pass CFAR. Roads and buildings are not masked.

## Results (P_fa 1e-6, water masked)

| | Candidates | Wells hit | Random points | Local decoys |
|---|---|---|---|---|
| CFAR | 481 | 0.26% | 0.44% | 0.18% |
| CFAR + D_A < 0.25 | 9 | 0% | 0.02% | 0% |

| Status | Wells | Hit by CFAR |
|---|---|---|
| Active | 1,581 | 0.38% (6) |
| Plugged | 936 | 0.32% (3) |
| Abandoned or orphan | 806 | 0% |
| Never drilled | 89 | 0% |

- Wells are hit no more often than random ground at any threshold from 3 to 10 dB (ratio 0.5 to 1.1).
- Steadiness. No pixel in the window has D_A < 0.25 except 9 candidates. Median D_A is 0.53, the Rayleigh value for pure speckle.
- The 9 steady targets are all very bright (9 to 29 dB above background). Two sit near active wells (34 m and 82 m) but outside the hit ellipse. The other seven are 380 to 825 m from any well, in clusters on the river floodplain.
- Most of the 481 CFAR candidates sit on the floodplain and on slopes facing the radar, not on the upland well fields.

## Interpretation

- At Sentinel-1 resolution, Venango wellheads, pumpjacks and tank sites do not stand out in brightness and are not steady scatterers. Active wells are hit at the same rate as random ground.
- This matches the NISAR steady-bright-target result (Warren wells 3.9% against 5.2% random).
- The note's own guide says this number decides whether sublooks, polarimetry or finer data are worth it. A hit rate at chance argues against more C-band work. A finer sensor (X-band, about 1 m) is the step the note points to if the idea is kept.
- Caveats. Single VV polarization (no VH in CSLC). No oversampling, so peaks keep up to about 4 dB fence loss. DEP coordinate accuracy is unknown, and the 10 m x 20 m ellipse may be too tight for older records.

## Outputs

- `data/9t/results/s1/s1_metal_cfar_hit_rates_9t613590.csv` (threshold sweep, by status)
- `data/9t/results/s1/s1_metal_cfar_candidates_9t613590.gpkg` (481 candidates, `steady` flag, SCR, D_A)
- `data/9t/results/s1/s1_metal_cfar_wells_9t613590.gpkg` (wells with hit flags, D_A and SCR at the well)
- `data/9t/results/s1/s1_metal_cfar_summary_9t613590.json`
- `data/9t/results/s1/s1_metal_cfar_map_9t613590.png` (greyscale amplitude, wells as blue circles, candidates as orange plus signs; lost/found palette, validated all pairs, worst dE 21.1 deutan)

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_s1_cslc_window_fetch_9t.py --range 2025-04-01 2026-04-15 T077
python notebooks/wellsight_v2/s5_eval/_s1_metal_cfar_9t.py
```

## Sources

- OPERA CSLC-S1 V1, NASA JPL OPERA, ASF DAAC. https://www.earthdata.nasa.gov/data/catalog/asf-opera-l2-cslc-s1-v1-1
- Amplitude dispersion criterion D_A < 0.25: Ferretti, Prati and Rocca 2001, Permanent scatterers in SAR interferometry, IEEE TGRS 39(1), 8-20.
