# Companion notes for the design talk, tile 9t

CIVE 6359 design talk, 1 December 2026. One section per slide of the 10-slide deck. Each section gives what the slide shows, the background behind it, the reasons for each choice, and the oral questions it is likely to draw. All numbers use NISAR dates from June 2026 onward and tile 9t only.

## Slide 1. Title

On the slide. NISAR L-band radar at known oil and gas well sites in western Pennsylvania.

Background. The question is narrow on purpose. It asks whether a marker shows at sites we already know. It does not try to predict new wells. A marker that does not show at a known well cannot find an unknown one, so prediction waits on this answer.

## Slide 2. The question

On the slide. The one-sentence question, the expected signal, and our own NISAR product beside the lidar.

Question. At known well sites on tile 9t, does NISAR L-band radar show a repeatable contrast at well pads, pits or surface steel that differs from nearby ground with no well?

Site. Tile 9t is a 4.5 km square in Venango County, Pennsylvania, near 41.50° N, 79.54° W. Forested Appalachian Plateau with 150 years of oil drilling. Lidar mapping gives 506 pits and 650 pads, 645 of them with a full ring for testing. DEP lists 1,068 wells. A pad is the cleared, graded ground around a well. A pit is the dug hollow beside it.

Expected signal and where each number comes from.
- Pits and pads. The per-site excess spreads by about 0.9 dB for pits and 0.5 dB for pads. With 506 pits the smallest shift the test can detect is about 0.14 dB. With 645 pads it is about 0.07 dB. These use 2.8 standard errors, the usual value for 80% power at a 5% two-sided test, times 1.25 for using the median.
- Steel. At least 6.5 to 7.2 dB above the ground around it. This is 3 robust standard deviations of brightness on the tile (slide 8).
- Motion. More than about 12 mm in 12 days. That is twice the 6 mm phase noise of one interferogram pair at a pit.

The image (bonus product). NISAR HV mean backscatter, track 162, the eight summer dates 25 June to 29 September 2026. We placed each image on the lidar ground and averaged in linear power. Valleys and slopes match the lidar, which shows L-band reaches the ground under canopy. Limits: terrain lighting dominates, speckle hides anything under tens of metres, calibration is provisional.

Likely question. How big is your signal compared with the noise, and over what time? Answer: one pixel's brightness spreads by about 2.3 dB, far more than a pit contrast. Pooling 506 pits brings the detectable shift down to about 0.14 dB over one summer of 4 to 8 dates per track.

## Slide 3. Two things the radar records

On the slide. Amplitude and phase, and which tests use each.

Background. Amplitude is the strength of the echo. Brightness is amplitude squared, echo power, in decibels. dB is a log scale, and +3 dB is twice the power. Phase is where in its cycle the wave returns. The phase difference between two dates on one track measures movement toward or away from the satellite. Coherence is how alike the signal stays between two dates, from 0 to 1.

Why amplitude for most tests. Amplitude responds to roughness, slope, moisture and metal, so a change in the ground surface shows there first. It can be read from one image, so every date counts.

Why phase only for disturbance and motion. Phase measures what amplitude cannot: movement and disturbance between dates. It only compares dates on the same track, and under deciduous forest L-band phase can lose stability within 12 days.

A track is one fixed orbit path that repeats every 12 days.

## Slide 4. Data: three tracks

On the slide. Geometry table, product, dates, the dates figure, the source.

| Track | Pass | Looks toward | Incidence angle | Dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

Product. Level 2 geocoded single-look complex images (GSLC), HH and HV, 5 m. Level 1 RSLC to place each image on the lidar ground. Both keep phase, so one download gives backscatter, coherence and interferograms.

Why L-band. The targets sit under deciduous canopy. A 24 cm wave passes through leaves better than C-band (5.5 cm) or X-band (3 cm) and keeps coherence longer.

Why these tracks. They are every NISAR track over 9t. We did not pick among them.

Why both look directions. A slope facing the radar looks bright, and the same slope seen from the other side looks dark. A feature in shadow on one pass can show on the other.

Why two ascending tracks. Their angles differ by 8°. The steeper one passes through more canopy.

Why tracks are not merged. Each has its own geometry and calibration, the conversion from recorded signal to echo strength. Each site is measured on each track, then the three are combined per site.

Dates. 20 June to 16 November 2026, 32 acquisitions. Dates before 1 June are excluded. The October 2025 to January 2026 images were beta processing with different calibration, and every fall date fell in it, so season could not be told from processing. Two dates on track 26 are dropped: 22 July has no valid pixels, and 8 September matches no other date of its track.

Seasons. Summer 1 June to 30 September. Sentinel-2 forest greenness reached 97% of summer level by 1 June and stayed above 88% through 4 October. Fall 21 October to 30 November, the first NISAR date after the last full-leaf Sentinel-2 scene on 17 October. Full leaf-off is not confirmed because clouds hid late October. Both windows were fixed before any test.

