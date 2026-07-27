# What counts as a good score? WellSight numbers against the literature

**Date:** 2026-07-27
**Question asked:** what values are considered good for these tasks, without
cherry-picking the parameters that flatter us?

Short answer up front. **Our road extraction sits squarely inside the published
band for the same task. Our pit and pad numbers sit below the published band for
comparable features, but almost every published number in that band comes from a
curated test region, and the two studies that also report a random or
large-area test set drop by 20 to 50 points when they do.** Compared like with
like, we are roughly where the field is. Compared to headline numbers, we are
behind. Both statements are true and the second one is the one people quote.

---

## Our numbers, stated once

Scored against hand-drawn annotation withheld from training. Thresholds selected
on val, test scored once frozen.

| Model | Metric | Value |
|---|---|---|
| pit U-Net | R / P / F1 @ IoU 0.3 | 0.754 / 0.620 / 0.681 |
| pad U-Net | R / P / F1 @ IoU 0.3 | 0.882 / 0.547 / 0.675 |
| road U-Net | pixel IoU | 0.581 |
| road vector extraction | completeness / correctness / F1 | 0.695 / 0.824 / 0.754 |
| road vector extraction | **quality** (= TP/(TP+FP+FN)) | **0.605** |

Quality is derived, not measured separately. It is the standard third number in
the road-extraction literature and is what makes our road result comparable.

---

## The strictness scale — read your own number off the curve

Rather than defend one IoU, here is the whole curve. **The probability threshold
is selected once on val at IoU 0.3 and held fixed across every row.** Only the
strictness of what counts as a correct match changes. Re-selecting the operating
point per row would manufacture a flattering curve, which is the thing this
table exists to rule out.

| IoU required | pit R | pit P | pit F1 | pad R | pad P | pad F1 |
|---|---|---|---|---|---|---|
| 0.05 | 0.862 | 0.709 | 0.778 | 0.914 | 0.567 | 0.700 |
| 0.10 | 0.862 | 0.709 | 0.778 | 0.903 | 0.560 | 0.691 |
| 0.20 | 0.831 | 0.684 | 0.750 | 0.892 | 0.553 | 0.683 |
| **0.30** | **0.754** | **0.620** | **0.681** | **0.882** | **0.547** | **0.675** |
| 0.40 | 0.662 | 0.544 | 0.597 | 0.828 | 0.513 | 0.634 |
| 0.50 | 0.585 | 0.481 | 0.528 | 0.742 | 0.460 | 0.568 |
| 0.60 | 0.446 | 0.367 | 0.403 | 0.602 | 0.373 | 0.461 |
| 0.70 | 0.185 | 0.152 | 0.167 | 0.344 | 0.213 | 0.263 |
| 0.80 | 0.031 | 0.025 | 0.028 | 0.097 | 0.060 | 0.074 |
| 0.90 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

Figure: `data/derivatives/eval_9t_instance_precision/iou_strictness_scale_pit_pad_9t.png`
Table: `.../iou_strictness_scale_pit_pad_9t.md`
Source: `.../metrics_9t.csv`, written by `_reeval_instance_precision_9t.py`.

### What the shape says

**Pit precision runs 0.71 down to 0.03 as IoU goes 0.05 to 0.80.** Pad precision
runs 0.57 to 0.06 over the same range. Neither model survives IoU 0.9 at all.

**The two models fail differently, and the curves show it.**

- The **pad** curve is flat from 0.05 to 0.30, losing only 3 points of recall.
  Pads are large, so once a pad is found its outline agrees well enough that
  tightening the requirement changes almost nothing. The collapse starts at 0.40.
- The **pit** curve is already falling by 0.20 and drops 11 points of recall
  between 0.20 and 0.30. Pit floors are ~26 m² median, so a few pixels of
  boundary disagreement move the IoU a lot. Pits are penalised for being small,
  not for being missed.

**This is why floor-inside-rim containment was worth measuring separately.** At
IoU 0.3 the pit model scores recall 0.754. Asked only whether it put a detection
inside the right rim, it locates 126 of 127 held-out pits. The 0.754 is mostly a
delineation score wearing a detection score's clothes.

### Which number to quote

IoU 0.5 is the common default in general object detection, and at 0.5 we report
pit F1 0.528 and pad F1 0.568. IoU 0.3 is more usual in the lidar-archaeology
literature, where features are small and annotation boundaries are subjective.
Quote 0.3 if the comparison is to that literature, quote 0.5 if the comparison is
to computer vision, and **say which one**. Do not quote 0.05.

---

## Roads — we are inside the band

The fair comparison is *forest* roads from lidar DTM. These are unpaved benches
under canopy, which is our problem.

| Source | Completeness | Correctness | Quality |
|---|---|---|---|
| Post-processing algorithm study | 0.844 | 0.716 | 0.632 |
| SVM classification study | 0.750 | 0.630 | 0.520 |
| **WellSight `road_unet_1m_recall` + extraction** | **0.695** | **0.824** | **0.605** |

Ferraz, Mallet & Chehata (2016), already cited in this project, report >80% of
roads correctly retrieved with 10–15% erroneous detections.

We trade completeness for correctness relative to those studies. Our quality
0.605 lands between 0.520 and 0.632. **This is an ordinary, credible result for
the task.**

### The comparison people will wrongly reach for

Optical road-extraction benchmarks report much higher numbers:

| Benchmark | Reported IoU |
|---|---|
| Massachusetts Roads | 0.67–0.75 |
| DeepGlobe Roads | 0.66–0.79 |

