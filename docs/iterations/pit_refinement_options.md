# Pit U-Net refinement options — literature survey

**Date:** 2026-07-27
**Status:** survey only. Nothing here is implemented yet.
**Trigger:** two observations from QGIS review of `pit_prob_floor.tif` on 9t.
1. Features that clearly are pits carry lower probability than they should.
2. Some pit floors come out fragmented or partial rather than as one blob.

This doc names what the literature offers for each, ranked by expected gain per
unit of work. It is the pit-side analogue of what clDice did for roads.

---

## What the pit model does today

Read from `notebooks/wellsight_v2/pits/_pit_unet_v2.py` and
`notebooks/wellsight_v2/_dl.py` on 2026-07-27.

| Setting | Value |
|---|---|
| Loss | `FocalCE` alone, `gamma=2.0`, `alpha=(0.05, 0.475, 0.475)` |
| Region/overlap term | none |
| Boundary term | none |
| Topology term | none |
| Channels | `lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11` |
| Patch | 256 px at 0.5 m = 128 m |
| Train augmentation | D4 (rot90 x flip), `random_d4` |
| Inference augmentation | **none** — single forward pass, `_dl.py:444` |
| Patch blending | **uniform box mean** over overlaps, `_dl.py:445-449` |

Two of those rows are the direct mechanical causes of the two symptoms.

---

## Symptom 1 — probabilities lower than they should be

### Cause: focal loss is systematically under-confident

We train on focal loss alone with `gamma=2.0`. Focal loss down-weights easy,
confidently-correct pixels. That is the point for class imbalance. The side
effect is that the network stops being rewarded for pushing correct predictions
toward 1.0, so peak softmax values compress downward.

Mukhoti et al. 2020 measured this directly. They found focal-loss models are
better calibrated than cross-entropy models precisely because focal loss is
empirically *under*-confident, which offsets the over-confidence that
overfitting normally produces. Under-confidence is the documented behaviour of
the loss we chose, not a defect in the pits.

This reframes the observation. The model is not failing to see these pits. It is
reporting a number that is not on a calibrated scale. Our own measurement agrees
— every one of the 127 held-out rims has `max_prob >= 0.05`, median 0.846.

### Fix A — temperature scaling (cheapest thing in this document)

Guo et al. 2017. Fit a single scalar `T` on the validation split, divide the
logits by it, re-softmax. One parameter. No retraining. Minutes of compute.

Important property: temperature scaling is monotonic. It cannot change which
pixel outranks which, so it cannot change recall at a *re-tuned* threshold. What
it changes is whether 0.30 means what a reader thinks 0.30 means. Worth doing
for honest reporting and for making thresholds transferable to other tiles.
It will not by itself find a new pit.

### Fix B — test-time augmentation (best effort-to-payoff ratio)

Wang et al. 2019. Run inference over the 8 D4 transforms, invert each, average.
Costs 8x inference and zero training. We already have `random_d4`, so the
transform code exists.

Why it should help us specifically: our features are nadir terrain rasters with
no canonical orientation, which is exactly the equivariance TTA assumes. A real
pit scores high under all 8 views. A directional artifact — a swath seam, a
hillshade-aligned stripe — does not, and averaging suppresses it. Expect both a
confidence lift on true pits and a fragmentation reduction, so this one addresses
both symptoms at once.

### Fix C — replace pure focal with focal + Dice/Tversky

Salehi et al. 2017 introduced the Tversky index, which puts tunable weights
`alpha` and `beta` on false positives and false negatives. Abraham & Khan 2019
added focal modulation on top. Raising `beta` buys recall directly, and the
region term restores the incentive to saturate confident pixels that pure focal
removed.

This is a retrain, so it is a bigger commitment than A or B.

---

## Symptom 2 — fragmented and partial floors

### Cause 2a: uniform patch blending

`predict_full_tile` averages overlapping 256 px patches with **equal weight**.
A prediction made at the extreme edge of a patch, where the network has context
on one side only, is weighted the same as a prediction made at patch centre with
full context. A pit that straddles a patch boundary therefore gets its
probability diluted by the worst-informed view of it.

