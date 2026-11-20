# The NISAR work in plain language

Written 2026-11-15. Rewritten 2026-11-18 around the marker objective, with the work since then added.
This is the one document to read if you want the whole story.
It adds no new analysis. Every number comes from the files listed at the end.

## 1. Objective and short version

**Objective.** At known sites, find out whether NISAR shows a repeatable marker tied to a well pad, pit or surface equipment.
We compare each mapped feature with its own surroundings and with nearby non-well spots.
The outcome is the strength and consistency of a measured contrast.
Prediction, candidate ranking and discovery are outside the present scope.

**Short version.**
- We found two small leads and several markers that did not hold up.
- The strongest lead is a small brightness contrast at 506 mapped pits. It is not yet tied to well sites in particular.
- A weaker lead is slightly more loss of signal stability at pads between passes.
- Pad brightness, steel, water and motion gave no marker.
- Pits holding a pool on their floor look no different to the radar from other pits (section 7).
- A Sentinel-1 C-band cross-check found no pit signal in coherence, motion or steady bright targets.
- NISAR did see a building clearly. So the measurement works on real structures.
- Earlier classifier and candidate-ranking work is archived (section 11).

## 2. The markers we examined

| Potential marker | What was measured | Reading |
|---|---|---|
| **Pit brightness** | Across 506 mapped pits, the pit-to-ring contrast beat the control-to-ring contrast by **0.25 dB in fall HH** (p 0.0002) and **0.19 dB in summer HV** (p 0.0002). | **Strongest lead.** Most of the excess comes from control spots being dark, not pits standing out. In fall the pits were 0.12 dB darker than their rings and control spots 0.39 dB darker. The direct summer-minus-fall change was not conclusive. |
| **Pad coherence loss** | Across 649 pads, **169 snow-free coherence-loss events against 136.4 expected** from control spots (p 0.001). | **Weaker lead.** Pads lost signal stability slightly more often. No dated well activity explains it. Vegetation, traffic and weather are plausible. Winter shows no excess (13 against 13.1). |
| **Pad brightness** | Across 650 pads, fall and summer HH were within 0.01 dB of control spots. Winter HH was -0.086 dB (p 0.0016). | No dark pad signature. The winter value is exploratory. Snow and processing level varied. |
| **Steel** | Steady bright targets near DEP wells (section 6). | No marker. Wells hit at chance. |
| **Water** | 8 wet and 5 dry reference pits. Then 23 lidar-found pool pits against 477 other pits (section 7). | No marker. Wet and dry overlap. Pool pits match other pits. |
| **Motion** | Pit interferograms and slope motion at wells. | No marker. 0 of 15 coherent wells flagged after correction. |

**Limits that apply to every row**
- Control spots were the same shape as the feature, moved 150 to 600 m onto background. They were not matched on canopy, slope or road access. Part of the pit excess may come from that.
- The pit contrast is small. The 95% interval for fall HH runs from 0.10 to 0.43 dB.
- The "fall" season rests on 1 date on tracks 26 and 90 and 3 dates on track 162 (section 3).
- The data are beta and provisional, with calibration offsets between tracks.
- Position is inferred from lidar and not surveyed (section 4).

## 3. The data

| Item | What we used |
|---|---|
| Satellite | NISAR L-band, HH and HV polarisation, 5 m grid |
| Tracks | 26 (descending), 90 and 162 (ascending) |
| Main area | Tile 9t, Venango County, 4.5 km square |
| Second area | Tile 613590, Venango County |
| Extra areas | Warren and McKean, for early checks |
| Truth | Pit and pad outlines you drew from lidar, inner pit rims, and Pennsylvania DEP well records |
| Cross-check | Sentinel-1 C-band (5.5 cm), from NASA's OPERA archive |

**The dates on hand (2026-11-18).** A date counts when at least half the window holds valid pixels.

| Track | Pass | 9t | 613590 |
|---|---|---|---|
| 26 | descending | 10 dates. 2025-11-12, 12-18, 12-30. 2026-06-28, 08-15, 08-27, 09-08, 09-20, 10-02, 10-14 | Same 10 |
| 90 | ascending | 12 dates. 2025-11-04. 2026-01-15, 06-20, 07-02, 07-14, 07-26, 08-19, 08-31, 09-12, 09-24, 10-06, 10-18 | Same 12 |
| 162 | ascending | 15 dates. 2025-10-28, 11-09, 11-21, 12-03. 2026-01-08, 01-20, 06-25, 07-07, 07-19, 08-12, 08-24, 09-05, 09-17, 09-29, 10-11 | **6 dates**. 2025-10-28 to 2026-01-20 only |

