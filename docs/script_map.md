# What every script in wellsight_v2 does

> **Paths in this document are as-of its date.** The repository moved to an
> area-major layout on 2026-08-12/13 (`data/<area>/{derived,models,results}/`,
> ground truth in `qgis/annotations/`). This file is a historical record and is
> deliberately NOT rewritten — rewriting it would make the record describe a
> world that did not exist when the work happened. Current layout: `STRUCTURE.md`.

One line each, from the docstring. 92 scripts.

## s1_build (10) - LAZ to DEM to channels

| Script | What it does |
|---|---|
| `_build_3x3_hillshades.py` | Build 1 m DEM + hillshade for every non-overlapping 3x3 mosaic in data/source_laz/westernpa/. |
| `_build_contours_data_3x3.py` | Generate elevation contours from each per-block DEM in a data_3x3 region. |
| `_build_data_3x3_derivatives.py` | Build the full WellSight derivative stack for every 3x3 block under |
| `_build_data_3x3_partial_westernpa.py` | Group EVERY WesternPA 2019 D20 LAZ tile into a derivative block. |
| `_build_derivatives.py` | Generic LAZ -> derivative-stack builder. |
| `_build_exag_derivatives.py` | Vertically-exaggerated openness + slope from an existing DEM (annotation aid). |
| `_build_extra_channels.py` | Experimental *linear-feature* channels for road/trail detection. |
| `_fetch_nisar_9t.py` | Fetch NISAR L-band granules covering the 9t core (NW Pennsylvania). |
| `_fetch_permian_grids.py` | Fetch USGS 3DEP LPC tiles for contiguous 3x3 grids over Permian well clusters. |
| `_stack_features.py` | Stack the per-pixel input features into a single multi-band float32 GeoTIFF. |

## s2_labels (11) - annotations to label rasters + splits

| Script | What it does |
|---|---|
| `_build_label_grids.py` | Build 2x2 derivative grids over the most well-dense areas, for annotation. |
| `_build_orient_labels.py` | Build per-pixel road-orientation label rasters for the `orient` sweep variant. |
| `_build_pit_dataset.py` | Build labeled raster + spatial-block train/val/test split for the pit segmentation task. |
| `_build_plat_road_dataset.py` | Build labels and manifests for plat segmentation, road segmentation, and road classification. |
| `_build_plat_split.py` | Pad-aware spatial-block split for the STANDALONE plat/pad U-Net. |
| `_build_unified_split.py` | Unified spatial-block split for the MULTITASK U-Net (pit + road + plat heads). |
| `_merge_review_added_roads_613590_into_roads_shp.py` | Fold the corrected 613590 road review into the master annotation file. |
| `_prep_annotations.py` | Reproject, validate, and spatial-join annotation layers. |
| `_prep_road_1m.py` | Prep the 1 m road-training inputs from the 9t_1m derivative stack. |
| `_rebuild_labels_road_9t_1m.py` | Rebuild ONLY the 1 m road label raster for 9t from current annotations. |
| `_sanity_render.py` | Render a grid of sample pits with label overlay for visual QC. |

## s3_train (13) - labels + features to best.pt

| Script | What it does |
|---|---|
| `_drainage_unet_1m.py` | Drainage-focused 9t road/drainage U-Net (1 m, 3-class bg/road/drainage). |
| `_multitask_unet.py` | Multi-task U-Net for pit / road / plat joint segmentation at 0.5 m. |
| `_pad_maskrcnn.py` | Plat (pad) instance segmentation with Mask R-CNN on 9t. |
| `_pad_unet_cv5.py` | 5-fold cross-validation of the pad (plat) U-Net on 9t. |
| `_pad_yolo.py` | Plat (pad) instance segmentation with YOLOv8-seg on 9t. |
| `_pit_maskrcnn.py` | Pit instance segmentation with Mask R-CNN (torchvision, ResNet-50 FPN v2). |
| `_pit_unet_cv5.py` | 5-fold cross-validation of the pit U-Net on 9t. |
| `_pit_unet_v2.py` | Pit semantic segmentation v2: 3-class (bg / floor / wall) at 0.5 m. |
| `_pit_yolo.py` | Pit instance segmentation with YOLOv8-seg on 9t. |
| `_plat_unet.py` | Binary plat segmentation U-Net (plat / background) at 0.5 m. |
| `_road_sweep_202607.py` | Road U-Net top-5 optimization sweep (2026-07-20). |
| `_road_unet_1m_corrected.py` | Road U-Net fine-tuned on the human corrections for 613590 (active learning). |
| `_road_unet_1m_recall.py` | Recall-focused 9t-only road U-Net (1 m, 3-class bg/road/drainage). |

