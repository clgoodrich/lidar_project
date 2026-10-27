# NISAR pad-feature products and scoring (9t)

## Goal
Test whether any NISAR-derived parameter separates annotated well pads from ground that is not a pad. Plan: `docs/iterations/nisar_feature_products_plan.md`. Pits are in `docs/iterations/nisar_pit_features_scored_9t.md`.

## Inputs
- NISAR L2 GSLC windows, 5 m, tracks 26 / 90 / 162 (10 / 11 / 15 usable dates), HH and HV. RSLC windows (34 dates) for the sub-aperture and height products.
- 649 usable pad polygons (626 with matched decoys). Lidar slope, roughness and canopy cover on the 5 m grid.
- PRISM daily rain and temperature at the 9t centre, 2025-09-01 to 2026-10-18 (`data/9t/derived/weather/weather_prism_daily_9t.csv`, script `_weather_prism_daily_9t.py`).

## Products (351 bands scored, including 3 lidar controls and 2 road-context bands; the model keeps 337 NISAR bands after the missingness filter; scripts in `notebooks/wellsight_v2/s5_eval/`)
| Product | Script | Bands |
|---|---|---|
| Dual-pol (RVI, RFDI, entropy, alpha, DoP, rho, phi) | `_nisar_feat_dualpol_9t.py` | 21 |
| Texture and edge | `_nisar_feat_texture_9t.py` | 15 |
| Spatial (multi-scale sd, skew, kurtosis, gradient, DoG, anisotropy, GLCM) | `_nisar_feat_spatial_9t.py` | 63 |
| Amplitude trend and season | `_nisar_feat_amp_trend_9t.py` | 42 |
| Temporal (dispersion, IQR, HV/HH ratio, correlation, cross-track) | `_nisar_feat_temporal_9t.py` | 43 |
| Events (bright and dark outliers) | `_nisar_feat_events_9t.py` | 15 |
| Geometry (terrain-flattened brightness, simulated facet area) | `_nisar_feat_geometry_9t.py` | 14 |
| Line-of-sight motion | `_nisar_feat_los_motion_9t.py` | 12 |
| Coherence decay, short/long, season, closure phase | `_nisar_feat_coherence_9t.py` | 43 |
| Sub-aperture (3 azimuth looks, 2 range bands, HH) | `_nisar_feat_subaperture_9t.py` | 15 |
| Height above lidar ground and baseline decorrelation | `_nisar_feat_height_resid_9t.py` | 9 |
| Rain and freeze response (API slope, wet-dry, frozen) | `_nisar_feat_rain_freeze_9t.py` | 22 |
| Road context (annotated roads, circular, not NISAR) | `_nisar_feat_road_context_9t.py` | 2 |

Outputs: `data/9t/derived/nisar_features_5m/nisar_feat_<product>_9t_5m.tif` (git-ignored).

## Protocol
- Positive: median over the 49 core pixels nearest the pad centre (core = pad shrunk 5 m, or 15 m).
- Negative: 4-pixel-radius discs, 10 per pad, at least 100 m from any pad, pit, road or DEP well, with disc mean cover within 0.05 and mean slope within 1 degree of the pad. Road-near mode (`ROAD_NEAR=1`): decoys 30-100 m from a road instead.
- Scorer `_nisar_feat_score_9t.py`: AUC, bootstrap CI, Mann-Whitney p, Benjamini-Hochberg q, split by canopy class. Model `_nisar_feat_model_9t.py`: gradient boosting, 5-fold CV grouped by 500 m block, bands more than 20% missing in either class dropped, median imputation, placebo (decoy against decoy).

## Checks that changed the result
1. Coarse bins leaked: lidar cover scored AUC 0.24 against "matched" decoys. Continuous matching brought the controls to 0.49 (cover), 0.47 (roughness), 0.45 (slope).
2. Missingness leaked in the model (losmotion: 81% NaN for pads, 32% for decoys). Pooled AUC fell 0.91 to 0.80.
3. Pad cores were medians over more pixels than decoys. Both now use 49 pixels.
4. Placebo AUC 0.48-0.50 in every run.
5. Road proximity: pads sit a median 7 m from a road, the old decoys at least 100 m. Decoys re-drawn 30-100 m from a road did not lower the score.

