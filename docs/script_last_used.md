# When was each script last actually run?

Source: `docs/analysis_log.md`, 137 dated entries from 2026-04-30 to 2026-08-06. `last_run` is the newest entry naming the script; `last_edit` is the last commit that touched it.

**They are not the same thing.** A recent `last_edit` with an old `last_run` means the file was refactored, not used — which is the state the 2026-08-12 reorganisation left most of the repo in.

| Bucket | Scripts |
|---|---:|
| run within 45 days | 57 |
| run, but longer ago | 15 |
| **never named in the log** | **110** |

## By tree

| Tree | run <=45d | run older | never in log |
|---|---:|---:|---:|
| `roads_studio` | 0 | 0 | 5 |
| `tests` | 1 | 0 | 5 |
| `tools` | 5 | 0 | 11 |
| `ui` | 0 | 0 | 10 |
| `wellsight` | 3 | 5 | 42 |
| `wellsight_v2` | 48 | 10 | 37 |

## Run within 45 days

- `notebooks/wellsight_v2/_instance_common.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_build_label_grids.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_build_pad_road_dataset.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_build_pad_split.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_prep_annotations.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s2_labels/_sanity_render.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s3_train/_pad_unet.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s3_train/_pit_unet_v2.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s3_train/_road_unet_1m_recall.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s4_infer/_infer_roads_data_3x3.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/s7_analysis/_pad_morphology_bins.py` — last run **2026-08-18**
- `tests/test_no_legacy_id_columns.py` — last run **2026-08-18**
- `notebooks/wellsight_v2/_common.py` — last run **2026-08-17**
- `notebooks/wellsight_v2/s1_build/_make_rrim.py` — last run **2026-08-15**
- `notebooks/wellsight_v2/s2_labels/_prep_road_1m.py` — last run **2026-08-12**
- `notebooks/wellsight_v2/s5_eval/_heldout_rim_containment_9t.py` — last run **2026-08-12**
- `notebooks/wellsight_v2/s5_eval/_road_methods_compare.py` — last run **2026-08-12**
- `notebooks/wellsight_v2/s5_eval/_road_optimize.py` — last run **2026-08-12**
- `tools/apply_moves.py` — last run **2026-08-12**
- `tools/convert_path_literals.py` — last run **2026-08-12**
- `tools/golden.py` — last run **2026-08-12**
- `tools/verify_no_path_literals.py` — last run **2026-08-12**
- `tools/verify_paths.py` — last run **2026-08-12**
- `notebooks/wellsight_v2/s2_labels/_rebuild_labels_road_9t_1m.py` — last run **2026-08-06**
- `notebooks/wellsight_v2/s2_labels/_merge_review_added_roads_613590_into_roads_shp.py` — last run **2026-08-05**
- `notebooks/wellsight_v2/s7_analysis/_bold_vs_faint_roads.py` — last run **2026-08-05**
- `notebooks/wellsight_v2/s7_analysis/_classify_9t_roads_bold_faint.py` — last run **2026-08-05**
- `notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py` — last run **2026-08-05**
- `notebooks/wellsight_v2/s7_analysis/_road_morphology_bins.py` — last run **2026-08-05**
- `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py` — last run **2026-08-04**
- `notebooks/wellsight_v2/s5_eval/_match_rules_pit_pad_9t.py` — last run **2026-08-04**
- `notebooks/wellsight/build/_icp_change_map.py` — last run **2026-07-31**
- `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py` — last run **2026-07-31**
- `notebooks/wellsight_v2/s7_analysis/_score_bold_faint_exemplar_segments.py` — last run **2026-07-31**
- `notebooks/wellsight_v2/s3_train/_road_sweep_202607.py` — last run **2026-07-29**
- `notebooks/wellsight_v2/s6_review/_build_drainage_review_package.py` — last run **2026-07-29**
- `notebooks/wellsight_v2/s6_review/_build_road_corrections_613590.py` — last run **2026-07-29**
- `notebooks/wellsight_v2/s6_review/_calibrate_drainage_extraction_9t.py` — last run **2026-07-29**
- `notebooks/wellsight_v2/s6_review/_overlay_drainage_review_613590.py` — last run **2026-07-29**
- `notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py` — last run **2026-07-28**
- `notebooks/wellsight_v2/s5_eval/_pad_cv5_tau_scale.py` — last run **2026-07-28**
- `notebooks/wellsight_v2/_dl.py` — last run **2026-07-27**
- `notebooks/wellsight_v2/s5_eval/_export_pit_floor_threshold_tifs.py` — last run **2026-07-27**
- `notebooks/wellsight_v2/s5_eval/_pad_threshold_products_9t.py` — last run **2026-07-27**
- `notebooks/wellsight_v2/s5_eval/_road_threshold_products_9t.py` — last run **2026-07-27**
- `notebooks/wellsight_v2/s5_eval/_threshold_common.py` — last run **2026-07-27**
- `notebooks/wellsight_v2/s7_analysis/_icp_change_9t.py` — last run **2026-07-25**
- `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` — last run **2026-07-23**
- `notebooks/wellsight_v2/s3_train/_road_unet_1m_corrected.py` — last run **2026-07-20**
- `notebooks/wellsight_v2/s5_eval/_compare_corrected_613590.py` — last run **2026-07-20**
- `notebooks/wellsight_v2/s7_analysis/_photo_source_locations.py` — last run **2026-07-20**
- `notebooks/wellsight_v2/s7_analysis/_well_provenance_flags.py` — last run **2026-07-20**
- `notebooks/wellsight_v2/s7_analysis/_well_age_morphology.py` — last run **2026-07-19**
- `notebooks/wellsight/_compare_known_wells.py` — last run **2026-07-02**
- `notebooks/wellsight_v2/s5_eval/_pit_optimize.py` — last run **2026-07-01**
- `notebooks/wellsight/build/_icp_old_vs_new.py` — last run **2026-06-29**

