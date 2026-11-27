# NISAR L-band at known oil and gas wells, tile 9t: technical write-up

Written 2026-11-25, revised the same day after an outside review (section 12). Findings rewritten 2026-11-26 after a second review and a full rerun (sections 5 to 8). Covers all NISAR work on tile 9t that uses dates from 2026-06-01 onward.
Every number comes from the result files listed in section 13. Earlier versions of the results, which used beta dates or other tiles, are withdrawn (section 10).

---

## 1. Question

Do known oil and gas wells on tile 9t hold a NISAR persistent scatterer? A persistent scatterer is a pixel whose echo stays strong and steady over many dates.

Supporting questions:
- Do lidar-mapped pits and pads differ from their surroundings in radar brightness?
- Do pads lose phase coherence more often than background ground?
- Do pits or slopes show measurable motion?

The work measures contrasts at known sites. It does not predict, rank or discover new wells.

*Why known sites first.* A marker that does not show where a well is known to sit cannot help find unknown wells.

*Why radar.* Lidar maps pits and pads under canopy, but it is flown once. NISAR repeats every 12 days at no cost. Its 24 cm L-band wave passes through leaves better than C-band (5.5 cm) or X-band (3 cm).

## 2. Study area

- Tile 9t is a 4.5 km square in Venango County, Pennsylvania, centred near 41.50° N, 79.54° W.
- It is forested Appalachian Plateau ground, with steep incised valleys and about 150 years of oil drilling.
- Pennsylvania DEP lists 1,068 wells in the tile. 617 are active, 271 plugged, 174 abandoned or orphaned and 10 permitted but never drilled.
- Lidar mapping from 2019 gives 650 well pads and 506 pits. A pad is the cleared, graded ground around a well. A pit is the dug hollow beside it.

## 3. Data

### 3.1 Radar

| Item | Value |
|---|---|
| Mission | NISAR (NASA-ISRO), L-band, 24 cm wavelength |
| Products | Level 2 geocoded single-look complex (GSLC), HH and HV, 5 m grid. Level 1 radar-geometry SLC (RSLC) for re-geocoding |
| Dates used | 20 June to 16 November 2026, 32 acquisitions |
| Source | NASA ASF DAAC |

| Track | Pass | Looks toward | Incidence | Dates used |
|---|---|---|---|---|
| 26 | Descending | East | 41° | 8 |
| 90 | Ascending | West | 39° | 12 |
| 162 | Ascending | West | 47° | 12 |

- These are all the NISAR tracks over 9t. None was chosen over another.
- The two pass directions see each slope from opposite sides. A target hidden on one can show on the other.
- Two track 26 dates are dropped. 22 July has no valid pixels. 8 September matches no other date of its track at any shift.

### 3.2 Reference data

- USGS 3DEP lidar, project PA_WesternPA_2019_D20, about 4.8 points per m². It supplies the ground model, canopy height and the pit and pad outlines.
- Pennsylvania DEP well locations and status, April 2026 export.

### 3.3 How the data was obtained

- NASA's catalogue (CMR) was queried for every GSLC whose footprint touches 9t, in all three NISAR collections: beta, provisional and standard. The query needs no login.
- Each catalogue entry gives an HTTPS link at ASF. Earthdata Login redirects that link to a signed address on NASA's cloud storage (Amazon S3, region us-west-2, through CloudFront).
- Each file is a 22.6 GB HDF5 image of a whole frame, stored in 512 × 512 compressed chunks. Only the chunks covering 9t plus a 200 m margin were read, using HTTPS range requests. That is about 40 MB per polarisation per date.
- Each window was saved as a 2-band complex image (HH and HV) on the product's 5 m grid, with phase kept.
- When two frames covered 9t on one date, the one with more valid pixels was kept.

### 3.4 What data exists, and why the record starts in June

- **Date rule.** Only dates from 2026-06-01 onward enter any result. The rule is enforced in code, so no step can pick an earlier date.
- **Why.** The October 2025 to January 2026 images are beta products from older software, with different calibration. Every fall and winter date was beta and every summer date was not. Mixing them would let processing pose as season, and would inflate amplitude spread.
- **February to May 2026 does not exist publicly over 9t.** A full catalogue search on 2026-11-24 found only three granules over 9t between January and May. All three are January beta and already on disk.
  - The first public L-band release covers acquisitions from 17 June 2026 onward. Earlier acquisitions are held for a reprocessing campaign that ASF places in 2027.
  - So the gap is release status, not access. No download method or calibration choice can recover it.
