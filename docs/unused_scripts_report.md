# Which scripts are actually used?

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

`tools/find_unused_scripts.py` over 88 files in `notebooks/wellsight`.

Libraries and entry points are judged differently. A library exists to be imported, so zero importers means dead. An entry point is run by hand, so zero importers means nothing -- it is judged on whether anything *mentions* it and whether its declared outputs exist on disk.

| Verdict | Count |
|---|---:|
| LIVE | 58 |
| ORPHAN OUTPUT (ran, but nothing points at it) | 21 |
| DEAD library (no importers) | 1 |
| DEAD candidate (no mention, no importer, no output) | 8 |

## DEAD candidates

Nothing mentions these, nothing imports them, and none of the output paths they declare exist. Strongest evidence available that they never ran. Still not deleted -- review before archiving.

### `notebooks/wellsight/_rasterize_instances.py`

### `notebooks/wellsight/build/_build_hillshade_az135.py`

### `notebooks/wellsight/build/_build_water_banks_oilcreek.py`

### `notebooks/wellsight/build/_build_water_banks_synthetic.py`

### `notebooks/wellsight/build/_build_water_solid_oilcreek.py`

### `notebooks/wellsight/build/_build_water_void_density.py`

### `notebooks/wellsight/fetch/_fetch_dense_3x3.py`

### `notebooks/wellsight/fetch/_fetch_pa_laz.py`

## DEAD libraries

No `__main__` guard, so they exist only to be imported, and nobody imports them.

### `notebooks/wellsight/preprocessing/_build_cornrow_demo_nb.py`

## ORPHAN OUTPUT

These ran at least once -- their outputs are on disk -- but no doc, script or launcher points at them. Either undocumented one-offs, or steps someone still runs from memory. Do NOT archive without asking.

### `notebooks/wellsight/analysis/_chm_age_proxy.py`
- outputs exist: `data/derivatives/annotations/oil_gas_locations.gpkg` (+1 more)

### `notebooks/wellsight/analysis/_chm_age_proxy_v2.py`
- outputs exist: `data/derivatives/annotations/oil_gas_locations.gpkg` (+1 more)

### `notebooks/wellsight/annotations/_sanity_render.py`
- outputs exist: `data/derivatives/tiles/9t/hillshade_9t_05.tif` (+4 more)

### `notebooks/wellsight/build/_build_3x3_hillshades_mckean.py`
- outputs exist: `data/source_laz/mckean`

### `notebooks/wellsight/build/_build_chm_e1423n2238.py`
- outputs exist: `data/source_laz/mckean`

### `notebooks/wellsight/build/_build_dsm_chm_westernpa.py`
- outputs exist: `data/derivatives/tiles/data_3x3/westernpa_d20`

### `notebooks/wellsight/build/_build_hillshade_variants.py`
- outputs exist: `data/derivatives/tiles/data_3x3`

### `notebooks/wellsight/build/_build_hillshades_downloadlist7.py`
- outputs exist: `data/derivatives/tiles/extras` (+1 more)

### `notebooks/wellsight/build/_build_hydrology_9t.py`
- outputs exist: `data/derivatives/tiles/9t` (+2 more)

### `notebooks/wellsight/build/_build_oilcreek_22tile_mosaic.py`
- outputs exist: `data/source_laz/westernpa` (+1 more)

### `notebooks/wellsight/build/_build_water_2006_oilcreek.py`
- outputs exist: `data/external/oil_creek/statewide_2006_plan.txt`

### `notebooks/wellsight/build/_build_water_banks_all.py`
- outputs exist: `data/source_laz/mckean`

### `notebooks/wellsight/build/_build_water_oilcreek_22tile.py`
- outputs exist: `data/source_laz/westernpa` (+1 more)

### `notebooks/wellsight/build/_clean_road_network.py`
- outputs exist: `data/external/tiger_roads/roads_clipped.gpkg`

### `notebooks/wellsight/build/_filter_streams_roads_mckean.py`
- outputs exist: `data/derivatives/tiles/data_3x3/northcentral_b19`

### `notebooks/wellsight/build/_make_derivatives_walkthrough_nb.py`
- outputs exist: `notebooks/wellsight/derivatives_walkthrough.ipynb`

### `notebooks/wellsight/build/_make_training_walkthrough_nb.py`
- outputs exist: `notebooks/wellsight/training_walkthrough.ipynb`

### `notebooks/wellsight/build/_predict_multitask_oilcreek.py`
- outputs exist: `data/derivatives/tiles/extras/oilcreek_22tile` (+1 more)

### `notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py`
- outputs exist: `data/source_laz/westernpa`

### `notebooks/wellsight/pits/_pit_unet_v2_infer.py`
- outputs exist: `data/derivatives/tiles/9t/pit_unet_v2` (+5 more)

### `notebooks/wellsight/plats/_pad_yolo_infer.py`
- outputs exist: `data/derivatives/tiles/9t/iterations/pad_06_yolo` (+1 more)

## LIVE

