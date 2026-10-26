# NISAR feature products for pad detection: plan

Written 2026-10-26. Status: plan only, except product 1 (running).

## Question
Can NISAR find well pads where there is no lidar? The physical hypothesis is that a pad is unnaturally flat and stable, so radar measures tied to flatness and stability should separate it from natural ground.

## Data on disk
- GSLC windows, complex, HH and HV, 5 m grid, EPSG:32617.
  - 9t: `data/9t/derived/nisar_gslc_5m/`. Tracks 26 (descending), 90 and 162 (ascending), about 49 dates, 2025-10 to 2026-10.
  - Warren: `data/warren/derived/nisar_gslc_5m/`. Same tracks, 49 dates.
- RSLC windows: 9t only, `data/9t/derived/nisar_rslc_window/`.
- GCOV (20 m, 2026-01-20 only), 9t.
- Lidar 1 m derivatives (slope, roughness_5, CHM, DEM, DSM) for both areas.
- Truth: 995 annotated pads on 9t (650 usable), pit and road annotations, held-out pad U-Net predictions (`data/9t/results/pad/thresholds/`). Warren has no annotations.
- Limits: no VV, so no full polarimetric decomposition. Radar-to-lidar registration is about 10 m on 9t and unchecked on Warren. Track 26 dates 2026-07-22 and 2026-09-08 are bad granules.

## Shared design
- One feature stack per area: `data/<area>/derived/nisar_features_5m/nisar_feature_stack_<area>_5m.tif`. One band per feature, band names set with `set_band_description`. Ignored by git.
- One script per product family. Each reads the complex windows through `_nisar_gslc_interferogram_pits_9t.load_complex` and `interferogram`, and appends its bands to the stack. Names follow `_nisar_<what>_<area>.py`.
- Product 1 builds the stack. Later products add bands, so every run is cached and never recomputed.
- One scorer reads the stack and scores every band against pads. No product scores itself.
- Memory: at most three heavy runs in parallel. A 9t stack of 49 complex windows is about 0.5 GB. Per-pixel fits are vectorised over the 981 x 981 grid.

## Scoring protocol (applies to every product)
- Positives: annotated pad cores (pad shrunk 5 m), pixels on the 5 m grid. One value per pad (median of core pixels).
- Negatives, three kinds, always reported separately.
  1. Matched: same canopy-cover class and slope class as the pad, at least 100 m from any pad, DEP well, road or pit.
  2. Unmatched: any ground at least 100 m from the same features.
  3. U-Net: pixels where the held-out U-Net probability is below 0.1 (lidar says not a pad).
- Report per feature: AUC with bootstrap 95% CI, per canopy class (open under 25%, partly grown 25 to 50%, grown over above 50%).
- Multiple testing: Benjamini-Hochberg over all features, q = 0.05. A feature counts only if the CI for matched AUC excludes 0.5 after correction.
- Spatial split for any model: 500 m blocks, 5-fold, no pad and no negative shares a block with its test fold.
- Baseline every model must beat: canopy cover and slope alone (no NISAR). Incremental AUC must be at least 0.05.
- Registration: score at zero shift and at the best shift already measured (`nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_forcedshift_9t_5m.json`). Report both.
- Tracks are not merged before scoring. Each track's feature is scored alone, then combined.
- Stop rule: if no single feature and no model beats the baseline on matched negatives, write the null result, update the log and BACKLOG, and stop.

## Products

### 1. Flatness check and amplitude statistics (running)
- Script: `notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py`.
- Bands per track: HH and HV mean dB, HV minus HH, HH std in dB, p90 minus p10, amplitude dispersion; HH coherence over all pairs binned by gap (up to 12, 13 to 36, over 36 days) and the short-minus-long decay; track differences (ascending 90 minus 162, descending minus ascending).
- Test: Spearman against lidar slope and roughness on open ground (cover under 0.30 and 0.10), with closed canopy as control; AUC steep versus flat.
- Output: `data/9t/results/nisar/nisar_features_vs_flatness_per_feature_9t.csv`, `nisar_features_vs_flatness_summary_9t.json`.
- Gate: a feature that does not follow lidar flatness on open ground is dropped from the pad test.

### 2. Dual-pol polarimetry
- Script: `_nisar_dualpol_features_9t.py`.
- Inputs: HH and HV complex, 3 x 3 or 5 x 5 boxcar covariance C2 = [[<HH HH*>, <HH HV*>], [<HV HH*>, <HV HV*>]], averaged over dates per track.
- Bands: RVI = 4 HV / (HH + HV) in power, RFDI = (HH - HV) / (HH + HV), entropy and alpha from the eigen-decomposition of C2, degree of polarisation, HH-HV correlation magnitude and phase.
- Cost: low. Pure numpy over the stack.
- Expectation: weak. RFDI and the HV/HH ratio are the most likely to move.

