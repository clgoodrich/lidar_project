# Sentinel-1 C-band interferograms at pits, Oct-Nov 2025 (9t, 613590)

Run 2026-11-13. The NISAR L-band pit test repeated with Sentinel-1 C-band over the same autumn.

## Goal

Ask whether pits show a coherence or line-of-sight phase difference from matched decoys at C-band.
Use the same pits, rings, decoys and seed as the NISAR run (`_nisar_gslc_interferogram_pits_9t.py`).

## Data

- OPERA CSLC-S1 V1 (NASA JPL OPERA, distributed by ASF DAAC). Geocoded complex SLC bursts, VV only, 5 m x 10 m, UTM 17N, flattened.
- Search is NASA CMR by point, 2025-10-01 to 2025-11-30. Ten bursts, all Sentinel-1A. No Sentinel-1C bursts were returned.
- Two burst IDs. T077-163486-IW2 covers both areas. T004-006689-IW1 covers only the east edge of 9t (58 to 60 pits). Both are ascending.
- Five dates per burst at 12 days. T004: 10-07, 10-19, 10-31, 11-12, 11-24. T077: 10-12, 10-24, 11-05, 11-17, 11-29.
- Files are 263 MB each, 2.6 GB total, in `data/_source/s1_cslc/` (git-ignored, logged in `data/_source/_download_ledger.csv`).

## Method

- Interferogram of consecutive dates on one burst (12 days). Coherence and multilooked phase on the native grid with a 2 x 4 pixel boxcar (20 m x 20 m, 8 looks).
- Resampled (nearest) onto the area's 5 m NISAR SLC grid. Pit, ring and decoy pixel sets are then identical to the NISAR run.
- Coherence excess = (pit - ring) - median(decoy - ring). Phase as LOS mm, lambda 5.547 cm.
- Pixels outside a burst are dropped from each sum. The first run let them in as zero, and track 4 phases read exactly 0 mm. Fixed before the results below.

## Results

| Area | Pits | Pairs | Tile coherence | Coherence excess, pooled | LOS excess, pooled | Decoy LOS scatter |
|---|---|---|---|---|---|---|
| 9t | 506 (T077), 58-60 (T004) | 8 | 0.42 to 0.47 | +0.004 [-0.004, +0.016], p 0.19 | -0.43 mm [-0.73, +0.08] | 4.9 to 5.8 mm |
| 613590 | 36 | 4 | 0.42 | +0.011 [-0.006, +0.037], p 0.08 | +0.55 mm [-0.70, +2.35] | 4.9 to 6.0 mm |

- No pair on 9t has an interval that excludes zero.
- On 613590 one of four pairs (11-17 to 11-29) gives p 0.02 with an interval that still spans zero. That is not significant after four tests.
- Tile coherence of about 0.42 at 8 looks sits near the estimator's floor for fully decorrelated ground (about 0.3). Forest loses most C-band coherence in 12 days, even in autumn.

## Interpretation

- C-band agrees with L-band. Pits show no coherence or phase difference from decoys.
- C-band coherence over forest is lower than NISAR L-band on the same autumn (NISAR track 162 0.53 to 0.65). The shorter wave is scattered by the remaining canopy.
- The persistent-scatterer screen was not run. Five dates are too few (pure speckle passes D_A < 0.25 in 6.6% of pixels at 5 dates).

## Outputs

- `data/9t/results/s1/s1_ifg_pits_by_pair_9t.csv`, `s1_ifg_pits_per_pit_9t.csv`, `s1_ifg_pits_summary_9t.json`
- `data/613590/results/s1/s1_ifg_pits_by_pair_613590.csv`, `s1_ifg_pits_per_pit_613590.csv`, `s1_ifg_pits_summary_613590.json`

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_s1_cslc_fetch_9t.py
python notebooks/wellsight_v2/s5_eval/_s1_ifg_pits_9t.py --slc
python notebooks/wellsight_v2/s5_eval/_s1_ifg_pits_9t.py --slc --area 613590
```

## Source

OPERA CSLC-S1 V1 product, NASA JPL OPERA project, distributed by ASF DAAC. https://www.earthdata.nasa.gov/data/catalog/asf-opera-l2-cslc-s1-v1-1
