# Session Resume — 2026-05-07

## What we accomplished this session

### 1. Geomorphon audit & fixes
- Audited `notebooks/wellsight/_build_geomorphon_enc.py` against Jasiewicz & Stepinski (2013)
- Core algorithm was correct (line-of-sight zenith angle, 8 directions, enclosure count)
- **Fixed flatness threshold**: 1.5° → 1.0° (paper default)
- **Fixed NaN fill**: global median → nearest-neighbor via `distance_transform_edt` (prevents false enclosure near data gaps)
- Regenerated all rasters: `geomorphon_enc_{5,8,12}_{9t,mk5,mkf}_1m.tif`
- Same fix applied to `notebooks/_build_geomorphon_enc.py` (duplicate)

### 2. Pit rim polygon rework
- Archived old spoke algorithm to `notebooks/wellsight/archive/_pit_rim_polygons_spoke_v1.py`
- Rewrote `notebooks/wellsight/_pit_rim_polygons.py` with:
  - Climb-then-fall state machine for slope decay detection (same proven logic as v1)
  - LRM zero-crossing refinement (outward-only nudge when LRM confirms)
  - Per-spoke confidence scoring
  - **5-spoke circular moving average** smoothing on rim distances → circularity 0.60 → **0.90**
  - Coordinate sign fix for world-y (row increases down, y increases up)
  - SNAP_R=2 (matching v1)
- **Three polygon layers** in `data/derivatives/pit_1m_polygons.gpkg`:
  - `floor` — pit bottom (mean radius 2.07m, area 16 m²)
  - `rim` — wall-to-terrain transition (mean radius 6.08m, area 135 m²)
  - `outer` — full envelope including outer downslope (mean radius 10.19m, area 338 m²)
- Results: 852/861 polygons, **100% point containment** on all tiles, 0.98m mean depth

### 3. U-Net pit detector
- Installed PyTorch 2.7.1+cu118 (GTX 1070 Ti, compute capability 6.1)
- Built `notebooks/wellsight/_pit_unet.py`:
  - 10 input channels: LRM_5, LRM_11, TPI_05, TPI_15, openness_neg, slope, hillshade, enc_5, enc_8, enc_12
  - 4-level U-Net, 32-base filters, 7.7M parameters
  - 128x128 patches, 50/50 balanced sampling, rotation/flip augmentation
  - BCE + Dice loss, cosine annealing LR schedule
  - Trained 60 epochs on 9t+mk5, validated on mkf (held out)
  - Best model epoch 46, val_loss=0.4184
- Outputs: `pit_unet_pred_{9t,mk5,mkf}.tif`, `pit_unet_model.pt`
- Standalone U-Net recall: 85-94% but only 40-44% precision

### 4. Combined U-Net → XGBoost pipeline
- Built `notebooks/wellsight/_pit_unet_xgb_combined.py`:
  - U-Net probability map → `peak_local_max` at threshold 0.20 → 2,762 candidates
  - Extract 55 features per candidate (same as _pit_pipeline_1m.py + unet_prob)
  - 37.8% positive rate (vs 1.2% with template matching — much better signal)
  - XGB + LightGBM + HistGB ensemble, GroupKFold CV, isotonic calibration
- **Results (combined vs standalone):**
  - @0.80: **280 pits at 87.7% precision** (vs XGB-only: 95 pits at 93.6%)
  - @0.90: **87 pits at 96.7%** (vs XGB-only: 88 at 94.1%)
  - @0.50: **475 pits at 75.8%** (vs XGB-only: 366 at 67.1%)
- Outputs: `pit_combined_candidates.gpkg`, `pit_combined_metrics.txt`

### 5. Misc
- Added `.gitignore` entries for large files in `lidar_project` repo
- Confirmed `data/source_laz/westernpa/` can be moved to free space — only build scripts reference it, all derivatives already computed
- Presentation prep: discussed how XGBoost works, ROC/AUC/PR metrics, template mean vs median, geomorphon enclosure, LiDAR return characteristics for pits

## Current file locations (lidar_project)

### Active pipeline scripts (notebooks/wellsight/)
- `_build_geomorphon_enc.py` — geomorphon raster generation (FIXED)
- `_pit_pipeline_1m.py` — template + geomorphon → XGBoost (original pipeline)
- `_pit_rim_polygons.py` — three-layer rim polygon extraction (REWORKED)
- `_pit_unet.py` — U-Net training + inference
- `_pit_unet_eval.py` — U-Net standalone evaluation
- `_pit_unet_xgb_combined.py` — combined U-Net → XGBoost pipeline
- `_build_wellsight_notebook.py` — builds the morphology pipeline notebook

