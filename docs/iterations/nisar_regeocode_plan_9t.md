# Plan: re-place NISAR radar pixels on the 9t lidar ground (Stage 0 done)

Written 2026-10-09. Stage 0 ran on 2026-10-09 and the gate failed, so Stages 1–3 are needed. Results are in the Stage 0 section.

## Goal

NASA places each GSLC pixel using a 30 m global elevation model. That model is based on the Copernicus DEM. Under forest it sits partway up the canopy. A side-looking radar turns a height error into a sideways shift. So pixels may land metres from where the ground really is, and the shift changes with tree height.

This plan places the same radar samples using the 1 m lidar bare-earth DEM instead.

**What it will fix**
- Where each pixel sits on the map.
- The topographic phase in interferograms. The lidar DEM removes it more precisely.
- Slope brightness, through a lidar-based terrain correction.
- It also adds a mask for layover and shadow.

**What it will not fix**
- Resolution. The radar's own resolution is about 5.5 m. Range spacing is 3.1 m slant, about 4.7 m on the ground. Along-track spacing is 4.4 m. Output stays on a 5 m grid. A finer grid would only interpolate.
- Speckle, or the short stack.

## Facts read from the files on 2026-10-09

All three are from granules over 9t, track 162, 2026-09-29, read remotely as metadata only.

**RSLC (radar geometry, before map placement)**
- 41 granules over 9t: 12 beta, 29 provisional. Collections `NISAR_L1_RSLC_BETA_V1` and `NISAR_L1_RSLC_PROVISIONAL_V1`.
- `science/LSAR/RSLC/swaths/frequencyA/HH` and `HV`: 54,720 x 53,886 complex64, about 23.6 GB per polarization. Chunked 512 x 512, so windowed reads work as they do for GSLC.
- `swaths/zeroDopplerTime` (rows) and `swaths/frequencyA/slantRange` (columns) give each sample's time and range.
- The focusing is zero-Doppler. A Doppler centroid table is in `metadata/processingInformation/parameters/frequencyA/dopplerCentroid` (322 x 110). The estimation method is `geometric`.
- The orbit has 40 state vectors and Hermite interpolation (`metadata/orbit`). The orbit type is MOE.
- `identification/lookDirection` = `Left`.

**GSLC (the product we use now)**
- `metadata/radarGrid` holds 3-D cubes on a 500 m x 500 m grid in EPSG:32617. There are 21 heights from −1000 to 9000 m above the ellipsoid, in 500 m steps.
- The cubes include `zeroDopplerAzimuthTime`, `slantRange`, `incidenceAngle` and `losUnitVectorX/Y`.
- **This is the key fact.** The cubes map any (x, y, ellipsoid height) to a radar time and range. So a lidar ground point can be sent to an RSLC row and column by interpolating the cubes. No orbit solver is needed for the main path.
- `ellipsoidalFlatteningApplied` = True and `topographicFlatteningApplied` = True. NASA removed the geometric phase with its own DEM.
- `algorithms/geocoding` = Sinc interpolation. `demInterpolation` = biquintic.
- `timingCorrections` holds solid-earth-tide and ionosphere tables for slant range and azimuth.
- The time units are seconds since midnight of the acquisition date. They are given per file.

**Look direction over 9t, from `losUnitVectorX/Y` (target to sensor, east and north)**

| Track | Pass | East | North | Incidence | Radar looks |
|---|---|---|---|---|---|
| 162 | ascending | +0.695 | +0.230 | 47.0° | west |
| 090 | ascending | +0.598 | +0.179 | 38.6° | west |
| 026 | descending | −0.615 | +0.225 | 40.9° | east |

**Lidar DEM**
- `data/9t/derived/1m/dem_9t_1m.tif` is in NAD83(2011) / UTM 17N, with NAVD88 heights in metres (Geoid12B). Source: `docs/03_las_inspection_report.md`.
- The radar needs ellipsoid heights. The geoid in Venango County is about 34 m below the ellipsoid. Skipping that conversion would shift every pixel by about 30 m. The same 34 m height error divided by tan(incidence) is a ground shift of 32–43 m.

## Stage 0. Measure the current offset first (decision gate)

Script `notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py`

1. Build a 5 m bare-earth DEM from the 1 m DEM by block mean. Compute surface normals.
2. Per track, read `losUnitVectorX/Y` and `incidenceAngle` from the GSLC cubes at 9t. Compute the local incidence angle of every 5 m cell.
3. Simulated brightness: the area-projection model, using the lidar cell area seen per radar pixel (Small 2011). Mark layover and shadow.
4. Cross-correlate the simulated image with the mean HH image per track (`nisar_hh_summer_2026_track*_9t_5m.tif`). Search shifts of −30 to +30 m at 1 m steps.
5. Repeat on 1 km blocks. This gives a shift map. A shift that grows with canopy height means the height error is real.

