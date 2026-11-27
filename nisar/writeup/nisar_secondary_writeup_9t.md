# NISAR L-Band Radar at Known Oil and Gas Well Sites: Baseline and Stricter Controls on Tile 9t

## Abstract

Western Pennsylvania holds thousands of old oil and gas wells, and many have no reliable location. Airborne lidar finds the pads and pits these wells left behind, but it is flown once. This study asks whether NISAR L-band radar, which passes every 12 days, shows a repeatable signal at well sites mapped from lidar on one tile (9t, Venango County). We tested pit and pad brightness, pad coherence, and steel with 32 dates from June to November 2026. We then re-ran every test with control spots matched on slope, a terrain correction, and per-track scoring. The steel excess at pads came from bright slopes, not hardware. Pad coherence fell to borderline. Pads darker in fall (HH, about −0.13 dB) and pits brighter in summer (HV, about +0.16 dB) held under every control.

## 1. Introduction

A well that is not found cannot be plugged. Lidar shows the pads and pits around old wells, but a survey is a single snapshot. NISAR's L-band signal (24 cm wavelength) passes through leaves and images the same spot every 12 days. If a well site leaves a mark in the radar, NISAR could add repeat looks to a one-time lidar map. We test at known sites first. A marker that does not show at a known well cannot find an unknown one.

The expected signals are small. A pit or pad should differ from its surroundings by a few tenths of a decibel (dB). One pixel varies by about 2.3 dB between dates because of speckle, the random grain in every radar image. So hundreds of sites must be pooled. Steel casing or a tank should be much brighter, about 6.5 to 7 dB above background, and steady over time.

## 2. Study Area and Data

Tile 9t is a 4.5 km lidar tile in Venango County with steep forested slopes and incised valleys. Annotators mapped 506 pits and 650 pads from the lidar. Well records come from the Pennsylvania DEP.

NISAR geocoded single-look complex images came from the NASA ASF archive, in HH and HV at 5 m spacing. Three tracks cover the tile (Table 1). NISAR looks left, so the descending track views slopes from the east and the ascending tracks view them from the west. We used every track because a slope that is bright from one side is dark from the other.

Table 1. NISAR tracks over tile 9t.

| Track | Pass | Looks toward | Incidence | Dates |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

Dates run from 20 June to 16 November 2026. NASA changed its processor on 23 October, which darkened later dates by 0.3 to 0.4 dB. The step was equal over open ground and forest, so contrasts against nearby ground cancel it.

## 3. Methods

### 3.1 Placing the radar on the lidar ground

NASA's elevation model sits partway up the canopy, which put the radar 8 to 12 m off the lidar. At that error a pit test would measure rims and forest. We wrote a geocoder that places every image on the lidar ground plus 10% of canopy height, and removed a 1.3 m datum offset. Each track still needed a fitted range offset of 2 to 4 m.

### 3.2 Measuring a site

Each feature is compared with a ring of ground around it (10 to 30 m for pits, 20 to 60 m for pads). The ring cancels slope, canopy and viewing angle. The same contrast is taken at five control spots placed 150 to 600 m away on unmapped ground. The excess is the feature's contrast minus theirs, tested with a Wilcoxon signed-rank test. Seasonal effects were also tested date by date, because every site shares the same weather.

A persistent scatterer is a pixel whose echo stays strong and steady over many dates, as steel does and forest does not. We kept pixels whose amplitude varied less than 0.25 of its mean (Ferretti et al., 2001) and that were 3 or more standard deviations brighter than the ground within 250 m. A well or pad counted as hit if a kept pixel fell within 6 m.

### 3.3 Baseline and stricter controls

The first full run (26 November) matched control spots on canopy only and pooled the three tracks. It gave a steel lead and a coherence lead at pads, plus two seasonal effects (Table 2). Steel at DEP wells matched control spots at every well status, even though a known building passed the same screen. Each later check targeted one way this baseline could be wrong.

Pads are flat benches cut into hillsides. Control spots matched only on canopy could sit on different slopes, and slope alone changes radar brightness. So we re-picked control spots to match each pad on canopy (within 0.15) and lidar slope (within 5°).

