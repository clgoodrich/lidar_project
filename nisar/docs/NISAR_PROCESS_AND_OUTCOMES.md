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

**Step 2. Fix the position.** NASA's product sat about 10 m off the lidar. That is two radar pixels, which matters for a pit.
The cause is the elevation model NASA used. It sits above the true ground in forest.
We wrote our own geocoder, swapped in lidar heights, and solved the leftover shifts for each date and track.
After this, 46 of 48 blocks on 9t agreed with a lidar simulation to within 2.5 m. On 613590 it was 31 of 48.
This agrees with a simulation. It is not an independent check of position.

**Step 3. Combine ascending and descending passes.** The satellite looks from two sides on different tracks.
Each track lights the hills differently. We placed all tracks on the same lidar grid and kept them as separate bands.
We did not average them, because the lighting differences are information about the terrain.

**Step 4. Build features.** We made 303 radar bands for each target.
They cover brightness, texture, coherence (how stable the signal is between dates), season, and terrain lighting.
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
