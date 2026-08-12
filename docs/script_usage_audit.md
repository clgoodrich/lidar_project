# Script usage audit

Import edges are resolved exactly: each file's `sys.path.insert` expressions are folded into real directories, then module names are resolved against them in order. 39 module names exist in both `notebooks/wellsight` and `notebooks/wellsight_v2`, so stem-matching produces a wrong graph. See the module docstring for the full methodology.

**This audit moves nothing.**

| Verdict | Count | Meaning |
|---|---:|---|
| ACTIVE | 68 | reachable from an entry point |
| HISTORICAL | 55 | ran, and cited in docs. Keep for reproducibility |
| ORPHAN | 50 | ran, nothing documents it. Ask |
| SUPERSEDED | 6 | never ran, has a v2 twin. Archive candidate |
| UNREFERENCED | 30 | never ran, no twin. Investigate individually |

## DOCUMENTED (0)

_none_

## HISTORICAL (55)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/_compare_known_wells.py` | 3 | yes | - |
| `notebooks/wellsight/_unet_instance_eval.py` | 1 | yes | - |
| `notebooks/wellsight/annotations/_build_pit_dataset.py` | 3 | yes | yes |
| `notebooks/wellsight/annotations/_build_plat_road_dataset.py` | 3 | yes | yes |
| `notebooks/wellsight/build/_build_data_3x3_partial_westernpa.py` | 1 | yes | yes |
| `notebooks/wellsight/build/_build_diagnostics_9t.py` | 2 | yes | - |
| `notebooks/wellsight/build/_build_road_review_package.py` | 1 | yes | yes |
| `notebooks/wellsight/build/_build_streams_9t.py` | 2 | yes | - |
| `notebooks/wellsight/build/_filter_streams_xsec_9t.py` | 2 | yes | - |
| `notebooks/wellsight/build/_icp_change_map.py` | 2 | yes | - |
| `notebooks/wellsight/build/_icp_old_vs_new.py` | 1 | yes | - |
| `notebooks/wellsight/build/_infer_roads_data_3x3.py` | 1 | yes | yes |
| `notebooks/wellsight/build/_pit_optimize.py` | 3 | yes | yes |
| `notebooks/wellsight/build/_road_corrections_diff.py` | 1 | yes | yes |
| `notebooks/wellsight/multitask/_multitask_unet.py` | 10 | yes | yes |
| `notebooks/wellsight/pits/_pit_maskrcnn.py` | 1 | yes | yes |
| `notebooks/wellsight/pits/_pit_maskrcnn_infer.py` | 2 | yes | yes |
| `notebooks/wellsight/pits/_pit_yolo.py` | 2 | yes | yes |
| `notebooks/wellsight/pits/_pit_yolo_infer.py` | 2 | yes | yes |
| `notebooks/wellsight/plats/_pad_maskrcnn.py` | 1 | yes | yes |
| `notebooks/wellsight/plats/_pad_maskrcnn_infer.py` | 2 | yes | yes |
| `notebooks/wellsight/roads/_build_road_multiblock_dataset.py` | 3 | yes | - |
| `notebooks/wellsight/roads/_road_unet_1m.py` | 8 | yes | - |
| `notebooks/wellsight/roads/_road_unet_1m_recall.py` | 8 | yes | yes |
| `notebooks/wellsight/roads/_road_unet_multiblock.py` | 6 | yes | - |
| `notebooks/wellsight_v2/analysis/_bold_vs_faint_roads.py` | 3 | yes | - |
| `notebooks/wellsight_v2/analysis/_classify_9t_roads_bold_faint.py` | 3 | yes | - |
| `notebooks/wellsight_v2/analysis/_road_morphology_bins.py` | 3 | yes | - |
| `notebooks/wellsight_v2/annotations/_build_pit_dataset.py` | 3 | yes | - |
| `notebooks/wellsight_v2/annotations/_build_plat_road_dataset.py` | 3 | yes | - |
| `notebooks/wellsight_v2/build/_build_data_3x3_partial_westernpa.py` | 1 | yes | - |
| `notebooks/wellsight_v2/build/_build_drainage_review_package.py` | 1 | yes | - |
| `notebooks/wellsight_v2/build/_build_label_grids.py` | 3 | yes | - |
| `notebooks/wellsight_v2/build/_build_road_review_package.py` | 1 | yes | - |
| `notebooks/wellsight_v2/build/_calibrate_drainage_extraction_9t.py` | 2 | yes | - |
| `notebooks/wellsight_v2/build/_fetch_permian_grids.py` | 1 | yes | - |
| `notebooks/wellsight_v2/build/_icp_change_9t.py` | 3 | yes | - |
| `notebooks/wellsight_v2/build/_icp_change_9t_rebuild.py` | 3 | yes | - |
| `notebooks/wellsight_v2/build/_icp_change_classify_9t.py` | 4 | yes | - |
| `notebooks/wellsight_v2/build/_infer_roads_data_3x3.py` | 1 | yes | - |
| `notebooks/wellsight_v2/build/_pit_optimize.py` | 3 | yes | - |
| `notebooks/wellsight_v2/build/_road_corrections_diff.py` | 1 | yes | - |
| `notebooks/wellsight_v2/drainage/_drainage_unet_1m.py` | 8 | yes | - |
| `notebooks/wellsight_v2/eval/_export_pit_floor_threshold_tifs.py` | 2 | yes | - |
| `notebooks/wellsight_v2/eval/_heldout_rim_containment_9t.py` | 4 | yes | - |
| `notebooks/wellsight_v2/multitask/_multitask_unet.py` | 10 | yes | - |
| `notebooks/wellsight_v2/pits/_pit_maskrcnn.py` | 1 | yes | - |
| `notebooks/wellsight_v2/pits/_pit_maskrcnn_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/pits/_pit_yolo.py` | 2 | yes | - |
| `notebooks/wellsight_v2/pits/_pit_yolo_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/plats/_pad_maskrcnn.py` | 1 | yes | - |
| `notebooks/wellsight_v2/plats/_pad_maskrcnn_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/plats/_pad_unet_cv5.py` | 7 | yes | - |
| `notebooks/wellsight_v2/plats/_pad_unet_infer_grid.py` | 2 | yes | - |
| `notebooks/wellsight_v2/roads/_road_unet_1m_recall.py` | 8 | yes | - |

