# Looking for Orphaned Wells from Orbit: NISAR L-Band Radar at Known Well Sites in Western Pennsylvania

Colton Goodrich, University of Houston, November 2026

## Introduction

Our lidar work showed that old well sites leave clear marks on the ground. Pads, pits, and access roads are all visible once the canopy is stripped away. The catch is that a lidar survey is flown once, and flying it again is expensive. NISAR, the joint NASA and ISRO radar satellite, passes over the same ground every 12 days and its data is free. Its L-band signal has a wavelength of about 24 centimeters, long enough to pass through leaves and bounce off the ground underneath. So the obvious question is whether a well site shows up in the radar at all.

We decided to test this at sites we already know before trying to find anything new. If the radar cannot see a marker at a known well, it certainly cannot use that marker to find an unknown one. Our test area is tile 9t in Venango County, a 4.5-kilometer lidar tile with 506 mapped pits, 650 mapped pads, and 1,068 DEP well records.

The difficulty is that every radar image is covered in speckle, a random grain that makes a single pixel jump around by about 2.3 dB from one date to the next. A pit or pad is expected to differ from its surroundings by only a few tenths of a dB. In simple terms, the signal we are looking for is about ten times smaller than the noise in any one pixel. The only way around this is to pool hundreds of sites and look for a consistent lean. Steel is the exception. A wellhead, casing, or tank should return a strong, steady echo several dB brighter than the ground around it.

## Data

We used every NISAR date available over the tile from 20 June to 16 November 2026, which comes to 32 images across three tracks (Table 1). Each image has two polarizations at 5-meter spacing. HH is sent and received horizontally and favors the ground, while HV is received vertically and favors the canopy. NISAR looks to the left of its flight path, so the descending track sees slopes from the east and the two ascending tracks see them from the west. This matters because a hillside that faces the radar comes back bright and the same hillside seen from the other side comes back dark.

Table 1: NISAR tracks over tile 9t

| Track | Pass | Looks toward | Incidence | Dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

### Can the Radar See the Ground?

Before anything else, we had to know whether the signal reaches the ground under this forest at all. We never measured penetration directly, but three things in our data point the same way. When we lined the radar up against the lidar terrain, the hills and valleys matched best with the reflecting surface placed at about a tenth of canopy height, which is roughly 2 meters up in these stands. Ground under closed canopy is also barely brighter than open ground (AUC 0.50 to 0.56, where 0.5 means no difference). Likewise, dropping the leaves in fall barely changed anything (AUC 0.48 to 0.52). This fits the physics. Leaves are a few centimeters across, so the 24-centimeter wave passes them, while trunks and branches scatter it all year. In simple terms, the radar does see the ground, but every pixel also carries trunk echo that dilutes a small change on the surface.

## Methodology

### Placing the Radar on the Ground

Our first problem was that NASA's images did not line up with our lidar. They were off by 8 to 12 meters. NASA places each pixel using a global elevation model that sits partway up the tree canopy rather than on the ground, and on steep slopes that error shifts the pixel sideways. A pit is only a few pixels wide, so at that offset we would have been measuring rims and forest instead of pits. We wrote our own geocoder that places every image on the lidar ground surface. A later review caught a second, smaller error of 1.3 meters from a mismatch between the two coordinate frames, and that was fixed as well.

### Measuring a Site

Each feature is compared with a ring of ground around it, 10 to 30 meters out for pits and 20 to 60 meters out for pads. The ring shares the same slope, canopy, and viewing angle, so subtracting it removes most of what is not the feature. We then do the same thing at five control spots, which are copies of the outline dropped 150 to 600 meters away on ground with no mapped well features. If the pads are really different, they should lean further from their rings than the control spots do. For seasonal effects we also scored each date separately, since a single rainy day moves every pad at once.

For steel we used the persistent scatterer approach of Ferretti et al. (2001). A persistent scatterer is a pixel whose echo stays bright and steady over many dates, which is how steel behaves and how forest does not. We kept pixels that were steady (amplitude varying by less than a quarter of its mean) and bright (three standard deviations above the ground within 250 meters). A well or pad counted as a hit if one of these pixels sat within 6 meters of it.

