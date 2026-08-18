# Script usage audit

Import edges are resolved exactly: each file's `sys.path.insert` expressions are folded into real directories, then module names are resolved against them in order. 39 module names exist in both `notebooks/wellsight` and `notebooks/wellsight_v2`, so stem-matching produces a wrong graph. See the module docstring for the full methodology.

**This audit moves nothing.**

| Verdict | Count | Meaning |
|---|---:|---|
| ACTIVE | 124 | reachable from an entry point |
| HISTORICAL | 28 | ran, and cited in docs. Keep for reproducibility |
| ORPHAN | 34 | ran, nothing documents it. Ask |
| SUPERSEDED | 0 | never ran, has a v2 twin. Archive candidate |
| UNREFERENCED | 24 | never ran, no twin. Investigate individually |

## DOCUMENTED (0)

_none_

## HISTORICAL (28)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/_compare_known_wells.py` | 3 | yes | - |
| `notebooks/wellsight/_unet_instance_eval.py` | 1 | yes | - |
| `notebooks/wellsight/build/_build_diagnostics_9t.py` | 2 | yes | - |
| `notebooks/wellsight/roads/_build_road_multiblock_dataset.py` | 3 | yes | - |
| `notebooks/wellsight/roads/_road_unet_multiblock.py` | 6 | yes | - |
| `notebooks/wellsight_v2/s1_build/_build_data_3x3_partial_westernpa.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s2_labels/_build_pit_dataset.py` | 3 | yes | - |
| `notebooks/wellsight_v2/s2_labels/_build_pad_road_dataset.py` | 3 | yes | - |
| `notebooks/wellsight_v2/s2_labels/_prep_road_1m.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s3_train/_multitask_unet.py` | 10 | yes | - |
| `notebooks/wellsight_v2/s3_train/_pad_maskrcnn.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s3_train/_pit_maskrcnn.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s3_train/_pit_unet_v2.py` | 6 | yes | - |
| `notebooks/wellsight_v2/s3_train/_pit_yolo.py` | 2 | yes | - |
| `notebooks/wellsight_v2/s3_train/_pad_unet.py` | 7 | yes | - |
| `notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py` | 8 | yes | - |
| `notebooks/wellsight_v2/s4_infer/_infer_roads_data_3x3.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s4_infer/_pad_maskrcnn_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/s4_infer/_pit_maskrcnn_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/s4_infer/_pit_yolo_infer.py` | 2 | yes | - |
| `notebooks/wellsight_v2/s5_eval/_export_pit_floor_threshold_tifs.py` | 2 | yes | - |
| `notebooks/wellsight_v2/s5_eval/_heldout_rim_containment_9t.py` | 4 | yes | - |
| `notebooks/wellsight_v2/s5_eval/_pit_optimize.py` | 3 | yes | - |
| `notebooks/wellsight_v2/s6_review/_build_road_review_package.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s6_review/_road_corrections_diff.py` | 1 | yes | - |
| `notebooks/wellsight_v2/s7_analysis/_bold_vs_faint_roads.py` | 3 | yes | - |
| `notebooks/wellsight_v2/s7_analysis/_classify_9t_roads_bold_faint.py` | 3 | yes | - |
| `notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py` | 3 | yes | - |

## ORPHAN (34)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/analysis/_chm_age_proxy.py` | 2 | - | - |
| `notebooks/wellsight/analysis/_chm_age_proxy_v2.py` | 2 | - | - |
| `notebooks/wellsight/build/_build_3x3_hillshades_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_chm_e1423n2238.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_chm_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_dsm_chm_westernpa.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_hillshade_variants.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_hillshades_downloadlist7.py` | 2 | - | - |
| `notebooks/wellsight/build/_build_hydrology_9t.py` | 3 | - | - |
| `notebooks/wellsight/build/_build_oilcreek_22tile_mosaic.py` | 2 | - | - |
| `notebooks/wellsight/build/_build_water_2006_oilcreek.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_water_banks_all.py` | 1 | - | - |
| `notebooks/wellsight/build/_build_water_oilcreek_22tile.py` | 2 | - | - |
| `notebooks/wellsight/build/_clean_road_network.py` | 1 | - | - |
| `notebooks/wellsight/build/_filter_streams_roads_mckean.py` | 1 | - | - |
| `notebooks/wellsight/build/_make_derivatives_walkthrough_nb.py` | 1 | - | - |
| `notebooks/wellsight/build/_make_training_walkthrough_nb.py` | 1 | - | - |
| `notebooks/wellsight/build/_predict_multitask_oilcreek.py` | 2 | - | - |
| `notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py` | 1 | - | - |
| `notebooks/wellsight/roads/_road_postfilter.py` | 1 | - | - |
| `notebooks/wellsight_v2/_instance_common.py` | 11 | - | - |
| `notebooks/wellsight_v2/s1_build/_build_data_3x3_derivatives.py` | 2 | - | - |
| `notebooks/wellsight_v2/s2_labels/_build_pad_split.py` | 2 | - | - |
| `notebooks/wellsight_v2/s2_labels/_build_unified_split.py` | 1 | - | - |
| `notebooks/wellsight_v2/s2_labels/_sanity_render.py` | 5 | - | - |
| `notebooks/wellsight_v2/s3_train/_pad_yolo.py` | 2 | - | - |
| `notebooks/wellsight_v2/s4_infer/_pad_yolo_infer.py` | 2 | - | - |
| `notebooks/wellsight_v2/s4_infer/_pit_unet_v2_infer.py` | 7 | - | - |
| `notebooks/wellsight_v2/s5_eval/_heldout_overlap_9t.py` | 3 | - | - |
| `notebooks/wellsight_v2/s5_eval/_plot_iou_strictness_scale_9t.py` | 2 | - | - |
| `notebooks/wellsight_v2/s5_eval/_road_methods_compare.py` | 3 | - | - |
| `notebooks/wellsight_v2/s5_eval/_style_heldout_gpkg.py` | 1 | - | - |
| `notebooks/wellsight_v2/s5_eval/_uncounted_well_recovery_9t.py` | 4 | - | - |
| `tools/rewrite_qgis_paths.py` | 1 | - | - |

