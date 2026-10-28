# NISAR work in this repository: data, methods, results and limits

Written 2026-10-26, revised the same day after two outside reviews (Section 14). This file is for an outside reader who wants to judge the method. It says what data we hold, what each test does, where every script and output lives, what the results are, and where the weak points are. Numbers come from the files named beside them. Nothing here has been peer reviewed.

## 1. The question and the short answer

**Question.** Does NISAR L-band radar carry a signal that identifies oil and gas well pads, pits, wells and pumpjacks in western Pennsylvania? And can it help the lidar detector we already have?

**Short answer, as of 2026-10-27 (after correction and the follow-up checks, Section 15).**
- **On this tile, NISAR does not add to lidar or to location for detecting pads or pits.** After fixing the pipeline, NISAR scores 0.640 for pads against decoys drawn anywhere, and 0.479 (chance) against decoys from the pad's own neighbourhood. A classifier that sees only map coordinates scores 0.815 in the first design. A rich lidar texture baseline scores 0.92. Adding NISAR to it changes nothing.
- The first-pass scores of 0.71 to 0.88 were wrong. They came from location, optimistic cross-validation and mismatched sample sizes (Sections 9 and 14).
- NISAR does not identify wells, pumpjacks or steel. Every direct test of that was null.
- NISAR did not help screen false positives from the lidar pit detector (gain -0.026, p 0.58), nor from the pad detector (Section 15: NISAR alone separates true from false candidates at 0.72, but score + NISAR scores below the score alone).
- The fusion with the lidar U-Net was redone with an isolated retrain. NISAR adds nothing (0.995 against 0.999).
- A frozen model trained on 9t pits and tested on 36 pits of tile 613590 gave the same answer (NISAR alone 0.658, no gain over lidar).
- This does not show NISAR can never help. It shows that here, with a 4.9 km tile, 5 m posting and these features, it does not.

AUC here is P(target value > comparison value). 0.5 is no separation. Below 0.5 means the target is lower.

## 2. Study areas and ground truth

| Area tag | Place | Role |
|---|---|---|
| `9t` | Venango County, PA. A 4.5 km square (EPSG:6346 bounds 619500, 4593000 to 624000, 4597500). | Every scored result. |
| `613590`, `mkf` | Two other lidar areas. | Data-extension plan only (`docs/iterations/nisar_area_extension_613590_mkf.md`). No scored result. |
| `warren` | Warren County swath, 7 USGS lidar tiles. | Bright-target test against DEP wells only. No pad annotations, so no pad scoring. |

**Ground truth on 9t** (`qgis/annotations/annotations_proj.gpkg`):
- `plat` layer: 995 hand-drawn well-pad polygons. 649 fall usable inside the NISAR window.
- `pit_outside` layer: 723 pit-rim polygons (median 197 m², about 8 NISAR pixels). 495 usable.
- `roads` layer: annotated roads, used to keep decoys away from roads.
- Pennsylvania DEP well export, April 2026 (`data/_source/reference/dep_wells/venango_wells_all.gpkg`). DEP positions are unreliable by tens of metres. The annotations came from lidar, not from DEP.
- Annotations are incomplete. Some real pads are unannotated and can sit in the decoy set.

**Lidar** is the 2019 Pennsylvania QL2 survey (about 4.8 points per m²). It supplies canopy cover, slope, roughness and the bare-earth surface used to place radar pixels.

## 3. The NISAR data

**Product.** NISAR (NASA-ISRO SAR), L-band (24 cm wavelength, 1.257 GHz), left-looking. Files come from the ASF DAAC cloud. Collections are `NISAR_L2_GSLC_BETA_V1` and the provisional equivalent, and `NISAR_L1_RSLC_BETA_V1` and `..._PROVISIONAL_V1`. **Neither is validated or fully calibrated.** Beta and provisional processing differ in calibration, which shows up as per-track brightness offsets (Section 7).

**Polarisations.** HH and HV only. There is no VV, so full quad-pol decomposition is not possible. The "dual-pol" features are the HH/HV ones.

**Tracks over 9t.**

| Track | Direction | GSLC windows indexed | Date range |
|---|---|---|---|
| 26 | descending | 11 | 2025-11-12 to 2026-10-14 |
| 90 | ascending | 11 | 2025-11-04 to 2026-10-06 |
| 162 | ascending | 15 | 2025-10-28 to 2026-10-11 |

The feature scripts use 10, 11 and 15 usable dates (flagged bad dates removed in `notebooks/wellsight_v2/_nisar_area.py`, `BAD_DATES`).

**What we hold locally.** We never downloaded whole granules (about 22.6 GB each). `_fetch_nisar_gslc_window_9t.py` reads only the HDF5 chunks that cover the study area through HTTPS range requests, about 40 MB per polarisation per date.