- **A permanent instrument gap** runs from 27 July to 10 August 2026, per ASF. It matches the hole in our dates between 26 July and 12 August.
- **Empty files found.** Eleven track 90 files for 3 January to 8 June were fetched as neighbouring frames, but they are 0% valid. Their footprint lies about 12 km north of 9t. They were never used, because the date rule already excluded them.

## 4. Methods

### 4.1 Placing the radar on the lidar ground

- NASA's images sat 8 to 12 m off the lidar on all three tracks. The offset always pointed away from the satellite and grew under taller canopy.
- That pattern is what a too-high elevation model produces. NASA's elevation model sits partway up the canopy in forest.
- A new geocoder placed each image on the lidar bare-earth ground (no canopy term; the 10% canopy setting is used only in the brightness-simulation check). Lidar heights were converted from NAVD88 to WGS84 ellipsoid height with NOAA Geoid12B first, so no geoid offset (about −33 m here) is left for the cross-correlation to absorb. Heights of 0, 10, 25 and 50% were tested, and 10% matched best.
- The remaining shift was solved for each date and track. Radar brightness was simulated from lidar slope facing the satellite, and the simulation was cross-correlated with each image in 48 blocks (16 blocks × 3 tracks).
- Pass rule: a block agrees within 2.5 m, half a 5 m pixel, so a target stays in its own pixel. The rule was set in the plan, not fitted.
- Result: 47 of 48 blocks pass. The median block offset is 1.0 to 1.4 m per track.
- *Why.* A pit is only a few pixels across. At 8 to 12 m off, a test measures the rim or the forest instead of the pit.
- *Limit.* The check uses the same simulation that set the offsets, so it is not independent. No surveyed point or corner reflector exists on 9t.
- No radar elevation model was built. The lidar is the height reference. Repeat-pass radar heights under forest would carry metres of error.

### 4.2 Tracks kept separate

- Every measurement runs per track. Tracks are combined only at the end, by site.
- *Why.* Each track has its own viewing direction, angle and calibration. Phase only compares dates on one track.

### 4.3 Site contrasts: ring and control spots

- **Ring.** Each feature's brightness is compared with a ring of ground around it: 20 to 60 m for pads and 10 to 30 m for pits. The ring cancels most of the local slope, canopy and track effects.
- **Control spots.** Five spots of the same shape as the feature, 150 to 600 m away, with no mapped feature. They measure how much any patch differs from its ring by chance.
- **Excess.** The feature's ring contrast minus the median of its control spots' ring contrasts.
- **Statistics.** A Wilcoxon signed-rank test on per-site excess, and a bootstrap 95% interval over sites. Wilcoxon assumes no bell curve, which suits small, noisy radar contrasts.
- Hundreds of sites are pooled, because one site is lost in speckle.

### 4.4 Seasons

- Summer is 1 June to 30 September. Fall is 21 October to 30 November, after leaf drop.
- Early October is half-leafed, so it is in neither season.
- The windows were fixed before any post-June result was seen.

### 4.5 Persistent-scatterer screen for steel

Persistent-scatterer analysis has two steps. Step 1 picks steady, bright pixels. Step 2 reads motion from their phase. Only step 1 was run.

| Rule | Value | Source or reason |
|---|---|---|
| Amplitude dispersion (standard deviation over mean, across dates) | under 0.25 | Ferretti, Prati and Rocca (2001), Sec. III-C. Pure speckle gives about 0.52 |
| Brightness above the median within 250 m | at least 3 robust SD per track: 7.2, 7.0 and 6.5 dB on tracks 26, 90 and 162 | Usual outlier rule. Robust SD is 1.4826 × median absolute deviation, so a few bright targets do not inflate it |
| Hit radius | 6 m | 3.5 m pixel half-diagonal plus 2.5 m placement tolerance |

- *Why amplitude, not phase.* Ferretti showed that for strong targets the spread of amplitude tracks the spread of phase. Amplitude needs no unwrapping and works with the 8 to 12 dates available.
- *Why 250 m.* Fifty pixels, more than twice the largest pad, so a pad cannot set its own background. Smaller than the valley sides that change brightness.
- **Control spots for this test.** Five per well, 150 to 600 m away, at least 60 m from any well or pad, drawn from the same canopy-cover band as the well (within 0.15).
- **Comparison.** Hit rate at wells against hit rate at control spots, by Fisher's exact test, separately for each DEP status. Never-drilled permits are the negative control: they have no steel, so they should match control spots.
- **Positive check.** A building at 41.502787, -79.519712.

### 4.6 Other tests

