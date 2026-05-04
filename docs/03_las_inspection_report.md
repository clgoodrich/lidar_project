# 03 — LAS Inspection Report: `output2.las`

**File:** `data/files/output2.las` · **Inspected:** 2026-04-13 · **Tooling:** PDAL 2.10.0 CLI + `laspy` 2.7.0

## Header summary

| Property              | Value                                                                                           |
|-----------------------|-------------------------------------------------------------------------------------------------|
| LAS version           | **1.4**                                                                                         |
| Point format          | **7** (XYZ + Intensity + GPS time + RGB; no waveform)                                           |
| Point count           | **9 717 579**                                                                                   |
| File size             | 334 MB (uncompressed `.las`, not `.laz`)                                                        |
| Bounds (X)            | 622 500.00 – 623 999.99 m                                                                       |
| Bounds (Y)            | 4 594 500.00 – 4 595 999.99 m                                                                   |
| Bounds (Z)            | 363.31 – 517.99 m                                                                               |
| Tile size             | 1 500 × 1 500 m = 2.25 km²                                                                      |
| Vertical relief       | 154.7 m                                                                                         |
| Mean point density    | **≈ 4.32 pts/m²** (between USGS QL1 ≥ 7 and QL2 ≥ 2)                                            |
| Mean ground density   | **≈ 2.62 pts/m²** (class=2 only)                                                                |
| Creation date         | DOY 103, 2026 (i.e. 2026-04-13)                                                                 |
| Global encoding       | 16 (bit 4 set = WKT-style CRS present in VLRs)                                                  |

## CRS

| Axis       | CRS                                                          |
|------------|--------------------------------------------------------------|
| Horizontal | **NAD83(2011) / UTM zone 17N (EPSG:6346)** · units **metres** |
| Vertical   | **NAVD88 height + Geoid12B (EPSG:5703)** · units **metres**  |

**No unit conversion required** — both axes are metric, so slope and
curvature computations do not need a US Survey Feet → metres step. Verified
from the compound WKT embedded in the LAS VLRs.

## Classification histogram

| Code | Label                       | Count      | %        |
|-----:|-----------------------------|-----------:|---------:|
|    1 | Unclassified                |  3 814 090 | 39.25 %  |
|    2 | **Ground**                  |  5 903 148 | 60.75 %  |
|    7 | Noise                       |         50 | < 0.01 % |
|   17 | Bridge deck                 |        218 | < 0.01 % |
|   18 | High noise                  |         73 | < 0.01 % |

**Interpretation.** USGS has already run ground classification — `class=2`
is populated and usable directly. Vegetation is **not** split into low/medium
/high (classes 3/4/5); it is lumped into `class=1` (Unclassified). This
matches the standard USGS 3DEP Lidar Base Specification. Any "above-canopy"
reasoning must go through a DEM-relative height (AGL = Z − DEM), not through
class labels.

## Return distribution

| Return # | Count      | % of points |
|---------:|-----------:|------------:|
| 1        | 7 675 615  |       79.0 %|
| 2        | 1 672 021  |       17.2 %|
| 3        |   325 951  |        3.4 %|
| 4        |    40 569  |        0.4 %|
| 5        |     3 259  |     < 0.1 % |
| 6        |       157  |     < 0.1 % |
| 7        |         7  |     < 0.1 % |

Healthy first-return dominance; multi-return density under canopy is
sufficient to resolve vertical structure (CHM) and to identify single-return
ground hits (sometimes a specular-surface or canopy-gap signature).

## Point-format-7 dimensions present

`X, Y, Z, Intensity, ReturnNumber, NumberOfReturns, ScanDirectionFlag,
EdgeOfFlightLine, Classification, Synthetic, KeyPoint, Withheld, Overlap,
ScanAngleRank, UserData, PointSourceId, GpsTime, ScanChannel, Red, Green,
Blue`

Consequence: **RGB bands are available** on every point. Not central to pad
detection but worth noting for any future vegetation or land-cover work.

## Intensity & scan-angle

| Field           | Min | Max    | Mean     | Notes                          |
|-----------------|-----|--------|----------|--------------------------------|
| Intensity       |  96 | 65 520 | 15 495.6 | 16-bit, zero % = 0 (fully populated) |
| ScanAngleRank   | varies | varies | varies | Populated — enables angular analysis |

Intensity needs range / scan-angle normalisation before being gridded to a
raster; not required for pad detection, but note for future metallic-surface
work.

## Data-quality flags

- **No waveform.** Point format 7 = discrete-return. Pulse-width / echo-ratio
  / rise-time derivatives are not available without a waveform collection.
- **Overlap field present but not inspected here.** `Classification.Overlap`
  is tracked separately by LAS 1.4 — if we ever do an intensity-vs-scan-angle
  test we should filter overlap points out.
- **No reported point-density voids** observed in the aggregate stats, but a
  per-cell ground-density raster is required downstream to flag cells where
  the DEM is interpolated rather than measured.
- **Creation year 2026, not collection year.** The `creation_*` fields are the
  LAS-file build date. The actual collection is the USGS 3DEP
  *PA_WesternPA_1_2019* acquisition (leaf-off Nov 2019 – Mar 2020).

## Implications for the pipeline

1. Skip SMRF / PMF ground re-classification. USGS `class=2` is authoritative.
2. DEM = rasterise `class=2` points (min or TIN-interp) at 1 m.
3. DSM = rasterise `ReturnNumber == 1` (max-Z per cell).
4. CHM = DSM − DEM. No extra unit conversion step.
5. Ground-return density raster is a mandatory quality mask; flag cells with
   < N pts/m² (threshold to be set in the design spec).
6. Intensity-based detectors are feasible (Feature Type I analogues) but are
   out of the pilot scope per the design spec.
7. Reproject wells CSV → EPSG:6346 before any spatial join.

## Pilot sub-window candidates

Per the WellSight Bootstrap rule, the first detector run must target a small
sub-window around 3–5 known wells, not the full tile. Recommended candidates,
drawn from the 84 documented wells, to be selected in the design spec based
on spatial isolation (clear background signal) + forest cover.
