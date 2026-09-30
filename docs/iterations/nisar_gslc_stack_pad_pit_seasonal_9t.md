# NISAR multi-date brightness at 5 m: pads and pits against their surroundings and against decoys, 9t

**Date:** 2026-09-30
**Status:** done. This follows `docs/iterations/nisar_gcov_pad_vs_forest_backscatter_9t.md` and is option 1 of the reappraisal in the 2026-09-30 analysis log entry.
**Scripts:**
- fetch: `notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py`
- analysis: `notebooks/wellsight_v2/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py`

## Goal

One January image gave a faint pad signal, too grainy to read pad by pad.
Averaging many dates suppresses the grain, and the full-resolution product is posted at 5 m, not 10 m.
The test asks three things:
- whether pads then separate from their surroundings
- whether the leaf-on against leaf-off change separates them
- whether anything shows at pit scale

## Data

**Source.** NISAR L2 GSLC, the geocoded full-resolution image with phase kept.
- Beta collection: 2025-10-28 to 2026-01-20.
- Provisional collection: 2026-06-20 to 2026-09-24.
- Mode "4005": the main band is 40 MHz, with a 5 MHz side band. The centre frequency is 1.239 GHz, a wavelength of 24.2 cm.
- Posting is 5 m in EPSG:32617. Polarizations are HH and HV.

**Only the 9t window was read.** Each GSLC file is about 22.6 GB and is stored in 512 × 512 gzip chunks.
- The fetch reads the file index, then requests only the chunks that cover 9t plus 200 m, over HTTPS.
- Each saved window is about 9.3 MB, 981 × 981 pixels, with complex HH and HV.
- 32 windows came to 300 MB on disk, instead of about 720 GB of whole files.

**Acquisitions used.** 32 unique date-and-track pairs were fetched. One is dropped: 2026-07-22 on track 026D has no valid pixels over 9t.

| Track | Leaf-off fall (Oct–Nov 2025) | Winter (Dec 2025–Jan 2026) | Leaf-on (Jun–Sep 2026) |
|---|---|---|---|
| 026 descending | 1 | 2 | 5 |
| 090 ascending | 1 | 1 | 8 |
| 162 ascending | 3 | 3 | 7 |

**Other inputs.**
- Annotations: pads are the `plat` layer and pits are `pit_outside`, the whole pit including its rim. Roads are used only for exclusion zones.
- 2019 canopy cover from `data/9t/derived/1m/chm_9t_1m.tif`: the share of 1 m cells taller than 2 m in each 5 m pixel.

## Method

- **Brightness.** Intensity is |s|². It is averaged per track and season in linear power.
- **Seasonal change.** It is a ratio of means over a set of pixels, mean(leaf-on) / mean(leaf-off fall), in dB. It is taken within one track, so terrain and viewing geometry cancel.
- **Pad test.** Core pixels have their centre at least 3 m inside the pad. The ring is 20–60 m outside, kept 10 m clear of every pad and road.
- **Pit test.** The pixels are those inside the whole pit. The ring is 10–30 m outside, kept 5 m clear of every pit and road.
- **Decoys.** These are the key control.
  - Radar brightness is right-skewed, so the mean of a few pixels sits below the mean of many, even over the same ground.
  - A pit covers about 8 pixels and its ring hundreds. That alone makes a pit look darker than its ring.
  - Each feature therefore gets 5 decoys: the same shape moved 150–600 m onto background at least 20 m from any pad, pit or road. Each decoy gets a ring built the same way.
  - The **excess** is the feature's difference from its ring, minus the median of its decoys' differences. Only the excess is evidence.
- **Positive control, per pixel.** Background pixels under 10% canopy are compared with pixels over 90%. Comparing single pixels has no size effect.
- **Registration.** Each track's leaf-on HV mean is correlated with canopy cover at shifts of −20 to +20 m. A shift is applied only if the best correlation is at least 0.10. A sensitivity run, `--force-best-shift`, applies each track's best shift anyway.
- **Statistics.** Tracks are computed separately, then averaged per feature. Tests are the Wilcoxon signed-rank on the excess and the AUC of feature differences against all decoy differences. 95% CIs bootstrap the features.

## Results

### What the decoys changed

A first trial had no decoys. Pits looked 2.4 dB darker than their rings in seasonal change, and pads 1.5 dB darker.
The same run showed open and closed canopy with identical seasonal change, pixel by pixel.
Those two findings cannot both be real. The decoys confirm that the trial's effect came from feature size.
Decoys alone come out 0.1–0.4 dB darker than their rings, with no feature present.

This also applies to the earlier GCOV pad test, which compared small pads with large rings in the same way. Its −0.44 dB includes some size effect. That doc now carries a note.

### Positive control: at 5 m, open ground and forest barely differ