- The seasonal pit and pad tests ran on 31 of these dates (7, 10 and 14 by track). Later downloads were not added. The tests were not rerun.
- 613590 has no summer or fall 2026 on track 162. Its seasonal numbers are thinner than 9t's.
- Nothing is usable between 2026-01-20 and 2026-06-20. Section 3a explains why.
- Some dates are beta (not fully calibrated) and some are provisional. Season and processing level are tangled. Beta covers Oct 2025 to Jan 2026, provisional Jun to Oct 2026.
- NASA plans validated reprocessing of the older dates in 2027.

## 3a. The spring 2026 gap (checked 2026-11-15)

The satellite did record over 9t and 613590 in spring 2026. The raw data is released. Processed images of our frames are not, so we cannot use it yet.
- **Raw data exists.** NASA's archive lists raw Level 0 files (RRSD) for spring passes on tracks 90 and 162, for example 2026-04-09, 2026-04-21, 2026-05-27 and 2026-06-08. Each raw pass is about 60 GB and covers our areas.
- **Raw data cannot be clipped.** It is echo data, not an image. Each image pixel is built from echoes spread over kilometres of flight path. Using it means downloading the whole file and focusing it ourselves with ISCE3, NASA's open-source processor.
- **Processed spring images exist only for the neighbouring frame.** The April 9 GSLC on track 90 is frame 23. Its south edge sits about 12 km north of 9t. Track 162's spring files are frame 24. Our clipped windows from those files held no valid pixels over 9t or 613590.
- **The frames over us are not out yet.** Frame 22 on track 90 and frame 23 on track 162 return no processed files between 2026-01-21 and 2026-06-19.
- **One new date did arrive.** 2026-10-18 on track 90 was added for both areas.
- **The fetch was widened.** `nisar/code/s1_build/_fetch_nisar_gslc_window_9t.py` now also searches by track and neighbouring frame. A rerun will pick up the covering frames when NASA releases them.

| Option | Cost |
|---|---|
| Wait for NASA's processed frames | None. Rerun the fetch from time to time |
| Focus raw passes ourselves | About 60 GB and several hours per pass, about 1.2 TB for the spring. Raw access returned HTTP 403 in October and has not been retested |

## 4. The process, step by step

**Step 1. Get the data.** We cut small windows from huge NASA files with range reads. Each window was about 9 MB from a file of 22.6 GB.

**Step 2. Fix the position.** We inferred that NASA's product sat about 8 to 12 m off the lidar. That is about two radar pixels, which matters for a pit.
We never checked this against a surveyed point. Four things point to a real error.
- The shift points away from the satellite on all three tracks.
- All three geometries give the same height error, 8 to 10 m.
- The shift grows with canopy height (correlation 0.55 to 0.62).
- Our fix matched the predicted shift (correlation 0.82 to 0.90).

The cause is the elevation model NASA used. It sits partway up the canopy in forest.
We wrote our own geocoder, swapped in lidar heights, and solved the leftover shifts for each date and track.
We also tested where the radar echo sits. We put it at 0, 10, 25 and 50% of canopy height above the ground.
The best fit was 10%, about 1 to 2 m above the ground. A canopy-top surface was not run.
After this, 46 of 48 blocks on 9t agreed with a lidar simulation to within 2.5 m. With bare earth it was 40 of 48. On 613590 it was 31 of 48.
This is agreement with a simulation that also set the track offsets. It is not an independent check of position.

**We did not build a NISAR elevation model.** The lidar DEM is the reference the radar is placed on. Radar heights are never made.
A NISAR DEM would need repeat-pass interferometry. Three things work against it here.
- The orbit repeats in a tight tube. Short baselines give poor height sensitivity.
- L-band phase loses stability under deciduous forest in 12 days.
- Water vapour adds phase errors larger than a weak height signal.
The expected result is metres of error in the open and noise under trees. Lidar resolves pits and pads to about 10 cm.
It could be run as an experiment, scored against lidar. The first step would be to read the real baselines from the products.

**Step 3. Handle the three tracks.** A track is a fixed, repeating orbit path with its own viewing direction and angle.
We placed all three on the same lidar grid and computed every measure per track. We never merged them into one image.
Section 4a explains why.

