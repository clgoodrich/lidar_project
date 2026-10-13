# NISAR GSLC tests on 613590 and McKean

**Date:** 2026-10-12
**Status:** done. All 9t NISAR tests were re-run on two more areas. The 9t pad result holds in McKean. The well and pit results do not hold up as signals.
**Follows:** `docs/iterations/nisar_wells_steel_pads_slopes_9t.md`, `nisar_gslc_stack_pad_pit_seasonal_9t.md`, `nisar_gslc_interferogram_pits_9t.md`, and Stage 0 in `nisar_regeocode_plan_9t.md`. The user asked for "the nisar analysis for the 613590 and the mckean region".

All results use NASA's placement of the pixels. Stage 0 found that placement 8–12 m off on 9t. This doc finds it off on both new areas too.

**Found on 2026-10-13, not re-run here** (details in `docs/iterations/nisar_regeocode_plan_9t.md`, "Leftover offsets traced and fixed"):
- Two NASA granules on track 026 are misplaced by more than the window. 2026-09-08 sits in the track 026 results of both areas. 2026-07-22 sits in McKean's.
- NASA's beta dates (Oct 2025–Jan 2026) and provisional dates (Jun–Oct 2026) sit 3.2 m apart in slant range, 4–7 m on the ground. Every stack here mixes both.
- So the multi-date results below are smeared by 4–7 m on top of the placement offset. They stand as recorded and need a re-run on corrected stacks.

## Areas

| | 9t (reference) | 613590 | McKean (mkf) |
|---|---|---|---|
| Window | 4.9 km square | 4.9 km square | 10.4 km square |
| Lidar | Venango D20 QL2 | Venango D20 QL2 | PA_Northcentral_2019_B19 QL1, 59 tiles |
| Lidar cover of the window | full | full | 58% |
| Usable dates, track 026 / 090 / 098 / 162 | 9 / 11 / – / 14 | 9 / 11 / – / 6 | 10 / 0 / 9 / 14 |
| DEP wells in window | 1,072 | 812 | 4,549 |
| Annotated pads / pits | 647 / 506 | 0 / 36 | 345 / 181 |

- A date is usable when at least half its window is valid. Track 162 mostly misses 613590, with 8 of 14 windows empty. Track 090 misses McKean entirely, with 6 of 6 empty.
- Track 098 covers McKean only. NASA delivers it in UTM 18 (EPSG:32618).
- McKean wells come from the statewide DEP export of the same date: `data/_source/reference/dep_wells/oil_gas_locations.gpkg`. Venango areas keep `venango_wells_all.gpkg`.
- McKean pads are annotated in two clusters only (see the HH panel of the stack figure). Decoys elsewhere may sit on pads nobody outlined. That would push pad and decoy scores together.

## What was built

- **Area switch.** `notebooks/wellsight_v2/_nisar_area.py`. Every NISAR script takes `--area 9t|613590|mkf`. Output names carry the area tag. 9t output names are unchanged.
- **McKean lidar.** DEM, DSM, CHM and hillshade built from the 59 USGS tiles with `notebooks/wellsight_v2/s1_build/_build_derivatives.py`. Outputs are in `data/mckean/mkf/derived/1m/`. The build's 20 GB merged point file filled drive C:. It was deleted with the user's OK. `tpi_grad_mag` was never written.
- **GSLC fetch.** `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py`.
  - Track 098 is read in UTM 18 and moved onto the 5 m UTM 17 grid by nearest neighbour. Nearest keeps each complex value whole, so phase is never mixed. Every 098 date takes the same warp, so 098 interferograms pair pixels exactly. Checked: the warped file has the same CRS, shape and bounds as track 162.
  - Remote reads now time out (120 s per read, 600 s per file). Two runs hung for 25 minutes without it.
- **Fixes found by the new areas.**
  - Stack: seasonal rasters stay as delivered even when a track's statistics use a lidar shift. 9t never had a shift applied, so it never hit this.
  - Stack figure: maps a track that has a leaf-on mean.
  - Slope motion: stops with a message when track 090 or 162 has no summer pairs.
  - Lidar match: uses only tracks with usable windows, skips blocks with no lidar, and reads track 098's look vectors in UTM 18, turned by 4.0° to UTM 17 grid north.
  - Pad change: reads the `pad` column by name. `ev.pad` is a pandas method.

## Results

### Placement against the lidar (Stage 0 check)

Block median shift of radar features away from the satellite, metres.

| Track | 9t | 613590 | McKean |
|---|---|---|---|
| 026 | 9.6 | 9.7 | 12.5 |
| 090 | 11.9 | 10.8 | – |
| 098 | – | – | 18.8 |
| 162 | 9.1 | 9.4 | 14.2 |
| Blocks within 2.5 m | 0 of 48 | 0 of 48 | 3 of 157 |

- The offset is real on all three areas and all four tracks. It is always away from the satellite.
- McKean's offset is larger. Converted with tan(incidence), it is a 12–13 m height error against 8–10 m on 9t.
- In McKean the shift grows with block canopy height (correlation 0.19 / 0.34 / 0.64 on 026 / 098 / 162). The Allegheny forest is taller than Venango's. This fits NASA's heights or the scattering sitting in the canopy, not on the ground.

### Steel at wells

Share of wells with a steady bright target within 15 m, against same-canopy decoys 150–600 m away.