## s4_infer (12) - best.pt + new area to candidates

| Script | What it does |
|---|---|
| `_infer_roads_data_3x3.py` | Run the trained road U-Net over every data_3x3 block in a region. |
| `_pad_maskrcnn_infer.py` | Full-tile inference for the Mask R-CNN pad model on 9t. |
| `_pad_unet_infer_grid.py` | Apply the PA-trained pad/plat U-Net straight to a label_grids/<grid> tile. |
| `_pad_yolo_infer.py` | Full-tile inference for the YOLOv8-seg pad model on 9t. |
| `_pit_maskrcnn_infer.py` | Full-tile inference for the Mask R-CNN pit model on 9t. |
| `_pit_unet_v2_infer.py` | Full-tile inference + test-set eval for pit_unet_v2. |
| `_pit_yolo_infer.py` | Full-tile inference for the YOLOv8-seg pit model on 9t. |
| `_postfilter_tile_candidates.py` | Turn raw per-tile U-Net probability rasters into clean candidate polygons. |
| `_predict_on_tile.py` | Run trained pit / road / plat U-Nets on a tile suffix's derivative stack. |
| `_refine_roads_data_3x3.py` | Post-process the raw road U-Net rasters into clean, connected road centerlines. |
| `_road_infer.py` | Generic road-model inference: load any road best.pt and predict a tile. |
| `_yolo_infer_tile.py` | Generalized YOLOv8-seg inference (pit + pad models) on an arbitrary 0.5 m tile. |

## s5_eval (23) - score against held-out truth

| Script | What it does |
|---|---|
| `_build_undecided_pit_candidates_9t.py` | Export the pit detections that match no annotated pit -- the undecided set. |
| `_compare_corrected_613590.py` | Before/after visual for the 613590 road correction loop. |
| `_cv5_centroid_precision_pit_pad_9t.py` | Centroid-matched precision to pair with the CV5 containment/locate recall. |
| `_export_pit_floor_threshold_tifs.py` | Export thresholded views of the pit U-Net floor probability raster. |
| `_heldout_overlap_9t.py` | How many HELD-OUT hand-drawn annotations does the model's geometry overlap? |
| `_heldout_rim_containment_9t.py` | Held-out pits scored by RIM containment: did predicted floor land inside the rim? |
| `_map_cv5_unmatched_pit_thr0p50_9t.py` | Map the CV5 pit predictions at threshold 0.50 that match no annotated pit. |
| `_match_rules_pit_pad_9t.py` | Matching rules for pit/pad scoring: fix a defect, then test two relaxations. |
| `_pad_cv5_tau_scale.py` | Pad CV recall/precision as a function of IoU strictness, pooled over 5 folds. |
| `_pad_threshold_products_9t.py` | Per-threshold PAD products: what each probability cutoff claims, and what it misses. |
| `_pit_cv5_tau_scale.py` | Pit CV recall/precision as a function of IoU strictness, pooled over 5 folds. |
| `_pit_optimize.py` | Optimize pit (well-depression) post-processing against ground truth. |
| `_pit_threshold_products_9t.py` | Per-threshold pit products, built so the MISSED pits are actually findable. |
| `_plot_iou_strictness_scale_9t.py` | Precision / recall / F1 as a function of how strict the IoU match has to be. |
| `_reeval_instance_precision_9t.py` | Honest 9t instance metrics: matched extent, matched class, val-frozen thresholds. |
| `_road_methods_compare.py` | Bake-off of SEVERAL distinct road-extraction algorithms on the same prob. |
| `_road_optimize.py` | Optimize road-network post-processing against ground truth. |
| `_road_sweep_aggregate.py` | Aggregate the road sweep into a leaderboard (variants + baselines). |
| `_road_threshold_products_9t.py` | Per-threshold ROAD products: what each probability cutoff claims, and what it misses. |
| `_score_road_pred_vs_roads_shp_613590.py` | Score a road probability raster for 613590 against the roads in roads.shp. |
| `_style_heldout_gpkg.py` | Make the held-out GeoPackages self-styling in QGIS. |
| `_threshold_common.py` | Shared pieces for the per-threshold "what does this cutoff claim?" products. |
| `_uncounted_well_recovery_9t.py` | DEP POSITIONAL RELIABILITY CHECK -- NOT A MODEL SCORE. |

