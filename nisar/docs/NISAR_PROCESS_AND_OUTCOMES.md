# The NISAR work in plain language

Written 2026-11-15. This is the one document to read if you want the whole story.
It says what we did, why we did it that way, and what came out.
It adds no new analysis. Every number comes from the files listed at the end.

## 1. The short version

We asked whether radar from the NISAR satellite could help our lidar detector find more well pits and pads.
We set the pass mark before we looked. Radar plus lidar had to beat lidar alone by 0.05 in score.
No design we tried reached it.
The one fair test was on 36 held-out pits in a second area. Lidar alone scored 0.881. Lidar plus radar scored 0.865.
The gain was -0.017. The 95% range was -0.055 to +0.020.
That rules out a gain of +0.05 for those pits. It does not prove radar can never help.
A second satellite (Sentinel-1) gave the same answer. Radar does not reveal pits, pads or old wells here.
Radar did see a building very clearly. So the method works. The targets are just not radar-bright.

## 2. Why we tried radar at all

Our detector finds pits and pads from lidar bare-earth elevation.
Lidar has two limits. It was flown in 2019, and it only sees the shape of the ground.
Radar is flown often, so it could show change. It also responds to metal, water and ground roughness, which lidar does not.
NISAR is a new NASA and ISRO satellite. It uses L-band, a long 24 cm wavelength that passes through leaves better than shorter bands.
Its data are free. That made it a cheap test.

Two ideas drove the test.

- Steel is bright. A wellhead or tank might show as a steady bright spot.
- Pits and pads are scars. Their roughness, wetness or soil might change the radar signal.

## 3. The data

| Item | What we used |
|---|---|
| Satellite | NISAR L-band, HH and HV polarisation, 5 m grid |
| Dates | 2025-10-28 to 2026-10-14 |
| Tracks | 26 (descending), 90 and 162 (ascending) |
| Main area | Tile 9t, Venango County, 4.5 km square |
| Second area | Tile 613590, used for the held-out test |
| Extra areas | Warren and McKean, for early checks |
| Truth | Pit and pad outlines you drew from lidar, and Pennsylvania DEP well records |
| Cross-check | Sentinel-1 C-band (5.5 cm), from NASA's OPERA archive |

Three facts about the data shape everything below.

- Some dates are beta (not fully calibrated) and some are provisional. Season and processing level are tangled.
- No scenes were released from 2026-01-20 to 2026-06-20.
- NASA plans validated reprocessing of the older dates in 2027.

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
The best fit was 10%, about 1 to 2 m above the ground, not at the canopy top. A canopy-top surface fit worse.
After this, 46 of 48 blocks on 9t agreed with a lidar simulation to within 2.5 m. That used the 10% echo height. With bare earth it was 40 of 48. On 613590 it was 31 of 48.
This is agreement with a simulation that also set the track offsets. It is not an independent check of position.
The independent test, steady bright points at wells, found no clear peak.

**Step 3. Handle the three tracks.** A track is a fixed, repeating orbit path with its own viewing direction and angle.
Tracks 90 and 162 are ascending and track 26 is descending. Each has its own dates (14, 11 and 8 usable).
We placed all three on the same lidar grid and computed every feature per track.
We never merged them into one image. The model receives each track's features as separate columns.
A few bands compare directions, such as ascending minus descending HH. They rest on the single descending track.
Section 4a explains why they cannot be merged and what that did to the data.

**Step 4. Build features.** We computed 346 radar bands for each target. The model keeps 337 after dropping bands with over 20% missing values.
The held-out test on 613590 uses 293, the bands that exist on both areas.
There is no principled reason for these counts. Section 4b shows where they come from.
We also tried four speckle filters. Speckle is the grainy noise in radar images.

**Step 5. Score against fair decoys.** For each pit or pad we drew decoy spots with the same canopy cover (within 0.05) and slope (within 1 degree).
A model learned to tell targets from decoys. The score is AUC. It is the chance that a real target ranks above a decoy. 0.5 is a coin flip.
We used 5-fold spatial block cross-validation with 500 m blocks and a 250 m buffer. That stops the model from peeking at neighbours.
We ran four controls. They were lidar-only, richer lidar with 26 bands, map x and y only, and a placebo with pads moved 150 to 300 m.

**Step 6. Set the gate in advance.** Radar plus rich lidar had to beat rich lidar alone by 0.05.
We wrote down three predictions for the held-out test before running it. All three held.

**Step 7. Invite review.** Two outside reviews and one adversarial review checked the work.
They found real mistakes. We fixed them and reran the tests. Section 7 lists them.

**Step 8. Cross-check with a second radar.** We repeated the main ideas with Sentinel-1 C-band, using your pit outlines.
Section 6 covers it.

## 4a. Amplitude, phase and the three tracks

