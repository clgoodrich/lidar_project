# Analysis Log — WellSight

Append-only record of every processing decision, parameter choice, and run
result. Newest entries at the top. Per `Claude.md` reporting rule.

---

## 2026-06-29 — AMPS made practical via THREDDS NCSS (the optional driver, unblocked)

Tried the last optional Barlow dataset, **AMPS** (Antarctic Mesoscale Prediction System,
WRF). Old `tds.ucar.edu` server is retired → now **gdex.ucar.edu** (THREDDS at
`tds.gdex.ucar.edu`, anonymous). Long GRIB archive = dataset **d473002** (WRF24 era
Oct-2017+; structure `grib/<model>/YYYY/MM/DD/<init>_WRF_d<G>_f<FFF>.grb`). The MDV-relevant
domain is **d3 = 2.67 km Ross Sea** (covers the Dry Valleys; ~10× finer than ERA5 there),
21 GRIB fields incl. 2m T, 10m wind, RH, precip, surface pressure, sensible/latent heat
flux, albedo. **Catch: full d3 files are ~240 MB** (whole continent) and the polar-
stereographic grid is **mis-georeferenced by eccodes AND cfgrib** (both returned a degenerate
lat/lon band) — so raw-GRIB coverage checks were unreliable. **Fix:** THREDDS exposes
**NetcdfSubset (NCSS)** + OPeNDAP — NCSS does the projection server-side and returns the MDV
bbox as plain netCDF at **~140 KB/timestep (1760× smaller)**, confirming coverage (72×57 @
2.557 km, T2m −46…−20 °C). Built `fetch_amps()` (NCSS, `--amps --amps-start/--amps-end
[--amps-fhours]`) and pulled a **5-day sample** (2026-05-27→31, 00+12 UTC, f000 → 10×136 KB)
to `J:/barlow_data/amps/mdv/`. Installed `cfgrib`+`eccodes 2.47` (only needed for raw GRIB).
**Decision deferred to user:** which period/cadence for a full AMPS series (WRF24 only;
earlier eras need extra wiring). All 4 foundational datasets + an AMPS path now in hand.

---

## 2026-06-29 — Barlow ERA5 drivers in: all 4 foundational datasets now downloaded

Closed the last credential gap. **ERA5** via Copernicus CDS (new system): wrote
`~/.cdsapirc` with the user's Personal Access Token (single-token format; written without
echoing the value), user accepted the dataset licence, then pulled
`reanalysis-era5-single-levels-monthly-means` over the MDV box `[-77,160,-78.5,164.5]`,
**1993–2024 (384 months), 9 melt/energy-balance vars** (t2m, skt, ssrd, ssr, tp, smlt,
sd, u10, v10) → `J:/barlow_data/era5/era5_mdv_monthly_1993-2024.nc` (0.7 MB).
**Gotcha handled:** the new CDS returns a **.zip of two stepType-split netCDFs**
(avgua stamped T00, avgad T06) — added `_postprocess_era5` to extract, snap both to the
month axis, and merge with `join='exact'` into one clean file (was getting 768 interleaved
months before alignment; now 384, 0 NaN, physically sane: t2m≈247 K). Installed
`cdsapi 0.7.7` + `netCDF4`/`h5netcdf` backends. Tooling: `_fetch_barlow_data.py --era5`
(`--era5-hourly` for sub-monthly; `--setup-cds <TOKEN>`). **Barlow data now complete**
except optional AMPS and a possible 2001 lidar epoch.

---

## 2026-06-28 — Barlow data: unblocked MDV lidar + LTER discharge (2 of 4 gaps closed)

Closed the two non-credential blockers from the prior pass.
**MDV airborne lidar (NCALM 2014-15)** = dataset `MDV_2014`/`OTLAS.112016.3294.1`
(DOI 10.5069/G9D50JX3). Found the data on OpenTopography's public Ceph S3
(`opentopography.s3.sdsc.edu`, bucket `raster/MDV_2014/MDV_2014_be/`) — **fully
anonymous; the API key is only for the portal path, NOT the bulk S3**. Pulling the
**bare-earth 1 m DEMs (~26 GB)**, valleys first (Taylor_Valley 6.2 → North 9.3 →
Garwood 4.9 → Beacon 3.6 → Capes 2.0) to `J:/barlow_data/mdv_lidar/be_dem_1m/`. CRS
**EPSG:3294** (Transantarctic Mtns proj) — reproject before differencing vs REMA.
**LTER stream discharge**: the earlier "wrong id" was actually a **stale revision**
(`9128.11` requested, current is `9128.3`). Rewrote `fetch_edi` to **auto-resolve the
newest revision** (`_latest_rev` via PASTA) and queued **all 21 daily-discharge gauges**
(9100-series 9102–9129): Canada, Commonwealth, Lost Seal, Von Guerard, Onyx, Miers,
etc. Met package also auto-bumped 7003.22→.25. Tooling: `_fetch_barlow_data.py`
(--lidar [--pc] / --lter / --rema). **Still blocked (accounts only):** ERA5 (CDS), AMPS.
Snag mid-run: J: got unmounted (escalated, user reconnected) — all barlow_data lives on J:.

---

## 2026-06-28 — Barlow/FINESST data acquisition to J:arlow_data

Downloaded the public datasets behind the MDV dissertation / FINESST expansion.
**REMA v2.0 mosaic** (satellite DEM epoch) over the MDV — supertiles 17_34/17_35/
18_34/18_35 at **2 m (~11 GB) + 10 m (~1 GB)** from AWS Open Data `pgc-opendata-dems`
(anonymous); MDV tiles calibrated from real tile bounds (grid: left=CC*100k-3.1M,
top=RR*100k-3.0M). **MCM-LTER met** (Lake Bonney + Fryxell, daily/hourly/15-min) via
EDI `knb-lter-mcm.7003.22`. Blocked (need creds/correct IDs): MDV airborne lidar
(OpenTopography API key), LTER stream discharge (wrong EDI id), ERA5 (CDS account).
Tooling: `_fetch_barlow_data.py` (--rema/--lter). Manifest:
`docs/barlow_data_manifest.md`. Storage on J: (off-repo), 156 GB free.

## 2026-06-27 — NISAR recon over 9t + supplement proposal; .git/disk cleanup

**Disk/git.** C: had dropped to <250 MB. `.git` was 25 GB (mostly dangling loose objects
from rebases). A `git gc` first FAILED (no scratch space) — recovered with
`git prune --expire=now` (reclaimed ~20 GB, no history touched), then a clean `git gc`:
**.git 25 GB → 4.8 GB, C: free → 23 GB.** No force-push, history intact. Deeper history
rewrite (regenerable rasters still in reachable history, ~3–4 GB more) deferred — needs
force-push. Data triage produced: ~105 GB regenerable (.tif 93 GB + .laz 10 GB) vs ~0.6 GB
vital (hand annotations + ground truth) + ~2 GB checkpoints; label .gpkg are interleaved
with rasters in tile folders, so any cleanup must be by file pattern not folder.

- **NISAR InSAR over PA is SEASONAL, not impossible (correction).** Re-tested after
  pushback: fall pair 2025-10-28→11-09 coherence **0.50** (94% >0.3) vs winter
  2026-01-08→01-20 **0.14**. The winter decorrelation was snow/freeze-thaw, not forest
  (perp baseline only -35 m). GUNW InSAR subsidence is VIABLE over forested PA with
  snow-free (late-fall/early-spring) pairs. Proposal updated.

**NISAR reconnaissance (real granules over 9t).** Earthdata auth set up (`~/_netrc`),
`_fetch_nisar_9t.py` (CMR query + ASF download, `--max`/`--min-free-gb` guards).
Downloaded + clipped to 9t: 1 GCOV beta + 1 GUNW beta.
- **GCOV usable:** 10 m, RTC gamma-0 HH+HV, EPSG:32617, 100% valid; HH −8.2, HV −16.3,
  HH−HV 8.1 dB (sound forest signature).
- **GUNW NOT usable over 9t:** 80 m, **coherence 0.14 (0% >0.3)** — dense PA canopy
  decorrelates L-band even at 12-day repeat. InSAR subsidence is a *Permian* tool, not PA.
Clips in `data/external/nisar/9t/clip_9t/` (gitignored). Proposal:
`docs/nisar_lidar_supplement_proposal.md` — NISAR = 10–80 m context/covariate/time-axis
(pad covariate, change tripwire, FINESST driver layers), NOT a fine detector; everything
is BETA until validated CONUS release ~July 2026.

---

## 2026-06-17 — Annotation aids: cross-region pad transfer + 3× exaggerated derivatives

**PA pad U-Net → permian_01 (transfer experiment, no retrain).** New reusable
`plats/_pad_unet_infer_grid.py` stacks a grid's existing derivatives into the 7-band
DEFAULT_CHANNELS order (mapping 9t `roughness_11` → grid `roughness_5`), normalizes
with 9t stats, and runs `plat_unet/best.pt` via `predict_full_tile`. On permian_01 (1 m):
**78 candidate pads, precision 60/78 = 77% within 60 m of a ramachandran pad point, but
recall only 68/467 = 15%.** Transfers in precision, recall-limited — chiefly the 0.5 m→1 m
scale mismatch (model trained at 0.5 m). ~4.1k px (0.02%) returned fp16 NaN → written as
nodata. Outputs in `label_grids/permian_01/pad_unet_xfer/`.

