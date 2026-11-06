# 3.7 decisions

Newest first. One line per decision, with the date and who made it.

- Provincial file names and column names in the config are guesses. They are starting points to replace after S0. (2026-11-05, made by the build agent, change freely)
- Coordinate method strings map to classes by keyword. Stated uncertainties are 400 m for quarter sections, 200 m for legal subdivisions, 300 m for lot and concession, 10 m for surveyed. (2026-11-05, made by the build agent, change freely)
- Orphan-list rows are always V0. Regulator rows reach V1 when the method is documented and an uncertainty is set. (2026-11-05, made by the build agent, change freely)
- V2 needs a drawn feature inside the stated uncertainty and a blind judge's agreement. Proximity alone never promotes a record. (2026-11-05, made by the build agent, change freely)
- The shifted-set null rejects any shift that moves a record outside the scored footprint, between 300 and 2,000 m. (2026-11-05, made by the build agent, change freely)
- Per-province margins sit in `prereg.margin_by_area`. The core score uses them before the single margin. (2026-11-05, made by the build agent, change freely)
- Province window centres stay null until S2 prints them. The analyst pastes them into the config. (2026-11-05, made by the build agent, change freely)
- The shared transfer code lives in `3_4_gulf_texas/src/_geo_transfer_core.py`. Regions 3.5 to 3.8 import it by a relative path. (2026-11-05, made by the build agent, change freely)
- Stages every region shares are subcommands of the core (cover, density, blocks, derive, infer, score, width, agree, prereg) instead of one copy per region. (2026-11-05, made by the build agent, change freely)
- Assumed input paths and schemas live in `src/config_<id>.json`. A missing input stops the script with a message naming it. (2026-11-05, made by the build agent, change freely)
- User-only values (margins, gains, caps, floors) are null in the config. Scoring scripts refuse to run until they are set. (2026-11-05, made by the build agent, change freely)
- Scripts write run outputs only to `data/<area>/` or to this expansion folder. The build runs wrote only to this expansion folder. (2026-11-05, made by the build agent, change freely)
- Candidate extraction is threshold 0.10, 8-connected blobs, at least 4 m2, mean probability as the score (fw_00 section 4). (2026-11-05, made by the build agent, change freely)
- Matching is greedy IoU 0.3 on rasterised polygons. A second blob in a matched feature stays unmatched. (2026-11-05, made by the build agent, change freely)
- Truth features are assigned to the block that holds their centroid. (2026-11-05, made by the build agent, change freely)
- Under the block bootstrap each copy of a resampled block gets its own truth namespace, so pooled counts are recomputed per draw. (2026-11-05, made by the build agent, change freely)
- Fewer than 15 target blocks adds a permutation null band of the area difference, labelled as a null band and not as an interval. (2026-11-05, made by the build agent, change freely)
- Each window uses its own NAD83(2011) UTM zone (US) or NAD83(CSRS) UTM zone (Canada). Alaska uses Alaska Albers EPSG:3338. (2026-11-05, made by the build agent, change freely)
- A uint8 probability raster is read as DN / 254 with 255 as nodata, the mosaic convention in protocol section 2. (2026-11-05, made by the build agent, change freely)
- The training sampler rejects a whole patch that touches forbidden ground. Normalisation is fitted on training windows only. (2026-11-05, made by the build agent, change freely)