**Amplitude** is how bright each pixel is, in dB, for HH and HV.
Most of the bands come from it. Brightness, texture, dual-pol ratios, seasonal trend, bright and dark outliers and terrain-flattened brightness are all amplitude.
Every pad and pit score rests mainly on amplitude.

**Phase** was used in three places, and all three came out null or weak.
- Interferograms at pits. One date times the conjugate of the next date on the same track. Phase noise was about 7.5 mm per pit per pair, so any motion would need to exceed about 15 mm in 12 days.
- Coherence, which is how stable the signal is between dates. It fed the pad-change test and the coherence bands.
- The line-of-sight motion and height-residual bands. The Sentinel-1 interferograms used phase the same way.

We never ran persistent scatterer interferometry or a time-series deformation fit on NISAR. There are too few dates, and the data are beta or provisional.

**Why the tracks cannot be merged**
- Brightness depends on viewing direction. A slope facing the satellite is bright and the same slope seen from the other side is dark. Averaging blends two different measurements.
- Calibration differs by track. Per-track HV summer-versus-fall offsets range from +1.9 to +4.2 dB, which points to calibration and not season. An average would build that error in.
- Phase only works within a track. Interferometry subtracts two images taken from the same position. A different track has a different line of sight, so there is no valid subtraction.
- Dates do not line up between tracks. Seasonal change is measured inside one track, where terrain and angle cancel.

**What the tracks gave us**
- More dates. 33 in total, against at most 14 on one track.
- Cross-checks. A bright spot seen on all three tracks is not noise. The building at point 5 was one.

**What the tracks did to the data**
- Combining added nothing in the one test that isolates it. This is the ablation on 9t pads with matched decoys. Ascending tracks alone scored 0.828, all tracks 0.815 and the descending track alone 0.667. We know of no test showing three tracks beat one.
- Each track is thin. Every feature rests on 8 to 14 dates, so each is noisy.
- Season and track are tangled. Beta dates (Oct 2025 to Jan 2026) and provisional dates (Jun to Oct 2026) fall unevenly across tracks. Track 90 has no clean leaf-off date. A comparison across seasons can mix in geometry and calibration.
- Cross-track contrasts rest on one descending track. We cannot tell a real direction effect from track 26's own calibration.
- Motion is measured along one line of sight only. A real change in another direction would be partly invisible.

## 4b. Where the band count comes from, and what PCA says

**The count is arithmetic.** We wrote 13 scripts, each producing a handful of measures, and ran most of them once for each of the three tracks.
Seven dual-pol measures times three tracks gives 21 bands. Five texture measures times three gives 15. And so on.

| Product | Bands | Product | Bands |
|---|---|---|---|
| Amplitude statistics | 32 | Line-of-sight motion | 12 |
| Amplitude trend and season | 42 | Rain and freeze | 22 |
| Coherence | 43 | Spatial | 63 |
| Dual-pol | 21 | Sub-aperture | 15 |
| Events | 15 | Temporal | 43 |
| Geometry | 14 | Texture | 15 |
| Height residual | 9 | | |

These sum to 346. The scorer also holds 3 lidar controls and 2 road-context bands, which makes 351 scored.
Road context is circular and is excluded from every NISAR set.

**The 32 amplitude statistics.** The list was built from one hypothesis, that a pad is unnaturally flat.
So we took brightness (mean HH, mean HV, HV minus HH), its spread over dates, amplitude dispersion, and HH coherence at three date gaps with its decay.
That is 10 measures per track, 30 in all, plus 2 brightness differences between tracks.
Nothing says 32 is the right number. It is where the list ended. We never swept the number of bands.
The list is short because the data are small. There are about 33 dates, a pad or pit covers 4 to 9 pixels, and there are about 600 pads. Thousands of bands would only fit noise.

**The conclusion did not obviously depend on the count.** Six plain backscatter layers scored 0.462 on pads. All bands scored 0.622. The gain over lidar stayed near zero either way, -0.017 on held-out pits.
That is suggestive, not proof. We never ran a clean test with 2, 10, 32 and 346 bands.

**PCA (2026-11-15).** Principal component analysis finds the independent directions in a set of measurements.
We ran it on 60,000 random pixels of tile 9t. We used the 337 bands the model keeps, minus 3 that never varied. Each band was clipped at its 1st and 99th percentiles and standardised.
- The first component holds only 6.9% of the variance. The first five hold 22%.
- 26 components cover half the variance. 87 cover 80%, 127 cover 90%, 158 cover 95% and 212 cover 99%.
- A common summary, the participation ratio, gives an effective dimension of about 56.
- Each track alone needs 42 to 44 components for 90% of its roughly 100 to 110 bands.

