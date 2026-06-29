# Barlow / FINESST Data — Acquisition Manifest

**Date:** 2026-06-28
**Storage:** `J:\barlow_data\` (off-repo; 156 GB free remaining)
**Fetch tooling:** `notebooks/wellsight_v2/build/_fetch_barlow_data.py`
**Region:** McMurdo Dry Valleys, Antarctica (Taylor / Wright / Victoria-Barwick / Denton Hills)

The datasets behind Barlow's MDV stream-boundary dissertation and our FINESST
"couple geomorphic change to physical/climate drivers" expansion. Status below.

## ✅ Downloaded

| Dataset | Path | Size | Source / access |
|---|---|---|---|
| **MDV airborne lidar 2014-15 — bare-earth 1 m DEMs** (NCALM) | `mdv_lidar/be_dem_1m/` (Taylor_Valley, North, Garwood, Beacon, Capes) | ~26 GB | OpenTopography S3 `opentopography.s3.sdsc.edu` bucket `raster/MDV_2014/MDV_2014_be/`, **anonymous** (API key not needed for bulk S3). Dataset `OTLAS.112016.3294.1`, DOI 10.5069/G9D50JX3. CRS **EPSG:3294** (Transantarctic Mtns proj) |
| **REMA v2.0 mosaic, 2 m** (satellite DEM epoch) | `rema/2m/` (15 subtiles) | ~11 GB | AWS Open Data `pgc-opendata-dems`, anonymous; MDV supertiles 17_34/17_35/18_34/18_35 |
| **REMA v2.0 mosaic, 10 m** (overview) | `rema/10m/` (4 tiles) | ~1 GB | same |
| **MCM-LTER met — Lake Bonney (BOYM)** daily/hourly/15-min | `lter_climate/` | ~48 MB | EDI `knb-lter-mcm.7003.25` (air T, RH, shortwave radiation, wind; rev auto-resolved) |
| **MCM-LTER stream discharge — all 21 MDV gauges (daily)** | `lter_streams/` (21 CSVs) | ~3 MB | EDI 9100-series (`9102`–`9129`), daily summarized discharge/temp/conductivity. Streams: Canada, Commonwealth, Lost Seal, Von Guerard, Onyx@Vanda, Onyx-Lower-Wright, Miers, Adams, Huey, Lawson, Green, Delta, Crescent, House, Bohner, Priscu, Santa Fe, Aiken, Andersen, Harnish(×2) |
| **ERA5 reanalysis — MDV monthly drivers 1993-2024** | `era5/era5_mdv_monthly_1993-2024.nc` | 0.7 MB | Copernicus CDS `reanalysis-era5-single-levels-monthly-means`, box `[-77,160,-78.5,164.5]`, 384 months, 9 vars: t2m, skt, ssrd, ssr, tp, smlt, sd, u10, v10 (melt/energy-balance drivers) |
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