- `notebooks/wellsight/_common.py` — imported by 79, mentioned in 17
- `notebooks/wellsight/_compare_known_wells.py` — mentioned in 3
- `notebooks/wellsight/_dl.py` — imported by 12, mentioned in 10
- `notebooks/wellsight/_instance_common.py` — imported by 11, mentioned in 6
- `notebooks/wellsight/_unet_instance_eval.py` — mentioned in 2
- `notebooks/wellsight/annotations/_build_pit_dataset.py` — mentioned in 4
- `notebooks/wellsight/annotations/_build_plat_road_dataset.py` — mentioned in 5
- `notebooks/wellsight/annotations/_build_plat_split.py` — mentioned in 3
- `notebooks/wellsight/annotations/_build_unified_split.py` — mentioned in 3
- `notebooks/wellsight/annotations/_prep_annotations.py` — mentioned in 4
- `notebooks/wellsight/build/_build_3x3_hillshades.py` — imported by 4, mentioned in 6
- `notebooks/wellsight/build/_build_chm_mckean.py` — mentioned in 1
- `notebooks/wellsight/build/_build_contours_data_3x3.py` — mentioned in 3
- `notebooks/wellsight/build/_build_data_3x3_derivatives.py` — mentioned in 3
- `notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py` — mentioned in 3
- `notebooks/wellsight/build/_build_derivatives.py` — imported by 2, mentioned in 14
- `notebooks/wellsight/build/_build_diagnostics_9t.py` — mentioned in 3
- `notebooks/wellsight/build/_build_road_review_package.py` — mentioned in 7
- `notebooks/wellsight/build/_build_streams_9t.py` — mentioned in 3
- `notebooks/wellsight/build/_build_streams_t10k_mckean.py` — mentioned in 1
- `notebooks/wellsight/build/_filter_streams_chunked_mckean.py` — mentioned in 1
- `notebooks/wellsight/build/_filter_streams_xsec_9t.py` — mentioned in 6
- `notebooks/wellsight/build/_filter_streams_xsection_mckean.py` — mentioned in 2
- `notebooks/wellsight/build/_icp_change_map.py` — mentioned in 4
- `notebooks/wellsight/build/_icp_old_vs_new.py` — mentioned in 3
- `notebooks/wellsight/build/_infer_roads_data_3x3.py` — mentioned in 4
- `notebooks/wellsight/build/_make_rrim.py` — mentioned in 4
- `notebooks/wellsight/build/_pit_optimize.py` — mentioned in 5
- `notebooks/wellsight/build/_postfilter_tile_candidates.py` — mentioned in 2
- `notebooks/wellsight/build/_predict_on_mkf.py` — mentioned in 2
- `notebooks/wellsight/build/_predict_on_tile.py` — mentioned in 6
- `notebooks/wellsight/build/_refine_roads_data_3x3.py` — mentioned in 5
- `notebooks/wellsight/build/_road_corrections_diff.py` — mentioned in 4
- `notebooks/wellsight/build/_road_methods_compare.py` — mentioned in 2
- `notebooks/wellsight/build/_road_optimize.py` — imported by 1, mentioned in 19
- `notebooks/wellsight/build/_yolo_infer_tile.py` — mentioned in 2
- `notebooks/wellsight/fetch/_fetch_3dep_inventory.py` — mentioned in 1
- `notebooks/wellsight/multitask/_multitask_unet.py` — mentioned in 3
- `notebooks/wellsight/pits/_pit_maskrcnn.py` — imported by 3, mentioned in 11
- `notebooks/wellsight/pits/_pit_maskrcnn_infer.py` — imported by 1, mentioned in 8
- `notebooks/wellsight/pits/_pit_unet_v2.py` — mentioned in 6
- `notebooks/wellsight/pits/_pit_yolo.py` — mentioned in 8
- `notebooks/wellsight/pits/_pit_yolo_infer.py` — mentioned in 3
- `notebooks/wellsight/pits/_stack_features.py` — mentioned in 5
- `notebooks/wellsight/plats/_pad_maskrcnn.py` — mentioned in 5
- `notebooks/wellsight/plats/_pad_maskrcnn_infer.py` — mentioned in 2
- `notebooks/wellsight/plats/_pad_yolo.py` — mentioned in 1
- `notebooks/wellsight/plats/_plat_unet.py` — mentioned in 7
- `notebooks/wellsight/preprocessing/__init__.py` — mentioned in 1
- `notebooks/wellsight/preprocessing/cornrow_filter.py` — imported by 1, mentioned in 1
- `notebooks/wellsight/preprocessing/dem_idw_builder.py` — imported by 1
- `notebooks/wellsight/roads/_build_road_multiblock_dataset.py` — mentioned in 2
- `notebooks/wellsight/roads/_prep_road_1m.py` — mentioned in 10
- `notebooks/wellsight/roads/_road_postfilter.py` — mentioned in 1
- `notebooks/wellsight/roads/_road_unet.py` — mentioned in 3
- `notebooks/wellsight/roads/_road_unet_1m.py` — mentioned in 4
- `notebooks/wellsight/roads/_road_unet_1m_recall.py` — mentioned in 8
- `notebooks/wellsight/roads/_road_unet_multiblock.py` — mentioned in 2