**Step 4. Measure contrasts at known sites.** For each pit or pad we compared the feature with a ring around it.
We then compared that contrast with five control spots of the same shape, 150 to 600 m away. The difference is the excess.
Control spots are a comparison baseline. They show the contrast any patch of ground gives, so the excess is what the feature adds. They are not training data for a model. Scripts and file names still call them decoys.
A swap test shuffles feature and control labels to get a p-value.

**Step 5. Build bands.** We also computed 346 radar bands for each site, for screening. Section 4b says where the count comes from.
We tried four speckle filters. Speckle is the grainy noise in radar images.

**Step 6. Invite review.** Two outside reviews and one adversarial review checked the work.
They found real mistakes. We fixed them and reran the tests. Section 9 lists them.

**Step 7. Cross-check with a second radar.** We repeated the main ideas with Sentinel-1 C-band, using your pit outlines (section 8).

## 4a. Amplitude, phase and the three tracks

**Amplitude** is how bright each pixel is, in dB, for HH and HV.
Most of the bands come from it. Brightness, texture, dual-pol ratios, seasonal trend, outliers and terrain-flattened brightness are all amplitude.
The pit and pad brightness contrasts rest on amplitude.

**Phase** was used in three places.
- Interferograms at pits. One date times the conjugate of the next date on the same track. Phase noise was about 7.5 mm per pit per pair, so motion would need to exceed about 15 mm in 12 days.
- Coherence, which is how stable the signal is between dates. It fed the pad coherence-loss test.
- The line-of-sight motion and height-residual bands. The Sentinel-1 interferograms used phase the same way.

Persistent-scatterer analysis has two steps. Step 1 picks pixels whose brightness barely changes over dates (amplitude dispersion under 0.25, Ferretti et al. 2001). Step 2 fits motion and height from the phase at only those pixels.
We ran step 1. It is the steady-target screen in section 6, and it found almost no persistent scatterers at wells.
We did not run step 2. With no scatterers at wells there is nothing to measure there. It also needs about 20 or more dates on one track, and we have 10 to 15 split between beta and provisional.

**Why the tracks cannot be merged**
- Brightness depends on viewing direction. A slope facing the satellite is bright and the same slope seen from the other side is dark.
- Calibration differs by track. Per-track HV summer-versus-fall offsets range from +1.9 to +4.2 dB, which points to calibration and not season.
- Phase only works within a track. A different track has a different line of sight, so there is no valid subtraction.
- Dates do not line up between tracks. Seasonal change is measured inside one track, where terrain and angle cancel.

**What the tracks gave us**
- More dates. 37 on 9t in total, against at most 15 on one track.
- Cross-checks. A bright spot seen on all three tracks is not noise. The building in section 10 was one.

**What the tracks did to the data**
- Each track is thin. Every measure rests on a handful of dates per season.
- Season and track are tangled. Track 90 has no clean leaf-off date.
- Cross-track contrasts rest on one descending track. We cannot tell a real direction effect from track 26's own calibration.
- Motion is measured along one line of sight only.

## 4b. Where the band count comes from, and what PCA says

**The count is arithmetic.** We wrote 13 scripts, each producing a handful of measures, and ran most of them once per track.

| Product | Bands | Product | Bands |
|---|---|---|---|
| Amplitude statistics | 32 | Line-of-sight motion | 12 |
| Amplitude trend and season | 42 | Rain and freeze | 22 |
| Coherence | 43 | Spatial | 63 |
| Dual-pol | 21 | Sub-aperture | 15 |
| Events | 15 | Temporal | 43 |
| Geometry | 14 | Texture | 15 |
| Height residual | 9 | | |

These sum to 346. 337 survive a filter that drops bands with over 20% missing values.

**The 32 amplitude statistics.** The list came from one idea, that a pad is unnaturally flat.
So we took brightness (mean HH, mean HV, HV minus HH), its spread over dates, amplitude dispersion, and HH coherence at three date gaps with its decay.
That is 10 measures per track, 30 in all, plus 2 brightness differences between tracks.
Nothing says 32 is the right number. It is where the list ended.

**PCA (2026-11-15).** Principal component analysis finds the independent directions in a set of measurements.
We ran it on 60,000 random pixels of tile 9t, using 334 bands that varied.
- The first component holds only 6.9% of the variance.
- 26 components cover half the variance. 127 cover 90% and 212 cover 99%.
- The effective dimension is about 56.

