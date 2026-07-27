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