| Item | Content | Location | Size |
|---|---|---|---|
| GSLC windows | Complex HH and HV, 5 m, EPSG:32617, one GeoTIFF per date and track. Phase kept. | `data/9t/derived/nisar_gslc_5m/` (100 files, index `nisar_gslc_window_index_9t_5m.csv`) | 466 MB |
| RSLC windows | Single-look complex in radar geometry, HDF5, before map placement. | `data/9t/derived/nisar_rslc_window/` (35 files) | 1.5 GB |
| Lidar-placed SLC stack | The RSLC samples re-placed on the lidar ground (Section 4). 34 windows. | `data/9t/derived/nisar_slc_lidar_5m/` (index `nisar_slc_lidar_index_9t.csv`) | 601 MB |
| Earlier 10 m set and DEM | Used by the first GCOV pad-versus-forest test (not re-checked for this file). | `data/9t/derived/nisar_10m/`, `nisar_dem/` | |
| Feature rasters | One multi-band GeoTIFF per product (Section 6). | `data/9t/derived/nisar_features_5m/nisar_feat_<product>_9t_5m.tif` (22 files) | 1.2 GB |
| Weather | PRISM 4 km daily rain, tmin, tmax at the tile centre, 2025-09-01 to 2026-10-18. | `data/9t/derived/weather/weather_prism_daily_9t.csv` | small |
| Warren windows | 49 GSLC windows (track 26: 11, 90: 23, 162: 15), 2025-10-28 to 2026-10-18. | `data/warren/derived/nisar_gslc_5m/` | |

All heavy rasters are git-ignored. The large-file audit in `CLAUDE.md` was clean at the last commit.

## 4. Registration, the main source of doubt

NASA places each GSLC pixel with a 30 m global elevation model (Copernicus-based). Under forest that model sits partway up the canopy. A side-looking radar turns a height error into a sideways shift, so pixels land metres from the true ground position.

**What we did.** `notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py` (with `_nisar_geometry.py`) takes the RSLC samples and places them using the 1 m lidar bare earth. It uses the GSLC's own radar-grid cubes (`metadata/radarGrid`) to map a map position and height to a radar time and range. Plan and checks: `docs/iterations/nisar_regeocode_plan_9t.md`.

**What remains.** Registration is still about 10 m. Our 5 m pixels, the 5 to 40 m pads and the 1 to 3 pixel pits are all comparable to that. The best-shift search with wells found no clear peak (best 2.4% hit rate against 1.6% median over shifts), so registration was not independently confirmed. Every result should be read as "within a registration blur of about 10 m".

## 5. Experiments in order, and what each found

All iteration write-ups are in `docs/iterations/`. Results are in `data/9t/results/nisar/` (181 files) unless stated.

| # | Test | Script | Doc | Finding |
|---|---|---|---|---|
| 1 | Pad against forest backscatter, 10 m GCOV | `_nisar_gcov_pad_vs_forest_backscatter_9t.py` | `nisar_gcov_pad_vs_forest_backscatter_9t.md` | Pads slightly darker. Caveat added 2026-09-30: a few pad pixels were compared with hundreds of ring pixels, and brightness is right-skewed, so part of the difference was a sample-size artefact. |
| 2 | Seasonal 5 m stack, pads and pits against decoys | `_nisar_gslc_stack_pad_pit_seasonal_9t.py` | `nisar_gslc_stack_pad_pit_seasonal_9t.md` | Pads 0.2 to 0.4 dB darker than same-shaped decoys (AUC up to 0.71). Pits show a signal only after shifting onto the lidar. No leaf-on versus leaf-off effect. |
| 3 | Interferometry at pits | `_nisar_gslc_interferogram_pits_9t.py` | `nisar_gslc_interferogram_pits_9t.md` | Null. Phase noise about 7.5 mm per pit per pair, so any pit motion would have to exceed about 15 mm in 12 days. |
| 4 | Steel at wells (steady bright targets), pad coherence change, slope motion | `_nisar_steel_9t.py`, `_nisar_steel_snapped_9t.py`, `_nisar_pad_change_9t.py`, `_nisar_slope_motion_9t.py` | `nisar_wells_steel_pads_slopes_9t.md`, `nisar_steel_snapped.md` | Wells are not on steady bright targets more than chance. Small excess is setting (roads, clearings), not steel. Pad coherence-change events cannot be validated, because DEP spud and plug dates do not fall in the window. |
| 5 | Bright targets over 9t and Warren | `_nisar_bright_targets_9t.py`, `_nisar_bright_targets_wells_warren.py` | `nisar_bright_targets_wells_warren.md` | Warren: wells with a target 3.9% against 5.2% random (odds ratio 0.75, p 0.16). Under canopy 0.40 (p 0.006), fewer than chance. |
| 6 | Pumpjack pilot, lidar (not NISAR) | `_lidar_pumpjack_pilot_warren.py` | commits `4da4dbe`, `3a1f2eb` | Bright compact objects do not separate wells from controls. |
| 7 | Can NISAR screen false positives of the lidar pit detector? | `_nisar_pit_fp_screen_9t.py` | `nisar_pit_fp_screen.md` | No. 61 TP and 29 FP. Detector score alone 0.843, with NISAR 0.817 (gain −0.026, p 0.58). Low power, so it shows NISAR does not help at this effect size and does not show the effect is zero. |
| 8 | The feature-product study (the main one) | `_nisar_feat_*_9t.py` | `nisar_feature_products_plan.md`, `nisar_corrected_rescoring_9t.md` (current), `nisar_pad_features_scored_9t.md` and `nisar_pit_features_scored_9t.md` (first pass, superseded) | Sections 6 to 8 and 14. |

