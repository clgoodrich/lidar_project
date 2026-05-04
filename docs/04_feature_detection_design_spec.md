# 04 — Feature Detection Design Specification

**Status:** draft 1 · **Date:** 2026-04-13 · **Scope:** pilot tile `output2.las`

> This spec governs **what** WellSight tries to detect, **how** it decides, and
> **how** we know it worked. The companion pipeline diagram
> (`docs/05_processing_pipeline.md`) covers the plumbing.

## 1. What we are trying to detect

The `Claude.md` formation prompt names six surface signatures:

1. **Pad scars** — graded flat benches cut into hillsides.
2. Terrain depressions (wellhead subsidence, cellar pits).
3. Circular clearings.
4. Access-road remnants.
5. Disturbed-soil patterns.
6. Vegetation anomalies.

For the **pilot** we implement a single detector for (1) pad scars only,
because they have the clearest morphological signature at 1 m LiDAR
resolution, the largest detectable surface area per well, and the best
chance of surviving 60–160 years of reforestation. Later iterations add the
others as independent layers; each detector stands alone and is never fused
into a single "well likelihood" score.

## 2. Pad-scar signature (design hypothesis)

A graded pad on an Appalachian hillside leaves three spatially co-located
signals in the bare-earth DEM:

| Signal            | Physical cause                                 | Raster used                         |
|-------------------|------------------------------------------------|-------------------------------------|
| Low slope         | The working surface was levelled               | `slope.tif`                         |
| Low surface roughness | Compacted subsoil resists weathering       | `roughness_11.tif` (σ of elevation, 11×11) |
| Low local relief  | No natural convexity / concavity remains       | `local_relief.tif` (max−min, 10 m disk) |

A stronger (but not strictly required) fourth signal is the **asymmetric cut/
fill dipole**: strongly negative TPI on the uphill side (the cut bank) and
strongly positive TPI on the downhill side (the fill slope), with near-zero
TPI on the bench itself. This is computed as the **gradient of TPI at the
pad scale (~15 m)**. It is a confidence booster, not a primary gate — on
gentle slopes or on pads that have eroded into the hillslope the dipole is
weak.

Landscape-position sanity: pads sit at **mid-slope**, not on ridgetops or in
valley bottoms. We filter using a wide-scale TPI (51 m) for the pilot; HAND
replaces it if `pysheds` / `whitebox` proves reliable.

## 3. Detector stages (pad scars)

```
[DEM] ─► [slope, roughness_11, local_relief, tpi_15, tpi_51, tpi_grad]
             │
             ▼
   flatness_mask  =  slope<θs  AND  roughness<θr  AND  local_relief<θlr
             │
             ▼
   minimal-morphology cleanup  (closing radius 1 cell only)
             │
             ▼
   connected components  →  polygons
             │
             ▼
   per-polygon attrs:  area_m2, perimeter_m, compactness,
                       rectangularity (polygon / OBB area),
                       obb_aspect (short/long side),
                       mean(slope), mean(roughness), mean(local_relief),
                       mean(tpi_15), mean(tpi_51), mean(tpi_grad_mag)
             │
             ▼
   shape gate       compactness ≥ θc  OR  rectangularity ≥ θrect
   position gate    θtpi_lo  < mean(tpi_51) < θtpi_hi
   size gate        θa_min  < area_m2 < θa_max
             │
             ▼
   confidence scoring  (Section 5)
             │
             ▼
   candidate GeoPackage  (Section 6)
```

## 4. Initial thresholds (pilot, to be tuned)

| Name       | Default  | Role                                           |
|------------|----------|------------------------------------------------|
| `θs`       | 8°       | Max slope. Drohan & Brittingham (2012): reclaimed pads 3-8°; aged pads reach 8-10° from erosion/settling. PA DEP 25 Pa. Code Ch. 78 requires ≤5% grade (~2.9°) for new pads, but aged orphans exceed this. |
| `θr`       | 0.15 m   | Max 11×11 elevation stddev. Riley et al. (1999), Grohmann et al. (2011). |
| `θlr`      | 0.40 m   | Max 10 m-disk local relief.                    |
| `θc`       | 0.40     | Min compactness (4πA/P²) — rejects thin things |
| `θrect`    | 0.70     | Min rectangularity — accepts square/rect pads  |
| `θtpi_lo`  | −1.0 m   | Rejects valley floors (too negative TPI). TPI radii per Weiss (2001), De Reu et al. (2013). |
| `θtpi_hi`  | +3.0 m   | Rejects obvious ridge spurs                    |
| `θa_min`   | 100 m²   | Noise floor (~10 m square). Hammack et al. (2014, NETL): smallest documented PA conventional pads ~100-400 m². Allred et al. (2015): conventional pads 900-4000 m². |
| `θa_max`   | 20 000 m²| Allow up to modern unconventional. Drohan et al. (2012): Marcellus pads 2000-15000 m². |
| `θdens`    | 1.0 pt/m²| Min ground-return density for a cell to count  |

Tuning rule: vary one threshold at a time, rerun the bootstrap pilot window,
record the effect in `docs/analysis_log.md` with counts + distance-to-nearest-
well. No threshold change ships without a log entry.

## 5. Confidence scoring

Each candidate gets a `confidence_score ∈ [0, 1]` from a weighted sum of
normalised sub-scores, independent of ground-truth (no leakage):

| Sub-score           | Formula (clipped to [0, 1])                                                 | Weight |
|---------------------|-----------------------------------------------------------------------------|-------:|
| `s_flatness`        | 1 − (mean_slope / θs)                                                        | 0.25   |
| `s_smoothness`      | 1 − (mean_roughness / θr)                                                    | 0.20   |
| `s_relief`          | 1 − (mean_local_relief / θlr)                                                | 0.15   |
| `s_shape`           | max(compactness/θc, rectangularity/θrect) − 1, clipped to [0, 1]             | 0.20   |
| `s_position`        | piecewise-linear: full credit in mid-slope band, zero in valley/ridge tails  | 0.10   |
| `s_cut_fill`        | mean(|tpi_grad_mag|) / p95(tpi_grad_mag across tile)                         | 0.10   |