So the bands are redundant, but less than we expected. There are roughly 100 to 130 real directions.
Component 1 is overall brightness across all tracks. Component 2 is local texture on the ascending tracks. Component 3 is brightness on track 26 alone.
The sample is tile-wide, so forest dominates. PCA finds variance, not usefulness.
Files are `nisar/results/9t/nisar_feat_pca_*_9t_slc.*` and `nisar/results/9t/figures/nisar_feat_pca_9t_slc.png`. The script is `nisar/code/s5_eval/_nisar_feat_pca_9t.py`.

## 5. What each marker idea showed

| Idea | Result | How we know |
|---|---|---|
| Steel is bright | No | Section 6. |
| A pad is a scar | No | A 0.3 dB darkening seen early vanished after the position fix. Corrected fall and summer pad contrasts are within 0.01 dB of zero. |
| Pits change with season | A lead | +0.25 dB HH in fall and +0.19 dB HV in summer. Between-season change was not conclusive. Speckle filtering shrinks the contrasts. |
| Pads lose stability | A weaker lead | 169 events against 136.4 expected. |
| Old wells move | No | Pit coherence excess +0.0001. None of 282 wells flagged for slope motion held up. |
| Wet pits are dark | No | Wet and dry overlap (+1.58 against +1.74 dB). Pool pits match other pits (section 7). |

What the radar responds to. HV follows optical greenness far more than lidar canopy height (R squared 0.52 against 0.04).
In closed forest most raw HV is terrain lighting. Adding simulated terrain gain lifts the explained share from 0.07 to 0.57.

## 6. Steady bright targets (persistent-scatterer selection, step 1)

**Idea.** Casing, pumpjacks and tanks are steel. Steel gives strong echoes that stay the same between passes. Forest echoes flicker.
A steady bright target is a persistent scatterer. This section is the selection step of persistent-scatterer analysis. The phase step (section 4a) was not run.

**Method.**
- Per track, amplitude dispersion is the spread of HH brightness over dates divided by its mean. Forest pixels sit near 0.5.
- A steady bright target scores below 0.25 and is at least 6 dB brighter than the median within 250 m.
- A well is hit when a target sits within 15 m.
- Each well gets 5 control spots 150 to 600 m away with the same canopy cover. Never-drilled permits are a negative control.

**Results.**

| Test | Wells | Comparison | Reading |
|---|---|---|---|
| NISAR, 9t | 1 to 2% hit | 0.3 to 1% at control spots | Wells about 0.1 dB brighter, active and abandoned alike. Steadiness does not separate them (AUC 0.47 to 0.50). |
| NISAR, Warren (684 wells) | 3.9% hit | 5.2% at random spots | At chance (p 0.75). Under canopy 2.2% against 5.3%. |
| Sentinel-1, 9t and 613590 | 2 of 9 steady targets near active wells (34 m, 82 m), outside the hit zone | The other 7 sit on the river floodplain | Same as random ground |
| NISAR provisional dates only (June to October 2026), 9t and 613590 | 23 to 26% hit at 9t, 16 to 21% at 613590 | 20 to 24% at control spots | At chance. Steadiness AUC 0.49 to 0.53. Limited by date count, see below. |
| Registration from steady targets | Best 2.4% at one shift | 1.6% median | No clear peak. Cannot fix position. |

**Limitation of the provisional-only run (2026-11-20).**
- Amplitude work uses provisional dates only. That leaves 6 to 10 dates per track.
- Amplitude dispersion from so few dates is noisy. Speckle falls below 0.25 by chance.
- The screen passes 0.14 to 0.62% of pixels. Most of these are noise in open fields.
- The method was designed for about 30 or more dates. This is a limit of the data on hand.
- The result is reported as is. The screen stays in the analysis with this limit stated.

**Why it likely fails here.**
- A wellhead is 1 to 3 m. A 5 m pixel also holds trees and ground.
- 8 to 15 dates give a noisy steadiness estimate. Only 0.004 to 0.03% of pixels qualified.
- Plugged and orphaned wells often have the casing cut off or buried.

**Caveats.**
- The 9t NISAR run predates the 2026-10-26 bad-date fix and used NASA's placement, not the lidar-placed stack. It needs a rerun with `--slc`.
- 613590 has no NISAR steel test. Track 162 there has only 6 dates.

## 7. Marker sites and pool pits (2026-11-15 to 11-18)

