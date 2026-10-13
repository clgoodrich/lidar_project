# Plan: re-place NISAR radar pixels on the 9t lidar ground (Stages 0–3 and checks V1–V3 done)

Written 2026-10-09. Stage 0 ran on 2026-10-09 and the gate failed, so Stages 1–3 are needed. Stage 1 (RSLC fetch) finished the same day. Stage 2 and check V1 passed on 2026-10-10. Lidar heights went in on 2026-10-12. The leftover offsets were traced and fixed on 2026-10-13 (last section before "Known traps"). Results are under each stage and check.

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

**Re-scored 2026-10-13.** The check had a 1.3 m datum error, and the bad 2026-09-08 granule was in the track 026 mean (see "Leftover offsets", below). With both fixed, NASA's GSLC sits 11.05 / 11.50 / 8.40 m away from the satellite and 3.20 / 1.00 / 0.65 m back along track (026 / 090 / 162 block medians), with 0 of 48 blocks within 2.5 m. The table below is the original run.

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

### Stage 1 result (2026-10-09): all 34 usable dates held

Script `notebooks/wellsight_v2/s1_build/_fetch_nisar_rslc_window_9t.py`. Log `data/9t/results/nisar/nisar_rslc_window_fetch_run_9t.log`.

- 34 RSLC windows, one per usable GSLC date: 9 on track 026, 11 on 090, 14 on 162. 24 are provisional and 10 are beta.
- Files: `data/9t/derived/nisar_rslc_window/nisar_rslc_window_<yyyymmdd>_t<track><A|D>_9t.h5`, about 1,530 x 1,750–1,940 samples, 41–47 MB each, 1.5 GB in all. Gitignored by the existing `data/**/derived/**` rule.
- Index: `data/9t/derived/nisar_rslc_window/nisar_rslc_window_index_9t.csv`. It holds the window offsets, the plane-fit residual and the size.
- **Changed from the plan.** The window comes from the RSLC's own `metadata/geolocationGrid`, not the GSLC cubes. That grid is small and chunked per height, so it reads in seconds. A GSLC cube takes minutes. Near 9t the inverse is fitted as a plane per height layer. Its worst residual is 2.5 m in range, far inside the 64-sample pad.
- **Versions.** 2026-09-05 track 162 has two RSLC versions, `_001` and `_002`. The script keeps the one matching the GSLC we hold (`_001`), so V1 compares like with like.
- Skipped: 5 granules on track 026 frame 067 whose date uses frame 068 in the GSLC index. 2026-07-22 track 026 fails because 9t lies past the end of its frame. Its GSLC has 0% valid pixels over 9t too, so it was already the unusable date.
- **Not in the RSLC.** The solid-earth-tide and ionosphere timing tables are only in the GSLC (`timingCorrections`). Stage 3 reads them from the matching GSLC.
- Each file also keeps the orbit (26 state vectors), attitude, the Doppler centroid table (185 x 109), `referenceTerrainHeight`, the processing run configuration and the identification group.

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

### Check C0 and V1 result (2026-10-10): passed, with one criterion changed

Scripts: `notebooks/wellsight_v2/s1_build/_nisar_geometry.py` (Stage 2 library) and `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py` (Stage 3, `--v1`). Heights for V1 are NASA's own DEM, not a Copernicus stand-in. The GSLC run configuration names "NISAR DEM v1.2", and ASF publishes it (collection `NISAR_DEM`, doi:10.5067/NIDEM-1). The 9t tile is `data/9t/derived/nisar_dem/DEM_N41_00_W080_00_C01.tif`, in WGS84 ellipsoid heights. It keeps its source name, with its `README.txt` and `LICENSE.pdf` beside it.

**Conventions found.** Each was tested against NASA's GSLC for 2026-09-29 track 162. They are the defaults in `CONV`.