`confidence_score = Σ weight_i · sub_score_i`. Weights will be re-examined
after the first pilot validation pass.

## 6. Output schema (per candidate)

GeoPackage layer: `candidates_pads` (one row per candidate polygon).

Required fields:

| Field              | Type    | Description                                                                                           |
|--------------------|---------|-------------------------------------------------------------------------------------------------------|
| `cand_id`          | int     | Stable integer, generated at export.                                                                 |
| `detection_method` | str     | Free-text method tag, e.g. `"pad_v0.1_flatness_morph"`.                                               |
| `run_id`           | str     | Timestamped run identifier, links to analysis-log entry.                                              |
| `confidence_score` | float   | 0–1, as Section 5.                                                                                    |
| `confidence_label` | str     | `"candidate"` (≤ 0.70) / `"probable"` (> 0.70). Never `"confirmed"`.                                  |
| `area_m2`          | float   |                                                                                                       |
| `perimeter_m`      | float   |                                                                                                       |
| `compactness`      | float   |                                                                                                       |
| `rectangularity`   | float   |                                                                                                       |
| `obb_aspect`       | float   |                                                                                                       |
| `mean_slope`       | float   | degrees                                                                                               |
| `mean_roughness`   | float   | metres                                                                                                |
| `mean_local_relief`| float   | metres                                                                                                |
| `mean_tpi_15`      | float   | metres                                                                                                |
| `mean_tpi_51`      | float   | metres                                                                                                |
| `mean_tpi_grad_mag`| float   | per-metre                                                                                             |
| `nearest_well_m`   | float   | Distance to nearest record in `wells_in_tile.gpkg`                                                    |
| `nearest_well_id`  | str     | `Well_ident` of that record                                                                           |
| `inside_positional_uncertainty` | bool | True if `nearest_well_m ≤ 50 m`. (50 m = default PA DEP uncertainty model.)                 |
| `geometry`         | polygon | CRS: EPSG:6346                                                                                        |

Side-car file: `candidates_pads.parquet` with the same rows minus geometry
for fast analytics.

Compliance per `Claude.md`: **every candidate** carries confidence,
detection method, and nearest-well distance. No candidate is labelled
"confirmed."

## 7. Validation methodology

We cannot trust any pad candidate that wasn't stress-tested against noise.
Two checks, mandatory on every run:

### 7.1 Distance-to-nearest-well vs. random baseline

1. Compute the distribution of `nearest_well_m` across all candidates.
2. Generate *N = 200* random point sets of the same cardinality inside the
   tile, each point a uniform random location that has the same ground-return
   density ≥ `θdens` as real candidates (rejection sampling).
3. Report:
   - Median candidate `nearest_well_m`.
   - 5th / 50th / 95th percentile of the random null distribution.
   - Empirical p-value: fraction of random runs with median ≤ observed.
4. Threshold for "signal above chance": `p < 0.05`.

### 7.2 Within-uncertainty recall

1. Count known wells that have ≥ 1 candidate within 50 m.
2. Report "recall at 50 m" = that count / 84.
3. Compare against the random null of 7.1.

Neither check is a classifier — they measure whether the candidate set
carries *any* spatial signal relative to ground truth.

## 8. Bootstrap pilot (per WellSight rule)

Before the detector runs tile-wide, it runs on a sub-window first:

- **Selection:** 3–5 spatially-isolated documented wells (no other well
  within 150 m), in areas with valid ground density (`θdens`), in forested
  cover. Specific `Well_ident`s are chosen at runtime from
  `wells_in_tile.gpkg`.
- **Window:** 250 × 250 m square centred on each chosen well.
- **Acceptance:** pilot produces ≥ 1 candidate per well window AND
  `nearest_well_m` distribution is shifted versus the random baseline on
  Section 7.1 within those windows.
- **On rejection:** re-tune a single threshold per iteration; log every
  iteration; do not fan out to the full tile.

## 9. Iteration plan (pilot → scale-up)

```
v0.1  pilot, 3–5 well windows         → acceptance test 7.1/7.2 on the windows
v0.2  tile-wide run, no scoring tweak → full validation on the tile
v0.3  threshold sweep around promising axis (one at a time)
v0.4  consider second feature type (terrain depressions) as its own layer
v0.5  scale to 4–8 adjacent LAZ tiles (bootstrap rule re-applied)
```

Everything after v0.2 is conditional on v0.2 passing the validation gate.

## 10. Open decisions (escalated, not guessed)

| # | Question                                                               | Default used if no answer                                     |
|---|------------------------------------------------------------------------|---------------------------------------------------------------|
| 1 | Positional-uncertainty radius for "within uncertainty" flag            | 50 m (PA DEP pre-1990 literature default)                      |
| 2 | Minimum ground-return density (`θdens`)                                | 1.0 pts/m² (≈ 25th percentile of observed density histogram)   |
| 3 | Era-specific detectors?                                                | No — single pad detector covering full size range 40–20 000 m² |
| 4 | DEM interpolation method: PDAL TIN (`faceraster`) vs. min-Z binning     | PDAL TIN for the production DEM; min-Z binning only for QA     |
| 5 | Tool for slope/TPI/curvature: WhiteboxTools vs. hand-rolled SciPy      | WhiteboxTools where it ships a pre-tested implementation       |

Any escalated item that is answered by the user moves into the table above
with the new default and gets logged.
