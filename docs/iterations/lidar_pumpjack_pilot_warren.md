# Pumpjack search in 2019 lidar: pilot and first test (Warren/Sheffield, 9t)

**Date:** 2026-10-22
**Scripts:** `notebooks/wellsight_v2/s5_eval/_lidar_pumpjack_pilot_warren.py` (contact sheets), `notebooks/wellsight_v2/s5_eval/_lidar_pumpjack_metrics_warren.py` (test)

## Goal
Find out whether a pumpjack or tank shows in raw lidar points as a compact object 2 to 7 m above ground with intensity above canopy.

## Inputs
- Lidar: USGS 3DEP `PA_WesternPA_2019_D20`, 7 tiles at `data/_source/lidar/warren_sheffield/` (about 4.8 points per m2). CRS is not in the headers. EPSG:26917 is assumed from the tile names, and the tile bounds convert to Sheffield, Warren County.
- 9t raw tiles: `H:\lidar_project_data_DO_NOT_DELETE\data\source_laz\westernpa\` (nine tiles, 17TPF619593 to 17TPF622596).
- Wells: DEP live layer `OilGas_Collector/OG_Layers_OG_Well_Data/MapServer/0`, queried by swath envelope. Active OIL or COMB. OIL&GAS, spud 1980 to 2015 (so standing in 2019). The 1,000-record cap was hit for the 9t block only.
- The product has no building class, so town cannot be filtered.

## Method
Per point, a 120 m box. Height above ground from class-2 ground by linear interpolation. Compact object: 8-neighbour group of 6 to 120 one-metre cells holding returns 2 to 7 m up and no return above 8 m. Bright: object median intensity at least 2x the median of returns above 8 m.
Test: 100 wells against 100 controls. Fisher exact on the share with a bright compact object within 40 m, Mann-Whitney on the brightest object's ratio.

## Results
- Pilot contact sheets, 8 wells each. Warren: one pad (123-45801) with objects about 6x canopy intensity. 9t: forest hides the pads, and one object (121-44015) sits about 25 m from the DEP point and about 60 m from the nearest annotated pad.
- Test, controls uniform at random: wells 37%, controls 57%, p 0.007. Controls fell in Warren town.
- Test, controls 150 to 400 m from a random well (same setting): wells 37%, controls 53%, odds ratio 0.52, p 0.033. Median brightest ratio 1.74 (wells) and 2.35 (controls), p 0.013.

## Interpretation
The metric does not find wells. More than half of the controls have a bright compact object, so the 2x rule is not specific. Wells score lower, plausibly because a pad is cleared ground with less brush. Pumpjack detection by intensity alone is not supported. It is not ruled out: DEP positions are tens of metres off, there is no pumpjack ground truth, and intensity is raw (not normalised for scan angle or range).

## Not done
Intensity normalisation, a shape rule (height 3 to 6 m, length 5 to 10 m), and any test with pumpjack truth.

## Reproduce
Save the DEP envelope query as JSON, then run the metrics script with that file. Outputs in `data/warren/results/pumpjack/`. Pilot clips are gitignored.
