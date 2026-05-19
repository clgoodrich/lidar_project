# Pit Detection Iterations — Index

This folder is the durable record of every pit-detection modeling iteration in the WellSight project. Each doc here is a self-contained lab notebook entry: hypothesis, what was changed, exact parameters, results, honest read, next steps.

The goal is that a reader (including future-you, six months from now) can land here, read top-to-bottom, and understand **what we tried, in what order, and what we learned** — without reading any source code.

## Live leaderboard

→ **[LEADERBOARD.md](LEADERBOARD.md)** — Current head-to-head comparison on the 20 held-out test pits.

## Iterations in order

1. **baseline** — `notebooks/wellsight/pits/_pit_unet_v2.py`, results under `data/derivatives/9t/pit_unet_v2/`. Custom 8 M-param U-Net, 7-channel feature stack, focal loss, checkpoint by `val_loss`. First useful model. See the leaderboard for headline numbers.
2. **[iter 01 — TTA + miou_pit checkpoint](iter_01_tta_miou.md)** — Trivial code changes, big jump in detection. Branch `iter-01-tta-miou`.
3. **[iter 02 — SMP U-Net with ImageNet-pretrained ResNet34](iter_02_smp_pretrained.md)** — Architectural swap. Mixed result: better boundaries, worse coverage. Branch `iter-02-smp-pretrained`.
4. **[iter 03 — Multi-scale + curvature + geomorphons](iter_03_multiscale_feats.md)** — Same architecture as iter 02 but with 11 features instead of 7. Best single model on every boundary-quality metric. Branch `iter-03-multiscale-features`.

## Methodology — what stays constant across iterations

These are the controls that make iteration-to-iteration comparison meaningful:

- **Same training set.** 74 pits in 17 spatial blocks. See [data-prep doc](../pipelines/pit_dataset.md).
- **Same validation set.** 16 pits in 4 blocks. Used to pick the best checkpoint per iteration.
- **Same test set.** 20 pits in 3 blocks. **Never** used for training or checkpoint selection. Only touched at the end of each iteration.
- **Same 9t tile.** All eval runs on the same 9000 × 9000 px @ 0.5 m raster, EPSG:6346.
- **Spatial-block split (12 × 12 grid).** Whole 375 m blocks assigned to train/val/test so two pits at the same site never straddle splits. See [annotations pipeline](../pipelines/annotations.md).
- **Same metrics.** See `Metric definitions` in [LEADERBOARD.md](LEADERBOARD.md).

## How to add an iteration

1. Branch off `main`: `git checkout -b iter-XX-<short_name>`.
2. Write code under `notebooks/wellsight/pits/iter_XX_<short_name>/`.
3. Outputs land under `data/derivatives/9t/iterations/XX_<short_name>/`.
4. Write the iteration's narrative doc here: `docs/iterations/iter_XX_<short_name>.md`. Use the existing iter docs as templates — keep the same section order (Goal/Hypothesis → What changed → Parameters → Results → Honest read → Next steps).
5. Update [LEADERBOARD.md](LEADERBOARD.md) with the new row.
6. Commit + push the branch.