## ORPHAN (50)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/_instance_common.py` | 11 | - | yes |
| `notebooks/wellsight/analysis/_chm_age_proxy.py` | 2 | - | - |
| `notebooks/wellsight/analysis/_chm_age_proxy_v2.py` | 2 | - | - |
| `notebooks/wellsight/annotations/_build_plat_split.py` | 2 | - | yes |
| `notebooks/wellsight/annotations/_build_unified_split.py` | 1 | - | yes |
| `notebooks/wellsight/annotations/_sanity_render.py` | 5 | - | yes |
| `notebooks/wellsight/build/_build_3x3_hillshades.py` | 1 | - | yes |
| `notebooks/wellsight/build/_build_3x3_hillshades_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_chm_e1423n2238.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_chm_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_data_3x3_derivatives.py` | 2 | - | yes |
| `notebooks/wellsight/build/_build_dsm_chm_westernpa.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_hillshade_variants.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_hillshades_downloadlist7.py` | 2 | - | - |
| `notebooks/wellsight/build/_build_hydrology_9t.py` | 3 | - | - |
| `notebooks/wellsight/build/_build_oilcreek_22tile_mosaic.py` | 2 | - | - |
| `notebooks/wellsight/build/_build_streams_t10k_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_water_2006_oilcreek.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_water_banks_all.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_water_oilcreek_22tile.py` | 2 | - | - |
| `notebooks/wellsight/build/_clean_road_network.py` | 1 | - | - |
| `notebooks/wellsight/build/_filter_streams_chunked_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_filter_streams_roads_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_filter_streams_xsection_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_make_derivatives_walkthrough_nb.py` | 1 | - | - |
| `notebooks/wellsight/build/_make_training_walkthrough_nb.py` | 1 | - | - |
| `notebooks/wellsight/build/_predict_multitask_oilcreek.py` | 2 | - | - |
| `notebooks/wellsight/build/_road_methods_compare.py` | 3 | - | yes |
| `notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py` | 1 | - | - |
| `notebooks/wellsight/pits/_pit_unet_v2_infer.py` | 7 | - | yes |
| `notebooks/wellsight/plats/_pad_yolo.py` | 2 | - | yes |
| `notebooks/wellsight/plats/_pad_yolo_infer.py` | 2 | - | yes |
| `notebooks/wellsight/roads/_road_postfilter.py` | 1 | - | - |
| `notebooks/wellsight_v2/_instance_common.py` | 11 | - | - |
| `notebooks/wellsight_v2/annotations/_build_plat_split.py` | 2 | - | - |
| `notebooks/wellsight_v2/annotations/_build_unified_split.py` | 1 | - | - |
| `notebooks/wellsight_v2/annotations/_sanity_render.py` | 5 | - | - |
| `notebooks/wellsight_v2/build/_build_3x3_hillshades.py` | 1 | - | - |
| `notebooks/wellsight_v2/build/_build_data_3x3_derivatives.py` | 2 | - | - |
| `notebooks/wellsight_v2/build/_build_pit_review_package.py` | 1 | - | - |
| `notebooks/wellsight_v2/build/_pit_corrections_diff.py` | 1 | - | - |
| `notebooks/wellsight_v2/build/_road_methods_compare.py` | 3 | - | - |
| `notebooks/wellsight_v2/eval/_heldout_overlap_9t.py` | 3 | - | - |
| `notebooks/wellsight_v2/eval/_plot_iou_strictness_scale_9t.py` | 2 | - | - |
| `notebooks/wellsight_v2/eval/_style_heldout_gpkg.py` | 1 | - | - |
| `notebooks/wellsight_v2/eval/_uncounted_well_recovery_9t.py` | 4 | - | - |
| `notebooks/wellsight_v2/pits/_pit_unet_v2_infer.py` | 7 | - | - |
| `notebooks/wellsight_v2/plats/_pad_yolo.py` | 2 | - | - |
| `notebooks/wellsight_v2/plats/_pad_yolo_infer.py` | 2 | - | - |
| `tools/rewrite_qgis_paths.py` | 1 | - | - |

