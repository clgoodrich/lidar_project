# NISAR review fixes and the flatten/gain test (2026-10-19)

## Goal

A code review of the NISAR stack raised five defects and one set of open questions about the
bright-target screen. This pass checks each claim against the code, fixes the five, and tests the two
radiometric questions (terrain flattening, per-date gain) on the bright-target screen.

## What was checked and what was found

| # | Claim | Verdict | Change |
|---|---|---|---|
| 1 | Missing radar samples count as zero power in seasonal means and coherence | Confirmed in the code. Effect on results is nil on 9t (no zero pixels in any date) and small on 613590 (track 162 has 1-2% zero at the swath edge). | A sample of exactly 0 is "no sample". It becomes NaN at load. A seasonal pixel needs valid samples on at least half of the season's dates. A coherence window needs at least half valid samples. |
| 2 | A date missing from the offsets table silently gets (0, 0) while the record says `coreg=True` | Confirmed. | `write_stack` raises `KeyError` when `--coreg` is set and a date has no row. |
| 3 | The pad-event p-value treats 13,629 pad-pair rows as independent trials | Confirmed. | Added a swap test (below). The naive binomial p stays in the table for comparison. |
| 4 | `rtc_area_factor` and `layover_shadow` are never called, so there is no radiometric flattening | Confirmed. A better normaliser already existed: the lidar area-projection simulation (`simulate` in `_nisar_lidar_sim_match_9t.py`), which bins facet area into radar cells the way Small (2011) does. | Flattening now uses that simulation. Bands 5 and 6 of the bright-target layers hold the flattened mean HH and its 250 m contrast. |
| 5 | Slope-motion phase is summed before the coherence mask, and across broken date chains | Confirmed. | Each pair adds phase only where it is itself coherent (>= 0.45). A pixel keeps a displacement only if every pair of the chain is coherent there. The date chain must be connected; the longest connected run is kept. |

Also fixed (found in the same review): the `in_lidar` mask in `_nisar_bright_targets_9t.py` was built
before the sort and reset, then applied after it. It now follows the sort. It only affected the
`share_by_context_in_lidar` summary.

Not changed, deferred (see BACKLOG): the cross-track merge rule, native RSLC chip measurement,
calibration-table retention, epoch handling in `lidar_heights`, an independent reflector validation set.

## Fix 3: the swap test

Unit: one pad with its five decoy copies, six whole time series over the same pairs.
Null: the pad is no different from a decoy, so any of its six series could be "the pad".
Each of 2,000 permutations picks one series per pad, refits the 1% threshold from the other
series, and counts flags. Whole series are swapped, so repeated pads, shared acquisitions and the
threshold fitted on the decoys all sit inside the null. Statistic: pad flag rate minus decoy flag rate.

Result, 9t, lidar-placed stack (`data/9t/results/nisar/nisar_pad_change_by_season_9t_slc.csv`):

| Season | Pad events | Expected from decoys | Naive binomial p | Swap-test p | Excess rate | Null 95th pct |
|---|---:|---:|---:|---:|---:|---:|
| Snow-free | 169 | 136.4 | 0.0037 | 0.001 | 0.0024 | 0.0012 |
| Winter | 13 | 13.1 | 0.55 | 0.51 | -0.0001 | 0.0045 |

Event counts did not change from the earlier run (fix 1 has no effect on 9t). The snow-free excess
survives the dependence-aware test. 0.001 is the floor for 2,000 permutations (one permutation in
2,000 reached the observed value). It stays a candidate: the test says pads flag more than their
decoys, not that the flags are disturbance. 613590 has no pad-change result: 0 of 995 annotated pads
fall inside its window.

## Fix 1 on the saved results

- 9t pad-change events: identical before and after.
- 613590 pit interferogram table (`..._per_pit_per_pair.csv`, 1,152 rows): pit and decoy values
  unchanged to four decimals. Only the tile-median coherence moved, in 25% of rows (swath-edge pixels).

## Fix 5 on 9t slope motion

