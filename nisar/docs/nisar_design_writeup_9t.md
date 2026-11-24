<style>
@page { size: Letter; margin: 0.6in; }
body, h1, h2, h3, p, li, td, th, code, em, strong { font-family: "Times New Roman", Times, serif; font-size: 11pt; color: #000; }
body { line-height: 1.2; }
h1, h2, h3 { font-weight: bold; margin: 7px 0 2px; border: none; padding: 0; }
p, ul, ol { margin: 3px 0; }
table { border-collapse: collapse; width: 100%; margin: 4px 0; break-inside: auto; }
th, td { border: 1px solid #000; padding: 2px 4px; vertical-align: top; background: none; text-align: left; }
th { font-weight: bold; }
code { background: none; padding: 0; }
img { max-width: 58%; display: block; margin: 4px auto 0; filter: grayscale(100%); }
</style>

# NISAR L-band radar at known oil and gas well sites, tile 9t, western Pennsylvania

CIVE 6359 capstone design write-up. Colton Goodrich. Draft of 2026-11-23.

## 1. Question and site

Question. At known well sites on tile 9t, does NISAR L-band radar show a repeatable contrast at well pads, pits or surface steel that differs from nearby ground with no well?

Site. Tile 9t is a 4.5 km square in Venango County, Pennsylvania, near 41.50° N, 79.54° W. It is forested Appalachian Plateau ground with 150 years of oil drilling. Lidar mapping gives 506 pits and 650 pads, of which 645 have a full ring of surrounding ground for testing. Pennsylvania DEP lists 1,068 wells in the tile. A pad is the cleared, graded ground around a well. A pit is the dug hollow beside it.

Expected signal. A pit or pad should change backscatter by a few tenths of a decibel at most, because it is a small change in slope and roughness under the same forest. One site cannot show this. Across sites, the per-site excess spreads by about 0.9 dB for pits and 0.5 dB for pads (robust standard deviation, summer). With 506 pits the smallest median shift the test can detect is about 0.14 dB. With 645 pads it is about 0.07 dB. These limits use 2.8 standard errors, the usual value for 80% power at a 5% two-sided test, and a factor of 1.25 for using the median. Steel should stand out by more: a pixel at least 6.5 to 7.2 dB above its surroundings (section 3 gives the reason). Motion at a pit must exceed about 12 mm in 12 days. That is twice the 6 mm phase noise of one interferogram pair at a pit, a two-standard-deviation margin.

Why a radar can see it. Lidar maps these features but is flown once. NISAR repeats every 12 days at no cost. A pit or pad changes slope and roughness at the scale of a 5 m pixel. Steel gives a strong, steady echo. Work on a pad scrambles the surface between passes.

## 2. Data

Mission and band. NISAR, L-band, 24 cm wavelength. The targets sit under deciduous canopy. A 24 cm wave passes through leaves to the ground better than C-band (5.5 cm) or X-band (3 cm), and its phase stays stable longer under forest.

Product. Level 2 geocoded single-look complex images (GSLC), HH and HV, 5 m grid, and Level 1 single-look complex images in radar geometry (RSLC). Both keep amplitude and phase. The RSLC is needed to place each image on the lidar ground (section 3).

Amplitude and phase. Amplitude is the strength of the echo. Brightness is its square, echo power, in decibels. Amplitude depends on roughness, slope, moisture and metal, so it is where a change in the ground surface would show. It can be read from a single image. Phase is where in its cycle the wave returns. The phase difference between two dates on one track measures movement toward or away from the satellite, and coherence measures how alike the signal stays. Phase answers whether a site moves or is disturbed. It cannot be compared across tracks, and under deciduous forest L-band phase can lose stability within 12 days. The pit, pad, steel and water tests therefore use amplitude. Only pad disturbance and motion, which amplitude cannot measure, use phase.

Geometry at 9t.

| Track | Pass | Looks toward | Incidence angle | Dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

These are all the NISAR tracks over 9t. Ascending and descending passes see each slope from opposite sides, so a feature in shadow on one can show on the other. Each track has its own geometry and calibration, so every measure is made per track and combined only per site.

Dates. 2026-06-20 to 2026-11-16, 12-day revisit, 32 acquisitions. Dates before 2026-06-01 are excluded. The October 2025 to January 2026 images were beta processing with different calibration, and every fall date fell in it, so season and processing could not be told apart. June 1 is the boundary between the two processing levels. Two dates on track 26 are dropped: 2026-07-22 has no valid pixels, and 2026-09-08 matches no other date of its track at any shift. A window is used when at least half its pixels are valid, so that each date covers most of the tile.

Seasons. Summer is 1 June to 30 September. Fall is 21 October to 30 November. Sentinel-2 vegetation index over closed forest on the tile reached 97% of its summer level by 1 June and stayed above 88% through 4 October 2026, so the summer window is full leaf. The last Sentinel-2 scene rated full leaf was 17 October, so fall starts at the first NISAR date after it. Clouds hid late October, so full leaf-off is not confirmed. Early October is in neither window because the canopy is changing. Both windows were fixed before any test used the new dates.

![Dates used on tile 9t](figures/nisar_dates_postjune.png)

Figure 1. Dates used per track on tile 9t. Triangles are the descending track, circles the ascending tracks. Shading marks the summer and fall windows.

Sources. NASA ASF DAAC through ASF Vertex, collections NISAR_L2_GSLC_PROVISIONAL_V1, NISAR_L2_GSLC_V1, NISAR_L1_RSLC_PROVISIONAL_V1 and NISAR_L1_RSLC_V1 [1]. Each date is read as a window over 9t by HTTPS range requests, so a 22.6 GB file need not be downloaded whole. Checked against USGS 3DEP lidar PA_WesternPA_2019_D20 [2], Pennsylvania DEP well locations [3] and pit and pad outlines drawn from that lidar.

## 3. Processing steps

| Step | Tool | Key choice and its reason |
|---|---|---|
| 1. Fetch windows over 9t | NASA CMR search, h5py, fsspec | Search every NISAR collection. New dates moved to a new collection name on 2026-10-23 |
| 2. Place each image on the lidar ground | Own geocoder in Python, from RSLC | Echo height set at the lidar ground plus 10% of canopy height. Of the heights tested (0, 10, 25, 50%), 10% matched a lidar simulation best |
| 3. Check placement against the lidar | Simulated brightness from lidar slope, cross-correlated in 48 blocks | A block passes within 2.5 m, half a pixel |
| 4. Season means per track | numpy | Power averaged before conversion to dB, because brightness is skewed and averaging dB biases small areas dark. A pixel needs valid values on half the season's dates |
| 5. Feature minus ring minus control spots | rasterio, geopandas | Ring 10 to 30 m around pits and 20 to 60 m around pads. Five control spots 150 to 600 m away |
| 6. Persistent-scatterer screen | numpy, scipy | Dispersion under 0.25, brightness 3 SD above the 250 m median, hit radius 6 m |
| 7. Coherence change at pads | Back-to-back pairs up to 24 days apart, 5 × 5 window | Event when a drop exceeds 99% of control-spot pairs |
| 8. Motion at pits and slopes | Interferograms, 5 × 5 looks to 25 m, summed pair phases [6] | 1 km low-pass removed, coherence mask 0.45 |
| 9. Statistics | scipy | Wilcoxon signed-rank on the per-site excess, bootstrap 95% interval |

Placement. NASA's GSLC places pixels with an elevation model that sits partway up the canopy in forest. Against the lidar this put features 8 to 12 m off, on all three tracks, always away from the satellite, and more so under taller canopy. That pattern is what a too-high elevation model produces. Re-placing each image on lidar heights removes it. To know the result is on the lidar ground, the lidar is used to simulate radar brightness from slope facing the satellite, and that simulation is cross-correlated with each image in 48 blocks. After placement, 47 of 48 blocks agree within 2.5 m, and the median block offset is 1.0 to 1.4 m per track. This check is not independent, because the same simulation fixed each track's offset. Section 4 gives the independent checks.

Reasons for the remaining values.

- Ring. The inner edge clears the feature by two pixels, so placement error of 2.5 m cannot put feature pixels in the ring. The outer edge stays within about one feature width, so the ring shares the feature's slope and forest. Pads are 40 to 100 m across, so their ring is wider. Ring pixels stay 5 m (pits) or 10 m (pads) clear of other features and roads, one and two pixels.
- Control spots. 150 m clears the feature's own 60 m ring with margin. 600 m keeps the spot on the same tile and terrain type. Five spots per site keeps the run to hours. A 40-spot run tests that results do not depend on which spots were drawn.
- Dispersion under 0.25. From Ferretti, Prati and Rocca [4]. Pure speckle sits near 0.52.
- 3 SD. Brightness above the 250 m median is centred on 0 dB. Its robust standard deviation (1.4826 × the median absolute deviation, which ignores a few bright targets) is 2.2 to 2.4 dB per track. Three SD is the usual outlier rule and leaves about 0.13% of pixels by chance under a normal tail. On 9t this is 6.5 to 7.2 dB.
- 250 m background. Fifty pixels, more than twice the largest pad, so a pad cannot set its own background, and smaller than the valley-side slopes that change brightness.
- 6 m hit radius. A target anywhere in a 5 m pixel is at most 3.5 m from its centre. Placement adds up to 2.5 m. Error in DEP well coordinates cannot be measured here and is not included.
- 5 × 5 window, 25 looks. Coherence estimates are biased upward with few looks. Twenty-five looks keeps that bias small [5] while staying near pad size.
- 24 days. Two revisits. Longer pairs lose coherence under forest regardless of disturbance.
- 99% of control-spot pairs. A false-alarm rate of 1%, so the expected count of events by chance is known directly from the control spots.
- Coherence mask 0.45. At 0.45 with 25 looks, one pair's phase noise is about 0.28 radians, about 5 mm, the same scale as the pit noise used in section 1.
- 1 km low-pass. Atmospheric delay varies over kilometres. Pits and pads are under 100 m, so removing variation longer than 1 km removes weather and keeps the targets.

## 4. How I would check the result

Independent evidence. A known building at 41.502787, -79.519712 should pass the steel screen. A real feature should show on more than one track, and real motion should agree between tracks 90 and 162. Surveyed points or corner reflectors would test placement without the lidar simulation. A Sentinel-1 C-band comparison at the same pits is a possible further check.

Results that would show something went wrong. Control spots differ among themselves as much as features differ from control spots. A contrast shows on one track only, or flips sign between the two ascending tracks. A contrast grows when the images are shifted 5 to 10 m, which would mean the ring and not the feature carries it. The building fails the steel screen.

## 5. What could go wrong

| Risk at 9t | How I would notice | What I would do instead |
|---|---|---|
| Images not on the lidar ground. NASA's elevation model sits in the canopy, and a leftover offset would smear a pit into its ring | Blocks fail the 2.5 m gate, offsets grow with canopy height, or the building sits off its mapped spot | Re-solve offsets per track, set corner reflectors, widen the hit radius by the measured offset |
| Too few dates. The dispersion rule was designed for about 30 dates. 9t has 8 to 12 per track | Steady pixels exceed the 0.13% expected by chance, or spread across open fields | Require two tracks, raise the cutoff, add dates as NASA releases them |
| Signal smaller than the noise | Intervals span zero, or results shift with the control-spot draw | Run 40 control spots per site, match control spots on canopy and slope |
| Decorrelation under leaves and wet snow | Coherence below 0.45 over most of a track | Use short pairs, mask by coherence, rely on amplitude tests |

## 6. Plan

The project ran over eight weeks of the course. The steps below are what was done each week, taken from the dated analysis log.

| Weeks of | Steps |
|---|---|
| 5 and 12 October 2026 | Fetch NISAR windows over 9t. First pit, steel, coherence and slope tests. Find the 8 to 12 m placement offset, write the geocoder, place images on lidar heights and rerun |
| 19 and 26 October | Fix defects found by two outside reviews. Test with 40 control spots. Compare against optical greenness, canopy and leaf state |
| 2 and 9 November | Two reviews of the decisions. Checkpoint talk on 10 November. Sentinel-1 cross-check. Narrow the question to markers at known sites |
| 16 and 23 November | Exclude beta dates, add the November dates, enforce the date rule in code, rerun all 9t tests, justify every threshold. Talk 1 December |

Beyond the course, the steps that remain are matched control spots, a comparison of pits with hollows that have no well, the 40-spot stability run, and persistent-scatterer motion once about 20 dates per track exist. Needs: about 80 MB of radar data per date, a few GB in all, one laptop, and Python with h5py, numpy, scipy, rasterio and geopandas.

## Bonus: a real product from the site

![Lidar beside NISAR summer HV over tile 9t](figures/nisar_tile_lidar_radar_9t.png)

Figure 3. Tile 9t. Left, lidar bare-earth hillshade, 1 m. Right, NISAR HV mean backscatter from track 162, the eight summer dates 2026-06-25 to 2026-09-29, placed on the lidar ground and averaged in linear power. Valleys and slopes match the lidar, which shows L-band reaching the ground under canopy. Terrain lighting dominates, speckle hides anything under tens of metres, and calibration is provisional.

## 7. Changes after the oral

[To be written after December 1.]

AI disclosure. Claude (Anthropic) wrote and ran much of the processing code, produced the figures, and drafted the text of the slides and this write-up from my direction; I set the question, site, band and constraints, reviewed every step, and the design decisions are mine.

## References

1. NASA ASF DAAC. NISAR Level 1 RSLC and Level 2 GSLC products. ASF Vertex, https://search.asf.alaska.edu/
2. U.S. Geological Survey. 3DEP lidar, project PA_WesternPA_2019_D20. https://www.usgs.gov/3d-elevation-program
3. Pennsylvania Department of Environmental Protection. Oil and gas locations, April 2026 export. https://www.dep.pa.gov/DataandTools/Pages/GIS.aspx
4. Ferretti, A., Prati, C., Rocca, F. (2001). Permanent scatterers in SAR interferometry. IEEE Transactions on Geoscience and Remote Sensing 39(1), 8–20. https://doi.org/10.1109/36.898661
5. Touzi, R., Lopes, A., Bruniquel, J., Vachon, P. W. (1999). Coherence estimation for SAR imagery. IEEE Transactions on Geoscience and Remote Sensing 37(1), 135–149. https://doi.org/10.1109/36.739146
6. Berardino, P., Fornaro, G., Lanari, R., Sansosti, E. (2002). A new algorithm for surface deformation monitoring based on small baseline differential SAR interferograms. IEEE Transactions on Geoscience and Remote Sensing 40(11), 2375–2383. https://doi.org/10.1109/TGRS.2002.803792
