# ICP: 2006-2008 PA Statewide N → 2019 USGS 3DEP D20 (block 618594 area)

Date: 2026-05-21. 5 m voxel-downsampled, ground-class only. PDAL filters.icp,
fixed = 2019, moving = 2006-2008 (after EPSG:2271 → EPSG:6346 reprojection and
Z × 0.3048 conversion from US feet to metres).

| Older tile | overlap (UTM) | dx (m) | dy (m) | dz (m) | √fitness ≈ RMSE (m) | converged |
|------------|---------------|--------|--------|--------|---------------------|-----------|
| 002957 | X 616322..619482, Y 4591776..4594935 | −1.087 | −0.259 | +0.052 | 1.014 | yes |
| 002958 | X 619368..622527, Y 4591890..4595050 | −0.489 | −0.415 | +0.099 | 0.946 | yes |
| 002959 | X 622413..625573, Y 4592004..4595164 | −0.538 | −0.723 | +0.112 | 1.112 | yes |
| 003110 | X 616208..619368, Y 4594821..4597981 | −1.185 | −0.842 | −0.047 | 0.983 | yes |
| 003111 | X 619253..622412, Y 4594935..4598095 | −0.306 | −0.637 | −0.026 | 0.915 | yes |
| 003112 | X 622298..625458, Y 4595050..4598209 | −1.112 | −1.154 | −0.085 | 0.989 | yes |

**Mean residual:** dx = −0.786 m, dy = −0.672 m, dz = +0.017 m, RMSE ≈ 0.99 m.

## Interpretation

- All six tiles show a sub-metre systematic shift of 2006-2008 → 2019: the
  older points sit ~0.8 m east-too-far and ~0.7 m north-too-far of the newer
  reference, with negligible vertical bias after the Z unit conversion.
- Rotation components are all <0.001° about every axis — pure translation.
- RMSE ~1 m is consistent with ground-class point-to-point matching after 5 m
  voxel sampling, not vegetation/canopy change.
- The pattern suggests a real datum-realisation difference (NAD83 original vs.
  NAD83(2011)) and/or different control between the 2006-2008 statewide
  contract and the 2019 D20 acquisition. Magnitude (~1 m) is typical for
  inter-epoch NAD83 plate motion + acquisition-control variation in PA.

## Files per tile (data/derivatives/icp/<id>/)

- `older_ground_5m_zm.las` — reprojected + Z-corrected + 5 m voxel sampled older cloud
- `newer_ground_5m.las` — merged + cropped + 5 m voxel sampled 2019 cloud
- `older_aligned*.las` — ICP-aligned moving cloud
- `_meta_icp*.json` — full ICP metadata (transform, fitness, centroid)
- `icp_summary.json` — convenience summary
