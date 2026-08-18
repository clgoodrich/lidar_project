# Did any archived script actually run recently?

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

Physical evidence, not log mentions: newest mtime of the output paths each script declares. Window 60 days (since 2026-06-13).

Biased toward *still used* — a shared output directory can be touched by a sibling script, so a hit warrants a look, not an automatic restore.

| Bucket | Scripts |
|---|---:|
| **output written within 60 days** | **17** |
| outputs exist but are older | 17 |
| no resolvable output path | 43 |

## Output touched within 60 days — review these

| Script | newest output | days | path |
|---|---|---:|---|
| `notebooks/wellsight/_instance_common.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/annotations/_build_pit_dataset.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/annotations/_build_pad_road_dataset.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/annotations/_build_pad_split.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/annotations/_prep_annotations.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/build/_pit_optimize.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/multitask/_multitask_unet.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/features_pit_9t_05.tif` |
| `notebooks/wellsight/pits/_pit_unet_v2.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/features_pit_9t_05.tif` |
| `notebooks/wellsight/pits/_pit_unet_v2_infer.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/features_pit_9t_05.tif` |
| `notebooks/wellsight/pads/_pad_unet.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/features_pit_9t_05.tif` |
| `notebooks/wellsight/roads/_prep_road_1m.py` | 2026-08-12 | 0 | `data/derivatives/annotations/annotations_proj.gpkg` |
| `notebooks/wellsight/roads/_road_unet.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/features_pit_9t_05.tif` |
| `notebooks/wellsight/roads/_road_unet_1m.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/road_dataset_manifest.csv` |
| `notebooks/wellsight/roads/_road_unet_1m_recall.py` | 2026-08-12 | 0 | `data/derivatives/tiles/9t/road_dataset_manifest.csv` |
| `notebooks/wellsight/annotations/_build_unified_split.py` | 2026-08-04 | 8 | `data/derivatives/tiles/9t/pit_blocks_9t.gpkg` |
| `notebooks/wellsight/annotations/_sanity_render.py` | 2026-08-04 | 8 | `data/derivatives/tiles/9t/labels_pit_9t_05.tif` |
| `notebooks/wellsight/pads/_pad_maskrcnn_infer.py` | 2026-07-02 | 41 | `data/derivatives/tiles/9t/iterations/pad_05_maskrcnn/best.pt` |

## Outputs exist, but older

- `notebooks/wellsight/build/_infer_roads_data_3x3.py` — newest output 2026-06-12
- `notebooks/wellsight/build/_predict_multitask_oilcreek.py` — newest output 2026-06-11
- `notebooks/wellsight/pits/_pit_maskrcnn_infer.py` — newest output 2026-06-11
- `notebooks/wellsight/pits/_pit_yolo_infer.py` — newest output 2026-06-11
- `notebooks/wellsight/pads/_pad_yolo_infer.py` — newest output 2026-06-11
- `notebooks/wellsight/build/_make_derivatives_walkthrough_nb.py` — newest output 2026-06-09
- `notebooks/wellsight/build/_make_training_walkthrough_nb.py` — newest output 2026-06-09
- `notebooks/wellsight/build/_build_water_2006_oilcreek.py` — newest output 2026-05-28
- `notebooks/wellsight/build/_build_oilcreek_22tile_mosaic.py` — newest output 2026-05-27
- `notebooks/wellsight/build/_build_water_oilcreek_22tile.py` — newest output 2026-05-27
- `notebooks/wellsight/build/_clean_road_network.py` — newest output 2026-05-21
- `notebooks/wellsight/build/_build_diagnostics_9t.py` — newest output 2026-05-15
- `notebooks/wellsight/build/_build_hydrology_9t.py` — newest output 2026-05-15
- `notebooks/wellsight/build/_build_streams_9t.py` — newest output 2026-05-15
- `notebooks/wellsight/build/_filter_streams_xsec_9t.py` — newest output 2026-05-15
- `notebooks/wellsight/analysis/_chm_age_proxy.py` — newest output 2026-04-21
- `notebooks/wellsight/analysis/_chm_age_proxy_v2.py` — newest output 2026-04-21

## No resolvable output path

Nothing to date them by. Absence of evidence.

- `notebooks/wellsight/_rasterize_instances.py`
- `notebooks/wellsight/_unet_instance_eval.py`
- `notebooks/wellsight/build/_build_3x3_hillshades.py`
- `notebooks/wellsight/build/_build_3x3_hillshades_mckean.py`
- `notebooks/wellsight/build/_build_chm_e1423n2238.py`
- `notebooks/wellsight/build/_build_chm_mckean.py`
- `notebooks/wellsight/build/_build_contours_data_3x3.py`
- `notebooks/wellsight/build/_build_data_3x3_derivatives.py`
- `notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py`
- `notebooks/wellsight/build/_build_derivatives.py`
- `notebooks/wellsight/build/_build_dsm_chm_westernpa.py`
- `notebooks/wellsight/build/_build_hillshade_az135.py`
- `notebooks/wellsight/build/_build_hillshade_variants.py`
- `notebooks/wellsight/build/_build_hillshades_downloadlist7.py`
- `notebooks/wellsight/build/_build_road_review_package.py`
- `notebooks/wellsight/build/_build_streams_t10k_mckean.py`
- `notebooks/wellsight/build/_build_water_banks_all.py`
- `notebooks/wellsight/build/_build_water_banks_oilcreek.py`
- `notebooks/wellsight/build/_build_water_banks_synthetic.py`
- `notebooks/wellsight/build/_build_water_solid_oilcreek.py`
- `notebooks/wellsight/build/_build_water_void_density.py`
- `notebooks/wellsight/build/_filter_streams_chunked_mckean.py`
- `notebooks/wellsight/build/_filter_streams_roads_mckean.py`
- `notebooks/wellsight/build/_filter_streams_xsection_mckean.py`
- `notebooks/wellsight/build/_postfilter_tile_candidates.py`
- `notebooks/wellsight/build/_predict_on_mkf.py`
- `notebooks/wellsight/build/_predict_on_tile.py`
- `notebooks/wellsight/build/_refine_roads_data_3x3.py`
- `notebooks/wellsight/build/_road_corrections_diff.py`
- `notebooks/wellsight/build/_road_methods_compare.py`
- `notebooks/wellsight/build/_road_optimize.py`
- `notebooks/wellsight/build/_yolo_infer_tile.py`
- `notebooks/wellsight/fetch/_fetch_3dep_inventory.py`
- `notebooks/wellsight/fetch/_fetch_dense_3x3.py`
- `notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py`
- `notebooks/wellsight/fetch/_fetch_pa_laz.py`
- `notebooks/wellsight/pits/_pit_maskrcnn.py`
- `notebooks/wellsight/pits/_pit_yolo.py`
- `notebooks/wellsight/pits/_stack_features.py`
- `notebooks/wellsight/pads/_pad_maskrcnn.py`
- `notebooks/wellsight/pads/_pad_yolo.py`
- `notebooks/wellsight/preprocessing/_build_cornrow_demo_nb.py`
- `notebooks/wellsight/roads/_road_postfilter.py`