## s6_review (8) - review packages, corrections back to s2

| Script | What it does |
|---|---|
| `_build_drainage_review_package.py` | Build a QGIS review package for human-in-the-loop DRAINAGE correction on a block. |
| `_build_pit_review_package.py` | Build a QGIS review package for human-in-the-loop pit correction on a block. |
| `_build_road_corrections_613590.py` | Turn the human road review of 613590 into a corrected training block. |
| `_build_road_review_package.py` | Build a QGIS review package for human-in-the-loop road correction on a block. |
| `_calibrate_drainage_extraction_9t.py` | Calibrate the drainage vectorizer on 9t, where hand-drawn drainage exists. |
| `_overlay_drainage_review_613590.py` | QC overlay for the 613590 drainage review package. |
| `_pit_corrections_diff.py` | Diff a human-corrected pit review against the pristine original. |
| `_road_corrections_diff.py` | Diff a human-corrected road review against the pristine original. |

## s7_analysis (12) - morphology, change detection, science

| Script | What it does |
|---|---|
| `_bold_vs_faint_roads.py` | Supervised contrast of the user's bold_roads vs faint_roads exemplars (9t). |
| `_classify_9t_roads_bold_faint.py` | Split the 9t annotated roads into bold and faint layers. |
| `_export_well_age_qgis.py` | Export the well-age-vs-morphology results as a QGIS-ready GeoPackage. |
| `_icp_change_9t.py` | Preliminary 2006-2008 -> 2019 ICP change product over the 9t block. |
| `_icp_change_9t_rebuild.py` | Rebuild the 2006-2008 -> 2019 DoD over the 9t block with ONE ICP solve. |
| `_icp_change_classify_9t.py` | Destripe the 9t DoD, segment significant change, and separate erosional |
| `_pad_morphology_bins.py` | Unsupervised pad morphology bins — joint 9t (Venango) + mkf (McKean). |
| `_photo_source_locations.py` | Georeference the field-photo sources found in the 2026-07-20 web sweep. |
| `_road_morphology_bins.py` | Unsupervised morphology bins for the 9t hand-drawn roads. |
| `_score_bold_faint_exemplar_segments.py` | Score every segment of the two hand-drawn exemplar shapefiles. |
| `_well_age_morphology.py` | Well age vs pad/pit morphology — does surface geometry encode drilling era? |
| `_well_provenance_flags.py` | Tag DEP wells with reporting-provenance flags (bounty-era proxy where possible). |

## shared (3)

| Script | What it does |
|---|---|
| `_common.py` | Shared utilities for active WellSight scripts. |
| `_dl.py` | Shared deep-learning building blocks for pit / road / plat U-Net trainers. |
| `_instance_common.py` | Shared helpers for instance-segmentation experiments on the 9t tile. |
