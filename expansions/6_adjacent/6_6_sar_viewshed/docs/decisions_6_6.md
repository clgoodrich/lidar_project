# 6.6 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Visibility is three-state. Raster codes are 1 visible, 0 hidden, 2 unknown, 255 nodata. A known blocker gives hidden. Otherwise any unknown obstacle gives unknown. Review 6.6-02 and F13. Made by the fix agent, change freely.
- 2026-11-06. Void cells (no ground return) count as unobserved terrain both as targets and as obstacles. The old rule masked void targets and used their interpolated height as known obstacles. Made by the fix agent, change freely.
- 2026-11-06. Cumulative visibility marks a cell unknown when no observer sees it and at least one call is unknown. Counts there are NaN, not 0. Made by the fix agent, change freely.
- 2026-11-06. The S5 walk model smooths each track with a centred 15 s moving average and keeps points at least 10 m apart (or 3 times the smoothed fix error). Review 6.6-01. Made by the fix agent, change freely.
- 2026-11-06. The GNSS band in S4 is two-sided. Calls that differ inside the band make the pair ambiguous. Ambiguous and unknown pairs are counted and left out of agreement. Made by the fix agent, change freely.
- 2026-11-06. The map shows unknown in neutral grey with cross hatching and nodata as white paper. The palette check is recorded beside MAP_COLOURS. Made by the fix agent, change freely.
- 2026-11-05. Line of sight uses numpy, not WhiteboxTools, which is not installed. Made by the build agent, change freely.
- 2026-11-05. The sweep casts rays to every perimeter cell at half-cell steps. Each cell takes the sample nearest its centre. Made by the build agent, change freely.
- 2026-11-05. Obstacles are at least one cell from the observer and at least one cell short of the target. Made by the build agent, change freely.
- 2026-11-05. O2 canopy path follows the framework. It counts CHM cells above 2 m along the ray whatever the ray height. Made by the build agent, change freely.
- 2026-11-05. The O2 binary map uses a 0.5 visibility threshold. Made by the build agent, change freely.
- 2026-11-05. Starting extinction values are 0.15 per m leaf-on and 0.05 per m leaf-off until S4 fits them. Made by the build agent, change freely.
- 2026-11-05. Void cells (no ground return) are masked by default. On 9t at 0.5 m that removes about 45% of cells. Made by the build agent, change freely.
- 2026-11-05. The cost surface is resampled to 5 m. NLCD multipliers are starting values. Open water is impassable. Made by the build agent, change freely.
- 2026-11-05. Acceptance level A and the time tolerance have no defaults. The validators refuse to gate until they are set. Made by the build agent, change freely.
- 2026-11-05. The tool lives in the expansion `src/`, not `tools/` as the framework names it. Made by the build agent, change freely.
- 2026-11-05. Field checks use a 1.7 m person target. Maps default to a ground target. Made by the build agent, change freely.

## Decisions

- 2026-11-06. Void obstacle model (viewshed.void_obstacle). User accepted the default lower_neighbour, the lower of the two nearest observed heights along the ray ("take defaults"). Change freely. A void with an observed sample on one side only stays unknown. Void targets stay unknown. The old rule is the sensitivity void_obstacle unknown. Tests test_void_obstacle_takes_the_lower_neighbour, test_fill_void_lower_by_hand, test_void_at_the_observer_stays_unknown, test_sweep_matches_brute_force_with_voids.
- 2026-11-06. Rerun on 9t, 500 m from 621750, 4595250. O0 unknown share 0.490 to 0.448. Unknown cells 1,540,127 to 1,408,436, which are now only the void targets. Visible cells 44 to 131,321. O1 unknown share 0.449 to 0.449 (1,410,893 to 1,409,557 cells). O1 visible 36 to 1,126. Pockets unchanged (16 and 12). The void_obstacle unknown run reproduces the old O0 numbers exactly.

## Needs user decision
- None open.