| Test | Signal | Compared against | Physical reason |
|---|---|---|---|
| Pad coherence | Phase, back-to-back date pairs | Control spots | Work on a pad scrambles the surface |
| Pool pits | Amplitude | Other pits | Calm water reflects radar away |
| Pit motion | Interferometric phase, 3 × 3 window (15 m, 9 looks) | Ring and control spots | A settling pit would move |
| Slope motion | Phase on two ascending tracks | Each other | Slow creep can shear a casing |

- **Pool pits** were defined from lidar before looking at the radar: at least half the floor flat, with weak lidar returns.
- **Pad coherence events** are pairs whose drop is reached by only 1% of control-spot pairs. A swap test gives the p-value. Each unit is one pad and its five control spots, as whole time series over the same date pairs. Each permutation picks which series is the pad, so shared dates and repeated pads sit inside the null. Spatial correlation between neighbouring pads is not modelled.
- **Coherence window.** Pit coherence and phase use a 3 × 3 window, 15 m and 9 looks. That is wider than most pits, so pit phase mixes with rim and forest. A 9-look estimator is biased upward, to about 0.3 for pure noise. Pad coherence uses a 5 × 5 window, 25 m and 25 looks, with 2000 swap permutations.
- **Rings exclude neighbours.** Pad rings stay 10 m clear of other pads. Pit rings stay 5 m clear of every pit and road.

## 5. Findings

All numbers are from the 2026-11-26 rerun. That rerun fixed four things found in an outside review (section 7):
- vector layers now sit on the radar datum, which moved them about 1.3 m;
- steadiness (D_A) uses the N−1 standard deviation;
- each date is scaled to its track's median brightness before D_A, so the processor-version step (5.6) does not count as unsteadiness;
- pixel lookups round down instead of truncating.

### 5.1 Steel at DEP well points: chance

| Well group | Wells | Wells with a steady bright pixel, any track | Control spots | p (Fisher) |
|---|---|---|---|---|
| Active | 618 | 1.5% | 1.6% | 0.86 |
| Plugged | 271 | 0.4% | 1.4% | 0.23 |
| Abandoned | 173 | 1.7% | 0.7% | 0.18 |
| Never drilled | 10 | 0% | 0% | 1.00 |

- Steady bright pixels make up 0.12%, 0.12% and 0.05% of valid pixels on tracks 26, 90 and 162 (1180, 1168 and 450 pixels).
- One plugged well has a steady bright pixel on two tracks. No active or abandoned well does.
- Active wells do no better than control spots. This comparison trusts DEP status, which may be stale.
- Control spots stay 60 m from mapped wells and 30 m from mapped pads. Undocumented wells can still fall among them, which pushes any contrast toward zero.
- **Open against canopy.** Under canopy (cover ≥ 0.30), plugged and abandoned wells have no hits. In the open, abandoned wells hit 4.1% against 1.1% at control spots. That is 74 wells, so about 3 wells.
- **Brightness alone.** Abandoned wells are brighter than their control spots (AUC 0.57, p = 0.003; median local excess 2.63 dB against 2.39 dB). This is one of many comparisons, and the steadiness rule does not back it. It is a lead, not a finding.
- **The building passes.** A steady bright pixel sits 2.5 m from it on track 162. The building is in the open and far larger than a wellhead. It shows the screen works on large targets. It does not show that L-band sees a casing through trees.
- DEP points sit a median 36 m from the nearest lidar pad (section 12). A 6 m hit radius around a DEP point often misses the real well. Section 5.2 removes that error.
- File: `nisar/results/9t/nisar_steel_summary_9t_slc.json`.

### 5.2 Steel at lidar pads: a small excess, not significant

Each lidar pad gets a 5 m buffer. Each pad also gets 5 control polygons of the same shape, shifted 150 to 600 m away, at least 60 m from any DEP well and 30 m from any pad, with canopy cover within 0.15. A pad is "hit" when any steady bright pixel falls inside it.

| Dates | Pads | Pads hit, any track | Controls hit | p (Fisher) | Pads hit, 2+ tracks | Controls, 2+ tracks |
|---|---|---|---|---|---|---|
| All post-June | 649 | 19.3% | 16.6% | 0.12 | 2.5% | 2.0% |
| Summer only (leaf-on) | 649 | 19.9% | 16.8% | 0.074 | 2.9% | 2.5% |

| Subgroup, all post-June | Pads | Pads hit | Controls hit | p |
|---|---|---|---|---|
| Open (cover < 0.30) | 60 | 23.3% | 15.3% | 0.17 |
| Canopy | 589 | 18.8% | 16.7% | 0.22 |
| Large third | 216 | 20.8% | 18.4% | 0.44 |
| Active DEP well inside | 230 | 18.7% | 12.8% | 0.025 |
| Plugged or abandoned only | 75 | 17.3% | 19.6% | 0.74 |
| No DEP well inside | 344 | 20.1% | 18.2% | 0.44 |