So the bands are redundant, but not as redundant as we expected. About a third to a half of them carry something not already in the others, so there are roughly 100 to 130 real directions.
The main axes are physical. Component 1 is overall brightness across all tracks, including the ascending-minus-descending difference.
Component 2 is local texture on the two ascending tracks, mostly the spatial group (45% of its weight).
Component 3 is brightness on track 26 alone, which shows how much a single track's own level matters.
Events, rain and freeze, height residual and sub-aperture carry almost no weight in the first five components.

Limits. The sample is tile-wide, so forest dominates. It was not taken at pad or pit pixels. PCA finds variance, not usefulness. A component that explains a lot of variance can still say nothing about pads.
Files are in `nisar/results/9t/nisar_feat_pca_*_9t_slc.*` and `nisar/results/9t/figures/nisar_feat_pca_9t_slc.png`. The script is `nisar/code/s5_eval/_nisar_feat_pca_9t.py`.

## 5. What each idea showed

| Idea | Result | How we know |
|---|---|---|
| Steel is bright | No | Wells were no more likely than random ground to hold a steady bright spot (Warren 3.9% against 5.2%). The bright spots that repeat across tracks are buildings, bridges and graded yards. |
| A pad is a scar | No | A 0.3 dB darkening seen early vanished after the position fix. |
| Pits change with season | A lead, not a result | Pit minus decoy contrasts of +0.25 dB HH in fall and +0.19 dB HV in leaf-on. Between-season change tests were not significant. Filtering shrinks them. |
| Old wells move | No | Pit coherence excess was +0.0001. None of 282 wells flagged for slope motion held up. |
| Wet pits are dark | No | Wet and dry pits overlap fully (+1.58 against +1.74 dB). Lidar intensity separated all 13 labelled pits. |

### The scores that matter

| Test | Radar alone | Rich lidar | Radar plus lidar | Reading |
|---|---|---|---|---|
| Pads, decoys anywhere on the tile | 0.64 | | | A place effect, not a pad effect |
| Pads, decoys nearby | 0.48 | | | Chance |
| Pads against other clearings (60) | 0.80 | 0.99 | 0.99 | Lidar already at the ceiling |
| Pits, held out on 613590 (36) | 0.658 | 0.881 | 0.865 | The one decisive test. Gate failed |
| Lidar U-Net with radar | | 0.999 | 0.995 | Ceiling-limited |
| Radar against Sentinel-2 optical | 0.622 | | | Optical alone scored 0.840 |

Why the tile-wide pad score of 0.64 is not a real signal.
It climbs from 0.44 to 0.71 as decoys move from 100 m to over 3.5 km away. Map x and y climb the same way, to 0.96.
Pads sit in certain parts of the tile. The radar is telling places apart, not pads.

Radar-alone scores also move with the decoy set. Do not quote them as headlines.

### What the radar is actually responding to

HV (the cross-polarised channel) follows optical greenness far more than lidar canopy height. R squared was 0.52 for optical and 0.04 for lidar.
In closed forest, most raw HV is terrain lighting. Adding simulated terrain gain lifts the explained share from 0.07 to 0.57.
We did not split ground from canopy returns. So we cannot say where the energy comes from.

## 6. The Sentinel-1 cross-check (November 2026)

We asked whether a shorter wavelength (C-band) and a long record (2017 to 2026) would show what NISAR could not.
We used OPERA Sentinel-1 products, which are already aligned for interferometry.
Tests used your annotated pits, not DEP wells, because the pits are where the disturbance is.

| Test | Result |
|---|---|
| Interferograms of pits, Oct-Nov 2025, April 2025 and 2026, every April 2017 to 2026 | No pit signal. April 2025 on 9t showed -1.18 mm (p 0.003). It did not return in other years. Pooled over years it was -0.06 mm (range -0.31 to +0.12). |
| Coherence at pits against decoys | A small +0.011 on 9t. It traces to how decoys were drawn and to open ground. Pits under closed canopy match their own ring. 613590 shows none. |
| Small-metal bright-spot detector (CFAR) at wells | Wells hit 0.26% against 0.44% for random ground. |
| Same detector at 666 annotated pits | Pits 0.15% against decoys 0.60% at a 1 in a million false alarm level. |
| Steadiest pixel at pits | Same as decoys (0.385 against 0.380 in April). Only 9 pixels in the window passed the steady test. None were at wells. |
| X-band (finer, 3 cm) | None free over our areas. The nearest Umbra scenes are about 86 km away near North East, Pennsylvania. |

Bright pixels near pits mean rough or open disturbed ground. They do not mean steel.

Deformation by persistent scatterer interferometry is not feasible on NISAR until the 2027 reprocessing.
It is feasible on Sentinel-1 through NASA's displacement products. We expect a null at Venango, where the ground is stable.

## 7. Mistakes we caught

