# v1 archive plan — the two-month rule

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

Rule: run on or after **2026-06-12** -> keep, else archive. Evidence is `docs/analysis_log.md`. Nothing is deleted; everything moves to `data/99_archive/superseded/notebooks_wellsight/` with structure preserved.

**11 stay, 77 archive** of 88.

## Staying, and why

| Script | Reason |
|---|---|
| `_common.py` | imported by kept build/_icp_old_vs_new.py |
| `_compare_known_wells.py` | run 2026-07-02 (within two months) |
| `_dl.py` | imported by kept roads/_road_unet_multiblock.py |
| `build/_icp_change_map.py` | run 2026-07-31 (within two months) |
| `build/_icp_old_vs_new.py` | run 2026-06-29 (within two months) |
| `build/_make_rrim.py` | run 2026-07-07 (within two months) |
| `preprocessing/__init__.py` | package marker for kept preprocessing/cornrow_filter.py |
| `preprocessing/cornrow_filter.py` | imported from outside v1 by tests/preprocessing/test_cornrow_filter.py |
| `preprocessing/dem_idw_builder.py` | imported by kept preprocessing/__init__.py |
| `roads/_build_road_multiblock_dataset.py` | run 2026-06-14 (within two months) |
| `roads/_road_unet_multiblock.py` | run 2026-06-14 (within two months) |

## Archiving

No `analysis_log.md` entry on or after the cutoff, and nothing outside v1 imports them.

- `_instance_common.py` — last run never in log
- `_rasterize_instances.py` — last run never in log
- `_unet_instance_eval.py` — last run never in log
- `analysis/_chm_age_proxy.py` — last run never in log
- `analysis/_chm_age_proxy_v2.py` — last run never in log
- `annotations/_build_pit_dataset.py` — last run never in log
- `annotations/_build_plat_road_dataset.py` — last run never in log
- `annotations/_build_plat_split.py` — last run never in log
- `annotations/_build_unified_split.py` — last run never in log
- `annotations/_prep_annotations.py` — last run never in log
- `annotations/_sanity_render.py` — last run never in log
- `build/_build_3x3_hillshades.py` — last run never in log
- `build/_build_3x3_hillshades_mckean.py` — last run never in log
- `build/_build_chm_e1423n2238.py` — last run never in log
- `build/_build_chm_mckean.py` — last run never in log
- `build/_build_contours_data_3x3.py` — last run 2026-06-08
- `build/_build_data_3x3_derivatives.py` — last run never in log
- `build/_build_data_3x3_partial_westernpa.py` — last run never in log
- `build/_build_derivatives.py` — last run never in log
- `build/_build_diagnostics_9t.py` — last run 2026-06-03
- `build/_build_dsm_chm_westernpa.py` — last run never in log
- `build/_build_hillshade_az135.py` — last run never in log
- `build/_build_hillshade_variants.py` — last run never in log
- `build/_build_hillshades_downloadlist7.py` — last run never in log
- `build/_build_hydrology_9t.py` — last run never in log
- `build/_build_oilcreek_22tile_mosaic.py` — last run never in log
- `build/_build_road_review_package.py` — last run never in log
- `build/_build_streams_9t.py` — last run never in log
- `build/_build_streams_t10k_mckean.py` — last run never in log
- `build/_build_water_2006_oilcreek.py` — last run never in log
- `build/_build_water_banks_all.py` — last run never in log
- `build/_build_water_banks_oilcreek.py` — last run never in log
- `build/_build_water_banks_synthetic.py` — last run never in log
- `build/_build_water_oilcreek_22tile.py` — last run never in log
- `build/_build_water_solid_oilcreek.py` — last run never in log
- `build/_build_water_void_density.py` — last run never in log
- `build/_clean_road_network.py` — last run never in log
- `build/_filter_streams_chunked_mckean.py` — last run never in log
- `build/_filter_streams_roads_mckean.py` — last run never in log
- `build/_filter_streams_xsec_9t.py` — last run 2026-06-07
- `build/_filter_streams_xsection_mckean.py` — last run never in log
- `build/_infer_roads_data_3x3.py` — last run never in log
- `build/_make_derivatives_walkthrough_nb.py` — last run never in log
- `build/_make_training_walkthrough_nb.py` — last run never in log
- `build/_pit_optimize.py` — last run never in log
- `build/_postfilter_tile_candidates.py` — last run never in log
- `build/_predict_multitask_oilcreek.py` — last run never in log
- `build/_predict_on_mkf.py` — last run never in log
- `build/_predict_on_tile.py` — last run never in log
- `build/_refine_roads_data_3x3.py` — last run never in log
- `build/_road_corrections_diff.py` — last run never in log
- `build/_road_methods_compare.py` — last run never in log
- `build/_road_optimize.py` — last run never in log
- `build/_yolo_infer_tile.py` — last run never in log
- `fetch/_fetch_3dep_inventory.py` — last run never in log
- `fetch/_fetch_dense_3x3.py` — last run never in log
- `fetch/_fetch_oilcreek_contiguous_20.py` — last run never in log
- `fetch/_fetch_pa_laz.py` — last run never in log
- `multitask/_multitask_unet.py` — last run never in log
- `pits/_pit_maskrcnn.py` — last run never in log
- `pits/_pit_maskrcnn_infer.py` — last run never in log
- `pits/_pit_unet_v2.py` — last run never in log
- `pits/_pit_unet_v2_infer.py` — last run never in log
- `pits/_pit_yolo.py` — last run never in log
- `pits/_pit_yolo_infer.py` — last run never in log
- `pits/_stack_features.py` — last run never in log
- `plats/_pad_maskrcnn.py` — last run never in log
- `plats/_pad_maskrcnn_infer.py` — last run never in log
- `plats/_pad_yolo.py` — last run never in log
- `plats/_pad_yolo_infer.py` — last run never in log
- `plats/_plat_unet.py` — last run never in log
- `preprocessing/_build_cornrow_demo_nb.py` — last run never in log
- `roads/_prep_road_1m.py` — last run never in log
- `roads/_road_postfilter.py` — last run never in log
- `roads/_road_unet.py` — last run never in log
- `roads/_road_unet_1m.py` — last run 2026-06-07
- `roads/_road_unet_1m_recall.py` — last run never in log
