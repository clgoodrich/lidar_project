# Notebook rebuild order — `notebooks/wellsight_v2`

Sequential list. Do them top to bottom. Each one reads what the one above it wrote.

## Done

- [x] **phase_1** — `s1_build/_build_derivatives.py`
- [x] **phase_2** — `s2_labels/_prep_annotations.py`
- [x] **phase_3** — `s2_labels/_build_pit_dataset_v2.py` + `s2_labels/_prep_road_1m.py`

## To do

- [ ] **phase_4** — `s2_labels/_build_pad_road_dataset.py` + `s2_labels/_build_pad_split.py`
- [ ] **phase_5** — `s2_labels/_manifest_guard.py` + `s2_labels/_build_unified_split.py` + `s2_labels/_sanity_render.py`
- [ ] **phase_6** — `s3_train/_pit_unet_cv5.py`
- [ ] **phase_7** — `s3_train/_pad_unet_cv5.py`
- [ ] **phase_8** — `s3_train/_road_unet_1m_recall.py`
- [ ] **phase_9** — `s4_infer/_predict_on_tile.py`
- [ ] **phase_10** — `s4_infer/_postfilter_tile_candidates.py`
- [ ] **phase_11** — `s5_eval/_threshold_common.py`, then `_pit_threshold_products_9t.py`, `_pad_threshold_products_9t.py`, `_road_threshold_products_9t.py`
- [ ] **phase_12** — `s5_eval/_heldout_rim_containment_9t.py`, `_cv5_centroid_precision_pit_pad_9t.py`, `_pit_cv5_tau_scale.py`, `_pad_cv5_tau_scale.py`
- [ ] **phase_13** — `s6_review/_build_pit_review_package.py` + `_pit_corrections_diff.py`, `s6_review/_build_road_review_package.py` + `_road_corrections_diff.py`
- [ ] **phase_14** — `s7_analysis/_well_age_morphology.py`, `_pad_morphology_bins.py`, `_icp_change_9t_rebuild.py`, `_icp_change_classify_9t.py`, `_export_well_age_qgis.py`

## Not in the sequence

Import these, do not transcribe: `_common.py`, `_dl.py`, `_instance_common.py`.

Everything else in `notebooks/wellsight_v2/` is either an optional side branch or
a dead experiment. The full breakdown, with per-script reasoning, is in
`docs/notebook_rebuild_plan_wellsight_v2.md`.
