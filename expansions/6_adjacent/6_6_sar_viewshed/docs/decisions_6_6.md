# 6.6 decisions

Newest first. One line per decision, with the date and who made it.

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