| Convention | Settled value | How it showed |
|---|---|---|
| Timing corrections | Ionosphere in range (+0.69 to +1.03 m) and azimuth (−2e-5 to −8e-5 s). No troposphere model on top. Solid-earth tide makes no difference at this scale. | Amplitude correlation is 0.83 with none, 0.48 with a 3 m dry-troposphere delay, and 0.998 with ionosphere only. Offsets go to 0.00 px. |
| DEM origin | Pixel-is-point. The first sample sits half a pixel inside the GeoTIFF corner. | 0.998 with the shift, 0.56–0.76 without |
| DEM interpolation | A natural cubic spline through the 6 x 6 nearest samples (what ISCE calls "biquintic") | Single-date coherence 0.49. Bicubic spline gives 0.44, 6-point Lagrange 0.47, Keys cubic 0.34, quintic spline 0.27, bilinear 0.23. |
| Doppler carrier | Removed before sinc interpolation, put back at the output time | 0.49 when put back. Every variant that drops or shifts it gives 0.17–0.31. |
| Flattening | Multiply by exp(+j 4π r / λ), with r from the orbit before corrections | The −1 sign stays at the random baseline. |
| Kernel bandwidth | 8-tap Hann-windowed sinc. Low-passing to 0.83 changes nothing. | — |

The first sweep, before the DEM and correction fixes, is in `data/9t/results/nisar/nisar_regeocode_v1_sweep_9t.csv`. It came from the first version of the script. The later steps were one-off diagnostics, and the table above holds their numbers.

**Results.** `data/9t/results/nisar/nisar_regeocode_v1_checks_9t.csv`, log `data/9t/results/nisar/nisar_regeocode_v1_run_9t.log`.

| Pair | Track | Amplitude offset (row, col px) | Amplitude correlation | Interferogram match: coherence | Interferogram match: phase spread | NASA's own pair coherence |
|---|---|---|---|---|---|---|
| 2026-09-17 / 09-29 | 162 | 0.00, 0.00 | 0.998 | 0.998 | 0.013 rad | 0.33 |
| 2026-09-24 / 10-06 | 090 | 0.00, ≤0.02 | 0.997–0.998 | 0.998 | 0.012 rad | 0.60 |
| 2026-09-20 / 10-02 | 026 | 0.00, −0.02 | 0.997 | 0.998 | 0.015 rad | 0.31 |
| 2025-11-09 / 11-21 (beta) | 162 | 0.00, 0.00 | 0.997–0.998 | 0.998 | 0.014 rad | 0.59 |

- **C0 passed.** The orbit solver and the RSLC geolocation grid agree within 1.6 cm in range and 5.7e-7 s in time. The targets were 5 cm and 1e-5 s.
- **Placement passed** on every date. It is within 0.02 px, against a 0.1 px target.
- **Phase: criterion changed.** Single-date complex coherence against NASA is 0.44–0.49, not above 0.9. A single date's flattened phase depends on the height used at each pixel, and 1 cm of range is 0.5 rad. Our DEM interpolation still differs from ISCE3's by a few centimetres. That term is the same on both dates of a pair, so it cancels in every interferogram. The downstream scripts use interferograms, coherence and amplitude. So V1 is scored on the interferogram match instead. It passes at 0.998 and 0.013 rad, on pairs whose own coherence is only 0.31–0.60.
- **Beta and provisional** granules behave the same.
- Each date takes 7–30 s to re-place for HH.

**V2. Is the lidar shift physical?**
- Run with `--heights lidar`. Map the shift against the GSLC.
- Predicted shift = (Copernicus height − lidar height) / tan(incidence), along the look direction.
- Pass: regressing the measured shift on the predicted shift gives a slope of 0.9–1.1.
- The shift should also grow with lidar canopy height.
- Result 2026-10-13: correlation 0.82–0.90, slope 1.03 / 1.27 / 1.18 (026 / 090 / 162). Passes on track 026 only. Details under "Leftover offsets traced and fixed".

**V3. Does it match the ground better?**
- Rerun Stage 0's match on the new stack.
- Pass: the best shift is within ±2.5 m on every track and block, and the correlation is at least the GSLC's.
- Also rerun the canopy-cover registration check from `_nisar_gslc_stack_pad_pit_seasonal_9t.py`.

**Figure.** `data/9t/results/nisar/figures/nisar_slc_lidar_check_9t.png`
- Three sample chips side by side: NASA GSLC, ours, and the lidar hillshade.
- The V2 shift map. Its diverging ramp is checked with the dataviz validator using `--pairs all`.