## 6. The feature-product study

**Idea.** Build every SAR-derived measurement we can think of, score each against matched non-pad ground, then test them together in a model.

### 6.1 Products (351 bands scored)

Scripts are in `notebooks/wellsight_v2/s5_eval/`. Shared code is `_nisar_feat_common.py`. Each product writes one raster, with the track as a suffix (`_t026`, `_t090`, `_t162`).

| Product | Script | Bands | What it measures |
|---|---|---|---|
| Amplitude statistics | `_nisar_features_vs_flatness_9t.py` | 32 | Median, percentile and coherence summaries of HH and HV dB per track. |
| Dual-pol | `_nisar_feat_dualpol_9t.py` | 21 | RVI, RFDI, entropy, alpha, degree of polarisation, rho, phi. |
| Texture and edge | `_nisar_feat_texture_9t.py` | 15 | Local coefficient of variation, edge strength. |
| Spatial | `_nisar_feat_spatial_9t.py` | 63 | Multi-scale standard deviation, skew, kurtosis, gradient, difference of Gaussians, anisotropy, GLCM texture. |
| Amplitude trend and season | `_nisar_feat_amp_trend_9t.py` | 42 | Slope over time, seasonal contrast. |
| Temporal | `_nisar_feat_temporal_9t.py` | 43 | Dispersion, IQR, HV/HH ratio, temporal correlation, cross-track differences. |
| Events | `_nisar_feat_events_9t.py` | 15 | Bright and dark outliers. |
| Geometry | `_nisar_feat_geometry_9t.py` | 14 | Terrain-flattened brightness and simulated facet area, using lidar terrain. |
| Line-of-sight motion | `_nisar_feat_los_motion_9t.py` | 12 | Phase-derived motion. |
| Coherence | `_nisar_feat_coherence_9t.py` | 43 | Coherence decay, short and long gaps, season, closure phase. |
| Sub-aperture | `_nisar_feat_subaperture_9t.py` | 15 | Three azimuth looks and two range bands (HH only). |
| Height residual | `_nisar_feat_height_resid_9t.py` | 9 | Scattering height above lidar ground, from phase against perpendicular baseline, and baseline decorrelation. |
| Rain and freeze | `_nisar_feat_rain_freeze_9t.py`, weather from `_weather_prism_daily_9t.py` | 22 | Brightness response to a 10-day antecedent rain index and to frozen ground. |
| Road context | `_nisar_feat_road_context_9t.py` | 2 | Distance to annotated roads. **Circular. Excluded from every NISAR set.** |
| Lidar controls | built in the scorer | 3 | Cover, slope, roughness. Used as the baseline. |

The model keeps 337 to 340 NISAR bands after the missingness filter.

### 6.2 Scoring protocol (`_nisar_feat_score_9t.py`)

1. **Target value.** For each pad, the median over the core pixels nearest the pad centre. Core = the polygon shrunk by 5 m (`CORE_SHRINK_M=15` keeps only large pads). Each target uses the largest of 9, 16, 25, 36 or 49 pixels that fits its core (pits: 4 or 9, no shrink). The first-pass run took up to 49 pixels and let small pads use fewer, while decoys always used 49. That mismatch was fixed on 2026-10-26.
2. **Decoys.** 10 per target. Each decoy is a disc with the same pixel count as its target, and must have the same minimum count of finite values. Allowed only at least 100 m from any pad, pit, road or DEP well. Matched on lidar mean canopy cover within 0.05 and mean slope within 1 degree. Matching uses continuous values. Coarse bins leaked (Section 9).
3. **Decoy variants.**
   - Default: decoys anywhere on the tile.
   - `ROAD_NEAR=1`: decoys 30 to 100 m from a road, because pads sit a median 7 m from a road.
   - `MATCH_ROUGH=1` (pits): decoy roughness within 0.25 of the target spread.
   - `LOCAL_M=750` or `1500`: decoys 100 m to `LOCAL_M` from their own target. This keeps pad and decoy in the same neighbourhood.
4. **Single-band statistics.** AUC with bootstrap CI, Mann-Whitney p, Benjamini-Hochberg q across bands, and the split by canopy class (open under 25%, partly 25 to 50%, grown over 50%).
5. **Samples file.** The scorer writes `nisar_<target>_samples_9t[suffix].npz` (values, blocks, cover, area, coordinates). All model, ablation, HH/HV and fusion scripts read it.

### 6.3 Model (`_nisar_feat_model_9t.py`, CV in `_nisar_feat_common.py: oof_probs`)