- Pads are hit slightly more often than controls in every main run, by 2 to 3 points. No main run reaches p < 0.05.
- Of 36 pad comparisons (2 date sets, 9 subgroups, any-track and 2+ tracks), 4 reach p < 0.05:
  - active-well pads, all dates, any track (p 0.025);
  - large pads, summer, any track (p 0.009);
  - plugged or abandoned pads, summer, any track (p 0.037);
  - open pads, summer, 2+ tracks (8.3% against 2.3%, p 0.043).
- About 2 would reach p < 0.05 by chance. None survives a Bonferroni correction (cutoff 0.0014).
- Active-well pads lead on all dates but not in summer (17.4% against 17.4%), so the lead is not stable.
- **This test has low power.** Controls are hit about 17% of the time. A pad covers about 70 pixels, and each pixel has a small false-alarm rate, so a hit somewhere in the pad is common by chance. Only 3 or 4 of 60 open pads show equipment in aerial photos (5.3). A real 3 to 6% hardware rate would be buried under a 17% background. So the test rules out "most pads hold a steady bright target". It cannot rule out a few.
- Of the 4 open pads with visible equipment, 2 are hit (P5 on 2 tracks, P55 on 1). Four pads is too few to mean anything.
- Controls are pooled across pads, and not every pad gets 5 (small pads average 4.6, open pads 3.3). A test matched pad by pad has not been run.
- Files: `nisar/results/9t/nisar_steel_pads_summary_9t_slc.json`, per pad `nisar/results/9t/nisar_steel_pads_sites_9t_slc.gpkg`, figure `nisar/results/9t/figures/nisar_steel_pads_hit_rate_9t_slc.png`.

**The two rules on their own.**
- Brightness passes 0.36 to 0.46% of valid pixels per track. Radar dB is right-skewed, so that is about three times what a bell curve gives.
- Steadiness passes 0.8 to 3.5%.
- Both together pass 0.05 to 0.12%. If the two rules were independent, both together would pass under 0.02%.
- So bright pixels are steadier than chance. Real stable targets exist on 9t.

### 5.3 What the steady bright targets are

The 40 strongest targets were inspected on NAIP aerial photos (June 2022, 0.6 m) and the lidar relief map. All 40 are on 2 or 3 tracks, ranked by brightness. This inspection was done before the rerun. The rerun moved the cutoffs by under 0.04 dB, so the strongest targets should be unchanged.

| What sits at the target | Targets |
|---|---|
| Houses and outbuildings | 9 |
| Metal yards: stacked pipe, equipment, trailers | 8 |
| Oilfield equipment (tanks on a lined pad; a small structure beside a DEP well) | 2 |
| Possible object at a clearing edge | 1 |
| Forested valley walls, nothing visible | 6 |
| Forest, nothing visible | 10 |
| Open ground or road, nothing visible | 4 |

- Half the strongest targets are buildings or metal. NISAR finds hard targets when they are large.
- Only 2 of 40 are oilfield equipment, and both are larger than a wellhead.
- Six sit on forested valley walls. That fits brightness without terrain flattening (β0) on slopes facing the radar.
- Several targets fall in one pipe yard, so the 40 cover fewer distinct places than they seem to.
- The analyst classified these by eye. Files: `nisar/results/9t/nisar_top_targets_naip_classes_9t.csv`, chips `nisar/results/9t/figures/nisar_naip_chips_targets_p1_9t.png` to `_p4_9t.png`.
- **No verified hardware set.**
  - Only 3 or 4 of the 60 open pads show equipment (`nisar_naip_chips_open_pads_p1_9t.png` to `_p6_9t.png`).
  - Most pads that were open in the 2019 lidar are under tree crowns in the June 2022 photos.
  - A hardware set needs leaf-off photos or a field visit.

### 5.4 Pit and pad brightness

| Feature | Measure | Excess (dB) | 95% interval | p |
|---|---|---|---|---|
| Pits (506) | Summer HV | **+0.16** | +0.07 to +0.23 | <0.001 |
| Pits | Summer HH | +0.10 | +0.00 to +0.21 | 0.031 |
| Pits | Fall HH | +0.05 | −0.05 to +0.20 | 0.30 |
| Pits | Fall HV | +0.06 | −0.05 to +0.24 | 0.12 |
| Pads (644) | Fall HH | **−0.15** | −0.23 to −0.07 | <0.001 |
| Pads | Fall HV | **−0.13** | −0.19 to −0.07 | <0.001 |
| Pads | Summer HH | +0.01 | −0.03 to +0.06 | 0.76 |
| Pads | Summer minus fall, HH | **+0.14** | +0.08 to +0.18 | <0.001 |

