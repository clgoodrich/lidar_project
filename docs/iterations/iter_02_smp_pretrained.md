# Iter 02 — SMP U-Net with ImageNet-pretrained ResNet34 encoder

**Branch:** `iter-02-smp-pretrained`
**Date:** 2026-05-19
**Status:** Pushed, awaiting PR review
**Outputs:** `data/derivatives/9t/iterations/02_smp_pretrained/`
**Code:** `notebooks/wellsight/pits/iter_02_smp_pretrained/`

## Goal / Hypothesis

The custom U-Net from baseline / iter 01 has ~8 M parameters and is trained from scratch on 74 pits. ImageNet has 1.28 M labeled images and a decade of community-tuned encoders. **Hypothesis:** swap the encoder for a `segmentation_models_pytorch` U-Net with an ImageNet-pretrained ResNet34, keep everything else from iter 01, and the pretrained features should give us +5–10 IoU pts roughly for free.

Risk noted up front: ImageNet pretraining is on 3-channel RGB photographs of cats/cars/buildings. Our input is 7 channels of geomorphological derivatives, not RGB photos. SMP handles the channel count by averaging the pretrained first-conv weights across channels and re-tiling, but the *semantic* prior in those weights is texture-heavy in a way that may or may not transfer to LiDAR.

## What changed

One change relative to iter 01: model architecture.

```python
# iter 01:
model = UNet(in_ch=7, n_classes=3, base=32)   # ~8 M params, random init

# iter 02:
model = smp.Unet(
    encoder_name="resnet34",
    encoder_weights="imagenet",
    in_channels=7,
    classes=3,
)                                              # ~24 M params, ImageNet-init encoder
```

Everything else — data, loss, optimizer, schedule, TTA, checkpoint criterion — is identical to iter 01. The dataset, sampler, focal loss, and trainer are imported from `_pit_unet_v2.py` so the only moving part is the model class.

Added dependency: `segmentation_models_pytorch` (installed via pip).

## Parameters

| Setting | Iter 01 | **Iter 02** |
|---|---|---|
| Architecture | Custom 4-level U-Net, base 32 | **SMP U-Net, ResNet34 encoder** |
| Encoder init | Random | **ImageNet** |
| Params | ~8 M | **~24.5 M** |
| Encoder downsampling | 16× max | **32× max** |
| In-channels | 7 | 7 |
| Patch size | 256 × 256 px @ 0.5 m | 256 × 256 px @ 0.5 m |
| Loss / opt / schedule | FocalCE / AdamW 1e-3 / cosine 40ep | same |
| Augmentation (train) | rot + flip | same |
| Checkpoint criterion | miou(pit) | same |
| Inference | 8-fold TTA | same |

Output classes, focal alpha, gamma, batch size, train/val/test split: all unchanged.

## Training

40 epochs in ~4 minutes (faster per-epoch than iter 01 because GPU utilization is better at 24 M params with batch 16). Initial 1–2 epochs of "all background" output — common with high-LR fine-tuning of a pretrained backbone — then rapid lift-off:

- ep 4: miou(pit) = 0.331 (iter 01 was ~0.10 at same epoch)
- ep 8: miou(pit) = 0.598 (iter 01 didn't hit that until ep 20)
- ep 15: best @ miou(pit) = **0.617**

Cosine schedule didn't help much past ep 15 — the model converged early and oscillated.

## Results — 20 held-out test pits

| Metric | Iter 01 | **Iter 02** | Δ vs Iter 01 |
|---|---:|---:|---:|
| Val miou(pit) — best ckpt | 0.594 | **0.617** | +0.023 |
| Floor pixel IoU (test region) | 0.385 | **0.440** | **+0.055** |
| Wall pixel IoU (test region) | 0.446 | **0.465** | +0.019 |
| Mean per-pit IoU | **0.637** | 0.564 | **−0.073** |
| Median per-pit IoU | 0.684 | **0.696** | +0.012 |
| Detected ≥10% recall | **20 / 20** | 16 / 20 | **−4 pits** |
| Local IoU > 0.3 | **18 / 20** | 16 / 20 | −2 |

This is a **tradeoff, not a clean win**.

## Honest read

Iter 02 is genuinely better at the easy pits — pixel IoUs and median per-pit IoU all moved up. The pretrained encoder produces sharper boundaries where it sees a pit.

But it **misses 4 of the 20 test pits** that iter 01 catches. The mean per-pit IoU drops 7 pts because of those 4 zeros pulling the average down.

Why?

1. **ResNet34's stem is aggressive.** First block is stride-2, then a max-pool stride-2 — the input is down to 64×64 before any meaningful processing. Subtle 5–15 m shallow pits at 0.5 m/px (which is 10–30 px wide) lose detail fast.
2. **ImageNet semantics are textural.** Pretrained features know about cat fur and asphalt; they're not specialized for "concave depression in terrain." For a clearly-rimmed pit those features still help (sharp edges, gradients). For a shallow asymmetric pit barely distinguishable from the surrounding hillslope, they don't.
3. **Total receptive field at the bottleneck.** 32× downsampling on 256 px input means 8×8 bottleneck — fine for plats, tight for small pits.

The misses are not random — they correlate with shallow / asymmetric / low-contrast pits. (Per-pit table at `data/derivatives/9t/iterations/02_smp_pretrained/test_per_pit.csv` confirms.)

## What's next

Iter 02 is the **boundary-quality champion** but doesn't replace iter 01. Two clear next moves:

1. **Iter 03 — give SMP the explicit geomorphological signal it lacks.** Add multi-scale LRM (5/11/25/51), DTM curvature (Laplacian), and a geomorphons terrain classifier as input channels. Same SMP architecture, just feed it features that already encode "this is a pit-like depression." Hypothesis: closes the missed-pit gap without losing iter 02's boundary quality.
2. **Ensemble iter 01 + iter 02 — combine the strengths.** Average or max the two softmax outputs at inference. Iter 01 contributes detection, iter 02 contributes boundaries. Probably the strongest single number we can post without new labels. Considered as a follow-up after iter 03 lands.

Decision for next iteration: do (1) first because it generates a real new model worth comparing on its own. (2) is bookkeeping that can happen later from already-saved checkpoints.
