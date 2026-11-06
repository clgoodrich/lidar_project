# 3.5 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Transfer checkpoint (pit and pad). User accepted the default of the current best 9t models. Pit is the five-fold `pit/unet_cv5` ensemble, pad the five-fold `pad/unet_cv5_iso` ensemble, policy fold_mean, sha256 per fold and lineage in `model.<task>`. Results are labelled provisional transfer model. No single 9t model is trained on all 9t ground, so the five folds together stand for it ("take defaults"). Change freely.
- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates F1-L1:pit:oklahoma, F1-L1:pad:oklahoma, secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- 2026-11-06. Void cap. User accepted the default 0.5 (was 0.9 in this config) ("take defaults"). Change freely.
- 2026-11-06. Margin. User accepted the default 0.03 recall ("take defaults"). Change freely.
- 2026-11-06. Useful gain delta_gain. User accepted the default 0.03 recall ("take defaults"). Change freely.
- Arms are scored per class. Pits use the pit policy and pit truth. Pads use the pad policy and pad truth. L0 (a pit model) is scored on pits only (F02, G-13). (2026-11-06, review repair by the fix agent, change freely)
- The label-budget curve scores with task pit (policy cutoff 0.35) and stamps the policy hash per row (F02). (2026-11-06, review repair by the fix agent, change freely)
- L2 fine-tunes with the head re-initialised by declaration (`out.`) and the 7 lidar channel names checked against the checkpoint (G-11). (2026-11-06, review repair by the fix agent, change freely)
- The paired-gain figure no longer fixes the axis at 0 to 1. Negative gains and their intervals are drawn, with a zero line. (2026-11-06, review repair by the fix agent, change freely)
- Paired arms must share the scored support per block. Arms with different masks raise instead of pairing (F07). (2026-11-06, review repair by the fix agent, change freely)
- OK status codes are mapped from the held RBDMS data dictionary. NE means no evidence at location, not new. (2026-11-05, made by the build agent, change freely)
- OK RBDMS has no coordinate-method field. Footage calls are labelled footage, else the count of quarter calls. (2026-11-05, made by the build agent, change freely)
- Creek, Kay and Pawnee are in UTM zone 14 (EPSG:6343), not 15 as the framework assumed. Each window keeps its own zone. (2026-11-05, made by the build agent, change freely)
- OK windows count orphans from both RBDMS (status OR) and the orphan list. The source column keeps them apart. (2026-11-05, made by the build agent, change freely)
- The label-budget plan uses only the valid historical held-out lists. Inner validation (15% of the pool) is drawn once and saved. (2026-11-05, made by the build agent, change freely)
- The label-budget plan and curve are written to this expansion's `results/tables/`, not to `data/9t/results/transfer/`. (2026-11-05, made by the build agent, change freely)
- Trained arms are two-class (background, pit or pad), because the primary truth is all drawn pit and pad features. L0 stays the three-class pit model. (2026-11-05, made by the build agent, change freely)
- One random-search list of 12 trials is drawn once and shared by every arm. Ranges are lr 5e-5 to 1e-3, foreground alpha 0.3 to 0.7, batch 4 or 8, epochs 15, 25 or 40. (2026-11-05, made by the build agent, change freely)
- Co-registration is phase correlation of gradient-magnitude edges (NAIP NIR against lidar slope) per block. The shift is applied as an integer roll. (2026-11-05, made by the build agent, change freely)
- Slope terciles are cut on training-window block means only. (2026-11-05, made by the build agent, change freely)
- Kansas windows are a separate joint-contrast group. They are never pooled with Oklahoma. (2026-11-05, made by the build agent, change freely)
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

- An ensemble cannot seed fine-tuning. `model.<task>.init_checkpoint` is null, so A1/L2 style fine-tuning refuses until one fold is named. (listed 2026-11-06)
- Support rule alignment with 3.0. The regional core uses the actual scored support (nodata and masks shrink the K budget and the denominator). The 3.0 reference now treats interior nodata as void under a cap and keeps the full block area. Pick one rule for both. (listed 2026-11-06)
- A pooled pit-and-pad primary for the one-foreground-class arms needs one declared cutoff for the merged class. Until then G is gated per class under Holm over the two class gains. (listed 2026-11-06)
- Confirm the Holm family. Until a pooled cutoff exists the gain is gated per class, so the family is F1-L1 pit and F1-L1 pad on Oklahoma. (2026-11-06)