### 3. Texture and edges
- Script: `_nisar_texture_edges_9t.py`.
- Input: the temporal mean power image per track (about 23 looks times 9 = strong despeckling).
- Bands: local variance-to-mean at 3 and 7 pixels, GLCM contrast and homogeneity at 7 x 7 (skimage), lacunarity, ratio-of-averages edge strength (four directions, max), CFAR edge map.
- Pad-shaped patch: threshold a smoothness measure, label connected patches, record area and compactness per patch.
- Cost: low to medium.
- Expectation: edges are the main hope, because a pad is a sharp-bordered patch.

### 4. Road and spur context
- Script: `_nisar_road_spurs_9t.py`.
- Method: oriented line filters (steerable second derivative, 5 to 8 orientations) on the mean power image give a linear-feature response. Skeletonise, find dead ends, and score pixels by distance to a dead end of a road-like line.
- Cross-check against the lidar road model output (`data/9t/results/road/`), which is also the training truth for roads.
- Cost: medium.
- Expectation: pads sit at the ends of access roads, so this could carry more than any single backscatter value. Radar road visibility is unknown.

### 5. Geometry and terrain-explained residual
- Script: `_nisar_geometry_residual_9t.py`.
- Incidence-angle dependence: per pixel, slope of mean dB against incidence angle across tracks 90 and 162 (two ascending angles) using each track's incidence from the granule metadata or `_nisar_geometry.py`.
- Ascending-to-descending ratio (already in product 1).
- Lidar-simulated residual: reuse `sim_layers(t, tf, shape)` from `_nisar_flatten_gain_test_9t.py` to get the simulated facet area; the residual is the measured dB minus 10 log10 of facet area minus the local median. This is the flattened view, so what is left is not terrain.
- Cost: low to medium. The simulator exists.
- Expectation: the best test of the "flat bench on a slope" idea.

### 6. Coherence and phase
- Script: `_nisar_coherence_decay_9t.py`.
- All pairs per track, 3 x 3 window. Fit gamma(dt) = g_inf + (g0 - g_inf) exp(-dt / tau) per pixel by a grid over tau and a linear solve for g_inf and g0. Bands: g_inf, g0, tau, fit residual.
- Mask snow dates (winter, from the earlier seasonal split) as a variant.
- Phase closure: triplets (i, j, k) in time order, closure = angle(I_ij I_jk conj(I_ik)). Band: mean absolute closure, short gaps only.
- Phase linking: select statistically homogeneous pixels with a KS test on the amplitude time series (7 x 7 neighbourhood), then EVD on the coherence matrix. Band: temporal coherence from the linked phase.
- Persistent scatterers: amplitude dispersion below 0.25 and phase dispersion (std of the phase against its model) below 0.3 rad.
- Cost: highest. About 250 pairs on track 90. Run per track, one process each.
- Expectation: decay and closure are the novel ones.

### 7. Rain and freeze response
- Script: `_nisar_weather_response_9t.py`.
- New input: daily precipitation at 9t. Source: PRISM daily (4 km) or NLDAS-2. Record the source and licence in `literature/CITATIONS.md` before use.
- Antecedent precipitation index API = sum over k of 0.9^k * P(t - k). Per pixel and per track, regress HH dB on API. Bands: slope, r squared.
- Freeze-thaw: mean dB on days with daily minimum below 0 C minus mean on days above 5 C. Band per track.
- Cost: low once the weather table exists.
- Expectation: a gravel pad drains and should respond differently from forest soil.

### 8. Transient targets and change events
- Script: `_nisar_transient_events_9t.py`.
- Per pixel and track, z-score each date's dB against the pixel's median and MAD. Bands: share of dates above z = 3, longest run, maximum z.
- Pad scoring: pad core share of pixels above threshold on any date, with events matched to dates.
- Truth: DEP wells with SPUD_DATE between 2025-10-28 and 2026-10-18. Count how many show an event within 60 days of spud, against decoys.
- Cost: low.
- Expectation: tests active drilling, not a static pad map. Also covers the "rig and trucks" idea.

### 9. Point targets and sub-aperture (9t only)
- Script: `_nisar_subaperture_9t.py`. Input: RSLC windows.
- Azimuth and range split-spectrum into three sub-looks. Bands: anisotropy (max over min sub-look power), sub-look coherence, impulse-response sidelobe cross strength around the brightest pixels.
- Cost: medium. Only 9t has RSLC.
- Expectation: separates metal from vegetation. Not a pad map, so score on bright targets near wells, not on pads.

