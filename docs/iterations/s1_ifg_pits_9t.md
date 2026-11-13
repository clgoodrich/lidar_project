# Sentinel-1 C-band interferograms at pits, Oct-Nov 2025 and April 2017-2026 (9t, 613590)

Run 2026-11-13. The NISAR L-band pit test repeated with Sentinel-1 C-band. Autumn 2025 matches NISAR track 162. Early to mid April (25 Mar to 20 Apr) adds the leaf-off spring that NISAR does not have.

## Goal

Ask whether pits show a coherence or line-of-sight phase difference from matched decoys at C-band.
Use the same pits, rings, decoys and seed as the NISAR run (`_nisar_gslc_interferogram_pits_9t.py`).

## Data

- OPERA CSLC-S1 V1 (NASA JPL OPERA, distributed by ASF DAAC). Geocoded complex SLC bursts, VV only, 5 m x 10 m, UTM 17N, flattened.
- Search is NASA CMR by point. Windows `octnov2025` (2025-10-01 to 11-30), `apr2025` and `apr2026` (25 Mar to 20 Apr). 17 bursts, all Sentinel-1A. No Sentinel-1C bursts were returned.
- Two burst IDs. T077-163486-IW2 covers both areas. T004-006689-IW1 covers only the east edge of 9t (58 to 60 pits). Both are ascending.
- Autumn, five dates per burst at 12 days. T004: 10-07, 10-19, 10-31, 11-12, 11-24. T077: 10-12, 10-24, 11-05, 11-17, 11-29.
- April 2025. T004 03-29 and 04-10. T077 04-03 and 04-15.
- April 2026. T077 03-29 and 04-10. T004 has one date (04-05), so no pair.
- April 2017 to 2024. 34 more dates, read as windows only by `_s1_cslc_window_fetch_9t.py` (HTTPS byte ranges, about 14 MB a date, 426 MB in all, `data/_source/s1_cslc_windows/`, git-ignored). OPERA holds only Sentinel-1A for these dates, so pairs are 12 days (one 24 days, T004 2021).
- Full bursts are 263 to 273 MB each, 4.5 GB total, in `data/_source/s1_cslc/` (git-ignored, logged in `data/_source/_download_ledger.csv`).

## Method

- Interferogram of consecutive dates on one burst (12 days). Coherence and multilooked phase on the native grid with a 2 x 4 pixel boxcar (20 m x 20 m, 8 looks).
- Resampled (nearest) onto the area's 5 m NISAR SLC grid. Pit, ring and decoy pixel sets are then identical to the NISAR run.
- Coherence excess = (pit - ring) - median(decoy - ring). Phase as LOS mm, lambda 5.547 cm.
- Pixels outside a burst are dropped from each sum. The first run let them in as zero, and track 4 phases read exactly 0 mm. Fixed before the results below.

## Results, October to November 2025

| Area | Pits | Pairs | Tile coherence | Coherence excess, pooled | LOS excess, pooled | Decoy LOS scatter |
|---|---|---|---|---|---|---|
| 9t | 506 (T077), 58-60 (T004) | 8 | 0.42 to 0.47 | +0.004 [-0.004, +0.016], p 0.19 | -0.43 mm [-0.73, +0.08] | 4.9 to 5.8 mm |
| 613590 | 36 | 4 | 0.42 | +0.011 [-0.006, +0.037], p 0.08 | +0.55 mm [-0.70, +2.35] | 4.9 to 6.0 mm |

- No pair on 9t has an interval that excludes zero.
- On 613590 one of four pairs (11-17 to 11-29) gives p 0.02 with an interval that still spans zero. That is not significant after four tests.
- Tile coherence of about 0.42 at 8 looks sits near the estimator's floor for fully decorrelated ground (about 0.3). Forest loses most C-band coherence in 12 days, even in autumn.

## Results, early to mid April

| Window | Area | Pairs | Tile coherence | Coherence excess | LOS excess | Decoy LOS scatter |
|---|---|---|---|---|---|---|
| Apr 2025 | 9t | 2 (T077 506 pits, T004 45) | 0.43, 0.46 | +0.006 [-0.014, +0.020] | -1.27 mm [-1.93, -0.15] | 4.5 to 5.0 mm |
| Apr 2025 | 613590 | 1 | 0.43 | +0.002 [-0.110, +0.042] | +2.86 mm [-2.14, +4.57] | 4.7 mm |
| Apr 2026 | 9t | 1 | 0.42 | -0.010 [-0.030, +0.007] | -0.56 mm [-1.20, +0.56] | 5.2 mm |
| Apr 2026 | 613590 | 1 | 0.43 | -0.070 [-0.108, +0.030] | +1.94 mm [-3.66, +4.75] | 5.3 mm |