**Four sites from an outside read (Codex).** Pads 303, 316 and 993 on 9t, and pit 718 on 613590.
We drew lidar and radar side by side for each.

| Site | What lidar shows | What radar shows | Reading |
|---|---|---|---|
| Pad 303 | A pit inside the pad with a pool on its floor | No steady NISAR pixel | The pool is a lidar feature |
| Pad 316 | Not in your pad outlines | Bright along the road | Best explained by the road |
| Pad 993 | Next to a pit, along a roadway | Bright along the road | Best explained by the road. Picked as an extreme, so expect some chance |
| Pit 718 | Under canopy, about 7 radar pixels | Nothing clear | Too small and covered to read |

**Pool pits.** You saw a pool in pad 303's pit and at other pits. We found such pits from lidar and asked whether radar treats them differently.
- The test compares the floor inside each inner rim with a ring 3 to 10 m outside the outer rim.
- A pool pit has at least half its floor flat (slope under 2 degrees) and weak lidar returns. Weak means ground intensity at most 0.7 of the ring, or point density at most half. Water absorbs the lidar pulse.
- Thresholds were set before looking at the radar. Pad 303's pit was the visual reference.

| Area | Pits tested | Pool pits | Radar difference, pool against other pits |
|---|---|---|---|
| 9t | 500 | 23, including pad 303's pit | None. Largest +0.41 dB HV in fall (p 0.25). All 8 measures p above 0.2 |
| 613590 | 36 (the pits with radar contrasts) | 0 | Not testable |

So pools show in lidar but give NISAR no consistent signal. The lidar is from 2019, so a pool then may not be a pool now.
613590 now has 155 inner rims. Only 36 have radar contrasts.

## 8. The Sentinel-1 cross-check (November 2026)

We asked whether a shorter wavelength (C-band) and a long record (2017 to 2026) would show what NISAR could not.
We used OPERA Sentinel-1 products, which are already aligned for interferometry.

| Test | Result |
|---|---|
| Interferograms of pits, Oct-Nov 2025, April 2025 and 2026, every April 2017 to 2026 | No pit signal. April 2025 on 9t showed -1.18 mm (p 0.003). It did not return in other years. Pooled it was -0.06 mm (range -0.31 to +0.12). |
| Coherence at pits against control spots | A small +0.011 on 9t. It traces to how control spots were drawn and to open ground. 613590 shows none. |
| Small-metal bright-spot detector (CFAR) at wells | Wells 0.26% against 0.44% for random ground. |
| Same detector at 666 annotated pits | Pits 0.15% against control spots 0.60%. |
| Steadiest pixel at pits | Same as control spots (0.385 against 0.380 in April). |
| X-band (finer, 3 cm) | None free over our areas. The nearest Umbra scenes are about 86 km away. |

Bright pixels near pits mean rough or open disturbed ground. They do not mean steel.

## 9. Mistakes we caught

- Early pad and pit scores were inflated. Control spots differed from targets in more than location.
- Two statistics (`skew7`, `kurt7`) were not true window moments. After the fix the headline moved by 0.005 or less.
- In the optical test we masked thin cirrus, which removed most of September. We also subtracted a reflectance offset these scenes do not use. Both were fixed.
- We guessed the radar "follows the terrain", then that it "looks like trees". Neither held up.
- We read a ground-elevation effect in closed forest as stand type. It was terrain lighting.
- The first Sentinel-1 interferogram counted pixels outside the burst as zero motion. Dropping them fixed it.
- The first bright-spot run put most hits on river banks. A water mask fixed it.
- We first said the spring 2026 files lacked footprints. They have footprints and miss our areas.
- The process PDF once failed to update because it was open. The render script now checks.

An adversarial review on 2026-11-09 found ten problems. We fixed most the same day.
Position is still not independently confirmed.

## 10. A check with a known answer

On 2026-11-13 you picked a spot (41.502787, -79.519712) and later told us it was a building.
- NISAR showed three pixels bright on all three tracks. The strongest was 17.7 dB above its surroundings. Its steadiness was 0.09, well under 0.25.
- Sentinel-1 showed a bright streak just south-south-east of the point.
So the steady-target test fires on a real structure. A null at pits is about the pits.
A building is far bigger than a wellhead. This does not show the test would catch small steel.

## 11. What this tells us, and what was archived