We list these because they changed the answer.

- Early pad and pit scores were inflated. Decoys differed from targets in more than location. The corrected design is the one reported.
- The U-Net sampler could read held-out pixels. We fixed it and reran the fusion.
- Two statistics (`skew7`, `kurt7`) were not true window moments. After the fix the headline moved by 0.005 or less.
- In the optical test we masked thin cirrus, which removed most of September. We then subtracted a reflectance offset these scenes do not use. Both were fixed.
- We guessed the radar "follows the terrain", then that it "looks like trees". Neither held up.
- We read a ground-elevation effect in closed forest as stand type. The audit showed it was terrain lighting.
- A first count of pads the U-Net "missed" was 30%. Merged blobs fooled the match. The fixed count is 7.4%.
- The first Sentinel-1 interferogram counted pixels outside the burst as zero motion. Dropping them fixed it.
- The first bright-spot run put most hits on river banks. A water mask fixed it.

An adversarial review on 2026-11-09 found ten problems and we fixed most on the same day.
Three remain. The dedupe comparison did not hold folds fixed. The wet and dry CSV generator is not in the repo. Position is not independently confirmed.

## 8. A check with a known answer

On 2026-11-13 you picked a spot (41.502787, -79.519712) and later told us it was a building.
We had read it as a graded yard, so this is a fair test of the radar.

- NISAR showed three pixels bright on all three tracks. The strongest was 17.7 dB above its surroundings. Its steadiness score was 0.09, well under the 0.25 steady cutoff.
- Sentinel-1 showed a bright streak just south-south-east of the point.
No pit or well site has come near that.
So the steady-bright-target test does fire on a real structure. A null at pits is about the pits.
A building is far bigger than a wellhead, so this does not show the test would catch small steel.

## 9. What this does and does not tell us

It tells us

- The current radar features should not go into the detector.
- Radar-alone scores are too sensitive to design to be headlines.
- Free Sentinel-2 optical does as well as the radar, or better, where lidar is absent.

It does not tell us

- That radar is useless. A smaller gain is not excluded.
- Anything about pads that lidar cannot see. They are not in the labels.
- Anything about wells changed since 2019. The labels come from lidar.
- Anything about the validated products. Those arrive in 2027.

## 10. What could still change the answer

| Path | Needs |
|---|---|
| Pad held-out test on 613590 | You mark the 161 candidates in `nisar/results/613590/nisar_pad_review_candidates_613590.gpkg`, without seeing radar |
| Independent position check | Surveyed structures or corner reflectors |
| Beta against provisional confound | The 2027 validated reprocessing |
| Spring scenes (flooded forest) | NASA to release the Feb to May 2026 gap |
| Fine X-band over our area | A paid scene from Umbra, Capella or ICEYE |
| Deformation test | Sentinel-1 displacement products, with an expected null |

## 11. Where to find the evidence

| Need | File |
|---|---|
| Start page | `nisar/README.md` |
| Full findings and tables | `nisar/docs/NISAR_FINDINGS.md` |
| How each number was made | `nisar/docs/NISAR_METHODS.md` |
| One page status | `nisar/writeup/nisar_project_status_brief.md` |
| One write-up per experiment | `nisar/docs/iterations/` |
| Held-out pre-registration | `nisar/docs/iterations/nisar_heldout_613590_prereg.md` |
| Independent review | `nisar/reviews/nisar_adversarial_20261109/REPORT.md` |
| Sentinel-1 write-ups | `nisar/sentinel1/docs/s1_ifg_pits_9t.md` and `nisar/sentinel1/docs/s1_metal_cfar_9t.md` |
| Site figures | `nisar/sentinel1/results/9t/sites/` |
| Scripts | `nisar/code/` and `nisar/sentinel1/code/` |
| Numbers and figures | `nisar/results/<area>/` and `nisar/sentinel1/results/<area>/` |

Glossary.

- **L-band, C-band, X-band.** Radar wavelengths of about 24 cm, 5.5 cm and 3 cm. Longer waves pass through leaves more easily.
- **HH, HV.** Transmit and receive polarisations. HV is cross-polarised and responds to volume scattering such as canopy.
- **Speckle.** Grainy noise from many small reflectors inside one pixel.
- **Coherence.** How similar the signal is between two dates. High means a stable surface.
- **Decoy.** A comparison spot matched to a target on canopy and slope.
- **AUC.** The chance a real target scores above a decoy. 0.5 is chance, 1.0 is perfect.
- **Held-out.** Scored on an area the model never trained on.
- **Gate.** The pass mark set before the test.
- **CFAR.** A bright-spot detector that sets its threshold from the local background.
- **Steadiness (D_A).** Spread of a pixel's brightness over dates divided by its mean. Under 0.25 is steady. Pure speckle is about 0.53.