Source. NASA ASF DAAC through ASF Vertex, search.asf.alaska.edu. New dates moved to a new collection name on 23 October, so the download searches every NISAR collection.

Likely question. Why this band and not another? Answer above under Why L-band.

## Slide 5. How each site is measured

On the slide. One pad up close in lidar and both radar look directions, and the three measurement steps.

Background. The pad cannot be seen by eye in speckle, the random grain in every radar image. That is why sites are measured as contrasts and pooled.

Steps and reasons.
- Feature brightness minus a ring of ground around it. Ring 10 to 30 m around pits, 20 to 60 m around pads. The ring cancels slope, canopy and viewing angle. The inner edge clears the feature by two pixels so a 2.5 m placement error cannot mix them. The outer edge stays within about one feature width so the ring shares the feature's slope and forest. These ring widths were set at first pass and the reasoning was checked afterward.
- The same at five control spots, copies of the outline 150 to 600 m away on unmapped ground. They show what chance gives. 150 m clears the feature's 60 m ring. 600 m keeps the same terrain. Five keeps the run to hours.
- The excess is the feature's value minus the median of its control spots. A Wilcoxon signed-rank test asks whether the excesses lean one way. Its p-value is the chance of a lean that large with no real effect. A bootstrap over sites gives the 95% interval.

Why power is averaged before dB. Brightness is skewed. Averaging in dB, or comparing a few pixels with hundreds, pulls small areas dark. An early trial without this showed pits 2.4 dB darker when they were not.

Known limit. With five control spots the numbers can shift with which spots are drawn. A 40-spot run with a swap test is the stability check.

## Slide 6. Placing the radar on the lidar ground

On the slide. The cross-section schematic.

What was wrong. NASA places pixels with an elevation model that sits partway up the canopy in forest. Against the lidar this put features 8 to 12 m off, on all three tracks, always away from the satellite, and more under taller canopy. That pattern is what a too-high elevation model produces.

What we did. Our own geocoder places each RSLC on the lidar ground plus 10% of canopy height. Of the heights tested (0, 10, 25 and 50%), 10% matched best. Then each date and each track is tied to the lidar.

How we know it is on the lidar ground. The lidar is used to simulate radar brightness from slope facing the satellite. That simulation is cross-correlated with each image in 48 blocks. After placement 47 of 48 blocks agree within 2.5 m, half a pixel, and the median block offset is 1.0 to 1.4 m per track.

Limit. This check is not independent, because the same simulation fixed each track's offset. The independent checks are a known building passing the steel screen and, ideally, corner reflectors at surveyed points.

Why it matters. A pit is only a few 5 m pixels across. At 8 to 12 m the test would measure the rim or the forest.

We did not build a radar elevation model. The lidar is the reference.

Likely question. Which step is most likely to fail at your site? Answer: placement, because a leftover offset of a few metres smears a pit into its ring. It shows as blocks failing the 2.5 m gate or offsets growing with canopy height.

## Slide 7. The tests

On the slide. Six tests, each with its signal, reason and key choice.

| Test | Signal | Why it could show | Key choice |
|---|---|---|---|
| Pit brightness | Amplitude | A pit changes slope, soil and canopy gaps at pixel scale | Ring 10 to 30 m, summer and fall, HH and HV |
| Pad brightness | Amplitude | A graded pad scatters differently from forest floor | Ring 20 to 60 m |
| Pad coherence | Phase | Work on a pad scrambles the surface between passes | Flag drops past 99% of control-spot pairs |
| Steel | Amplitude | Casing and tanks give strong, steady echoes | Slide 8 |
| Pool pits | Amplitude | Calm water reflects radar away | Pools found from lidar before the radar |
| Motion | Phase | A settling pit or creeping slope would move | Tracks 90 and 162 must agree |

Reasons for the key values.
- Coherence window 5 × 5, 25 looks. Coherence estimates are biased upward with few looks, and 25 keeps that bias small (Touzi et al. 1999).
- Pairs up to 24 days apart, two revisits. Longer pairs lose coherence under forest regardless of disturbance.
- 99% of control-spot pairs is a 1% false-alarm rate, so the expected chance count comes straight from the control spots.
- Motion uses a coherence mask of 0.45. At 0.45 with 25 looks, one pair's phase noise is about 0.28 radians, about 5 mm.
- A 1 km low-pass removes atmospheric delay, which varies over kilometres. Targets are under 100 m.
- HH is sent and received horizontal and favours ground and structures. HV is sent horizontal and received vertical and favours canopy.

Most of these values were set at first pass. Their reasons were worked out afterward.

Likely question. What would a second track, a second sensor or ground data add? Answer: a second track rules out a viewing-direction artefact, and real motion must agree between tracks 90 and 162. A second sensor (Sentinel-1) would rule out a NISAR processing artefact. Ground data, surveyed points or corner reflectors, would test placement independently.

## Slide 8. Persistent scatterers

On the slide. Definition, the three step 1 rules with sources, and why step 2 waits.