- Histogram gradient boosting (depth 3, learning rate 0.06, 200 iterations, L2 1.0, min leaf 40, balanced class weight).
- 5-fold CV grouped by 500 m block (block taken from the pad centroid). Training rows within 250 m of any test row are removed. AUC is pooled out-of-fold, with a block-bootstrap CI, and the five fold AUCs are reported too.
- Bands more than 20% missing in either **training** class are dropped, and the rest are median-imputed with training medians, inside each fold.
- **Controls in every run.** Simple lidar baseline (cover, slope, roughness). **Rich lidar baseline** (26 bands: the same spatial operators the SAR product uses, run on lidar cover, slope and roughness, plus forest fraction at 75 m and 155 m). **Map x/y only.** Combinations with each.
- **Gate.** NISAR + rich baseline must exceed the rich baseline by at least 0.05.
- **Placebo.** One decoy per target plays "pad" against the other decoys. It must score about 0.5.
- The first-pass run used the unbuffered split, global imputation, and only the simple baseline.

### 6.4 Added tests

| Test | Script | Purpose |
|---|---|---|
| Ablation | `_nisar_feat_ablate_9t.py` | Leave one product group out. HH only, HV only, no-polarisation bands. Single track or track pair. Pad-area terciles. |
| HH against HV twins | `_nisar_feat_hhhv_9t.py` | Keep only bands that exist in both HH and HV built by the same recipe (89 pairs). Paired signed-rank test. Model on HH twins, HV twins, both. Shuffled-label null (20 runs, shuffled within 500 m blocks). |
| Fusion with the lidar U-Net | `_nisar_feat_fusion_9t.py` | Add the pad U-Net's out-of-fold score as a feature (Section 7.5). |

## 7. Results

### 7.0 Corrected results (current)

Model AUC on the lidar-placed SLC stack, 5-fold block CV with a 250 m buffer, fold-local preprocessing. Full tables and attribution: `docs/iterations/nisar_corrected_rescoring_9t.md`.

| Feature set | Pads, decoys anywhere (633) | Pads, local decoys 100 to 1,500 m (297) | Pits (489) |
|---|---|---|---|
| simple lidar baseline | 0.465 | 0.435 | 0.849 |
| rich lidar baseline | 0.917 | 0.923 | 0.968 |
| map x/y only | 0.815 | 0.517 | 0.955 |
| **all NISAR** | **0.635** | **0.476** | **0.832** |
| NISAR without geometry | 0.624 | 0.483 | 0.781 |
| NISAR + rich lidar baseline | 0.921 | 0.904 | 0.967 |
| NISAR + rich baseline + map x/y | 0.930 | 0.890 | 0.987 |
| placebo | 0.477 | 0.519 | 0.498 |

- The gate (NISAR + rich lidar beats rich lidar by 0.05) fails in every column.
- Fold AUCs vary widely (all-NISAR fold spread 0.06 to 0.11), so a pooled AUC hides instability.
- HH against HV twins (89 pairs): pads with local decoys show no HH advantage (strength 0.037 against 0.035, p 0.47). Pits show one (0.073 against 0.050), but pits are not separable from location once coordinates are in the model.
- Ablation, decoys anywhere: removing any one group changes AUC by 0.012 or less.
- Re-scoring the **old** samples with only the new CV gives 0.699 and 0.587, against the old 0.815 and 0.713. The CV change explains 64% and 53% of the drop. The corrected data explains the rest.
- Single SAR bands still show weak differences on their own (best about 0.63 to 0.66, local decoys), but they do not carry across blocks.
- Lidar texture is the strongest single signal: local slope variation at 3 pixels scores 0.93. Pads are smooth graded surfaces.

### 7.1 to 7.6: first-pass results (superseded, kept for the record)

The tables below come from the first-pass pipeline. Do not quote them. They show how the early numbers were produced and why they were wrong. All AUCs are model AUCs from 5-fold block CV unless marked.

### 7.1 Pads, by decoy design

| Run | Pads | All NISAR | SAR only (no geometry) | Lidar baseline | Placebo |
|---|---|---|---|---|---|
| Core 5 m, decoys anywhere | 626 | 0.815 | 0.801 | 0.574 | 0.496 |
| Core 5 m, decoys 30 to 100 m from a road | 626 | 0.884 | 0.880 | 0.590 | 0.484 |
| Core 15 m, 139 large pads | 139 | 0.959 | 0.960 | 0.513 | 0.500 |
| Core 15 m, decoys near roads | 139 | 0.960 | 0.964 | 0.618 | 0.483 |
| **Local decoys, 750 m** | 87 | 0.695 | 0.693 | n/a | 0.466 |
| **Local decoys, 1,500 m** | 274 | **0.713** (CI 0.63 to 0.83) | 0.691 | 0.504 | 0.490 |

Road context alone scores 0.97 to 0.996 in every run. That is circular, because roads were drawn to reach pads. It is never counted as NISAR.

### 7.2 Is the score chance, or just location? (shuffled-label null)

Labels were shuffled among rows of the same 500 m block, which keeps each block's pad share. This estimates how much a model can learn from location alone.

| Target | Real AUC (HH + HV twins) | Shuffled mean (sd) | Shuffled max |
|---|---|---|---|
| Pads, road-near decoys | 0.877 | 0.775 (0.010) | 0.796 |
| Pits | 0.856 | 0.800 (0.009) | 0.811 |

The real score is far above chance (0.5), but much of it is location. This is why the local-decoy design (7.1) is the better estimate for pads.

### 7.3 Which NISAR aspect carries it

Pads, product groups alone, core 5 m (far decoys, then road-near decoys):

