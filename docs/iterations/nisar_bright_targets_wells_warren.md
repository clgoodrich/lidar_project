# NISAR steady bright targets over Warren, scored against DEP wells

## Goal
Run the 9t bright-target test on the Warren lidar swath. Ask whether DEP wells sit on steady bright radar targets more often than chance.

## Inputs
- NISAR L2 GSLC (beta and provisional), L-band, HH. Pulled as a window from the ASF cloud by `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py --area warren`.
- 49 windows: track 26 descending (11 dates), track 90 ascending (23), track 162 ascending (15). Dates run 2025-10-28 to 2026-10-18.
- Windows: `data/warren/derived/nisar_gslc_5m/` (5 m, complex, ignored by git).
- Warren 1 m CHM from `data/warren/derived/1m/full/chm_warren_1m.tif` (canopy cover).
- DEP wells: statewide export `data/_source/reference/dep_wells/oil_gas_locations.gpkg` (2026-04).

## Method
- Same steady-bright-target rule as 9t. Amplitude dispersion D_A < 0.25 and at least 6 dB above the 250 m median, per track.
- Tracks merged within 15 m. A well "has a target" if one lies within 15 m.
- Chance: 20,000 random valid pixels. Split by canopy cover (open below 0.30) so open wells are compared with open ground.
- Fisher exact test on the share with a target.
- Track 26 dates 2026-07-22 and 2026-09-08 dropped (same bad granules as 9t). The 2026-09-08 window is entirely empty at Warren.
- Warren has no annotated pads or roads, so context is wells only.

## Results
`data/warren/results/nisar/nisar_bright_targets_summary_warren.json`

| Group | Wells | With target | Random | Odds ratio | p |
|---|---|---|---|---|---|
| All | 684 | 3.9% | 5.2% | 0.75 | 0.16 |
| Open ground | 318 | 6.0% | 5.1% | 1.19 | 0.44 |
| Under canopy | 366 | 2.2% | 5.3% | 0.40 | 0.006 |

- 1,423 targets. 1,161 on one track, 238 on two, 24 on three.
- 262 targets repeat on two or more tracks. None is within 15 m of a well.
- Active wells 3.7% (570), plugged 1.8% (57).

## Interpretation
Wells are not on steady bright targets more often than chance. This matches 9t. Wells under canopy have fewer targets than random canopy ground. A DEP position error of tens of metres would blur any effect. There is no pumpjack truth, so this does not test pumpjacks directly.

## Not done
- No snapping of DEP wells to lidar features (no annotations at Warren).
- Tracks are not co-registered to the lidar. No shift search.

## Reproduce
```
python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py --area warren
python notebooks/wellsight_v2/s5_eval/_nisar_bright_targets_wells_warren.py --area warren
```
