# NISAR frozen held-out test on 613590, pre-registration (2026-10-27)

This file was written and committed before any 613590 sample was scored. Its purpose is to fix the model, the test set, the predictions and the decision rule in advance.

## Question

Does a NISAR model trained on 9t transfer to a different tile, and does it add to a lidar model there?

## What is frozen

- **Training data.** The 9t pit samples of the default design, `data/9t/derived/nisar_features_5m/nisar_pit_samples_9t_slc.npz`, all rows. No 613590 row is ever used to train, tune or select anything.
- **Model.** `C.oof_probs` settings in `notebooks/wellsight_v2/s5_eval/_nisar_feat_common.py`: histogram gradient boosting (depth 3, learning rate 0.06, 200 iterations, L2 1.0, minimum leaf 40, balanced class weight). Bands more than 20% missing in either training class are dropped. The rest are median-imputed with training medians.
- **Feature sets.** (a) rich lidar baseline (control and lidartex bands), (b) NISAR bands, (c) NISAR plus rich lidar baseline, (d) simple lidar baseline. Only bands present on both tiles are used. A band missing on 613590 is removed from every set.
- **No map coordinates.** They cannot transfer between tiles.

## Test set

- 36 annotated pit rims (`pit_outside`) inside the 613590 NISAR window, scored on the lidar-placed SLC stack (tag `613590_slc`).
- Decoys from the same scorer and the same default design (10 per pit, 4 or 9 pixels, matched on cover and slope, at least 100 m from any pit, pad, road or DEP well).
- **Pads cannot be tested.** The tile has no annotated pad polygons (0 of 995). This test says nothing about pads.
- 613590 has 8, 11 and 6 usable dates on tracks 26, 90 and 162. 9t has 8, 11 and 14. Track 162 is therefore weaker on 613590.

## Predictions, written before the run

1. NISAR alone will score between 0.50 and 0.75.
2. The gate will fail. NISAR plus the rich lidar baseline will not beat the rich lidar baseline by 0.05.
3. The rich lidar baseline will score above 0.80.

## Decision rule

- The gate passes only if (c) minus (a) is at least 0.05 and the lower end of a block-bootstrap 95% interval of that difference is above 0.
- Otherwise the result is "no gain".
- With 36 pits the interval will be wide. A wide interval that spans zero is reported as inconclusive, not as support for either side.

## Procedure

1. `NISAR_AREA=613590 NISAR_STACK=slc TARGET=pit python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py` writes the 613590 samples.
2. `python notebooks/wellsight_v2/s5_eval/_nisar_feat_heldout_9t.py` trains on 9t and scores 613590.
3. One run. A technical failure may be fixed and re-run. No change of model, band set or decoy design after seeing a score.

Results go to `docs/iterations/nisar_checks_9t.md`.