| Product | AUC |
|---|---|
| Spatial | 0.78, 0.82 |
| Geometry | 0.77, 0.77 |
| Sub-aperture | 0.72, 0.62 |
| Amplitude statistics | 0.68, 0.75 |
| Temporal | 0.66, 0.71 |
| Rain-freeze | 0.62, 0.67 |
| Height | 0.62, 0.69 |
| Coherence | 0.60, 0.73 |
| Dual-pol | 0.51, 0.58 (no signal) |

Leave-one-group-out (all NISAR 0.815 far, 0.884 road-near, 0.695 local 750 m): removing **spatial** costs 0.036, 0.027 and 0.050. Removing any other group costs 0.015 or less, except coherence under local decoys (0.046). The groups overlap, so a small drop does not mean a group is useless.

Local decoys, 750 m, product groups alone: spatial 0.709, geometry 0.698, dual-pol 0.62, coherence 0.594, the rest about 0.5.

### 7.4 HH against HV

On identical bands (89 twin pairs):

| | Pads, road-near | Pits |
|---|---|---|
| Mean per-band strength, HH / HV | 0.068 / 0.065 | 0.065 / 0.050 |
| Paired signed-rank p | 0.52 | 0.002 |
| Model on HH twins / HV twins | 0.847 / 0.828 | 0.836 / 0.788 |
| Model on both | 0.877 | 0.856 |

For pads, HH is not meaningfully better than HV. The earlier "HH only 0.795, HV only 0.742" comparison used unequal band sets (HH included the HH-only sub-aperture product). For pits, HH is modestly better. The pad twin test has not been run for local decoys or core 5 m with far decoys.

### 7.5 Fusion with the lidar U-Net (not reliable)

> The audit of 2026-10-26 found that the U-Net training sampler can read held-out pixels. The U-Net AUC below is not a leakage-free ceiling. Not re-run.

The pad U-Net 5-fold CV (`notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py`) wrote one probability raster per fold at 0.5 m. Each fold's model never saw that fold's 375 m blocks. For every pad and decoy, the score is the mean over a 10 m window of the raster of the fold that holds out the block the point lies in. Decoys in the 15 blocks with no pad were dropped. All sets use the same 3,195 rows (626 pads).

| Feature set | AUC |
|---|---|
| U-Net out-of-fold, raw score | about 1.00 (printed to 3 decimals as 1.0) |
| Lidar baseline | 0.505 |
| All NISAR | 0.749 |
| NISAR + baseline | 0.724 |
| NISAR + U-Net | 0.999 |

On "pad against ordinary ground" the U-Net is at ceiling, so there is no room for NISAR to add. The U-Net's own held-out detection recall is 0.80 to 0.94 (IoU 0.3) and precision 0.53 to 0.68 (`data/9t/models/pad/unet_cv5/pad_cv5_per_fold_9t.csv`). This test does not show where lidar fails.

### 7.6 Pits

495 usable pits (488 with decoys, 467 with roughness-matched decoys).

| Feature set | Cover and slope matched | Plus roughness matched |
|---|---|---|
| Lidar baseline | 0.858 | 0.853 |
| All NISAR | 0.910 | 0.911 |
| SAR only | 0.886 | 0.882 |
| NISAR + baseline | 0.949 | 0.959 |
| Placebo | 0.491 | 0.464 |

- Dual-pol volume measures (RFDI, RVI) are the strongest single group for pits and carry no signal for pads. Pits show less volume scattering.
- The strongest single bands are local HH contrast (`spatial:sd15_hh_t090`, 0.752) and `dualpol:rfdi_t162` (0.741).
- 82% of pits sit beside a pad. For the 88 pits at least 50 m from a pad, `sd15_hh_t090` reaches 0.818.
- NISAR beats the lidar baseline by 0.052 to 0.058. SAR only does not clear the 0.05 gate (0.029 gain with roughness matched).
- The shuffled-label null is 0.800, so the real margin over location is about 0.056.

## 8. How lidar enters, and where it does not

1. **Decoy matching.** Cover and slope are lidar-derived.
2. **Baseline.** Cover, slope and roughness form the comparison model. This is three terrain statistics, not the U-Net.
3. **Geometry products.** Terrain-flattened brightness and simulated facet area use lidar terrain.
4. **Registration.** The SLC stack is re-placed on the lidar bare earth, and the height and sub-aperture products depend on it.
5. **Fusion.** The U-Net's out-of-fold score (7.5).

SAR-only sets (no geometry) score about the same as all NISAR for pads. So lidar-derived geometry is not what carries the pad result.

## 9. Leaks and errors found, and what changed