AUC is the chance a closed-canopy pixel is brighter than an open one, per track. 0.5 means no separation.

| Metric | Track 026D | Track 090A | Track 162A |
|---|---|---|---|
| HH leaf-on | 0.537 | 0.495 | 0.515 |
| HV leaf-on | 0.542 | 0.515 | 0.517 |
| HV winter | 0.558 | 0.531 | 0.521 |
| HV seasonal change | 0.480 | 0.500 | 0.516 |

- **Leaves barely register.** L-band at 24 cm is scattered mostly by trunks and branches. Leaves are nearly transparent to it, so leaf-on against leaf-off does not track canopy at all.
- **Per-pixel noise is still large.** A 5 m pixel averaged over 1–8 single-look dates carries speckle of several dB. The GCOV test's HV AUC of 0.62 was on 10 m pixels, terrain-corrected, with about 5 looks per date.

### Registration: unresolved, but a consistent pattern

| Track | ρ unshifted | Best ρ | Best shift (dx, dy) |
|---|---|---|---|
| 026 descending | 0.049 | 0.068 | +10, −10 m |
| 090 ascending | 0.016 | 0.047 | −15, −5 m |
| 162 ascending | 0.021 | 0.063 | −10, −5 m |

- No track reaches the 0.10 bar, so the primary run uses the data as delivered.
- The pattern is still physically consistent:
  - Track 162's best shift equals the offset measured on the track-162 GCOV image, (−10, −5) m.
  - The two ascending tracks agree with each other.
  - The descending track points the other way in x. That is what a shift along the radar's range direction would do, since range points the opposite way for the two look directions.
- The offset is about 1–3 pixels. At pit scale that matters, so both runs are reported.

### Pads and pits against their decoys

Excess is the median of feature-minus-ring minus decoy-minus-ring, in dB, with its 95% CI.
AUC below 0.5 means features are darker than decoys.

**As delivered**

| Feature | Metric | Excess (dB) | AUC vs decoys |
|---|---|---|---|
| pad (647) | HH leaf-on | −0.23 [−0.29, −0.18] | 0.382 |
| pad | HV leaf-on | −0.20 [−0.25, −0.16] | 0.382 |
| pad | HV seasonal change | −0.16 [−0.22, −0.09] | 0.424 |
| pit (506) | HH leaf-on | −0.02 [−0.12, +0.09] | 0.507 |
| pit | HV leaf-on | −0.07 [−0.20, +0.02] | 0.476 |
| pit | HH leaf-off fall | +0.18 [+0.07, +0.35] | 0.553 |
| pit | HV seasonal change | −0.15 [−0.24, +0.03] | 0.456 |

**Best shift forced (sensitivity)**

| Feature | Metric | Excess (dB) | AUC vs decoys |
|---|---|---|---|
| pad | HH leaf-on | −0.32 [−0.38, −0.28] | 0.346 |
| pad | HV leaf-on | −0.40 [−0.46, −0.36] | 0.285 |
| pad | HV seasonal change | −0.13 [−0.20, −0.08] | 0.435 |
| pit | HH leaf-on | −0.40 [−0.51, −0.30] | 0.380 |
| pit | HV leaf-on | −0.45 [−0.57, −0.32] | 0.358 |
| pit | HV leaf-off fall | −0.41 [−0.52, −0.21] | 0.408 |
| pit | HV seasonal change | −0.01 [−0.21, +0.09] | 0.486 |

The full tables, with winter and every polarization, are in the summary CSVs.

## Interpretation

- **Pads carry a real but small signal.** They are 0.2–0.4 dB darker than same-shaped decoys, in both polarizations, in every season, and in both registrations.
  - At best, a pad is darker than a decoy 71% of the time (HV leaf-on, aligned).
  - That is a consistent statistical difference, not a detector.
- **Pits show a signal only when the data are shifted onto the lidar.** As delivered, pits are indistinguishable from their decoys. With the best shift forced, they are about 0.4 dB darker, and darker than a decoy about 62–64% of the time.
  - The shift was chosen from canopy correlation, not from pits, so it was not tuned to produce this.
  - Clearings do feed into the canopy correlation, though, so the check is not fully independent.
  - The pit result therefore depends on alignment we cannot yet pin down. It is suggestive, not established.
- **The seasonal change adds nothing.** L-band barely sees leaves, so leaf-on against leaf-off does not separate clearings from forest.
  - The whole tile is brighter in summer than in fall, by different amounts per track (HV): +1.9 dB on track 162, +2.9 dB on 090, and +4.2 dB on 026.
  - A real seasonal change should be about the same on every track. Spread like this points to a calibration difference between the beta and provisional processing, made noisier by the single fall date on 090 and 026.
  - Feature-minus-ring differences cancel that offset. Absolute summer-against-fall numbers should not be quoted.