## Results (model AUC, 5-fold block CV)
| Run | all NISAR | SAR only (no geometry) | lidar baseline | placebo |
|---|---|---|---|---|
| Core 5 m, 626 pads, decoys far from roads | 0.815 | 0.801 | 0.574 | 0.496 |
| Core 5 m, decoys 30-100 m from a road | 0.884 | 0.880 | 0.590 | 0.484 |
| Core 15 m, 139 large pads | 0.959 | 0.960 | 0.513 | 0.500 |
| Core 15 m, decoys near roads | 0.960 | 0.964 | 0.618 | 0.483 |
- Road context alone scores 0.97-0.996: circular (roads were drawn to reach pads), never counted as NISAR.
- Product groups alone, core 5 m (far decoys / near-road decoys): spatial 0.78 / 0.82, geometry 0.77 / 0.77, sub-aperture 0.72 / 0.62, temporal 0.66 / 0.71, amp_stats 0.68 / 0.75, rain-freeze 0.62 / 0.67, height 0.62 / 0.69, coherence 0.60 / 0.73, dual-pol 0.51 / 0.58 (no signal).
- Single bands: 227 of 351 pass q < 0.05 at core 5 m. Core 15 m: texture falls (edge effect), short-gap HH coherence on track 162 (AUC 0.24, pads less coherent) and centre-minus-surround brightness (AUC 0.25, pads darker) get stronger.
- Result files: `data/9t/results/nisar/nisar_pad_feature_auc_per_band_9t[_core15m][_roadnear].csv`, `nisar_pad_model_auc_by_set_9t[_core15m][_roadnear].csv`, summary JSONs beside them.

## Ablation (2026-10-26, `_nisar_feat_ablate_9t.py`)
| Set | core 5 m far | core 5 m near-road | core 15 m |
|---|---|---|---|
| all NISAR | 0.815 | 0.884 | 0.959 |
| without spatial | 0.779 | 0.857 | 0.957 |
| without geometry | 0.801 | 0.880 | 0.960 |
| without coherence | 0.824 | 0.883 | 0.960 |
| without dual-pol | 0.825 | 0.889 | 0.963 |
| HH bands only | 0.795 | 0.840 | 0.959 |
| HV bands only | 0.742 | 0.829 | 0.926 |
| ascending tracks only | 0.828 | 0.864 | 0.963 |
| descending track only | 0.667 | 0.793 | 0.915 |

- Spatial structure is the only group whose removal clearly hurts. Groups overlap, so no group is individually necessary beyond that. HH carries more than HV. Ascending tracks carry more than the descending one.
- Pad-area terciles (core 5 m, far decoys): 0.854 / 0.806 / 0.785, smallest to largest. The signal is not confined to large pads.
- Files: `data/9t/results/nisar/nisar_pad_ablation_auc_9t[_roadnear][_core15m].csv`.

## Location control, HH/HV twins, fusion (2026-10-26)
- Shuffled-label null (labels shuffled within 500 m blocks): 0.775 pads (road-near), 0.800 pits. The early 0.82-0.88 pad scores were mostly location.
- Local decoys (`LOCAL_M=750` / `1500`, 100 m to LOCAL_M from the pad): 87 / 274 pads usable, NISAR 0.695 / 0.713, placebo 0.466 / 0.490, baseline 0.504 at 1500 m.
- HH/HV twins (89 pairs, `_nisar_feat_hhhv_9t.py`): pads road-near HH 0.847, HV 0.828, both 0.877, p 0.52. Pits HH 0.836, HV 0.788, both 0.856, p 0.002.
- Fusion (`_nisar_feat_fusion_9t.py`): U-Net out-of-fold about 1.00, NISAR 0.749, NISAR + U-Net 0.999 on 626 pads. NISAR adds nothing on pad against ordinary ground.
- Full description for outside readers: `NISAR_METHODS.md` in the repo root.

## Limits
- Pad size is not matched. The 15 m core keeps only large pads, which may differ from small ones in kind.
- Registration about 10 m, unlabelled pads inside the decoy set, one area, single date window.
- Freeze response rests on 1-2 frozen dates per track. Height residual is local only (the 500 m long-wave removal also removes the mean canopy offset: forest median under 1 m).
- PRISM is one 4 km cell for the whole tile, so rain timing is shared by every pixel. Recent PRISM days are provisional.

## Not built / not possible
- Spud-date truth for events: the DEP export's latest spud date is 2018-10-08, none fall in the NISAR window.
- Warren: no pad annotations, and the lidar radar simulation is missing for geometry.

## Reproduce
```
python notebooks/wellsight_v2/s5_eval/_weather_prism_daily_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py
for p in dualpol texture spatial amp_trend temporal events geometry los_motion coherence subaperture rain_freeze road_context; do python notebooks/wellsight_v2/s5_eval/_nisar_feat_${p}_9t.py; done
NISAR_STACK=slc python notebooks/wellsight_v2/s5_eval/_nisar_feat_height_resid_9t.py   # then rename the file to nisar_feat_heightresid_9t_5m.tif if it carries _slc
python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py && python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
CORE_SHRINK_M=15 ROAD_NEAR=1 python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py   # and the model with the same variables
```