| Problem | Effect | Fix |
|---|---|---|
| Coarse cover bins | Lidar cover scored AUC 0.24 against "matched" decoys. | Continuous matching. Controls then score 0.49 (cover), 0.47 (roughness), 0.45 (slope). |
| Model missingness | One product was 81% NaN for pads and 32% for decoys. Pooled AUC fell 0.91 to 0.80 when handled. | Drop bands over 20% missing in either class. Median-impute the rest. |
| Unequal sample sizes | Pad cores were medians over more pixels than decoys. | Both use 49 pixels (9 for pits). |
| Road proximity | Pads sit a median 7 m from a road. Decoys were at least 100 m. | `ROAD_NEAR=1` decoys. The score did not fall. |
| Location | Shuffled-label null 0.775 to 0.800. | Local decoys (`LOCAL_M`). Real pad score about 0.71. |
| Script slip | The model script ignored `MATCH_ROUGH` in its file name, so one run re-read unmatched samples. | Suffix fixed and the matched run redone. |
| Block assignment | Block of a pad was taken from the median of flattened pixel indices, a different block from the centroid's for 13.9% of pads. | Block from the centroid. |
| Unequal pixel counts, still | 76% of pads had fewer than 49 core pixels, decoys always 49. The 15 m core had a median of 9. | Per-pad pixel count, same-size decoys, same finite-value rule. |
| Bad date in default stack | `BAD_DATES` applied only to the SLC stack, so 2026-09-08 (track 26) was in every GSLC product. | Dropped on every stack. |
| Wrong stack | The study ran on NASA's GSLC, not the lidar-placed stack. | Products rebuilt on the SLC stack. |
| Labels before the split | Band filtering and imputation used all rows. | Done inside each training fold. |
| Neighbouring footprints | Unbuffered GroupKFold. | 250 m train-test buffer. |
| No location or rich-lidar control | The lidar baseline was matched on its own variables and could not fail. | Map x/y and rich lidar baseline added. |
| Height product | Unit error, wrong wavelength, forced sign. | Fixed, then dropped (forest median 0.1 to 0.8 m). |
| Early comparison | Pad pixels compared with many ring pixels (right-skewed brightness). | Equal pixel counts, matched decoys. |

## 10. Weak points a reviewer should press on

(State after correction. Section 14 lists what the reviews raised.)

- **Registration** is about 10 m, not independently confirmed.
- **One area, one date window.** No spatial transfer test. Warren has no pad labels.
- **Local decoys** cover 274 of 649 pads (pads with at least 10 matching candidates within 1,500 m). Those pads may differ from the rest. Matched decoys can also contain unannotated pads.
- **Pad size** is not matched. Terciles of pad area (core 5 m, far decoys) score 0.854, 0.806, 0.785. Under local 750 m decoys the largest third falls to 0.53, but that is about 29 pads and noisy.
- **Pits** sit beside pads in 82% of cases, so pit and pad signatures overlap. The lidar baseline favours pits because pits are depressions.
- **Freeze and rain products** rest on 1 to 2 frozen dates per track and one 4 km PRISM cell for the whole tile.
- **Height residual** is local only (the long-wave removal also removes the mean canopy offset).
- **Beta and provisional calibration** differ between dates and tracks. Per-track HV summer-versus-fall offsets range from +1.9 to +4.2 dB, which points to calibration, not season.
- **Multiple comparisons.** 351 bands are scored. Benjamini-Hochberg q is applied to single bands only, not to model choices (which sets to report).
- **Mechanism is untested.** HH's role is hypothesised, not shown.
- **No held-out area.** CV is by 500 m block inside one tile.

## 11. Not done

The checks raised by the reviews were run on 2026-10-27 (Section 15) and again after two outside reviews of `NISAR_FINDINGS.md` (Section 16). What remains:
- A pad held-out test on a second tile. 613590 has no annotated pad polygons. A review package of 161 candidates is at `data/613590/results/nisar/nisar_pad_review_candidates_613590.gpkg`.
- A registration estimate that works. The test with lidar objects and steady bright radar points was null.
- A larger sample of pads against other clearings (60 pads, radar and Sentinel-2 tie), and pit decoys with footprint matching and incidence matching as separate factors.
- A calibrated HV noise floor, and LOS motion as connected-network displacement (kept exploratory).
- Change detection through time, pads that lidar cannot see at all, and old pads with known ages.
- Warren pad scoring (no annotations) and Warren geometry (no lidar radar simulation).
- Spring dates (flooded-forest double bounce) (`docs/iterations/BACKLOG.md`).

## 12. Where things are

### 12.1 Scripts

| Folder | Content |
|---|---|
| `notebooks/wellsight_v2/_nisar_area.py` | Area registry (`9t`, `613590`, `mkf`, `warren`), paths, stack choice (`NISAR_STACK`), bad dates. |
| `notebooks/wellsight_v2/s1_build/` | `_fetch_nisar_gslc_window_9t.py`, `_fetch_nisar_rslc_window_9t.py`, `_nisar_geometry.py`, `_nisar_regeocode_lidar_9t.py`. |
| `notebooks/wellsight_v2/s5_eval/` | 34 `_nisar_*` scripts: earlier tests (steel, pad change, slope motion, bright targets, interferograms, GCOV, seasonal stack, pit false-positive screen) and the whole feature study (`_nisar_feat_*`). Also `_weather_prism_daily_9t.py`, which the rain-freeze product needs. |
| `notebooks/wellsight_v2/nisar_reflectors/` | Python contracts for a compact-reflector framework (`docs/iterations/nisar_reflector_framework.md`). Design only. |
| `docs/presentation/` | NISAR slides, figures and `_nisar_broad_statements.py`. |

