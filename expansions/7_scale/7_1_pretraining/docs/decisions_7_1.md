# 7.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-05. Masked reconstruction targets lrm_25 and lrm_5. The stack has no raw DEM and lrm_25 is the DEM minus its 25 m smooth. Made by the build agent, change freely.
- 2026-11-05. Contrast views are slope, roughness_11 and tpi_05 against lrm_25, lrm_5 and both openness channels. The stack has no hillshade or curvature. Made by the build agent, change freely.
- 2026-11-05. The U-Net output conv is the projection head. Fine-tuning replaces it with a new 3-class head. Made by the build agent, change freely.
- 2026-11-05. Window-level negatives come from batches that take half their chips from one window, with no two chips overlapping. Made by the build agent, change freely.
- 2026-11-05. Blocks with no pits form their own stratum and are cut at the same fraction as pit-bearing blocks. Made by the build agent, change freely.
- 2026-11-05. Corpus chips are an index into the window stacks, not copies. Made by the build agent, change freely.
- 2026-11-05. Run outputs go to this expansion's results/ and models/ folders, not data/9t/results/ssl/. The build was scoped to the expansion folder. Made by the build agent, change freely.
- 2026-11-05. A derived G below 0 is floored at 0 and the raw value is kept. A negative margin would let an arm win while doing worse. Made by the build agent, change freely.
- 2026-11-05. Candidate extraction and matching use the 7.3 scorer until the 3.0 scorer is frozen. Made by the build agent, change freely.
- 2026-11-05. The provisional split takes a seeded 15% of training blocks as inner validation. It never feeds the primary claim. Made by the build agent, change freely.
- 2026-11-05. Fine-tuning reads the full 9t stack into memory (about 2.6 GB with labels). Made by the build agent, change freely.
