# road_bold_vs_faint — the faint variety was absent from the labels, and the model is blind to it

**Date:** 2026-07-29, updated 2026-07-30
· **Script:** `notebooks/wellsight_v2/s7_analysis/_bold_vs_faint_roads.py`
· **Outputs:** `data/derivatives/experiments/road_morphology_bins/bold_vs_faint_*`
· **Supersedes the central conclusion of** [[road_morphology_bins]]
· **Related:** [[road_unet_1m_recall]], [[road_active_learning_loop]], [[road_sweep_202607]]

## Goal

The user hand-labelled exemplars of the two road varieties they see —
`annotations/bold_roads.shp` (8 lines, 1.79 km) and
`annotations/faint_roads.shp` (21 lines, 2.35 km) — and asked for a comparison
of the roads *and their surroundings*.

This is also a direct test of [[road_morphology_bins]], which concluded from
unsupervised clustering that 9t roads are one width and that their incision
depth is a continuum rather than two populations.

## Headline: that earlier conclusion was wrong, and here is why

**Zero of the 21 faint roads exist in `roads.shp`.**

| | coverage by `roads.shp` (5 m buffer) | median distance to nearest annotated road |
|---|---|---|
| bold (n=8) | **8/8**, 0.98–1.00 | 0.0 m |
| faint (n=21) | **0/21**, 0.00 for every line | **87.4 m** |

[[road_morphology_bins]] analysed `roads.shp`. That file contains only the bold
variety. It found one population because only one population was in the file.
**It measured the annotated population and mistook it for the road
population.** The "one width, depth is a continuum" result stands as a
description of the *annotated* roads and is void as a description of the roads.

## The model is blind, not weak

Sampled from `tiles/9t/road_unet_1m_recall/road_prob.tif`:

| | P(road) mean | median | ≥ 0.5 | range |
|---|---|---|---|---|
| **bold** | 0.775 | 0.806 | **8/8 (100%)** | 0.57 – 0.89 |
| **faint** | **0.032** | 0.022 | **0/21 (0%)** | 0.00 – 0.09 |

No overlap. The best faint road (0.09) scores six times lower than the worst
bold road (0.57). P(drainage) is ~0 for both, so these are not being
misclassified as drainage — they are simply not detected as anything.

**Every road metric this project has published is conditional on the bold
class.** The 0.754 extraction F1, the recall figures in [[road_unet_1m_recall]],
and the α-tuning in [[road_recall_alpha_fix]] were all scored against
`roads.shp`. None of them say anything about the faint variety.

This also explains the active-learning loop: on 613590 the user drew **373 added
roads / 37.68 km** the model had missed. Those are almost certainly this class.

## What separates them — the road itself