These are not in one folder. The feature study is in `s5_eval/` beside unrelated pit, pad and road scripts. Moving them would require `tools/apply_moves.py` and import fixes.

### 12.2 Outputs

- `data/9t/results/nisar/`: all scored results. The key families are:
  - `nisar_pad_feature_auc_per_band_9t[_core15m][_roadnear][_local750][_local1500].csv` (single-band AUCs)
  - `nisar_pad_model_auc_by_set_9t[...].csv` and `nisar_pad_model_summary_9t[...].json`
  - `nisar_pad_ablation_auc_9t[...].csv`
  - `nisar_pad_hhhv_pairs_9t_roadnear.csv`, `nisar_pad_hhhv_models_9t_roadnear.csv`, and the `nisar_pit_hhhv_*` pair
  - `nisar_pad_fusion_auc_9t_slc_unet_cv5[_iso].csv`
  - 2026-10-27 checks, all `_9t_slc[...]`: `nisar_{pad,pit}_repeatcv_auc_*`, `nisar_{pad,pit}_band_cluster_tests_*`, `nisar_pad_status_auc_*`, `nisar_pad_subset_effect_auc_*`, `nisar_pad_fp_screen_{auc,precision,bands,candidates}_*_cv5_iso_tau0p{30,50}`, `nisar_radnorm_*`, `nisar_signal_checks_*`; design tags `_shape_inc`, `_placebo`, `_confuser`, `_roadnear_confuser`. 613590: `data/613590/results/nisar/nisar_pit_heldout_*_613590_slc`
  - `nisar_pit_feature_auc_per_band_9t[_roughmatch].csv`, `nisar_pit_model_auc_by_set_9t[_roughmatch].csv`, `nisar_pit_ablation_auc_9t[_roughmatch].csv`
  - earlier tests: `nisar_steel_*`, `nisar_pad_change_*`, `nisar_slope_motion_*`, `nisar_bright_targets_*`, `nisar_gslc_*`, `nisar_pit_fp_screen_*`
- `data/warren/results/nisar/`: the Warren bright-target results.
- Sample files for the model: `data/9t/derived/nisar_features_5m/nisar_<pad|pit>_samples_9t[suffix].npz` (git-ignored).

### 12.3 Docs

`docs/iterations/nisar_*.md` (15 files), `docs/analysis_log.md` (newest on top), `docs/iterations/LEADERBOARD.md` (NISAR section at the end), `docs/iterations/BACKLOG.md`, `docs/nisar_lidar_supplement_proposal.md`.

## 13. Reproduce the feature study

```
# data (needs Earthdata credentials in ~/_netrc)
python notebooks/wellsight_v2/s1_build/_fetch_nisar_gslc_window_9t.py
python notebooks/wellsight_v2/s1_build/_fetch_nisar_rslc_window_9t.py
python notebooks/wellsight_v2/s1_build/_nisar_regeocode_lidar_9t.py
python notebooks/wellsight_v2/s5_eval/_weather_prism_daily_9t.py

# feature products
python notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py
for p in dualpol texture spatial amp_trend temporal events geometry los_motion coherence subaperture rain_freeze road_context; do
  python notebooks/wellsight_v2/s5_eval/_nisar_feat_${p}_9t.py; done
NISAR_STACK=slc python notebooks/wellsight_v2/s5_eval/_nisar_feat_height_resid_9t.py
#   then rename the output to nisar_feat_heightresid_9t_5m.tif if it carries "_slc"

# scoring and model (env variables select the design)
python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
ROAD_NEAR=1 ...                 # decoys 30-100 m from a road
CORE_SHRINK_M=15 ...            # large pads only
LOCAL_M=1500 ...                # decoys in the pad's neighbourhood
TARGET=pit [MATCH_ROUGH=1] ...  # pits instead of pads

# extra tests (same environment variables as the run they read)
python notebooks/wellsight_v2/s5_eval/_nisar_feat_ablate_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_hhhv_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_fusion_9t.py   # needs pad_xy in the samples file
```

The scripts use a fixed seed (20261026). The samples file must come from the same environment variables as the script that reads it.

## 14. Review history and corrections (2026-10-26)

Two outside reviews arrived on the day this file was first written.
1. An outside methods review (it read the scorer, model, null, fusion and the feature products).
2. A Codex audit, `docs/iterations/nisar_methodology_audit_20261026.md`, with scripts and machine-readable results in `tmp/nisar_method_audit.py` and `tmp/nisar_boundary_audit.py`.

I checked each claim against the code and data before acting. Upheld and fixed: the block-assignment bug, unequal pixel counts, bad date in the default stack, GSLC instead of the lidar-placed stack, labels used before the split, unbuffered CV, the height-product unit and wavelength errors. Added controls: rich lidar baseline and map x/y only. Not upheld: the claim that the range bandwidth is 20 MHz (it is 40 MHz, from the file index).

The audit's most consequential finding was that a coordinate-only classifier (0.738) beat NISAR (0.713) on the same local-decoy samples. The corrected re-run confirms location is the larger effect. Details, attribution and the full list of what remains: `docs/iterations/nisar_corrected_rescoring_9t.md`.

