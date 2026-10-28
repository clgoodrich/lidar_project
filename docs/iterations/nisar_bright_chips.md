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

## Pits under open sky against canopy (9t, 2026-10-28)
Question: how many recorded and predicted pits sit in the open, where optical imagery can see them, and how many sit under trees?

Inputs: the cross-validated pit results at threshold 0.50, `data/9t/results/pit/centroid_matching/pit_cv5_centroid_match_thr0p50_9t_05.gpkg`. Cover is the share of 1 m canopy cells above 2 m inside the pit polygon plus a 5 m ring (about 15 m across). Open is below 0.3, partial 0.3 to 0.8, canopy above 0.8.

| Set | n | Open | Partial | Canopy |
|---|---|---|---|---|
| Recorded pits, found | 447 | 70 | 327 | 50 |
| Recorded pits, missed | 23 | 4 | 16 | 3 |
| Predictions that match a recorded pit | 447 | 87 | 285 | 75 |
| Predictions with no recorded pit | 241 | 60 | 133 | 48 |
| Ground, same 15 m window | | 26% | 47% | 28% |

- Pits favour partial cover (73% of recorded pits against 47% of the ground). Both fully open and fully closed ground hold fewer than their share.
- The model finds about 95% of recorded pits in every class (open 70 of 74, partial 327 of 343, canopy 50 of 53).
- Precision is 59% in the open, 68% in partial cover and 61% under canopy.
- The 60 unmatched predictions in the open are the ones an optical image could check.

Output: `data/9t/results/pit/pit_cover_split_9t.gpkg`, layers `recorded_found`, `recorded_missed`, `predicted_matched`, `predicted_no_record`, with `cover` and `cover_class`.
Not saved as a script. Cover is lidar from 2019 and counts any surface above 2 m, including pad edges and buildings.

## Pads under open sky against canopy (9t, 2026-10-28)
Same question for pads. Recorded pads are the annotated pad polygons whose centroid lies in the 9t tile (650). Predictions are the out-of-fold pad U-Net candidates at probability 0.5 (1,044), from `_nisar_pad_fp_screen_9t.candidates()`. A pad counts as found, or a prediction as matched, at IoU 0.3 or more. Cover is the share of 1 m canopy cells above 2 m inside the polygon. Open is below 0.3, partial 0.3 to 0.8, canopy above 0.8.

| Set | n | Open | Partial | Canopy |
|---|---|---|---|---|
| Recorded pads, found | 600 | 54 | 512 | 34 |
| Recorded pads, missed | 50 | 9 | 39 | 2 |
| Predictions that match a recorded pad | 598 | 57 | 500 | 41 |
| Predictions with no recorded pad | 446 | 75 | 332 | 39 |

- Found rate: open 86% (54 of 63), partial 93% (512 of 551), canopy 94% (34 of 36).
- Precision: open 43%, partial 60%, canopy 51%.
- Only 63 of 650 recorded pads (10%) are fully open. 551 (85%) are partial. Median cover inside a pad polygon is 0.54.
- Cover above 2 m inside a pad is high for a cleared surface. Likely causes are regrowth on old pads, trees at drawn edges and polygons that extend past the cleared ground. Not checked.
- The 75 unmatched predictions in the open are the ones an optical image could check.

Output: `data/9t/results/pad/pad_cover_split_9t.gpkg`, layers `recorded_pads` and `predicted_pads`, with `cover`, `cover_class`, `best_iou` and `verdict`. One-off, no saved script.

### Pads open with a buffer (9t, 2026-10-28)
A pad passes when its own cover is below 0.3 and the ring around it is also below 0.3. Ring = pad polygon buffered by 15 m or 30 m, minus the pad. Same 1 m canopy cells above 2 m.

| Set | Open pad | Open pad and open 15 m ring | Open pad and open 30 m ring |
|---|---|---|---|
| Recorded pads (650) | 63 | 30 (27 found, 3 missed) | 29 (26 found, 3 missed) |
| Predictions (1,044) | 132 | 69 (37 match, 32 no recorded pad) | 60 (32 match, 28 no recorded pad) |

- Only 30 of 650 recorded pads (4.6%) are open with a 15 m margin. About half of the open pads have trees in the ring.
- Median cover in the 15 m ring is 0.56 and in the 30 m ring 0.54. Most pads are surrounded by forest.
- Output: columns `ring15` and `ring30` added to both layers of `data/9t/results/pad/pad_cover_split_9t.gpkg`. One-off, no saved script.