Outputs
- `data/9t/results/nisar/nisar_lidar_sim_match_shifts_9t.csv`: one row per track and block.
- `data/9t/derived/nisar_gslc_5m/nisar_lidar_sim_t{026,090,162}_9t.tif` (gitignored): simulated brightness, local incidence and layover/shadow bands.
- `data/9t/results/nisar/figures/nisar_lidar_sim_match_9t.png`

**Gate**
- If every block's best shift is within ±2.5 m (half a pixel), NASA's placement is already good. Stop here, and record that the 10–15 m offset came from the weak canopy match.
- If shifts are larger, or vary with canopy height, go on to Stage 1.
- Either way, Stage 0's simulator is reused as the final check in V3.

### Stage 0 result (2026-10-09): gate failed, go on to Stage 1

Script `notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py`. Radar image: band 1 (mean HH dB over all dates) of `data/9t/derived/nisar_gslc_5m/nisar_bright_targets_layers_t<track>_9t.tif`. Blocks are 4 x 4 of 1.1 km, not 1 km, so they divide the 4.5 km tile evenly.

| Track | Looks | Whole-tile shift (east, north) | Away from satellite, block median (range) | Along track, block median | Implied DEM height error |
|---|---|---|---|---|---|
| 026 descending | east | +10, +1 m | 9.6 m (3.7–18.8) | 4.1 m | 8.3 m |
| 090 ascending | west | −10, −3 m | 11.9 m (7.0–20.1) | −0.2 m | 9.5 m |
| 162 ascending | west | −8, −2 m | 9.1 m (5.7–14.9) | −0.4 m | 9.7 m |

- 0 of 48 blocks are within the ±2.5 m gate. No block hit the ±30 m search edge.
- The two ascending tracks push features west and the descending track pushes them east. All three point away from the satellite. That is what a placement height that is too high does.
- Converted with tan(incidence), the three geometries agree on a height error of 8–10 m. This makes a real height error much more likely than a coincidence.
- The shift grows with block canopy height. The correlation is 0.55 (026), 0.60 (090) and 0.62 (162).
- The along-track part is near zero on the ascending tracks. On 026 it is 4 m, which is not explained yet. V1 will show whether it is a timing or frame issue.
- The match is weak in absolute terms. The best correlation is 0.12–0.37 per block. Going from no shift to the best shift raises it by about 0.04. Forest brightness adds texture that bare earth cannot predict. The agreement across three independent geometries is the strong evidence, not any single peak.
- Two readings fit and Stage 0 cannot tell them apart. (1) NASA's DEM sits about 9 m above the ground under trees. (2) The HH energy comes from inside the canopy, not the ground. Under (2), placing on bare earth would move canopy returns to the wrong spot. V2 separates them. It compares the measured shift with Copernicus minus lidar height, and runs `--surface dsm`.
- The DEM is NAD83(2011) and the GSLC is WGS84, about 1–1.5 m apart here. That is small next to 8–12 m.
- This replaces the earlier 10–15 m estimate from the canopy-cover match. The size is similar, and now it has a direction.

Outputs
- `data/9t/results/nisar/nisar_lidar_sim_match_shifts_9t.csv`
- `data/9t/results/nisar/nisar_lidar_sim_match_summary_9t.json`
- `data/9t/results/nisar/nisar_los_by_track_9t.json` (look and along-track vectors read from the radarGrid cubes)
- `data/9t/results/nisar/nisar_lidar_sim_match_run_9t.log`
- `data/9t/derived/nisar_gslc_5m/nisar_lidar_sim_t026_9t.tif`, `_t090_`, `_t162_` (gitignored). Bands: simulated brightness dB, shadow fraction, layover fraction.
- `data/9t/results/nisar/figures/nisar_lidar_sim_match_9t.png`. The palette is the lost/found set, reused as validated (`--pairs all`, worst pair ΔE 21.1 deutan). Tracks also differ by marker shape.

Notes for later stages
- A full radarGrid cube takes about 2.5 minutes to read remotely. Read only the cells over 9t. Stage 1's window step needs that.
- The cubes also hold `alongTrackUnitVectorX/Y`. Stage 0 used them for the azimuth direction.

## Stage 1. Fetch RSLC windows

Script `notebooks/wellsight_v2/s1_build/_fetch_nisar_rslc_window_9t.py`. It follows the existing `_fetch_nisar_gslc_window_9t.py` and reuses its `query`, `signed_url` and blockcache reader.

