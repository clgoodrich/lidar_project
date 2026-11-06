# 4.5 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Scripts live in this expansion's `src/`, not in `notebooks/wellsight_v2/s7_analysis/`. Outputs go to `results/<run_id>/` here, not `data/9t/results/change/`. Made by the build agent, change freely.
- 2026-11-05. Flight bounds come from metadata first, then a full GPS-time scan, then project-year bounds. A sampled GPS read never sets a bound. Made by the build agent, change freely.
- 2026-11-05. The LAS header creation date is used as an upper bound on the early flight end, because a file cannot predate its points. Made by the build agent, change freely.
- 2026-11-05. Tile bboxes fall back to the US-foot twin CRS when the header CRS misses 9t. The 2006 to 2008 tiles need it. Made by the build agent, change freely.
- 2026-11-05. A well joins a pad within 15 m. Pads within 30 m form one complex, the cluster unit. Made by the build agent, change freely.
- 2026-11-05. A pad is treated when it holds an eligible well and no ambiguous well. Made by the build agent, change freely.
- 2026-11-05. Minimum eligible pads 20 and delta_rate 0.10 are placeholders for the user decisions. Made by the build agent, change freely.
- 2026-11-05. Control pools need every well spudded before the early window end and none plugged before the late flight. Made by the build agent, change freely.
- 2026-11-05. Matching is greedy nearest neighbour without replacement, 1 to 3 controls, caliper 0.5 SD per covariate. Made by the build agent, change freely.
- 2026-11-05. The flag rule imports its constants from `_change_features_9t.py` and reimplements its nested function in `_dod_shared_io.Field`. Made by the build agent, change freely.
- 2026-11-05. Registration is a DEM-level least-squares shift on stable ground. The published chain used point ICP, so S3 recovery is for the DEM chain. Made by the build agent, change freely.
- 2026-11-05. Change field for S4 is `dod_v2_highpass_9t_2m.tif`, the field behind the saved v2 summary. Made by the build agent, change freely.
