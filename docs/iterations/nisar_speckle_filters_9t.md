# NISAR speckle filters on tile 9t (2026-11-08)

## Goal

The NISAR images were single-look. Speckle was reduced only by averaging dates. Leaf-off fall has one date per track on 9t, so that season had no averaging at all. This pass tries four standard speckle filters. It asks whether the seasonal pad and pit test changes when each date is filtered first.

## Inputs

- Lidar-placed SLC stack `data/9t/derived/nisar_slc_lidar_5m/` (complex HH and HV, 5 m, 34 dates, 1 dropped).
- Pads and pits from `annotations_proj.gpkg`, the same as the seasonal test.

## Filters

All filters work on linear intensity |s|², with 1 look and a 5 × 5 window (25 m).

| Filter | Source | Settings |
|---|---|---|
| Median | standard | 5 × 5 |
| Frost | Frost et al. 1982 | weights exp(−K·Ci²·r), K = 1 |
| Gamma-MAP | Lopes et al. 1990 | Cu = 1, Cmax = √2 |
| Lee sigma (improved) | Lee et al. 2009 | 3 × 3 MMSE first estimate. 90% sigma range with an unbiased truncated mean for 1 look. Point targets with 5 or more of 9 pixels above the 98th percentile are kept |

No-sample pixels are filled with the local mean for filtering, then set back to no-sample.

## Scripts

- `notebooks/wellsight_v2/s5_eval/_nisar_speckle_filter_maps_9t.py` writes QGIS images to `data/9t/derived/nisar_speckle_filters/nisar_speckle_<filter>_<date>_t090A_9t.tif`. Band 1 is HH dB and band 2 is HV dB. Dates are 2025-11-04 (leaf-off) and 2026-07-14 (leaf-on).
- `notebooks/wellsight_v2/s5_eval/_nisar_speckle_filter_seasonal_9t.py` reruns `_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc --decoys 40` with each date filtered first. It uses the same seed, so the decoys are the same. Outputs go to `data/9t/results/nisar/speckle_filters/<filter>_w5/`.

## Results

The filters worked. On the first date, the local ENL of HH rose from 0.98 to between 9.6 and 14.8. On the 2025-11-04 image, the HH spread fell from 5.95 dB to between 2.2 and 2.5 dB. The median filter lowers the mean to 0.69 of the original (about −1.6 dB), because the median of speckle sits below its mean.

The unfiltered run matches the October swap40 baseline exactly (largest difference 0.0).

Pits, median excess over decoys in dB, with the swap-test p in brackets:

| Metric | None | Median | Frost | Gamma | Sigma |
|---|---|---|---|---|---|
| HH leaf-off fall | +0.246 (0.0002) | +0.102 (0.008) | +0.199 (0.0002) | +0.141 (0.0002) | +0.214 (0.0002) |
| HV leaf-on | +0.194 (0.0002) | +0.074 (0.003) | +0.143 (0.0002) | +0.105 (0.0002) | +0.147 (0.0002) |
| HH change, leaf-on minus fall | −0.103 (0.13) | −0.067 (0.08) | −0.137 (0.002) | −0.116 (0.001) | −0.134 (0.0004) |

Pit AUC against decoys stays between 0.54 and 0.58. The best is HH leaf-off with Frost at 0.580, against 0.564 unfiltered.

Pads. With median, Gamma and sigma, pads read 0.05 to 0.19 dB darker than decoys in leaf-on and winter. The AUC is 0.41 to 0.48. Frost and the unfiltered run show almost nothing.

## Interpretation

- Filtering did not make a usable pit signal. The effects got smaller, because a 25 m window mixes a pit of about 8 pixels with its ring. The AUC moved by at most 0.016.
- Some p-values fell, for example the HH seasonal change in pits. This pass makes 16 metrics × 4 filters of comparisons, with no correction. Treat new low p-values as leads only.
- The pad darkening with median, Gamma and sigma may come from texture. Those filters smooth forest and clearings by different amounts. The earlier pad signal did not survive a location check.
- A smaller window (3 × 3) would mix less of the ring into the pit. It is not run.

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_nisar_speckle_filter_maps_9t.py 20251104_t090A 20260714_t090A
for f in none median frost gamma sigma; do
  python -u notebooks/wellsight_v2/s5_eval/_nisar_speckle_filter_seasonal_9t.py --filter $f --win 5
done
```

Each seasonal run takes about an hour on one core.
