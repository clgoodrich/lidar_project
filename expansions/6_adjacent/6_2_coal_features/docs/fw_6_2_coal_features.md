# Framework 6.2. Coal and mine features (separate study, shares 6.3 infrastructure)

**Tier A by instruction (user, 2026-11-05, stop deferring).** Written to full depth so it can be modified later. Nothing here has been run.
**Evidence level.** (a) drawn feature, per class. No level (b), (c) or (d) claim is made for any mine feature.
**Depends on.** 6.3 for the codebook, sampling and blind-labelling machinery. P1 for isolated trainers. P2 for audit blocks. 3.0 scorer.
**Blocks.** Nothing. It informs 6.3 (class K) and 5.1.
**Status of the study.** A separate study with its own area and its own labels. It reuses 6.3 tooling and does not share results with the well work.

## 1. Problem and objective
Mine portals, subsidence pits and spoil heaps are legacy hazards. In lidar they also look like well pits and pads. A pit model trained in oil country can fire on them, and a mine model can fire on wells.

**Question 1 (inventory audit).** What are the identity, position error and completeness of the assumed PA DEP mine-feature layers against lidar and imagery?
**Question 2 (mutual confusion).** How often do the existing well pit and pad models score mine features above the review cutoff, and how often does a mine-feature classifier fire on well pits and pads?
**Question 3 (extra classes).** Can mine portal, subsidence and spoil heap be learned as classes at useful recall at K = 40 per km², without losing well-feature recall?

**Hypotheses.** H1. Position error of inventory points is small enough for the tolerances in section 3. H2. The existing pit model flags at least some subsidence features at the 0.50 cutoff. H3. Adding mine classes as negatives for the well models reduces mine detections without a recall loss beyond Δ.

## 2. Scope
In. Inventory audit, class design, labelling, confusion matrix against existing pit and pad outputs, a mine-class model on the 6.3 trainer, retraining the well models with mine negatives.
Out. Any claim that a mine feature is a well or a well is a mine feature. Mine hazard ranking. Underground mine mapping. Any use in the Venango result (Venango has little coal, so it cannot supply the test).
**Area assumption.** The test area is a coal-rich Pennsylvania area that is not Venango (proposed, for example Greene, Washington or Fayette County, chosen from the DEP layer counts in S0). The choice is a user decision.

## 3. Definitions
- **Mine portal.** An entry to an underground mine, seen as a notch or bench cut into a hillslope, often with a flat apron and a drainage channel.
- **Subsidence.** A collapse depression above shallow workings. Often a sinkhole or a trough.
- **Spoil heap.** A mound or ridge of waste rock or coal refuse. Includes gob piles and valley fills as a sub-label.
- **Class set.** M (portal), S (subsidence), H (spoil heap), W (well pit or pad, per 6.3 class P), O (other, per the 6.3 codebook), U (uncertain). Mine classes map to 6.3 class K as a group.
- **Per-class matching tolerance.** The distance or IoU at which a candidate matches an inventory record or a drawn feature. Proposed starting values, fixed before scoring.

| Class | Truth geometry | Match rule | Starting tolerance |
|---|---|---|---|
| M portal | Point, buffered | Candidate centroid to record | 30 m |
| S subsidence | Polygon of the depression | IoU | 0.3 (same as pits) |
| H spoil heap | Polygon of the mound | IoU | 0.3, with a centroid fallback at 50 m for heaps over 1 ha |
| W well | Drawn floor polygon | IoU | 0.3 (as 3.0) |

The tolerances are re-chosen after S0 from the measured offsets. They are fixed in the preregistration before any scoring.
- **Eligible area.** Complete blocks in the test area, including blocks with no features.
- **Confusion matrix.** Rows are adjudicated truth class. Columns are the top-K candidate label of each model. Cells carry block-bootstrap intervals.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Frozen pit and pad models | `data/9t/models/pit/unet_cv5/`, `data/9t/models/pad/unet_cv5_iso/` | held |
| 9t well candidates (reference for well-side confusion) | `data/9t/results/pit/centroid_matching/pit_candidates_undecided_thr0p50_9t.gpkg` | held |
| Derivative builder at 0.5 m | `notebooks/wellsight_v2/s1_build/_build_derivatives.py` | held |
| Pit inference | `notebooks/wellsight_v2/s4_infer/_predict_on_tile.py` | held |
| Review package and diff tools | `s6_review/_build_pit_review_package.py`, `_pit_corrections_diff.py` | held |
| 6.3 codebook and sampler | `docs/iterations/confuser_codebook.md`, `s6_review/_confuser_sample_9t.py` | 6.3 deliverable |
| Coal-area lidar tiles | `data/_source/lidar/<coal_area>/` | assumed, see section 5 |
| PA DEP mine layers | `data/<coal_area>/source/dep_mine_features/` | assumed, proposed path |

