# NISAR radar brightness over well pads against the forest around them, 9t

**Date:** 2026-09-26
**Status:** done. First test of the pad-scale claim in `docs/nisar_lidar_supplement_proposal.md`.
**Script:** `notebooks/wellsight_v2/s5_eval/_nisar_gcov_pad_vs_forest_backscatter_9t.py`

## Goal

NISAR gives no elevation, so it cannot find pits.
The supplement proposal says it can still describe the ground at pad scale.
This test asks the simplest form of that question.
Is an annotated pad brighter or darker on the radar than the forest right around it?

## Data

| Input | Detail | Path |
|---|---|---|
| NISAR L2 GCOV, beta V1 | 2026-01-20, ascending, left-looking, frequency A. 10 m grid, EPSG:32617. RTC gamma-0 in HH and HV, linear power. About 5.3 looks per pixel. | `data/_source/reference/nisar/9t/NISAR_L2_GCOV_BETA_V1/NISAR_L2_PR_GCOV_010_162_A_023_4005_DHDH_A_20260120T101554_20260120T101629_X05010_N_F_J_001.h5` |
| Pads | `plat` layer, 995 pads | `qgis/annotations/annotations_proj.gpkg` |
| Roads | `roads` layer, kept out of the forest ring | same file |
| 2019 canopy height | 1 m CHM from the 9t lidar | `data/9t/derived/1m/chm_9t_1m.tif` |

Terms:
- **HH** is sent and received horizontally. Over forest it is dominated by trunks and the ground below them.
- **HV** is sent horizontally and received vertically. It comes mostly from canopy volume.
- **gamma-0** is backscatter corrected for terrain slope (Small 2011). Pads on hillsides can then be compared with flat ones.

## Method

- **Pad core pixel.** A 10 m pixel whose centre is at least 5 m inside the pad. The pixel then lies wholly inside the pad.
- **Forest ring pixel.** Centre 20–60 m outside the pad, and at least 10 m from any pad or annotated road.
  The ring is each pad's own local comparison. Slope, aspect and look angle are close to the pad's.
- **Per-pad value.** Mean of linear gamma-0 over the pixels, then converted to dB.
- **Statistics.**
  - Paired pad-minus-ring difference, tested with the Wilcoxon signed-rank test.
  - AUC, meaning the chance a random pad is brighter than a random ring. 0.5 is no separation. Below 0.5 means pads are darker.
  - 95% CI on the median difference from 2000 bootstrap resamples of pads.
- **Canopy strata.** Each pad is sorted by its 2019 lidar canopy cover. Cover is the share of 1 m cells taller than 2 m.
- **Positive control.** All 9t pixels under 10% canopy against all pixels over 90%. Radar that cannot separate these cannot separate pads.
- **Registration check.** The canopy/HV correlation is recomputed with the lidar sampled up to 40 m off each NISAR pixel.

345 of 995 pads are too small or too thin to hold one whole 10 m pixel. 650 pads are tested.

## Results

### Registration: the radar sits about one pixel off the lidar

The canopy/HV correlation peaks at dx −10 m, dy −5 m (Spearman ρ 0.162 against 0.138 unshifted).
The peak is clear and well inside the searched range.
So the radar image sits about 10 m east and 5 m north of the lidar.
This is beta, pre-calibration data, so an offset of this size is not surprising.

Both georeferencings are reported below.
- **As delivered** uses the product's own coordinates.
- **Aligned** moves the NISAR grid by the measured shift. Pixel values do not change.

The shift is measured off a weak correlation, so it is itself uncertain by about 5 m.

### Positive control: this January image barely separates open ground from forest

| | As delivered | Aligned |
|---|---|---|
| HH, open / closed canopy (median dB) | −8.40 / −8.02 | −8.42 / −8.00 |
| HH AUC, closed brighter | 0.553 | 0.562 |
| HV, open / closed canopy (median dB) | −16.76 / −15.84 | −16.82 / −15.73 |
| HV AUC, closed brighter | 0.620 | 0.638 |

Forest is only about 1 dB brighter than open ground in HV.
A single pixel gets the answer right about 62% of the time.

### Pads against their own forest ring

Median pad-minus-ring difference in dB, with its 95% CI. AUC below 0.5 means pads are darker.

**As delivered**

| Pads, by 2019 canopy | n | HH diff | HH AUC | HV diff | HV AUC |
|---|---|---|---|---|---|
| all | 650 | −0.44 [−0.56, −0.30] | 0.377 | −0.12 [−0.20, −0.00] | 0.462 |
| open (<25%) | 76 | −0.86 [−1.16, −0.48] | 0.300 | −0.31 [−0.50, −0.16] | 0.417 |
| partly grown (25–50%) | 269 | −0.49 [−0.71, −0.21] | 0.393 | −0.17 [−0.35, −0.02] | 0.433 |
| grown over (>50%) | 305 | −0.30 [−0.50, −0.19] | 0.385 | +0.03 [−0.12, +0.12] | 0.497 |

**Aligned**