Same pairs and same mean-coherence share, stricter accumulation
(`data/9t/results/nisar/nisar_slope_motion_summary_9t_slc.json`):

| | Before | After |
|---|---:|---:|
| Track 090 displacement spread (std) | 17.5 mm | 10.9 mm |
| Track 162 displacement spread | 16.0 mm | 9.8 mm |
| Track 026 displacement spread | 9.0 mm | 7.7 mm |
| 090 vs 162, pixels compared | 7,698 | 410 |
| 090 vs 162, Pearson r (all slopes) | 0.077 | 0.173 (block 95% CI 0.063 to 0.28) |
| Wells with coherent chain / flagged | 282 / 0 | 15 / 0 |

Reading: pairs that were not coherent were adding noise, so the spread falls by 30-40%. The
correlation rises, but on 5% of the pixels, and the CI is wide. The aspect split now has 4, 68 and
11 pixels, too few to read. The rule (every pair coherent, 0.45) is strict. 613590 has no summer
pairs on track 162, so the 090-vs-162 test does not run there.

## The flatten/gain test

Script: `notebooks/wellsight_v2/s5_eval/_nisar_flatten_gain_test_9t.py`.
Same screen as `_nisar_steel_9t.py` (D_A < 0.25, 6 dB over the 250 m median), four variants on the
same valid pixels: raw, per-date gain normalised, terrain flattened, both. Flattening divides power
by the simulated facet-area factor (bare earth) and drops cells with more than 20% shadow or layover.

Outputs, per area, in `data/<area>/results/nisar/`:
`nisar_flatten_gain_test_counts_<tag>.csv`, `nisar_flatten_gain_test_track_agreement_<tag>.csv`,
`nisar_flatten_gain_test_summary_<tag>.json` (tag `9t_slc` or `613590_slc`).

SBT pixels per track:

| Area | Track | Dates | Gain range | Raw | Gain | Flat | Both |
|---|---:|---:|---:|---:|---:|---:|---:|
| 9t | 026 | 8 | 2.8 dB | 773 | 960 | 554 | 702 |
| 9t | 090 | 11 | 1.2 dB | 1,828 | 1,842 | 1,375 | 1,387 |
| 9t | 162 | 14 | 3.3 dB | 170 | 221 | 148 | 196 |
| 613590 | 026 | 8 | 2.6 dB | 956 | 1,113 | 800 | 931 |
| 613590 | 090 | 11 | 1.0 dB | 1,798 | 1,803 | 1,336 | 1,358 |
| 613590 | 162 | 6 | 3.0 dB | 1,533 | 2,042 | 1,282 | 1,796 |

Agreement between tracks, brightness-over-median maps, Pearson r:

| Pair | Area | Raw | Gain | Flat | Both |
|---|---|---:|---:|---:|---:|
| 090 vs 162 (both look west) | 9t | 0.344 | 0.350 | 0.294 | 0.298 |
| 090 vs 162 | 613590 | 0.326 | 0.336 | 0.306 | 0.314 |
| 026 vs 090 (opposite looks) | 9t | -0.056 | -0.060 | -0.001 | -0.002 |
| 026 vs 162 | 9t | -0.064 | -0.068 | -0.015 | -0.015 |
| 026 vs 090 | 613590 | 0.017 | 0.018 | 0.054 | 0.058 |
| 026 vs 162 | 613590 | 0.006 | 0.007 | 0.026 | 0.031 |

SBT of track A with an SBT of track B within 15 m, against the chance share from a shifted mask
(`..._track_agreement_...csv`): 090 vs 162 on 9t, 7.5% raw and 5.9% flat against about 0.3% chance.

### Interpretation

- **Flattening works as a normaliser.** The opposite-look pair (026 against the ascending tracks)
  goes from a negative correlation (-0.06) to about zero on 9t. A negative value is what an
  uncorrected terrain term gives: a slope bright from one side is dark from the other.
- **It removes 25-30% of SBT pixels.** These are slope-facing facets. About 70% of the screen's
  hits survive, so it was mostly reading real contrast.