It tells us
- NISAR shows at most small, hard-to-attribute contrasts at pits and pads.
- A dark pad signature is not supported.
- Steel, water and motion are not confirmed markers here.

It does not tell us
- That the pit contrast belongs to well sites. Non-well depressions have not been compared.
- Anything about the validated products. Those arrive in 2027.
- Anything about sites changed since 2019. The outlines come from lidar.

**Archived on 2026-11-15.** Earlier work trained classifiers to tell sites from decoy spots used as training negatives, set a +0.05 pass mark and swept the number of bands.
That is prediction, outside the present objective. 17 scripts and 98 result files were moved to `nisar/archive/prediction/`.
The earlier version of this document is `nisar/archive/prediction/NISAR_PROCESS_AND_OUTCOMES_prediction_version_20261115.md`.
Nothing was deleted. The moves are logged in `docs/MOVES.csv` under `nisar_prediction_archive`.
For the record, the held-out pit test on 613590 gave -0.017 against lidar alone (95% interval -0.055 to +0.020). No component count changed that.

## 12. Next steps

| Step | Needs |
|---|---|
| Rerun pit and pad contrasts with control spots matched on canopy, slope and road access | Desk work |
| Compare pits with non-well depressions | Desk work. Tells a well marker from a depression marker |
| Rerun the seasonal tests on all 37 dates | Desk work |
| Rerun the 9t steel test on the lidar-placed stack | Desk work |
| Pool cue on all 155 inner rims in 613590 | Desk work, lidar only |
| Independent position check | Surveyed structures or corner reflectors |
| Spring scenes | NASA's processed frames, or focusing raw passes (section 3a) |
| Beta against provisional confound | The 2027 validated reprocessing |
| Fine X-band | A paid scene from Umbra, Capella or ICEYE |

## 13. Where to find the evidence

| Need | File |
|---|---|
| Start page | `nisar/README.md` |
| Full findings and tables | `nisar/docs/NISAR_FINDINGS.md` |
| How each number was made | `nisar/docs/NISAR_METHODS.md` |
| One write-up per experiment | `nisar/docs/iterations/` |
| Seasonal pit and pad contrasts | `nisar/results/9t/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_swap40_9t_slc_5m.csv` |
| Steady targets | `nisar/docs/iterations/nisar_wells_steel_pads_slopes_9t.md`, `nisar/docs/iterations/nisar_bright_targets_wells_warren.md` |
| Pool pits | `nisar/results/9t/nisar_pit_pool_radar_9t.csv`, `nisar/results/kml/nisar_pit_pool_9t.kml` |
| Marker site KMLs | `nisar/results/kml/nisar_marker_sites_9t.kml`, `nisar/results/kml/nisar_marker_sites_613590.kml` |
| Site figures | `nisar/sentinel1/results/9t/sites/`, `nisar/sentinel1/results/613590/sites/` |
| Inner pit rim KMLs | `qgis/annotations/kml/pit_inside_9t.kml`, `qgis/annotations/kml/pit_inside_613590.kml` |
| Date indexes | `nisar/derived/<area>/nisar_gslc_5m/nisar_gslc_window_index_<area>_5m.csv` |
| Independent review | `nisar/reviews/nisar_adversarial_20261109/REPORT.md` |
| Sentinel-1 write-ups | `nisar/sentinel1/docs/s1_ifg_pits_9t.md`, `nisar/sentinel1/docs/s1_metal_cfar_9t.md` |
| Archived prediction work | `nisar/archive/prediction/` |
| Figures for this document | `nisar/docs/figures/`, made by `nisar/code/s7_analysis/_nisar_process_figures.py` |

Glossary.

- **L-band, C-band, X-band.** Radar wavelengths of about 24 cm, 5.5 cm and 3 cm. Longer waves pass through leaves more easily.
- **HH, HV.** Transmit and receive polarisations. HV responds to volume scattering such as canopy.
- **Speckle.** Grainy noise from many small reflectors inside one pixel.
- **Coherence.** How similar the signal is between two dates. High means a stable surface.
- **Control spot.** A spot of the same shape as the feature, 150 to 600 m away on background. It is a comparison baseline, not training data. Code and file names call it a decoy.
- **Excess.** Feature-minus-ring contrast, minus the same for control spots.
- **CFAR.** A bright-spot detector that sets its threshold from the local background.
- **Steadiness (D_A).** Spread of a pixel's brightness over dates divided by its mean. Under 0.25 is steady. Pure speckle is about 0.53.