## SUPERSEDED (0)

_none_

## UNREFERENCED (24)

| Script | executed | cited | v2 twin |
|---|---:|---:|---:|
| `notebooks/wellsight/_rasterize_instances.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_hillshade_az135.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_banks_oilcreek.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_banks_synthetic.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_solid_oilcreek.py` | 0 | - | - |
| `notebooks/wellsight/build/_build_water_void_density.py` | 0 | - | - |
| `notebooks/wellsight/build/_make_rrim.py` | 0 | yes | - |
| `notebooks/wellsight/fetch/_fetch_3dep_inventory.py` | 0 | - | - |
| `notebooks/wellsight/fetch/_fetch_dense_3x3.py` | 0 | - | - |
| `notebooks/wellsight/fetch/_fetch_pa_laz.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/__init__.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/_build_cornrow_demo_nb.py` | 0 | - | - |
| `notebooks/wellsight/preprocessing/dem_idw_builder.py` | 0 | - | - |
| `notebooks/wellsight_v2/s1_build/_build_contours_data_3x3.py` | 0 | yes | - |
| `notebooks/wellsight_v2/s1_build/_stack_features.py` | 0 | - | - |
| `notebooks/wellsight_v2/s4_infer/_postfilter_tile_candidates.py` | 0 | - | - |
| `notebooks/wellsight_v2/s4_infer/_predict_on_tile.py` | 0 | - | - |
| `notebooks/wellsight_v2/s4_infer/_refine_roads_data_3x3.py` | 0 | yes | - |
| `notebooks/wellsight_v2/s4_infer/_yolo_infer_tile.py` | 0 | - | - |
| `notebooks/wellsight_v2/s5_eval/_pad_cv5_tau_scale.py` | 0 | yes | - |
| `notebooks/wellsight_v2/s5_eval/_pit_cv5_tau_scale.py` | 0 | - | - |
| `notebooks/wellsight_v2/s7_analysis/_score_bold_faint_exemplar_segments.py` | 0 | yes | - |
| `tests/__init__.py` | 0 | - | - |
| `tests/preprocessing/__init__.py` | 0 | - | - |

## ACTIVE — by tree

- `notebooks/wellsight` — 50
- `notebooks/wellsight_v2` — 47
- `ui/pages` — 3
- `roads_studio/__init__.py` — 1
- `roads_studio/app.py` — 1
- `roads_studio/core.py` — 1
- `roads_studio/main.py` — 1
- `roads_studio/train.py` — 1
- `tests/conftest.py` — 1
- `tests/preprocessing` — 1
- `tools/apply_moves.py` — 1
- `tools/audit_script_usage.py` — 1
- `tools/build_reference_index.py` — 1
- `tools/find_duplicates.py` — 1
- `tools/find_unused_scripts.py` — 1
- `tools/plan_archive.py` — 1
- `tools/plan_consolidation.py` — 1
- `tools/plan_stage_refactor.py` — 1
- `tools/verify_backup.py` — 1
- `tools/verify_paths.py` — 1
- `ui/app.py` — 1
- `ui/jobs.py` — 1
- `ui/paths.py` — 1
- `ui/registry.py` — 1
- `ui/state.py` — 1
- `ui/style.py` — 1
- `ui/widgets.py` — 1
