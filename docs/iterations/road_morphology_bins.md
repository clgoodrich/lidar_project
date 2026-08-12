# road_morphology_bins — do 9t roads split into "big" and "faint"?

**Date:** 2026-07-29 · **Script:** `notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py`
· **Outputs:** `data/derivatives/experiments/road_morphology_bins/`
· **Related:** [[pad_morphology_bins]], [[road_unet_1m_recall]], [[road_sweep_202607]]

> **CORRECTED 2026-07-29 — read [[road_bold_vs_faint]] first.** The central
> conclusion below ("width is constant, depth is a continuum, there is no second
> population") describes the **annotated** roads, not the roads. The user's
> `faint_roads.shp` exemplars showed that **0 of 21 faint roads exist in
> `roads.shp`** (median 87.4 m from the nearest annotated line), so this analysis
> sampled a population from which the faint variety had already been excluded.
> There ARE two varieties; one of them is missing from the label set, and the
> road model scores it 0.032 mean P(road) against 0.775 for bold. The
> width/depth/continuum measurements below remain valid **within the bold
> class**, as does `prominence_z` as a within-bold terrain-fair measure.

## Goal

The annotated roads look like they come in two varieties — wide engineered
roads and faint narrow traces. Is that a real split in the terrain data, and if
so where is the boundary?

## Inputs / provenance

- `data/derivatives/annotations/roads.shp` (1,997 lines, EPSG:4326) reprojected
  to EPSG:6346 and clipped to the 9t block footprint (`pit_blocks_9t.gpkg`) →
  **1,112 roads / 186.20 km**; 1,096 survive the ≥3-transect requirement.
- 9t **0.5 m** rasters: `dem_9t_05`, `slope_9t_05`, `chm_9t_05`,
  `intensity_ground_9t_05`, `lrm_5_9t_05`. 1 m would alias a 3–6 m tread.
- External check: TIGER/Line 2024 roads (`data/external/tiger_roads/roads_clipped.gpkg`).
- Held out of clustering: `mean_proad` from `road_unet_1m_recall/road_prob.tif`.

## Method

"Big vs faint" is a **cross-section** property, so the features are transect
measurements, not plan-shape ones. Perpendicular transects every 10 m, ±25 m at
0.5 m spacing → **18,062 transects / 1.82 M samples**. Each transect is
detrended by a line fit through the **outer thirds only** (|d| ∈ [15, 25] m), so
the road never influences the trend surface meant to represent its own
hillslope. Per-road features are medians over its transects. Then
StandardScaler → PCA(90%) → KMeans, k by silhouette, mirroring
[[pad_morphology_bins]].

## Three measurement problems found and fixed

1. **The first run binned terrain, not size.** Including hillslope/cut/fill gave
   a k=2 split with hillslope 8.7° vs 2.7° — it separated *where* a road sits,
   not *how big* it is. Terrain features were moved out of the clustering and
   are reported alongside instead.
2. **`tread_width_m` is invalid on flat ground.** It is the contiguous run of
   slope ≤ 8° through the centreline, which has no terminating shoulder when the
   surroundings are already flat. It reports *wider* treads for the fainter,
   flatter roads — backwards. Replaced for clustering by `berm_sep_m` and
   `incision_fwhm_m`; kept in the output table as a caveated descriptive column.
3. **CHM medians measured zeros, not canopy.** `chm_9t_05` is heavily
   zero-inflated (tile median 0.091 m, p99 25.8 m), so a transect median is
   ~0 regardless of canopy. Switched to p90 within each band.

Also noted: `intensity_ground_9t_05` is 44.6% nodata over the transect samples
(ground-return intensity only exists where ground returns do), so `inten_ratio`
is the weakest feature in the set.

## Result — the premise is half right

**k=2 is the best partition** (silhouette 0.229, against 0.164 for k=3 and below
for k=4–8), so a two-way split is the right shape *if* you want bins. But what
separates the bins is not what the question assumed.

| | bin 0 | bin 1 |
|---|---|---|
| n / km | 686 / 106.3 | 410 / 79.4 |
| **incision depth** | **0.51 m** | **0.86 m** |
| **width (berm-to-berm)** | **14.0 m** | **15.0 m** |
| **width (FWHM of trough)** | **6.38 m** | **6.50 m** |
| relief amplitude | 0.57 m | 1.01 m |
| shoulder gradient | 0.28 | 0.45 |
| hillslope at crossing | 2.85° | 7.85° |
| CHM canopy deficit | 4.35 m | 6.87 m |
| TIGER match rate | 0.080 | 0.061 |
| model P(road) | 0.746 | 0.753 |

### 1. Width does not vary. At all.

Variance explained by the bins (η²) is **0.001** for `incision_fwhm_m` and
0.016 for `berm_sep_m`, against **0.508** for incision depth. Across the whole
network `berm_sep_m` has a coefficient of variation of just **0.20**
(p25–p75 = 12.5–16.25 m).

The 9t roads are essentially all the same width. That is consistent with a
single construction standard — a single-lane access road — built everywhere,
which is what you would expect of lease and haul roads in one oilfield.

### 2. What varies is depth, and it is a continuum, not two populations.

Incision depth spans 0.23 m (p5) to 1.18 m (p95), a 5x range. But a 1-D
Gaussian mixture on log depth prefers **one component** (BIC −776) over two
(−753) or three (−746). The histogram is a single right-skewed hump.

**So the k=2 bins are a threshold on a continuum, not a discovered class
boundary.** Any cut point is a choice, not a finding. This is the central
result and it is a negative one.

### 3. Depth is substantially terrain, not road size.

Incision depth correlates **+0.42 (Spearman)** with the hillslope at the
crossing, and the bins still carry η² 0.24 on hillslope even with terrain
features excluded. This is physically expected: a road benched into a sideslope
*must* be cut in, while the same road on a flat bench need not be.

So a meaningful part of "that road looks faint" is really "that road is on flat
ground".

### 4. Neither bin is the maintained public network.

Only **80 of 1,096 roads (7%)** match a TIGER road over ≥50% of their length,
and the match rate is *lower* for the more-incised bin (0.061 vs 0.080). The
annotated network is overwhelmingly non-public — lease, haul, and skid roads —
so TIGER cannot serve as a "big road" label here. Model confidence is also flat
across bins (0.746 vs 0.753): the U-Net is not finding faint roads harder by
this measure.

## `prominence_z` — the deliverable to actually use

Because raw depth conflates "faint road" with "flat ground", the script fits
log(incision depth) against log(hillslope) and keeps the residual, z-scored.
This measures how strongly a road is expressed **for the terrain it sits on**,
which is what a human means by faint.

Terrain coupling drops from Spearman **+0.416 → −0.002**. It is on every road in
the output GeoPackage.

Recommended usage: **threshold `prominence_z`, do not use the hard bins.** The
bins are a defensible default partition, but the underlying quantity is
continuous and the cut point should be chosen per task.

## Outputs

`data/derivatives/experiments/road_morphology_bins/`

| file | contents |
|---|---|
| `road_morphology_bins_9t_05.gpkg` (layer `roads_binned`) | 1,096 roads, all cross-section features, `bin`, `prominence_z`, `tiger_match`, `mean_proad` |
| `road_morphology_bins_9t_05.csv` | same, tabular |
| `road_bin_profiles_9t_05.json` | per-bin medians, silhouette by k, transect config |
| `fig_road_width_vs_depth_9t_05.png` | **headline** — width is one population, depth is a continuum, depth tracks terrain |
| `fig_road_bin_crosssections_9t_05.png` | median transect profile + canopy profile per bin |
| `fig_road_bin_features_9t_05.png` | z-scored feature signature heatmap |
| `fig_road_bin_map_9t_05.png` | 9t map coloured by bin |

## Interpretation

The visual impression of "two varieties" is real but is mostly an impression of
**contrast**, not of size. Roads are one width; they differ in how deeply they
are cut, and how deeply they are cut depends heavily on the slope they cross.

Practical consequences:

- **Do not build a two-class road model.** There is no second population to
  learn. A width-based or size-based class split would be fitting a threshold,
  not a category.
- **`prominence_z` is the useful variable** — for prioritising candidates, for
  stratifying training samples, and for reporting which roads the model finds.
- **Terrain-stratified evaluation is now possible.** Model recall can be
  reported against `hillslope_deg` and `prominence_z` bands, which answers
  "does the road model miss faint roads?" properly. It was never asked, and the
  flat `mean_proad` across bins suggests the answer may be no.

## Caveats

- Every number is 9t only — one landscape, one survey, one annotator.
- `inten_ratio` rests on a channel that is 44.6% nodata over the samples.
- The annotator drew centrelines, not extents, so width is measured from the
  DEM alone and inherits any centreline placement error.
- Silhouette 0.229 is weak-but-real structure, the same regime as
  [[pad_morphology_bins]] (0.156). Bins are soft.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py          # k by silhouette
python notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py --k 3    # force k
```
