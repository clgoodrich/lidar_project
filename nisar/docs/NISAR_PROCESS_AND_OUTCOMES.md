# The NISAR work in plain language

Written 2026-11-15. Rewritten 2026-11-23 for three rules now in force.
- Only NISAR dates from 2026-06-01 onward are used for any result.
- Only tile 9t is in scope.
- Every persistent-scatterer threshold has a stated source.

Each step says what we did and why we did it. Every number comes from the files listed in section 12.
Earlier versions of this document are in git history.

## 1. Objective

At known sites on tile 9t, find out whether NISAR shows a repeatable marker tied to a well pad, pit or surface equipment.
We compare each mapped feature with its own surroundings and with nearby spots that hold no mapped feature.
The outcome is the strength and consistency of a measured contrast.
Prediction, candidate ranking and discovery are outside the present scope.

*Why known sites first.* A marker that does not show where we know a well sits cannot help find unknown ones.

*Why radar at all.* Lidar finds pits and pads under the canopy, but it is flown once. NISAR passes every 12 days at no cost. Its L-band wave (24 cm) passes through leaves better than shorter radar.

## 2. The data

| Item | What we use |
|---|---|
| Satellite | NISAR L-band, HH and HV polarisation, 5 m grid |
| Area | Tile 9t, Venango County, 4.5 km square |
| Truth | 506 pits and 645 pads drawn from lidar, inner pit rims, Pennsylvania DEP well records |
| Dates | 2026-06-20 to 2026-11-16 |

**Tracks over 9t.**

| Track | Pass | Radar looks toward | Angle from vertical | Usable dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

*Why these tracks.* They are every NISAR track that covers 9t. We did not pick among them.

*Why both directions.* A slope facing the radar looks bright and the same slope seen from the other side looks dark. A pit edge or pad cut can hide from one side and show from the other.

*Why two ascending tracks.* Their angles differ by 8°. The steeper one passes through more canopy. More tracks also give more dates.

**Which dates, and why.**
- Only dates from 2026-06-01 onward are used. The rule is enforced in code (`DATE_FLOOR` in `nisar/code/_nisar_area.py`), so no script can pick an earlier date.
- *Why.* The October 2025 to January 2026 beta images came from older software and are not fully calibrated. Every fall and winter date was beta and every summer date was not. A seasonal difference could come from processing instead of season.
- NASA labels dates from June to October 2026 provisional. From 2026-10-23 it publishes them in a standard collection under a new name. Our downloads search both.
- Two dates are never used. 2026-07-22 on track 26 has no valid pixels. 2026-09-08 on track 26 sits far from where the rest of its track puts the ground.
- Nothing usable exists between January and June 2026. The raw data is released, but processed images of our frames are not.

**Seasons.** Summer runs 2026-06-01 to 09-30. Fall runs 2026-10-21 to 11-30.

| Track | Summer dates | Fall dates |
|---|---|---|
| 26 | 4 | 2 |
| 90 | 8 | 2 |
| 162 | 8 | 3 |

*Why these windows.* Leaves in western Pennsylvania turn in early October and drop in late October. Fall should mean leaf-off, when L-band sees the ground best. Early October is half-leafed, so it is in neither season.
*Why set them first.* The windows were fixed before any result from the new dates was seen. That keeps the choice from being tuned to the answer.

## 3. Amplitude and phase

**Amplitude** is how strong the echo is, in dB. It depends on roughness, slope, moisture and metal.
It drives the pit and pad brightness tests, the steel test and the water test.
*Why.* A pit or pad changes the surface, so amplitude is where a marker would show first.

**Phase** is where in its cycle the wave returns. Between two dates on one track it measures tiny changes in distance.
It drives the coherence test at pads and the motion tests.
*Why.* Work on a pad scrambles the surface between passes. A settling pit or slope would move.

Phase only compares dates on the same track. Under deciduous forest L-band phase can lose stability within 12 days. That is why most tests are built on amplitude.

## 4. The process, step by step

**Step 1. Get the data.** We cut a small window around 9t from each NASA file with range reads. A window is tens of megabytes from a file of 22.6 GB.
*Why.* Reading only the needed chunks makes every date affordable to fetch.