### Tightening the Controls

The first full run gave us four results worth chasing. Pads seemed to hold slightly more steel than the control spots, pads lost coherence more often than chance, pads were darker in fall, and pits were brighter in summer. The pad results looked promising, but they made us suspicious of our control spots. A well pad is a flat bench cut into the side of a hill. Our control spots were matched to the pads on canopy cover but not on slope, and slope alone changes how bright the radar sees the ground.

So we rebuilt the test in three ways. First, we re-picked the control spots to match each pad on both canopy and slope. Second, we used the lidar terrain to predict how brightly each pixel is lit by the radar and divided that out, which removes the bright faces of hills. Third, we scored each track on its own. Real steel should look bright from every direction, whereas a terrain effect should flip depending on which way the radar is looking. We also tried two filters meant to separate steel from bright forest.

The pit result raised its own question. Pits might be brighter in summer simply because they are dips that hold moisture, regardless of any well. To check this we searched the lidar for natural hollows of the same size and depth that sit well away from any well, pit, pad, or road. It turned up 90 hollows that fit.

## Results

Table 2: First run versus stricter controls

| Test | First run | Stricter controls | Reading |
|---|---|---|---|
| Steel at pads | 19.3% vs 16.6%, p 0.12 | Slope-matched 19.6% vs 14.1%, p 0.0009. Terrain-corrected 12.6% vs 10.1%, p 0.065 | Bright slopes, not steel |
| Steel by track | Pooled | Tracks 26 and 90 favor pads, track 162 reverses | Geometry |
| Pad coherence | 220 vs 182 drops, p 0.007 | 205 vs 182, p 0.056 | Borderline |
| Pads, fall HH | −0.15 dB | −0.12 to −0.13 dB | Holds |
| Pits, summer HV | +0.16 dB | +0.16 to +0.21 dB | Holds |
| Hollows, summer HV | Not tested | +0.09 dB (−0.29 to +0.41) | Unsettled |

The steel result is the clearest example of why the extra controls mattered. Matching on slope actually made the pads look better at first. Once the bright hillsides were removed, though, most of the gap closed. Steel sitting on the flat part of a pad would have survived that correction, so what we had been seeing was the lit slope beside the pad. Track 162 sealed it with fewer hits on pads than on control spots.

Pad coherence fell to borderline, while both seasonal effects held.

The hollows landed between zero and the pit value, with a range wide enough to include both. In simple terms, the test could not tell us whether the pit signal is about wells or about dips. On a tile this size there are just not enough well-free hollows to answer it.

## Discussion

### What Did Not Work

Steel detection did not work at pads or at DEP wells, and neither steel filter found anything. The building check we hoped would confirm our placement also failed, since 8 of the 9 buildings we could use sit outside the lidar coverage.

### Limitations

Matching on slope came at a cost. Only 469 of the 650 pads had five matched control spots, and the ones that dropped out are likely the steepest. Most importantly, nothing here has been checked against hardware on the ground. We can say pads and pits differ from chance, but we cannot point to a pad and say it has a pumpjack on it.

## Future Work

The biggest gap is a labelled set of pads with and without hardware from leaf-off aerial imagery, so a steel detector can be tested against a known answer. A second lidar tile would supply enough natural hollows to settle the pit question. A corner reflector, a small metal target with a known position, would finally check our placement. Lastly, dry dates in the fall of 2027 would tell us how much of the pad darkening is season and how much is wet ground.

## Conclusion

NISAR does not see well hardware on tile 9t. What first looked like steel at pads turned out to be the bright faces of the hills they are cut into. The radar does pick up something, though. Pads read darker in fall and pits read brighter in summer, and both held up under every control we threw at them. Whether the pit signal belongs to wells or to any wet dip in the ground is still an open question.

## References

Ferretti, A., Prati, C., & Rocca, F. (2001). Permanent scatterers in SAR interferometry. IEEE TGRS, 39(1), 8–20.