Background. A persistent scatterer is a pixel whose echo stays strong and steady over many dates, usually a hard object. Step 1 selects them. Step 2 reads motion from their phase.

| Rule | Value | Source |
|---|---|---|
| Steadiness, amplitude's standard deviation over dates divided by its mean | under 0.25 | Ferretti, Prati and Rocca 2001. Pure speckle sits near 0.52 |
| Brightness above the 250 m median | 3 robust SD or more | Usual outlier rule. 1 SD is 2.2 to 2.4 dB, so 6.5 to 7.2 dB |
| Hit radius | 6 m | Half a pixel diagonal, 3.5 m, plus 2.5 m placement |

Notes.
- Only the 0.25 comes from the literature. Ferretti and colleagues designed it for about 30 dates. 9t has 8 to 12, so speckle passes more often.
- Robust SD is 1.4826 × the median absolute deviation. It ignores a few bright targets. Three SD leaves about 0.13% of pixels by chance under a normal curve. It replaced a fixed 6 dB on 23 November, which had no recorded reason.
- 6 m replaced 15 m on 23 November. 15 m dated from before lidar placement. Error in DEP well coordinates is not in the budget because it cannot be measured here.
- The 250 m window is more than twice the largest pad, so a pad cannot set its own background. Set at first pass.
- Step 2 needs about 20 dates on one track. It waits on new dates.

Likely question. What result would show that your design does not work? Answer: the known building at 41.502787, -79.519712 failing the steel screen. If it cannot find a building it cannot find a wellhead.

## Slide 9. Checks and risks

Independent checks. A known building should pass the steel screen. Real features should show on more than one track. Surveyed points or corner reflectors would test placement without the lidar simulation.

Signs the design failed. Control spots differ among themselves as much as from features. A contrast shows on one track only. A contrast grows when placement is shifted 5 to 10 m, which would mean the ring, not the feature, carries it.

| Risk | How we would notice | What we would do instead |
|---|---|---|
| Images not on the lidar ground | Blocks fail the 2.5 m gate, or the building sits off its spot | Re-solve offsets, set corner reflectors, widen the hit radius |
| Too few dates, 8 to 12 per track | Steady pixels exceed the 0.13% expected, or flood open fields | Require two tracks, raise the cutoff, add dates |
| Signal smaller than noise | Intervals span zero, or shift with the control-spot draw | 40 control spots, matched on canopy and slope |
| Decorrelation under leaves and wet snow | Coherence under 0.45 over most of a track | Short pairs, coherence mask, lean on amplitude |

## Slide 10. Plan

The eight weeks of the course, from the dated analysis log.

| Week of | Step |
|---|---|
| 5 October 2026 | Fetch NISAR windows over 9t, first tests, find the 8 to 12 m offset |
| 12 October | Write the geocoder, place images on lidar heights, rerun |
| 19 October | Fix review defects, test with 40 control spots |
| 26 October | Corrected scoring, compare with optical greenness and leaf state |
| 2 November | Outside reviews of the decisions, checkpoint deck |
| 9 November | Checkpoint talk on 10 November, Sentinel-1 cross-check, question narrowed |
| 16 November | Exclude beta dates, add November dates |
| 23 November | Date rule in code, rerun 9t tests, justify thresholds, write design |

Needs. About 80 MB of radar data per date, a few GB in all. One laptop. Python with h5py, numpy, scipy, rasterio and geopandas.

Beyond the course. Matched control spots, pits against hollows with no well, the 40-spot stability run, and persistent-scatterer motion at about 20 dates per track.

Why the design changed after the checkpoint. The checkpoint asked whether radar raises recall at a fixed inspection budget. That is prediction. Since 15 November the question is whether a marker exists at known sites, because prediction depends on that answer. Since 19 November only June 2026 dates are used, and since 23 November only tile 9t.

AI disclosure. Claude (Anthropic) wrote and ran much of the processing code, produced the figures, and drafted the slide text from my direction. I set the question, site, band and constraints, reviewed every step, and the design decisions are mine.

## References

1. NASA ASF DAAC. NISAR L1 RSLC and L2 GSLC. https://search.asf.alaska.edu/
2. USGS 3DEP lidar, PA_WesternPA_2019_D20. https://www.usgs.gov/3d-elevation-program
3. Pennsylvania DEP oil and gas locations, April 2026. https://www.dep.pa.gov/DataandTools/Pages/GIS.aspx
4. Ferretti, Prati, Rocca (2001). Permanent scatterers in SAR interferometry. IEEE TGRS 39(1), 8–20. https://doi.org/10.1109/36.898661
5. Touzi, Lopes, Bruniquel, Vachon (1999). Coherence estimation for SAR imagery. IEEE TGRS 37(1), 135–149. https://doi.org/10.1109/36.739146
6. Berardino, Fornaro, Lanari, Sansosti (2002). Small baseline differential SAR interferograms. IEEE TGRS 40(11), 2375–2383. https://doi.org/10.1109/TGRS.2002.803792
