# 4.7 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. SMRF parameters `ladder.reclass`. User accepted the default PDAL filters.smrf defaults (cell 1, slope 0.15, window 18, threshold 0.5, scalar 1.25) ("take defaults"). Change freely.


- 2026-11-06. The ladder is nested. The shuffle seed depends on the seed index only, so each lower rung is a subset of every higher rung with the same seed index. The density curve is a paired sensitivity, so nesting removes between-rung sampling noise. The framework asked for seeded random thinning and did not require nesting. Every run checks the nesting. Made by the review-fix agent, change freely.
- 2026-11-06. Every rung is reclassified. Class 2 is reset to 1 and PDAL filters.smrf is rerun on the thinned points through the PDAL CLI. The native rung is reclassified the same way, so all rungs share one classifier. The native class is kept as the NativeClass extra dimension for the count check (review 4.7-01). Made by the review-fix agent, change freely.
- 2026-11-06. Thinning stays stratified by native class (ground and non-ground). n_ground and ground_ppsm in the ladder now mean SMRF ground. Made by the review-fix agent, change freely.

- 2026-11-05. Area folder is data/oilcreek/ (existing), area tag oc. made by the build agent, change freely.
- 2026-11-05. Thinning keeps exactly round(rate x n) points of ground and of non-ground, chosen by PDAL filters.randomize with seed then filters.head. Seeds are expkit.child_seed(master, rung, seed). made by the build agent, change freely.
- 2026-11-05. Native rung is the original file, listed once with no seed. made by the build agent, change freely.
- 2026-11-05. Gridded counts use writers.gdal binmode. Without it the default radius counts one point in several cells. made by the build agent, change freely.
- 2026-11-05. Footprint is every 1 m cell with any return. Native density is ground returns over that area. made by the build agent, change freely.
- 2026-11-05. Rung stacks use one grid from the native extent so rungs pair cell for cell. made by the build agent, change freely.
- 2026-11-05. Bootstrap resamples sites within hillside, and every draw is applied to all rungs. With two hillsides a cluster bootstrap over hillsides would be degenerate. made by the build agent, change freely.
- 2026-11-05. Point sites match a candidate within 10 m. Polygon sites match at IoU 0.3. made by the build agent, change freely.
- 2026-11-05. Results are labelled conditional on lidar-visible sites unless S1 shows selection independent of lidar. Unknown selection counts as lidar-based. made by the build agent, change freely.

## Needs user decision

None open after the 2026-11-06 defaults.