## 5. Assumed data
Every item is assumed to exist. Each carries VERIFY. Nothing below is confirmed.

| Item | Assumption | VERIFY |
|---|---|---|
| Mine-feature layers | PA DEP publishes point or polygon layers for abandoned mine land problem areas, mine openings and subsidence-prone areas, downloadable as shapefile or from an ArcGIS service. | Open the DEP GIS data catalogue. List layer names, geometry type, field names, vintage and licence. Save the listing in `docs/iterations/coal_inventory_audit.md`. |
| Feature types in the layers | Portals, subsidence, spoil or refuse piles carry a type field that maps onto M, S and H. | Tabulate the type field. Record which codes map to which class and which do not map. |
| Position error | Records are digitised from maps or field GPS with unknown error. | S0 measures it. Do not assume a number. |
| Completeness | Records cover only inventoried hazards. Unlisted features exist. | S0 completeness check on a random block sample. |
| Lidar over the coal area | A PA lidar program with ground-classified LAZ covers the test counties at QL2 or better. | Query the same catalogue as `s1_build/_list_lidar_windows_inventory_us.py`. Measure ground points per m² per block. Record the void fraction. |
| Imagery | PA orthoimagery (PASDA) covers the area for identity checks. | Pull two chips per sampled record. Record the acquisition year. |
| CRS | Layers arrive in EPSG:4326 or a PA State Plane. | Read the layer CRS. Reproject to EPSG:6346 and assert. Check the lidar CRS from the header. |
| Licence | DEP layers are public. | Read the data licence. Record the citation in `literature/CITATIONS.md`. |

If a VERIFY fails, stop and report. Do not substitute a different inventory silently.

## 6. Prerequisites and decisions
User decisions. Test area. Margin Δ for well-recall loss and the useful mine-detection reduction. Reviewer pair (the 6.3 pair may serve). The 6.3 codebook pilot should finish first so class K is already split.

## 7. Procedure
**S0. Inventory audit (about 12 hours).**
- Script `notebooks/wellsight_v2/s6_review/_coal_inventory_audit.py` (proposed). Draw 50 records per class by simple random sampling within the test area (or all if fewer). For each, render a hillshade chip and an aerial chip with the record marked.
- Reviewers label identity (confirmed feature of that class, a different class, nothing visible, uncertain) and measure offset in metres to the nearest visible feature.
- Completeness. In 20 random complete blocks, a reviewer lists every mine feature visible, blind to the layer. Completeness is listed records matched over visible features.
- Outputs `data/<coal_area>/results/coal/coal_audit_records.csv`, `coal_audit_summary.json`, doc `docs/iterations/coal_inventory_audit.md`. Re-choose tolerances from the 90th percentile of offset by class.

**S1. Derivatives and candidates.** Run `_build_derivatives.py` at 0.5 m on the coal area. Run the frozen pit and pad models with the same proposal extraction as 3.0 (0.10 floor, 4 m² minimum, mean-probability score). Output under `data/<coal_area>/results/coal/candidates/`.

**S2. Labelling.** Extend the 6.3 sheets with the mine classes. Sample from non-audit blocks, stratified by model score band and by inventory proximity. Include inventory records and random candidates so unlisted features are found. Blind to score and to the layer. Two reviewers, adjudication by a third look, remaining disagreement stays U. Script `s6_review/_coal_sheets_coal.py` (proposed). Output `coal_labels_coal.csv`.

**S3. Confusion matrix on existing models.** Take the top-K candidates of the frozen pit and pad models in the coal blocks. Label each from the S2 labels (new candidates are labelled blind). Build the matrix of truth class by model decision. Outputs `coal_confusion_wells_vs_mine.csv`, figure `coal_confusion_wells_vs_mine.png`.