- **The brightness route is now close to exhausted for 9t.** Even with 31 dates at 5 m, pads differ from background by a few tenths of a dB. Only a better-aligned, larger stack, or spring dates with water in the pits, would change that.

## What would change the picture

Logged in `docs/iterations/BACKLOG.md`.

1. **Independent registration.** Use point-like bright targets, such as active pumpjacks, tanks or buildings, located in the lidar DSM. That would fix the 5–15 m offset without relying on canopy correlation. It decides whether the pit signal is real.
2. **Spring dates (March–April).** Standing water under bare trees gives the flooded-forest double bounce in HH. This is the one mechanism that could make a pit bright, not faintly dark.
3. **Coherence (option 2 of the reappraisal).** The complex windows are already saved, so coherence needs no new download.

## Limits

- Leaf-off fall has only 1 date on tracks 026 and 090, so their fall and seasonal-change values are noisy.
- The beta and provisional collections were processed differently. Feature-minus-ring differences cancel any tile-wide offset, but not an offset that varies across the tile.
- The GSLC is not terrain-flattened, so a flat pad and a sloping ring can differ for geometric reasons. The decoys share this only on average.
- Decoys avoid features by 20 m, but they can land on unannotated clearings, which would shrink the excess.
- Pads and pits are annotated from 2019 lidar, and the radar is from 2025–26.

## Outputs

In `data/9t/derived/nisar_gslc_5m/` (gitignored by the `data/**/derived/**` rule):
- `nisar_gslc_hh_hv_complex_<yyyymmdd>_t<track><A|D>_9t_5m.tif`: 32 windows of complex HH and HV.
- `nisar_gslc_window_index_9t_5m.csv`: track, frame, collection, bandwidth, centre frequency and valid fraction for each window.
- `nisar_<pol>_<season>_track<NNN>_9t_5m.tif`: per-track season means in dB, as delivered (not shifted to the lidar).
  - `<season>` is `fall_2025` (Oct-Nov), `winter_2025_26` (Dec-Jan) or `summer_2026` (Jun-Sep, leaf-on).
  - Tracks 162 and 090 are ascending. Track 026 is descending.
  - Example: `nisar_hv_summer_2026_track162_9t_5m.tif`
- `nisar_<pol>_change_summer_minus_fall_track<NNN>_9t_5m.tif`: summer mean minus fall mean, in dB.
- Renamed twice on 2026-09-30, first from `..._mean_db_t162A_...` and then to these short names. Both passes are logged in `docs/MOVES.csv`, with phases `nisar_readable_names` and `nisar_short_names`.

In `data/9t/results/nisar/`:
- `nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_9t_5m.csv` and `.json`
- `nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_forcedshift_9t_5m.csv` and `.json`
- `nisar_gslc_stack_{pad,pit}_vs_ring_and_decoys_per_feature_9t_5m.csv` and the `_forcedshift` versions
- `nisar_gslc_stack_open_vs_closed_canopy_control_by_track_9t_5m.csv` and the `_forcedshift` version
- `nisar_gslc_window_fetch_run_9t.log`, `nisar_gslc_stack_run_9t.log` and `nisar_gslc_stack_run_forcedshift_9t.log`

In `data/9t/results/nisar/figures/`:
- `nisar_gslc_stack_pad_pit_vs_decoy_leafon_leafoff_seasonal_change_9t_5m.png`
- `nisar_gslc_stack_pad_pit_vs_decoy_leafon_leafoff_seasonal_change_forcedshift_9t_5m.png`

Figure colours: features are `#1F5FA8` circles and decoys are `#D97706` squares. That is the lost/found pair, with worst all-pairs ΔE 21.1 for deuteranopia. The maps use greyscale, and PuOr (purple to orange, no green) for signed change.

QGIS project, added 2026-09-30:
- `qgis/nisar_gslc_seasonal_backscatter_draped_on_lidar_dem_9t_5m.qgz` holds all 24 season rasters.
  - There is one group per track, and it opens on track 162 HV leaf-on.
  - Season means are grey. Seasonal change is blue-white-orange, centred on each raster's own median.
  - Pads have solid blue outlines and pits have dashed orange outlines. Both have a white halo.
  - The 9t lidar DEM is the project terrain. View > 3D Map View drapes the visible radar layer on it.
- Built by `notebooks/wellsight_v2/s6_review/_build_nisar_gslc_qgis_project_9t.py`, run with QGIS's own python.

## Reproduce

```bash
python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py            # ~40 min, ~1-2 GB transferred
python notebooks/wellsight_v2/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --force-best-shift
"C:/Program Files/QGIS 3.40.10/bin/python-qgis-ltr.bat" notebooks/wellsight_v2/s6_review/_build_nisar_gslc_qgis_project_9t.py
```
