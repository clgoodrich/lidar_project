# Four architectures on the same folds — does the network matter?

**Date:** 2026-09-19
**Status:** pit complete (20 folds), pad complete (20 folds), roaddrain not run
**Trainer:** `notebooks/wellsight_v2/s3_train/_arch_compare_9t_1m.py`
**Aggregator:** `notebooks/wellsight_v2/s5_eval/_aggregate_arch_compare_1m.py`
**Grid:** 1 m, 9t. **Channels:** the 7-band stack. **Schedule:** 40 epochs, batch 8, lr 1e-3.

## Why

Every pit and pad number in `LEADERBOARD.md` comes from one architecture — a
plain 4-level U-Net, base 32, about 7.8 M parameters. Nothing on that page says
whether a bigger or a pretrained network would do better. The claim that data is
the bottleneck rather than the model was an assertion, repeated in the leaderboard
commentary, with no controlled run behind it.

This is the controlled run. Four architectures, identical folds, identical
channels, identical loss and schedule. Each rung changes exactly one thing:

| from | to | isolates |
|---|---|---|
| `unet` | `r34_scratch` | encoder **depth** |
| `r34_scratch` | `r34_imagenet` | ImageNet **pretraining** |
| `r34_imagenet` | `unetpp_r34_imagenet` | dense **skip connections** |

## What the number is

Validation IoU of the scored class at each fold's best epoch — floor for pit,
pad for pad. The held-out fold never influences its own best epoch: inner
validation is a *different* fold, `inner = (k + 1) % 5`.

**This is not comparable to the detection numbers in `LEADERBOARD.md`.** Those
are recall and precision at IoU 0.3 after polygonising a probability raster, at
0.5 m. These are segmentation IoU at 1 m. Different grid, different quantity.
Nothing here should be quoted as a recall.

## Result

| target | architecture | params | folds | IoU | sd | min | max |
|---|---|---|---|---|---|---|---|
| pit | U-Net (plain) | 7.8 M | 5 | **0.559** | 0.020 | 0.529 | 0.589 |
| pit | ResNet-34, from scratch | 24.4 M | 5 | 0.528 | 0.025 | 0.491 | 0.560 |
| pit | ResNet-34, ImageNet | 24.4 M | 5 | 0.548 | 0.015 | 0.524 | 0.565 |
| pit | U-Net++, R34 ImageNet | 26.1 M | 5 | **0.561** | 0.020 | 0.533 | 0.590 |
| pad | U-Net (plain) | 7.8 M | 5 | 0.555 | 0.020 | 0.524 | 0.584 |
| pad | ResNet-34, from scratch | 24.4 M | 5 | 0.567 | 0.028 | 0.528 | 0.604 |
| pad | ResNet-34, ImageNet | 24.4 M | 5 | **0.599** | 0.018 | 0.576 | 0.627 |
| pad | U-Net++, R34 ImageNet | 26.1 M | 5 | **0.608** | 0.019 | 0.587 | 0.636 |

### The ladder, one rung at a time

| target | step | delta IoU | pooled sd | verdict |
|---|---|---|---|---|
| pit | deeper encoder | −0.031 | 0.032 | within noise |
| pit | ImageNet pretraining | +0.020 | 0.029 | within noise |
| pit | dense skip connections | +0.013 | 0.025 | within noise |
| pad | deeper encoder | +0.013 | 0.035 | within noise |
| pad | ImageNet pretraining | +0.032 | 0.034 | within noise |
| pad | dense skip connections | +0.009 | 0.026 | within noise |

**No single rung survives its own noise.** But that is not the whole question —
three small same-signed steps can add up while none of them is individually
significant, and reporting only the rungs would hide it.

### End to end

| target | plain U-Net → full stack | delta | pooled sd | |
|---|---|---|---|---|
| pit | 0.559 → 0.561 | **+0.002** | 0.028 | +0.1 sd — within noise |
| pad | 0.555 → 0.608 | **+0.054** | 0.028 | +1.9 sd — suggestive |

## Interpretation

**The two targets answer differently, and that is the result.**