## Run, but longer ago

- `notebooks/wellsight_v2/s1_build/archive/_fetch_nisar_9t.py` — last run 2026-06-27 (46 days)
- `notebooks/wellsight_v2/s1_build/archive/_build_exag_derivatives.py` — last run 2026-06-17 (56 days)
- `notebooks/wellsight_v2/s1_build/archive/_fetch_permian_grids.py` — last run 2026-06-17 (56 days)
- `notebooks/wellsight_v2/s4_infer/_pad_unet_infer_grid.py` — last run 2026-06-17 (56 days)
- `notebooks/wellsight_v2/s3_train/_drainage_unet_1m.py` — last run 2026-06-16 (57 days)
- `notebooks/wellsight/roads/_build_road_multiblock_dataset.py` — last run 2026-06-14 (59 days)
- `notebooks/wellsight/roads/_road_unet_multiblock.py` — last run 2026-06-14 (59 days)
- `notebooks/wellsight_v2/s1_build/archive/_build_contours_data_3x3.py` — last run 2026-06-08 (65 days)
- `notebooks/wellsight/build/_filter_streams_xsec_9t.py` — last run 2026-06-07 (66 days)
- `notebooks/wellsight/roads/_road_unet_1m.py` — last run 2026-06-07 (66 days)
- `notebooks/wellsight_v2/s1_build/_build_data_3x3_partial_westernpa.py` — last run 2026-06-07 (66 days)
- `notebooks/wellsight_v2/s4_infer/_refine_roads_data_3x3.py` — last run 2026-06-07 (66 days)
- `notebooks/wellsight_v2/s3_train/_pad_maskrcnn.py` — last run 2026-06-06 (67 days)
- `notebooks/wellsight_v2/s3_train/_pit_maskrcnn.py` — last run 2026-06-06 (67 days)
- `notebooks/wellsight/build/_build_diagnostics_9t.py` — last run 2026-06-03 (70 days)

## Never named in the log

The log started 2026-04-30. Anything older than that, or run without being logged, lands here. Absence is weak evidence, not proof.