- **Pits are slightly brighter than control spots in summer HV.**
  - A clean canopy gap would lower HV, so a gap alone does not explain this.
  - Likely causes: shrubs or rough canopy edges around old pits, bounce between pit banks and trunks, or the pit wall that faces the radar.
  - Summer HH reaches p 0.031, which is weak among this many tests.
- **Pads are slightly darker than control spots in fall, after leaf drop.**
  - That fits the physics. Bare trunks in the ring give strong trunk-ground double bounce in HH. A cleared pad has no trunks.
  - Fall dates are all on the newer processor version (5.6). Its gain step is the same over open ground and forest, so it cancels in pad-minus-ring.
- **No terrain flattening.** Brightness is β0. A flat pad in a sloped ring, or a pit with one wall facing the radar, changes brightness through local incidence angle alone.
- **Control spots are unmatched.** They are not matched on canopy or slope, and pads are flatter and more open than random forest. Part of each contrast may come from land cover, not well sites.
- All contrasts are a few tenths of a dB, far below what one site can show against speckle. Fall rests on 2 or 3 dates per track.
- Hollows with no well have not been compared.
- File: `nisar/results/9t/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_9t_slc_5m.json`.

### 5.5 Pad coherence

| Pad date pairs | Events | Expected from control spots | Swap-test p |
|---|---|---|---|
| 18,200 | 220 | 182.0 | 0.007 |

- Pads lose coherence slightly more often than control spots: about 2 extra events per 1,000 pad-pairs.
- 46% of events fall on pads with an active DEP well, against 35% of all pads. That leans toward activity, but there are no dated well records to test it.
- Control spots are not matched on canopy or slope. Vegetation, traffic and weather are all plausible causes.
- Coherence uses a 5 × 5 window (25 m, 25 looks) and 2000 swap permutations.
- File: `nisar/results/9t/nisar_pad_change_summary_9t_slc.json`.

### 5.6 Processor version and season are confounded

- Every date from 2026-06-20 to 2026-10-18 is provisional, processor version P05023. Every date from 2026-10-23 to 2026-11-16 is standard, P05036, which has a new calibration.
- So the switch coincides with leaf drop, which is the same trap as the beta dates (section 10).
- Each track has one date on each side of the switch, 12 days apart. The step was measured as the change across the switch minus the previous same-version 12-day change.

| Track | HH step, all pixels | HH, open ground | HH, closed forest |
|---|---|---|---|
| 26 | −0.38 dB | −0.39 | −0.39 |
| 162 | −0.27 dB | −0.28 | −0.26 |
| 90 | not measurable | | |

- The step is the same over open ground and forest, so it is a flat gain change. It cancels in every feature-minus-ring contrast. Per-date scaling removes it from D_A.
- Track 90's Oct 18 date is itself abnormally dark: 1.0 dB below Oct 6, then up again by Oct 30. That masks the version step on track 90.
- The 9 buildings give noisy values (−0.9 to +0.6 dB) on single peak pixels.
- File: `nisar/results/9t/nisar_processor_step_summary_9t_slc.json`.

### 5.7 Pool pits

23 of 500 pits qualify as pool pits. They are 0.17 to 0.27 dB brighter than other pits on every measure, but no difference is significant (all p ≥ 0.35). Twenty-three sites cannot separate a few tenths of a dB from chance. The lidar dates from 2019, so a pool then may not be one now. This test has not been rerun with the datum fix.

### 5.8 Motion

- **Pits.** Over 28 interferometric pairs, pit motion against the ring is −0.24 mm in HH (95% interval −0.43 to −0.02). One pair's noise is about 5.6 mm, and soil moisture alone shifts L-band phase this much. It is not evidence of motion. This test has not been rerun with the datum fix.
- **Slopes: not creep.**
  - Tracks 90 and 162 agree at r = 0.33 (0.20 to 0.45).
  - NISAR looks left, so on these ascending tracks the radar sits east and looks west. Downslope creep would move east-facing slopes toward the radar and west-facing slopes away. The sign must flip.
  - It does not. Steep slopes move −5.9 mm facing east (50 pixels), −8.1 mm facing west (3 pixels) and −8.0 mm facing north or south (7 pixels).
  - One sign on every aspect fits a summer-to-fall change in a layered atmosphere over the incised valleys, or a shift in where the signal scatters. It does not fit creep.
  - Only 257 pixels pass the coherence rule on both tracks.

## 6. Interpretation