Issues the audit raised that are not addressed and that matter for the claims above: the LOS-motion bands are not measured displacement (zero-filled steps, disconnected gaps); season and processing release are confounded (all winter acquisitions are beta, all summer ones provisional); `skew7` and `kurt7` are not true window moments; single-band p-values assume independence; the regeocode reproduction command in Section 13 omits the lidar and write options.

## 15. Follow-up checks (2026-10-27)

Write-up with every table: `docs/iterations/nisar_checks_9t.md`. Pre-registration of the 613590 test: `docs/iterations/nisar_heldout_613590_prereg.md`.

| Check | Result |
|---|---|
| Decoys with the target's own footprint and matched incidence (scorer options `SHAPE=1 INC_MATCH=1`) | Pads: NISAR 0.657 (tile-wide) and 0.490 (local). Pits: NISAR falls from 0.829 to 0.568. No gain over lidar. |
| Pad footprint moved 150 to 300 m (`PLACEBO=1`) | Pseudo-pads are found by map coordinates (0.890), not by NISAR (0.504). |
| Decoys only from other clearings (`CONFUSER=1`) | 60 pads. NISAR 0.80, rich lidar 0.99, combined 0.99. |
| DEP status of the well on the pad | No group shows a NISAR signal beyond lidar. 9 pads on orphan-list wells, too few to score. |
| Frozen model on 613590 pits | NISAR 0.658, rich lidar 0.881, combined 0.865. Gate failed. All three predictions held. |
| Repeated CV (10 repeats), block-clustered band tests | Gain over lidar -0.01 to +0.003. Significant pad bands fall from 229 (naive) to 20 (clustered), and local-decoy bands from 137 to 0. |
| Isolated U-Net retrain | Recall at IoU 0.3 is 0.872 against 0.888 for the original sampler (F1 about 0.705 for the isolated model; 0.888 is a recall, corrected 2026-10-27). Fusion: NISAR + U-Net 0.995 against U-Net 0.999. |
| Pad false-positive screen on U-Net candidates | NISAR alone separates true from false (0.72, tau 0.3). Score + NISAR 0.831 against score 0.849. Precision at 70% recall +0.034 (-0.008 to +0.061). |
| Signal quality | Single-look speckle (ENL about 0.85), neighbour correlation 0.38, impulse response 3.9 m (slant range) by 5.7 m (azimuth), occupied bandwidth 31 to 33 MHz, no RFI. |
| Per-date radiometric normalisation | HV date offsets sd 1.1 to 1.8 dB. Normalising changes no AUC by more than 0.015. |
| LOS motion | Kept exploratory. Removing the group changes AUC by -0.005 and +0.010. |

Corrected along the way: `skew7` and `kurt7` are now true window moments (headline moved by 0.005 or less). The reviewer's 20 MHz claim stays not upheld: measured occupied bandwidth is 31 to 33 MHz against a nominal 40.

## 16. Follow-up checks after two outside reviews (2026-10-27)

Write-up with every table: `docs/iterations/nisar_followup_checks_9t.md`. Summary in `NISAR_FINDINGS.md`, Section 5.

| Check | Result |
|---|---|
| Radar where lidar is weak (pads the U-Net missed, in canopy, lidar-weak quartile) | Gain over rich lidar +0.001, 0.000 and +0.015 (tile-wide design only; +0.003 in the local design). Gate +0.05 not met. |
| Radar alone against Sentinel-2 alone | Matched decoys: Sentinel-2 0.840, NISAR 0.622. Other clearings (60 pads): 0.781 and 0.795. NISAR adds nothing to Sentinel-2. |
| Why 0.64 tile-wide and 0.48 local | NISAR AUC rises with decoy distance, 0.44 (100 to 500 m) to 0.71 (over 3.5 km), like map x/y and Sentinel-2. A place effect. |
| Terrain flattening of HV | Adding HV minus the simulated facet gain changes no score by more than 0.002. |
| Registration from point targets | No peak. Uninformative. No shift applied. |
| Pit drop on a fixed set of 173 pits | NISAR 0.811 (full set), 0.756 (173 pits, original decoys), 0.643 (173 pits, shape and incidence decoys). One third sample, two thirds design. |
| Optical audit | Reflectance offset already removed in all scenes. On unseen 1 km squares optical explains 0.44 to 0.55 of HV, lidar under 0.02. In closed forest the terrain gain explains most of raw HV (held-out R2 0.57 with lidar). |

Correction: the isolated pad U-Net has recall 0.872, precision 0.592 and F1 about 0.705. The 0.888 reported as its F1 in an earlier version of `NISAR_FINDINGS.md` is the original sampler's recall.

Scripts (`notebooks/wellsight_v2/s5_eval/`): `_nisar_weak_lidar_9t.py`, `_nisar_radar_vs_optical_pads_9t.py`, `_nisar_optical_feats_9t.py`, `_nisar_pad_distance_bands_9t.py`, `_nisar_hvflat_9t.py`, `_nisar_registration_points_9t.py`, `_nisar_pit_fixed_subset_9t.py`, `_nisar_vs_optical_heldout_9t.py`.
