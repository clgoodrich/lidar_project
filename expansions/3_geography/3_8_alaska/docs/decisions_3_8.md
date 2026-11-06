# 3.8 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates E2_rate_mm_yr (one primary, Holm equals the unadjusted rule), secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- Injection recovery adds the known signal to the noisy stack and reads the rate from that one inversion. The old difference against an uninjected inversion cancelled the noise exactly (G-08). The synthetic self-test bias moved from +0.021 to -0.296 mm/yr at noise 0.3 rad. (2026-11-06, review repair by the fix agent, change freely)
- End-of-season rate takes every year's sample from the same calendar month, the latest thaw month up to end_of_season_month present in every year. Months are never mixed across years (season mixing minor). (2026-11-06, review repair by the fix agent, change freely)
- The E2 gate reports the share of undefined bootstrap draws and is inconclusive if any draw is undefined. The permutation band is labelled descriptive. (2026-11-06, review repair by the fix agent, change freely)
- Held lists give 47 Alaska wells after deduplication and 21 sites at 300 m. 27 of the 47 have a blank status. (2026-11-05, made by the build agent, change freely)
- Deduplication drops repeated identifiers, then points within 5 m. (2026-11-05, made by the build agent, change freely)
- Mission wavelengths are c over centre frequency (Sentinel-1 0.0555 m, NISAR L 0.2385 m, ALOS-2 0.2425 m). Check against mission specifications. (2026-11-05, made by the build agent, change freely)
- The inversion is least squares on incremental phase per coherence-mask pattern. A disconnected network keeps the minimum-norm solution. (2026-11-05, made by the build agent, change freely)
- The synthetic injection self-test recovers every amplitude exactly, because the chain has no unwrapping step. A real test must inject before unwrapping. (2026-11-05, made by the build agent, change freely)
- Controls match exactly on land cover, ice class, slope class and frame, then nearest on standardised wetness and road distance. Each control is used once. (2026-11-05, made by the build agent, change freely)
- Sites closer than the variogram range of control rates are merged into one cluster before the site bootstrap. (2026-11-05, made by the build agent, change freely)
- The location-only baseline is a spatially grouped logistic regression on coordinates and matching covariates. (2026-11-05, made by the build agent, change freely)
- The pad footprint for series extraction is the site hull buffered by half the default pad side (50 m). (2026-11-05, made by the build agent, change freely)
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
- `delta_mm_yr` (D-AK1 actionable rate) is still null. It is not a recall margin, so the 0.03 default does not apply. The E2 gate refuses until it is set. (2026-11-06)
