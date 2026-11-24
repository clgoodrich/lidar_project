# Slide 1 notes. Question and site

What the slide says. On tile 9t, which pixels does NISAR show as persistent scatterers, and do they sit at oil and gas wells more often than at nearby ground with no well? The site map shows the tile with its mapped pads and pits. The expected signal and the reason a radar can see it sit beside the map.

The site. Tile 9t is a 4.5 km square in Venango County, Pennsylvania, centred near 41.50° N, 79.54° W. It is forested Appalachian Plateau ground with steep, incised valleys and 150 years of oil drilling. Pennsylvania DEP lists 1,068 wells inside the tile. Of these, 617 are active, 271 are plugged, 174 are abandoned or orphaned, and 10 were permitted but never drilled. Lidar mapping from 2019 gives 650 well pads and 506 pits. A well pad is the cleared, graded ground around a well. A pit is the dug hollow beside it.

What a persistent scatterer is. A persistent scatterer is a pixel whose echo stays strong and nearly unchanged over many dates. Hard objects such as steel structures and buildings behave this way. Forest does not, because leaves and branches move between passes, so its echo changes from date to date.

Why wells. A producing well often has steel above ground: the casing, which is the steel pipe lining the well, a pumpjack, tanks and pipe. Steel is a strong, stable reflector at radar wavelengths. A vertical casing standing on flat ground forms a corner with the ground, and a corner returns energy back toward the satellite. If wells carry steel that the radar can see, pixels at wells should pass a persistent-scatterer screen more often than pixels on ordinary ground.

The expected signal, with numbers.
- A persistent-scatterer candidate is a pixel at least 6.5 to 7.2 dB brighter than the ground within 250 m, whose amplitude varies over dates by less than a quarter of its mean.
- By chance, a pixel passes both rules at most about 0.13% of the time. The brightness rule alone sets that ceiling (slide 3).
- A well counts as hit if a candidate lies within 6 m. Five pixels fall within that radius. A well with no steel is therefore hit by chance on one track at most about 0.65% of the time, and on any of three tracks at most about 1.9%.
- With 617 active wells and five control spots each, about 3,000 control spots, the design can detect a well hit rate about 1.7 percentage points above the control-spot rate. That uses 2.8 standard errors, the usual value for 80% power at a 5% two-sided test.

Why a radar can see it. Lidar maps pads and pits but cannot see a casing under canopy, and it is flown once. NISAR repeats every 12 days at no cost. Its 24 cm L-band wave passes through leaves, so the canopy flickers less in the echo and a steel target stands out more than it would at shorter wavelengths.

Questions to expect.
- How big is your signal compared with the noise? A target must clear 3 robust standard deviations of the tile's own brightness spread, about 2.3 dB per standard deviation. Chance alone hits about 1.9% of wells over three tracks, so the test looks for a well rate clearly above that.
- What would show the design does not work? A known building at 41.502787, -79.519712 failing the screen. If the screen cannot find a building, it cannot find a wellhead.

<!-- pagebreak -->

# Slide 2 notes. Data

What the slide says. 32 NISAR L-band dates on three tracks, June to November 2026, over all of tile 9t. The table lists mission and band, product, tracks and geometry, dates and count, source, and the data checked against. The figure shows the dates used per track.

Mission and band. NISAR, the NASA-ISRO radar satellite, at L-band, a 24 cm wavelength. The wells sit under deciduous canopy. A 24 cm wave passes through leaves to the ground better than C-band (5.5 cm) or X-band (3 cm). Under L-band the canopy contributes a smaller, steadier share of the echo, which matters for a test built on steadiness.

Product. Level 2 geocoded single-look complex images (GSLC), HH and HV, on a 5 m grid. Level 1 single-look complex images in radar geometry (RSLC) are also used, because they let each image be placed again on the lidar ground (slide 3). The persistent-scatterer screen uses HH. HH is sent and received horizontally and favours ground and hard structures. HV is sent horizontally and received vertically and favours canopy volume.

Why amplitude and not phase. Amplitude is the strength of the echo. Phase is where in its cycle the wave returns. Persistent scatterers are defined by stable phase, but measuring phase stability needs a long, co-registered and unwrapped stack. Ferretti, Prati and Rocca (2001) showed that for strong targets the spread of amplitude over dates tracks the spread of phase. The screen therefore uses amplitude. It needs no unwrapping and works with the 8 to 12 dates per track available here. Reading motion from the phase of the selected pixels is a later step that needs about 20 or more dates per track.

Tracks and geometry.

| Track | Pass | Looks toward | Incidence angle | Dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

These are all the NISAR tracks over 9t. Ascending means the satellite is heading north. Descending means heading south. Incidence angle is the beam's angle from vertical. The two directions see each object from opposite sides, so a casing in a slope's shadow on one pass can show on the other. A candidate seen on two tracks is unlikely to be noise. Each track has its own geometry and calibration, so the screen runs per track and tracks are compared only at the end.