| Status | 9t wells / decoys | 613590 wells / decoys | McKean wells / decoys |
|---|---|---|---|
| active | 1.3% / 1.0% | 4.6% / 4.2% | 4.0% / 6.7% |
| plugged | 1.1% / 0.5% | 4.4% / 6.1% | 5.2% / 5.3% |
| abandoned | 1.7% / 0.3% (p 0.063) | 6.1% / 4.4% (p 0.21) | 5.8% / 3.9% (p 0.017) |
| not drilled | 0% / 2.0% | 5.0% / 4.0% | 4.1% / 5.2% |

- No usable well signal in either new area.
- Abandoned wells sit above their decoys in all three areas. Only McKean passes p < 0.05, and that is one of 12 tests. Taken as a candidate pattern only. It needs a test fixed in advance on fresh data.
- Hit rates are higher on 613590 and McKean than on 9t, at wells and decoys alike. Fewer dates make D_A look steadier by chance. Track 162 on 613590 has 6 dates and gives 1,348 target pixels, while track 026 has 9 dates and gives 25.

### Bright targets

| | 9t | 613590 | McKean |
|---|---|---|---|
| Targets | 331 | 1,305 | 5,236 |
| Seen on 2+ tracks | 8 | 74 | 382 |
| Share at a well / random spots at a well | 4.9% / 3.8% | 3.7% / 3.0% | 5.3% / 7.0% |

Bright targets fall at wells, pads and roads about as often as random spots do. They are candidate metal, not well locations.

### Pads and pits, seasonal brightness (stack)

Median pad or pit minus its decoy, each against its own ring, dB.

- **Pads are darker than decoys in McKean, as on 9t.** HV winter −0.33 dB (95% CI −0.55 to −0.17), HV leaf-on −0.18 dB, AUC 0.41–0.44. 9t gave −0.1 to −0.28 dB. This is the one result that holds across areas. 613590 has no pads.
- **Pits.** McKean pits are brighter in HV leaf-off fall, +0.46 dB (CI 0.25–0.73, AUC 0.59). 9t pits are brighter in HH leaf-off fall, +0.18 dB. 613590 has 36 pits and nothing clears noise. The two areas disagree on polarization, and track 026 on McKean was shifted 5 m onto the lidar. Treat it as a lead, not a signal.

### Pits, interferometric coherence

| | 9t | 613590 | McKean |
|---|---|---|---|
| Pits / pairs | 506 / 21 | 36 / 17 | 181 / 25 |
| HH coherence, pit minus ring | 0.000 | −0.006 | +0.009 (CI 0.001–0.014) |

Null on 9t and 613590. McKean's excess is too small to use at 5 m.

### Pad change (coherence loss on pads)

| | 9t | McKean |
|---|---|---|
| Snow-free events / expected from decoys | 143 / 124 (p 0.045) | 72 / 73 (p 0.57) |

The faint 9t excess does not repeat in McKean.

### Slope motion

Could not run on either new area. The test compares tracks 090 and 162. 613590 has no summer pairs on 162. McKean has no usable 090 windows. A version comparing 162 against 098 would work in McKean. Added to BACKLOG.

## Outputs

Per area, with `<area>` = `613590` or `mkf`, `<dir>` = `data/613590` or `data/mckean/mkf`:

- Windows: `<dir>/derived/nisar_gslc_5m/nisar_gslc_hh_hv_complex_<date>_t<track><A|D>_<area>_5m.tif` and `nisar_gslc_window_index_<area>_5m.csv`. Gitignored.
- Seasonal rasters, bright-target layers and lidar sims: `<dir>/derived/nisar_gslc_5m/`. Gitignored.
- Results: `<dir>/results/nisar/`
  - `nisar_steel_wells_<area>.gpkg`, `nisar_steel_by_status_<area>.csv`, `nisar_steel_by_canopy_<area>.csv`, `nisar_steel_summary_<area>.json`
  - `nisar_bright_targets_points_<area>.gpkg`, `nisar_bright_targets_summary_<area>.json`
  - `nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_<area>_5m.csv/.json` and per-feature CSVs
  - `nisar_gslc_interferogram_pits_vs_decoys_win3_<area>_5m_summary.json`, `_by_pair.csv`, `_per_pit_per_pair.csv`
  - `nisar_lidar_sim_match_shifts_<area>.csv`, `nisar_lidar_sim_match_summary_<area>.json`, `nisar_los_by_track_<area>.json`
  - McKean only: `nisar_pad_change_by_season_mkf.csv`, `nisar_pad_change_per_pair_mkf.csv`, `nisar_pad_change_events_mkf.gpkg`, `nisar_pad_change_summary_mkf.json`
  - Run logs: `nisar_gslc_window_fetch_run_<area>.log`, `nisar_analysis_run_<area>.log`
- Figures: `<dir>/results/nisar/figures/`. Stack, interferogram, steel and lidar-match figures for both areas. Pad-change figures for McKean.

## Reproduce

```bash
for a in 613590 mkf; do
  python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py --area $a
  for s in _nisar_gslc_stack_pad_pit_seasonal_9t _nisar_gslc_interferogram_pits_9t _nisar_steel_9t \
           _nisar_bright_targets_9t _nisar_pad_change_9t _nisar_slope_motion_9t _nisar_lidar_sim_match_9t; do
    python notebooks/wellsight_v2/s5_eval/$s.py --area $a
  done
done
```

Pad change needs annotated pads, so skip it for 613590. McKean also needs the 1 m DEM and CHM first:

```bash
python notebooks/wellsight_v2/s1_build/_build_derivatives.py ... --suffix mkf_1m --out-dir <absolute path to data/mckean/mkf/derived/1m>
```

The build merges all tiles into one 20 GB file first. Check free disk space before running it. The already merged `F:/lidar_project/consolidated/lidar_all/mckean_full.las` (EPSG:6346) would avoid that step.
