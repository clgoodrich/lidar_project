# Roads on 613590: the first out-of-domain test with real ground truth

**Date:** 2026-08-06
**Goal:** Retrain the road model on 9t data only, predict 613590, and score against
the 613590 roads now carried in `annotations/roads.shp`.

## Why this tile is worth something

613590 is the cleanest out-of-domain test the project has. A model trained on 9t
alone has never seen a pixel of it — not a training patch, not a validation crop.
That is a stronger claim than the 9t held-out road numbers can make, where ~40 m
chunking puts 39.8% of held-out chunks on a parent road that also has chunks in
train (`BACKLOG.md`, "Split leakage at block boundaries").

The 9t and 613590 footprints are disjoint:

    9t      [619500, 4593000] .. [624000, 4597500]
    613590  [613499, 4590000] .. [617998, 4594501]

Zero of the 1,490 new road lines intersect the 9t extent, so folding them into
`roads.shp` on 2026-08-05 did not contaminate the 9t labels.

## Read this before quoting any number

`roads.shp` ground truth on 613590 is **not one thing**. The `src` column splits it:

| src | km | Provenance |
|---|---|---|
| `613590_review_r2` | 138.23 | A **previous road model's output**, chunked and vetted by hand |
| `613590_added_r2` | 48.87 | **Drawn from scratch** on roads the previous model missed |

Scoring a road model against `613590_review_r2` is circular, and not mildly so.
Measured completeness on that subset, across eleven different models:

| Model | review completeness |
|---|---|
| ENSEMBLE_max, ENSEMBLE_mean, alpha078, boundary, corrected_r1, corrected_r2 | 0.999 – 1.000 |
| cldice, cldice_sg3 | 0.997 – 0.998 |
| orient | 0.983 |
| **recall_relabeled20260806** | **0.962** |

Eleven models, one number. The subset cannot rank anything, because those lines
*are* a sibling model's output. **Only `613590_added_r2` carries information**, and
it is adversarially hard by construction: these are precisely the roads a sibling
model failed to find. Every metric below is reported on the added subset.

Correctness is a **lower bound** on this tile. `roads.shp` covers 613590 only where
the annotator worked, so a prediction on a real road nobody drew counts against it.

## Metric

Copied from `_road_threshold_products_9t.py` so the numbers stay comparable:

    coverage(chunk) = fraction of chunk length within TOL_M of a pixel called road
    found           = coverage >= COVER_FRAC

TOL_M = 5 m, COVER_FRAC = 0.5, chunks ~40 m. Completeness / correctness / quality
follow Wiedemann et al. 1998 (logged in `literature/CITATIONS.md`). Correctness is
measured on **pixels** (`correctness_px`) because a probability raster has no honest
line length; the label carries that caveat everywhere it appears.

## What had to be rebuilt first

Three inputs predated the 2026-07-30 `roads.shp` extension and were quietly wrong:

1. **`labels_road_9t_1m.tif`** held 556,773 road px (~185.6 km) while `roads.shp`
   carried **206.09 km** inside 9t. About **19 km of hand-drawn road was labelled
   background** — and it was disproportionately the faint lines added on 07-30,
   exactly the class the model fails on. Rebuilt to **614,003 px (+57,230)**.
   Old raster preserved as `labels_road_9t_1m_pre2026-08-06.tif`.
2. **`road_dataset_manifest.csv` / `road_chunks_9t.gpkg`** rebuilt: 15,292 road
   chunks, 3,315 train / 983 val / 672 test in-tile.
3. `data/derivatives/tiles/9t_1m/` no longer exists (a dead junction into
   `E:\lidar_project_data_DO_NOT_DELETE`), so `_prep_road_1m.py` cannot run.
   `_rebuild_labels_road_9t_1m.py` rebuilds only the labels off the surviving
   feature stack's grid.

`plat_dataset_manifest.csv` was restored from a snapshot after the rebuild, so pad
CV5 fold assignment is unchanged. Rebuilding it surfaced a separate finding:
**`plat.shp` has 995 features but the manifest only ever had 650.**

## The controlled result

Same recipe, same architecture, same hyperparameters, same 9t-only training data.
**The only change is the label raster.**

| Model | thr | added completeness | correctness_px | quality |
|---|---|---|---|---|
| `road_unet_1m_recall` (Jun 14, stale labels) | 0.50 | 0.613 | 0.835 | 0.547 |
| **`recall_relabeled20260806`** | 0.50 | **0.759** | 0.828 | **0.655** |
| | 0.40 | 0.788 | 0.802 | 0.660 |
| | 0.30 | 0.816 | 0.768 | 0.655 |

**+0.146 completeness on hand-drawn faint road at no correctness cost** (0.835 →
0.828, inside noise). Quality +0.108. Recovering 19 km of mislabelled road bought
more than any architecture change in the sweep.

