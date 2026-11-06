# 3.6 decisions

Newest first. One line per decision, with the date and who made it.

- Pad scoring uses `ek.policy_for('pad')` (cutoff 0.525, score order) and the pad reference from `reference.tables_by_task.pad`. The policy is stamped into `ca_pad_primary_<area>.json` (F02). (2026-11-06, review repair by the fix agent, change freely)
- The equipment rule no longer looks at truth pads. It flags model candidates near an equipment object. Model, rule and union are compared at the same K over all candidates. The union puts flagged candidates first (`union_rule flagged_first`, a build default). The union can now lose (G-10). (2026-11-06, review repair by the fix agent, change freely)
- The pad transfer checkpoint is now an explicit config key and is unset. The candidate on disk is `pad/unet_cv5_iso/fold0/best.pt`. (2026-11-06, review repair by the fix agent, change freely)
- Pilot field gates are ground density at least 2 points per m2, the date-gap cap and the developed-land cap. Ranking is pad density, then lower vegetation, then newer NAIP. (2026-11-05, made by the build agent, change freely)
- The USGS 2026 file holds 2,517 deserted and 423 orphan California rows, not the 2,237 and 362 the framework states. The total of 2,940 matches. (2026-11-05, made by the build agent, change freely)
- Label packs hold three PNG chips per block (NAIP RGB, hillshade, nDSM clipped 0 to 12 m). The manifest is checked for forbidden field names. (2026-11-05, made by the build agent, change freely)
- Wells join to the nearest pad when buffered pads overlap. (2026-11-05, made by the build agent, change freely)
- The equipment rule flags a pad when any nDSM object 1.5 to 12 m high and 1 to 400 m2 touches the pad or its 10 m buffer. (2026-11-05, made by the build agent, change freely)
- The Q3 paired comparison resamples blocks of pads, union recall minus model recall. (2026-11-05, made by the build agent, change freely)
- Status is read only by `_ca_status_by_pad.py`, which refuses to run before the S5 primary JSON exists. (2026-11-05, made by the build agent, change freely)
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

## Needs user decision

- Multiplicity. No correction is applied across areas, arms, classes or strata. Decide a family and a correction, or declare each gate a separate question. (listed 2026-11-06)
- Support rule alignment with 3.0. The regional core uses the actual scored support (nodata and masks shrink the K budget and the denominator). The 3.0 reference now treats interior nodata as void under a cap and keeps the full block area. Pick one rule for both. (listed 2026-11-06)
- Undefined bootstrap draws. Any undefined draw now makes a gate inconclusive (expkit SH-01). A tolerated share (`max_undefined`) would have to be declared in the prereg. (listed 2026-11-06)
- The pad transfer checkpoint (one fold or a five-fold ensemble). `model.pad.transfer_checkpoint` is null. (listed 2026-11-06)
- The union rule for the exploratory equipment comparison. `flagged_first` is a build default. (listed 2026-11-06)
