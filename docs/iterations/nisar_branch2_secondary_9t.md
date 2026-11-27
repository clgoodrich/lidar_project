# NISAR 9t — Branch 2 secondary analysis (26–27 Nov 2026)

Source for a later 3-page write-up. Each item: why, what was run, result, reading.
Branch 1 (baseline) files in `nisar/results/9t/` are not touched. Branch 2 outputs go to `nisar/results/9t/v2/`.

## 0. Status of the outside plan

- Already done in the 26 Nov rerun (commit 75b244c): datum fix (1.29 m), D_A with ddof=1 and per-date scaling, pixel floor, seasonal n_decoys, slope look direction, processor-step test, coherence split by active wells, spec errata.
- That rerun overwrote Branch 1 results in place. The pre-fix baseline exists only in git at ad621b9.
- Two claimed bugs were not real:
  - `_nisar_pit_pool_9t.py` "_slc_slc": A.TAG is the area ("9t"), so the file name is right.
  - Pad dissolve by pad_id: pad_id is unique per polygon (995 of 995). Rerun outputs identical to baseline.
- Real fix: `_fetch_nisar_gslc_window_9t.py` now skips windows with no valid pixels.

## 1. Geolocation against buildings (Track 2A)

- Why: placement had never been checked against an independent point.
- Method: brightest pixel near each NAIP building vs the lidar wall facing the radar. NISAR looks left, so track 26 lights the west wall and tracks 90/162 the east wall.
- Result: only 1 of 9 buildings (T4) is inside the 9t lidar tile. The other 8 sit where radar is placed on NASA's DEM.
- T4: ascending peaks 1.7 m from the east wall, 9 m off north-south. Descending peak 30 m away (not the building).
- Reading: no conclusion. Needs neighbouring-tile lidar or a corner reflector.
- Files: `nisar/code/s5_eval/_nisar_building_geoloc_9t.py`, `nisar/results/9t/nisar_building_geoloc_summary_9t_slc.json`.

## 2. Troposphere vs fitted range offsets (Track 2B)

- Why: the geocoder models ionosphere only. Each track then gets an empirical slant-range offset.
- Result: fitted 3.80 / 2.01 / 2.82 m (t26 / t90 / t162). Dry delay 2.90 / 2.82 / 3.21 m. Means 2.88 vs 2.97 m. Residual RMS 0.73 m.
- Reading: the offsets mostly absorb the dry troposphere. For new tiles, apply the delay model and fit only the residual.
- Files: `nisar/code/s5_eval/_nisar_tropo_offset_check_9t.py`, `nisar/results/9t/v2/nisar_tropo_offset_check_9t.csv`.

## 3. Steel screen at pads, Branch 2 version (Track 2C)

- Why: baseline controls pass ~17%, so a few-percent hardware rate has no power. Baseline pooled tracks, matched controls on canopy only, used a pooled Fisher test.
- Changes: controls matched on canopy (0.15) and lidar slope (5°); each track separate; matched swap test and CMH over size × canopy strata; terrain-flattened variant; HH/HV filter; continuous composite; sub-look score.
- Units: 469 pads with 5 complete controls each.

| Variant | Pads | Controls | Swap p |
|---|---|---|---|
| Raw, any track | 19.6% | 14.1% | 0.0009 (passes Bonferroni, 20 tests) |
| Raw, t26 / t90 | 9.4 / 9.6% | 6.0 / 6.1% | 0.005 / 0.005 |
| Raw, t162 | 2.6% | 4.1% | 0.97 (pads lower) |
| Flattened, any track | 12.6% | 10.1% | 0.065 |
| Flattened + HH/HV, any | 11.7% | 9.6% | 0.096 |
| Composite score | AUC 0.47–0.51 | | 0.29–0.99 |
| Sub-look coherence | AUC 0.49–0.53 | | 0.02 (t26 only) – 0.88 |

- Reading: the raw excess is mostly terrain. Flattening removes bright slopes and most of the gap. Hardware on a flat pad would survive flattening, so this argues against hardware. No variant gives a usable detector.
- Files: `nisar/code/s5_eval/_nisar_steel_pads_v2_9t.py`, `nisar/results/9t/v2/nisar_steel_pads_v2_tests_9t_slc.csv`, `..._units_9t_slc.csv`, `..._summary_9t_slc.json`.

## 4. Sub-look coherence (Track 2C)

