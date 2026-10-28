# Steady bright radar targets, checked on lidar hillshade and Sentinel-2

## Goal
Find out what the strongest steady bright NISAR targets are. Targets come from the earlier whole-area runs (`nisar_bright_targets_*`) in 9t, 613590, Warren and McKean (mkf).

## Inputs
- Targets: `nisar_bright_targets_points_9t_slc.gpkg`, `..._613590_slc.gpkg`, `..._warren.gpkg`, `..._mkf.gpkg`. Same rule everywhere (amplitude dispersion under 0.25, 6 dB above a 250 m background, merge 15 m).
- Lidar hillshade, 1 m, from each area's `derived/1m/` folder.
- Sentinel-2 L2A, 10 m, Element 84 Earth Search STAC. The clearest scene from June to September 2026 that covers each target (all 2026-06-03).

## Selection
- Every target seen on all three tracks: 9t 9, 613590 30, Warren 24, McKean 2.
- McKean has only two, so the ten brightest two-track targets inside the lidar tile were added.

## Method
A 400 m chip around each target. Left is the lidar hillshade, right is Sentinel-2 true colour. The ring is 15 m wide. Each target carries its tracks, brightness, canopy cover, distance to the nearest DEP well and the earlier context label.

## Outputs
Sheets (12 targets each), one folder per area:
- `data/9t/results/nisar/nisar_bright_chips_p1_9t.png`
- `data/613590/results/nisar/nisar_bright_chips_p1_613590.png`, `_p2_`, `_p3_`
- `data/warren/results/nisar/nisar_bright_chips_p1_warren.png`, `_p2_`
- `data/mckean/mkf/results/nisar/nisar_bright_chips_p1_mkf.png`

Target tables: `nisar_bright_chips_targets_<area>.csv` in the same folders.

## Results (read by eye)
- **Mostly buildings and towns.** 613590 and Warren targets sit on river towns, an industrial site with a pond, bridges and riverbanks. McKean's two-track targets are towns and large graded industrial pads with bright roofs.
- **9t is the only area with pad-like targets.** Targets 3, 4 and 5 sit on one bare, graded pad with a road, well within 22 to 47 m. The earlier context label called them "elsewhere", because no annotated pad polygon covers them. Target 2 is a small bare clearing with a berm. Target 9 is on a forest road. Targets 1 and 7 are a village outside the lidar tile.
- **McKean target 1** is 6 m from a DEP well. It is outside the lidar tile and sits on a facility with rectangular lots and tanks, not a lone well.
- **Distance to wells.** Median distance to the nearest DEP well is 47 m (9t), 33 m (McKean), 298 m (613590) and 297 m (Warren). Only 9t and McKean have targets near wells, and in both the targets are on graded pads or facilities.
- **Not wells.** None of the 75 chips shows a lone well or pumpjack as the target.

## Not settled
- Sentinel-2 at 10 m cannot show a tank or a pumpjack. Pad-scale features only.
- Several chips fall at the lidar edge or outside it (9t 2, 613590 4, Warren 4, McKean 1), so no hillshade exists there.
- This is a visual check of 75 targets. There is no score.
- No field check.

## Reproduce
`python notebooks/wellsight_v2/s5_eval/_nisar_bright_chips.py`

## Open ground against under canopy (2026-10-28)
Cover is the share of 1 m lidar cells above 2 m in each 5 m cell, 2019. Open is below 0.3, partial is 0.3 to 0.8, under canopy is above 0.8. Targets outside the lidar tile are left out. Ground is the lidar-covered area of each class.

Targets per square kilometre, all targets:

| Area | Open | Partial | Under canopy |
|---|---|---|---|
| 9t | 91 | 90 | 97 |
| 613590 | 138 | 130 | 128 |
| Warren | 38 | 94 | 95 |
| McKean | 63 | 89 | 41 |

Reading:
- In 9t and 613590 targets fall in proportion to ground. Forest holds as many per square kilometre as open ground.
- In Warren and McKean open ground holds fewer. McKean's denominator includes lidar outside the radar window, so its rates are rough.
- Median brightness is about 7 dB in every class in 9t and 613590. Under-canopy targets are not weaker.
- Cover above 2 m counts roofs as canopy. In the towns "under canopy" is largely buildings. Warren's under-canopy targets are the brightest (median 10 dB) for that reason.

Table: `data/9t/results/nisar/nisar_bright_cover_split_all_areas.csv`. Tile-wide cover split is a one-off calculation, not saved as a script.