Confirmation from the probability field, mean P(road) sampled every 2 m:

| Model | review lines | added lines | gap |
|---|---|---|---|
| Jun 14 recall | 0.891 | 0.432 | −0.459 |
| relabeled 08-06 | 0.815 | 0.549 | **−0.266** |

The faint-road gap closed by 0.193. Review confidence *fell* (0.891 → 0.815), which
is healthy — the model is no longer a near-clone of the model that drew those lines.

## Every candidate, best operating point, added subset

| Model | best thr | completeness | correctness_px | quality |
|---|---|---|---|---|
| `corrected_r2` ⚠️ | 0.70 | 0.919 | 0.842 | 0.784 |
| **sweep_orient** | 0.40 | 0.811 | 0.816 | **0.686** |
| **sweep_ENSEMBLE_mean** | 0.30 | 0.820 | 0.804 | 0.684 |
| **sweep_ENSEMBLE_max** | 0.70 | 0.808 | 0.812 | 0.681 |
| sweep_boundary | 0.50 | 0.777 | 0.837 | 0.674 |
| sweep_alpha078 | 0.50 | 0.782 | 0.829 | 0.674 |
| `corrected_r1` ⚠️ | 0.50 | 0.788 | 0.822 | 0.674 |
| sweep_cldice_sg3 | 0.50 | 0.777 | 0.825 | 0.667 |
| **recall_relabeled20260806** | 0.40 | 0.788 | 0.802 | 0.660 |
| sweep_cldice | 0.30 | 0.761 | 0.827 | 0.657 |
| road_unet_1m_recall (Jun 14) | 0.30 | 0.691 | 0.784 | 0.581 |
| sweep_cldice_mkf | 0.70 | 0.640 | 0.615 | 0.457 |

⚠️ trained on 613590 corrections — **not a valid score on this tile**. `corrected_r2`
saw these exact added lines, so its 0.919 is memorisation. Its correctness still
collapses to 0.665 at thr 0.50, which is the more interesting half of that row.

**Maximum road recovery:** `sweep_ENSEMBLE_max` at thr 0.30 finds **0.909** of the
hand-added roads at 0.651 correctness, from models that never saw the tile.

**`sweep_cldice_mkf` is a clear negative result:** 1,838,487 predicted road px, 2.4×
every other model, correctness 0.520. Multi-block McKean training over-predicts
badly, consistent with the earlier `road_unet_mb` rejection.

## Interpretation

The retrained 9t-only model beat its own predecessor decisively (+0.11 quality) but
still sits **below the sweep variants**. That is not a contradiction — it is the
obvious next experiment. Every sweep variant was trained on the **old, 19-km-short
labels**. If relabelling is worth +0.11 quality to the recall recipe, `orient`,
`boundary` and the ensemble members should all move too, and from a higher base.

The evidence is now consistent across three independent measurements — completeness,
mean P(road), and the `BACKLOG.md` faint-road audit of 2026-07-29 — that the road
model's dominant failure mode is **a road class under-represented in the labels**,
not architecture, not loss function, and not capacity.

## Reproduce

    python notebooks/wellsight_v2/annotations/_build_plat_road_dataset.py
    python notebooks/wellsight_v2/roads/_rebuild_labels_road_9t_1m.py
    python notebooks/wellsight_v2/roads/_road_unet_1m_recall.py --epochs 40 --tag relabeled20260806
    python notebooks/wellsight_v2/eval/_score_road_pred_vs_roads_shp_613590.py \
        --prob data/derivatives/tiles/9t/road_unet_1m_recall_relabeled20260806/road_prob_613590_1m.tif \
        --label recall_relabeled20260806

## Files

- Model: `data/derivatives/tiles/9t/road_unet_1m_recall_relabeled20260806/`
  (`best.pt` ep 39, val road IoU 0.594; `road_prob_613590_1m.tif`; `test_metrics.json`)
- Scores: `data/derivatives/eval_613590_roads/road_score_vs_roads_shp_613590_1m.csv`
  (12 models x 5 thresholds x 3 subsets)
- `data/derivatives/eval_613590_roads/_road_score_vs_roads_shp_613590_1m.json`
- `data/derivatives/eval_613590_roads/road_found_vs_missed_thr0p50_613590_1m.gpkg`
- Scripts: `notebooks/wellsight_v2/eval/_score_road_pred_vs_roads_shp_613590.py`,
  `notebooks/wellsight_v2/roads/_rebuild_labels_road_9t_1m.py`

## Caveats

- 9t held-out val/test IoU is **not comparable** across the relabel. The Jun 14
  model scored 0.640 val road IoU against labels missing 19 km of road; the new one
  scores 0.594 against fuller labels. Different denominators, not a regression.
- Correctness on 613590 is a lower bound (incomplete annotation coverage).
- Single seed per variant. Deltas under ~0.02 quality are not separable.
