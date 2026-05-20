# Pit iter 06 — DEM-only single-channel input (REJECTED EXPERIMENT)

**Branch:** `pit-iter-06-dem-only`
**Date:** 2026-05-20
**Status:** Complete; **rejected** — model never escaped all-background minimum
**Outputs:** `data/derivatives/9t/iterations/06_dem_only/`
**Code:** `notebooks/wellsight/pits/iter_06_dem_only/`

## Goal / Hypothesis

The pit U-Net normally trains on a 7- or 11-channel **feature stack** derived from the DEM (LRMs at multiple scales, slope, TPI, openness ±, roughness, curvature, geomorphons). The question: **can a U-Net learn to find pits from raw elevation alone**, or do those engineered features carry signal the model can't recover on its own?

If the model could learn its own LRM-equivalent features from raw elevation, the hand-crafted feature pipeline would be decorative. If not, the engineered features are doing real work the network can't replicate.

Same architecture as iter 01 (custom UNet, base=32), same train/val/test split, same focal loss, same TTA inference. Only the input differs: 1 channel of raw DEM elevation values (mean 444.5 m, std 30.9 m in TRAIN blocks).

## What changed

Single change: input is `dem_9t_05.tif` directly (z-score normalized), wrapped in a 1-channel "feature stack" so the existing trainer doesn't need modification.

The U-Net's first convolution adapted automatically (`in_ch=1`); total parameter count basically unchanged at 7.76 M (vs 7.76 M for the 7-channel version — the input conv is a tiny fraction of the whole network).

This is also the **first iteration to use the `wsight` consolidated package** as its runner — see `docs/pipelines/wsight_package.md`. The runner is ~120 lines vs ~280 for the older copy-paste iterations.

## Parameters

| Setting | Iter 01 | **Iter 06** |
|---|---|---|
| Input channels | 7 | **1 (raw DEM)** |
| Input normalization | per-channel z-score over TRAIN blocks | same (single channel) |
| Architecture | Custom UNet base=32 | same |
| Params | ~7.8 M | 7.76 M |
| Loss / opt / schedule | FocalCE / AdamW 1e-3 / cosine 40ep | same |
| Augmentation | rot + flip | same |
| Checkpoint criterion | miou(pit) | same |
| Inference | 8-fold TTA | same |

## Training

```
ep   1/40  va_iou c0=0.990  c1=0.000  c2=0.000  miou_pos=0.000
ep  10/40  va_iou c0=0.990  c1=0.000  c2=0.000  miou_pos=0.000
ep  20/40  va_iou c0=0.989  c1=0.000  c2=0.000  miou_pos=0.000
ep  30/40  va_iou c0=0.990  c1=0.000  c2=0.000  miou_pos=0.000
ep  40/40  va_iou c0=0.989  c1=0.000  c2=0.000  miou_pos=0.000
Best val miou: 0.000
```

40 epochs of complete failure. The model collapsed to predicting "background" everywhere and stayed there. Training loss did decrease over time (from ~0.017 to ~0.007) — the model became more confident in its all-background prediction, not less.

## Results — 20 held-out test pits

| Metric | Iter 01 (7-ch) | Iter 03 (11-ch) | **Iter 06 (1-ch DEM)** |
|---|---:|---:|---:|
| Val miou(pit) — best ckpt | 0.594 | **0.639** | **0.000** |
| Floor pixel IoU (test region) | 0.385 | 0.456 | **0.000** |
| Wall pixel IoU (test region) | 0.446 | 0.505 | **0.000** |
| Mean per-pit IoU | 0.637 | 0.648 | **0.000** |
| Detected ≥10% recall | 20/20 | 18/20 | **0/20** |
| Local IoU > 0.3 | 18/20 | 17/20 | **0/20** |

Total collapse. The model finds zero pits.

## Honest read

**Hypothesis falsified, decisively.** The engineered features are not decorative — they carry signal that a U-Net cannot recover from raw DEM in 40 epochs with our training setup.

Why this likely happened:

1. **Scale mismatch.** DEM standard deviation in our TRAIN blocks is 30.9 m. Pit floors are typically 1–3 m below their immediate surroundings. After z-score normalization, the pit-relevant signal is ~0.03–0.1 standard deviations — buried inside the bulk elevation variation across the tile. The engineered LRMs explicitly remove the bulk variation, exposing this local signal.

2. **Receptive-field requirement.** To detect a pit from raw elevation, the network needs to compare a pixel against its immediate neighborhood, which means learning effectively a multi-scale local-relief filter through the conv stack. With only 74 training pits and a strong all-background prior (99.89% of pixels), there's not enough gradient signal for the network to discover this filter from scratch. The engineered features hand it that filter on a plate.

3. **All-background local minimum is strong.** Focal loss with alpha=(0.05, 0.475, 0.475) was specifically designed to make the network *care* about the rare positive classes. Even that wasn't enough. Training loss did fall over time — the model wasn't broken; it was just confidently wrong.

4. **40 epochs may not be enough** for the model to find pits from raw DEM if it ever could. But waiting 200 epochs to see is a poor use of compute when iter 01 nails 20/20 detection in 20 epochs with the engineered stack.

## What the engineered features actually do

Confirming hypothesis from a falsified result:

- **LRMs at 4 scales** (5, 11, 25, 51 px) act as multi-scale band-pass filters that remove regional elevation trend and expose local-relief anomalies — exactly the "pit shows as a circular depression of N meters depth" signal the U-Net needs.
- **Slope** and **roughness** flag pit walls (sharp slope transitions) and floors (uniformly flat).
- **Openness ±** highlights concavities (negative openness) and ridges (positive openness).
- **TPI, curvature, geomorphons** add more terrain-form context.

The U-Net's role is to **combine** these signals into a coherent pit / floor / wall prediction, weighted by context. It's not its role to invent them.

## What's next

- **Iter 06 stays rejected.** Engineered features are load-bearing for this architecture and data size.
- The DEM-only result confirms that any future attempt at "feed the model less and let it learn more" should first try **DEM + a single LRM-25 channel** — i.e., subtract just the most important hand-crafted feature and see if the network can fill the gap. If even that fails, the engineered pipeline is genuinely irreplaceable.
- A separate question — whether a **bigger model** (e.g., DeepLabV3+, HRNet) trained from scratch on more data could learn its own multi-scale local-relief filters — is left for the [BACKLOG](BACKLOG.md). With 110 labels, the answer is almost certainly "no" regardless of architecture.

**Stick with iter 03 / iter 04 / iter 05b moderate_buf5 as the operational layers** — they remain the right choices.
