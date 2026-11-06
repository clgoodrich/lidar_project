# 3.4 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Transfer checkpoint (pit and pad). User accepted the default of the current best 9t models. Pit is the five-fold `pit/unet_cv5` ensemble, pad the five-fold `pad/unet_cv5_iso` ensemble, policy fold_mean, sha256 per fold and lineage in `model.<task>`. Results are labelled provisional transfer model. No single 9t model is trained on all 9t ground, so the five folds together stand for it ("take defaults"). Change freely.
- 2026-11-06. Multiplicity. User accepted the default Holm over the declared primary gates A0:pit:la_caddo, A0:pit:tx_east (A1 is its own family q2_family), secondaries and sensitivities reported and never gated (`_transfer_holm_gate.py`) ("take defaults"). Change freely.
- 2026-11-06. Undefined bootstrap draws. User accepted the default max_undefined 0 (any undefined draw makes the gate inconclusive) ("take defaults"). Change freely.
- 2026-11-06. Void cap. User accepted the default 0.5 (was 0.9 in this config) ("take defaults"). Change freely.
- 2026-11-06. Margin. User accepted the default 0.03 recall ("take defaults"). Change freely.
- 2026-11-06. Useful gain delta_gain. User accepted the default 0.03 recall ("take defaults"). Change freely.
- Regional scoring takes cutoff, minimum area, IoU and match order only from `ek.policy_for(task, mode)` (pit 0.35, pad 0.525, score order). `score_raster` needs a task. The old 0.10 default is gone. The policy dict and hash are stamped into every score output (F02, G-01). (2026-11-06, review repair by the fix agent, change freely)
- Extraction is 4-connected, the same as the 3.0 polygoniser. Candidates and truth are assigned by centroid. Candidates outside scored blocks are removed before matching. The 3.0 dedupe rule is applied (F02, G-03). (2026-11-06, review repair by the fix agent, change freely)
- Support rule, one policy. A block's scored support is its finite, unmasked cells. The K budget and the truth denominator use that support. Truth counts only when its centroid lies on a supported cell of an eligible block. Blocks with zero support are dropped and listed (F07). (2026-11-06, review repair by the fix agent, change freely)
- Water polygons from S4 (`xfer_water_mask_<area>.gpkg`) are removed from the support at scoring time. Blocks with unknown void are ineligible when a void cap is declared. The old fillna(0) is gone (G-13). (2026-11-06, review repair by the fix agent, change freely)
- Core `score` takes `--task pit|pad`. Only truth of that class is scored, against the reference of that task (`reference.tables_by_task`). `--classes pit,pad` is gone (G-13). (2026-11-06, review repair by the fix agent, change freely)
- Pooled recall ranks by score, area, numeric blob id, then draw occurrence. Hits are credited to the truth's own block and only denominator truth can be a hit (F09, F10, G-04). (2026-11-06, review repair by the fix agent, change freely)
- External truth ids are mapped to internal labels 1..n. Zero, negative and string ids work. Duplicate ids raise (F10). (2026-11-06, review repair by the fix agent, change freely)
- Areas need a projected metre CRS (a compound CRS with a metre horizontal part passes), no rotation, cell area |a*e|. Mask rasters must match the full affine (F11). (2026-11-06, review repair by the fix agent, change freely)
- Fine-tuning loads a checkpoint only through `init_from_checkpoint`. Layers that cannot load must be in an explicit allow-list (A1 re-initialises `d1.0.` for the 8-band stack). Channel names must match the checkpoint when the first layer loads. The record goes into best.pt as `init_load` (G-11). (2026-11-06, review repair by the fix agent, change freely)
- Gates. Fewer than 15 blocks gives inconclusive. The permutation band is reported as descriptive and never gates. Any undefined bootstrap draw gives inconclusive, and the share is reported. (2026-11-06, review repair by the fix agent, change freely)
- 9t parity run. The 9t pit mosaic (115 blocks with data) through the fixed core gives recall 0.9165 at K 40, equal to the current 3.0 scorer on the same raster. The old core gave 0.5785. On the 3.0 filled raster (144 blocks) the core gives 0.9463, equal to the current 3.0 reference tables. Both differences are 0.0000. Output `results/tables/xfer_core_parity_recall_9t.json`. (2026-11-06, review repair by the fix agent, change freely)
- S0 uses the held Permian RRC sample (`data/_experiments/permian_sample/rrc_orphan_wells_permian.gpkg`) until layer 2 is paged. It has no reliability field. (2026-11-05, made by the build agent, change freely)
- RRC field names in `RRC_COLMAP` are guesses. Edit them after reading the real layer schema. (2026-11-05, made by the build agent, change freely)
- Window centres come from `lidar_win_windows_us.csv`. Caddo is -93.962, 32.8519 there, not -93.9433, 32.7439 as in the plan table from the pilot list. (2026-11-05, made by the build agent, change freely)
- East Texas counties with no rows in the USGS county table enter the rule with zero density, so they are listed and not dropped. (2026-11-05, made by the build agent, change freely)
- The 9t pit depth reference is median DEM in a 5 m ring minus the floor minimum, over the `pit_inside` layer (503 polygons on disk). (2026-11-05, made by the build agent, change freely)
- The 9t depth table is written to this expansion's `results/tables/`, not to `data/9t/`, to keep the build inside the expansion folder. (2026-11-05, made by the build agent, change freely)
- Minimum detectable depth detrends with a 21-cell (10.5 m) median filter before the robust SD on NLCD 81 and 82 cells. (2026-11-05, made by the build agent, change freely)
- Wetland share is the larger of the NLCD 90 and 95 share and the NWI polygon share. Blocks with water share 0.5 or more are ineligible. (2026-11-05, made by the build agent, change freely)
- Wet strata cut points 0.1 and 0.5 and void strata cut points 0.45 and 0.7 are placeholders in the prereg block. (2026-11-05, made by the build agent, change freely)
- Relief normalisation divides lrm_25, lrm_5 and tpi_05 by block relief (p95 minus p5 of the plane residual, floor 0.25 m) and adds a plane-removed elevation band. (2026-11-05, made by the build agent, change freely)
- A1 fine-tunes all layers from the isolated pit checkpoint at lr 1e-4 for 20 epochs, three seeds. These are defaults to be fixed in the A1 prereg. (2026-11-05, made by the build agent, change freely)
- The shared transfer code lives in `3_4_gulf_texas/src/_geo_transfer_core.py`. Regions 3.5 to 3.8 import it by a relative path. (2026-11-05, made by the build agent, change freely)
- Stages every region shares are subcommands of the core (cover, density, blocks, derive, infer, score, width, agree, prereg) instead of one copy per region. (2026-11-05, made by the build agent, change freely)
- Assumed input paths and schemas live in `src/config_<id>.json`. A missing input stops the script with a message naming it. (2026-11-05, made by the build agent, change freely)
- User-only values (margins, gains, caps, floors) are null in the config. Scoring scripts refuse to run until they are set. (2026-11-05, made by the build agent, change freely)
- Scripts write run outputs only to `data/<area>/` or to this expansion folder. The build runs wrote only to this expansion folder. (2026-11-05, made by the build agent, change freely)
- Candidate extraction is threshold 0.10, 8-connected blobs, at least 4 m2, mean probability as the score (fw_00 section 4). (2026-11-05, made by the build agent, change freely) Superseded 2026-11-06, see the review repair entries above.
- Matching is greedy IoU 0.3 on rasterised polygons. A second blob in a matched feature stays unmatched. (2026-11-05, made by the build agent, change freely) Superseded 2026-11-06, see the review repair entries above.
- Truth features are assigned to the block that holds their centroid. (2026-11-05, made by the build agent, change freely)
- Under the block bootstrap each copy of a resampled block gets its own truth namespace, so pooled counts are recomputed per draw. (2026-11-05, made by the build agent, change freely) Superseded 2026-11-06, see the review repair entries above.
- Fewer than 15 target blocks adds a permutation null band of the area difference, labelled as a null band and not as an interval. (2026-11-05, made by the build agent, change freely) Superseded 2026-11-06, see the review repair entries above.
- Each window uses its own NAD83(2011) UTM zone (US) or NAD83(CSRS) UTM zone (Canada). Alaska uses Alaska Albers EPSG:3338. (2026-11-05, made by the build agent, change freely)
- A uint8 probability raster is read as DN / 254 with 255 as nodata, the mosaic convention in protocol section 2. (2026-11-05, made by the build agent, change freely)
- The training sampler rejects a whole patch that touches forbidden ground. Normalisation is fitted on training windows only. (2026-11-05, made by the build agent, change freely)

## Needs user decision

- An ensemble cannot seed fine-tuning. `model.<task>.init_checkpoint` is null, so A1/L2 style fine-tuning refuses until one fold is named. (listed 2026-11-06)
- Support rule alignment with 3.0. The regional core uses the actual scored support (nodata and masks shrink the K budget and the denominator). The 3.0 reference now treats interior nodata as void under a cap and keeps the full block area. Pick one rule for both. (listed 2026-11-06)
- Confirm the Holm family. The fix agent read fw_3_4 section 7 as A0 pit on T1 and T2. Pad rows are reported, not gated. Add A0 pad gates to `multiplicity.family` if pads are primary too. (2026-11-06)