### Key outputs (data/derivatives/)
- `geomorphon_enc_{5,8,12}_{9t,mk5,mkf}_1m.tif` — enclosure rasters (REGENERATED)
- `pit_1m_polygons.gpkg` — three layers: floor, rim, outer (REWORKED)
- `pit_unet_model.pt` — trained U-Net weights + normalization stats
- `pit_unet_pred_{9t,mk5,mkf}.tif` — per-pixel probability maps
- `pit_combined_candidates.gpkg` — combined pipeline candidates with proba
- `pit_combined_metrics.txt` — combined pipeline performance
- `pit_1m_ensemble_metrics.txt` — original XGBoost-only performance
- `pit_1m_candidates_ensemble.gpkg` — original XGBoost candidates

### Archived
- `notebooks/wellsight/archive/_pit_rim_polygons_spoke_v1.py` — old spoke algorithm

## What's next (potential)
- Audit the U-Net's false positives — some may be real undocumented pits
- Feed combined pipeline candidates back into the rim polygon extractor
- Statewide scaling across 3DEP tiles
- Fix stale documentation (methodology.md still says "90 pits" and "THR ≈ 0.148")
- Automated pad detector to remove pad-prior dependency

---

# Session Resume — 2026-05-12 / 2026-05-13: Ramachandran 2024 replication

## What we accomplished this session

### 1. Ramachandran eval replication (TX/CO well-pads)
- Cloned `data/external/well-pad-denver-permian/` (Stanford ML Group eval repo)
- Downloaded Zenodo bundle to `data/external/ramachandran_2024/permian_denver_data/`
  - `training/well-pad_dataset.csv` (88,044 rows: 10,432 pos + 77,612 neg)
  - `deployment/permian_well_pads.csv` (194,973 polygons)