Dates and why. 20 June to 16 November 2026, 12-day revisit, 32 acquisitions. Dates before 1 June are excluded. The October 2025 to January 2026 images were beta processing with a different calibration. Mixing two calibrations in one stack would inflate every pixel's amplitude spread and break the steadiness rule. June 1 is the boundary between the two processing levels. Two dates on track 26 are dropped: 22 July has no valid pixels, and 8 September matches no other date of its track at any shift.

Source. NASA ASF DAAC through ASF Vertex, search.asf.alaska.edu. Each date is read as a small window over 9t by HTTPS range requests, instead of downloading a 22.6 GB file. New dates moved to a new collection name on 23 October, so the search covers every NISAR collection.

Checked against. USGS 3DEP lidar, project PA_WesternPA_2019_D20, and Pennsylvania DEP well locations and status, April 2026 export.

Question to expect. Why this band and not another? Because the target sits under leaves. L-band reaches through the canopy and keeps the canopy echo steadier than C-band or X-band, so steel is easier to separate from forest.

<!-- pagebreak -->

# Slide 3 notes. Processing steps and what could go wrong

What the slide says. Five steps from download to result, each with its tool and key choice, and three risks, each with how it would be noticed and what to do instead.

Step 1. Fetch windows over 9t and place them on the lidar ground. Tool: h5py and our own geocoder. NASA places pixels with an elevation model that sits partway up the canopy in forest. Against the lidar this put features 8 to 12 m off on all three tracks, always away from the satellite and more under taller canopy, which is what a too-high elevation model produces. Our geocoder places each image on the lidar ground plus 10% of canopy height. Of the heights tested, 0, 10, 25 and 50%, 10% matched best.

Step 2. Tie dates and tracks to the lidar. Tool: a lidar backscatter simulation. The lidar is used to simulate radar brightness from slope facing the satellite, and the simulation is cross-correlated with each image in 48 blocks. A block passes within 2.5 m, half a pixel. After placement 47 of 48 blocks pass, and the median block offset is 1.0 to 1.4 m per track. This check is not independent, because the same simulation fixed each track's offset.

Step 3. Amplitude statistics per track. Tool: numpy. Mean HH power and amplitude dispersion over all post-June dates. Amplitude dispersion is the standard deviation of amplitude over dates divided by its mean.

Step 4. Persistent-scatterer screen. Tool: numpy and scipy.
- Dispersion under 0.25, the standard cutoff of Ferretti, Prati and Rocca (2001). Pure speckle sits near 0.52, so 0.25 asks for half the variability of natural ground.
- Brightness at least 3 robust standard deviations above the median within 250 m. The robust standard deviation is 1.4826 times the median absolute deviation, which ignores a few bright targets. On 9t it is 2.2 to 2.4 dB per track, so the cutoff is 6.5 to 7.2 dB. Three standard deviations is the usual outlier rule and leaves about 0.13% of pixels by chance.
- The 250 m window is fifty pixels, more than twice the largest pad, so a pad cannot set its own background, and smaller than the valley sides that change brightness. It was set at first pass and the reason worked out afterward.
- Hit radius 6 m: a target anywhere in a 5 m pixel is at most 3.5 m from the pixel centre, plus 2.5 m placement.

Step 5. Compare wells with control spots. Tool: scipy. Five control spots per well, 150 to 600 m away, at least 60 m from every well and pad, with the same canopy cover within 0.15 because open ground and forest give different brightness. Fisher's exact test compares hit rates by DEP status. Never-drilled permits are a negative control and should be hit only at the control-spot rate.

Risk 1. Images not on the lidar ground. A leftover offset of a few metres moves a target outside the 6 m radius. Noticed when blocks fail the 2.5 m gate, the known building sits off its spot, or the well hit rate peaks when the images are shifted. Instead: re-solve offsets per track, set corner reflectors at surveyed points, widen the radius by the measured offset.

Risk 2. Too few dates. The dispersion rule was designed for about 30 dates. 9t has 8 to 12 per track, so speckle passes more often. Noticed when the pass fraction exceeds the 0.13% expected or candidates spread across open fields. Instead: require a candidate on two tracks, raise the cutoff, add dates as NASA releases them.

Risk 3. No steel left to see. Plugged and orphaned wells often have the casing cut off or buried, and a casing is far smaller than a 5 m pixel. Noticed when the building passes but wells match the control-spot rate. Instead: compare by DEP status, since active wells keep pumpjacks and tanks.

Question to expect. Which step is most likely to fail at your site? Placement, because a pit or casing is only a pixel or two wide and a few metres of offset moves it out of the hit radius.