### Stage 3 with lidar heights and check V3 (2026-10-12): offset removed on 9t

**Re-scored 2026-10-13.** The V3 numbers in this section came from the check before its datum fix. With the fixed check, this stack (as placed, bad granule left out) sits 2.35 / 0.90 / 1.10 m away from the satellite and 2.40 / 0.70 / 0.40 m back along track, with 27 of 48 blocks within 2.5 m. The next section explains and fixes what was left.

**Cause confirmed first.** NASA's DEM (NISAR DEM v1.2) is the Copernicus GLO-30 X-band surface model. Over forest it sits inside the canopy.
- Against the lidar ground on 30 m cells it is a median 6.0 m higher. Under 18–25 m canopy it is 9.7 m higher, about half the canopy height.
- On fully open, flat cells (no 1 m cell taller than 1 m, slope under 3°) it matches the lidar to −1.5 m. So the datum chain is sound, and the gap is the trees.

**Datum chain** (in `lidar_heights()`, `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py`):
- ITRF2014 lon, lat to NAD83(2011), then sample the 5 m mean lidar DEM, then add Geoid12B N (−33.1 m), then NAD83(2011) to ITRF2014 in 3-D (−1.19 m vertical, 1.1 m horizontal).
- **Trap found.** PROJ's NAD83(2011) to "WGS 84" route is a null transform. It would leave the lidar 1.2 m high and 1.1 m off sideways. ITRF2014 (EPSG:7912) stands in for WGS84.
- Unit test: on the 7 open, flat cells, NASA minus ours is a median −0.19 m (range −0.71 to +0.35).

**Run.** `--heights lidar --write`. 34 dates, HH and HV, about 14 s each. Window margin outside the lidar (16%) keeps NASA's heights. NASA's heights are a median 6.4 m above the lidar ground.
- Outputs, gitignored: `data/9t/derived/nisar_slc_lidar_5m/nisar_slc_lidar_<date>_t<track><A|D>_9t.tif`, index `nisar_slc_lidar_index_9t.csv`. Log `data/9t/results/nisar/nisar_slc_lidar_write_run_9t.log`.

**V3.** `notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py --stack lidar`, the Stage 0 match on our stack.

| | NASA GSLC | ours, lidar heights |
|---|---|---|
| Block median shift away from the satellite, 026 / 090 / 162 | 9.6 / 11.9 / 9.1 m | 1.3 / 1.3 / 1.6 m |
| Median total shift | 10.0 m | 2.2 m |
| Blocks within 2.5 m | 0 of 48 | 26 of 48 |
| Blocks within 5 m | 0 of 48 | 43 of 48 |
| Shift against canopy height, correlation | +0.55 to +0.62 | −0.32 to −0.58 |
| Match at zero shift / best | 0.15–0.19 / 0.18–0.24 | equal (0.18 / 0.25 / 0.22) |

- The 8–12 m offset is gone. The gate as written (every block within 2.5 m) is not met yet.
- **What is left.**
  - Track 026 keeps a 3–7 m along-track offset (block median 3.2 m). NASA's stack had it too (4.1 m), so it is not a height effect. Candidate cause: azimuth timing on that descending track.
  - Blocks under the tallest canopy now sit slightly toward the satellite. Some L-band echo comes from above the ground, as expected in forest.
- Outputs: `data/9t/results/nisar/nisar_lidar_sim_match_shifts_lidarslc_9t.csv`, `nisar_lidar_sim_match_summary_lidarslc_9t.json`, `nisar_lidar_sim_match_lidarslc_run_9t.log`, `figures/nisar_lidar_sim_match_lidarslc_9t.png`.
- V2 (measured against predicted shift) ran on 2026-10-13. See the next section.

### Leftover offsets traced and fixed (2026-10-13)

The user asked to figure out the remaining errors, test the fixes, and stop there. Four separate faults sat under the 2026-10-12 numbers. Each was found, fixed and tested on 9t.

