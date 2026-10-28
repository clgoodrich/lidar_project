# Leaf-on, leaf-off and snow dates against the NISAR acquisitions, 9t

## Goal
Find the NISAR dates when trees are bare and the ground is not snow-covered, so the radar can be split into leaf-off and leaf-on stacks. Nothing has been scored with the split yet.

## Inputs
- **Snow and weather.** NOAA GHCN-Daily, station USC00368873 (Tionesta 2 SE Lake, 4.9 km from the tile). Daily snowfall, snow depth, precipitation, tmax and tmin, 2025-09-01 to 2026-10-20. Downloaded from the NCEI Data Service (`daily-summaries`). Thirteen other nearby stations (Titusville, Franklin, CoCoRaHS sites) are in the same file.
- **Leaf state.** Sentinel-2 L2A NDVI (Element 84 Earth Search STAC, tile 17TPG), median over 2,684 closed-forest 10 m cells (lidar cover above 0.95 and mean canopy height above 12 m) in a 2 km box. Cloud, shadow, snow and no-data masked. A scene needs 30% valid cells.
- **PRISM** daily weather already in `data/9t/derived/weather/weather_prism_daily_9t.csv` (rain, tmin, tmax). No snow.

## Method
Rolling median of three scenes, scaled between the winter low (0.268) and summer high (0.902). Leaf-off below 0.35 of the range, leaf-on above 0.65, transition between. Linear interpolation to each NISAR date.

## Results
**Season at 9t.** NDVI of closed forest falls from 0.68 on 2025-10-16 to 0.54 on 10-29. It is at its winter low in Feb to Apr (0.15 to 0.42). It climbs from 0.42 on 04-17 to 0.82 on 05-27, stays near 0.88 to 0.90 through summer and starts falling again in October (0.76 on 10-07, 0.68 on 10-17).

**Snow at Tionesta.** Snow on the ground (depth above 0): Nov 4 days, Dec 17, Jan 22, Feb 18, Mar 1, none after. Peak depth 330 mm in February.

**NISAR dates, November to January** (all 9t and 613590 tracks):

| Date | Track | Leaf state | Snow depth mm | Note |
|---|---|---|---|---|
| 2025-11-04 | 90 | transition | 0 | |
| 2025-11-09 | 162 | transition | 0 | |
| 2025-11-12 | 26 | transition | 0 | 191 mm snowfall in prior 3 days |
| 2025-11-21 | 162 | leaf-off | 0 | clean |
| 2025-12-03 | 162 | leaf-off | 102 | snow |
| 2025-12-18 | 26 | leaf-off | 0 | 51 mm snowfall in prior 3 days |
| 2025-12-30 | 26 | leaf-off | 51 | snow |
| 2026-01-08 | 162 | leaf-off | missing | depth missing at Tionesta |
| 2026-01-15 | 90 | leaf-off | 25 | snow |
| 2026-01-20 | 162 | leaf-off | 76 | snow |

- Leaf-off dates with no snow on the ground: 2025-11-21 (track 162), 2025-12-18 (track 26, wet after snow) and 2026-01-08 (track 162, depth unknown). Track 90 has none.
- No 9t NISAR date falls between 2026-01-20 and 2026-06-20, so there is no early-spring bare-tree date, as there is in the Google image (April).
- All remaining dates (2026-06-20 to 2026-10-14) are leaf-on, apart from some transition in mid-October.

## Cautions
- No clear Sentinel-2 view between 2025-10-29 and 2026-02-01. The leaf state in that window is a straight-line interpolation. The Nov and Dec leaf-off calls are therefore weak.
- The Feb to Apr NDVI values are noisy (snow edges, clouds). Two mid-July scenes (0.57, 0.49) are probably haze or shadow.
- One station. Snow can differ over the tile and with elevation. 01-08 is missing at the nearest station.
- Closed forest here includes some conifers, which keep NDVI above zero in winter.
- No score was run on the split yet.

## Files
- Script: `notebooks/wellsight_v2/s5_eval/_nisar_leaf_state_9t.py`
- `data/9t/derived/weather/noaa_ghcn_daily_near_9t.csv` (14 stations)
- `data/9t/derived/weather/noaa_snow_at_nisar_dates_9t.csv`
- `data/9t/derived/weather/leaf_state_ndvi_curve_9t.csv`
- `data/9t/derived/weather/nisar_dates_leaf_and_snow_9t.csv`
