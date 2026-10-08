# NISAR L-band for wells: steel, pad change and slope motion, 9t

**Date:** 2026-10-07
**Status:** done. Three tests. None gives a usable well signal yet. Details per test below.
**Follows:** `docs/iterations/nisar_gslc_interferogram_pits_9t.md`. The user asked for the three options from the 2026-10-05 "what L-band can do for wells" answer.

| Test | Question | Answer |
|---|---|---|
| 1. Steel | Do bright, steady radar targets sit at DEP wells? | No. Hit rates are 1–2% at wells and 0.3–1% at decoys. Wells are 0.1 dB brighter than decoys, but active wells are no brighter than abandoned ones. |
| 2. Pad change | Do pads lose coherence in some pairs more often than decoys? | Barely. 143 snow-free events against 124 expected. Pads with active wells flag no more often than other pads. |
| 3. Slope motion | Is there motion on slopes, and at wells? | There is a weak shared signal on slopes in both ascending tracks. Its direction by aspect does not match downslope creep. No well stands out. |

## Data

- The 31 saved GSLC windows in `data/9t/derived/nisar_gslc_5m/` (complex HH and HV, 5 m, EPSG:32617, 4.9 km square). No new download.
- Dates per track: 8 on track 026 (descending), 10 on track 090 and 13 on track 162 (both ascending).
- Wells: DEP April 2026 export, `data/_source/reference/dep_wells/venango_wells_all.gpkg`. Inside the window there are 708 active, 297 plugged, 214 abandoned or orphan and 21 never-drilled wells.
- Pads: `plat` layer of `qgis/annotations/annotations_proj.gpkg`. 649 of 995 are usable inside the window.
- Slope and aspect: the 2019 lidar DEM, `data/9t/derived/1m/`.

## 1. Steel at wells

**Idea.** Casing, pumpjacks and tanks are steel. Steel gives strong echoes that stay the same from pass to pass. Forest echoes flicker. A pixel that is bright and steady is a persistent-scatterer candidate (Ferretti et al. 2001).

**Method.**
- Per track, amplitude dispersion D_A = std / mean of the HH amplitude over all dates.
- A steady bright target (SBT) has D_A < 0.25 and is at least 6 dB brighter than the 250 m median around it.
- Well score = the number of tracks with an SBT within 15 m.
- Continuous scores too: the brightest pixel within 15 m, and the lowest D_A within 15 m.
- Decoys: 5 per well, 150–600 m away, at least 60 m from any DEP well or pad, same canopy cover ±0.15.
- Never-drilled wells are a negative control.
- Registration check: the active-well hit rate with the stack shifted −20 to +20 m.

**Results.**

| Group | Wells | SBT within 15 m, wells | Decoys | Brightness AUC, wells vs decoys | p |
|---|---|---|---|---|---|
| Active | 617 | 1.3% | 1.0% | 0.53 | 0.014 |
| Plugged | 271 | 1.1% | 0.5% | 0.52 | 0.45 |
| Abandoned or orphan | 174 | 1.7% | 0.3% | 0.56 | 0.022 |
| Never drilled | 10 | 0% | 2.0% | 0.46 | 0.7 |

- Only 0.004–0.03% of pixels per track qualify as SBTs. A forest pixel has D_A near 0.5. With 8–13 dates the estimate is noisy.
- Wells are about 0.1 dB brighter than matched decoys. This holds for active and abandoned wells alike.
- Steady-ness does not separate wells from decoys (AUC 0.47–0.50).
- Registration: the best shift is (−10, +15) m with a 2.4% hit rate. The median over all shifts is 1.6%. That is no clear peak, so this does not fix the registration.

**Reading it.**
- If pumpjacks showed, active wells would beat abandoned wells. They don't.
- The small brightness excess is probably setting, not steel. Wells sit by roads and clearings more often than decoys do. Decoys avoided wells and pads but not roads.
- At 5 m, a pumpjack or a casing stub is a small target inside a forest pixel. It does not stand out over 31 dates.