- Why: a point scatterer stays the same across the two halves of the azimuth spectrum; speckle does not.
- Method: carrier removed, azimuth band split at its centre, both halves placed with the production geocoder, multi-date coherence per pixel.
- Result: tile median 0.35–0.43. Known targets (3×3 max): metal yards 0.91–0.97, buildings 0.81–0.89, forest targets 0.78–0.86.
- Reading: weak separation of steel from forest on 8–12 dates. No pad signal.
- Files: `nisar/code/s5_eval/_nisar_sublook_9t.py`, `nisar/results/9t/v2/nisar_sublook_summary_9t.json`, rasters `nisar/derived/9t/v2/nisar_sublook_coherence_t{026,090,162}_9t.tif` (git-ignored).

## 5. Pad coherence with matched controls

- Why: baseline decoys were not matched on canopy or slope.
- Result: 205 drops vs 182 expected, swap p 0.056 (baseline 220 vs 182, p 0.007). Active-well share 46% (unchanged).
- Reading: the strongest lead weakens to borderline once terrain is matched.
- Files: `nisar/results/9t/v2/nisar_pad_change_matched_summary_9t_slc.json`, `..._events_9t_slc.gpkg`.

## 6. Seasonal brightness: 40 decoys and matched decoys

| Effect | Baseline (5) | 40 decoys | Matched (5) |
|---|---|---|---|
| Pads fall HH | −0.15 dB, p 2e-5 | −0.13, p 7e-5 | −0.12, p 4e-5 |
| Pits summer HV | +0.16 dB, p 8e-4 | +0.21, p 1e-4 | +0.16, p 0.004 |

- Reading: both effects hold under more and better-matched controls. These p-values treat sites as independent; the date-level test (26 Nov) is the stricter one for the pad effect.
- Files: `nisar/results/9t/v2/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_swap40_9t_slc_5m.csv`, `..._matched_9t_slc_5m.csv`.

## 7. Pits vs natural hollows

- Why: the pit HV excess could be any small closed depression, not a well marker.
- Hollows: lidar fill minus DEM > 0.2 m, floor 30–300 m², grown 3 m, ≥40 m from DEP wells, ≥20 m from pits, pads and roads, outline 75–500 m². 34 kept (pits: 723).
- Result (matched decoys): hollows summer HV −0.09 dB, 95% CI −0.30 to +0.77, p 0.46 (pits +0.16, CI +0.09 to +0.23). Summer HH +0.19, p 0.22.
- Reading: hollows do not show the pit HV excess, but 34 hollows give a CI that still contains +0.16. Not settled. Most closed depressions of pit size on 9t are the drawn pits, so a bigger hollow set needs another tile.
- Results: `nisar/results/9t/v2/nisar_gslc_stack_pad_pit_vs_decoy_summary_by_season_hollows_matched_9t_slc_5m.csv` (the "pit" rows are the hollows).
- Files: `nisar/code/s5_eval/_nisar_hollows_9t.py`, `nisar/derived/9t/nisar_hollows_polygons_9t.gpkg`.

## Overall reading (for the write-up)

- Matching controls on terrain weakens both pad leads: steel mostly disappears after flattening; coherence drops to p 0.056.
- Pad fall darkening and pit summer HV survive more and matched controls.
- Whether the pit HV signal is specific to well pits is still open (hollows too few).
- Sub-look and polarimetric filters add nothing on 8–12 leaf-on/leaf-off dates.

## 8. Not doable now (Track 2D)

- Hardware truth set: needs PASDA leaf-off imagery or field visit.
- Winter P05036+ stack, multi-county benchmark, Sentinel-1 cross-check, PS motion: need data not yet released or more dates.

## Reproduce

```
python nisar/code/s5_eval/_nisar_building_geoloc_9t.py --slc
python nisar/code/s5_eval/_nisar_tropo_offset_check_9t.py
python nisar/code/s5_eval/_nisar_sublook_9t.py
python nisar/code/s5_eval/_nisar_steel_pads_v2_9t.py --slc
python nisar/code/s5_eval/_nisar_pad_change_9t.py --slc --v2 --match
python nisar/code/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc --v2 --decoys 40
python nisar/code/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc --v2 --match
python nisar/code/s5_eval/_nisar_hollows_9t.py
python nisar/code/s5_eval/_nisar_gslc_stack_pad_pit_seasonal_9t.py --slc --v2 --match --pits-file nisar/derived/9t/nisar_hollows_polygons_9t.gpkg --tag hollows
```