- `notebooks/wellsight/_common.py`
- `notebooks/wellsight/_dl.py`
- `notebooks/wellsight/_rasterize_instances.py`
- `notebooks/wellsight/_unet_instance_eval.py`
- `notebooks/wellsight/analysis/_chm_age_proxy.py`
- `notebooks/wellsight/analysis/_chm_age_proxy_v2.py`
- `notebooks/wellsight/build/_build_3x3_hillshades_mckean.py`
- `notebooks/wellsight/build/_build_chm_e1423n2238.py`
- `notebooks/wellsight/build/_build_chm_mckean.py`
- `notebooks/wellsight/build/_build_dsm_chm_westernpa.py`
- `notebooks/wellsight/build/_build_hillshade_az135.py`
- `notebooks/wellsight/build/_build_hillshade_variants.py`
- `notebooks/wellsight/build/_build_hillshades_downloadlist7.py`
- `notebooks/wellsight/build/_build_hydrology_9t.py`
- `notebooks/wellsight/build/_build_oilcreek_22tile_mosaic.py`
- `notebooks/wellsight/build/_build_streams_9t.py`
- `notebooks/wellsight/build/_build_streams_t10k_mckean.py`
- `notebooks/wellsight/build/_build_water_2006_oilcreek.py`
- `notebooks/wellsight/build/_build_water_banks_all.py`
- `notebooks/wellsight/build/_build_water_banks_oilcreek.py`
- `notebooks/wellsight/build/_build_water_banks_synthetic.py`
- `notebooks/wellsight/build/_build_water_oilcreek_22tile.py`
- `notebooks/wellsight/build/_build_water_solid_oilcreek.py`
- `notebooks/wellsight/build/_build_water_void_density.py`
- `notebooks/wellsight/build/_clean_road_network.py`
- `notebooks/wellsight/build/_filter_streams_chunked_mckean.py`
- `notebooks/wellsight/build/_filter_streams_roads_mckean.py`
- `notebooks/wellsight/build/_filter_streams_xsection_mckean.py`
- `notebooks/wellsight/build/_make_derivatives_walkthrough_nb.py`
- `notebooks/wellsight/build/_make_training_walkthrough_nb.py`
- `notebooks/wellsight/build/_predict_multitask_oilcreek.py`
- `notebooks/wellsight/build/_predict_on_mkf.py`
- `notebooks/wellsight/fetch/_fetch_3dep_inventory.py`
- `notebooks/wellsight/fetch/_fetch_dense_3x3.py`
- `notebooks/wellsight/fetch/_fetch_oilcreek_contiguous_20.py`
- `notebooks/wellsight/fetch/_fetch_pa_laz.py`
- `notebooks/wellsight/preprocessing/__init__.py`
- `notebooks/wellsight/preprocessing/_build_cornrow_demo_nb.py`
- `notebooks/wellsight/preprocessing/cornrow_filter.py`
- `notebooks/wellsight/preprocessing/dem_idw_builder.py`
- `notebooks/wellsight/roads/_road_postfilter.py`
- `notebooks/wellsight/roads/_road_unet.py`
- `notebooks/wellsight_v2/s1_build/_build_3x3_hillshades.py`
- `notebooks/wellsight_v2/s1_build/_build_data_3x3_derivatives.py`
- `notebooks/wellsight_v2/s1_build/_build_derivatives.py`
- `notebooks/wellsight_v2/s1_build/archive/_stack_features.py`
- `notebooks/wellsight_v2/s2_labels/_build_orient_labels.py`
- `notebooks/wellsight_v2/s2_labels/_build_pit_dataset.py`
- `notebooks/wellsight_v2/s2_labels/_build_unified_split.py`
- `notebooks/wellsight_v2/s2_labels/_manifest_guard.py`
- `notebooks/wellsight_v2/s3_train/_multitask_unet.py`
- `notebooks/wellsight_v2/s3_train/_pad_yolo.py`
- `notebooks/wellsight_v2/s3_train/_pit_yolo.py`
- `notebooks/wellsight_v2/s4_infer/_pad_maskrcnn_infer.py`
- `notebooks/wellsight_v2/s4_infer/_pad_yolo_infer.py`
- `notebooks/wellsight_v2/s4_infer/_pit_maskrcnn_infer.py`
- `notebooks/wellsight_v2/s4_infer/_pit_unet_v2_infer.py`
- `notebooks/wellsight_v2/s4_infer/_pit_yolo_infer.py`
- `notebooks/wellsight_v2/s4_infer/_postfilter_tile_candidates.py`
- `notebooks/wellsight_v2/s4_infer/_predict_on_tile.py`
- `notebooks/wellsight_v2/s4_infer/_road_infer.py`
- `notebooks/wellsight_v2/s4_infer/_yolo_infer_tile.py`
- `notebooks/wellsight_v2/s5_eval/_build_undecided_pit_candidates_9t.py`
- `notebooks/wellsight_v2/s5_eval/_cv5_centroid_precision_pit_pad_9t.py`
- `notebooks/wellsight_v2/s5_eval/_heldout_overlap_9t.py`
- `notebooks/wellsight_v2/s5_eval/_map_cv5_unmatched_pit_thr0p50_9t.py`
- `notebooks/wellsight_v2/s5_eval/_pit_cv5_tau_scale.py`
- `notebooks/wellsight_v2/s5_eval/_pit_threshold_products_9t.py`
- `notebooks/wellsight_v2/s5_eval/_plot_iou_strictness_scale_9t.py`
- `notebooks/wellsight_v2/s5_eval/_reeval_instance_precision_9t.py`
- `notebooks/wellsight_v2/s5_eval/_road_sweep_aggregate.py`
- `notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py`
- `notebooks/wellsight_v2/s5_eval/_style_heldout_gpkg.py`
- `notebooks/wellsight_v2/s5_eval/_uncounted_well_recovery_9t.py`
- `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py`
- `notebooks/wellsight_v2/s6_review/_build_road_review_package.py`
- `notebooks/wellsight_v2/s6_review/_pit_corrections_diff.py`
- `notebooks/wellsight_v2/s6_review/_road_corrections_diff.py`
- `notebooks/wellsight_v2/s7_analysis/_export_well_age_qgis.py`
- `roads_studio/__init__.py`
- `roads_studio/app.py`
- `roads_studio/core.py`
- `roads_studio/main.py`
- `roads_studio/train.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/preprocessing/__init__.py`
- `tests/preprocessing/test_cornrow_filter.py`
- `tests/test_paths_config.py`
- `tools/audit_script_usage.py`
- `tools/build_reference_index.py`
- `tools/check_archived_still_used.py`
- `tools/find_duplicates.py`
- `tools/plan_archive.py`
- `tools/plan_stage_refactor.py`
- `tools/plan_v1_archive.py`
- `tools/rewrite_qgis_paths.py`
- `tools/script_last_used.py`
- `tools/verify_backup.py`
- `tools/write_provenance.py`
- `ui/app.py`
- `ui/jobs.py`
- `ui/pages/1_Roads.py`
- `ui/pages/2_Analysis.py`
- `ui/pages/3_Jobs.py`
- `ui/paths.py`
- `ui/registry.py`
- `ui/state.py`
- `ui/style.py`
- `ui/widgets.py`