## 2. Coherence change at pads

**Idea.** Work on a pad changes its surface. The pair that spans the work loses coherence on the pad. Pads are 40–100 m across, many pixels.

**DEP dates can't validate this here.** Only one well in the window has a plug date near the stack: 121-39189, plugged 2025-10-12, before the first date. It is not on an annotated pad. So this is detection against a decoy false-alarm rate, not validation.

**Method.**
- 21 pairs, consecutive dates on one track, at most 24 days apart. HH coherence, 5 x 5 window (25 m).
- d = pad core coherence (pad shrunk 5 m) minus ring coherence (20–60 m out).
- Anomaly = d minus that pad's own median d on the same track.
- Same steps for 5 same-shape decoys per pad.
- Threshold = the anomaly that only 1% of decoy pairs fall below, per season. Pairs starting Dec–Mar are winter.

**Results.**

| Season | Pad pairs | Pad events | Expected from decoys | p (more than decoys) |
|---|---|---|---|---|
| Snow-free | 12,331 | 143 | 123.5 | 0.045 |
| Winter | 1,298 | 13 | 13.1 | 0.55 |

- Pads with 2 or more events: 3.9%. Decoys: 3.0%.
- Pads with an active well flag at 1.13% of pairs. Other pads flag at 1.15% (Fisher p = 0.93).
- The strongest events do show a dark patch that fills the pad outline in the coherence chip (figure below). Those are real coherence losses on the pad.

**Reading it.**
- The detector works. It finds pads that lost coherence in one pair.
- But pads lose coherence only slightly more often than decoys, about 20 extra events in 12,000 pad pairs.
- Confound: decoys sit mostly under forest, pads are open ground. Rain on bare ground can drop coherence without anyone working the site. So even the 20 extra events are not proof of work.
- The events are **candidates**. They can be checked in QGIS against imagery, or against DEP inspection records.

## 3. Slope motion, summer 2026

**Idea.** Creep on colluvial slopes can shear a casing. InSAR over 25 m can see millimetres when coherence holds. This is a simple chain version of a time series (Berardino et al. 2002).

**Method.**
- Snow-free chain, June to September 2026, per track. HH interferograms, 5 x 5 multilook to 25 m.
- The phase trend over 1 km is removed from each pair (atmosphere, orbit).
- Cumulative phase = sum of the pair phases. LOS displacement in mm, positive toward the satellite. Pixels with mean coherence < 0.45 are masked.
- Real motion appears in both ascending tracks (090 and 162). Noise does not. So the test is the correlation between them, with a 500 m block bootstrap.
- Aspect test on steep slopes. The ascending radar looks east. Downslope creep on a west-facing slope moves toward the satellite. On an east-facing slope it moves away.

**Results.**

| Track | Span | Pairs | Coherent share | Spread |
|---|---|---|---|---|
| 090 asc | 06-20 to 09-24 | 7 | 71% | 16.5 mm |
| 162 asc | 06-25 to 09-17 | 6 | 26% | 15.8 mm |
| 026 desc | 08-15 to 09-20 | 3 | 1% | 44 mm (noise) |

| Slope | Pixels | r, 090 vs 162 | 95% block CI |
|---|---|---|---|
| Flat < 5° | 1,569 | −0.004 | −0.05 to 0.04 |
| Moderate 5–15° | 4,838 | 0.086 | 0.05 to 0.12 |
| Steep ≥ 15° | 1,001 | 0.123 | 0.05 to 0.20 |

| Steep slopes facing | Pixels | Mean LOS, mm | 95% block CI |
|---|---|---|---|
| West | 136 | −4.3 | −7.2 to −0.8 |
| East | 686 | +4.9 | 4.0 to 5.8 |
| North or south | 179 | −1.4 | −4.0 to 1.1 |