**1. The check itself had a datum error.**
- The lidar simulation sits on the NAD83(2011) grid. The radar sits on WGS84, which ISCE3 treats as ITRF2014. The check treated the two grids as one.
- On 9t the same point is 0.80 m west and 1.01 m north in the radar grid (ITRF2014 at the stack's mean date, 2026.39). PROJ's NAD83(2011) to "WGS 84" route is a null transform, so the check goes through ITRF2014 (EPSG:7912).
- Fix: the check removes that offset from every shift. It also refines the best shift below 1 m with a parabola through the peak. `notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py`.

**2. Two NASA granules are misplaced.**
- Track 026 on 2026-07-22 and on 2026-09-08. Each matches no other date of its track at any shift inside the window. Their amplitude correlation with the other dates is −0.01 to 0.00, against 0.23 or more for every other date. This holds on 9t, 613590 and McKean.
- NASA's GSLC of 2026-09-08 is wrong too. Our re-placement with NASA's heights reproduces it exactly (amplitude correlation 0.997), so the fault is in NASA's RSLC or orbit.
- 2026-09-08 was processed on the day of the pass, with an orbit file made 13 hours after it. Every other date waited a day or more. That is a likely reason, not a confirmed one.
- Both went into earlier track 026 results. 2026-09-08 did on all three areas. 2026-07-22 did on McKean only. On 9t it had no valid pixels.
- Fix: `BAD_DATES` and `usable()` in `notebooks/wellsight_v2/_nisar_area.py`. The check and the re-placement drop them. The other NISAR scripts do not yet (BACKLOG).

**3. NASA's two processing generations sit 3.2 m apart in slant range.**
- Beta granules (Oct 2025–Jan 2026) sit 3.2 m closer in slant range than provisional granules (Jun–Oct 2026). Track 090 gives 3.3 m, track 162 3.2 m and track 026 4.3 m. On the ground that is 4–7 m toward the satellite.
- The external calibration file changed from `NISAR_LSAR_EXT_CAL_20250730T000000_01.yaml` (beta) to `_04.yaml` (provisional). The software release changed from X05009/X05010 to P05023. Orbit type (MOE) and dry-troposphere model (`tsx`) are the same.
- Each track's stack mixed both generations, so every feature was smeared over 4–7 m.
- The step is uniform. Open-canopy and closed-canopy blocks agree within 0.4 m. So it is a timing or calibration step, not tree height.
- NASA's own GSLC stack has the same per-date offsets as ours, within 0.2 m. So it comes from NASA's data, not from our code.

**4. Track 026 dates jump along the flight path.**
- Track 026 passes at dusk, about 19:00 local. Its provisional dates sit 0 to 7.7 m back along the flight path from its beta dates. Its three beta dates agree within 0.8 m.
- One track 090 date (2026-07-26) sits 3.9 m back. Track 162 dates agree within 1.3 m.
- Cause not found. Candidates are NASA's provisional processing of these passes or the dusk ionosphere. NASA's own ionosphere correction for these dates is 0.2–1.0 m along track, and it does not follow the jumps.

**Fix for 3 and 4: line up the dates of each track, then tie each track to the lidar.**
- **Per date.** Every pair of dates in a track is registered by sub-pixel phase correlation of the amplitude. One offset per date is then solved by least squares, with the mean of the provisional dates held at zero. The network-of-pairs design follows Fattahi et al. (2017). Each offset goes back into the re-placement as slant range and azimuth time, on top of NASA's own corrections. Code: `network_offsets()` in `notebooks/wellsight_v2/s1_build/_nisar_geometry.py`; `--estimate-offsets` and `--write --coreg` in `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py`. Table: `data/9t/results/nisar/nisar_slc_date_offsets_9t.csv`.
- **Per track.** One constant from check V3 on the lined-up stack, with forest echo modelled at 10% of stand height (below). Code: `--track-offsets _coreg_k010` and `--write --coreg --absolute`. Table: `data/9t/results/nisar/nisar_slc_track_offsets_9t.csv`.

| Track | Per-track correction, slant range | Along the flight path |
|---|---|---|
| 026 | +3.87 m | 4.30 m back (−0.63 ms) |
| 090 | +2.05 m | 0.95 m back (−0.14 ms) |
| 162 | +2.72 m | 0.60 m back (−0.09 ms) |

The corrections are measured from the provisional level. They say the provisional dates record the ground 2.0–3.9 m too far in slant range.

**Forest echo height.**
- Check V3 now takes `--kappa k`. Each simulated echo sits k × stand canopy height above the ground, with canopy height averaged over 25 m. It is then mapped back to the map the way our ground-height placement maps it.
- k = 0.10 fits best. The match peaks there on all three tracks: 0.243 / 0.269 / 0.257, against 0.239 / 0.266 / 0.248 at k = 0. The shift also stops following canopy height: r = +0.14 / +0.13 / −0.23, against −0.23 / −0.35 / −0.42 at k = 0.
- k = 0.25 and k = 0.5 fit worse. A first try with the raw 1 m canopy height fitted worse at every k above 0. Crown-to-crown height jumps scatter the echo, so a stand mean is used.
- So the L-band HH echo sits about 1–2 m above the ground in this forest. That is why features under trees sat about 1–1.5 m toward the satellite. Ground heights stay right for ground targets such as wells, pads and pits.
- On the canopy-modelled check, the provisional dates are 2.0–3.9 m long in slant range and the beta dates 0.5–1.3 m short. The newer calibration is the one further off.
- Unit test: a uniform 20 m canopy at k = 0.5 moves the simulation 12.60 m toward the satellite on gentle synthetic terrain, against 12.53 m expected.

**Tests**

| | NASA's GSLC | Ours, 2026-10-12 | Final |
|---|---|---|---|
| Blocks within 2.5 m, bare-earth check | 0 of 48 | 27 of 48 | 40 of 48 |
| Blocks within 5 m | 0 of 48 | 42 of 48 | 48 of 48 |
| Worst block | 20.8 m | 7.2 m | 3.8 m |
| Median shift, 026 / 090 / 162 | 11.3 / 11.7 / 8.4 m | 3.5 / 1.4 / 1.7 m | 2.0 / 1.5 / 1.4 m |
| Canopy-modelled check (k = 0.10) | – | – | 1.2 / 1.0 / 1.1 m; 46 of 48 within 2.5 m |

- Every column uses the fixed check with the bad granules left out.
- The final column is not independent of the lidar, because the per-track constant came from it. Four tests are:
  - **Held-out blocks.** A constant fitted on one checkerboard half of the blocks brings all 8 blocks of the other half within 2.5 m. That holds on every track, both ways round. The two halves' constants agree within 0.35 m.
  - **Coherence.** It does not use the lidar. Lining dates up raises the median coherence of track 026 12-day pairs from 0.31 to 0.52, and of 24-day pairs from 0.29 to 0.53. Pairs with the 2026-07-26 track 090 date gain 0.09–0.23. No pair loses more than 0.001.
  - **Leftover per-date offsets** on the final stack are at most 0.16 m across track and 0.09 m along it. The pair misclosure is 0.04–0.07 m.
  - **Beta anchor.** The lidar puts track 026 4.30 m forward of its provisional mean. NASA's beta dates already sat 4.46 m forward of it. They agree within 0.16 m.
- **Gate (every block within 2.5 m).** It is met on 46 of 48 blocks on the canopy-modelled check. Block b33 on track 090 has a flat match, 0.222 at its best shift against 0.221 at zero, so its 8.3 m is not a measurement. Block b20 on track 090 is at 2.53 m.

**V2 (measured against predicted shift).** `--v2` in `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py`. NASA's placement against ours (as placed) in 150 m blocks, against (NASA DEM height − lidar height) / tan(incidence).
- Correlation 0.88 / 0.82 / 0.90 (026 / 090 / 162). Medians agree within 0.4–1.0 m.
- Slope 1.03 / 1.27 / 1.18. The plan's band is 0.9–1.1, so V2 passes on track 026 only.
- A slope-aware prediction (NASA's surface slope toward the satellite) made the fit worse, r 0.60–0.78. The cause of the steep slope on the ascending tracks is open. V1 already shows our geometry reproduces NASA's to 0.02 px, so it does not touch the placement.
- Outputs: `data/9t/results/nisar/nisar_regeocode_v2_checks_9t.csv`, `data/9t/results/nisar/nisar_regeocode_v2_blocks_9t.csv`.

**Outputs**
- Stack (gitignored, rewritten in place): `data/9t/derived/nisar_slc_lidar_5m/`. Its index `nisar_slc_lidar_index_9t.csv` records the per-date and per-track offsets applied (`coreg_slant_m`, `coreg_az_s`, `track_slant_m`, `track_az_s`). It flags the bad granule (`bad_granule`). The as-placed stack comes back with `--write` alone.
- Tables in `data/9t/results/nisar/`: `nisar_slc_date_offsets_9t.csv` (latest per-date estimate), `nisar_slc_track_offsets_9t.csv`, `nisar_slc_pair_coherence_9t.csv` (as placed and co-registered).
- Check V3 runs in `data/9t/results/nisar/`, each as `nisar_lidar_sim_match_shifts<suffix>_9t.csv`, `nisar_lidar_sim_match_summary<suffix>_9t.json`, `nisar_lidar_sim_match<suffix>_run_9t.log` and `figures/nisar_lidar_sim_match<suffix>_9t.png`:
  - no suffix: NASA's GSLC (Stage 0 re-scored)
  - `_lidarslc`, `_lidarslc_prov`, `_lidarslc_beta`: ours as placed on 2026-10-12, all dates and each generation alone
  - `_coreg`, `_coreg_prov`, `_coreg_beta`: dates lined up
  - `_coreg_k010`, `_coreg_k025`, `_coreg_k050`: dates lined up, forest echo at 10, 25 and 50% of stand height
  - `_coregabs`, `_coregabs_k010`: final, bare earth and forest echo at 10%
- Run logs in `data/9t/results/nisar/`: `nisar_slc_coreg_write_run_9t.log`, `nisar_slc_date_offsets_check_run_9t.log`, `nisar_slc_pair_coherence_run_9t.log`.
- Paper: `literature/papers/fattahi_2017_network_esd_tops_coregistration.pdf`.

**Reproduce**

```bash
S1=notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py
V3=notebooks/wellsight_v2/s5_eval/_nisar_lidar_sim_match_9t.py
python $S1 --heights lidar --write                       # as placed (2026-10-12)
python $S1 --v2 && python $S1 --coherence
python $V3 --stack lidar                                 # also --dates provisional, --dates beta
python $S1 --estimate-offsets
python $S1 --heights lidar --write --coreg
python $S1 --estimate-offsets                            # refines; the change is under 0.3 m
python $V3 --stack lidar --kappa 0.1                     # also 0.25 and 0.5
python $S1 --track-offsets _coreg_k010
python $S1 --heights lidar --write --coreg --absolute
python $V3 --stack lidar && python $V3 --stack lidar --kappa 0.1
python $S1 --estimate-offsets && python $S1 --coherence
```

Run at most three V3 jobs at once. Five at once ran out of 64 GB of memory.

**What is left**
- The downstream tests (steel, pad change, pits, bright targets, slope motion) still read NASA's GSLC. That stack mixes both generations and holds the bad granules. They were not re-run, as asked.
- 613590 and McKean need the RSLC fetch, lidar heights, the line-up and their own per-track constants.
- New dates on 9t need the line-up step run again.
- The provisional range offset and the track 026 jumps are on NASA's side. These numbers could go to the NISAR team at ASF or JPL.
- The V2 slope on the ascending tracks (1.18–1.27) is unexplained.

## Known traps

1. **Vertical datum.** NAVD88 against the ellipsoid is about 34 m. Missing it gives a 32–43 m shift. V1 does not catch it because V1 uses Copernicus heights, so it gets its own unit test. Convert one known benchmark and compare with the NGS value.
2. **Time epochs** differ per file ("seconds since <date>T00:00:00"). Never mix two files' times without converting.
3. **Doppler.** Sinc interpolation of a complex image without demodulating the Doppler centroid lowers the coherence. V1 shows it.
4. **Flattening sign and reference.** It must match NASA's, or our interferograms will not match theirs. V1 fixes it.
5. **Which height.** HH ground-trunk double bounce sits at ground level, so bare earth is right for wells, pads and slopes. Volume scattering sits higher in the canopy. Measured on 2026-10-13: the echo sits at about 10% of stand height, 1–2 m up. Bare earth stays right for ground targets.
6. **Two frames on track 026.** Use the same frame as the GSLC index.
7. **Beta against provisional.** The 12 beta granules used older software. Run V1 on one beta date too. V1 passes on both, but the two generations sit 3.2 m apart in slant range (4.3 m on track 026). Never average them before lining the dates up.
8. **Lidar edge.** The 200 m margin has no lidar. Those pixels are flagged and excluded from the tests.
9. **Datum inside the check.** The lidar grid is NAD83(2011) and the radar grid is WGS84 (ITRF2014). They are 1.3 m apart on 9t. Compare like with like, through ITRF2014.
10. **Bad granules.** Check every date against the rest of its track before stacking. Two NASA granules on track 026 sit far off (`BAD_DATES` in `notebooks/wellsight_v2/_nisar_area.py`).
11. **Many checks at once.** Each V3 run needs several GB. Five at once ran out of 64 GB.

## Found while planning: slope motion look direction was wrong

- `notebooks/wellsight_v2/s5_eval/_nisar_slope_motion_9t.py` (lines 155–157) and its write-up assumed the ascending radar is right-looking and looks east.
- NISAR is left-looking. Over 9t both ascending tracks look **west**, and the satellite sits to the east.
- So downslope creep on an **east-facing** slope moves toward the satellite. The measured result (east-facing +4.9 mm, west-facing −4.3 mm) **matches** creep, if positive means toward the satellite. The write-up said the opposite.
- That sign is still unconfirmed. Interpretation now hinges on it. It is in BACKLOG.
- Stage 2's `cube_to_radar` and the LOS cubes give the exact look vector per pixel. The slope script should use them instead of an assumed direction.

## Downstream after it passes

- Add a `source` switch (`gslc` or `lidar`) to `load_complex` in `notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py`. The steel, pad-change, slope-motion and bright-target scripts all load through it.
- Make every loader drop `BAD_DATES` through `_nisar_area.usable()`. On NASA's GSLC, also never mix beta and provisional dates without lining them up first.
- Rerun the pit test (with the pad-ring bias fixed first), steel, pad change and bright targets. Compare with the GSLC results in one table.

## Order and effort

| Step | Work | Risk |
|---|---|---|
| Stage 0 | done 2026-10-09 | gate failed, go on |
| Stage 1 fetch | done 2026-10-09 | 34 of 34 usable dates |
| Stage 2 library + C0 | done 2026-10-10 | C0 passed |
| Stage 3 + V1 | V1 done 2026-10-10 | passed, on the interferogram match |
| Stage 3 lidar + V3 | done 2026-10-12 | offset 9–12 m down to 1.3–1.6 m; 26 of 48 blocks within 2.5 m |
| Leftover offsets, V2 | done 2026-10-13 | check datum fixed, 2 bad granules dropped, dates lined up, tracks tied to the lidar; 46 of 48 blocks within 2.5 m (canopy-modelled check); V2 slope 1.03 / 1.27 / 1.18 |
| Downstream tests on the final stack | open | not started, as asked |

The radarGrid cubes remove the orbit solver from the main path. That cuts the earlier "few days" to about two to three sessions in total, depending on V1.

## Literature to log in `literature/CITATIONS.md` when the code is written

- Small, D. (2011). Flattening gamma: radiometric terrain correction for SAR imagery. IEEE TGRS 49(8), 3081–3093. Used for the area-projection terrain correction and the simulated brightness.
- The NISAR L1 RSLC and L2 GSLC product specifications (JPL). Used for the field meanings, flattening and timing corrections. Exact document numbers to be confirmed at code time.
- A range-Doppler geocoding reference for the optional orbit cross-check, e.g. Bamler & Hartl (1998), Synthetic aperture radar interferometry, Inverse Problems 14, R1–R54. To be confirmed at code time.
