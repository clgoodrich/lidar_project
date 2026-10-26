# NISAR pad-feature products and scoring (9t)

## Goal
Test whether any NISAR-derived parameter separates annotated well pads from ground that is not a pad. Plan: `docs/iterations/nisar_feature_products_plan.md`.

## Inputs
- NISAR L2 GSLC windows, 5 m, tracks 26 / 90 / 162 (10 / 11 / 15 usable dates), HH and HV.
- 649 annotated pad polygons (626 have matched decoys). Lidar slope, roughness and canopy cover on the 5 m grid.

## Products (303 bands, scripts in `notebooks/wellsight_v2/s5_eval/`)
| Product | Script | Bands |
|---|---|---|
| Dual-pol (RVI, RFDI, entropy, alpha, DoP, rho, phi) | `_nisar_feat_dualpol_9t.py` | 21 |
| Texture and edge (cv, sd dB, entropy, ratio of averages) | `_nisar_feat_texture_9t.py` | 15 |
| Spatial (multi-scale sd, skew, kurtosis, gradient, DoG, anisotropy, GLCM) | `_nisar_feat_spatial_9t.py` | 63 |
| Amplitude trend and season (median, p10, p90, leaf-on/off, trend) | `_nisar_feat_amp_trend_9t.py` | 42 |
| Temporal (dispersion, IQR, HV/HH ratio, correlation, cross-track) | `_nisar_feat_temporal_9t.py` | 43 |
| Events (bright and dark outliers) | `_nisar_feat_events_9t.py` | 15 |
| Geometry (terrain-flattened brightness, simulated facet area) | `_nisar_feat_geometry_9t.py` | 14 |
| Line-of-sight motion | `_nisar_feat_los_motion_9t.py` | 12 |
| Coherence decay, short/long, season, closure phase | `_nisar_feat_coherence_9t.py` | 43 |
| Flatness gate and amp stats | `_nisar_features_vs_flatness_9t.py` | 32 |

Outputs: `data/9t/derived/nisar_features_5m/nisar_feat_<product>_9t_5m.tif` (git-ignored).

## Protocol
- Positive: median over the 49 core pixels nearest the pad centre (core = pad shrunk 5 m, or 15 m).
- Negative: 4-pixel-radius discs, 10 per pad, at least 100 m from any pad, pit, road or DEP well, with disc mean cover within 0.05 and mean slope within 1 degree of the pad.
- Scorer `_nisar_feat_score_9t.py`: AUC with bootstrap CI, Mann-Whitney p, Benjamini-Hochberg q, split by pad canopy class. Model `_nisar_feat_model_9t.py`: gradient boosting, 5-fold CV grouped by 500 m block, bands more than 20% missing in either class dropped, median imputation.

## Checks that changed the result
1. Coarse bins leaked: lidar cover scored AUC 0.24 against "matched" decoys. Fixed with continuous matching (controls now 0.49 cover, 0.47 roughness, 0.45 slope).
2. Missingness leaked in the model (losmotion: 81% NaN for pads against 32% for decoys). Pooled AUC fell 0.91 to 0.80 after dropping and imputing.
3. Pad cores were medians over many more pixels than decoys. Both now use 49 pixels.
4. Placebo (decoy against decoy): AUC 0.50.

## Results
- Single bands, core 5 m: 199 of 300 NISAR bands pass q < 0.05. Best AUCs 0.66 to 0.68: spatial contrast (gradient, centre-minus-surround, local sd).
- Core 15 m (139 large pads): texture falls (0.66 to 0.58), so much of it was the pad edge. Short-gap HH coherence on track 162 gets stronger (AUC 0.24, pads less coherent), as does centre-minus-surround brightness (0.25, pads darker).
- Model, core 5 m: all NISAR 0.81 (CI 0.76-0.86), SAR only without geometry 0.79, lidar baseline 0.57. Gate (+0.05) passed.
- Model, core 15 m: all NISAR 0.96, baseline 0.51, placebo 0.54.
- Product groups alone, core 5 m: spatial 0.78, geometry 0.77, amp_stats 0.68, texture 0.68, temporal 0.66, dual-pol 0.51 (no signal).
- Results: `data/9t/results/nisar/nisar_pad_feature_auc_per_band_9t.csv`, `..._9t_core15m.csv`, `nisar_pad_model_auc_by_set_9t.csv`, `..._9t_core15m.csv`, summary JSONs beside them.

## Limits
- Decoys sit at least 100 m from roads, pads always sit beside one. The model may learn a road-adjacent signature. Decoys 30-100 m from a road would test it.
- Pad size is not matched. The 15 m core keeps only large pads.
- Registration of about 10 m, unlabelled pads inside the decoy set, one area.
- The AUC 0.96 at core 15 m is not trusted until the road-adjacent control is run.

## Not built
Rain and freeze response (needs PRISM or NLDAS rain), road dead-end context, height residual and volume coherence, sub-aperture metal signature. `_nisar_events_vs_spud_9t.py` (spud-date truth) not written.

## Reproduce
```
python notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py
for p in dualpol texture spatial amp_trend temporal events geometry los_motion coherence; do python notebooks/wellsight_v2/s5_eval/_nisar_feat_${p}_9t.py; done
python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
CORE_SHRINK_M=15 python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py
CORE_SHRINK_M=15 python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
```