- Wells: 280 DEP wells on coherent pixels. None is flagged by both ascending tracks (more than 2 SD, same sign). 0.4 expected by chance.
- Median absolute LOS at wells: 7.7 mm on steep slopes, 7.3 mm on flat ground. No difference.

**Reading it.**
- The two ascending tracks share something on slopes and nothing on flat ground. That part is real.
- It is not downslope creep, as measured. East-facing slopes move toward the satellite and west-facing slopes move away. Creep would do the opposite.
- If the NISAR phase sign is the reverse of what this script assumes, the pattern would fit creep. But it would be about 20 mm/yr on every steep slope in the tile. That is far more than the regional creep in Venango is expected to be.
- More likely explanations:
  - a soil-moisture phase (De Zan et al. 2014), since east- and west-facing slopes dry differently through the summer
  - a DEM error in the processing DEM, which is larger on steep slopes
- Track 026 has too few coherent pixels to act as the independent check.
- Per pair the noise is about 6 mm. Summed over 6–7 pairs it is 15 mm. A single well site would have to move several centimetres in a summer to show.

## What this means for the wells

- L-band at 5 m does not see well steel through the canopy in 31 beta dates.
- Pad coherence change is a working detector with a high false-alarm rate. It produces candidates to check, not a monitoring product.
- Slope motion needs three things before it can rank wells:
  - the phase sign confirmed from the NISAR GSLC specification
  - a moisture-free check, such as a longer stack or winter-to-winter pairs
  - a landslide inventory to test against. The only one on disk, `data/_archive/parked/barlow_finesst/barlow/Shapefiles/OutcropGeology/shapefiles/svl_landslides_poly.shp`, is in Antarctica.

## Outputs

In `data/9t/results/nisar/`:
- Steel:
  - `nisar_steel_wells_9t.gpkg`, layer `dep_wells_sbt`
  - `nisar_steel_by_status_9t.csv`
  - `nisar_steel_by_canopy_9t.csv`
  - `nisar_steel_summary_9t.json`
- Pad change:
  - `nisar_pad_change_events_9t.gpkg`, layer `candidate_pad_events`
  - `nisar_pad_change_all_9t.csv`
  - `nisar_pad_change_by_season_9t.csv`
  - `nisar_pad_change_summary_9t.json`
- Slope motion:
  - `nisar_slope_motion_wells_9t.gpkg`, layer `dep_wells_los_summer2026`
  - `nisar_slope_motion_tracks_9t.csv`
  - `nisar_slope_motion_spread_9t.csv`
  - `nisar_slope_motion_aspect_9t.csv`
  - `nisar_slope_motion_summary_9t.json`

In `data/9t/results/nisar/figures/`:
- `nisar_steel_9t.png`
- `nisar_pad_change_hist_9t.png`
- `nisar_pad_change_top_events_9t.png`
- `nisar_slope_motion_9t.png`

In `data/9t/derived/nisar_gslc_5m/` (gitignored):
- `nisar_steel_count_9t.tif` (0–3 tracks)
- `nisar_slope_motion_t{026,090,162}_9t.tif`

Figure colours:
- Wells and pads use the lost/found palette `#1F5FA8` / `#D97706` / `#A31515`, with greys for controls.
- Check: dataviz `validate_palette.js --mode light --pairs all`, 2026-10-07.
  - Steel figure: CVD worst pair is 10.9 deutan. Normal-vision worst pair is 12.0, active against never-drilled grey. Each bar is labelled on the axis.
  - Pad figure: worst pair 15.0 protan.
- No red/green pair. Displacement uses PuOr, purple to white to orange.

## Limits

- NISAR beta and provisional data are not yet validated for interferometry.
- Registration to the lidar is still weak. The steel test did not fix it.
- DEP well coordinates for old wells can be tens of metres off.
- The NISAR phase sign was not confirmed against the product specification.
- No spring dates.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_nisar_steel_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_pad_change_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_slope_motion_9t.py
```