**S4. Mine-class model.** Copy the 6.3 isolated trainer. Classes M, S, H and background, with W and O as explicit negatives. Three seeds, five spatially blocked folds, fold-local normalisation, whole-window leakage guard. Output `data/<coal_area>/models/coal/unet_cv5/<arm>/seed<s>/fold<k>/` with `.gitignore` rules.

**S5. Reverse confusion.** Score the mine-class model on 9t well pits and pads (the 424 annotated pits). Count well features it labels as mine at K. Intervals by block.

**S6. Well model with mine negatives.** Retrain the 6.3 confuser arm with M, S and H as the negative class. Compare to a random-negative arm and a baseline, using the 6.3 pooled blind scoring. Test on audit blocks of the coal area and on 9t.

## 8. Statistical analysis plan
- Unit of resampling is the block. B = 2000, percentile 95% interval (fw_00_common section 4).
- **Primary (Q2).** Share of top-K well-model candidates in coal blocks that adjudicate to M, S or H, per km² at K = 40. One estimand. Everything else is exploratory.
- **Primary (Q3).** Mine detections per km² at K, mine-negative arm minus random-negative arm. Well-recall change on 9t, non-inferiority against Δ.
- Q1 is descriptive. Offset percentiles and completeness with Clopper-Pearson intervals.
- Per-class cells with fewer than 15 truth features are reported with exact intervals and marked exploratory.
- Seeds describe training variance. They are not landscapes.

## 9. Quality control and leakage
- Row counts asserted at every join. Expected and observed stated.
- CRS asserted for every layer and raster on read.
- No audit block in any training, calibration or mining list. Windows that touch held-out blocks are rejected.
- Labellers see no score, no layer attributes, no arm. Log it. A 10% random subset re-labelled.
- Inventory records are never used as training labels before S0 passes. Drawn and adjudicated labels only.
- Same config run twice gives identical outputs.
- Sanity render of two known features per new product.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| S0 readiness | Identity confirmed for at least the share set in the preregistration and 90th percentile offset below the tolerance | Use records as match targets |
| S0 failure | Identity or offset below that. Layer unusable for matching | Label from imagery and lidar only. Record the verdict per layer, not per feature |
| Q3 success | Mine-detection reduction lower bound above 0 and well-recall loss lower bound above minus Δ | Adopt mine negatives for the next well model |
| Q3 failure | Reduction upper bound below 0, or recall-loss upper bound below minus Δ | Keep the finding. One failed run does not retire the idea |
| Inconclusive | Otherwise | Report. Add seeds or blocks |
Margins come from the tolerable missed-well burden and the useful reduction in review load, both stated before the run. Never from fold spread.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s6_review\_coal_inventory_audit.py`, `_coal_sheets_coal.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_coal_confusion_coal.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s3_train\_coal_unet_cv5.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\<coal_area>\results\coal\` (audit, labels, confusion, figures)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\coal_inventory_audit.md`, `coal_feature_scope.md`, `coal_confusion_study.md`
- Colourblind-safe figures. Blue `#1F5FA8` wells, orange `#D97706` mine classes, grey `#8E959B` uncertain, plus marker shapes. Validate all pairs.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Inventory incomplete or mispositioned | S0 measures both. Label from imagery and lidar |
| Subsidence and pits are truly indistinguishable in lidar | Keep U. Report the confusion, do not force a class |
| Early well platforms labelled as spoil | Track P and U suppression as in 6.3 |
| Coal area terrain differs from 9t | Report as an area effect. Do not call it a class effect |
| Class imbalance | Balanced sampling. Per-class exact intervals |
| Valley fills are large and break the window size | Sub-label H. Use polygon IoU. Tile windows |

## 13. Resources
S0 about 12 hours. Labelling about 2 reviewer-hours per 20 candidates (6.3 pilot to confirm). Derivatives and inference hours per area, measured on one block first. Training 3 seeds by 5 folds on the GTX 1070 Ti, epoch time measured first. Disk several GB on F:.

## 14. Handoff and open questions
- Test area. Margin Δ. Reviewer names. DEP layer verification result.
- Stop and report if any VERIFY fails or a leakage check fails.

## 15. Documentation updates
`coal_inventory_audit.md`, `coal_feature_scope.md`, `coal_confusion_study.md`, `analysis_log.md`, `BACKLOG.md`, `LEADERBOARD.md` for model results, `literature/CITATIONS.md` for the DEP layers, master plan, 6.3 codebook (class K split).