**Step 2. Place the radar on the lidar ground.** NASA's images sat 8 to 12 m off the lidar.
The cause is the elevation model NASA used, which sits partway up the canopy in forest.
We wrote our own geocoder and placed each image on the lidar ground plus 10% of canopy height.
The 10% came from testing 0, 10, 25 and 50%. We then solved the leftover shift for each date and each track.
On post-June dates, 47 of 48 blocks on 9t now agree with a lidar simulation to within 2.5 m. The median block offset is 1.0 to 1.4 m per track.
*Why.* A pit is only a few 5 m pixels across. At 8 to 12 m a test measures the rim or the forest.
*Limit.* The check uses a simulation that also set the track offsets. It is not a surveyed point.

**We did not build a NISAR elevation model.** The lidar is the reference the radar is placed on. Radar heights are never made.
*Why.* A radar elevation model needs repeat-pass phase. The orbit's short baselines, fast phase loss under forest and water vapour would give metres of error. Lidar already resolves pits and pads to about 10 cm.

**Step 3. Keep the tracks apart while measuring.** One run handles all three tracks. Each site's contrast is measured on each track separately. The three are then combined per site, and each track is also reported on its own.
*Why.* Each track has its own viewing direction, angle and calibration. Blending them would mix those differences into the result. Phase only works within a track.

**Step 4. Measure each site against its ring and against control spots.**
- Take the feature's brightness minus a ring around it. Pads use a 20 to 60 m ring and pits a 10 to 30 m ring.
- Do the same at five control spots of the same shape, 150 to 600 m away, with no mapped feature.
- The excess is the feature's contrast minus the median of its control spots.
- A Wilcoxon signed-rank test on the per-site excess gives the p-value. A bootstrap over sites gives the 95% interval.

*Why the ring.* Brightness changes with slope, canopy and track. A site's own surroundings cancel most of that.
*Why control spots.* Any patch differs a little from its ring by chance. Control spots show how big that chance difference is.
*Why Wilcoxon.* It assumes no bell curve, which suits small, noisy radar contrasts.
*Limit.* With 5 control spots per site, results can shift with which spots are drawn. On 613590 in October a p-value moved from 0.001 to 0.13 with the random seed. A 40-control-spot run with a swap test is the stability check. It is a next step, not part of these numbers.
*Why pool hundreds of sites.* One site is lost in speckle, the grain in radar images. No one can judge a pad by eye.

**Step 5. Invite review.** Two outside reviews and one adversarial review checked the work. The 8 to 12 m placement error came out of that.
*Why.* Small radar contrasts are easy to fool yourself with.

## 5. The tests

Each test traces to a physical reason, stated before the test was run.

| Test | Signal | Compared against | Why it could show |
|---|---|---|---|
| Pit brightness | Amplitude | Ring and control spots, summer and fall, HH and HV | A pit changes slope, soil and canopy gaps at pixel scale |
| Pad brightness | Amplitude | Same | A graded pad scatters differently from forest floor |
| Pad coherence | Phase | Control spots, each pair of back-to-back dates | Work on a pad scrambles the surface |
| Steel (persistent scatterers) | Amplitude | Control spots | Casing and tanks give strong, steady echoes |
| Pool pits | Amplitude | Other pits | Calm water reflects radar away |
| Pit motion | Phase | Ring and control spots | A settling pit would move |
| Slope motion | Phase | The second ascending track | Slow creep can shear a casing |

*Why polarisation.* HH favours ground and structures. HV favours canopy volume. Comparing them separates the two.

## 6. Results on 9t, post-June dates

### Pit and pad brightness

| Feature | Measure | Excess (dB) | 95% interval | p |
|---|---|---|---|---|
| Pits (506) | Summer HV | **+0.18** | +0.09 to +0.26 | <0.001 |
| Pits | Summer HH | +0.03 | −0.06 to +0.14 | 0.09 |
| Pits | Fall HH | +0.01 | −0.08 to +0.11 | 0.90 |
| Pits | Fall HV | +0.14 | +0.02 to +0.25 | 0.08 |
| Pits | Summer minus fall, HH | +0.12 | −0.00 to +0.22 | 0.06 |
| Pads (645) | Fall HH | **−0.13** | −0.21 to −0.02 | <0.001 |
| Pads | Fall HV | **−0.11** | −0.17 to −0.06 | <0.001 |
| Pads | Summer HH | +0.02 | −0.03 to +0.06 | 0.77 |
| Pads | Summer minus fall, HH | +0.15 | +0.09 to +0.19 | <0.001 |
| Pads | Summer minus fall, HV | +0.11 | +0.05 to +0.15 | <0.001 |

