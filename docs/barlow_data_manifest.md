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
| **REMA v2.0 mosaic, 2 m** (satellite DEM epoch) | `rema/2m/` (15 subtiles) | ~11 GB | AWS Open Data `pgc-opendata-dems`, anonymous; MDV supertiles 17_34/17_35/18_34/18_35 |
| **REMA v2.0 mosaic, 10 m** (overview) | `rema/10m/` (4 tiles) | ~1 GB | same |
| **MCM-LTER met — Lake Bonney (BOYM)** daily/hourly/15-min | `lter_climate/` | ~196 MB | EDI `knb-lter-mcm.7003.22` (air T, RH, shortwave radiation, wind) |
| **MCM-LTER met — Lake Fryxell (FRLM)** daily | `lter_streams/`* | ~4 MB | EDI (daily AIRT/RADN/RH/SOILT/SURF/WSPD) |

\* the FRLM daily files landed in `lter_streams/` from an earlier package-ID pass; they are
met, not discharge — move if tidying.

## ⛔ Not downloaded — needs credentials or a corrected ID

| Dataset | Why blocked | How to get it |
|---|---|---|
| **MDV airborne lidar 2001 & 2014** (NCALM) — Barlow's training base + lidar change epochs | OpenTopography S3 (`opentopography.s3.sdsc.edu /raster/MDV_2014`) blocks anonymous listing | Free **OpenTopography API key** → portal bulk download, or `aws s3 --no-sign-request` if their bucket policy allows. ~tens of GB. |
| **MCM-LTER stream discharge** (17 gauges, melt-season flow) | EDI package id `9128` guess returned 0 entities | Find correct package on the [MCM data catalog](https://mcm.lternet.edu/data); add to `LTER_PACKAGES` and re-run `--lter`. |
| **ERA5 reanalysis** (spatial gap-fill for drivers) | Copernicus CDS needs an account + `~/.cdsapirc` | Register at CDS, install `cdsapi`, then a small request script for the MDV box. |
| **AMPS** (Antarctic Mesoscale Prediction System) | NCAR archive | Optional alternative/complement to ERA5. |
| **WorldView/Maxar imagery, geology maps** | PGC imagery is NGA-licensed (restricted); geology via GNS/USGS | For label QC only; lower priority. |

## Notes
- REMA 2 m matches the airborne-lidar scale needed for Barlow's cm-to-m change detection;
  the lidar–REMA pair is the core validation once the OpenTopography lidar is in hand.
- Everything downloaded is **free/public**; the blocked items are credential- or
  catalog-ID-gated, not paywalled.
- To extend: `python notebooks/wellsight_v2/build/_fetch_barlow_data.py --rema --lter`
  (add `--list` to preview). REMA tiles are calibrated to the MDV in the script.
