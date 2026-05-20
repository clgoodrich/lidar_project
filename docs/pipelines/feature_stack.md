# Feature Stack Pipelines

How the per-pixel input rasters that feed every neural network get built.

## Concept

Every neural network in this project (pit U-Net, plat U-Net, road U-Net, road classifier) reads a stack of per-pixel feature channels. The features are LiDAR-derived terrain descriptors at 0.5 m resolution on the 9t tile (9000 × 9000 px, EPSG:6346, bounds 619500–624000 E × 4593000–4597500 N).

Two stacks exist:

- **7-channel stack** (baseline, iter 01, iter 02): `data/derivatives/9t/features_pit_9t_05.tif`
- **11-channel stack** (iter 03): `data/derivatives/9t/iterations/03_multiscale_feats/features_pit_v2_9t_05.tif`

Both are float32 BIGTIFFs, deflate-compressed with predictor 3, tiled 512×512, NaN nodata. Each band has a `set_band_description()` name in TIF metadata.

## Source rasters (already on disk)

Every channel either is or is derived from a raster under `data/derivatives/9t/`:

| Raster | What it is | How produced |
|---|---|---|
| `dem_9t_05.tif` | Ground-classified DTM (mean elevation) | PDAL `writers.gdal` from class-2 returns |
| `dsm_9t_05.tif` | Surface DSM (first-return) | PDAL `writers.gdal` first-return |
| `slope_9t_05.tif` | Slope (degrees) | `gdaldem slope` on DTM |
| `tpi_05_9t_05.tif` | TPI radius 5 px | local Whitebox / SAGA |
| `lrm_5_9t_05.tif`, `lrm_11`, `lrm_25`, `lrm_51` | Local Relief Models at four scales | DTM minus its Gaussian-smoothed version, σ in pixels |
| `openness_pos_9t_05.tif`, `openness_neg_9t_05.tif` | Positive/negative openness (Yokoyama 2002) | Whitebox `OpennessAboveBelow` |
| `roughness_11_9t_05.tif` | DEM roughness over 11-px window | Standard deviation in local window |
| `hillshade_9t_05.tif`, `hillshade_9t_05_az135.tif` | Visualization layers | `gdaldem hillshade` |

These were all produced upstream of this iteration cycle. They're not regenerated per iteration.

## Build script — 7-channel stack

**Script:** `notebooks/wellsight/pits/_stack_features.py`
**Output:** `data/derivatives/9t/features_pit_9t_05.tif`, `data/derivatives/9t/feature_stats.json`

Channels in order (this order is also their band index in the TIF + the channel order used at train and inference time):

1. `lrm_25` — coarse-scale residual; pit floors show as negative
2. `lrm_5` — fine-scale residual; pit rims show as sharp positive/negative bands
3. `slope` — degrees, captures pit walls
4. `tpi_05` — fine TPI; concavity at pit-floor scale
5. `openness_pos` — high on ridges/rims
6. `openness_neg` — high in concavities
7. `roughness_11` — texture descriptor; pits often quieter than surrounding ground

For each channel:
- Read the source TIF.
- Convert nodata sentinel to `NaN`.
- Compute mean and std **over TRAIN-block pixels only** (using `pit_blocks_9t.gpkg`). Test pixels do not enter the stats.
- Write band to the stacked TIF.
- Save the stats to `feature_stats.json`.

Per-channel z-score normalization happens at *runtime* in the trainer / inferer, not in the stacked TIF. This keeps the on-disk TIF compatible with QGIS overlays.

## Build script — 11-channel stack (iter 03)

**Script:** `notebooks/wellsight/pits/iter_03_multiscale_feats/build_features.py`
**Output:** `data/derivatives/9t/iterations/03_multiscale_feats/features_pit_v2_9t_05.tif`, `feature_stats_v2.json`

Same logic as the 7-channel build, plus four additional channels:

8. `lrm_11` — already on disk, added to the stack.
9. `lrm_51` — already on disk, added to the stack.
10. `curvature` — Laplacian of (Gaussian-smoothed σ=1.0) DTM. Negative = concave (pit-like), positive = convex (rim/ridge). Computed inside `build_features.compute_curvature()`. Stored as an intermediate at `data/derivatives/9t/iterations/03_multiscale_feats/curvature_9t_05.tif`.
11. `geomorphons` — WhiteboxTools `geomorphons(dem, search=50, fdist=0, forms=True)`. uint8 raster with classes 1..10. Class 10 ("pit") and 9 ("valley") are directly relevant. Stored at `geomorphons_9t_05.tif`.

The two intermediate rasters (`curvature_9t_05.tif`, `geomorphons_9t_05.tif`) are kept on disk for QGIS overlay and for re-running the stack build without recomputing.

## Per-channel statistics (TRAIN blocks only)

From `feature_stats.json` (7-channel) and `feature_stats_v2.json` (11-channel), means and stds used for runtime z-score normalization:

| Band | Name | Mean | Std | p2 | p98 |
|---|---|---:|---:|---:|---:|
| 1 | lrm_25 | −0.001 | 0.183 | −0.46 | 0.43 |
| 2 | lrm_5 | 0.000 | 0.034 | −0.07 | 0.09 |
| 3 | slope | 10.350 | 7.544 | 1.10 | 31.21 |
| 4 | tpi_05 | 0.000 | 0.134 | −0.32 | 0.33 |
| 5 | openness_pos | 86.820 | 2.749 | 78.38 | 89.75 |
| 6 | openness_neg | 86.986 | 2.616 | 79.32 | 89.86 |
| 7 | roughness_11 | 0.278 | 0.213 | 0.00 | 0.85 |
| 8 | lrm_11 | 0.000 | 0.085 | −0.19 | 0.21 |
| 9 | lrm_51 | −0.004 | 0.327 | −0.85 | 0.67 |
| 10 | curvature | 0.000 | 0.027 | −0.07 | 0.06 |
| 11 | geomorphons | 6.061 | 1.038 | 3.00 | 9.00 |

LRMs are correctly centered at zero (they're residuals from a smoothed surface). Slope mean ~10° matches a heavily-incised Appalachian Plateau tile. Openness values in the high 80s are normal for the geometric definition.

## How to add a new channel

1. Compute the per-pixel raster aligned to `dem_9t_05.tif` (same grid, same CRS). Save as a TIF under `data/derivatives/9t/` (or under the iteration's folder if it's only for one experiment).
2. Add it to the `CHANNELS` (or `EXISTING_CHANNELS` + new tuple) list in the build script. The list's order **is** the on-disk band order **is** the channel order in the trainer / inferer. Keep them in sync.
3. Rerun the build script. It will recompute `feature_stats.json` over the TRAIN blocks only.
4. Update the trainer's `CH_ORDER` (or `ch_order`) list to include the new channel name.
5. Bump `N_CH` if the trainer hard-codes the count (the SMP trainer does).
6. Train from scratch — pretrained encoders don't transfer cleanly across input-channel counts.

## Caveats

- **NaN handling.** Source rasters use a variety of nodata sentinels; the build script converts all to `NaN`. At training time NaN is replaced with 0 (post-normalization). This is reasonable for our tile because nodata regions are small / at the tile edges. Don't blindly trust it for tiles with large nodata holes.
- **The channel-order list is the source of truth in three places** (build script, trainer, inferer) and they must agree. Discrepancies cause silent feature swaps and unexplainable model regressions.
- **Train-block statistics are not a guarantee against leakage.** They're computed from the train spatial blocks, but the raster *itself* exists across the whole tile (you can't compute a Gaussian residual locally). For derivative features the leakage is bounded by the kernel size; for `geomorphons` with `search=50 px` it's bounded by 25 m. Acceptable for our regime.
