# PCA of the NISAR feature bands, 9t

> **Archive note (2026-11-15).** The prediction-scoring scripts and result files named below moved to `nisar/archive/prediction/`. That work is outside the present objective. See `nisar/archive/prediction/README.md`.

**Date:** 2026-11-15
**Status:** done
**Script:** `nisar/code/s5_eval/_nisar_feat_pca_9t.py`

## Goal

The scorer uses 337 NISAR bands. How many independent directions do they hold?
The user asked why there are 32 amplitude statistics and 351 bands in all, and then asked for a PCA.

## Inputs

- The lidar-placed stack on tile 9t. `nisar/derived/9t/nisar_features_5m/nisar_feat_<product>_9t_slc_5m.tif` for 12 products, and the first 32 bands of `nisar_feature_stack_9t_slc_5m.tif` (amplitude statistics).
- Road context and the three lidar controls are left out.

## Method

| Step | Detail |
|---|---|
| Sample | 60,000 random pixels, seed 20261115, same pixels for every band |
| Missing values | Drop bands over 20% missing (the scorer's rule), median-impute the rest |
| Scaling | Clip each band to its 1st to 99th percentile, then z-score |
| PCA | SVD of the standardised matrix |

346 bands built. 337 kept. 3 more dropped for zero variance, leaving 334.

## Results

| Measure | Value |
|---|---|
| Variance in PC1 | 6.9% |
| Variance in first 5 PCs | 22.2% |
| Variance in first 10 PCs | 31.8% |
| PCs for 50 / 80 / 90 / 95 / 99% | 26 / 87 / 127 / 158 / 212 |
| Participation ratio (effective dimension) | 56.5 |
| PCs for 90% within one track (026 / 090 / 162) | 44 / 42 / 44, from 111 / 103 / 112 bands |

- PC1 is overall brightness on all tracks, with the ascending-minus-descending difference loading highest.
- PC2 is local texture on tracks 90 and 162. The spatial group holds 45% of its weight.
- PC3 is brightness on track 26 alone (59% of its weight).
- Events, rain and freeze, height residual and sub-aperture carry under 3% of the weight in each of the first five PCs.

## Interpretation

The bands are partly redundant. About 100 to 130 independent directions remain, not the 337 the model sees.
An earlier note here guessed the effective number was "much smaller" than 351. That was too strong for the 90% measure.
The sample is tile-wide and forest dominates. PCA measures variance, not usefulness for finding pads.
It does not test whether fewer bands would change the NISAR-plus-lidar gain.

## Files

- `nisar/results/9t/nisar_feat_pca_scree_9t_slc.csv`
- `nisar/results/9t/nisar_feat_pca_loadings_9t_slc.csv` (first 10 PCs)
- `nisar/results/9t/nisar_feat_pca_group_share_9t_slc.csv`
- `nisar/results/9t/nisar_feat_pca_summary_9t_slc.json`
- `nisar/results/9t/figures/nisar_feat_pca_9t_slc.png` (blue and orange only, no red/green pair)

## Reproduce

`python nisar/code/s5_eval/_nisar_feat_pca_9t.py`

## Held-out sweep over the number of components (2026-11-15)

**Script:** `nisar/archive/prediction/code/_nisar_feat_pca_sweep_heldout_9t.py`
Exploratory. Run after the pre-registered 613590 test and not part of it.

Same frozen design as `nisar/archive/prediction/code/_nisar_feat_heldout_9t.py`. Train on the 9t pit samples (5,379 rows), score the 613590 pit samples (396 rows, 36 pits).
The NISAR bands are replaced by their first k components. The PCA is fitted on the 9t training rows only, then applied to 613590.
278 of the 293 shared bands survive the missing-value rule and zero-variance filter. The rich lidar baseline is 26 bands.
The run reproduces the saved result: all 293 bands plus rich lidar scores 0.865, gain -0.017 (-0.055 to +0.020).

| NISAR input | Alone | With rich lidar | Gain over rich lidar (95% block bootstrap) |
|---|---|---|---|
| Rich lidar only | | 0.881 | |
| All 293 bands | 0.658 | 0.865 | -0.017 (-0.055, +0.020) |
| PC1 | 0.496 | 0.876 | -0.005 (-0.017, +0.003) |
| first 2 | 0.572 | 0.865 | -0.016 (-0.036, -0.000) |
| first 5 | 0.630 | 0.874 | -0.007 (-0.022, +0.006) |
| first 10 | 0.600 | 0.874 | -0.008 (-0.025, +0.006) |
| first 30 | 0.593 | 0.872 | -0.010 (-0.026, +0.006) |
| first 60 | 0.597 | 0.865 | -0.017 (-0.037, +0.002) |
| first 127 | 0.578 | 0.858 | -0.023 (-0.048, -0.002) |

- No component count gives a gain. Every point estimate is negative and none reaches +0.05.
- The radar-alone score is highest at 5 components (0.630). The brightness axis, PC1, scores chance (0.496) on pits.
- The gain gets worse as components are added. With 127 the interval excludes zero on the negative side. That is what fitting noise looks like.
- Only 36 pits, eight component counts, and the counts were chosen after the fact. Read the pattern, not any one row.

Files: `nisar/archive/prediction/results/613590/nisar_pit_heldout_pca_sweep_613590_slc.csv` and `.json`.
Reproduce: `python nisar/archive/prediction/code/_nisar_feat_pca_sweep_heldout_9t.py --slc`