## SUPERSEDED (6)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/build/_build_contours_data_3x3.py` | 0 | yes | yes |
| `notebooks/wellsight/build/_build_derivatives.py` | 0 | yes | yes |
| `notebooks/wellsight/build/_postfilter_tile_candidates.py` | 0 | - | yes |
| `notebooks/wellsight/build/_predict_on_tile.py` | 0 | - | yes |
| `notebooks/wellsight/build/_refine_roads_data_3x3.py` | 0 | yes | yes |
| `notebooks/wellsight/build/_yolo_infer_tile.py` | 0 | - | yes |

## UNREFERENCED (30)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/_rasterize_instances.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_hillshade_az135.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_banks_oilcreek.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_banks_synthetic.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_solid_oilcreek.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_void_density.py` | 0 | - | - |
| `notebooks/wellsight/build/_make_rrim.py` | 0 | yes | - |
| `notebooks/wellsight/build/_predict_on_mkf.py` | 0 | - | - |
| `notebooks/wellsight/fetch/_fetch_3dep_inventory.py` | 0 | - | - |
| `notebooks/wellsight/fetch/_fetch_dense_3x3.py` | 0 | - | - |
| `notebooks/wellsight/fetch/_fetch_pa_laz.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/__init__.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/_build_cornrow_demo_nb.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/dem_idw_builder.py` | 0 | - | - |
| `notebooks/wellsight_v2/analysis/_score_bold_faint_exemplar_segments.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_build_contours_data_3x3.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_build_derivatives.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_build_exag_derivatives.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_build_extra_channels.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_fetch_nisar_9t.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_overlay_drainage_review_613590.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_postfilter_tile_candidates.py` | 0 | - | - |
| `notebooks/wellsight_v2/build/_predict_on_tile.py` | 0 | - | - |
| `notebooks/wellsight_v2/build/_refine_roads_data_3x3.py` | 0 | yes | - |
| `notebooks/wellsight_v2/build/_yolo_infer_tile.py` | 0 | - | - |
| `notebooks/wellsight_v2/eval/_pad_cv5_tau_scale.py` | 0 | yes | - |
| `notebooks/wellsight_v2/eval/_pit_cv5_tau_scale.py` | 0 | - | - |
| `roads_studio/train.py` | 0 | - | - |
| `tests/__init__.py` | 0 | - | - |
| `tests/preprocessing/__init__.py` | 0 | - | - |

## ACTIVE — by tree

- `notebooks/wellsight_v2` — 33
- `notebooks/wellsight` — 10
- `ui/pages` — 3
- `roads_studio/__init__.py` — 1
- `roads_studio/app.py` — 1
- `roads_studio/core.py` — 1
- `roads_studio/main.py` — 1
- `tests/conftest.py` — 1
- `tests/preprocessing` — 1
- `tools/apply_moves.py` — 1
- `tools/audit_script_usage.py` — 1
- `tools/build_reference_index.py` — 1
- `tools/find_duplicates.py` — 1
- `tools/find_unused_scripts.py` — 1
- `tools/plan_archive.py` — 1
- `tools/plan_consolidation.py` — 1
- `tools/verify_backup.py` — 1
- `tools/verify_paths.py` — 1
- `ui/app.py` — 1
- `ui/jobs.py` — 1
- `ui/paths.py` — 1
- `ui/registry.py` — 1
- `ui/state.py` — 1
- `ui/style.py` — 1
- `ui/widgets.py` — 1