**For pits, architecture is irrelevant.** A 26.1 M-parameter U-Net++ with a
pretrained encoder scores 0.561 against a 7.8 M plain U-Net's 0.559. The gap is
0.002 against a fold sd of 0.020 — nothing. Tripling the parameter count and
adding ImageNet initialisation buys no measurable accuracy. The leaderboard's
standing claim that data is the bottleneck now has a controlled experiment
behind it rather than an assertion, and it holds for the pit model.

**For pads it is not nothing.** The full stack gains 0.054 IoU over the plain
U-Net, about 1.9 sd. Each contributing step is individually inside the noise, so
this is suggestive rather than established — but the direction is consistent
across all three rungs and every one of the five folds of `unetpp_r34_imagenet`
(0.587–0.636) lands above every one of the five plain U-Net folds bar one
(0.524–0.584). That non-overlap is worth more than the sd arithmetic suggests.

Why pads and not pits is a plausible story rather than a measured one: a pad is a
wide textured clearing, which is closer to the kind of regional texture an
ImageNet encoder has features for. A pit is a sub-metre depression whose signal
is local relief, where a deeper encoder's larger receptive field buys little.
Nothing here tests that explanation.

**Two honest qualifications.**

1. **The ImageNet encoder is fed a stack that looks nothing like a photograph.**
   `smp` adapts the first convolution from 3 channels to 7 by repeating and
   rescaling. Whatever ImageNet features survive that on a DEM derivative stack
   is unknown. `r34_scratch` is in the table precisely so pretraining is measured
   rather than assumed, and on pit the pretrained model still fails to reach the
   plain U-Net.
2. **The pad gain costs 92 GPU-minutes against the plain U-Net's 65**, and 3.3×
   the parameters, for a result that is suggestive at five folds.

**Recommendation: keep the plain U-Net for pit, and re-run pad with more seeds.**
The pit answer is settled. The pad answer is the one live lead in this table, and
it needs folds or seeds, not a new architecture.

## What went wrong, and what it cost

`pad/unetpp_r34_imagenet` died on fold 2 with a host-RAM `MemoryError` in the
dataloader (`_dl.py:271`, allocating a 7×256×256 patch), taking folds 3 and 4
with it. `roaddrain/unet` stopped after **1 of 40 epochs** on fold 0.

Neither failure was noticed, because the trainer writes `pooled_metrics.json`
only when one invocation completes every requested fold — so a dead run leaves
no summary file at all, and 37 finished folds sat unscored. The aggregator now
reads the fold directories directly and prints the unfinished ones by name
instead of averaging over whatever happens to be present.

The crashed fold is preserved at
`data/9t/models/_arch_compare/1m/pad/unetpp_r34_imagenet/fold2_CRASHED_oom_2026-09-18/`
rather than deleted — it holds a `best.pt` with no `train_log.csv`, which is
exactly the state that makes a fold look finished in a directory listing.

The trainer's docstring also promises a per-fold `fold_metrics.json` that it
never writes. That is a doc/code mismatch, not a lost result.

## Not done

**Held-out detection scoring.** These are segmentation IoU numbers. Whether a
0.002 IoU difference moves recall at IoU 0.3 is unmeasured, and the leaderboard
speaks in detection terms. Added to `BACKLOG.md`.

**roaddrain.** One fold, one epoch. The row does not exist.

## Reproduce

```bash
# train one arm (repeat per target x arch)
python notebooks/wellsight_v2/s3_train/_arch_compare_9t_1m.py \
    --target pit --arch unetpp_r34_imagenet --folds 5
# score everything on disk
python notebooks/wellsight_v2/s5_eval/_aggregate_arch_compare_1m.py
```

## Outputs

`data/9t/results/arch_compare_1m/`

- `arch_compare_per_fold_9t_1m.csv`
- `arch_compare_summary_9t_1m.csv`
- `arch_compare_ladder_9t_1m.csv`
- `arch_compare_unfinished_9t_1m.json`

`docs/presentation/figures_30to45min/4_models/arch_compare_four_architectures_9t_1m.png`

Checkpoints: `data/9t/models/_arch_compare/1m/<target>/<arch>/fold<k>/best.pt`
(gitignored under `data/**/models/**/*.pt`).