- **No well-linked persistent scatterer.** At 8 to 12 dates per track, NISAR L-band shows none on 9t.
- **DEP points:** chance (5.1). DEP points sit a median 36 m from the lidar pad, so this test is weak by design.
- **Lidar pads:** about 2 to 3 points above controls in every run, never significant, and no subgroup survives correction (5.2). Controls are hit 17% of the time, so a small real rate cannot be ruled out. The data rule out "most wellheads are steady bright targets". They do not rule out "a few pads with large equipment are".
- **The screen works on large hard targets** (5.3). Half the strongest targets are buildings and metal yards. Two of 40 are oilfield equipment, both large.
- **Two physical reasons make a bare wellhead hard to see, even in the open:**
  1. *Too weak against clutter.* A 5 × 5 m forest pixel at about −8 dB holds about +6 dBsm of clutter. Passing the 6.5 to 7.2 dB rule needs a target of roughly +13 to +16 dBsm, about a 1.5 to 2 m corner reflector or a tank battery. A 15 to 20 cm casing standing 1 m high falls short unless it forms a clean corner with the ground.
  2. *Wrong polarisation for a pipe.* NISAR collects HH and HV over North America, not VV. A vertical pipe couples weakly with HH.
- **Three more causes the data cannot yet separate:**
  3. *No steel left.* Plugged casings are cut or buried. Pumpjacks move between passes.
  4. *Trees block the view.* Leaf drop can also make a real target under canopy look unsteady.
  5. *Too few dates.* The 0.25 cutoff was designed for about 30.
- **Pit and pad brightness** contrasts are small but consistent (5.4). They may partly reflect land cover, since control spots are unmatched. Use them as pooled evidence, not a per-site marker.
- **Pad coherence** shows a small excess, weighted toward active-well pads (5.5). It is the strongest pad-level signal. It needs matched controls and dated activity records before it means more.
- **Slope motion** is atmosphere or scattering change, not creep (5.8).
- **The processor switch** is a flat gain step and does not explain the season contrasts (5.6).

## 7. Errors caught and corrected

- Early pad and pit scores were inflated, because control spots differed from targets in more than location.
- NASA's placement was 8 to 12 m off. Fixing it removed an early pad darkening and an abandoned-well lead.
- Two statistics were not true window moments. The fix moved the headline by 0.005 dB or less.
- A fall pit contrast of +0.25 dB came from beta dates. It does not repeat on post-June dates.
- The hit radius of 15 m predated lidar placement. It is now 6 m.
- The downloader originally missed the standard collection, and with it late October and November. It now searches all three collections.
- 2026-11-26: vector layers were moved to the radar grid with a PROJ route that applies no shift from NAD83(2011). They sat about 1.3 m (−0.80 m east, +1.01 m north) off the radar pixels. Now routed through ITRF2014.
- 2026-11-26: D_A used the N standard deviation, 7% low at 8 dates. Now N−1, with each date scaled to its track's median brightness.
- 2026-11-26: the slope script assumed a right-looking radar. NISAR looks left. The slope aspect result is now read as atmosphere, not creep.
- 2026-11-26: the docs said the geocoder adds 10% of canopy height. The code uses bare ground only. The docs said pad coherence used a 3 × 3 window and 5000 permutations. The code uses 5 × 5 and 2000.
- Eleven empty track 90 spring files were saved without a validity check. They were never used. The fix is to skip windows with no valid pixels.

Two outside reviews and one adversarial review checked the work. The 8 to 12 m placement error came out of that review.

## 8. Limitations

- 8 to 12 dates per track, and 2 or 3 fall dates.
- No public NISAR L-band over 9t from February to May 2026, and an instrument gap from 27 July to 10 August.
- Placement is not checked against a surveyed point.
- Brightness-test control spots are not matched on canopy, slope or road access. Steel-test control spots are matched on canopy only.
- Five control spots per site can shift results with the random draw. A 40-spot stability check has not been run.
- L-band phase can lose stability under leaves within 12 days.
- The 2019 lidar may not show the ground as it is now.
- DEP well-coordinate error is not included in the 6 m hit radius. Measured against lidar pads, it is far larger than 6 m (section 12).
- Brightness is β0, not terrain-flattened γ0.
- No VV polarisation over North America.
- Processor version P05023 covers every summer date and P05036 every late-fall date (5.6). The measured step is a flat gain, but other changes in the new version cannot be ruled out.
- Pad steel controls are hit about 17% of the time, so the pad test has low power. Controls are pooled, not matched pad by pad.
- Many comparisons were run. Single p-values between 0.01 and 0.05 are not findings on their own.

## 9. Next steps

