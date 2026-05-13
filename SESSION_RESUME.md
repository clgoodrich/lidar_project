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
- Confirmed `data/files/` can be moved to free space — only build scripts reference it, all derivatives already computed
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
- `_pilotA_overlay_pads.py` → 8 PNG overlays in `data/derivatives/pilot_A/overlays/`
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