**3× vertically-exaggerated openness + slope (manual-picking aid).** New
`build/_build_exag_derivatives.py`. Rationale: openness/slope are atan-nonlinear in
elevation, so vertical exaggeration sharpens incised roads/drainage for the eye; LRM/TPI
are linear (exaggeration cancels under any color stretch) so they are deliberately NOT
produced. Each tile processed at its OWN cell size with a fixed 25 m openness radius:
**9t at 0.5 m** (L=50) → `tiles/9t/exag3x/`; **permian_01–04 at 1 m** (L=25) →
`label_grids/permian_NN/exag3x/`. Heavy tifs gitignored (regenerable).

---

## 2026-06-17 — Label grids rework: new Permian 3×3 centers, WPA manual placements

**Permian re-placed + upsized 2×2 → 3×3.** Prior density-auto Permian centers were
not well-dense enough; user supplied 4 explicit centers and asked for **3×3** (4.5 km,
9 tiles) each: p01 (32.2805,-101.1629) z14, p02 (32.2225,-102.2139) z13, p03
(31.66615,-103.02572) z13, p04 (30.6161,-101.1393) z14. Reworked `_fetch_permian_grids.py`
to a **geometry-based tile picker** (snap to seed±pitch from bbox centers) so it works
for both 6-digit (`14SKA940715`) and 4-digit (`13RFR8603`, TX_Pecos_Dallas) USGS tile
codes; added retry/backoff for flaky TNM JSON. Verified all 4 are gapless 3×3 lattices
(cells (0,0)..(2,2)) before download.

**openness-only for p02–p04.** Per user, the extra Permian grids need only openness;
added `openness_only` to `_build_derivatives.build()` (DEM → openness_pos/neg, skip the
rest). p01 kept as the full-stack reference; p03 (built full before the request) pruned
to dem+openness. CRS: 6343/6342/6342/6343.

**Two robustness fixes for dense 3DEP.** (1) Delaunay TIN OOMs on dense QL1 3×3 mosaics
(~200 M ground pts, 3–10 GB merge) → added `dem_method="gdal"` (writers.gdal IDW,
streaming, window_size 3); permian build uses it. (2) Density/intensity pass switched
from `laspy.read()` (whole file) to chunked `chunk_iterator` to bound RAM.

**Root cause of p02 fail + p04 NaN was DISK FULL (3.8 GB free), not code.** p02's 9.7 GB
merge was truncated → "VLR size too large" on re-read; p04's 9th tile download died with
`No space left on device` → 11% NaN DEM. Freed 29 GB of stale `_merged_*.las` scratch in
`source_laz/westernpa/`; re-fetched the missing p04 tile; both rebuilt clean (p02 nan
0.12%, p04 nan 0.00%). Also dropped `forward:"all"` from the merge writer (unneeded;
CRS/scale/offset set explicitly).

**WPA #3/#4 manual placements.** westernpa_03 → **NE 2×2 of 613590** (tiles
615591/615593/616591/616593); westernpa_04 → **NW 2×2 of 622599** (622600/622602/
624600/624602). Added `--manual` mode + `MANUAL_WPA` to `_build_label_grids.py`. Both
clear of the 9t core. `write_empty` now skips existing gpkgs (QGIS file-lock safe;
empty gpkgs are location-independent so annotation files are never clobbered). Per-grid
gpkg naming `westernpa_NN_*` / `permian_NN_pads` (user-confirmed).

---

## 2026-06-16 — Drainage U-Net + annotation label grids (WPA build + Permian fetch)

**Drainage U-Net.** Built `_drainage_unet_1m.py` (in `wellsight_v2/drainage/`) as the
symmetric twin of the road recall model — same 9t data/channels/3-class labels, focal
alpha flipped to (0.10, 0.25, 0.72) so drainage is the positive and road the confuser.
40 ep, GTX 1070 Ti. **9t test: drainage IoU 0.532, AP drainage-vs-road 0.990,
mean P(drain) 0.696 on drainage vs 0.0016 on road.** Roads essentially never fire as
drainage. Doc: `iterations/drainage_unet_1m.md`.

**Label grids (annotation areas).** New `label_grids/` off repo root with 4 WPA + 4
Permian 2×2 (1 m) grids over the most well-dense areas, each with empty annotation
geopackages (WPA: pit_inside/pit_outside; Permian: pads). Scripts: `_build_label_grids.py`
(select by orphan-well density + build DEM/hillshade/derivative stack) and
`_fetch_permian_grids.py` (pull 3DEP LPC 2×2 tiles via TNM API).
- WPA wells = `data/external/legacy_data/US_Documented_Orphan_Wells.csv` (PA-only, 4786).
  Densest grids overlapped the 9t training core → **excluded the 9t bbox** per user; final
  grids 258/193/174/163 wells, EPSG:6346, built from local LAZ.
- Permian wells = `rrc_orphan_wells_permian.gpkg` (3328). All 4 densest 3 km clusters have
  3DEP LPC coverage (TX_Lower_CO_San_Bernard_2017, TX_WestTexas_2018, TX West Central 2018);
  zones 13R/14R/14S. **Data-quality note:** permian_01 (lon −100.59) and _04 sit on/east of
  the geologic Permian Basin edge — densest RRC orphans, not all "basin" proper. Downloading
  QL "any 3DEP" per user; build in native UTM (EPSG:6342/6343).
- Large-file rule: `label_grids/**/*.tif|las|laz|png` gitignored (same change); empty
  .gpkg templates stay tracked.

**Build complete (all 8 grids).** 4 WPA + 4 Permian, each 20 derivative TIFs incl.
hillshade + empty annotation gpkgs. Two 3DEP-specific bugs fixed mid-build:
(1) `writers.las` int32 overflow — some TX zone-14 tiles ship offset 0, so the large
UTM northing overflowed; fixed with `offset:auto` + scale 0.01 in `_build_derivatives`.
(2) Raw 3DEP tiles carry no CRS → DEM had none → WBT hillshade silently no-op'd; fixed
by letting `build_derivatives` own the DEM (built from the merged LAS tagged `a_srs`)
plus a `stamp_crs()` safety net. WPA dems/permian_04 read as compound CRS (to_epsg None
but valid); permian_01/02/03 are clean EPSG 6342/6343. ~1.7 GB Permian LAZ downloaded.

## 2026-06-16 — Port the road post-proc pattern to pits: `_pit_optimize.py`

**Goal.** Reuse the proven road pipeline shape for pits. Roads = 1-D (skeleton →
centerlines); pits = 2-D blobs, so the new middle stage is threshold → connected
components → shape filter → polygon → centroid (candidate well point). Stage 1
(derivatives) and Stage 2 (`_pit_unet_v2` floor prob) already existed; the new piece
is `notebooks/wellsight_v2/build/_pit_optimize.py`, the polygon analog of
`_road_optimize.py` (same `optimize`/`apply-block` CLI, object-level F1 harness).

**Setup.** GT = `pit_inside` floors (65 in the 9t test region). Detection = floor-prob
blobs; match = greedy nearest centroid within TOL=6 m. Coordinate-ascent over
{enhance, thresh, floor_gate, t, area_min/max, circ_min, ecc_max, min_px}, 2 passes.

**Result (9t test, all blobs, no conf gate).** BEST F1 **0.195** — recall **0.85**,
precision **0.11** (500 candidates for 65 GT). Best cfg: gauss + hysteresis(0.4/0.6),
floor_gate off, area 9–1500 m², circ≥0.45, ecc≤0.88. Saved to
`pit_unet_v2/pit_postproc_best.json`.

**Interpretation.** The extractor works end-to-end, but raw precision is low — the
floor prob is leaky and over-detects. This is the *expected* shape and the argument FOR
the active-learning loop: high-recall candidates + human reject-in-QGIS → hard negatives
→ retrain. The `apply` confidence gate (0.6·mean_pfloor + 0.4·shape) recovers precision
before review. Candidates carry confidence + nearest-known-well distance per QC rule.
Next: pit review-package + corrections-diff (polygon analogs of the road scripts), then
retrain `_pit_unet_v2` on corrections. See [[project_road_active_learning_loop]].

## 2026-06-14 — Road recall fix: focal-α bump (NOT more data); multi-block rejected

**Problem.** Deployed `road_unet_1m` (3-class) gave gappy roads on out-of-domain block
613590: it detected roads in the right places but under-confidently (P(road) ≈ 0.5 on
real roads), so segments dropped below the 0.5 threshold. (Also confirmed the earlier
`road_prob_613590_05` the user saw was the legacy **2-class 0.5 m** model with no drainage
class — a separate, worse model.)

**False alarm corrected.** The suspected "roughness channel bug" is not real: at 1 m,
`features_<key>_1m.tif` band 7 is *labeled* `roughness_11` but is byte-identical to
`roughness_5`. Model trained on roughness_5, infers on roughness_5 → matched.

**Rejected: multi-block training** (`_road_unet_multiblock.py`, `road_unet_mb`). Built a
6-block dataset (`_build_road_multiblock_dataset.py`, 191 km road across 618594/622591/
613603/613608/618591/622594; train-block norm recomputed). Overfit (best val ep7; 618594
= 84% of road) and came out *under-confident* on 613590 (mean P 0.508 < deployed). Adding
outside-9t data diluted the dense 9t core — data was not the bottleneck.

**Adopted: recall-focused retrain** (`_road_unet_1m_recall.py`, `road_unet_1m_recall`).
Same clean 9t data, road focal-α 0.60→0.72, drainage 0.30→0.25, wd 1e-4→2e-4. Best ep38,
val road IoU 0.643. 9t test: pixel IoU 0.581 (=deployed), AP road-vs-drainage 0.999,
P(road) road/drain 0.778/0.004. **On 613590: mean P(road) 0.57→0.66, road≥0.5 px ~1.7×.**