| Pads, by 2019 canopy | n | HH diff | HH AUC | HV diff | HV AUC |
|---|---|---|---|---|---|
| all | 650 | −0.28 [−0.37, −0.19] | 0.421 | −0.06 [−0.17, +0.04] | 0.484 |
| open (<25%) | 71 | −0.78 [−0.94, −0.35] | 0.338 | −0.40 [−0.64, −0.28] | 0.385 |
| partly grown (25–50%) | 260 | −0.35 [−0.51, −0.19] | 0.403 | −0.23 [−0.36, −0.03] | 0.448 |
| grown over (>50%) | 319 | −0.17 [−0.28, +0.00] | 0.458 | +0.13 [−0.03, +0.21] | 0.536 |

Stratum counts differ between runs because canopy cover is re-sampled on the moved grid.
The HH/HV ratio results are in the summary JSON. They add nothing beyond HH.

## Interpretation

- **Pads are slightly darker than the forest around them, mostly in HH.**
  Bare or grassy ground is smoother than forest. It sends less signal back, and it lacks the trunk-to-ground bounce that brightens HH.
- **The more open the pad, the larger the difference.**
  Open pads are about 0.8–0.9 dB darker in HH. A pad is darker than a random ring pixel about 66–70% of the time.
  Grown-over pads are nearly indistinguishable from forest in HV.
  So the signal comes from the clearing, not from anything specific to a well.
- **The signal is real but too weak to detect pads.** Each pad is tested against its own ring, and 30% of open pads still come out brighter.
  Speckle is one reason. At 5.3 looks a single pixel scatters by about ±2 dB, and a small pad averages only a few pixels.
- **The image date is a poor one.** 20 January is leaf-off, and the ground was likely frozen or under snow. The winter InSAR pair from the same date lost coherence for the same reason.
  Both conditions shrink the contrast between forest and open ground. The weak positive control shows it.
- **Alignment does not change the conclusion.** The aligned run shrinks the all-pad HH difference from −0.44 to −0.28 dB. It keeps every sign and the open-pad effect.
  The raw registration estimate is too noisy to prefer one run over the other.

**Bottom line.** One January NISAR image carries a faint pad signal, strongest where the pad is still open. It can help characterise a candidate that lidar has already found. It cannot find pads on its own.

## Limits

- One beta image, from one winter date. Validated CONUS products were expected from about July 2026.
- The pads come from 2019 lidar. Some may have regrown or been disturbed by 2026, so the image is seven years later than the labels.
- 35% of pads are too small to hold a whole 10 m pixel and are not tested.
- The rings of neighbouring pads can overlap, and the pads cluster. The bootstrap resamples pads, not areas, so the CIs are somewhat too narrow.

## Next steps

These are logged in `docs/iterations/BACKLOG.md`.
1. Repeat with a leaf-on, snow-free GCOV granule, and with a fall one. If contrast is seasonal, the control AUC should rise.
2. Average several dates to beat speckle. This is the time-series use the proposal argues for.
3. Measure the registration against a sharp target, such as a road cut or a reservoir edge, rather than canopy correlation.

## Outputs

- `data/9t/derived/nisar_10m/nisar_gcov_hh_gamma0_db_20260120_9t_10m.tif` is HH gamma-0 in dB, clipped to 9t, in the as-delivered georeference.
- `data/9t/derived/nisar_10m/nisar_gcov_hv_gamma0_db_20260120_9t_10m.tif` is the same for HV.
- In `data/9t/results/nisar/`:
  - `nisar_gcov_pad_vs_forest_ring20to60m_per_pad_hh_hv_20260120_asdelivered_9t.csv`
  - `nisar_gcov_pad_vs_forest_ring20to60m_per_pad_hh_hv_20260120_aligned_9t.csv`
  - `nisar_gcov_pad_vs_forest_ring20to60m_summary_hh_hv_20260120_asdelivered_9t.json`
  - `nisar_gcov_pad_vs_forest_ring20to60m_summary_hh_hv_20260120_aligned_9t.json`
  - `nisar_gcov_pad_vs_forest_run_asdelivered_9t.log`
  - `nisar_gcov_pad_vs_forest_run_aligned_9t.log`
- In `data/9t/results/nisar/figures/`:
  - `nisar_gcov_pad_vs_forest_ring20to60m_hh_hv_by_2019_canopy_20260120_asdelivered_9t.png`
  - `nisar_gcov_pad_vs_forest_ring20to60m_hh_hv_by_2019_canopy_20260120_aligned_9t.png`

The figure colours are the lost/found pair `#1F5FA8` (pad) and `#D97706` (forest ring). They were validated with the dataviz `validate_palette.py --mode light --pairs all`, giving worst-pair ΔE 21.1 for deuteranopia. Pad and ring also differ by marker and position. HH and HV use grey and black with different markers.

## Reproduce

```bash
python notebooks/wellsight_v2/s5_eval/_nisar_gcov_pad_vs_forest_backscatter_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_gcov_pad_vs_forest_backscatter_9t.py --align
```