Road-level statistics, n = 8 vs 21, Mann-Whitney with Benjamini-Hochberg
correction. **25 of 65 features significant at q < 0.05**, six at perfect
separation (|Cliff's δ| = 1.00).

| feature | bold | faint | δ | q |
|---|---|---|---|---|
| `opos_road` (positive openness on tread) | 85.76 | 88.47 | **−1.00** | <0.05 |
| `lrm25_road` (25 m local relief) | −0.127 | −0.023 | **−1.00** | <0.05 |
| `rough_contrast` | +0.129 | 0.000 | **+1.00** | <0.05 |
| `lrm5_road` | −0.010 | −0.003 | −0.98 | <0.05 |
| `tpi15_road` | −0.178 | −0.024 | −0.96 | <0.05 |
| `incision_depth_m` | **0.547** | **0.181** | +0.96 | <0.05 |
| `slope_contrast` (road − context) | +2.39° | −0.44° | +0.95 | <0.05 |
| `relief_amp_m` | 0.576 | 0.233 | +0.80 | <0.05 |
| `length_m` | 222 | 119 | +0.85 | <0.05 |

A bold road is a **3× deeper notch with a sharp shoulder**. The transect profile
shows bold spiking to 7.8° at the shoulder against a 2.7° background, while
faint barely lifts off its own 4° background. Negative openness dips to 86.4 on
bold and stays flat at ~88.7 on faint — visually the single cleanest
discriminator.

Note where the faint median sits: **incision 0.181 m is below the p5 (0.23 m) of
the entire annotated population** measured in [[road_morphology_bins]]. The
faint class is not the low tail of the annotated distribution — it is outside
it.

## What separates them — the surroundings

This is what the question asked for, and it is as strong as the cross-section.

| context feature | bold | faint | δ | q |
|---|---|---|---|---|
| `road_density_100m_km` | **0.716 km** | **0.104 km** | **+1.00** | <0.05 |
| `dist_pad_m` | **0 m** | **126 m** | −0.94 | <0.05 |
| `canopy_cover_context` (CHM > 2 m, 25–60 m) | **0.155** | **0.310** | −0.60 | 0.040 |
| context slope (25–60 m band) | 2.7° | 4.0° | — | — |

**Bold roads live in open, pad-adjacent, road-dense country.** Every one touches
an annotated pad. They sit in clusters with 7× the surrounding road length, in
landscape with half the canopy cover.

**Faint roads are isolated in closed forest.** 126 m from the nearest pad, in
sparse road networks, under twice the canopy, on slightly steeper and more
uniform hillslopes.

So the two varieties differ in *setting* as much as in *construction*. That is a
useful detection signal and a serious confound — see below.

## Contrast against the surroundings, normalised — the sharpest framing

A raw `road - context` difference conflates a strong feature with a quiet
neighbourhood. The honest question is how many **local sigma** the road departs
by, using the context band's own robust spread (MAD x 1.4826) as the
denominator. That is what "stands out" means, and it is effectively what a
detector sees.

| channel | bold (sigma) | faint (sigma) | delta | q |
|---|---|---|---|---|
| `opos_zcontrast` | **-5.21** | **-0.29** | -1.00 | <0.05 |
| `lrm25_zcontrast` | -2.56 | -0.47 | -1.00 | <0.05 |
| `tpi15_zcontrast` | -2.46 | -0.32 | -0.93 | <0.05 |
| `rough_zcontrast` | +1.88 | 0.00 | +0.99 | <0.05 |
| `slope_zcontrast` | +1.56 | -0.28 | +0.95 | <0.05 |
| `relief10_zcontrast` | +0.95 | -0.34 | +0.81 | <0.05 |
| `oneg_zcontrast` | -1.44 | +0.03 | -0.79 | <0.05 |

**A faint road departs from its surroundings by less than half a local sigma on
every channel.** Bold roads clear 5 sigma in positive openness. This is the
cleanest available statement of what "faint" is, and it says the signal is
genuinely absent rather than merely below a badly-chosen threshold.

### The surroundings are noisier too — a double penalty

The context band's own spread differs between the classes:

| context spread (MAD, 25-60 m) | bold | faint | delta | q |
|---|---|---|---|---|
| `dsm_ctx_spread` | 1.62 | **3.79** | -0.65 | 0.018 |
| `chm_ctx_spread` | 0.024 | **0.059** | -0.67 | 0.016 |
| `rough_ctx_spread` | 0.000 | 0.079 | -0.47 | 0.091 |
| `slope_ctx_spread` | 1.62 | 2.05 | -0.43 | 0.127 |
| `dem_ctx_spread` | 1.22 | 2.00 | -0.43 | 0.127 |

Faint roads carry a **weaker signal into a noisier neighbourhood** — more than
twice the surface (DSM/CHM) variability, consistent with the denser canopy
already measured. Both terms of the signal-to-noise ratio work against them.
Only the DSM and CHM spreads survive BH correction at n=8 vs 21; the terrain
spreads trend the same way but do not.

### The near band (5-15 m) — the disturbance footprint

Reported for completeness; it was computed but omitted from the first pass.

| feature | bold | faint | delta | q |
|---|---|---|---|---|
| `oneg_near` | 88.28 | 88.87 | -0.76 | 0.003 |
| `opos_near` | 88.10 | 88.77 | -0.76 | 0.003 |
| `canopy_cover_near` | 0.214 | 0.333 | -0.46 | 0.130 |

Openness still separates at 5-15 m out, so a bold road's disturbance extends
beyond its tread into the shoulder zone. Nothing else in this band survives
correction.

### Two channels to distrust

- **`roughness_11` is quantised.** Only 1,032 unique values across 81 M cells,
  on a sqrt(k) ladder (0, 0.0913, 0.1291, 0.1581, 0.1826, ...) with the tile
  median sitting on the 4th rung. The bold-vs-faint difference of 0.129 vs 0.000
  is a **single rung**, so `rough_contrast`'s |delta| = 1.00 partly reflects a
  coarse instrument rather than a wide gap. Direction is trustworthy, magnitude
  is not. `openness_pos` by contrast has 2.2 M unique values and is genuinely
  continuous.
- **`chm_zcontrast` = 402 for bold** is division by a near-zero CHM MAD (0.024),
  not a real effect. Same zero-inflation problem noted above. Use
  `canopy_cover_*` instead.
- `gdens` is 42% nodata with a context spread of exactly 0 — it carries no
  information here and should be dropped from this analysis.

## Applying it: layers for the 9t annotated network

Script: `notebooks/wellsight_v2/s7_analysis/_classify_9t_roads_bold_faint.py`.

### First attempt was wrong — the user said the map "looked random", and it was

The first version scored **whole roads** and forced a binary label at the
midpoint threshold. Two measurements explain why that produced visual noise:

- **Within-road variability exceeds between-road variability.** Pooled
  within-road SD of the score is **2.230** against a between-road SD of
  **1.892** — ICC **0.419**. The median road's own transects vote only **57%
  bold**, and 17% of roads are a 40-60% internal split. "This road is bold" is
  not a well-posed statement; a haul road that degrades into a trace got one
  label for both halves.
- **The threshold sat in the mode.** 47% of roads fell within 1 sigma of the
  boundary and 22% within 0.5 sigma. 18% fell in the *gap between the two
  exemplar ranges* and were forced to a side with no evidence either way.

### Second attempt also looked random, for a deeper reason

Segment scoring (50 m segments, transects every 5 m) fixed the *unit* but the
map still read as noise. Two measurements found why:

- **The cut points came entirely from the exemplars.** `bold_hi` was the bold
  exemplars' maximum and `faint_lo` the faint exemplars' minimum. Nothing in the
  pipeline ever asked how `roads.shp` itself was distributed.
- **So they landed inside the mode.** `bold_hi` = -1.99 sat at **percentile
  52.8** of the network and `faint_lo` = -1.09 at **percentile 71.9**, at 86%
  and 93% of peak histogram density. Adjacent segments with near-identical
  scores fell on opposite sides.

A second defect was found in the same pass: the divide-by-zero **floor on the
context MAD was computed separately per `featurise()` call** — 0.3731 over the
29 exemplars against 0.4654 over the 3.7k segments, a 25% discrepancy affecting
the ~5% of transects that hit it. The two score sets were not on one scale.

A detour tried to replace the cut with an unsupervised one (KDE valley / GMM
crossover / Otsu, all near percentile 27). **That was wrong** and the labels
below falsify it: Otsu's cut scores only **83.8%** balanced accuracy. GMM BIC
preferring k=2 by -811 was skew being absorbed by a second Gaussian, not
bimodality — BIC kept improving through k=4, and the KDE trough between the two
apparent peaks is only **4.9%** deep at percentile 1.7. The score distribution
is a skewed continuum, consistent with [[road_morphology_bins]].

### The actual fix was more labels — 2026-07-30

The user extended `roads.shp` by **159 lines / 15.55 km inside 9t** (1,155 ->
1,314 lines, 186.87 -> 202.42 km), adding the faint variety that had been
missing. Faint exemplars inside the layer went from **0/21 to 18/21** (median
distance to the nearest line 101.8 m -> **0.6 m**).

That made the correct test possible for the first time: label `roads.shp`
segments by proximity to an exemplar (60% of length within **8 m**), then fit
the cut on **those segments**, not on the exemplar geometries.

| matched set | n segments | median score | IQR |
|---|---|---|---|
| bold | 37 | **-4.72** | [-6.49, -2.77] |
| faint | 42 | **-0.44** | [-0.72, +0.03] |

**Cliff's delta -0.981, AUC 0.990, Mann-Whitney p = 7.4e-14.** The two classes
overlap only across -1.24 to -0.70.

| cut | value | balanced accuracy |
|---|---|---|
| Youden J on matched segments | **-1.585** (pct 57.0) | **97.3%** in-sample |
| — grouped CV, whole parent roads held out, 38 folds | | **94.1%** |
| unsupervised Otsu (rejected) | -3.45 (pct 27.3) | 83.8% |

The original exemplar-derived midpoint was **-1.54**. The threshold was right
all along; the *layer* was wrong. With no faint roads in `roads.shp` that cut
had nothing correct to select, so it sliced the bold population's dim tail.

| layer | segments | km | share |
|---|---|---|---|
| `roads_bold_9t` | 2,303 | 114.81 | 57.0% |
| `roads_faint_9t` | 1,740 | 86.61 | 43.0% |

**263 of 1,280 parent roads (21%) are internally mixed** (25-75% bold segments)
— confirmation that whole-road labelling was never well-posed.

The `ambiguous` class is retired. It existed to absorb the gap between exemplar
ranges; with a cross-validated cut there is no gap to absorb.

### It is not a terrain proxy

Segment-level `faint_score` vs slope: Spearman **-0.040** (p = 0.011). Median
slope 4.68 deg bold vs 4.42 faint — indistinguishable. The concentration of
faint segments on the steep eastern valley sides is a real spatial pattern, not
the terrain axis leaking back in (which is what happened to incision depth,
Spearman +0.42).

### The split predicts detection on held-out ground

| 9t blocks | bold | faint |
|---|---|---|
| train (memorised) | 0.898 (99% >= 0.5, n=1332) | 0.764 (83%, n=1054) |
| **test (never trained)** | **0.825 (96% >= 0.5, n=292)** | **0.734 (83%, n=270)** |
| **exemplar-matched segments only** | **0.855** | **0.037** |

The last row is the important one. Segments matching the hand-drawn faint
exemplars score **0.037** mean P(road) — the model is effectively blind to them.
The class-wide faint mean of 0.734 is far higher, so the exemplars sit at the
extreme end of the class; but that extreme end exists and is invisible.

### How to use the layers

`faint_score` is the raw `opos_zcontrast`; move the cut yourself if you want.
`margin_sigma` is distance from the boundary. `parent_road` joins segments back
to their source line. `exlabel` marks the 79 exemplar-matched segments the cut
was fitted on. `P_road` and `split` are attached — **filter to `split = 'test'`
before concluding anything about detection**, since train-block probabilities
are memorisation.

## Per-feature comparison of the labelled segments — 2026-07-31

Every feature, bold-exemplar segments vs faint-exemplar segments, ranked by
Cliff's δ. Two products, both on 9t.

**Figure** `fig_bold_vs_faint_feature_ridgeline_9t_05.png` — one ridgeline row
per feature. Each feature is z-scored on the **pooled** bold+faint values, so
all eight share one x axis in pooled-SD units and the classes are normalised
against each other rather than against the network. y is KDE density, rescaled
per panel. Rug ticks are individual segments, so the reader can check the
smoothing against the sample. Built on the 79 `roads.shp` segments that match an
exemplar — the same set the cut was fitted on.

| feature | bold median | faint median | δ | AUC | p |
|---|---|---|---|---|---|
| `P_road` | 0.856 | 0.023 | **+1.000** | 1.000 | 2.4e-14 |
| `opos_zcontrast` | -4.72 | -0.44 | -0.981 | 0.990 | 7.4e-14 |
| `incision_depth_m` | 0.515 m | 0.178 m | +0.976 | 0.988 | 9.9e-14 |
| `lrm25_zcontrast` | -2.63 | -0.34 | -0.925 | 0.963 | 1.7e-12 |
| `tpi15_zcontrast` | -2.46 | -0.46 | -0.906 | 0.953 | 4.8e-12 |
| `slope_zcontrast` | +1.32 | -0.13 | +0.777 | 0.889 | 3.0e-09 |
| `relief10_zcontrast` | +0.88 | -0.24 | +0.722 | 0.861 | 3.7e-08 |
| `oneg_zcontrast` | -1.24 | -0.01 | -0.655 | 0.828 | 5.9e-07 |

Three readings:

- **`P_road` δ = +1.000 is not a result, it is the problem.** Perfect
  separation, zero overlap. The road model is a trained detector, not an
  independent measurement, and it has already decided these are different
  things. This row is circular with respect to the classification and must not
  be cited as evidence the classes are separable.
- **The top four terrain features are one physical fact measured four ways.**
  Bold roads are cut into the hillside, faint roads sit on it.
  `incision_depth_m` is the legible version: **51.5 cm vs 17.8 cm** median.
- **The bottom three are terrain, not roads.** `slope`, `relief10`, `oneg` sit
  at δ 0.66-0.78 with visibly overlapping curves. A road on a steep slope *has*
  to be cut to be level; these are consequences of siting, not independent
  evidence of boldness. Using them as discriminators would import a terrain
  bias.

The distribution shapes also explain the earlier failures. The faint curves are
tight and near zero, the bold ones wide and pushed out — "no measurable cut" is
a narrow condition, "some amount of cut" spans a range. That asymmetry is why
the whole-network distribution reads as a skewed continuum and why the
unsupervised cuts landed inside the mode.

**CSV** `bold_faint_exemplar_segments_9t_05_scores.csv` — the exemplar
shapefiles themselves, chopped to ~50 m and scored: 36 bold segments from 8
lines (1.786 km), 48 faint from 21 lines (2.351 km). Distinct from the figure's
population, which is `roads.shp` segments *matched to* exemplars. Medians agree
closely (`opos` -4.39 / -0.26 here vs -4.72 / -0.44 matched), which is the
cross-check that the matching step is not distorting the labelled set.

Both passes reuse the MAD floors computed on the 9t `roads.shp` network
(`opos` 0.4600, `oneg` 0.4623, `slope` 1.3221, `lrm25` 0.0319, `tpi15` 0.0457,
`relief10` 0.1267, `dem` 0.3457) so every score sits on one scale. `MIN_LEN` is
lowered 20 m -> 5 m for the exemplar pass so no line is silently dropped; in the
event no segment fell below 5 transects.

## Caveats, and they matter

- **`dist_pad_m` = 0 for all 8 bold roads.** Bold-vs-faint may be partly
  confounded with pad-adjacent-vs-not. With n = 8 these cannot be separated.
  The contrast is real; the *attribution* of it to "boldness" rather than "pad
  access road" is not established.
- **n = 8 vs 21 exemplars**, chosen by eye as clear cases. Effect sizes from
  deliberately clear examples overstate what a random sample would give. The
  q-values are honest for these data; the population effect will be smaller.
- **Transect-level statistics are pseudo-replication** (transects within a road
  are correlated). They are reported in the CSV as `delta_transect` for power
  but never quoted as the result.
- **Two profile panels are unusable.** CHM median is flat at 0 — that raster is
  zero-inflated (tile median 0.091 m), so only the `canopy_cover_*` fraction
  form is meaningful. `roughness_11` renders as quantized steps at this scale.
- **`gdens` / `inten` are 42–45% nodata** over the samples.

## What to do about it

1. **Annotate the faint class.** This is a label-coverage problem before it is a
   model problem. No loss function, architecture, or threshold fixes a class
   that is absent from the training data. The 37.68 km of added roads on 613590
   is a head start.
2. **Re-report every road metric as bold-conditional** until faint labels exist,
   or state the restriction explicitly.
3. **Do not build a two-class road model yet** — but for a new reason. Not
   "there is no second population" (there is), but that the second population
   has ~0 labelled examples.
4. **Use the context features.** Road density, pad proximity, and canopy cover
   separate the classes nearly as well as the cross-section does, and they are
   cheap. They are also the features most likely to encode the pad confound, so
   validate on faint roads far from pads.
5. **Retire the `prominence_z` framing from** [[road_morphology_bins]] as a
   bold/faint discriminator. It was fitted on bold-only data. It remains valid
   as a within-bold terrain-fair prominence measure.

## Outputs

`data/derivatives/experiments/road_morphology_bins/`

| file | contents |
|---|---|
| `bold_vs_faint_features_9t_05.csv` | 29 roads, all band + contrast + proximity features, label |
| `bold_vs_faint_effectsizes_9t_05.csv` | 65 features ranked by Cliff's δ, with p, BH q, transect-level δ |
| `bold_vs_faint_summary_9t_05.json` | headline numbers + top 25 |
| `fig_bold_vs_faint_profiles_9t_05.png` | median transect profiles, 6 rasters, road/context bands shaded |
| `fig_bold_vs_faint_effects_9t_05.png` | ranked effect sizes with q labels |
| `roads_bold_faint_9t_05.gpkg` | layers `roads_bold_9t` / `roads_faint_9t` / `roads_scored_9t` |
| `roads_bold_faint_9t_05_scores.csv` | 4,043 network segments, features + class + `exlabel` + `P_road` + `split` |
| `roads_bold_faint_9t_05_threshold.json` | cut, provenance, CV accuracy, shared MAD floors |
| `fig_roads_bold_faint_split_9t_05.png` | network histogram with the cut |
| `fig_bold_vs_faint_feature_ridgeline_9t_05.png` | 2026-07-31, per-feature ridgeline, pooled-z, δ-ranked |
| `bold_faint_exemplar_segments_9t_05_scores.csv` | 2026-07-31, 84 exemplar segments (36 bold / 48 faint), 7 features + `P_road` |

## Method

Perpendicular transects every 10 m, **±60 m** at 0.5 m (wide enough to hold real
context), 414 transects. Three bands: road (|d| ≤ 3 m), near (5–15 m), context
(25–60 m). Every raster contributes a per-band statistic plus explicit contrast
terms (road − context). Detrending for the elevation residual uses |d| ∈
[30, 60] m so the road and its berms never influence their own trend surface.

## Reproduce

```bash
# the original 29-exemplar effect-size study
python notebooks/wellsight_v2/s7_analysis/_bold_vs_faint_roads.py

# fit the cut and write the bold/faint layers over the 9t network
python notebooks/wellsight_v2/s7_analysis/_classify_9t_roads_bold_faint.py

# score every segment of bold_roads.shp / faint_roads.shp to CSV
python notebooks/wellsight_v2/s7_analysis/_score_bold_faint_exemplar_segments.py
```

The ridgeline figure is generated by a scratch script; regenerate it from
`bold_faint_exemplar_segments_9t_05_scores.csv` or from the `exlabel` column of
`roads_bold_faint_9t_05_scores.csv`.
