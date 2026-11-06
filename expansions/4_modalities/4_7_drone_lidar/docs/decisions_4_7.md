# 4.7 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Area folder is data/oilcreek/ (existing), area tag oc. made by the build agent, change freely.
- 2026-11-05. Thinning keeps exactly round(rate x n) points of ground and of non-ground, chosen by PDAL filters.randomize with seed then filters.head. Seeds are expkit.child_seed(master, rung, seed). made by the build agent, change freely.
- 2026-11-05. Native rung is the original file, listed once with no seed. made by the build agent, change freely.
- 2026-11-05. Gridded counts use writers.gdal binmode. Without it the default radius counts one point in several cells. made by the build agent, change freely.
- 2026-11-05. Footprint is every 1 m cell with any return. Native density is ground returns over that area. made by the build agent, change freely.
- 2026-11-05. Rung stacks use one grid from the native extent so rungs pair cell for cell. made by the build agent, change freely.
- 2026-11-05. Bootstrap resamples sites within hillside, and every draw is applied to all rungs. With two hillsides a cluster bootstrap over hillsides would be degenerate. made by the build agent, change freely.
- 2026-11-05. Point sites match a candidate within 10 m. Polygon sites match at IoU 0.3. made by the build agent, change freely.
- 2026-11-05. Results are labelled conditional on lidar-visible sites unless S1 shows selection independent of lidar. Unknown selection counts as lidar-based. made by the build agent, change freely.
