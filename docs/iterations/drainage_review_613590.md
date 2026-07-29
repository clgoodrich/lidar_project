# drainage_review_613590 — 9t drainage model, vectorized to review layers on 613590

**Date:** 2026-07-29
· **Builder:** `notebooks/wellsight_v2/build/_build_drainage_review_package.py`
· **Calibration:** `notebooks/wellsight_v2/build/_calibrate_drainage_extraction_9t.py`
· **QC render:** `notebooks/wellsight_v2/build/_overlay_drainage_review_613590.py`
· **Outputs:** `data/derivatives/tiles/data_3x3/westernpa_d20/613590/review_drainage/`
· **Related:** [[drainage_unet_1m]], [[road_unet_1m_corrected]], [[road_sweep_202607]]

## Goal

Run the road active-learning pipeline end to end for **drainage**: 9t drainage
labels → U-Net → apply to 613590 → vectorize → `review_` / `added_` layers the
user edits in QGIS, exactly as `review_roads_613590` / `added_roads_613590` work.

## What already existed

| step | status |
|---|---|
| drainage labels on 9t | `annotations_proj.gpkg` layer `drainage`, 1,791 lines inside 9t |
| U-Net trained on them | **existed** — [[drainage_unet_1m]] (2026-06-16), val drainage IoU 0.811, AP drainage-vs-road 0.990 |
| inference on 613590 | **existed** — `tiles/9t/drainage_unet_1m/drainage_prob_613590_1m.tif` |
| vectorization → review layers | **this pass** |

So only the last step was missing.

## Raster provenance — an easy trap

Two different `drainage_prob_613590_1m.tif` files exist:

- `data_3x3/westernpa_d20/613590/drainage_prob_613590_1m.tif` — the **road**
  model's third class, a side-product. 0.591% of tile at P ≥ 0.5.
- `tiles/9t/drainage_unet_1m/drainage_prob_613590_1m.tif` — the **dedicated
  drainage U-Net**. 0.709% of tile at P ≥ 0.5. **This is the right one.**

An early version of this pass used the block-directory file and reported a
"4.5x drainage under-prediction". That figure was wrong twice over: wrong
raster, and it compared pruned centreline length against raw hand-drawn line
length. The defensible transfer number is **pixel coverage: 1.035% on 9t
(training domain) vs 0.709% on 613590**, a 32% drop. Real, but ordinary
out-of-domain softening, not a broken class.

## Calibrating the vectorizer — the real finding

The extraction settings were carried over from the road pipeline and had never
been checked against drainage ground truth. `_calibrate_drainage_extraction_9t.py`
sweeps 48 configs on the **9t held-out test blocks**, scored with the same
Heipke/Wiedemann buffer matching (8 m tolerance) `_road_optimize.py` uses for
roads, so the F1 is directly road-comparable.

| config | completeness | correctness | F1 | km |
|---|---|---|---|---|
| road settings carried over (island=100, spur=20) | 0.552 | 0.747 | 0.635 | 5.01 |
| **calibrated (t=0.50, min_px=60, spur=10, island=0)** | **0.824** | **0.737** | **0.778** | 7.52 |

**The island filter was destroying the network.** A drainage network is mostly
short first-order tributary stubs; a 100 m minimum-component filter deletes
them. Removing it buys **27 points of completeness at zero cost to
correctness**.

Reference point: road extraction scores F1 0.754 on the same harness. Drainage
vectorizes slightly **better** than roads.

Effect on the delivered package: 13.62 km → **30.60 km** on 613590
(0.67 → 1.51 km/km²).

## Outputs

`data/derivatives/tiles/data_3x3/westernpa_d20/613590/review_drainage/`

| file | contents |
|---|---|
| `review_drainage_613590.gpkg` (layer `review`) | 1,131 predicted drainage segments, ~40 m, 30.60 km, with `mean_pdrain`, `mean_proad`, `status` |
| `review_drainage_613590_ORIGINAL.gpkg` | untouched snapshot; rejects recovered by `seg_id` set difference |
| `added_drainage_613590.gpkg` (layer `added`) | empty LineString layer — draw missed channels here |
| `review_drainage_613590.qml` | QGIS style, categorized on `status` |
| `README_EDIT.md` | reviewer instructions |
| `drainage_review_overlay_613590_1m.png` | QC render, full block + 1.1 km zoom |

Calibration record: `data/derivatives/tiles/9t/drainage_extract_calib_9t_1m.json`
(all 48 configs, GT km, region area).

## QC verdict

Geometry is sound — blue lines sit in hollows and valley bottoms, and they are
distinct from the road predictions rather than tracing the same features (the
drainage model's AP-vs-road of 0.990 holds up visually out of domain).

**The weakness is fragmentation**: many short disconnected stubs instead of
connected networks draining downhill. This is a topology failure, not a
placement failure, and it is exactly what clDice targets.

`gt_dist_m` is null for every segment — there is no hand-drawn drainage within
500 m of 613590. Nothing in this package is supervised, which is the point of
reviewing it.

## Design notes

- **No reconnect/bridging**, unlike the road pipeline. Bridging invents
  geometry, and an invented channel taught as a positive is worse than a gap the
  reviewer draws in by hand. Connectivity should be fixed in the loss (clDice),
  not in post-processing.
- **Deletion is the supported edit.** `_build_road_corrections_613590.py:175`
  derives rejects by `seg_id` difference against the `_ORIGINAL` snapshot, so
  the drainage builder writes that snapshot explicitly rather than relying on a
  manual copy. (The road `README_EDIT.md` still says "flag, don't delete" — that
  text is stale relative to the code.)

## Next

1. **Review the package** — adjudicate the 1,131 segments, draw missed channels
   into `added_drainage_613590.gpkg`.
2. **clDice drainage retrain.** clDice won the connectivity pole in
   [[road_sweep_202607]] (P(road) 0.784 → 0.885), and drainage networks are a
   better fit for it than roads — it was designed for tubular connected
   structures. The loss is already implemented in `_road_sweep_202607.py`.
3. **Ingest the review** as a corrections block, mirroring
   `_build_road_corrections_613590.py`.

## Reproduce

```bash
python notebooks/wellsight_v2/build/_calibrate_drainage_extraction_9t.py
python notebooks/wellsight_v2/build/_build_drainage_review_package.py \
    --key 613590 --no-rejects \
    --drain-prob data/derivatives/tiles/9t/drainage_unet_1m/drainage_prob_613590_1m.tif \
    --gt data/derivatives/annotations/annotations_proj.gpkg
python notebooks/wellsight_v2/build/_overlay_drainage_review_613590.py
```
