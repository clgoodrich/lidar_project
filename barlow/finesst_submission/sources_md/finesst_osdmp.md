# Open Science and Data Management Plan

*FINESST proposal companion document (2-page limit). Anonymized section — no names or
institutional identifiers. Verify final question list against ROSES F.5 §5.1.1.3 before
submission.*

---

## 1. Data and software the project will use

All input data are free, public, and archived by their originating programs; nothing is
purchased or restricted.

| Input | Archive / host | Access |
|---|---|---|
| 2001 airborne lidar DEM (NASA ATM, 2 m) | USGS ScienceBase | public |
| 2014–15 airborne lidar DEM + point cloud (NCALM, 1 m) | OpenTopography | public |
| REMA satellite DEM v2 (2 m mosaic, 2021–23) | Polar Geospatial Center / AWS Open Data | public |
| Stream discharge (21 gauges), meteorology, glacier mass balance, soil climate | MCM-LTER via the Environmental Data Initiative (EDI) | public |
| Stream-channel outlines (labels) | EDI (`knb-lter-mcm` scope) | public |
| ERA5 reanalysis | Copernicus Climate Data Store | public (free account) |
| AMPS Antarctic mesoscale model output | NCAR GDEX | public |

One dataset in this domain is *not* public: the prior dissertation's hand-digitized
training tiles, held by their author. If shared, they will be used under the author's
terms and **will not be redistributed**; any project products derived with them will be
released in forms that do not reproduce the tiles themselves. If not shared, the project
digitizes its own training set — which, unlike the original, **will be published** (§2).

All processing software is open source: Python (numpy/scipy, rasterio, geopandas,
PyTorch), PDAL, GDAL/OGR, and WhiteboxTools. No proprietary software is required to
reproduce any result.

## 2. Data and software the project will produce

| Product | Format / standard | Where released |
|---|---|---|
| Elevation-change (DoD) rasters, all epoch pairs | Cloud-Optimized GeoTIFF, explicit CRS (EPSG:3294), nodata and units in metadata | Zenodo (DOI per release) |
| Per-stream erosion/deposition rate tables | CSV with data dictionary | Zenodo; offered to EDI for co-listing with the LTER stream data they derive from |
| Per-pixel calibrated detection-threshold layers (O3) | Cloud-Optimized GeoTIFF | Zenodo |
| Stream-channel outlines + process-classified geomorphic-change maps (O2) | GeoPackage (OGC) / Cloud-Optimized GeoTIFF | Zenodo |
| Training labels (if self-digitized) | GeoPackage + tile rasters | Zenodo — closing the label-access gap this field currently has |
| Trained model weights | PyTorch checkpoint + ONNX export, with training configuration | Zenodo |
| Processing code (full pipeline: fetch → derivatives → detection → change → attribution) | Python, version-controlled public repository, OSI-approved license (Apache-2.0) | Public repository, archived to Zenodo (DOI) at each release |
| Driver-attribution model outputs (O1) | CSV + fitted-model objects with documentation | Zenodo, with the O1 publication |

**Documentation standard.** Every released raster/vector product carries: coordinate
reference system (EPSG code), acquisition epochs and processing date, method summary,
uncertainty estimate (NMAD/LOD95 or the O3 per-pixel layer), and a pointer to the exact
code version (commit/DOI) that produced it.

## 3. When and where products are shared

- **Code**: developed in the open in a public repository from award start; released
  versions archived with DOIs.
- **Data products**: released no later than the publication of the paper they support,
  and at yearly milestones regardless of publication status (Yr 1: driver tables +
  Taylor Valley rates; Yr 2: cross-valley detection products; Yr 3: uncertainty layers +
  synthesis products).
- **Publications**: submitted to open-access venues or archived as accepted manuscripts
  in a public repository, consistent with SMD open-access policy.

## 4. Licenses

Data products: CC0 or CC-BY. Software: Apache-2.0. Third-party inputs remain under their
original terms and are cited, not re-hosted, except where their license permits
convenience copies.

## 5. Protections and exceptions

The project uses no human-subjects data, no export-controlled data, and no commercially
restricted data. The single access-limited item (the author-held label tiles) is handled
as described in §1: use with permission, no redistribution, and a published replacement
set if the project digitizes its own.

## 6. Roles and oversight

The FI is responsible for day-to-day data management, repository hygiene, and product
releases; the PI reviews each public release. Working data are stored on
institutionally backed storage with an off-machine mirror; the public archives (Zenodo,
EDI) provide long-term preservation beyond the award period.

## 7. Reproducibility commitment

Every number and figure in project publications will regenerate from public inputs via
the released code: a single documented command sequence per product. Heavy intermediate
rasters are treated as regenerable and are not archived; the scripts and small
tables/figures that define them are.