| Step | Why |
|---|---|
| Treat the screen as exploratory: rank pixels on brightness and steadiness instead of fixed cutoffs | No dB threshold needs to be set in advance |
| Done 2026-11-25: steel screen per lidar pad polygon | Small excess, not significant (5.2) |
| Done 2026-11-25: separate pass rates and leaf-on-only run | Same answer (5.2) |
| Done 2026-11-25: inspect the top 40 targets on NAIP | Buildings and metal yards, 2 oilfield (5.3) |
| Verified hardware and empty pad sets from leaf-off photos or a field visit | Leaf-on NAIP 2022 shows equipment on only 3 or 4 of 60 open pads |
| Lidar-based radiometric terrain correction (γ0) | Stops micro-topography leaking into pit and pad brightness |
| Steadiness from leaf-on dates only | Stops leaf drop failing real under-canopy targets |
| Report the brightness and steadiness pass rates separately | The 0.13% combined rate should not be compared with the bell-curve figure for brightness alone |
| Azimuth sub-look coherence on the RSLCs | Steel stays coherent across sub-looks within one image while forest decorrelates. Needs no long stack and is unaffected by leaf drop |
| HH/HV ratio and HH-HV coherence | Cancels shared calibration shifts and suppresses forest volume |
| 10 to 15 open-sky buildings, bridge abutments or towers, kept out of the offset fit | An independent placement check without corner reflectors |
| Relative calibration: match each date's histogram, within a track, to a reference date over stable pixels | Calibration constants cancel, so other datasets can join |
| Add the October 2025 to January 2026 beta dates after relative calibration | Up to 15 more dates. Matching will not fix beta cross-track banding or mask offsets, so accept them only if the median dispersion of stable background pixels does not rise, as well as the building check |
| Sentinel-1 track 77 (C-band) on the same screen | Covers spring 2026 and gives an independent sensor |
| Rerun on reprocessed early-2026 L-band when ASF releases it (expected 2027) | Fills the spring gap. The pipeline reruns unchanged |
| Compare wells in the open with wells under canopy, and check November leaf-off dates | Tests whether the radar sees through trees |
| Compare pits with hollows that have no well | Tells a well marker from a depression marker |
| Corner reflectors at surveyed points on 9t | An independent placement check |
| Persistent-scatterer step 2 (motion) | Needs about 20 or more dates per track |

## 10. Withdrawn results

These used dates before June 2026 or areas outside 9t, so they are no longer findings:
- The fall HH pit contrast of +0.25 dB.
- Winter pad brightness and winter coherence.
- The 8 wet and 5 dry reference pits.
- The 346-band radar feature set and its principal component analysis.
- Tile 613590, Warren and McKean results.
- The earlier Sentinel-1 cross-check, which used 2017 to 2026 dates.

## 11. Glossary

- **Amplitude.** The strength of the echo.
- **Phase.** Where in its cycle the wave returns. Between dates on one track it measures millimetre changes in distance.
- **HH, HV.** Send and receive polarisations. HH favours ground and structures. HV favours canopy volume.
- **Speckle.** Grainy noise from many small reflectors inside one pixel.
- **Coherence.** How similar the signal is between two dates.
- **Amplitude dispersion.** Standard deviation of amplitude over dates divided by its mean.
- **Robust SD.** 1.4826 × the median absolute deviation. Equal to the standard deviation for a bell curve, but unaffected by a few extreme pixels.
- **Control spot.** A same-shaped spot on background, used for comparison only.
- **Excess.** Feature-minus-ring contrast, minus the same for control spots.
- **Range request.** An HTTPS request for one byte range of a file instead of the whole file.

## 12. Review response, 2026-11-25

An outside review of this write-up raised the points below. Each was checked against the code and data.