Our 0.581 pixel IoU looks poor next to those. **It is not a valid comparison.**
Those are paved roads in RGB satellite imagery, with high contrast, sharp edges,
and no canopy. We are finding 3 m wide unpaved benches in a bare-earth model
built from returns that made it through closed deciduous canopy. If anyone
raises these numbers, that is the answer.

---

## Pits and pads — we are below the band, and the band is soft

The closest published analogues are small anthropogenic features in forested
lidar DTMs.

| Source | Feature | Reported |
|---|---|---|
| Suh et al. 2021 | relict charcoal hearths | **F1 0.955** localised test region |
| Suh et al. 2021 | relict charcoal hearths | **F1 0.86** at town scale |
| Gallwey et al. 2019 | historic mining pits | F1 up to 0.87 |
| Trier et al. / follow-ups | charcoal kilns (Mask R-CNN) | F1 up to 0.84 |
| — | stone walls (FCN, U-Net-like) | F1 0.88 |
| **WellSight pit U-Net** | casing-depression pits | **F1 0.681** |
| **WellSight pad U-Net** | drilling pads | **F1 0.675** |

Taken at face value we are 0.16 to 0.27 F1 behind. Three things qualify that,
and none of them is an excuse to ignore the gap.

**1. Test-set construction dominates these numbers.** Suh et al. report their own
drop, 0.955 to 0.86, purely from moving off a localised test region to town
scale. That is a 10-point penalty for changing nothing but where you score.

**2. The one study that used a genuinely random test set found a much larger
drop.** Verschoof-van der Vaart & Lambers (WODAN2.0) report ~70% on a small
non-random testing set, and on a large random testing set: **~50% barrows, ~46%
Celtic fields, ~18% charcoal kilns.** Charcoal kilns are the closest thing in
that study to our pits, being small circular platforms, and they fell to 0.18.

**3. Our targets may simply be harder.** A charcoal hearth is a deliberately
built, flat, 10–15 m platform. A casing depression is a collapse feature with a
median annotated floor of 26 m². Nothing guarantees our F1 ceiling is theirs.

The honest reading: **against curated-region numbers we are behind; against
large-area or random-test numbers we are competitive.** Our own test set is
closer to the first regime than the second, which is the problem below.

---

## The cherry-picking problem, specifically

This is the part that matters more than the comparison.

### What our protocol already does right

- **Thresholds are selected on val and test is scored once frozen.** Pre-07-02
  numbers selected thresholds on test itself. That is fixed.
- **Ground truth is hand-drawn annotation withheld from training.** No state well
  list is used to score any model.
- **Hand-drawn negatives are scored too.** The road confusion check uses
  annotated `drainage` and `not_road`, not a proxy.
- **Full threshold sweeps are published, not just the best point.** Anyone can
  see the whole curve in `*_threshold_sweep_9t.csv`.

### What still inflates our numbers

Ranked by how much I think each is worth.

1. **We test on held-out blocks inside the training tile, not a held-out tile.**
   This is exactly the "small, non-random testing dataset" regime that WODAN2.0
   showed is worth 20 to 50 points. 9t is one landscape, one survey, one canopy
   condition, one operator's annotation style. **This is the single largest
   unquantified optimism in every number on this page.**
2. **Road chunk leakage.** 485 of 1,220 held-out road chunks (39.8%) share a
   parent road with train chunks. Measured cost ~1.5 points, so small, but it
   means the road numbers are not split the same way pit and pad numbers are.
3. **Single seed everywhere.** No trainer sets `set_determinism` or seeds the
   loader generator. Run-to-run spread is unmeasured, so small differences
   between models may be noise.
4. **Small n, no confidence intervals.** 65 test pits, 93 test pads. A 0.03 F1
   difference on n=65 is not a result.
5. **We report at a chosen threshold at all.** Even a val-selected threshold is a
   choice. Threshold-free summaries do not have this problem.

### What would fix it, cheapest first

| # | Action | Effect |
|---|---|---|
| 1 | Report **average precision / PR-AUC** alongside F1 | Removes threshold choice from the headline entirely |
| 2 | Score on **613590 as a held-out tile**, models untouched | Converts the biggest unknown into a number |
| 3 | Seed the trainers, run 3 seeds, report mean ± spread | Says which differences are real |
| 4 | Add **binomial confidence intervals** on n=65/93 | Stops over-reading small gaps |
| 5 | Split roads by **parent road**, not chunk | Removes the 39.8% leakage |

Item 2 is the one that answers the question being asked. Everything else tunes
the number. A held-out-tile score tells you whether the number transfers, which
is what "is this good?" ultimately means for a method meant to find undocumented
wells somewhere we have not annotated.

---

## The recommendation

Do not quote our pit and pad F1 against Suh's 0.955. Quote it against the
large-area numbers, and say which regime our test set is in. The defensible
sentence today is:

> Road extraction quality of 0.605 is within the published range for forest-road
> detection from lidar (0.52–0.63). Pit and pad F1 near 0.68 sits below
> curated-region results for comparable features, and above the large-random-test
> results reported where those are available. Our test blocks are inside the
> training tile, so these should be treated as an upper bound until scored on a
> held-out tile.

That is not a flattering sentence. It is one that survives a reviewer.

---

## Reproduce

No new computation. Our values are from:
- `data/derivatives/eval_9t_instance_precision/_reeval_9t.json`
- `data/derivatives/tiles/9t/road_unet_1m_recall/road_postproc_best.json`
- `data/derivatives/eval_9t_{pit,pad,road}_thresholds/*_sweep_9t.csv`

Citations logged in `literature/CITATIONS.md`.