- **The 090-vs-162 agreement falls a little (0.34 to 0.29).** Both tracks look west, so part of
  their shared signal was shared terrain illumination. What remains (r about 0.3, SBT overlap over 20 times
  chance on 9t) is not terrain.
- **Gain normalisation matters most on track 162.** SBT counts rise 30% on 613590 track 162 (1,533
  to 2,042) once each date is divided by its scene median. The dates there span 3 dB. A date-varying
  gain inflates D_A and hides real stable targets. Part of the 1-3 dB date spread is real
  (season, moisture), so gain normalisation is a correction that also removes some real signal.
  It is not yet a default.
- **Caveat.** The factor is a distributed-target normaliser from the bare-earth simulation. It is
  not a point-target calibration. Calibration tables are still not carried through the RSLC
  subsetter.
- **Oddity, unexplained.** 613590 track 162 (beta dates only) has a mean HH power near -14 dB,
  about 6 dB below every other track and area (-6 to -8.5 dB).

## The 613590 seasonal test is sensitive to the decoy draw

Re-running `_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc --area 613590` printed a pit table that
differed from the saved CSV. A controlled comparison found the cause. All runs wrote to a scratch
folder (C:/Users/colto/AppData/Local/Temp/claude/C--Users-colto-Documents-GitHub-lidar-project/ab3360bc-5677-4af3-8b45-906def933ed8/scratchpad/ab/), so nothing in the repo changed.

- The script as committed (HEAD) reproduces the saved CSV exactly. The saved numbers are not stale.
- Fix 1 leaves every pit value unchanged (`median_feature_minus_ring_db` identical in all 8 rows).
  Only the decoys move. Zero-valued pixels leave the seasonal means, which changes the valid-pixel
  mask the decoys are drawn from, so the random draws change.
- Two more seeds (20260931, 20260932) with the fixed script show how far a draw alone moves the result.

Median pit excess over decoys, HH, dB (Wilcoxon p in brackets):

| Metric | Saved (old code) | Fixed, seed 0 | Fixed, seed 1 | Fixed, seed 2 |
|---|---:|---:|---:|---:|
| Leaf-off fall | 0.38 (0.018) | 0.52 (0.001) | 0.64 (0.001) | 0.63 (<0.001) |
| Winter | 0.51 (0.022) | 0.26 (0.035) | 0.56 (0.018) | 0.31 (0.069) |
| Leaf-on | 0.28 (0.048) | 0.15 (0.033) | 0.41 (0.031) | 0.22 (0.044) |
| Change, leaf-on vs fall | -0.36 (0.131) | -0.72 (0.004) | -0.71 (0.038) | -0.49 (0.038) |

Reading:
- A different decoy draw alone moves the excess by about 0.2 to 0.3 dB and a p-value anywhere from
  0.001 to 0.13. Single-draw p-values on 613590 are not stable.
- The HH leaf-off fall excess is positive in all four runs (0.38 to 0.64 dB, p 0.018 or lower). It is
  the one pit result that holds across draws. The winter, leaf-on and change rows do not.
- The test uses five decoys per pit. Averaging over many draws (or a permutation test as in fix 3)
  would give a stable number. Not done.
- The repo's saved 613590 seasonal files are still the old ones. The raster write hits a file locked
  by another program, so the real-path rerun waits for the lock to clear. The fixed numbers above
  come from the scratch runs.

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_nisar_pad_change_9t.py --slc
python notebooks/wellsight_v2/s5_eval/_nisar_slope_motion_9t.py --slc
python notebooks/wellsight_v2/s5_eval/_nisar_flatten_gain_test_9t.py --slc
python notebooks/wellsight_v2/s5_eval/_nisar_flatten_gain_test_9t.py --slc --area 613590
python notebooks/wellsight_v2/s5_eval/_nisar_gslc_interferogram_pits_9t.py --slc --area 613590
```

Scratch audits (not saved in the repo): per-date zero-pixel share and per-date median power.