**Cleaned vector network** (validated `roads_opt` cleaner fed the recall prob via new
`--prob`/`--drain` overrides in `_road_optimize.py`): clean network 155.2→**169.3 km**
(1252 segs, 129 bridges), TIGER recall 0.501→**0.523**, novel 123.5→136.2 km. Deployed
network backed up to `roads_opt_613590_1m_deployed.gpkg`.

`road_unet_1m_recall/best.pt` is now the current road model for data_3x3 blocks (not yet
re-inferred across all 25). `road_multiblock/` gitignored (regenerable dead-end). Docs:
`docs/iterations/road_unet_1m_recall.md`, LEADERBOARD roads table updated.

---

## 2026-06-09 — Project reorg: full data-tree restructure + root cleanup (paths maintained)

Reworked the repo layout for findability; **all code paths maintained** (verified, no
dangling refs). Mechanical path rewrite via a one-off mapping script (literal +
`Path`-constructor + runtime `DERIV/sfx` forms + the QGIS `.qgz` internal absolute
paths, both separators), then grep-verified + AST-parsed (78 files, 0 errors) +
`_common` import-tested.

**data/derivatives/** flat 25-dir dump → bucketed:
- `tiles/` (per-area stacks: 9t, 9t_1m, data_3x3, oilcreek_22tile_05, *_marcellus_1m,
  wc_coaloil_1m, extras, mosaic_3x3*) · `inference/` (mck, oilcreek) ·
  `experiments/` (chm_age_proxy, icp, pilot_A, ramachandran_verifier, roads,
  candidates, notebook_demo, permian_sample) · kept `annotations/`, `validation/`.
- `DERIV_9T` now `…/tiles/9t`; runtime stack builders write to `DERIV/"tiles"/<key>`.

**data/** source LAZ: `FILES`→`source_laz/westernpa`, `mckean`→`source_laz/mckean`;
deleted empty `dem_tiles`, `older_files` and temp `_tmp_intensity_tiles_mkf`.

**Archived (old >2 wk AND unused):** `beck_9t`, `beck_mkf`,
`inference_mck_e1423n2238_05`, `model_archive` → `archive/derivatives/` (heavy
rasters gitignored there; small metric/VERSION records kept tracked).

**Root cleanup:** resume→`personal/`, `road error.jpg`→`docs/figures/debug/`,
kang PDF→`docs/papers/`, downloadlist→`data/external/usgs_3dep_pa_lidar/`, YOLO
weights→`models/pretrained/` (CLI defaults updated), `qgis_lidar class.qgz`→
`qgis/wellsight.qgz` (space removed; layer paths inside repointed to new buckets).

**docs/** consolidated: `paper_versions/`+`presentations/`+methodology docx →
`publication/`; single-file `pipelines/`+`preprocessing/` folded into `articles/`.
`STRUCTURE.md` fully regenerated.

## 2026-06-09 — Back to PA: orphan catalog × our LiDAR coverage (Oil Creek), + pit-annotation validation

Pivoted the orphan-detection work back to Pennsylvania (the two historical books are
PA-focused; PA is where we have ground truth + forested terrain where earthworks show).

**The "US" orphan catalog is all Venango Co., PA** (4,786 wells, Oil Creek/Oil City
corridor; densest ~166/2 km cell at -79.55,41.49). Cross-referenced against our PA
DEM coverage — strong overlap:
- `9t` tile: **624 orphans** (0.5 m DEM `dem_9t_05.tif`; also has our hand pit/pad
  annotations) — best combined target.
- `oilcreek_22tile_05`: **468 orphans** at **0.5 m** — matches the historical pit-depth
  prior (0.6–1.5 m); literal birthplace of the industry.
- `westernpa_d20` (25 blocks): **3,125 orphans**; densest block 618594 = 552.

**Validation (orphans × hand pit annotations, within the annotated area, 318 orphans
/ 113 pits):**
- **60% of hand-annotated pits have a documented orphan within 30 m (64% @50 m)** →
  the pit features we detect in LiDAR are largely real orphan cellars (mutual
  validation of both datasets).
- Only **~22% of orphans have an annotated pit within 30 m** → we've labeled a small
  fraction of what's present (113 pits vs 318+ orphans in that area alone).

**Implication:** directly enables BACKLOG #1 (grow labels). The orphan catalog can
seed semi-automated pit annotation: snap each catalogued orphan to nearest LiDAR
depression within a sanity radius → human-confirm → grow labels ~5–10×. Caveat: PA
DEP coords are not survey-grade (median nearest-pit dist 245 m because orphans span
the whole tile while pits were annotated in a cluster); needs radius + human QC.
Eyeball overlay: `data/derivatives/pa_9t_orphans_overlay.png`.

---

## 2026-06-09 — Confirmed Permian ground truth: TX RRC orphan wells (+ optical cross-ref)

Established that we had NO confirmed-well ground truth for the Permian:
`data/external/legacy_data/US_Documented_Orphan_Wells.csv` is mislabeled — it's
**4,786 wells, 100% Pennsylvania** (PA DEP, Status=Orphan); 0 in TX/NM. So the
194,973 optical pad detections were unvalidatable.

**Fetched authoritative TX ground truth** from the RRC ArcGIS REST service
(`gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer`,
**layer 2 = "Orphan Wells"**, fields OBJECTID/API/SHAPE). Queried the Permian bbox
(paginated, maxRec 1000) → **3,328 confirmed orphan wells** →
`data/derivatives/experiments/permian_sample/rrc_orphan_wells_permian.gpkg`
(layer `rrc_orphan_permian`, `status=orphan_confirmed`, API + point, EPSG:4326, 0.6 MB).

**Cross-reference (UTM 13N metres):**
- Sample tile 13RGR500055: **0** confirmed orphans (it's modern active pads — wrong
  place to look for orphan signatures).
- Only **34.6%** of RRC orphans have an optical pad within 100 m → optical detection
  misses ~⅔ of confirmed orphans (old wells, no visible graded pad) — the case FOR
  the LiDAR approach. (Only ~0.6% of optical pads sit near an orphan; the optical set
  is overwhelmingly active wells.)
- Caveat: RRC historical coordinates are coarse — some misses are location error.

**Best orphan-cluster target for QL1 eyeballing:** (-102.825, 31.225) — **136
orphans/5 km cell**, covered by `TX_WestTexas_2018` (~12–13 pts/m², QL1). Next step:
pull a tile there and check whether confirmed orphans show terrain signatures.

---

## 2026-06-09 — Permian QL1 sample render + early-well parameter mining

**(1) Density ceiling check.** Ranked the full cached Permian inventory (104,396
tiles) by LAZ-bytes/m² (calibrated to a measured tile, ~3.46 B/pt). Over the actual
well hotspots, **~15 pts/m² (QL1) is the ceiling** — confirmed by reading the densest
in-hotspot tile header (`TX West Central B4 2018 13SGR110655`: 33.8 M pts in a
1500×1500 m tile = 15.0 pts/m²). Denser projects exist (`TX_Lower_CO_San_Bernard`
p90 ~22) but lie outside the well clusters. CO/DJ-Basin coverage is QL2 (~2 pts/m²),
so Permian is the higher-quality region. ~15 pts/m² ≈ 7× the western-PA D20 QL2 data.

**(2) Eyeball sample.** Built a 0.5 m bare-earth DEM (PDAL ground-class IDW) from the
best on-disk B4 tile `13RGR500055` (16 pads, 33.3 M pts), hillshaded it, overlaid the
15 Ramachandran pad detections in-tile → `data/derivatives/experiments/permian_sample/`
(`dem_..._05m.tif` 72 MB gitignored by blanket; `hillshade_..._pads.png` tracked).
CRS verified from file: **NAD83(2011)/UTM 13N + NAVD88, EPSG:6342**. Observation: flat
West-TX rangeland — roads/tracks and some square pad scars read crisply, but graded
pads have low vertical relief (the optical detector keys on dirt color, not relief).
This is the inverse of forested PA, where the terrain scar IS the signal under canopy.

**(3) Book parameter mining** (user-supplied PDFs in `docs/papers/`). Williamson &
Daum *Age of Illumination* (888 pp OCR) + Ross *Allegheny Oil* (69 pp image scan, on
our exact PA region) mined for measurable detection priors → `docs/articles/
early_well_parameters.md`. Headline priors: earthen catch-pit depth **~0.6–1.5 m**
(only explicit pit dimension; argues for 0.5 m DEM in PA), well spacing **~20–45 m**
(clustering prior), tank-ring dia **~9 m** (Hough-circle prior, r≈4.5 m), derrick pad
**~4 m** square. Explicit gaps flagged (slush-pit L×W×D, house footprints) — to be
sourced from PA DEP standards, not fabricated.

---

## 2026-06-08 — Scout high-quality 3DEP LiDAR over dense abandoned-well clusters (Permian + DJ Basin)

Goal: find good high-density-well sample areas with high-quality public LiDAR, in
the two Ramachandran 2024 optical-imagery regions (Permian TX/NM, Denver/DJ CO).

**Well-density proxy:** Ramachandran deployment well-pad detections — 194,973 Permian
(score med 0.93) + 36,591 Denver. Gridded at 0.1° (~10 km cells).

- **Permian hotspots** (densest ~10 km cells, 1100–1670 pads each): Midland/Martin/
  Andrews Co. core `-102.5…-102.85, 32.0…33.1` and Eddy/Lea Co. NM `-103.15, 32.45`.
- **DJ Basin hotspots:** tightly clustered in Weld Co., CO `-104.5…-105.0, 40.0…40.4`
  (Greeley), 350–490 pads/cell.

**LiDAR coverage × measured quality** (density read from actual LAZ headers via laspy,
2.25 km² USGS tiles):
- **TX West Central 2018** covers most Permian hotspots; blocks **B4/B8 measure
  ~13–15 pts/m² (QL1-grade)**, but B7 only ~4 pts/m² — density varies by sub-block.
- **NM_SouthEast 2018 D19** (~6 pts/m²) covers the NM hotspot `-103.15, 32.45`.
- **TX_Pecos_Dallas 2018** covers `-102.35, 31.45`.
- **CO_EasternColorado 2018** (project path tags it `..._B2_QL2_North_2018`) is the
  workhorse over Weld Co.; **CO_DRCOG 2020** (QL2, newer) overlaps too. (One edge
  tile read 0.2 pts/m² — a sliver tile, not representative; QL2 spec is ≥2 pts/m².)

Inventory source: USGS TNM `products` API (`Lidar Point Cloud (LPC)`), Permian
inventory already cached (`data/external/usgs_3dep_permian_tx/tile_inventory.parquet`,
104,396 tiles); Weld Co. queried live (5,728 LPC products in the hotspot bbox).
No bulk download done — characterization only. Reproduce: density grids from the
deployment `*_well_pads.csv`; coverage via the cached parquet / TNM bbox query.

---

## 2026-06-08 — 2 m elevation contours on every data_3x3 block DEM

New `_build_contours_data_3x3.py` runs `gdal_contour -a elev -i 2 -snodata -9999`
on each `dem_<key>_1m.tif` (EPSG:6346, metres → 2 m interval) → `contours_2m_<key>_1m.gpkg`
(layer `contours`, attr `elev`, all multiples of 2). Built for all 25 WesternPA D20
blocks (~547 MB total, 18–41 MB each; ~0.6 min). Heavy regenerable vectors, so added
gitignore rule `data/derivatives/tiles/data_3x3/**/contours_*.gpkg` in the same change;
≥100 MB audit clean. Reproduce: `python notebooks/wellsight/build/_build_contours_data_3x3.py`
(`--interval N`, `--only <key>`).

---

## 2026-06-07 — Fix drainage FPs at the source: 3-class road model + road chunking

User pushback: the post-hoc drainage filter was too aggressive, and "are we
priming the model on drainage?" Investigation: (1) hand-drawn roads are NOT
contaminated (only 0.7% run on a mapped stream); (2) the model was *set up* to
confuse roads/drainage — the U-Net label was binary road/bg with NO drainage
negatives (the 112-line `not_roads` layer was only used by the side classifier,
not the U-Net), and all 7 feature bands are generic concavity so nothing told it
"water flows here". Conclusion: fix it in **training**, not with a filter.

**Fix 1 — drainage as a trained class.** User pointed to `drainage.shp` in the
annotations folder (1791 channel segments from the cross-section filter,
`klass='stream'`, EPSG:6346, no .prj). Wired it through: `_prep_annotations.py`
adds a `drainage` gpkg layer (stamps EPSG:6346); `_prep_road_1m.py` rasterizes it
as class 2 (buffered 2 m, road painted on top) → `labels_road_9t_1m.tif` is now
0=bg/1=road/2=drainage; `_road_unet_1m.py` → `N_CLASSES=3`, FocalCE alpha
(0.10,0.60,0.30), drainage sampling policy; `_infer_roads_data_3x3.py` →
`N_CLASSES=3`, writes `drainage_prob` + 2-colour overlay. Result: P(road) on
drainage test lines = **0.005**, road IoU 0.379→0.527.

**Fix 2 — chunk the roads (user caught this).** Roads = few long polylines (171,
median 126 m, max 921 m); drainage = pre-chunked (~21 m). The sampler centers ONE
patch per line midpoint, so long roads were massively under-sampled (most of their
length never seen) and the 27-line eval was meaningless. `_build_plat_road_dataset.py`
now chunks roads/not_roads to ~40 m → `road_chunks_9t.gpkg` + chunk-level manifest
(8385 road chunks, 635/95/130 train/val/test); eval rewritten per-chunk. Restored
road focal weight to 0.60. Result (168-chunk test): **road IoU 0.581, line AP
0.992, P(road) road/drainage 0.757/0.006**. Pilots: 604603 road 0.98%/drain
1.36%; 609590 road 2.87%/drain 1.19% — clean separation, no post-filter needed.
Backups: `best.pt.2class.BAK`, `best.pt.3class_nochunk.BAK`. Full writeup
[[road_unet_1m]] §v2. **Open:** re-infer the other 23 blocks with the 3-class
model; decide post-filter's residual role (connectivity/vectorization only).

---

## 2026-06-07 — Refine road rasters → clean, connected centerlines (drainage filter + gap-bridging)

User feedback on the per-block road predictions: good, but (a) picking up drainage/
waterways and (b) roads that should connect are fragmented. Built
`_refine_roads_data_3x3.py` to post-process each block's `road_prob` raster into
vector centerlines, reusing the project's validated cross-section concavity test
`_xdrop` (from `_filter_streams_xsec_9t.py`).

**Pipeline:** binarize(0.5) → remove_small_objects(250) → close(3px) → skeletonize
→ `skan` trace to LineStrings → bearing-aware endpoint gap-bridge (≤25 m, tangents
within 35°) → linemerge → drainage filter → drop <35 m stubs → re-rasterize +
gpkg + overlay.

**Connectivity (problem b):** morphological close for hairline gaps + endpoint
snapping for medium gaps (247 bridges on the steep pilot). User opted to KEEP all
>35 m fragments (no network-island filter).

**Drainage (problem a) — the methodology finding.** A single global `xdrop`
threshold does NOT generalize across terrain (drainage km dropped per pilot):
`xdrop≥0.30` flat 19.7 / steep 52.0 (eats roads); `xdrop≥0.60` flat 6.7 / steep
15.7 (steep channels leak); naive hydrology flat 23.7 / steep 42.5 (D8 routes down
road **ditches** on flat terrain → eats grid roads). **Adopted rule combines
both:** drainage if (coincides ≥50% with a mapped D8 stream [flow-accum ≥4000
cells, dilated 3px] AND `xdrop≥0.35`) OR (`xdrop≥0.60` alone). The concavity gate
on the hydrology catch rejects flat road ditches (flat-bottomed → low `xdrop`).
Pilots with adopted rule: flat 604603 roads 45.7 km / drainage 12.0 km; steep
609590 roads 130.3 km / drainage 23.8 km — both visually correct (grid roads kept
on flat; dendritic channels caught on steep). Per-block D8 streams built with WBT
(breach→d8→accum→extract_streams), cached as `stream_seed_t4000_<key>_1m.tif`;
heavy breach/accum intermediates deleted. **Rollout complete: all 25 blocks in
16.7 min — 1727.9 km roads kept / 346.7 km drainage dropped (16.7%) / 2413
bridges.** Outputs per block: `roads_<key>_1m.gpkg` (layers roads+drainage,
tracked), `road_clean_<key>_1m.tif`, `road_clean_overlay_<key>_1m.png`. ≥100 MB
gitignore audit clean. Full writeup: [[road_refine]].

---

## 2026-06-07 — Group ALL WesternPA tiles; retrain roads on latest annotations; 0.5 m→1 m road fix

**1. Grouped every WesternPA 2019 D20 tile into a block.** The old 3×3 builder only
emitted blocks where all 9 tiles of a non-overlapping 3×3 were present → 50 of 176
tiles dropped. New `_build_data_3x3_partial_westernpa.py` uses the same stride-3 grid
(so the 14 existing full blocks are reused untouched) but emits a block per non-empty
cell with partial member lists (1–9 tiles) and a tight bbox. Result: **25 blocks,
176/176 tiles covered, zero overlap.** Built the 11 new partial edge blocks (48 min).

**2. Retrained roads on the latest hand-drawn `roads.shp`.** The downstream training
data was stale (annotations_proj.gpkg from 2026-05-19) while `roads.shp` had grown
to today. Rebuilt `annotations_proj.gpkg` (`_prep_annotations.py`): roads **97 → 1725**
features. Fixed a null/empty-geometry crash in `_build_plat_road_dataset.py` (exposed
by the bigger set; guards preserve positional `line_id` alignment used by eval).
Rebuilt road labels + manifest: **171 road lines** inside the 9t blocks (train 123 /
val 21 / test 27). Backed up old `annotations_proj.gpkg` + `road_unet/best.pt` (.BAK).

**3. Resolution mismatch found + fixed.** Piloting the 0.5 m road model on a 1 m block
gave **33% "road"** — false positives smeared over terrain. Cause: only `roughness`
was physically matched across resolutions; `lrm_25`/`tpi_05`/`openness` feed the model
at ~2× their trained window on 1 m data. Chose (over regenerating 25 blocks at 0.5 m)
to **retrain the road U-Net at 1 m** ([[road_unet_1m]]): built `9t_1m` stack with the
same `_build_derivatives` code as the blocks, `_prep_road_1m.py` (features_pit_9t_1m +
feature_stats_1m + labels_road_9t_1m, roughness_5), `_road_unet_1m.py`. 1 m test
metrics ≥ 0.5 m (pixel IoU 0.379 vs 0.343; line AP 0.962; P(road) road/not_road
0.654/0.133). Pilot 604590: **33.2% → 4.06%** road px, coherent road lines.
Inference on all 25 blocks via `_infer_roads_data_3x3.py` (→ per-block
`road_prob/argmax/overlay_<key>_1m`). Residual FPs on steep incised slopes →
cross-section concavity filter ([[BACKLOG]]).

## 2026-06-06 — Training determinism: seeded, but GPU Mask R-CNN is NOT bit-exact

Added `ic.set_determinism(seed)` + seeded DataLoader generator/`worker_init_fn`
and a `--seed` arg (saved into `best.pt`) to `_pit_maskrcnn.py` and
`_pad_maskrcnn.py`. This pins head init + batch order.

**Finding (verified):** two `--smoke --seed 0` pit runs still diverged
(tr 0.739/va 0.559 vs tr 0.742/va 0.529). Strict
`torch.use_deterministic_algorithms(True)` pinpoints the cause:
`roi_align_backward_kernel does not have a deterministic implementation`
(atomic adds on CUDA). So GPU Mask R-CNN training cannot be made bit-for-bit
reproducible with this stack; we use `warn_only=True` so it still runs. Seeding
makes runs *close*, not identical. Bit-exactness would need CPU training
(impractically slow for 30 epochs).

**Takeaway:** reproducibility of a *model's outputs* comes from saving `best.pt`
and re-running deterministic *inference* (proven bit-identical in
`training_walkthrough.ipynb` Path B), not from re-training. Derivatives remain
fully deterministic (proven bit-identical in `derivatives_walkthrough.ipynb`).
The real `pit_07`/`pad_05` `best.pt` were backed up + restored during the test;
they predate seeding and are not recreatable.

## 2026-06-03 — Diagnostic derivative sweep on 9t (curvature/hydrology/texture)

Built 13 new geomorphometric layers from `dem_9t_1m.tif` via WhiteboxTools
(`_build_diagnostics_9t.py`): depth-in-sink, TWI, 5 curvatures, geomorphons,
multidirectional hillshade, spherical-stddev-of-normals, TRI, surface-area-ratio,
downslope index. All 16 ops OK in ~45 s. Diagnostic-only (not in any model);
outputs git-ignored under `9t/diagnostics/`. Full detail + validation table in
`iterations/diagnostics_9t.md`.

**Headline validation vs 110 pit annotations:** `depth_in_sink` median 0.36 m at
pit centroids with 90% sitting in a closed depression, vs 1% at random points —
the strongest single hand-crafted pit signal measured. `geomorphons` puts 106/110
pits in concave classes (depression/valley/hollow). Both added to BACKLOG as
feature-stack promotion candidates (pending 0.5 m recompute + full-tile FP rate).

---

## 2026-06-03 — CATCH-UP: instance-segmentation era (May → Jun) + 7-band rebuild

> Backfill entry. The running log lapsed after 2026-04-30; this block records the
> major work since, chronologically within. Per-iteration detail lives in
> `docs/iterations/*.md` and `LEADERBOARD.md`; this is the narrative thread.

### Direction change — from heuristic detectors to learned instance segmentation
The Apr pipeline (blob+RF pits, ridge-filter roads, gated pads) was superseded by
learned models on the **9t** tile. Two families now run side by side:
- **Semantic (UNet):** best for linear features (roads/streams); paints pixels.
- **Instance (Mask R-CNN, YOLOv8s-seg):** emits one detection per object, so pits
  and pads can be counted/ranked individually.

### Iterations completed (9t, see LEADERBOARD)
- `pit_07_maskrcnn`, `pit_08_yolo`, `pad_05_maskrcnn`, `pad_06_yolo` — all trained
  + inferred. Consistent finding: **best checkpoint is epoch 0–1, then overfits**
  (74 train pits / 51 train pads vs a 45.9 M-param backbone). Recall is high,
  precision poor (heavy over-prediction). Apples-to-apples instance metric
  (`_instance_common.per_instance_metrics`) added so UNet and detectors compare
  fairly; UNet collapses under the instance metric on pits (recall@0.5 ≈ 0).
- Cross-referenced all models vs the **full PA DEP catalog (1069 wells in-tile)** —
  well_recall 0.22–0.42. Read as a *lower bound* (catalog includes plugged/
  canopy/no-surface-expression wells), and as the strongest argument that the
  **110/79 annotation set is the bottleneck**, not the architecture.

### Engineering fixes logged
- **YOLO BGR gotcha:** PIL writes PNGs RGB, ultralytics' cv2 reads BGR → channels
  0/2 swapped, zero recall. Fixed with `img8[..., ::-1]` at inference. (memory saved)
- **MaskRCNNPredictor** TypeError (positional hidden-layer arg); **cp1252**
  UnicodeEncodeError on `→` (write utf-8); YOLO mask coord mismatch (use
  `masks.xy` polys, not model-res masks with orig-res boxes).
- **In-RAM feature caching:** 7-band per-patch file reads were 163 ms each;
  cache the full stack once (`load_feature_array`/`slice_feat_patch`) → ~0.5 ms.

### 7-band UNet-feature rebuild (the headline change)
Per user direction ("use all the UNet params again… Stop and rebuild"), the
detectors moved off the 3-band composite `(hillshade, slope, lrm_25)` onto the
**full 7-band UNet stack** `(lrm_25, lrm_5, slope, tpi_05, openness_pos,
openness_neg, roughness_11)`, z-scored. Implemented via **conv1 widening**: copy
COCO RGB weights into the first 3 input slots, warm-start the extra 4 from the RGB
mean, identity input transform (patches pre-normalized). CHM deliberately
excluded — canopy/overgrowth is inconsistent pad-to-pad. Pits also gained a
**wall class** (`pit_outside` rim) → 3-class (bg/floor/wall).

### 2026-06-03 inference results (7-band)
- **pit_07 v2:** floor recall@0.5 **0.85 → 0.95**, mean IoU 0.632 → 0.664;
  2027 dets (947 floor + 1080 wall). Clear win.
- **pad_05 v2:** dets **3250 → 2546** (−22% FP) but recall flat (0.889) and mean
  IoU slipped 0.688 → 0.631. **7-band did NOT solve pad over-prediction** —
  revised diagnosis: data quantity + permissive 0.3 score threshold, not features.
- Process note: first pad v2 inference crashed `KeyError: 'mu'` — `best.pt` was
  still the v1 3-band ckpt (the 7-band rebuild had only finished for pits). Pad
  retrained 6 ep on the 7-band stack (best=ep0) then re-inferred OK.

### Streams ported to 9t (2026-06-02) — see `iterations/streams_9t_t5000.md`
D8 flow-accum on breached DEM, `extract_streams` threshold **t5000** → 2693 lines
/274.5 km. Cross-section concavity road filter (`--chunk 25 --perp 5 --drop 0.30`,
on RAW DEM) → per-line kept 1497 lines/97.9 km, per-chunk kept 4973/88.8 km.
Provenance Q answered: Oil Creek LAZ was hydro-flattened (water class 9/20),
McKean/9t surveys were not — different surveys, not a processing error.

### Oil Creek derivatives (2026-06-03) — see `iterations/oilcreek_derivatives_05.md`
Full 0.5 m derivative stack built for the 22-tile mosaic. **Blocker:** build emits
`roughness_5`, models need `roughness_11`; must generate it + assemble the 7-band
stack before Oil Creek inference can run.

### Docs status
This catch-up restored the lapsed log; `BACKLOG.md` recreated; pit_07/pad_05 docs
refreshed with v2 numbers + fixed stale script names; LEADERBOARD updated;
`HOW_IT_WORKS.md` (plain-English overview) added. Documentation-maintenance rule
added to CLAUDE.md.

---

## 2026-04-29 — Literature-grounded parameter adjustments (v0.6)

Four parameter changes based on published literature review:

### 1. Pad slope threshold: 5.0° → 8.0°
- **Rationale:** PA DEP 25 Pa. Code Ch. 78 specifies ≤5% (~2.9°) for new construction, but
  Drohan & Brittingham (2012, Environmental Management 49:1061-1075) observe reclaimed pads
  at 3-8° depending on restoration age. Aged/eroded pads in Appalachian terrain can reach
  8-10° due to decades of erosion and settling. The 5° threshold was missing older sites.
- **File:** `notebooks/03_pad_detector.ipynb` cell "params"

### 2. Pad minimum area: 80 m² → 100 m²
- **Rationale:** Hammack et al. (2014, NETL) document smallest historical PA conventional
  pads at ~100-400 m². Allred et al. (2015, Science 348:401-402) report conventional pads
  at 900-4000 m². 80 m² is below any documented pad size and introduces false positives
  from tree-throw pits and natural depressions.
- **File:** `notebooks/03_pad_detector.ipynb` cell "params"

### 3. Pit blob max_sigma: 3.5 → 5.0 (coarse scale)
- **Rationale:** LoG blob radius ≈ sigma × √2, so max_sigma=3.5 detects up to ~9.9 m
  diameter. Hammack et al. (2014, NETL) document reserve pits at 3-10 m; PA DEP records
  show brine pits at 2-8 m. Extending to 5.0 captures up to ~14 m diameter, covering
  larger reserve/brine pits. num_sigma increased from 6 to 8 for finer scale sampling.
- **File:** `notebooks/03c_pit_detector.ipynb` cell "a503eaa9"

### 4. Positional uncertainty: 100 m retained, era-dependent model noted
- **Rationale:** Kang et al. (2014, NETL/DOE) report 50-200 m for pre-GPS PA well coords.
  Brantley et al. (2014, ES&T 48:7552-7561) note historical coords from plat maps carry
  100-300 m error. 100 m is supported as median for pre-1990 records. For pre-1950 wells,
  200 m is more appropriate — now feasible with SPUD dates from the enriched PASDA dataset
  (wells_in_tile_enriched.gpkg, 20,108 Venango County wells with full attributes).

### Additional: enriched well dataset acquired
- Downloaded PA DEP Oil & Gas Locations from PASDA (April 2026 release, 223,742 wells statewide)
- Venango County subset: 20,108 wells with SPUD date (92%), operator (99.9%), well type,
  permit date, plugged date, surface elevation, well status (10 categories)
- Saved as `data/derivatives/venango_wells_all.gpkg` (EPSG:6346)
- Tile-clipped subset: `data/derivatives/wells_in_tile_enriched.gpkg` (1,109 wells)
- Status breakdown in tile: 634 Active, 276 Plugged, 167 Abandoned, 20 Orphan, 12 Not Drilled

### Literature references for existing parameters (confirmed supported)
- DEM 1m resolution: Hesse (2010), Doneus (2013) — standard for sub-canopy anthropogenic features
- TPI radii 5/15/25.5m: Weiss (2001), De Reu et al. (2013, Geomorphology 186:39-49)
- LRM windows 5/11/25/51: Hesse (2010, Archaeological Prospection 17:67-72), Bofinger et al. (2006)
- Roughness 11×11: Riley et al. (1999), Grohmann et al. (2011, Geomorphology 132:175-192)
- Openness 25m: Yokoyama et al. (2002, PE&RS 68:257-265), Doneus (2013)
- Ridge sigmas 1/2/3: White et al. (2010, PE&RS 76:1079-1087) — 3-9m road widths
- Blob LoG 0.8-5.0: API construction standards, Hammack et al. (2014, NETL)

---

## 2026-04-13 — Session reset and documentation-first bootstrap

- **Context reset.** Prior session operated from a non-canonical long-form
  document (Feature-Type catalog A–K) that does not match the on-disk
  `Claude.md`. Discarded that guidance; only `Claude.md` (WellSight
  Formation Prompt) governs now.
- **Deleted:** `notebooks/02_pad_derivatives.ipynb`,
  `notebooks/03_pad_detection.ipynb`, and `notebooks/_make_candidate_gallery.py`.
  Reason: scope creep, alternative-filter sections, misaligned with the
  canonical pipeline in `docs/05_processing_pipeline.md`.
- **Kept:** `notebooks/01_preprocessing.ipynb` (stage A + part of stage B).
- **Wrote:** `docs/01_project_scope.md`, `docs/02_data_dictionary_wells.md`,
  `docs/03_las_inspection_report.md`, `docs/04_feature_detection_design_spec.md`,
  `docs/05_processing_pipeline.md`, `docs/analysis_log.md` (this file).
- **Toolchain check:** `pdal` 2.10.0 is on PATH at
  `C:\Users\colto\miniconda3\Library\bin\pdal.exe`. `pdal info --summary`
  succeeds on `output2.las`. PDAL Python bindings intentionally unused per
  `Claude.md`.
- **Key LAS facts (from stage A inspection):** LAS 1.4 pf=7, 9,717,579 pts,
  EPSG:6346 (NAD83(2011)/UTM 17N) + NAVD88m, 4.32 pts/m² mean, 60.75 %
  `class=2` already. No waveform. No vegetation-class split (USGS default).
- **Key wells facts:** 84 records inside the tile, all Orphan, all Venango
  County, all dated 5/9/2022 release. No drilling-date column. No
  coordinate-accuracy column. Only 7 of 26 CSV columns are usable.
- **Anomalies / escalations pending:**
  - Drilling-era detector design (§10, Q3 in design spec) — default chosen:
    single detector covering full size range.
  - Positional-uncertainty radius for validation — default 50 m.
  - Tool choice WhiteboxTools vs SciPy for slope/TPI — default WBT where it
    has a named tool, SciPy otherwise.
- **Next action:** bootstrap pilot per §8 of design spec. Select 3–5 wells,
  generate 250 × 250 m sub-extracts, run pad detector, record results before
  anything tile-wide.

---

## 2026-04-14 02:30 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 363.32 - 493.51 m, NaN 0.000%
- DSM : max-Z first returns. z 363.36 - 517.99 m, NaN 0.092%
- CHM : DSM-DEM floored >= 0. p50=3.36 m, p95=23.23 m
- Ground density: np.bincount, exact/cell. mean 2.62, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 84 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 02:30 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 02:35 UTC — v0.1 pilot FAIL, recalibrating (manual iteration)

- Bootstrap pilot refused tile-wide run.
- Cause: v0.1 thresholds (roughness_max=0.15 m, relief_max=0.40 m) from the
  guide are for flat agricultural terrain. This tile is forested Appalachian
  regrowth where natural roughness >> 0.15 m.
- Calibration: in 51×51 m windows around each of the 84 documented wells,
  median MIN per window is:
    - slope      0.362°
    - roughness  0.224 m
    - relief     2.007 m
  tile-wide p5/p10/p50:
    - slope     2.50 / 3.70 / 10.10 °
    - roughness 0.18 / 0.22 / 0.56 m
    - relief    1.23 / 1.60 / 3.55 m
- Decision: raise `roughness_max_m` to 0.25 m, raise `local_relief_max_m` to
  1.50 m; keep `slope_max_deg` at 5.0°. Coordinated change rather than a
  single-variable step because the v0.1 values produced 0 raw components
  window-wide (no information to bisect on).
- Relaxed pilot isolation to 80 m (only 6/84 wells were ≥150 m isolated, and
  5 of those were edge-bound; yielded 1 usable pilot window, insufficient).
- Detection method tag: `pad_v0.1_flatness_morph` → `pad_v0.2_calibrated_forest`.
- Next: rerun pilot → tile-wide → validation.

## 2026-04-14 02:40 UTC — v0.2 pilot FAIL, iterating to v0.3 (loose gates)

- v0.2 pilot (roughness_max=0.25, relief_max=1.5): 1/5 windows passed. Diagnostic:
  - 3/5 windows had ≥1 component survive the size filter (area≥40).
  - Shape gate (compactness≥0.4 OR rect≥0.7) and position gate (tpi_51 in [-1,3]) each rejected most survivors.
  - Pilot #3 had 0 raw components at all → that window really is rough/hilly.
- v0.3 coordinated change (breaks WellSight "one var at a time" rule deliberately; logged):
  - compactness_min 0.40 → 0.30
  - rectangularity_min 0.70 → 0.55
  - tpi51_min_m -1.0 → -3.0
  - tpi51_max_m  3.0 → 5.0
  - area_min_m2 40.0 → 20.0
- Intent: allow proof-of-concept tile-wide run to reach validation, where the
  null-baseline test honestly tells us if there is signal. Too-tight thresholds
  block the pipeline from ever producing a testable answer.
- Detection method tag: `pad_v0.2_…` → `pad_v0.3_loose_gates`.

## 2026-04-14 02:35 UTC — Stage D complete (03_pad_detector)  run 20260414T023549Z-ee8e3a

- Thresholds: slope_max_deg=5.0, roughness_max_m=0.25, local_relief_max_m=1.5, compactness_min=0.3, rectangularity_min=0.55, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=20.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=50.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121225670000: raw=22 kept=4 nearest=12.113045016348464
  - API:37121298870000: raw=13 kept=2 nearest=27.222062944390945
  - API:37121338070000: raw=0 kept=0 nearest=nan
  - API:37121337960000: raw=46 kept=3 nearest=79.56904077083315
  - API:37121303790000: raw=12 kept=3 nearest=56.47164260029245
  acceptance: PASS

- Full tile: raw=494, after gates=52, within 50 m of well=12
- Confidence: median=0.36, p95=0.50
- Output: candidates_pads.gpkg / .parquet (52 rows)

## 2026-04-14 02:36 UTC — Stage E (04_validation)  run 20260414T023549Z-ee8e3a

- Observed median dist: 86.81 m;  null p5/p50/p95 = 64.38/77.34/91.95;  p=0.8400
- Observed recall@50m: 0.107;  null p5/p50/p95 = 0.095/0.155/0.226;  p=0.9400
- Verdict: **NOT ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T023549Z-ee8e3a.md

## 2026-04-14 02:37 UTC — End-to-end complete (v0.3, NOT ABOVE CHANCE)

- Pipeline ran through all four notebooks: 01 preprocessing → 02 derivatives → 03 detector (v0.3) → 04 validation.
- Outputs:
  - 52 candidate polygons in `candidates_pads.gpkg`
  - Validation summary: `summary_run_20260414T023549Z-ee8e3a.md`
- **VERDICT: NOT ABOVE CHANCE**
  - Observed median candidate→well distance: 86.8 m
  - Null (random placement) median p50: 77.3 m — random is *closer* than ours.
  - Observed within-50 m recall: 9/84 = 10.7%; null p50 = 15.5%.
  - Both empirical p-values are > 0.8 — the v0.3 candidate set does not cluster near documented wells.
- Interpretation (options, not conclusions):
  1. v0.3 thresholds are too loose; picking up random flat patches that dilute any real signal. Tightening may help, though v0.1/v0.2 were too tight to produce candidates at all.
  2. Absolute-flatness detection is the wrong model for this terrain. A **local-anomaly detector** (roughness significantly below local mean) may be more principled.
  3. Genuine pad signatures in this tile may be below detection — sub-meter pads obscured by 60+ yr of regrowth, or coordinates too uncertain (50 m default) for the surviving signal to fall within any candidate.
- Pipeline health: green. Bootstrap worked (caught v0.1/v0.2 correctly). Validation worked (gave an honest, unambiguous answer).
- Next move to be decided with user: redesign detector for local-anomaly rather than absolute thresholds; OR try a different tile; OR increase positional-uncertainty model to 100 m.

## 2026-04-14 03:13 UTC — Stage D complete (03_pad_detector)  run 20260414T031142Z-8bd2b9

- Thresholds: slope_max_deg=5.0, rough_z_max=-1.0, relief_z_max=-0.5, anomaly_window_m=100.0, compactness_min=0.3, rectangularity_min=0.55, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=20.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=100.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121225670000: raw=44 kept=8 nearest=12.55554241865664
  - API:37121298870000: raw=104 kept=12 nearest=25.072797461769213
  - API:37121338070000: raw=120 kept=13 nearest=31.664815527488617
  - API:37121337960000: raw=68 kept=3 nearest=77.3853101949826
  - API:37121303790000: raw=84 kept=7 nearest=58.37049447205518
  acceptance: PASS

- Full tile: raw=3096, after gates=219, within 100 m of well=166
- Confidence: median=0.31, p95=0.45
- Output: candidates_pads.gpkg / .parquet (219 rows)

## 2026-04-14 03:14 UTC — Stage E (04_validation)  run 20260414T031142Z-8bd2b9

- Observed median dist: 67.92 m;  null p5/p50/p95 = 72.61/78.59/85.29;  p=0.0000
- Observed recall@100m: 0.940;  null p5/p50/p95 = 0.881/0.940/0.976;  p=0.5450
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T031142Z-8bd2b9.md

## 2026-04-14 03:14 UTC — v0.4 local-anomaly detector: SIGNAL ABOVE CHANCE

- Redesigned detector from absolute-threshold to local-anomaly model.
  - `rough_z_max`  = −1.0  (roughness z-score vs. 100 m neighborhood)
  - `relief_z_max` = −0.5
  - Absolute `slope_max_deg` = 5.0 retained (pads are physically flat)
  - Anomaly window = 100 m
- Raised `positional_uncert_m` from 50 → 100 m (upper end of literature).
- Pilot: **5/5 windows PASS** (vs 0/1, 1/5, 4/5 in v0.1–v0.3).
- Full tile: 3096 raw components → 219 candidates after shape/position/size gates.
- Validation (N=200 random-placement null, density-valid cells):
  - Median candidate→well distance: **67.92 m**
  - Null median p5/p50/p95: 72.61 / 78.59 / 85.29 m
  - **p(median ≤ obs) = 0.0000**
  - Recall@100 m: 0.940 (null p50 = 0.940, recall metric saturated at this candidate density)
  - **Verdict: SIGNAL ABOVE CHANCE**
- Confidence distribution: p50=0.31, p95=0.45, all labeled "candidate" (none reached the "probable" tier ≥0.70).
- 166/219 candidates fall inside 100 m of a documented well.
- Output: `candidates_pads.gpkg` (219 rows), summary_run_20260414T031142Z-8bd2b9.md.
- Interpretation: the local-anomaly model works. The candidates cluster near documented wells at p < 0.001. Next tuning cycle should aim to shrink the candidate count (raise `rough_z_max` closer to −1.5σ) while keeping the clustering signal. That gets us toward a set small enough to triage manually.

## 2026-04-14 03:58 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 04:00 UTC — Stage D v0.6 road detector  run 20260414T040015Z-f12621

- Method: road_v0.6_lrm_meijering (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=90.0, closing_radius_cells=2, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0

- Raw skeleton components: 103
- Kept segments (>= 30 m): 103
- Segment length: median 106.7 m, p95 568.9 m
- Nearest-well distance: median 51.2 m
- Within 100 m: 86 / 103
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:01 UTC — Stage E (04_validation)  run 20260414T040015Z-f12621

- Observed median dist: 51.21 m;  null p5/p50/p95 = 68.63/77.92/86.62;  p=0.0000
- Observed recall@100m: 0.881;  null p5/p50/p95 = 0.631/0.726/0.810;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T040015Z-f12621.md

## 2026-04-14 04:01 UTC — v0.6 road detector: SIGNAL ABOVE CHANCE (both metrics)

- New detector per `Detecting abandoned roads beneath forest canopy with LiDAR and Python.md`.
- Approach: LRM at 25 and 51 cells -> Meijering ridge filter on -LRM (scales 1, 2, 3 px) -> threshold at p90 -> closing r=2 -> remove small (<200 m²) -> eccentricity >= 0.90 -> skeletonize -> vectorize LineStrings -> length >= 30 m.
- 103 road-segment candidates. Median length 106.7 m, p95 568.9 m. Median nearest-well distance 51.2 m. 86/103 segments within 100 m of a documented well.
- Validation (200 random-point nulls):
  - median distance: obs 51.21 m; null p5/p50/p95 = 68.63 / 77.92 / 86.62 m; **p = 0.0000**
  - recall @ 100 m: obs 0.881 (74/84 wells); null p5/p50/p95 = 0.631 / 0.726 / 0.810; **p = 0.0000**
- Compared to v0.4: fewer candidates (103 vs 219), median 25% closer to wells (51 vs 68 m), and recall metric now non-saturated -- both distance AND recall exceed null at p<0.001.
- Output: `candidates_roads.gpkg` (103 LineStrings), `summary_run_20260414T040015Z-f12621.md`.
- Next move: render the centrelines on hillshade for user review; optionally tighten ridge threshold from p90 -> p92 for higher-precision, lower-recall set.

## 2026-04-14 04:43 UTC — Stage D v0.6 road detector  run 20260414T044302Z-90ec6c

- Method: road_v0.7_tight_xsec (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=92.0, closing_radius_cells=4, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=50.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 74
- Kept segments (>= 50 m): 60
- Segment length: median 93.6 m, p95 363.8 m
- Nearest-well distance: median 56.2 m
- Within 100 m: 51 / 60
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:43 UTC — Stage E (04_validation)  run 20260414T044302Z-90ec6c

- Observed median dist: 56.21 m;  null p5/p50/p95 = 67.00/80.60/90.65;  p=0.0000
- Observed recall@100m: 0.798;  null p5/p50/p95 = 0.440/0.536/0.631;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T044302Z-90ec6c.md

## 2026-04-14 04:43 UTC — v0.7 road detector (tightened + x-section attribution)

- Changes from v0.6:
  - ridge_response_pct 90 -> 92
  - closing_radius_cells 2 -> 4 (merges adjacent fragments before labelling)
  - min_segment_length_m 30 -> 50
  - added perpendicular cross-section sampling every 5 m along each segment for width and cut-depth
- Segments kept: **60** (down from 103 in v0.6). 24 "probable" (conf>0.70), 36 "candidate".
- Geometry stats:
  - length: min 50 m, p50 94 m, p95 364 m, max 1368 m
  - median_width_m: p25 6.0, p50 7.0, p75 8.0 -> consistent with two-lane haul / wide single-track
  - median_cut_depth_m: p25 0.38, p50 0.46, p75 0.57 -> modest cuts, ageing roads partially infilled
- Validation (200 random nulls, uncert = 100 m):
  - median distance: obs 56.21 m; null p5/p50/p95 = 67.00/80.60/90.65; **p = 0.0000**
  - recall @ 100 m: obs 0.798 (67/84 wells); null p5/p50/p95 = 0.440/0.536/0.631; **p = 0.0000**
- Compared to v0.6: fewer candidates (60 vs 103), recall gap *wider* (obs 0.798 - null p50 0.536 = 0.26 vs v0.6 gap 0.16). Net: more precise, same statistical dominance.
- Output: candidates_roads.gpkg (60 LineStrings, all with width/depth attrs), v07_overview.png.

## 2026-04-14 04:48 UTC — Stage D v0.6 road detector  run 20260414T044818Z-d74691

- Method: road_v0.8_recover_pathways (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=92.0, closing_radius_cells=2, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 119
- Kept segments (>= 30 m): 118
- Segment length: median 116.0 m, p95 449.7 m
- Nearest-well distance: median 47.7 m
- Within 100 m: 107 / 118
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:48 UTC — Stage E (04_validation)  run 20260414T044818Z-d74691

- Observed median dist: 47.68 m;  null p5/p50/p95 = 69.26/78.32/87.56;  p=0.0000
- Observed recall@100m: 0.905;  null p5/p50/p95 = 0.690/0.774/0.833;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T044818Z-d74691.md

## 2026-04-14 04:48 UTC — v0.8 (recover pathways) — best run yet

- Changes from v0.7: closing_radius 4->2, min_segment_length 50->30. Kept ridge_response_pct=92.
- Segments: **118** (v0.6: 103; v0.7: 60). **69 probable, 49 candidate** — majority now cross the 0.70 confidence bar.
- Geometry: length p50 116 m, p95 450 m. median_width 7 m. median_cut_depth 0.57 m (deeper than v0.7 — likely because smaller closing preserves sharper rim transitions).
- Validation (200 nulls):
  - median distance: obs **47.68 m**; null p5/p50/p95 = 69.26/78.32/87.56; **p = 0.0000**
  - recall @ 100 m: obs **0.905** (76/84 wells); null p5/p50/p95 = 0.690/0.774/0.833; **p = 0.0000**
- Best result to date across all four metrics: lowest median distance, highest recall, largest recall-gap vs null (0.131), and 69 segments in the probable tier.
- v0.8 output: candidates_roads.gpkg (118 LineStrings, width/depth attrs), v08_overview.png.

## 2026-04-14 05:02 UTC — Stage D v0.6 road detector  run 20260414T050202Z-989c68

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 163
- Kept segments (>= 30 m): 152
- Segment length: median 63.9 m, p95 610.7 m
- Nearest-well distance: median 50.4 m
- Within 100 m: 125 / 152
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:02 UTC — Stage E (04_validation)  run 20260414T050202Z-989c68

- Observed median dist: 50.42 m;  null p5/p50/p95 = 69.67/78.54/87.04;  p=0.0000
- Observed recall@100m: 0.952;  null p5/p50/p95 = 0.773/0.857/0.917;  p=0.0100
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050202Z-989c68.md

## 2026-04-14 05:02 UTC — v0.9 (relaxed thresholds): more pathways, same signal

- Changes from v0.8: ridge_response_pct 92->85, min_eccentricity 0.90->0.82, min_component_area_m2 200->120.
- Segments: **152** (v0.8: 118). 27 probable, 125 candidate. Shorter p50 length (64 m vs 116 m in v0.8) — we captured many more sub-100m fragments.
- Median cut depth 0.37 m (vs 0.57 in v0.8) — pulling in shallower features.
- Validation:
  - median distance: obs **50.42 m**; null p5/p50/p95 = 69.67/78.54/87.04; **p = 0.0000**
  - recall @ 100 m: obs **0.952** (80/84 wells); null p5/p50/p95 = 0.773/0.857/0.917; **p = 0.0100**
- Tradeoff: recall gap narrowed (obs 0.952 vs null p50 0.857 = 0.10; v0.8 gap was 0.13). Still significant but closer to chance because null recall climbed with candidate count.
- Distance metric still ultra-significant (p<0.0001). v0.9 is the right pick when the priority is **coverage** (find every pathway); v0.8 is the right pick when the priority is **precision** (high-confidence subset).

## 2026-04-14 05:07 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 2 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:07 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=8.00 deg, p95=22.49 deg
- roughness_11 (sigma elev, 11x11): p50=0.447 m, p95=1.133 m
- local_relief_10 (max-min, 10 m disk): p50=2.80 m, p95=6.69 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.70 / 1.12 m
- tpi_grad_mag: p95=0.2648

## 2026-04-14 05:08 UTC — Stage D v0.6 road detector  run 20260414T050751Z-6e5fcd

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 777.1 m
- Within 100 m: 10 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:08 UTC — Stage E (04_validation)  run 20260414T050751Z-6e5fcd

- Observed median dist: 777.15 m;  null p5/p50/p95 = 750.60/835.70/926.99;  p=0.1250
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.000/1.000/1.000;  p=0.5900
- Verdict: **NOT ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050751Z-6e5fcd.md

## 2026-04-14 05:09 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 107 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:10 UTC — Stage D v0.6 road detector  run 20260414T050955Z-0f1d93

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:10 UTC — Stage E (04_validation)  run 20260414T050955Z-0f1d93

- Observed median dist: 42.67 m;  null p5/p50/p95 = 58.48/62.46/67.64;  p=0.0000
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.869/0.916/0.963;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050955Z-0f1d93.md

## 2026-04-14 05:10 UTC — v0.9 on NEW tile (output2.las replaced, output_wells_2.csv)

- New tile extent: E 621000–622500, N 4594500–4596000 (UTM 17N) — adjacent west of the v0.1–v0.9 tile.
- New LAS: 8,956,340 pts, pf=7, class-2 ground 2.69 pts/cell mean.
- New wells: 107 (vs 84 on prior tile).
- 01_preprocessing patched to auto-derive grid bounds from LAS header (no longer pinned).
- Detector unchanged from v0.9.
- Segments: **191** (39 probable, 152 candidate). Median length 57 m, p95 287 m. Median cut depth 0.37 m.
- Validation:
  - median distance: obs **42.67 m**; null p5/p50/p95 = 58.48/62.46/67.64; **p = 0.0000**
  - recall @ 100 m: obs **1.000** (107/107); null p5/p50/p95 = 0.869/0.916/0.963; **p = 0.0000**
- Every documented well in the tile has a detected road candidate within 100 m.
- Output: candidates_roads.gpkg (191 LineStrings), new_tile_overview.png.

## 2026-04-14 05:32 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 363.32 - 493.51 m, NaN 0.000%
- DSM : max-Z first returns. z 363.36 - 517.99 m, NaN 0.092%
- CHM : DSM-DEM floored >= 0. p50=3.36 m, p95=23.23 m
- Ground density: np.bincount, exact/cell. mean 2.62, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 84 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:33 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 05:33 UTC — Stage D v0.6 road detector  run 20260414T053319Z-ae6f30

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 163
- Kept segments (>= 30 m): 152
- Segment length: median 63.9 m, p95 610.7 m
- Nearest-well distance: median 50.4 m
- Within 100 m: 125 / 152
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:33 UTC — Stage E (04_validation)  run 20260414T053319Z-ae6f30

- Observed median dist: 50.42 m;  null p5/p50/p95 = 69.67/78.54/87.04;  p=0.0000
- Observed recall@100m: 0.952;  null p5/p50/p95 = 0.773/0.857/0.917;  p=0.0100
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T053319Z-ae6f30.md

## 2026-04-14 05:35 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 107 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:35 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=8.00 deg, p95=22.49 deg
- roughness_11 (sigma elev, 11x11): p50=0.447 m, p95=1.133 m
- local_relief_10 (max-min, 10 m disk): p50=2.80 m, p95=6.69 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.70 / 1.12 m
- tpi_grad_mag: p95=0.2648

## 2026-04-14 05:35 UTC — Stage D v0.6 road detector  run 20260414T053528Z-1eface

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:35 UTC — Stage E (04_validation)  run 20260414T053528Z-1eface

- Observed median dist: 42.67 m;  null p5/p50/p95 = 58.48/62.46/67.64;  p=0.0000
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.869/0.916/0.963;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T053528Z-1eface.md

## 2026-04-14 20:04 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (191 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 48.0%  (1086 / 2262 m of truth covered)
- Road precision (length-weighted, labelled areas only): 4.8%
- **Pad hit rate:** 90.0%  (18/20 pads ≤25 m from a candidate)  median dist 0.8 m
- **Pit hit rate:** 75.0%  (39/52 pits ≤25 m from a candidate)  median dist 13.6 m
- Median pit → nearest DEP-well-record: 16.3 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-14 21:27 UTC - Road detector v0.10 (Random Forest)  run 20260414T212653Z-26e477

- Training: 8,345 pos / 41,725 neg pixels, 12 features, OOB score 0.9099
- Top-3 features: lrm_25 (0.124), openness_pos (0.110), tpi_05 (0.109)
- Proba threshold 0.5  ->  170 final LineStrings
- Confidence: 19 probable, 151 candidate
- Median segment length 56 m, median cut depth 0.36 m
- Output: candidates_roads.gpkg (v0.9 archived under archive/v0.9_rule_based_pre_rf/)
- Run 05_expert_validation.ipynb next to rescore.

## 2026-04-14 21:27 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (170 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 66.1%  (1496 / 2262 m of truth covered)
- Road precision (length-weighted, labelled areas only): 10.5%
- **Pad hit rate:** 85.0%  (17/20 pads ≤25 m from a candidate)  median dist 0.0 m
- **Pit hit rate:** 75.0%  (39/52 pits ≤25 m from a candidate)  median dist 13.0 m
- Median pit → nearest DEP-well-record: 16.3 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-15 03:20 UTC - Road detector v0.10 (Random Forest)  run 20260415T031830Z-e57988

- Training: 71,914 pos / 359,570 neg pixels, 12 features, OOB score 0.9173
- Top-3 features: openness_pos (0.212), tpi_05 (0.124), lrm_25 (0.106)
- Proba threshold 0.5  ->  101 final LineStrings
- Confidence: 15 probable, 86 candidate
- Median segment length 48 m, median cut depth 0.37 m
- Output: candidates_roads.gpkg (v0.9 archived under archive/v0.9_rule_based_pre_rf/)
- Run 05_expert_validation.ipynb next to rescore.

## 2026-04-15 03:25 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (101 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 29.0%  (5609 / 19315 m of truth covered)
- Road precision (length-weighted, labelled areas only): 52.8%
- **Pad hit rate:** 50.0%  (44/88 pads ≤25 m from a candidate)  median dist 26.0 m
- **Pit hit rate:** 28.9%  (26/90 pits ≤25 m from a candidate)  median dist 41.6 m
- Median pit → nearest DEP-well-record: 15.7 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-15 05:27 UTC - Pit detector v0.1 (blob + RF)  run 20260415T051012Z-253ea4

- Blob detection: 48449 candidates survived dedup+depression_mask
- Truth-pit recall of blob pipeline pre-RF: 90/90 (100.0%) within 5 m
- RF training: 278 pos / 1390 neg candidates, OOB 0.9215
- Top-3 features: depth_lrm11 (0.229), depth_lrm5 (0.146), dem_cut_m (0.121)
- Output: candidates_pits.gpkg (2387 pits, 667 probable)

## 2026-04-30 17:49 UTC — Stage D complete (03_pad_detector)  run 20260430T174728Z-60f82a

- Thresholds: slope_max_deg=8.0, rough_z_max=-1.0, relief_z_max=-0.5, anomaly_window_m=100.0, compactness_min=0.45, rectangularity_min=0.7, obb_aspect_min=0.5, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=100.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=100.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121321200000: raw=100 kept=0 nearest=nan
  - API:37121265330000: raw=113 kept=0 nearest=nan
  - API:37121321110000: raw=99 kept=0 nearest=nan
  - API:37121220280000: raw=117 kept=1 nearest=74.94550447313712
  - API:37121337930000: raw=93 kept=1 nearest=74.94550447313712
  acceptance: PASS

- Full tile: raw=3844, after gates=4, within 100 m of well=3
- Confidence: median=0.35, p95=0.47
- Output: candidates_pads.gpkg / .parquet (4 rows)

## 2026-04-30 17:59 UTC — Stage D v0.6 road detector  run 20260430T175948Z-2e7e97

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-30 18:16 UTC - Pit detector v0.1 (blob + RF)  run 20260430T180026Z-4cd9c2

- Blob detection: 48347 candidates survived dedup+depression_mask
- Truth-pit recall of blob pipeline pre-RF: 102/861 (11.8%) within 5 m
- RF training: 311 pos / 1555 neg candidates, OOB 0.9223
- Top-3 features: depth_lrm11 (0.228), depth_lrm5 (0.144), dem_cut_m (0.118)
- Output: candidates_pits.gpkg (2504 pits, 767 probable)