- Pits are slightly brighter than their control spots in summer HV. Fall shows no clear pit contrast.
- Pads are slightly darker than their control spots in fall, after leaf drop. Summer shows no pad contrast.
- Fall rests on 2 or 3 dates per track.
- Hollows with no well have not been compared yet. A pit contrast may mark depressions, not wells.

### Pad coherence

For each pair of back-to-back dates, a pad's coherence minus its ring, minus that pad's own median over pairs.
A pair is an event when the drop is one only 1% of control-spot pairs reach.

| Pad pairs | Events | Expected from control spots | Swap-test p |
|---|---|---|---|
| 18,172 | 211 | 181.9 | 0.022 |

Pads lose coherence slightly more often than control spots. No dated well activity is available to explain it. Vegetation, traffic and weather are plausible.
There is no winter season. All post-June pairs are snow-free.

### Steel (persistent-scatterer selection)

Persistent-scatterer analysis has two steps. Step 1 picks pixels whose brightness barely changes over dates. Step 2 reads motion from the phase at those pixels. We ran step 1.

| Rule | Value | Source |
|---|---|---|
| Steadiness (spread over mean of brightness) | under 0.25 | Ferretti, Prati and Rocca 2001. Pure speckle sits near 0.52 |
| Brightness above the 250 m median | at least 3 robust SD per track | The usual outlier rule. 1 SD is 2.2 to 2.4 dB, so 6.5 to 7.2 dB |
| Hit radius | 6 m | 3.5 m pixel half-diagonal plus 2.5 m placement |

*Why 3 SD.* Brightness above the 250 m median is centred on 0 dB. Three robust SD (1.4826 × median absolute deviation) leaves about 0.13% of pixels by chance under a normal curve. A fixed 6 dB had no recorded reason.
*Why 6 m.* That is what the radar side can deliver. Error in DEP well coordinates is not included because it cannot be measured here.

Steady bright pixels are 0.13%, 0.13% and 0.05% of valid pixels on tracks 26, 90 and 162.

| Well group | Wells | Hit, any track | Control spots | p |
|---|---|---|---|---|
| Active | 617 | 1.3% | 1.8% | 0.49 |
| Plugged | 271 | 0.4% | 0.9% | 0.71 |
| Abandoned | 174 | 1.1% | 1.2% | 1.00 |

Wells sit at chance. No well has a steady bright pixel on two or more tracks.
*Limit.* The steadiness cutoff was designed for about 30 dates. 9t has 8 to 12 per track, so speckle passes more often than in the original method.
*Step 2* needs about 20 or more dates on one track. It waits on new dates.

**A check with a known answer.** You marked a building at 41.502787, -79.519712.
On post-June dates a steady bright pixel sits 2.5 m from the point on track 162. A target seen on two tracks sits 9 m away.
A building is far bigger than a wellhead, so this does not show the test would catch small steel.

### Pool pits

A pool pit has at least half its floor flat and weak lidar returns, set before looking at the radar.
500 pits have an inner rim and lidar statistics. 23 are pool pits, including pad 303's pit.

| Measure | Pool pits (median excess, dB) | Other pits | Difference | Permutation p |
|---|---|---|---|---|
| Summer HH | +0.22 | +0.03 | +0.19 | 0.46 |
| Summer HV | +0.34 | +0.17 | +0.17 | 0.48 |
| Fall HH | +0.27 | +0.01 | +0.26 | 0.35 |
| Fall HV | +0.38 | +0.11 | +0.27 | 0.38 |

No measure separates pool pits from other pits (all p above 0.19). With 23 pool pits, a difference of a few tenths of a dB cannot be told from chance.
The lidar is from 2019, so a pool then may not be a pool now.

### Motion

| Test | Result |
|---|---|
| Pit interferograms, 28 pairs | Pit motion against ring −0.24 mm HH (95% interval −0.43 to −0.02). A single pair's noise is about 5.6 mm. |
| Slope motion, tracks 90 and 162 | Agreement r = 0.33 (0.20 to 0.45) across all slopes. Track 162 is coherent over only 39% of the tile. |