| Point | Verdict | Action |
|---|---|---|
| Brightness is β0, not terrain-flattened | Correct | Stated in 5.2 and 8. γ0 added to next steps |
| A canopy gap would lower HV, not raise it | Correct. The earlier wording was backwards | 5.2 rewritten |
| Fall pad darkening fits trunk-ground double bounce | Agreed | Added to 5.2, with a test |
| Clutter and target-strength arithmetic | Agreed | Added to section 6 |
| No VV over North America, and a vertical pipe favours VV | Agreed | Added to sections 6 and 8 |
| Moving pumpjacks raise dispersion | Agreed | Added to section 6 |
| 6 m radius is smaller than DEP coordinate error | **Correct, and now measured** (below) | Sections 6 and 8. Pad-polygon screen is the first next step |
| No NISAR S-band over Pennsylvania | Accepted. ISRO's S-band plan targets India and selected sites. Not checked against the observation plan | S-band removed from next steps |
| Leaf drop fails real under-canopy targets | Agreed | Leaf-on-only steadiness in next steps |
| Report the two pass rates separately | Agreed | In next steps |
| Rings may include neighbouring infrastructure | Already handled. Pad rings stay 10 m clear of other pads, pit rings 5 m clear of pits and roads | Stated in 4.6 |
| Swap test ignores shared dates | Partly handled. Whole series over the same date pairs are swapped within each pad unit. Spatial correlation between pads is not modelled | Stated in 4.6 |
| 3 × 3 coherence window, and its bias | Correct | Stated in 4.6 |
| Sub-millimetre pit phase may be soil moisture | Agreed | Noted below |
| Lidar heights not converted to ellipsoid | Already handled, with Geoid12B | Stated in 4.1 |
| Beta histogram matching will not fix banding | Agreed | Beta next step now needs a stable-background dispersion check |

**DEP coordinate check, new.** Distance from each of the 1,068 DEP wells on 9t to the nearest of the 650 lidar-mapped pads:

| Group | Wells | Inside a pad | Within 15 m of a pad | Median distance to pad edge |
|---|---|---|---|---|
| All | 1,068 | 25% | 35% | 36 m |
| Active | 616 | 33% | 42% | 29 m |
| Plugged | 271 | 18% | 31% | 43 m |
| DEP abandoned list | 151 | 10% | 18% | 47 m |
| DEP orphan list | 20 | 20% | 25% | 38 m |
| Never drilled | 10 | 10% | 20% | 91 m |

- 55% of DEP points sit more than 30 m from any mapped pad.
- This mixes two things. Some DEP points are misplaced, and some wells have no visible pad, especially old or abandoned ones. But even active wells, which should have pads, sit a median 29 m away. Coordinate error alone is far larger than 6 m.
- So the steel result in 5.1 tests DEP points, not wellheads. It stands as reported, but it cannot show that wellheads lack persistent scatterers.

**Pit motion caveat.** A −0.24 mm pit-against-ring phase difference is within what soil moisture and penetration-depth changes produce at L-band (De Zan et al., 2014). It is also within residual topographic phase from pit depth against ring canopy height. It is not evidence of subsidence.

## 13. Evidence and references

| Need | File |
|---|---|
| Date rule | `nisar/code/_nisar_area.py` (`DATE_FLOOR`) |
| Placement check | `nisar/results/9t/nisar_lidar_sim_match_summary_coregabs_k010_9t.json` |
| Steel test | `nisar/results/9t/nisar_steel_summary_9t_slc.json`, `nisar/results/9t/nisar_steel_by_canopy_9t_slc.csv` |
| Steady bright targets | `nisar/results/9t/nisar_bright_targets_summary_9t_slc.json` |
| Pit and pad brightness | `nisar/results/9t/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_9t_slc_5m.csv` |
| Pad coherence | `nisar/results/9t/nisar_pad_change_by_season_9t_slc.csv` |
| Pool pits | `nisar/results/9t/nisar_pit_pool_radar_9t.csv` |
| Pit interferograms | `nisar/results/9t/nisar_gslc_interferogram_pits_vs_decoys_win3_9t_slc_5m_summary.json` |
| Slope motion | `nisar/results/9t/nisar_slope_motion_summary_9t_slc.json` |
| DEP well distance to pads | `nisar/results/9t/nisar_dep_well_pad_distance_9t.gpkg` |
| Data availability search | `docs/analysis_log.md`, entry of 2026-11-24 |
| Process document | `nisar/docs/NISAR_PROCESS_AND_OUTCOMES.md` |
| Citations | `literature/CITATIONS.md` |

References:
- Ferretti, A., Prati, C. and Rocca, F. (2001). Permanent scatterers in SAR interferometry. *IEEE Transactions on Geoscience and Remote Sensing* 39(1), 8–20. Local copy `literature/papers/ferretti2001.pdf`.
- NASA ASF DAAC. NISAR Data User Guide, Available NISAR Data. https://nisar-docs.asf.alaska.edu/availability-overview/
- NASA Earthdata. NISAR L-band data released. https://www.earthdata.nasa.gov/news/nisar-l-band-data-released-expanding-record-surface-changes
- De Zan, F., Parizzi, A., Prats-Iraola, P. and López-Dekker, P. (2014). A SAR interferometric model for soil moisture. *IEEE Transactions on Geoscience and Remote Sensing* 52(1), 418–425. Cite-only.
- USGS 3DEP, PA_WesternPA_2019_D20 lidar.
- Pennsylvania DEP, oil and gas well records, April 2026 export.
