# Iter 01 — TTA + miou_pit checkpoint criterion

**Branch:** `iter-01-tta-miou`
**Date:** 2026-05-19
**Status:** Pushed, awaiting PR review
**Outputs:** `data/derivatives/9t/iterations/01_tta_miou/`
**Code:** `notebooks/wellsight/pits/iter_01_tta_miou/`

## Goal / Hypothesis

The baseline (`pit_unet_v2`) had two correctness bugs that didn't break training but throttled real-world performance:

1. The checkpoint criterion was `val_loss`. Because focal loss weights are biased heavily by the abundant background class, `val_loss` can fall while pit-class IoU also falls. The baseline's saved checkpoint (val_loss 0.0008, miou_pit 0.541) was strictly worse than its own ep27 peak (miou_pit 0.584).
2. Inference was a single forward pass with no test-time augmentation. Easy free IoU left on the table.

**Hypothesis:** fixing these two should give +5–10 IoU points with no architecture change, no new data, and ~30 minutes of engineering. A high-leverage cheap baseline upgrade.

## What changed

Two surgical changes to a copy of `_pit_unet_v2.py`, landed under `notebooks/wellsight/pits/iter_01_tta_miou/train.py`. Nothing else moved.

### 1) Save by `miou_pit`, not `val_loss`

```python
# baseline (wrong direction):
if va_loss < best_val:
    best_val = va_loss
    torch.save(..., OUTDIR / "best.pt")

# iter 01:
miou = float(np.nanmean(va_iou[1:]))  # mean of (floor IoU, wall IoU); excludes bg
if miou > best_miou:
    best_miou = miou
    torch.save(..., OUTDIR / "best.pt")
```

### 2) 8-fold test-time augmentation at inference

For each test patch, run 4 rotations × 2 horizontal flips = 8 forward passes, invert the augmentation on the resulting softmax, average. Per-pixel probability becomes the mean of 8 oriented predictions. Implementation:

```python
def tta_predict_batch(model, x):
    outs = []
    for k in range(4):
        for flip in (False, True):
            x_aug = x
            if k: x_aug = torch.rot90(x_aug, k=k, dims=(2, 3))
            if flip: x_aug = torch.flip(x_aug, dims=(3,))
            logits = model(x_aug)
            p = torch.softmax(logits, dim=1)
            if flip: p = torch.flip(p, dims=(3,))
            if k: p = torch.rot90(p, k=-k, dims=(2, 3))
            outs.append(p.float())
    return torch.stack(outs, dim=0).mean(dim=0)
```

Cost: inference is 8× slower per patch, but still finishes in ~5 minutes for the full 9t tile.

## Parameters

Identical to baseline except for the two changes above.

| Setting | Value |
|---|---|
| Architecture | Custom U-Net (4 down levels, base width 32) |
| Params | ~8 M |
| Input channels | 7 (`lrm_25`, `lrm_5`, `slope`, `tpi_05`, `openness_pos`, `openness_neg`, `roughness_11`) |
| Patch size | 256 × 256 px @ 0.5 m (128 m × 128 m on the ground) |
| Output classes | 3 (bg / floor / wall) |
| Loss | FocalCE, alpha = (0.05, 0.475, 0.475), gamma = 2.0 |
| Optimizer | AdamW, lr 1e-3, weight decay 1e-4 |
| Scheduler | Cosine annealing over 40 epochs |
| Epochs | 40 |
| Batch | 16 |
| Augmentation (train) | 4-way rotation + horizontal flip |
| Background sampling | 1 random bg patch per pit-centered patch |
| Checkpoint criterion | **`miou_pit` (changed)** |
| Inference | **8-fold TTA (changed)** |

## Training

40 epochs in ~5 minutes on a single RTX-class GPU. Best checkpoint hit at **ep 20**: val miou(pit) = **0.594** (floor 0.625 / wall 0.564). After ep 20 the training oscillated between 0.42–0.59 with a slight downward trend — characteristic of small val set (16 pits) where a single hard pit can swing the metric by 5+ pts.

The full `train_log.csv` and `run.log` live next to the checkpoint under `data/derivatives/9t/iterations/01_tta_miou/`.

## Results — 20 held-out test pits

| Metric | Baseline | **Iter 01** | Δ |
|---|---:|---:|---:|
| Val miou(pit) — best ckpt | 0.541 | **0.594** | +0.053 |
| Floor pixel IoU (test region) | 0.364 | 0.385 | +0.021 |
| Wall pixel IoU (test region) | 0.402 | 0.446 | +0.044 |
| Mean per-pit IoU | 0.566 | **0.637** | **+0.071** |
| Median per-pit IoU | 0.668 | 0.684 | +0.016 |
| Detected ≥10% recall | 16 / 20 | **20 / 20** | **+4 pits** |
| Local IoU > 0.3 | 16 / 20 | **18 / 20** | +2 |

Per-pit table at `data/derivatives/9t/iterations/01_tta_miou/test_per_pit.csv`. Headline JSON at `test_metrics.json`.

## Honest read

This is the single highest-leverage change in the project so far.

- The "+4 pits detected" is the result that matters operationally. The baseline silently failed on a fifth of the test set; iter 01 finds all of them at >10% recall. That's not a marginal metric move — it's a defect fix.
- Mean per-pit IoU jumped 7 points (0.566 → 0.637). The lift comes partly from the checkpoint fix (a strictly-better starting model) and partly from TTA smoothing out orientation-sensitive predictions on the rim.
- Wall pixel IoU moved more than floor IoU (+4.4 vs +2.1). Walls have sharper rotational signatures than floors, so TTA helps walls disproportionately.
- Median per-pit IoU barely moved (+1.6 pts). The mean climbed harder because the baseline's worst pits (the 4 zero-recall misses) get rescued — that's the kind of mean-pulling-up effect you want.

Cost: <30 minutes of code changes, ~5 minutes of additional inference. Reproducible.

## What's next

- This is the **detection-rate champion** in the leaderboard. Future iterations should hold this 20/20 number unless something explains the regression.
- Next iteration (iter 02) swaps the custom UNet for SMP + ImageNet-pretrained ResNet34. Hypothesis: better-quality boundaries on the easy pits.
- Open follow-up: per-class TTA voting (consensus across the 8 rotations) instead of averaging. Could be more conservative on boundary class.