- April coherence is no higher than autumn. Bare branches still decorrelate C-band in 12 days.
- One result excludes zero. 9t, T077, 2025-04-03 to 04-15, pits -1.18 mm median, Wilcoxon p 0.003 over 506 pits. Open pits (cover < 0.3) -1.50 mm, closed (> 0.7) -0.78 mm.
- It does not repeat. The same burst and season in 2026 gives -0.56 mm, p 0.60. 613590 in the same pair goes the other way (+2.86 mm, 36 pits).
- About 17 pair tests were run on 9t and 613590 across both seasons. A Bonferroni threshold for 17 is 0.003, so this one sits at the line.
- A 1 mm difference at C-band is about 0.2 rad. Soil moisture change between dates shifts C-band phase by that much, and pits hold water. A spring moisture effect is a more likely cause than ground motion.

## Results, every early-to-mid April 2017 to 2026 (`--window aprall`)

- 9t 21 pairs (T077 12, T004 9). 613590 12 pairs (T077).
- Phase. 9t T077 per-year medians run -0.52 to +1.03 mm, 2025 aside. Pooled -0.06 mm [-0.31, +0.12]. 613590 pooled -0.59 mm [-1.22, +0.45]. The April 2025 -1.18 mm is the most negative of 12 years and does not recur. Treat it as chance or a one-season moisture effect.
- Coherence, 613590. +0.0004 [-0.022, +0.018], p 0.77. Nothing.
- Coherence, 9t. +0.011 [+0.006, +0.014], pooled over years, p < 0.001. Split by canopy over the pit:

| Pit canopy | Pits | Coherence excess | Pit minus own ring |
|---|---|---|---|
| Open (< 0.3) | 97 | +0.018, p 0.0003 | +0.015 |
| Mid | 249 | +0.008, p 0.04 | +0.003 |
| Closed (> 0.7) | 160 | +0.011, p 0.02 | -0.000 |

- Under closed canopy the pit equals its own ring. The excess there comes only from decoys reading about 0.01 below their rings, which is a property of the decoy construction, not of pits.
- In the open the pit is 0.015 above its ring. Open bare ground holds C-band coherence better than the forest around it. That is a canopy contrast. Decoys are matched on shape, not on cover.
- So the 9t excess is design plus openness, not a pit signal. 613590 does not show it.

## Interpretation

- C-band agrees with L-band. Pits show no coherence difference from decoys in either season. Phase shows one 1 mm spring difference on 9t (April 2025) that did not recur in any of the other 11 Aprils. Pooled over 12 Aprils, the 9t coherence excess (+0.011) traces to decoy construction and open ground, and 613590 shows none.
- C-band coherence over forest is lower than NISAR L-band on the same autumn (NISAR track 162 0.53 to 0.65). The shorter wave is scattered by the remaining canopy.
- The persistent-scatterer screen was not run. Five dates are too few (pure speckle passes D_A < 0.25 in 6.6% of pixels at 5 dates).

## Outputs

For each `<window>` in `octnov2025`, `apr2025`, `apr2026`, `aprall` (the autumn files were renamed to carry the window on 2026-11-13):
- `data/9t/results/s1/s1_ifg_pits_by_pair_<window>_9t.csv`, `s1_ifg_pits_per_pit_<window>_9t.csv`, `s1_ifg_pits_summary_<window>_9t.json`
- `data/613590/results/s1/s1_ifg_pits_by_pair_<window>_613590.csv`, `s1_ifg_pits_per_pit_<window>_613590.csv`, `s1_ifg_pits_summary_<window>_613590.json`

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_s1_cslc_fetch_9t.py octnov2025 apr2025 apr2026
python notebooks/wellsight_v2/s5_eval/_s1_cslc_window_fetch_9t.py 2017 2018 2019 2020 2021 2022 2023 2024
python notebooks/wellsight_v2/s5_eval/_s1_ifg_pits_9t.py --slc --window <window>
python notebooks/wellsight_v2/s5_eval/_s1_ifg_pits_9t.py --slc --area 613590 --window <window>
```

## Source

OPERA CSLC-S1 V1 product, NASA JPL OPERA project, distributed by ASF DAAC. https://www.earthdata.nasa.gov/data/catalog/asf-opera-l2-cslc-s1-v1-1
