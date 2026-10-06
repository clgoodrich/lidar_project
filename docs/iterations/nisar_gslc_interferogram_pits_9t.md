# NISAR interferograms at well pits, 9t

**Date:** 2026-10-05
**Status:** done. Null result at pit scale.
**Script:** `notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py`
**Follows:** `docs/iterations/nisar_gslc_stack_pad_pit_seasonal_9t.md`. This is option 2 of the 2026-09-30 reappraisal, coherence from the saved complex windows.

## Goal

The user asked to try interferograms on sample well pits.
The reappraisal had dropped InSAR on single pits, because a pit is about one 5 m pixel. This run tests that directly.
Two questions:
- Do pits hold a different coherence from the ground around them? A disturbed or wet surface might.
- Does the phase show a pit moving relative to its ring?

## Data

- The 31 saved GSLC windows in `data/9t/derived/nisar_gslc_5m/` (complex HH and HV, 5 m, EPSG:32617). No new download.
- Pairs are consecutive dates on one track, at most 24 days apart. That gives 21 pairs: 4 on track 026, 7 on track 090 and 10 on track 162.
- Pits are the `pit_outside` layer, 506 pits inside the radar window. Canopy cover is from the 2019 CHM.

## Method

| Step | Detail |
|---|---|
| Interferogram | s1 × conj(s2). NISAR GSLC is already phase-flattened, so no topographic phase needs removing. |
| Flattening check | On the 2025-10-28 to 11-09 track 162 pair, the interferogram spectrum peaks at zero frequency, so no fringe ramp is left. HH coherence is 0.43 at 9 × 9 pixels. This matches the 0.50 measured from GUNW at 80 m. |
| Coherence and phase | 3 × 3 pixel boxcar, 15 m and 9 looks. A 9-look estimate reads high on low coherence. The bias is the same for pits, rings and decoys. |
| Pit and ring | Pit pixels have their centre in the pit, or the centroid pixel if none does. The ring is 10–30 m out, 5 m clear of pits and roads. |
| Decoys | 5 same-shape copies per pit, 150–600 m away on background. Excess = (pit − ring) − median(decoy − ring). |
| Motion | Pit phase minus ring phase, as line-of-sight mm. One radian is 1.9 mm, so a full colour cycle is 12 mm. |
| Registration | As delivered, plus a sensitivity run with each track's best canopy shift from the brightness stack, (−10, −5), (−15, −5) and (+10, −10) m. |

## Results

**Coherence holds over 9t outside winter.** The tile median for HH is 0.50 across pairs, and 0.42 for HV.
- The best pair is track 090, 2026-09-12 to 09-24, at 0.68.
- The worst is mid-winter, track 162, 2026-01-08 to 01-20, at 0.35.

**Pits are indistinguishable from their decoys.**

| | HH, as delivered | HH, shifted | HV, as delivered | HV, shifted |
|---|---|---|---|---|
| Pit coherence, median | 0.468 | | 0.419 | |
| Ring coherence, median | 0.466 | | 0.418 | |
| Coherence excess, per pit pooled over pairs | +0.0001 | −0.0047 | +0.0024 | −0.0050 |
| 95% CI | −0.004 to +0.005 | −0.009 to +0.001 | −0.002 to +0.006 | −0.008 to −0.001 |
| Open pits (canopy < 30%, n = 97) | +0.012 | −0.004 | +0.014 | −0.002 |
| Line-of-sight excess, mm | −0.3 | +0.1 | +0.05 | +0.3 |

- The coherence differences are about 1% of the coherence itself. They also change sign between the two registrations. The shifted run's p = 0.005 rests on −0.005.
- The open-pit HV result (+0.014, p = 0.01 as delivered) disappears once shifted (p = 0.51).
- In a single pair, pit-minus-ring motion scatters by 7.6 mm in HH. Decoys scatter by 7.4 mm. That scatter is phase noise, not pit motion.
- Pooled over 21 pairs, pit motion relative to ring is −0.3 mm, with a CI of −0.6 to +0.2 mm.

## Interpretation

- **No pit signal in coherence or phase at 5 m.** This supports the reappraisal. A pit is one or two pixels, and the 3 × 3 estimate mixes it with the ground around it.
- **No motion either.** In a 12-day pair, phase noise is about 7.5 mm per pit. A pit would have to settle by more than about 15 mm in 12 days to stand out in one pair. Pooled, the result rules out an average relative motion larger than about 1 mm per pair.
- **The sample chips show why.** In 120 m windows the pit outlines fall within one or two coherence cells, and nothing in the coherence or phase follows the pit rim.
- **Coherence over the whole tile is useful in its own right.** It is 0.5–0.68 in snow-free 12-day pairs. That supports cluster-scale or slope-scale motion work, option 3 of the reappraisal, not pit-scale work.

## Outputs

In `data/9t/results/nisar/`:
- `nisar_gslc_interferogram_pits_vs_decoys_win3_9t_5m_summary.json`, `..._by_pair.csv`, `..._per_pit_per_pair.csv`
- the same three with `_forcedshift` for the shifted run
- `figures/nisar_gslc_interferogram_pits_vs_decoys_win3_9t_5m_by_pair_hh.png` (and `_forcedshift_`)
- `figures/nisar_gslc_interferogram_sample_pits_open_vs_canopy_hh_win3_t090A_20260912_20260924_9t_5m.png`

In `data/9t/derived/nisar_gslc_5m/` (gitignored), for the best pair:
- `nisar_interferogram_coherence_hh_win3_t090A_20260912_20260924_9t_5m.tif`
- `nisar_interferogram_wrapped_phase_rad_hh_win3_t090A_20260912_20260924_9t_5m.tif`

Figure colours: pits `#1F5FA8` circles and decoys `#D97706` squares. This is the lost/found pair, checked with dataviz `validate_palette.js --mode light --pairs all`, worst pair ΔE 21.1 deutan. Coherence and amplitude are greyscale. Phase uses the cyclic "twilight" map, purple to white to orange, with no green.

## Limits

- NISAR beta and provisional data are not yet validated for interferometry.
- 9 looks bias coherence upward. A larger window would mix in more of the ring.
- Registration to the lidar is weak (canopy correlation ρ ≤ 0.07). The shifted run is a bracket, not a fix.
- No spring dates. Water in pits in March–April may change both brightness and coherence.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py --force-best-shift
```
