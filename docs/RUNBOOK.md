# RUNBOOK — from a LAZ file to pits, pads and roads

What to actually run, in order, and what each step needs. Written 2026-08-12
against the stage layout in `notebooks/wellsight_v2/`.

Two tracks, and they are not the same length:

* **Track A — a NEW area.** You have LAZ, you want detections. No annotation
  required. Five commands.
* **Track B — TRAINING.** Only for an area you have hand-annotated. Everything
  in Track A, plus labels, plus training.

Most of the time you want Track A.

---

## Track A — new LAZ → candidate pits / pads / roads

Placeholders: `<AREA>` is your suffix (`mck_e1424n2237_1m`), `<GLOB>` the source
tiles, `<BBOX>` the extent in EPSG:6346 metres as `x0,y0,x1,y1`.

### A1. Build the terrain derivatives — the only step that reads LAZ

```
python notebooks/wellsight_v2/s1_build/_build_derivatives.py \
    --tiles "data/_source/lidar/<region>/<GLOB>.laz" \
    --bbox "<BBOX>" --suffix <AREA> --res 1.0
```

One pass does everything: PDAL merges the tiles, `writers.gdal` IDW builds the
DEM, then 20 rasters come off it into `data/<AREA>/`.

Seven of those are the model input channels, and they are the only ones the
networks see:

    lrm_25   lrm_5   slope   tpi_05   openness_pos   openness_neg   roughness_5

At `--res 0.5` the seventh becomes `roughness_11`, which is what the 0.5 m
models were trained on. Match the resolution to the model you intend to run.

Runtime is dominated by the PDAL merge, not the raster maths: ~53 s for 19
tiles, ~217 s for 66. The DEM and derivatives take another minute or two.

### A2. Red Relief Image Map — optional, for looking at

```
python notebooks/wellsight_v2/s1_build/_make_rrim.py --tile <AREA> --suffix <RES>
python notebooks/wellsight_v2/s1_build/_make_rrim.py --tile <AREA> --suffix <RES> --simple
```

`--tile` is the area (`9t`, `613590`, `607594`, …) and `--suffix` is the
resolution token of the input rasters — `05` or `1m`. Together they resolve the
input dir to `data/<area>/derived/<res>/` via `path_for`; override with `--dir`.

Chiba et al. 2008: red-tinted slope over a differential-openness base. `--simple`
swaps the base for a Local Relief Model (Auld-Thomas 2022, patent-free). It
reuses the openness rasters from A1 and recomputes nothing.

**RRIM is a viewing product, not a model input.** It was tested as a channel and
rejected. Skip it if you only want detections.

> Note: this script still lives in the old `notebooks/wellsight_v2/` tree. It has no
> v2 equivalent. See "Known gaps" below.

### A3. Run the detectors

```
python notebooks/wellsight_v2/s4_infer/_predict_on_tile.py --suffix <AREA>
```

Discovers the seven channels by naming convention, stacks them itself — **no
separate feature-stack step is needed for inference** — and runs pit, road and
plat models in one go. Outputs land in `data/inference_<AREA>/`.

### A4. Turn probabilities into candidate polygons

```
python notebooks/wellsight_v2/s4_infer/_postfilter_tile_candidates.py \
    --suffix <AREA> --pit-thresh 0.60 --pad-thresh 0.70 \
    --pit-min-area 20 --pad-min-area 300
```

Raw argmax over-fires on unseen ground and calls the nodata corner foreground.
This applies the eroded valid-DEM mask, thresholds, drops small blobs, closes
and fills, then polygonises to `pit_candidates_<AREA>.gpkg` /
`pad_candidates_<AREA>.gpkg` plus an overlay PNG.

### A5. Roads as lines rather than pixels

```
python notebooks/wellsight_v2/s5_eval/_road_optimize.py --apply --block <AREA>
```

Skeletonise → spur prune → merge → island filter. The cleaning config was tuned
on 9t val blocks and frozen. `roads_studio` (`Roads Studio.bat`) is the
interactive version of the same knobs if you want to see what each one does.

---

## Track B — training on an annotated area