1. Query both RSLC collections over the 9t box.
2. Match each RSLC to the GSLC already chosen for that date and track. Match on date, track and frame, using `nisar_gslc_window_index_9t_5m.csv`. On track 026, use the frame the GSLC index kept.
3. Radar window:
   - Interpolate the matching GSLC's `radarGrid` cubes at the 9t corners plus a 200 m margin, at the lowest and highest 9t heights.
   - Take the min and max time and range, and convert them to rows and columns.
   - Pad by 64 samples on each side for the interpolator.
   - The expected size is about 1,500 x 1,700 samples, roughly 20 MB per polarization.
4. Save the HH and HV windows, the row and column offsets, and the time and range vectors for the window. Also save the Doppler table, the orbit, the timing-correction tables and the radarGrid cube subset over 9t. Copy every time and range unit attribute exactly.

Output
- `data/9t/derived/nisar_rslc_window/nisar_rslc_window_<yyyymmdd>_t<track><A|D>_9t.h5`. This folder gets a `.gitignore` line in the same change. About 41 x 40 MB = 1.7 GB.
- Index: `data/9t/derived/nisar_rslc_window/nisar_rslc_window_index_9t.csv`
- Run time: about 1 minute per date, the same as the GSLC fetch.

## Stage 2. Geometry library

File `notebooks/wellsight_v2/s1_build/_nisar_geometry.py`. Plain numpy and scipy, with no ISCE3, because ISCE3 does not run on Windows.

- `ellipsoid_height(dem_navd88, crs)`: NAVD88 to ellipsoid height through pyproj and the Geoid12B grid (`us_noaa_g2012bu0.tif`). This is the same geoid the LAS used. Also covers the NAD83(2011) to WGS84 horizontal step, about 1 m.
- `cube_to_radar(cube, x, y, h)`: interpolate time and range from the radarGrid cubes. Trilinear in x, y and h.
- `radar_index(t, r, window)`: map time and range to fractional RSLC row and column. Check that the cube's time epoch and the RSLC's time epoch are the same string, and fail if not.
- `sinc_interp(slc, row, col, fdc)`: 8-tap windowed sinc in each direction. The azimuth Doppler centroid is demodulated before interpolation and remodulated after. The Doppler table supplies `fdc`.
- `flatten(slc, r, wavelength)`: apply the same geometric phase removal NASA applied, using our range. The sign is fixed in check V1.
- `timing_corrections(t, r, tables)`: add the solid-earth-tide and ionosphere offsets. Check V1 decides whether NASA applied them inside geocoding.
- `layover_shadow(dem_1m, los)` and `rtc_area(dem_1m, los, window)`: area-projection terrain correction (Small 2011).
- Optional, for cross-checking only: `orbit_zero_doppler(x, y, h, orbit)`. This uses Hermite orbit interpolation and Newton iteration on (P − S(t)) · V(t) = 0. It is used in check C0, not in production.

## Stage 3. Re-place each date

Script `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py`

Options: `--heights copernicus` (for check V1), `--heights lidar` (production, the default) and `--surface dsm` (a sensitivity run).

For each date:
1. Output grid: the same 5 m EPSG:32617 grid as the existing GSLC window for that date. Downstream scripts then line up pixel for pixel.
2. Heights per output pixel:
   - lidar: the mean of the 25 bare-earth 1 m cells, converted to the ellipsoid.
   - copernicus: GLO-30 from the open AWS bucket, converted from EGM2008 to the ellipsoid.
   - Pixels in the 200 m margin outside the lidar tile take the Copernicus height and are flagged.
3. `cube_to_radar`, then `timing_corrections`, `radar_index`, `sinc_interp` and `flatten`.
4. Write HH and HV as complex64, like the GSLC windows.

Outputs, in `data/9t/derived/nisar_slc_lidar_5m/`, gitignored in the same change
- `nisar_slc_lidar_<yyyymmdd>_t<track><A|D>_9t.tif`: 2 bands, HH and HV, complex64. About 16 MB each.
- `nisar_slc_lidar_geometry_t<track>_9t.tif`, one per track: local incidence, layover/shadow mask, RTC area factor, the height used, and the shift against the GSLC in east and north metres.
- `nisar_slc_lidar_index_9t.csv`, plus `_PROVENANCE.json` with every parameter.

## Checks, in order. Each one must pass before the next.

**C0. Cube accuracy.**
- Compare trilinear with tricubic interpolation over 9t, and with the optional orbit solver at 20 points.
- Pass: range within 0.05 m and time within 1e-5 s (about 7 cm along track).