**Fix:** cosine/Hann feathering — weight each patch by a window that falls to
zero at its edges. Standard practice in tiled inference. Purely an inference
change, no retraining, and it should visibly clean up straight-line
discontinuities in `pit_prob_floor`.

This is worth checking first, because it predicts a specific signature. If the
fragmentation lines up with a 128 m grid, this is the cause.

### Cause 2b: nothing in the loss knows a pit is one connected object

Cross-entropy and focal loss are per-pixel. Splitting a floor into two blobs
costs almost nothing under either. This is the same blind spot clDice fixed for
roads, but roads are tubular and pits are not, so clDice is the wrong tool here.

The right tool is a topology loss on **Betti-0**, the number of connected
components. Hu et al. 2019 built this with persistent homology, making the
topological error differentiable so it trains end to end. Stucki et al. 2024
(Betti matching) made it fast enough to be practical.

For our case the constraint is simple and strong. One annotated pit should
produce exactly one component. Fragmentation is a Betti-0 error and this loss
penalises it by construction.

Cost: highest in this doc. Persistent homology is slow and fiddly. Park it until
the cheap fixes are measured.

### Cause 2c: no boundary supervision

Kervadec et al. 2019 boundary loss integrates over the *interface* between
regions rather than over regions, which is designed for exactly our situation of
tiny foreground against huge background. Pit floors are a fraction of a percent
of the tile. Reported as strongest on small foreground objects.

Complements a region term rather than replacing it.

---

## Channels we do not have

Suh et al. 2021 is the closest published analogue to this project. Relict
charcoal hearths are small circular platform features, under closed deciduous
canopy, mapped from airborne lidar in the northeastern US. They ran a U-Net over
lidar derivatives and reported F1 95.5% locally and 86% at town scale.

Their finding that matters to us: **slope, hillshade, and VAT worked best**, and
the model did better in deciduous forest on slopes above 15 degrees. We have
slope. We do not have VAT.

VAT (Visualization for Archaeological Topography) is a fixed blend of hillshade,
slope, positive openness and sky-view factor. Sky-view factor is Zakšek et al.
2011 and we do not compute it. It is closely related to our positive openness
but not identical, so it is not obviously redundant.

Guyot et al. 2018 likewise fed a multi-visualization stack to a CNN for buried
structures.

Caveat, and it is a real one: this is the same shape of claim as RRIM, which we
already tested and rejected as a model input because it is a pointwise function
of channels we already had. Sky-view factor needs to be checked for the same
redundancy before we spend a training run on it. Correlate it against
`openness_pos` first.

---

## Recommended order

| # | Change | Retrain? | Cost | Targets |
|---|---|---|---|---|
| 1 | Diagnose fragmentation against the 128 m patch grid | no | ~1 h | symptom 2 |
| 2 | Cosine-feathered patch blending | no | ~2 h | symptom 2 |
| 3 | D4 test-time augmentation | no | ~2 h | both |
| 4 | Temperature scaling on val | no | ~1 h | symptom 1 (reporting only) |
| 5 | Sky-view factor, redundancy check vs `openness_pos` | no | ~2 h | — |
| 6 | Focal + Tversky loss | yes | ~1 d | both |
| 7 | Boundary loss term | yes | ~1 d | symptom 2 |
| 8 | Betti-0 topology loss | yes | ~3 d | symptom 2 |

Steps 1 through 4 need no retraining and can be measured on the existing
checkpoint against the 127 held-out rims. That harness already exists in
`notebooks/wellsight_v2/eval/_heldout_rim_containment_9t.py`, so each of these
gets scored the same way and stays comparable.

Do 1 first. It is an hour, and it decides whether the fragmentation is an
inference-stitching bug or a model property. Those need different fixes and it
is worth knowing which before spending a day on a loss function.

---

## Reproduce

Nothing to reproduce yet. Citations are logged in `literature/CITATIONS.md`.

The 0.05 reference raster mentioned during this review:
`data/derivatives/tiles/9t/pit_unet_v2/pit_unet_floor_prob_thr0p05_9t_05.tif`