Only needed where hand annotation exists. Today that means 9t and 613590.

### B1. Annotations → projected truth

```
python notebooks/wellsight_v2/s2_labels/_prep_annotations.py
```

Reads the WGS84 shapefiles in `qgis/annotations/`, reprojects to
EPSG:6346, pairs pit floors to rims, and writes `annotations_proj.gpkg`.

**Run this after every QGIS session.** Stale projected truth was the single
biggest source of wrong numbers in this project.

### B2. Labels and splits

```
python notebooks/wellsight_v2/s2_labels/_build_plat_road_dataset.py   # pads + roads
python notebooks/wellsight_v2/s2_labels/_build_pit_dataset.py         # pits
python notebooks/wellsight_v2/s2_labels/_rebuild_labels_road_9t_1m.py # 1 m road labels
```

Rasterises annotations to label rasters and writes the per-object manifests
carrying the train/val/test block assignment.

### B3. Train

```
python notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py  --folds 5 --epochs 40
python notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py  --folds 5 --epochs 40
python notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py --epochs 40 --tag <tag>
```

The road trainer predicts 613590 at the end automatically. ~280–560 s/epoch.

### B4. Score

```
python notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py
python notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py --prob <road_prob.tif>
```

### B5. Review, and feed corrections back to B1

```
python notebooks/wellsight_v2/s6_review/_build_road_review_package.py --key <block>
# ... correct in QGIS ...
python notebooks/wellsight_v2/s6_review/_road_corrections_diff.py --key <block>
```

---

## The critical path, as a list

Everything Track A touches, and nothing else:

| # | Script | Stage |
|---|---|---|
| A1 | `s1_build/_build_derivatives.py` | build |
| A2 | `notebooks/wellsight_v2/s1_build/_make_rrim.py` | build (optional, viz) |
| A3 | `s4_infer/_predict_on_tile.py` | infer |
| A4 | `s4_infer/_postfilter_tile_candidates.py` | infer |
| A5 | `s5_eval/_road_optimize.py` | vectorise |

Plus `_common.py` and `_dl.py`, which everything imports.

**That is five scripts.** Everything else in the repository is training,
evaluation, review tooling, or one-off analysis.

---

## Known gaps — read before trusting a full-suite run

**1. `_predict_on_tile.py` is wired to older models.** Its task table is:

```
("pit",  "pit_unet_v2", ...)
("road", "road_unet",   ...)      <-- 0.5 m, 2-class, superseded
("plat", "plat_unet",   ...)
```

`road_unet` is the retired 2-class model. The 3-class `road_unet_1m_recall`
family replaced it on 2026-06-08, and `road_unet_1m_recall_relabeled20260806` is
the current best on the honest 613590 test. **The one-command path does not use
it.** For the best road result today, run `s4_infer/_road_infer.py` explicitly
with the checkpoint you want.

**2. The CV5 models cannot be used by `_predict_on_tile.py`.** `pit_unet_cv5` and
`pad_unet_cv5` keep their weights in `fold0/`…`fold4/`, with no top-level
`best.pt`. They are cross-validation artefacts for *measuring*, not deployment
checkpoints. Deploying them means picking a fold or ensembling — neither is wired
up.

**3. `_prep_road_1m.py` is hard-coded to 9t and deliberately disabled.** Its
`SRC_1M` points at a directory that no longer exists, so it raises rather than
silently rebuilding the feature stack with channels that do not match what the
models trained on. See its docstring. Use `_rebuild_labels_road_9t_1m.py` for
labels only.

**4. `_make_rrim.py` moved into v2 on 2026-08-15.** It now lives at
`notebooks/wellsight_v2/s1_build/_make_rrim.py`. Its `--dir` default was a
pre-area-major path that no longer existed; the input dir is now resolved from
`--tile` + `--suffix` through `path_for`. Cited in `literature/CITATIONS.md`
for Chiba 2008 and Auld-Thomas 2022.

---

## Reproduce this document

The stage layout it describes: `notebooks/wellsight_v2/README.md`.
Per-script last-run evidence: `docs/script_last_used.md`.