- Built `code/detectron2_shim.py` (40-line Boxes/Instances replacement — detectron2 won't install on Windows)
- Patched `eval_test.py` for cp1252 UnicodeEncodeError on fancy_grid box chars (added `encoding='utf-8'`)
- Ran `python code/eval_all.py` → reproduced Table 1 + Fig 2 successfully
- Findings: paper's published outputs are detector-only (RetinaNet); IMG_SIZE=512 in their constants, not 640

### 2. Pilot A — LiDAR bridge experiment over TX well-pads
- Built USGS 3DEP inventory for Permian bbox: `_fetch_3dep_inventory.py` → 104K tiles (7.7 TB)
- Filtered to 37K tiles intersecting Ramachandran pads: `_filter_3dep_tiles_to_well_pads.py`
- Picked Pilot A: 8 LAZ tiles, 574 MB total (NM_SouthEast UTM13N + TX_West_Central_B4/B7/B8 UTM13/14N)
- `_pilotA_build_dem_hillshade.py` → 8 DEM/hillshade/slope rasters (1m, native UTM per tile)
- `_pilotA_overlay_pads.py` → 8 PNG overlays in `data/derivatives/experiments/pilot_A/overlays/`
- `_pilotA_terrain_stats.py` → 99 pads vs 288 controls, Welch t-tests
- `_pilotA_summary_figure.py` → `pilot_A_summary.png`
- **Result**: Pads have significant LiDAR signature
  - elev_std −38% (p=0.003) — flat interiors
  - slope_std +74% (p<0.001), slope_p95 +61% (p<0.001) — sharp edges

### 3. Verifier replication (option C — in progress, paused)
- User chose: replicate just the EfficientNet-B3 verifier on NAIP imagery
- Substitution rationale: Ramachandran can't redistribute Google Earth chips (ToS); NAIP is closest CONUS-wide public substitute at ~60 cm
- Architecture: train EfficientNet-B3 on GT-bbox crops as positives + random crops from negative tiles as negatives
- Scripts written:
  - `notebooks/wellsight/_ramachandran_naip_fetch_pilot.py` — 50-chip pilot (verified visually, all OK)
  - `notebooks/wellsight/_ramachandran_naip_fetch.py` — full 88K fetch via Microsoft Planetary Computer STAC
  - `notebooks/wellsight/_ramachandran_verifier_train.py` — EfficientNet-B3, focal loss α=0.25 γ=2.0, Adam 1e-6, 300×300 input
  - `notebooks/wellsight/_ramachandran_verifier_eval.py` — picks threshold at 99% precision on valid, applies to test
- NAIP chips fetched: **87,467 / 88,044 (99.3%)** to `data/external/ramachandran_2024/naip_chips/{train,valid,test}/`
  - 577 failures (mostly API errors from PC throttling — test split is 100% complete)
  - Fetch took ~16 hours total across 3 restarts due to Planetary Computer rate limits and one wedge
- Training was started (`bp3lpviyz`) but **killed at ~40 min in (mid-epoch)** when user paused session
  - GPU was at 100%, 8 GB VRAM, fitting within 1070 Ti budget
  - No `verifier_best.pt` was saved — output buffering means we never observed an epoch boundary
  - `index.csv` (10.5 MB train/valid/test crop index) is on disk and reusable

## Where to resume
1. Re-run training: `cd C:/Users/colto/Documents/GitHub/lidar_project && python notebooks/wellsight/_ramachandran_verifier_train.py --epochs 8 --batch 48 --workers 4`
   - Wall time: ~80 min on 1070 Ti at GPU saturation
   - Consider adding `-u` flag or `flush=True` on prints so we can monitor mid-epoch
2. Run eval: `python notebooks/wellsight/_ramachandran_verifier_eval.py`
3. If results look strong, decide whether to also build the detector stage or stop at verifier

## Key project notes captured
- Microsoft Planetary Computer anonymous tier throttles hard after the first ~30K requests; wedges have happened
- Paper's `IMG_SIZE = 512` (not 640) — our chips downloaded at 512; annotation_image bboxes are in 640-coord and need scaling by 0.8
- Paper does NOT publish training code or verifier outputs in isolation; Table 1 is detector-only mAP
- 1070 Ti can handle EfficientNet-B3 at batch=48, 300×300 (uses ~8 GB VRAM)

---

# Session Resume — 2026-05-13 to 2026-05-15: Road extraction + Beck 2015 replication + reorg

## What we accomplished this session

### 1. v3 multi-channel road extraction (raster-domain)
- Built `_road_extract.py` on `mkf` with 7 channels:
  sato(±LRM_5, ±LRM_15), sato(-roughness) for flat valley roads,
  structure-tensor anisotropy of slope, asymmetric cut-fill bench,
  CHM canopy-gap (Beck-inspired), density anomaly (Beck-inspired)
- Cost-surface gap bridging via `skimage.graph.route_through_array`
  with `valid`-mask-guarded cost (kills no-data void bridging) and
  near-edge endpoint rejection
- Post-filter (`_road_postfilter.py`) drops both-endpoints-near-edge
  polylines and length>300m+straightness>0.93 lines
- mkf final result: **12,933 centerlines / 530 km / median width 4 m**.
  Largest single feature 2.6 km. Visible coverage matches hillshade
  road traces well except inside dense terraced/orchard areas
  (which the canopy_gap channel over-fires on).
- Outputs: `data/derivatives/experiments/roads/roads_mkf_clean.gpkg`,
  `road_score_mkf.tif`, `road_mask_mkf.tif`,
  `roads_overlay_mkf_clean.png`

### 2. Beck et al. 2015 replication study
- Faithful raster-domain implementation of the paper's algorithm in
  `_beck_road_replication.py`: per-canopy intensity range, support
  cleanup (3x3 + 5x5), isolation cleanup (11 px disk), density
  gate, slope-constrained Dijkstra connection routine, vectorize
- Downloaded 9t LAZ (17 tiles, 680 MB, PA_WesternPA_2019_D20,
  native EPSG:6346) and mkf LAZ (111 tiles, 5.4 GB,
  PA_Northcentral_2019_B19, native EPSG:6350 Albers — requires
  PDAL `filters.reprojection` to UTM 17N)
- Data-prep work to support Beck:
  - `_build_intensity_zscore.py` — per-LAZ-tile mean/std z-score
    (kills per-tile intensity calibration drift). 9t and mkf.
  - `_build_density_persource.py` — per-PointSourceId density,
    each pass normalized to its own median, mean-aggregated
    across passes per cell (kills flight-line nadir-edge density
    artifacts that contaminated raw ground-return count). 9t has
    4 passes (sources 637-640), mkf has 8 passes (269-276).
  - `_build_density_noverlap_9t.py` — uses USGS Overlap flag
    (no-op for 9t — all flags 0; useful template for other datasets).
- 9t Beck result: **372 centerlines / 10.04 km** (0.5 km/km²)
- mkf Beck result: **224 centerlines / 6.31 km** clustered in upper-left
  (mkf has 53.5% valid coverage; bbox extends outside project extent)

### 3. CRITICAL FINDING — Beck replication is mostly a dud on PA 2019
Cohen's d diagnostic on 9t (Beck-classified RL pixels vs everything else):
  - intensity z-score: d = -0.058  (essentially zero — intensity is
    NOT discriminating between Beck's "roads" and "not-roads")
  - density (per-pass-normalized): d = 0.354 (small)
  - CHM: d = 0.040 (zero)

Conclusion: Beck's primary signal (intensity) is doing nothing for us.
The output is dominated by (a) density anomaly + connectivity, with
horizontal striping that's residual flight-line scan-edge artifacts,
plus (b) a few real road traces.

Root cause: auto-calibration of intensity range uses density-anomaly
seed pixels — these are ALL canopy openings (roads + meadows + pads +
fields), not just roads. p25-p75 intensity of seed captures ~50% of
each canopy class, basically a pass-through. Beck did this manually
with KNOWN road samples; we didn't.

### 4. Three documented fix paths (not executed)
- **#1 Low-tail percentile** (5 min): use p5-p35 of seed intensity
  instead of p25-p75 — targets the dark-surface tail where gravel
  roads sit
- **#2 Manual sampling** (paper-faithful): pick ~5-10 road pixels
  by hand per canopy class from hillshade, set ranges from those
- **#3 Bootstrap from v3** (best recall): run v3 on 9t, sample
  intensity along v3 detections, re-run Beck with that

User paused at this decision point.

### 5. Massive reorganization (2026-05-15)
- All wellsight scripts grouped by workflow stage:
  `notebooks/wellsight/{fetch,build,pits,roads,pilotA,ramachandran,paper,runs,archive}/`
- 58 older root-level `notebooks/_*.py` scripts moved to
  `notebooks/archive/`
- Root cleanup: PDFs → `docs/papers/`, .docx → `docs/paper_versions/`,
  .pptx → `docs/presentations/`, *.png/*.jpg → `docs/figures/`, .md →
  `docs/articles/` or `docs/handoff/`, PA_LandCover/ and
  OilGasLocations_*/ → `data/external/`
- Created `STRUCTURE.md` at repo root documenting the new layout
- Updated paths in 3 paper-builder scripts and `_run_hotspots_and_mckean.py`
  (16 references rewritten)
- `.gitignore`: dropped stale root-anchor for OilGasLocations,
  added `data/external/legacy_data/`, plus catchalls for
  `data/derivatives/{roads,beck_*}/*.tif` and per-tile temp dirs
- Verified all moved/renamed scripts still work via smoke tests
- Renamed parameterized scripts (dropped `_9t` suffix):
  `_build_intensity_zscore_9t.py` → `_build_intensity_zscore.py`,
  `_build_density_persource_9t.py` → `_build_density_persource.py`

### 6. CRS verification
- All rasters (input + derived) and vectors confirmed EPSG:6346 with
  identical bounds per tile. Three 9t WhiteboxTools-built files had
  compound CRS (NAD83(2011) UTM 17N + NAVD88) — stripped the vertical
  datum so `to_epsg()` reports 6346 cleanly. No 2D processing change.

### 7. .gitignore policy
- Audited 60+ files >100 MB — all now covered by .gitignore patterns
- Saved durable user-feedback memory: any future script that may
  produce >=100 MB output gets a .gitignore rule in the same change.
  See `.claude/projects/.../memory/feedback_gitignore_large_files.md`

## Where to resume
- **Beck calibration**: User to choose path #1, #2, or #3 above.
  Likely #1 → quick check, then escalate if not enough recall.
- **mkf Beck**: same calibration issue applies; will benefit from same fix
- **v3 multi-channel**: ready to run on 9t (just `python notebooks/wellsight/roads/_road_extract.py --tile 9t`).
  Will surface a more complete-but-noisier road network for comparison.
- **Possibly merge v3 detections + Beck cleanup** as a hybrid approach.

## Key project notes captured
- PA 2019 D20 LiDAR has multi-pass density artifacts (4-8 passes per cell).
  Per-PointSourceId normalization helps but residual within-pass nadir-edge
  scan gradients persist. Beck's intensity attribute cannot rescue this on
  its own.
- mkf source LAZ is Conus Albers (EPSG:6350); 9t is UTM 17N (EPSG:6346).
  Build scripts handle reprojection.
- PA_Northcentral_2019_B19 doesn't cover all of mkf's UTM bbox (53% valid).
- ALL active scripts live under `notebooks/wellsight/<workflow>/`. Run
  from repo root: `python notebooks/wellsight/<workflow>/<script>.py`.
- CLAUDE.md (Claude.md on disk) at repo root is authoritative project doc.

