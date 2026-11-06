# 3.7 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Transfer checkpoint (pit and pad). User accepted the default of the current best 9t models. Pit is the five-fold `pit/unet_cv5` ensemble, pad the five-fold `pad/unet_cv5_iso` ensemble, policy fold_mean, sha256 per fold and lineage in `model.<task>`. Results are labelled provisional transfer model. No single 9t model is trained on all 9t ground, so the five folds together stand for it ("take defaults"). Change freely.
- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates A0 pit and pad in ab1, bc1 and on1 (six gates), secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- 2026-11-06. Void cap. User accepted the default 0.5 (was 0.9 in this config) ("take defaults"). Change freely.
- 2026-11-06. Margin per province. User accepted the default 0.03 recall ("take defaults"). Change freely.
- The shifted-set null wraps records around the footprint bounding box (torus shift). Count and composition stay fixed. At 100 spread records all 999 shifts are now kept (0 before). If fewer than n_shifts survive on an irregular footprint the excess is reported as not computable with NaN values (G-09). (2026-11-06, review repair by the fix agent, change freely)
- Province scoring inherits the fixed core (task policy, support rule, id mapping, gates). (2026-11-06, review repair by the fix agent, change freely)
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

## Needs user decision

- Support rule alignment with 3.0. The regional core uses the actual scored support (nodata and masks shrink the K budget and the denominator). The 3.0 reference now treats interior nodata as void under a cap and keeps the full block area. Pick one rule for both. (listed 2026-11-06)
- Confirm the Holm family. The fix agent declared six gates (pit and pad in each province). If one class is the primary per province the family shrinks to three. (2026-11-06)