### 10. Fusion and held-out U-Net comparison
- Script: `_nisar_pad_features_score_9t.py`, then `_nisar_pad_model_9t.py`.
- Scorer: runs the protocol above for every band. Output: `data/9t/results/nisar/nisar_pad_feature_auc_per_band_9t.csv`.
- Model: gradient-boosted trees (sklearn `HistGradientBoostingClassifier`) on the surviving bands plus the baseline, spatial 5-fold, report AUC, precision at 90% recall, and incremental AUC over the baseline.
- U-Net agreement: correlate model score with the held-out U-Net probability, and report where the NISAR model finds pads the U-Net misses and the reverse. Held-out predictions only.
- Warren: apply the frozen 9t model to Warren. No labels there, so report agreement with a Warren U-Net map (run only as a consistency check) and with DEP well locations.

### 11. Extra amplitude bands and trend
- Added to product 1's script as a second pass: temporal median, p10 and p90 as separate bands, and the per-pixel linear trend of HH dB over the year (slope in dB per 100 days, with its r squared).
- Seasonal means: leaf-off (Dec to Mar), leaf-on (Jun to Sep) and their difference, per polarisation.
- Cost: low. The trend is the regrowth idea: an old pad should brighten as it vegetates, but one year is short.

### 12. Coherence by season and polarisation
- Extends product 6. Repeat the gap-binned coherence for HV, and split by season (snow-free leaf-on, leaf-off, winter).
- Bands: coh_hv_short, coh_hv_long, coh_hh_leafon, coh_hh_leafoff, coh_hh_winter. HV coherence is more sensitive to canopy motion than HH.
- Cost: medium, same pair loop as product 6.

### 13. Deformation on pads
- Script: `_nisar_pad_los_motion_9t.py`.
- Chain of consecutive-pair phases (as in the existing slope-motion script), cumulative LOS displacement in mm, pixels with mean coherence under 0.45 masked.
- Per pad: median displacement and its drift over the year, against decoys. Tests settling or compaction.
- Cost: low, the chain code exists in `_nisar_slope_motion_9t.py`.

### 14. Interferometric height residual and volume coherence
- Script: `_nisar_height_residual_9t.py`.
- Height residual: the phase left after removing the lidar-DEM-predicted topographic phase, converted to height with the perpendicular baseline (`kz`). Only for pairs with a usable baseline and coherence above 0.5.
- Volume coherence: coherence against `kz` across pairs. A canopy lowers it, bare ground does not. Pol-InSAR (RVoG) canopy height is a possible extension, not planned.
- Cost: high, and baselines may be too short. A feasibility check on 10 pairs first.
- Expectation: long shot.

### 15. Geometry masks
- Layover and shadow masks per track from the lidar DSM (the facet-area simulator already marks them as NaN). Used as a mask and as a band (share of the pad core in shadow). A pad in the lee of a ridge is invisible, so it should not count as a miss.
- Cost: low, reuse `sim_layers`.

## Order and cost
| Step | Products | Reason |
|---|---|---|
| 1 | 1 | Gate. Running. |
| 2 | 5, 2, 3 | Cheap, and 5 tests the flatness idea directly |
| 3 | 8, 7 | Cheap, different physical idea |
| 4 | 6 | Expensive, run one process per track |
| 5 | 4 | Needs the road model outputs |
| 6 | 10 | Needs the surviving bands |
| 7 | 9 | 9t only, after the rest |
| Slot in | 11, 15 | With step 2, both cheap |
| Slot in | 12, 13 | With step 4, share the pair loop |
| Last | 14 | Feasibility check first, drop if baselines are too short |

## Documentation
- Each product gets `docs/iterations/<name>.md` (goal, inputs, params, results, interpretation, reproduce), an entry at the top of `docs/analysis_log.md`, a row in LEADERBOARD if it produces a model score, and a BACKLOG line for anything deferred.
- Literature to record in `literature/CITATIONS.md` when used: Berardino et al. 2002 (SBAS, already listed), Ferretti et al. 2011 (phase linking), Cloude and Pottier 1997 (entropy and alpha), Kim and van Zyl 2009 (RVI), Touzi et al. 1999 (ratio-of-averages edge detector), Zebker and Villasenor 1992 (decorrelation).
- Figures: colourblind rule, no red/green pair. Run the dataviz validator over all pairs.
- Large files: every new directory gets a `.gitignore` rule in the same change. Audit after each run.

## Risks
- Registration: a pad is 3 to 10 pixels, the radar-to-lidar offset is about 10 m. Scores will be blurred.
- Label incompleteness: unannotated pads in the negatives push every AUC toward 0.5. The 100 m exclusion and the U-Net negatives reduce it.
- Resolution: 5 m posting is oversampled relative to the native resolution, and pads are small.
- Canopy: L-band penetrates trees only partly. About half the pads are grown over, so the usable positives are the open and partly grown pads.
- Multiple testing: about 100 bands. The BH correction is required, and a single 'p = 0.03' is not a finding.
- Weather data: the daily series and the SAR dates must use the same time zone (UTC).