A pit would have to move far more than a millimetre to stand out from 5 to 7 mm of noise per pair.

## 7. Mistakes we caught

- Early pad and pit scores were inflated. Control spots differed from targets in more than location.
- NASA's placement was 8 to 12 m off. Fixing it removed an early pad darkening and an abandoned-well lead.
- Two statistics were not true window moments. The fix moved the headline by 0.005 or less.
- A fall pit contrast of +0.25 dB came from beta dates. It does not repeat on post-June dates.
- The hit radius of 15 m dated from before lidar placement. It is now 6 m.
- The download searched only the beta and provisional collections and missed late October and November. Both downloaders now search the standard collection.

## 8. Limitations

- 8 to 12 usable dates per track, and 2 or 3 fall dates.
- Placement is not checked against a surveyed point.
- Control spots are not matched on canopy, slope or road access.
- L-band phase can lose stability under leaves within 12 days.
- The 2019 lidar may not show the ground as it is now.

## 9. What we need

- More dates as NASA releases them, December onward.
- Surveyed points or corner reflectors on 9t to check placement.
- Hollows with no well, mapped from the 9t lidar.

## 10. Next steps

| Step | Why |
|---|---|
| Match control spots on canopy, slope and roads | Removes the largest known doubt about the excess |
| Compare pits with hollows that have no well | Tells a well marker from a depression marker |
| Run the 40-control-spot stability check on the brightness tests | 5 control spots per site can shift with the draw |
| Rerun every test as new dates arrive | More fall dates for the pad result, and enough dates for persistent-scatterer step 2 |
| Possible: a Sentinel-1 cross-check at 9t pits | A real ground marker should show on an independent radar |
| Rebuild the 346 radar bands and their PCA on post-June dates | The earlier bands used beta dates and are withdrawn |

## 11. Withdrawn from earlier versions

These used dates before June 2026 or areas outside 9t, so they are no longer findings.
- The fall HH pit contrast (+0.25 dB) and its interval.
- Winter pad brightness and winter coherence.
- The 8 wet and 5 dry reference pits. No script exists to redo them on post-June dates.
- The 346-band PCA. The bands were built on all dates.
- Tile 613590, Warren and McKean results.
- The Sentinel-1 cross-check. It used dates from 2017 to 2026. Redoing it is a possible next step.

## 12. Where to find the evidence

| Need | File |
|---|---|
| Date rule | `nisar/code/_nisar_area.py` (`DATE_FLOOR`) |
| Placement check | `nisar/results/9t/nisar_lidar_sim_match_summary_coregabs_k010_9t.json` |
| Pit and pad brightness | `nisar/results/9t/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_9t_slc_5m.csv` |
| Pad coherence | `nisar/results/9t/nisar_pad_change_by_season_9t_slc.csv` |
| Steel | `nisar/results/9t/nisar_steel_summary_9t_slc.json`, `nisar/code/s5_eval/_nisar_steel_9t.py` |
| Steady bright targets | `nisar/results/9t/nisar_bright_targets_summary_9t_slc.json` |
| Pool pits | `nisar/results/9t/nisar_pit_pool_radar_9t.csv` |
| Pit interferograms | `nisar/results/9t/nisar_gslc_interferogram_pits_vs_decoys_win3_9t_slc_5m_summary.json` |
| Slope motion | `nisar/results/9t/nisar_slope_motion_summary_9t_slc.json` |
| Citation | `literature/CITATIONS.md`, Ferretti, Prati and Rocca 2001 |
| Figures | `nisar/docs/figures/` |
| Run log | `docs/analysis_log.md` |

Glossary.
- **HH, HV.** Transmit and receive polarisations. HV responds to canopy volume.
- **Speckle.** Grainy noise from many small reflectors inside one pixel.
- **Coherence.** How similar the signal is between two dates. High means a stable surface.
- **Control spot.** A spot of the same shape as the feature, 150 to 600 m away on background. A comparison, not training data. Code calls it a decoy.
- **Excess.** Feature-minus-ring contrast, minus the same for control spots.
- **Steadiness.** Spread of a pixel's brightness over dates divided by its mean.
- **Robust SD.** 1.4826 × the median absolute deviation. It equals the standard deviation for a normal curve and ignores a few extreme pixels.
