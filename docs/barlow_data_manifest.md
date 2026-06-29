# Barlow / FINESST Data — Acquisition Manifest

**Date:** 2026-06-28
**Storage:** `J:\barlow_data\` (off-repo; 156 GB free remaining)
**Fetch tooling:** `notebooks/wellsight_v2/build/_fetch_barlow_data.py`
**Region:** McMurdo Dry Valleys, Antarctica (Taylor / Wright / Victoria-Barwick / Denton Hills)

The datasets behind Barlow's MDV stream-boundary dissertation and our FINESST
"couple geomorphic change to physical/climate drivers" expansion. Status below.

## The real target = the DISSERTATION (not the 2022 paper)

The actual parent work is **Barlow, M.C. (2026)**, *"A Comprehensive Spatial Analysis of
Stream Boundary and Geomorphological Change Detection: McMurdo Dry Valleys, Antarctica"*,
PhD dissertation, Univ. Houston (chair Glennie). See `docs/articles/barlow_dissertation_explained.md`
and `docs/finesst/FINESST_Barlow_Expansion_Concept.pdf`. The 2022 *Remote Sensing* paper
(doi:10.3390/rs14010234) is only **Chapter 4** (Taylor Valley U-Net proof-of-concept). The
dissertation spans **4 valleys × 3 epochs (2001 lidar, 2014 lidar, 2021-23 REMA)** + DoD
change detection (ICP, Laplacian/NMAD, LOD95). Data requirements (from the FINESST brief):

| Requirement | Our source | Status |
|---|---|---|
| MDV lidar **2014** (DEM + intensity) | `MDV_2014` DEM (all valleys) + Taylor PC | ✅ |
| MDV lidar **2001** (2 m DEMs, the 2nd change epoch) | **USGS ScienceBase** (NASA ATM; NOT OpenTopography) parent `5d0d1d81...`, 18 sites 2.5 GB; same EPSG:3294 + overlapping extent as 2014 | ✅ |
| **REMA 2021-23** (satellite epoch) | PGC `pgc-opendata-dems` v2.0 mosaic (have) — may want time-stamped strips for true 2021-23 epoch | ⚠️ mosaic only |
| Derived per epoch: elev, slope, **aspect, curvature**, intensity, **MFD** flow-accum | `_build_barlow_inputs.py` builds elev/slope/intensity + **D8** flow-accum | ⚙️ add aspect+curvature; she used **MFD** not D8 |
| Labels: Barlow's 217 + multi-valley polygons | author-gated → MCM-LTER stream channels `6007` (aux/QC) | ✅ stand-in |
| LTER met / discharge | both | ✅ |
| **Glacier mass-balance**, **permafrost/active-layer** | LTER `2006` (glacier mass change, 7 glaciers) + `4020-4024` (continuous soil T/EC/VWC, active layer) | ✅ |
| Reanalysis ERA5 / AMPS (attribution) | both | ✅ |
| ArcticDEM, WorldView/Maxar | PGC | optional |

## ✅ Downloaded

| Dataset | Path | Size | Source / access |
|---|---|---|---|
| **MDV airborne lidar 2014-15 — bare-earth 1 m DEMs** (NCALM) | `mdv_lidar/be_dem_1m/` (Taylor_Valley, North, Garwood, Beacon, Capes) | ~26 GB | OpenTopography S3 `opentopography.s3.sdsc.edu` bucket `raster/MDV_2014/MDV_2014_be/`, **anonymous** (API key not needed for bulk S3). Dataset `OTLAS.112016.3294.1`, DOI 10.5069/G9D50JX3. CRS **EPSG:3294** (Transantarctic Mtns proj) |
| **MDV lidar 2014-15 — Taylor Valley point cloud** (for intensity) | `mdv_lidar/pc/Taylor_Valley/` (944 .laz) | ~9.6 GB | OpenTopography `pc-bulk/MDV_2014/Taylor_adj47`, anonymous. Carries the **intensity** returns Barlow uses (DEM does not). `--lidar --pc --regions Taylor_Valley` |
| **MDV lidar 2001 — ATM 2 m DEMs (all 18 sites)** | `mdv_lidar_2001/` (18 sites, .zip tiff/tfw) | 2.5 GB | USGS ScienceBase parent `5d0d1d81e4b0941bde52a1a1` (NASA ATM Dec-2001, UB-processed). EPSG:3294, 2 m. The **2nd change-detection epoch**; overlaps & co-registers with 2014. `--atm2001` |
| **MCM-LTER GIS — stream-channel / watershed / glacier shapefiles** (label source) | `labels/gis/` (12 stream channels + watersheds + glaciers) | 0.4 MB | EDI `knb-lter-mcm.6007`; public stand-in for Barlow's non-public 217 label tiles. Plus relict-channel locations `knb-lter-mcm.26` |
| **REMA v2.0 mosaic, 2 m** (satellite DEM epoch) | `rema/2m/` (15 subtiles) | ~11 GB | AWS Open Data `pgc-opendata-dems`, anonymous; MDV supertiles 17_34/17_35/18_34/18_35 |
| **REMA v2.0 mosaic, 10 m** (overview) | `rema/10m/` (4 tiles) | ~1 GB | same |
| **MCM-LTER met — Lake Bonney (BOYM)** daily/hourly/15-min | `lter_climate/` | ~48 MB | EDI `knb-lter-mcm.7003.25` (air T, RH, shortwave radiation, wind; rev auto-resolved) |
| **MCM-LTER stream discharge — all 21 MDV gauges (daily)** | `lter_streams/` (21 CSVs) | ~3 MB | EDI 9100-series (`9102`–`9129`), daily summarized discharge/temp/conductivity. Streams: Canada, Commonwealth, Lost Seal, Von Guerard, Onyx@Vanda, Onyx-Lower-Wright, Miers, Adams, Huey, Lawson, Green, Delta, Crescent, House, Bohner, Priscu, Santa Fe, Aiken, Andersen, Harnish(×2) |
| **ERA5 reanalysis — MDV monthly drivers 1993-2024** | `era5/era5_mdv_monthly_1993-2024.nc` | 0.7 MB | Copernicus CDS `reanalysis-era5-single-levels-monthly-means`, box `[-77,160,-78.5,164.5]`, 384 months, 9 vars: t2m, skt, ssrd, ssr, tp, smlt, sd, u10, v10 (melt/energy-balance drivers) |
| **LTER glacier mass balance** | `lter_glacier/` (7 glaciers) | 0.6 MB | EDI `knb-lter-mcm.2006` snow/ice/total mass change (Taylor, Canada, Commonwealth, Howard, Adams, Hugh, Sues) — melt/ablation driver |
| **LTER soil / active-layer** | `lter_soil/` (5 stations × T/EC/VWC) | 285 MB | EDI `knb-lter-mcm.4020-4024` continuous soil temperature, EC, volumetric water content — permafrost/active-layer driver |
| **AMPS d3 — MDV high-res drivers (sample)** | `amps/mdv/` (10 timesteps, 2026-05-27→31) | 1.4 MB | GDEX THREDDS **NCSS** subset of dataset `d473002` (AMPS WRF24, d3 = **2.67 km** Ross Sea grid covering MDV, ~10× finer than ERA5). 8 vars: 2m T, 10m wind u/v, surface pressure, sensible+latent heat flux, albedo, geopotential. **Anonymous.** f000 analysis, 00+12 UTC |

\* the fetcher now **auto-resolves the newest EDI revision** (`_latest_rev`) — the earlier
0-entities failure was a hardcoded stale revision (`9128.11` vs current `9128.3`), not a wrong package.
\* an older Fryxell (FRLM) daily-met file may still sit in `lter_streams/` from a prior pass; it is met, not discharge — move if tidying.

## ⛔ Not downloaded — optional / lower priority

| Dataset | Why blocked | How to get it |
|---|---|---|
| **MDV airborne lidar 2001** (earlier NCALM epoch) | The 2014-15 epoch is in (above); a separate ~2001 survey would give a second lidar epoch for change detection if one exists on OT | Search OpenTopography catalog for an MDV 2001 collection; add region/bucket to `fetch_opentopo`. |
| **ERA5 hourly** (melt-season detail) | Monthly is in (above); hourly is larger and only needed for sub-monthly melt dynamics | `_fetch_barlow_data.py --era5 --era5-hourly` (per-year files; accept hourly dataset licence first). |
| **AMPS — full MDV time series** | only a 5-day sample pulled so far; scope (period + cadence) is a user decision | `--amps --amps-start YYYYMMDD --amps-end YYYYMMDD [--amps-fhours 000,012]`. WRF24 era only (Oct 2017→present); earlier eras (WRF30/45/60, MM5) need separate path/var wiring. ~140 KB per timestep via NCSS. |
| **WorldView/Maxar imagery, geology maps** | PGC imagery is NGA-licensed (restricted); geology via GNS/USGS | For label QC only; lower priority. |

## Reproduce everything from scratch

Two committed scripts regenerate the entire dataset + derivatives. All sources are
free/public; the only manual prerequisites are the ERA5 CDS token + a one-time licence
click (everything else is anonymous). Run from the repo root:

```bash
F=notebooks/wellsight_v2/build/_fetch_barlow_data.py
# --- elevation epochs ---
python $F --atm2001                                   # 2001 ATM 2m DEMs (ScienceBase, 2.5 GB)
python $F --lidar                                     # 2014 bare-earth 1m DEMs (26 GB)
python $F --lidar --pc --regions Taylor_Valley        # 2014 Taylor point cloud / intensity (9.6 GB)
python $F --rema                                      # REMA 2m+10m mosaic (12 GB)
# --- labels + drivers (small CSV/zip; auto newest EDI rev; skips existing) ---
python $F --lter                                      # met, 21 discharge gauges, glacier, soil, LABELS
#   then unzip labels/mcmlter-gis-watershed_shapefiles-*.zip -> labels/gis/
# --- climate reanalysis ---
python $F --setup-cds <YOUR_CDS_TOKEN>                # writes ~/.cdsapirc (one time)
#   accept ERA5 licence once at cds.climate.copernicus.eu, then:
python $F --era5                                      # ERA5 monthly drivers 1993-2024
python $F --amps --amps-start 20260527 --amps-end 20260531   # AMPS d3 MDV sample (NCSS)
# --- derived U-Net input rasters (no download; needs DEM+PC above) ---
B=notebooks/wellsight_v2/build/_build_barlow_inputs.py
python $B --bbox 26000 37000 33000 44000             # validated pilot stack
# python $B                                           # full Taylor Valley (~11 GB/raster)
```

**Not script-reproducible (genuinely unavailable):** Barlow's own 217 hand-drawn label
tiles (author-only — LTER `6007` channels are the public stand-in). **Optional / parked:**
REMA time-stamped strips (potentially tens of GB), ArcticDEM, WorldView/Maxar (restricted).
Add `--list` to any fetch to preview without downloading.

## Notes
- REMA 2 m matches the airborne-lidar scale needed for Barlow's cm-to-m change detection;
  the lidar–REMA pair is the core validation once the OpenTopography lidar is in hand.
- Everything downloaded is **free/public**; the blocked items are credential- or
  catalog-ID-gated, not paywalled.
- To extend: `python notebooks/wellsight_v2/build/_fetch_barlow_data.py --rema --lter --lidar --era5`
  (add `--list` to preview). REMA tiles are calibrated to the MDV in the script.
- **AMPS via NCSS:** the full GRIB files are ~240 MB (whole Antarctica, polar-stereographic
  that eccodes/cfgrib mis-georeferences); GDEX THREDDS **NetcdfSubset** returns the MDV box
  at ~140 KB/timestep with correct coords — always subset, never pull whole files. d3 (2.67 km)
  covers the MDV (domain spans −85→−68 S, all lon). Needs `cfgrib`+`eccodes` only if reading
  raw GRIB; NCSS output is plain netCDF (xarray-readable).
- **ERA5 / CDS:** auth is `~/.cdsapirc` (single Personal Access Token on the new CDS);
  set it with `--setup-cds <TOKEN>`. The dataset licence must be accepted once on the CDS
  website. The new CDS returns a **.zip of two stepType-split netCDFs** (avgua T00 /
  avgad T06); `_postprocess_era5` extracts, snaps the month axis, and merges to one clean file.
- **CRS note:** MDV lidar is **EPSG:3294**, REMA is polar-stereographic (EPSG:3031) —
  reproject to a common grid before any DEM-of-difference change detection.
