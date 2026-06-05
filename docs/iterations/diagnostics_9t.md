# diagnostics_9t — second-wave DEM derivatives (curvature / hydrology / texture)

**Status:** built + sanity-checked 2026-06-03. Diagnostic-only — **not wired into any trained model.** Purpose: see which additional geomorphometric layers separate pits / pads / roads, before deciding whether any earn a slot in the model feature stack.

**Input.** `data/derivatives/dem_9t_1m.tif` (1 m bare-earth DEM, EPSG:6346). Built at 1 m (not 0.5 m): faster, cleaner for curvature/geomorphons on multi-meter features. If a layer is promoted to the model stack, recompute at 0.5 m to match `features_pit_9t_05.tif`.

**Builder.** `notebooks/wellsight/build/_build_diagnostics_9t.py` (WhiteboxTools v2.4.0). All 16 ops succeeded in ~45 s total (geomorphons dominates at ~25 s). Outputs in `data/derivatives/9t/diagnostics/` (git-ignored, ~regenerable).

## Layers produced

| Layer | Tool | What it diagnoses | Value range (valid%) |
|---|---|---|---|
| `depth_in_sink` | FillDepressions − DEM | **closed-depression depth** — near-direct pit signal | 0–2.82 m (100%) |
| `twi` | WetnessIndex(SCA, slope) | wet/flat accumulation — pad flatness context | −1.1 to 23.3 |
| `profile_curv` | ProfileCurvature | concavity *along* slope — pit lips, pad downhill edge | −1.21 to 0.95 |
| `plan_curv` | PlanCurvature | curvature *across* slope — rims, flow convergence | wide (flat-area artifacts) |
| `total_curv` | TotalCurvature | overall bending magnitude | 0–2.25 |
| `mean_curv` | MeanCurvature | bowl vs dome | −0.77 to 0.75 |
| `gaussian_curv` | GaussianCurvature | saddle vs bowl vs dome | −0.44 to 0.52 |
| `geomorphons` | Geomorphons (search=50) | **categorical landform** (1 flat … 10 depression) | codes 2–10 |
| `mdhillshade` | MultidirectionalHillshade | shaded relief, no azimuth blind spot | 0–32767 |
| `sph_stddev_normals` | SphericalStdDevOfNormals(f=11) | surface-orientation disturbance | 0.13–38.6° |
| `tri` | RuggednessIndex | terrain ruggedness (texture) | 0–3.7 |
| `sar` | SurfaceAreaRatio | 3D/planar area — flat (≈1) vs rough pads | 1.0–3.89 |
| `downslope_index` | DownslopeIndex(drop=2) | local drainage gradient | 0–5.16 |

(`slope`, the filled DEM, and SCA are computed as intermediates and deleted.)

## Validation against the 110 pit annotations (the headline)

Sampled each layer at the 110 `pit_inside` centroids vs 2000 random background points:

**`depth_in_sink` is a near-standalone pit detector.**
| | median | % in a sink (>0) | % >0.2 m deep |
|---|---|---|---|
| at pit centroids | **0.36 m** | **90%** | **71%** |
| at random points | 0.00 m | 1% | 0% |

A ~90× separation in "sits in a closed depression." This is the strongest single hand-crafted pit signal we've measured.

**`geomorphons` agrees:** 106 / 110 pits land in concave landform classes —
depression (46), valley (32), hollow (28) — only 4 in slope/spur. One categorical band that says "pit-like" almost for free.

## Interpretation / next steps
- **depth_in_sink** and **geomorphons** are the clear winners for *pits* and are the top candidates to add to the pit feature stack (recompute at 0.5 m first). Caveat: these were validated *at* known pits; precision over the full tile (false sinks from culverts, natural kettles) still needs the background false-positive rate measured before promotion.
- Curvature (profile/plan) and **sar** are the most promising *pad/road edge* discriminators but haven't been quantitatively validated yet — eyeball in QGIS next.
- None are in the models yet; this stays diagnostic until a promotion decision. See [[BACKLOG]].

**Reproduce.**
```
python notebooks/wellsight/build/_build_diagnostics_9t.py
```