Slopes facing the radar return more echo and can look like steel. We used the lidar terrain to predict how strongly each pixel is lit and divided it out.

Real steel should show from every viewing side. Pooled tracks can hide one that disagrees. So steel was scored on each track separately, with a matched swap test and a test stratified by pad size and canopy. Two filters tried to separate steel from bright forest. One used the HH to HV ratio. The other used sub-look coherence, where a point target looks alike in images made from the two halves of the radar aperture.

Pits might be brighter simply because they are dips that hold moisture. So we found natural hollows in the lidar. These are closed depressions deeper than 0.2 m with a 10 to 300 m² floor, at least 40 m from any DEP well and 20 m from any mapped pit, pad or road. The same dip finder picks up 340 of the 506 mapped pits. It left 90 well-free hollows.

We also compared the fitted range offsets with the expected tropospheric delay (Saastamoinen, 1972), since our geocoder models only the ionosphere.

## 4. Results

Table 2. Baseline and stricter-control results.

| Test | Baseline | Stricter controls | Reading |
|---|---|---|---|
| Steel at pads | 19.3% vs 16.6%, p 0.12 | Slope-matched 19.6% vs 14.1%, p 0.0009. Terrain-corrected 12.6% vs 10.1%, p 0.065 | Bright slopes, not steel |
| Steel by track | Pooled | Tracks 26 and 90 favour pads, track 162 reverses | Geometry |
| Pad coherence | 220 vs 182 drops, p 0.007 | 205 vs 182, p 0.056 | Borderline |
| Pads, fall HH | −0.15 dB | −0.12 to −0.13 dB | Holds |
| Pits, summer HV | +0.16 dB | +0.16 to +0.21 dB | Holds |
| Hollows, summer HV | Not tested | +0.09 dB (−0.29 to +0.41), p 0.48 | Unsettled |
| HH/HV, sub-look | Not tested | No pad signal | No gain |

Slope matching first made the steel excess look stronger. Terrain correction then removed most of it. Steel on the flat pad would have survived that correction, so the excess came from lit slopes beside pads.

Coherence drops still lean toward active-well pads (46% of drops, 35% of pads). Both seasonal effects held with 40 control spots and with slope-matched ones.

The hollows came out between zero and the pit value, and their range includes both. The test cannot say whether pit brightness marks a well or any wet dip.

The fitted offsets averaged 2.88 m against a predicted dry delay of 2.97 m (0.73 m RMS), so they mostly absorb the troposphere. A placement check against buildings failed because 8 of 9 buildings lie outside the lidar.

## 5. Discussion

Without slope matching and terrain correction, a terrain effect would have been reported as steel. But only 469 of 650 pads had five matched control spots, and the dropped pads are likely the steepest. Terrain correction could dim hardware against a cut bank, but not hardware on the flat bench.

The sub-look result is weak evidence. Its tile median (0.35 to 0.43) sat above the 0.3 expected for pure speckle, so the half-images were probably not fully independent. Matching and hollow thresholds were set before results were seen, but other values could move the borderline p-values. Site-level p-values treat sites as independent, so the date-level test is the one to quote for the pad effect.

No result is checked against hardware on the ground. They show pads and pits differ from chance, not that a given pad has a pumpjack.

## 6. Conclusion

NISAR does not see well hardware at pads or wells on tile 9t. Pads read darker in fall HH and pits read brighter in summer HV, and both held under every control we tried. Whether the pit signal is specific to wells is still open.

Pads labelled with and without hardware from leaf-off imagery would test a steel detector against a known answer. A second tile would supply enough hollows to settle the pit question. A corner reflector would check placement. Dry fall dates in 2027 would separate season from wet ground in the pad result.

## References

Ferretti, A., Prati, C., Rocca, F. (2001). Permanent scatterers in SAR interferometry. IEEE TGRS 39(1), 8–20.

Saastamoinen, J. (1972). Atmospheric correction for the troposphere and stratosphere in radio ranging of satellites. Geophys. Monogr. 15, 247–251.
