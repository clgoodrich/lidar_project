# pad_morphology_bins — unsupervised pad archetypes (9t + McKean)

**Date:** 2026-07-19 · **Script:** `notebooks/wellsight_v2/analysis/_pad_morphology_bins.py` · **Outputs:** `data/derivatives/experiments/pad_morphology_bins/`

> **v2 (same day):** script is now region-aware (joint 9t + McKean run, broad-k
> support). The v1 9t-only sections below still describe the k=4 run; the joint
> results are in the "v2 — joint 9t + McKean" section at the end. v1 script in
> git history at `880e7b6`.

## Goal

Follow-up to [[well_age_morphology]]: drop the age target and just ask whether
pads fall into natural morphology bins. Unsupervised, so the undated historic
population participates on equal footing; meaning (era, technology,
reclamation state) gets assigned to bins afterwards, not assumed.

## Inputs / provenance

- 650 pads inside the 9t raster footprint (`annotations_proj.gpkg` layer
  `plat`, EPSG:6346).
- 9t 0.5 m rasters: `slope_9t_05`, `lrm_11_9t_05`, `tpi_15_9t_05`,
  `chm_9t_05`, `hillshade_9t_05` (chips).
- `pit_inside` + `roads` annotation layers, `venango_wells_all.gpkg` (counts
  only — no dates used).

## Features (20 per pad)

Shape: area, perimeter, compactness, elongation, solidity, rectangularity.
Composition: n_pits inside, distance to nearest annotated road, catalog wells
within 50 m. Terrain: slope mean/std/flat-fraction inside; slope median in a
2–30 m annulus; slope_ratio (inside/annulus); edge slope (±2 m boundary ring);
lrm11 p95−p5; tpi15 mean. Canopy: CHM median inside / in annulus; chm_deficit
(annulus − inside, a regrowth-clock proxy). Size/count features log1p'd.

## Method

StandardScaler → PCA(90% var, 9 components) → KMeans, k selected by silhouette
over 3–8. **k = 4 won (silhouette 0.156)** — weak-but-real structure;
morphology is a continuum, bins are soft.

## Results — the four bins

| Bin | n | Signature (median) | Read |
|---|---|---|---|
| 0 | 45 | chm_deficit **7.3 m** (vs ≈0 elsewhere), tall surrounding forest | **Canopy-gap sites** — pad still open/regrowing; most recent activity or maintained clearings |
| 1 | 150 | Largest perimeter, lowest compactness/solidity, no pits | **Sprawling irregular lease clusters** on rolling ground |
| 2 | 240 | Compact, rounded, gentlest terrain (slope in/annulus/edge all low), no pits | **Flat compact pads on gentle terrain** — least engineered sites |
| 3 | 215 | 1+ pit, edge slope 12.3°, steep annulus, slope_ratio 1.10, high internal relief, smallest area | **Pit-bearing benched sites on steep hillsides** — cut into slopes, conform to terrain |

`fig_cluster_montage.png` (6 closest-to-center hillshade chips per bin)
confirms the bins are visually distinct. `fig_cluster_profile.png` is the
z-scored feature heatmap.

## Interpretation

- The strongest separators are exactly the features 2-D outlines lacked:
  canopy deficit, edge slope, terrain context (slope_ratio), pit presence.
- Bin 0 (canopy gap) is the clearest recency proxy — 45 sites where forest has
  not closed over. Cross-check against dated wells is a natural next step but
  deliberately NOT done here (bins first, meaning second).
- Bins 1 vs 2 split large-irregular from compact-round pads on gentle ground;
  bin 3 isolates the steep-terrain pit sites that dominated the pit
  annotations.
- Silhouette 0.156 means don't over-read bin boundaries; treat as archetypes
  with fuzzy edges, or switch to soft assignment (GMM) if bins become inputs
  to something downstream.

## QGIS

`pad_bins.gpkg` layer `pad_bins` (style embedded — categorized by
`cluster_lbl`, gray = incomplete features). All 20 features are in the
attribute table for Identify/filtering. `pad_features.csv` +
`cluster_summary.csv` hold the raw and per-bin numbers.

## Next steps

- Overlay dated wells on bins (does bin 0 skew modern? bin 3 historic?).
- Soft GMM assignment + per-pad membership probabilities.
- Extend to pits (pit-only sites are not represented — this run bins pads).
- Same pipeline on 613590/other blocks once their CHM exists.

## v2 — joint 9t + McKean (2026-07-19, user request: broader bins + McKean)

All 995 pads: 650 in 9t (Venango) + 345 in the mkf/McKean footprint
(696–706k E, 4645–4655k N). McKean features from `mkf_1m` (slope, lrm_11) and
`northcentral_b19` blocks e1423n2235/n2238 (+e1426\*) for tpi_15, CHM,
hillshade — best-covering source picked per pad. Composition features
(n_pits, road distance, well counts) are 9t-only annotations, so joint
clustering uses the 17 shape + terrain + canopy features only.

**Resolution caveat:** McKean rasters are 1 m vs 9t 0.5 m. Zonal medians are
fairly robust, but slope magnitudes read slightly lower at 1 m — which works
*against* the observed McKean-steeper result, so that contrast is conservative.

Silhouettes: **k=2 0.332** (best by far), k=3 0.216, k=4 0.187. The broad
structure is essentially binary, and it splits by region:

| k=2 bin | n | 9t / McKean | Median profile | Read |
|---|---|---|---|---|
| 0 | 603 | 593 / 10 | 1,692 m², edge 7.2°, slope_ratio 1.35, chm_deficit ≈0 | **Valley-field pads on gentle ground** (the 9t style) |
| 1 | 392 | 57 / 335 | 836 m², edge **18.3°**, slope_ratio 0.92, chm_deficit 1.6 m | **Small bench pads cut into steep hillsides** (the McKean style) |

k=3 (forced, for a middle grade) refines this: bin 0 = 376 gentle 9t pads;
bin 1 = 296 steep benches (292 McKean); bin 2 = 323 intermediate (270 9t +
53 McKean). Montage `fig_cluster_montage_joint_k3.png` (chips region-labeled)
makes the contrast unmistakable — McKean bench pads sit on contour roads in
steep dissected terrain, interiors flatter than surroundings (slope_ratio
< 1 = engineered bench), with a real 1.6–2 m canopy deficit (younger regrowth).

Interpretation: **region ≈ morphology regime.** The two fields were developed
differently — Venango 9t: larger irregular pads on rolling uplands; McKean:
small engineered benches on steep slopes. 57 9t pads land in the "bench" bin
and 10+53 McKean pads in the gentle/intermediate bins — cross-regime pads
worth eyeballing in QGIS. Any model trained on 9t pads alone has never seen
the dominant McKean archetype (consistent with the multi-block road-model
transfer lessons).

Outputs: `pad_bins_joint_k2.gpkg`, `pad_bins_joint_k3.gpkg` (styled, with
`region` + all features), `cluster_summary_joint_k{2,3}.csv`,
`summary_joint_k{2,3}.json` (incl. region×bin), profile + montage figures,
feature cache `pad_features_joint.csv`.

## Reproduce

```bash
python notebooks/wellsight_v2/analysis/_pad_morphology_bins.py --k 2   # broad
python notebooks/wellsight_v2/analysis/_pad_morphology_bins.py --k 3
python notebooks/wellsight_v2/analysis/_pad_morphology_bins.py         # silhouette k
```