**V1. Reproduce NASA's GSLC.**
- Run with `--heights copernicus` on 3 dates, one per track, and compare with NASA's GSLC window for the same date.
- Pass:
  - the amplitude cross-correlation peak is within 0.1 pixel on both axes
  - the median 5 x 5 complex coherence between ours and theirs is above 0.9
  - the phase difference has a standard deviation under 0.3 rad
- This check finds every convention error: time epoch, range reference, Doppler, flattening sign, timing corrections. It is the slow part. Each failure is fixed by testing one convention at a time.
- If V1 cannot pass, stop. Do not use the lidar outputs.

**V2. Is the lidar shift physical?**
- Run with `--heights lidar`. Map the shift against the GSLC.
- Predicted shift = (Copernicus height − lidar height) / tan(incidence), along the look direction.
- Pass: regressing the measured shift on the predicted shift gives a slope of 0.9–1.1.
- The shift should also grow with lidar canopy height.

**V3. Does it match the ground better?**
- Rerun Stage 0's match on the new stack.
- Pass: the best shift is within ±2.5 m on every track and block, and the correlation is at least the GSLC's.
- Also rerun the canopy-cover registration check from `_nisar_gslc_stack_pad_pit_seasonal_9t.py`.

**Figure.** `data/9t/results/nisar/figures/nisar_slc_lidar_check_9t.png`
- Three sample chips side by side: NASA GSLC, ours, and the lidar hillshade.
- The V2 shift map. Its diverging ramp is checked with the dataviz validator using `--pairs all`.

## Known traps

1. **Vertical datum.** NAVD88 against the ellipsoid is about 34 m. Missing it gives a 32–43 m shift. V1 does not catch it because V1 uses Copernicus heights, so it gets its own unit test. Convert one known benchmark and compare with the NGS value.
2. **Time epochs** differ per file ("seconds since <date>T00:00:00"). Never mix two files' times without converting.
3. **Doppler.** Sinc interpolation of a complex image without demodulating the Doppler centroid lowers the coherence. V1 shows it.
4. **Flattening sign and reference.** It must match NASA's, or our interferograms will not match theirs. V1 fixes it.
5. **Which height.** HH ground-trunk double bounce sits at ground level, so bare earth is right for wells, pads and slopes. Volume scattering sits higher in the canopy. The `--surface dsm` run shows how much that matters.
6. **Two frames on track 026.** Use the same frame as the GSLC index.
7. **Beta against provisional.** The 12 beta granules used older software. Run V1 on one beta date too.
8. **Lidar edge.** The 200 m margin has no lidar. Those pixels are flagged and excluded from the tests.

## Found while planning: slope motion look direction was wrong

- `notebooks/wellsight_v2/s5_eval/_nisar_slope_motion_9t.py` (lines 155–157) and its write-up assumed the ascending radar is right-looking and looks east.
- NISAR is left-looking. Over 9t both ascending tracks look **west**, and the satellite sits to the east.
- So downslope creep on an **east-facing** slope moves toward the satellite. The measured result (east-facing +4.9 mm, west-facing −4.3 mm) **matches** creep, if positive means toward the satellite. The write-up said the opposite.
- That sign is still unconfirmed. Interpretation now hinges on it. It is in BACKLOG.
- Stage 2's `cube_to_radar` and the LOS cubes give the exact look vector per pixel. The slope script should use them instead of an assumed direction.

## Downstream after it passes

- Add a `source` switch (`gslc` or `lidar`) to `load_complex` in `notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py`. The steel, pad-change, slope-motion and bright-target scripts all load through it.
- Rerun the pit test (with the pad-ring bias fixed first), steel, pad change and bright targets. Compare with the GSLC results in one table.

## Order and effort

| Step | Work | Risk |
|---|---|---|
| Stage 0 | done 2026-10-09 | gate failed, go on |
| Stage 1 fetch | 1–2 hours, mostly download | low |
| Stage 2 library + C0 | half a session | low, the cubes do the hard part |
| Stage 3 + V1 | half to two sessions | **this is where conventions bite** |
| V2, V3, figure, docs | half a session | low |

The radarGrid cubes remove the orbit solver from the main path. That cuts the earlier "few days" to about two to three sessions in total, depending on V1.

## Literature to log in `literature/CITATIONS.md` when the code is written

- Small, D. (2011). Flattening gamma: radiometric terrain correction for SAR imagery. IEEE TGRS 49(8), 3081–3093. Used for the area-projection terrain correction and the simulated brightness.
- The NISAR L1 RSLC and L2 GSLC product specifications (JPL). Used for the field meanings, flattening and timing corrections. Exact document numbers to be confirmed at code time.
- A range-Doppler geocoding reference for the optional orbit cross-check, e.g. Bamler & Hartl (1998), Synthetic aperture radar interferometry, Inverse Problems 14, R1–R54. To be confirmed at code time.
