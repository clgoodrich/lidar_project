# WellSight Literature & Citations

Master list of every paper/method reference that a WellSight design decision is
based on. **Rule (see `CLAUDE.md`): any time we act on the literature, add a row
here** — full citation, what it is, what we used it for, the file(s) it drove,
and a local PDF copy in `literature/papers/` when obtainable.

Local copies live in `C:\Users\colto\Documents\GitHub\lidar_project\literature\papers\`.
"cite-only" = paper is paywalled/bot-walled and could not be downloaded; the URL
is the source of record.

## Quick index

| Key | Year | Topic | Used for (WellSight) | Generated file(s) | Local PDF |
|---|---|---|---|---|---|
| Yokoyama et al. | 2002 | Topographic openness | `openness_pos/neg` channels | `notebooks/wellsight_v2/s1_build/_build_derivatives.py` | cite-only |
| Chiba et al. | 2008 | Red Relief Image Map (RRIM) | `diff_openness` channel + RRIM viz products | `notebooks/wellsight_v2/s1_build/_make_rrim.py`; `diff_openness_*` in `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` | ✓ `chiba_2008_red_relief_image_map.pdf` |
| Auld-Thomas (blog) | 2022 | "Simple Red Relief" (LRM-base RRIM) | RRIM variant (LRM as base layer) | `notebooks/wellsight_v2/s1_build/_make_rrim.py` | ✓ `auldthomas_2022_simple_red_relief.pdf` |
| Hesse | 2010 | LiDAR Local Relief Model (LRM) | `lrm_{3,5,11,25}` channels | `notebooks/wellsight_v2/s1_build/_build_derivatives.py` | cite-only |
| Sofia, Marinello & Tarolli | 2014 | SLLAC (slope local autocorrelation length) | `sllac_len`, `sllac_aniso` channels | `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` | cite-only |
| Frangi et al. | 1998 | Multiscale vesselness (Hessian) | `frangi_lrm`, `frangi_slresid` channels | `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` | cite-only |
| Sato et al. | 1998 | Multi-scale line filter (tubeness) | `ridge_sato` channel | `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` | cite-only |
| Steger | 1998 | Unbiased curvilinear-structure detector | `ridge_orient` (Steger-family ridge/orientation) | `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` | ✓ `steger_1998_curvilinear_detector.pdf` |
| Ferraz, Mallet & Chehata | 2016 | Forest-road detection from lidar (elongated planar model + graph gap-linking) | Motivates `slope_residual`, `rough_aniso`; blueprint for the planned gap-linking pass | `_build_extra_channels.py` + future road linker | cite-only |
| Batra et al. | 2019 | Orientation learning for road connectivity | Orientation field for gap-linking | `ridge_orient` in `_build_extra_channels.py` + future linker | ✓ `batra_2019_road_connectivity_cvpr.pdf` |
| Shit et al. | 2021 | clDice topology-preserving loss | `ClDiceFocal` road-segmentation loss | `notebooks/wellsight_v2/s3_train/_road_sweep_202607.py`; `cldice`/`cldice_mkf` `road_prob` rasters | ✓ `cldice_shit_2021.pdf` |
| Savitzky & Golay | 1964 | Least-squares polynomial smoothing/differentiation | 2D SavGol quadratic residual (detrends slope+curvature) | `savgol_resid_*` in `_build_extra_channels.py` | ✓ `savitzky_golay_1964.pdf` |
| Wood | 1996 | Multiscale quadratic-surface DEM geomorphometry | Basis for local quadratic land-surface fitting (SavGol residual, curvature) | `savgol_resid_*`, `profile_curv` in `_build_extra_channels.py` | cite-only |
| Soille | 2004 | Mathematical morphology (top-hat transform) | White/black top-hat cut/fill bench channels | `tophat_white/black` in `_build_extra_channels.py` | cite-only |
| Guo et al. | 2017 | Temperature scaling / calibration | *Candidate* — calibrate `pit_prob_floor` | `docs/iterations/pit_refinement_options.md` | ✓ `guo_2017_calibration_temperature_scaling.pdf` |
| Mukhoti et al. | 2020 | Focal loss is under-confident | *Candidate* — diagnosis of low pit probabilities | `docs/iterations/pit_refinement_options.md` | ✓ `mukhoti_2020_calibrating_focal_loss.pdf` |
| Wang et al. | 2019 | Test-time augmentation | *Candidate* — D4 TTA at pit inference | `docs/iterations/pit_refinement_options.md` | ✓ `wang_2019_test_time_augmentation.pdf` |
| Salehi et al. | 2017 | Tversky loss | *Candidate* — recall-weighted region term | `docs/iterations/pit_refinement_options.md` | ✓ `salehi_2017_tversky_loss.pdf` |
| Abraham & Khan | 2019 | Focal Tversky loss | *Candidate* — small/hard pit floors | `docs/iterations/pit_refinement_options.md` | ✓ `abraham_2019_focal_tversky_loss.pdf` |
| Kervadec et al. | 2019 | Boundary loss | *Candidate* — extreme foreground imbalance | `docs/iterations/pit_refinement_options.md` | ✓ `kervadec_2019_boundary_loss.pdf` |
| Hu et al. | 2019 | Topology loss (Betti numbers) | *Candidate* — Betti-0 anti-fragmentation, the pit analogue of clDice | `docs/iterations/pit_refinement_options.md` | ✓ `hu_2019_topology_preserving_segmentation.pdf` |
| Stucki et al. | 2024 | Efficient Betti matching | *Candidate* — makes the Betti-0 loss tractable | `docs/iterations/pit_refinement_options.md` | ✓ `stucki_2024_efficient_betti_matching.pdf` |
| Fiorucci et al. | 2022 | IoU is the wrong measure for small discrete objects; centroid-based measures | **Adopted** — replaced the pit/pad IoU sweep with centroid matching in the AGU abstract | `notebooks/wellsight_v2/s5_eval/_cv5_centroid_precision_pit_pad_9t.py`; `_match_rules_pit_pad_9t.py`; `docs/agu_abstract_2026.md` | cite-only |
| Lidberg et al. | 2024 | Hunting pits from national ALS with U-Net; centroid scoring | **Adopted** — the closest published analogue; its recall/precision/F1 protocol is now ours, and its Table 1 is our comparison band | `docs/iterations/centroid_matching_pit_pad_9t.md` | ✓ `lidberg_2024_hunting_pits_als_deep_learning.pdf` |
| Suh et al. | 2021 | U-Net on lidar for relict charcoal hearths | *Candidate* — closest published analogue; motivates VAT/SVF channels | `docs/iterations/pit_refinement_options.md` | cite-only |
| Zakšek et al. | 2011 | Sky-View Factor | *Candidate* — new channel, pending redundancy check vs `openness_pos` | `docs/iterations/pit_refinement_options.md` | cite-only |
| Guyot et al. | 2018 | Multi-visualization CNN for buried structures | *Candidate* — supports the channel-stack approach | `docs/iterations/pit_refinement_options.md` | cite-only |
| Verschoof-van der Vaart & Lambers | 2019 | WODAN, R-CNN on lidar | Benchmark context | `docs/iterations/benchmark_context_what_counts_as_good.md` | cite-only |
| Verschoof-van der Vaart & Lambers | 2022 | Evaluation measures; curated-vs-random test gap | **The cherry-picking argument** — curated test regions inflate 20–50 pts | `docs/iterations/benchmark_context_what_counts_as_good.md` | cite-only |
| Gallwey et al. | 2019 | Historic mining pits, transfer learning | Benchmark comparand for the pit U-Net (F1 ~0.87) | `docs/iterations/benchmark_context_what_counts_as_good.md` | cite-only |
| Archaeoscape | 2024 | ALS archaeology benchmark dataset | Cited as existing; **no numbers quoted** (PDF would not extract) | `docs/iterations/benchmark_context_what_counts_as_good.md` | ✓ `archaeoscape_2024_als_archaeology_benchmark.pdf` |
| Wiedemann et al. | 1998 | Empirical evaluation of road extraction: completeness / correctness / quality on a buffer match | **Adopted** — the scoring triple for the 613590 out-of-domain road test | `notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py` | cite-only |

---

## Detailed entries

### Yokoyama, Shirasawa & Pike 2002 — Topographic openness
- **Citation:** Yokoyama, R., Shirasawa, M., Pike, R.J. (2002). "Visualizing topography by openness: A new application of image processing to digital elevation models." *Photogrammetric Engineering & Remote Sensing* 68(3): 257–265.
- **About:** Positive/negative openness — angular measure of how enclosed a point is, looking out to a distance L over 8 azimuths. Convex forms → high positive openness; concave (channels, cuts) → high negative openness. Illumination-independent.
- **Used for:** The `openness_pos` / `openness_neg` terrain channels (8-direction Yokoyama, L = 25 cells) — 2 of the 7 road-model input channels.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_derivatives.py` (`openness()` function).
- **Source:** https://scispace.com/papers/visualizing-topography-by-openness-a-new-application-of-1e2fefq450 — cite-only (ASPRS paywall).

### Chiba, Kaneta & Suzuki 2008 — Red Relief Image Map (RRIM)
- **Citation:** Chiba, T., Kaneta, S., Suzuki, Y. (2008). "Red Relief Image Map: New Visualization Method for Three-Dimensional Data." *Int. Archives of Photogrammetry, Remote Sensing and Spatial Information Sciences* 37(B2): 1071–1076.
- **About:** Composite terrain visualization = red-chroma slope × brightness from differential openness (positive − negative). Steep = vivid red, ridges bright, channels/cuts dark; illumination-independent.
- **Used for:** The `diff_openness` channel (openness_pos − openness_neg, the RRIM brightness base) and the RRIM viewing products.
- **Generated:** RRIM builder `notebooks/wellsight_v2/s1_build/_make_rrim.py` (`rrim_openness_<area>_<res>.tif` under `data/<area>/derived/<res>/`); `diff_openness_*.tif` in `notebooks/wellsight_v2/s1_build/_build_extra_channels.py`.
- **Local PDF:** `literature/papers/chiba_2008_red_relief_image_map.pdf`.

### Auld-Thomas 2022 — "A Recipe for Simple Red Relief" (methods note)
- **Citation:** Ancient Maya Settlement project (Auld-Thomas et al.), "A Recipe for Simple Red Relief," 2022-02-12 (technical blog / methods note, not peer-reviewed).
- **About:** A simplified RRIM that swaps Chiba's differential-openness base for a Local Relief Model base — cheaper to compute, similar linear-feature legibility.
- **Used for:** The LRM-base RRIM variant.
- **Generated:** `notebooks/wellsight_v2/s1_build/_make_rrim.py --simple` (`rrim_simple_<area>_<res>.tif` under `data/<area>/derived/<res>/`).
- **Source:** https://ancientmayasettlement.com/2022/02/12/a-recipe-for-simple-red-relief/
- **Local PDF:** `literature/papers/auldthomas_2022_simple_red_relief.pdf`.

### Hesse 2010 — LiDAR Local Relief Model (LRM)
- **Citation:** Hesse, R. (2010). "LiDAR-derived Local Relief Models – a new tool for archaeological prospection." *Archaeological Prospection* 17(2): 67–72. doi:10.1002/arp.374
- **About:** LRM = DEM minus a smoothed (low-pass) DEM, isolating small shallow features (sunken roads, earthworks, terraces) independent of illumination angle.
- **Used for:** The `lrm_{3,5,11,25}` multi-scale channels (road-model inputs `lrm_5`, `lrm_25`).
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_derivatives.py`.
- **Source:** https://onlinelibrary.wiley.com/doi/abs/10.1002/arp.374 — cite-only (Wiley paywall).

### Sofia, Marinello & Tarolli 2014 — SLLAC
- **Citation:** Sofia, G., Marinello, F., Tarolli, P. (2014). "A new landscape metric for the identification of terraced sites: The Slope Local Length of Auto-Correlation (SLLAC)." *ISPRS Journal of Photogrammetry and Remote Sensing* 96: 123–133.
- **About:** Anthropogenic earthworks (terraces, roads) leave an *organized* topographic signature. SLLAC measures the length over which the slope field stays auto-correlated in a direction; natural terrain is noisy (short length), engineered surfaces are persistent (long, directional).
- **Used for:** The `sllac_len` / `sllac_aniso` channels. **Note:** our implementation is a documented 4-direction *approximation* of the method, not a faithful reproduction of the paper's normalized-cross-correlation formulation.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_sllac`).
- **Source:** https://www.sciencedirect.com/science/article/abs/pii/S0924271614001786 — cite-only (Elsevier paywall).

### Frangi et al. 1998 — Multiscale vesselness
- **Citation:** Frangi, A.F., Niessen, W.J., Vincken, K.L., Viergever, M.A. (1998). "Multiscale vessel enhancement filtering." *MICCAI 1998*, LNCS 1496: 130–137.
- **About:** Hessian eigenvalue filter that responds to elongated (tubular) structures across scales; returns a vesselness magnitude per pixel.
- **Used for:** `frangi_lrm`, `frangi_slresid` — enhancing linear road/trail treads as dark ridges. Via `skimage.filters.frangi`.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_frangi`).
- **Source:** https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/ — cite-only.

### Sato et al. 1998 — Multi-scale line filter (tubeness)
- **Citation:** Sato, Y., et al. (1998). "Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images." *Medical Image Analysis* 2(2): 143–168.
- **About:** Hessian-based line-enhancement filter (tubeness); companion to Frangi, different eigenvalue combination.
- **Used for:** `ridge_sato` channel. Via `skimage.filters.sato`.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_ridge`).
- **Source:** Medical Image Analysis — cite-only (Elsevier paywall).

### Steger 1998 — Unbiased detector of curvilinear structures
- **Citation:** Steger, C. (1998). "An unbiased detector of curvilinear structures." *IEEE TPAMI* 20(2): 113–125. doi:10.1109/34.659930
- **About:** Scale-space line model that extracts sub-pixel line position, width, and **orientation** without the bias Gaussian smoothing introduces on asymmetric profiles.
- **Used for:** `ridge_orient` — the per-pixel along-ridge orientation field (Steger-family; we compute the Hessian orientation directly). This orientation field is what enables the planned connectivity/gap-linking step.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_ridge`).
- **Local PDF:** `literature/papers/steger_1998_curvilinear_detector.pdf`.

### Ferraz, Mallet & Chehata 2016 — Forest road detection from lidar
- **Citation:** Ferraz, A., Mallet, C., Chehata, N. (2016). "Large-scale road detection in forested mountainous areas using airborne topographic lidar data." *ISPRS Journal of Photogrammetry and Remote Sensing* 112: 23–36.
- **About:** Models forest roads as *planar elongated features with relief variation in the orthogonal direction*; detects candidates then uses graph/least-cost linking + a road-geometry model to prune false positives. Closest published analog to our problem (under-canopy forest roads at scale).
- **Used for:** Motivates the `slope_residual` (low-slope tread) and `rough_aniso` (smooth-along/rough-across) channels; blueprint for the planned orientation-guided gap-linking pass (the principled version of the least-cost-path reconnect we previously reverted).
- **Generated:** informs `_build_extra_channels.py` + a future road-linking script (not yet built).
- **Source:** https://www.sciencedirect.com/science/article/abs/pii/S0924271615002609 ; open landing (bot-walled): https://hal.science/hal-02375998 — cite-only.

### Batra et al. 2019 — Orientation learning for road connectivity
- **Citation:** Batra, A., Singh, S., Pang, G., Basu, S., Jawahar, C.V., Paluri, M. (2019). "Improved Road Connectivity by Joint Learning of Orientation and Segmentation." *CVPR 2019*: 10385–10393.
- **About:** Jointly predicts road segmentation **and** per-pixel orientation; the orientation head yields topologically connected, less-fragmented road masks.
- **Used for:** Justifies producing an orientation field (`ridge_orient`) to drive gap-linking; candidate future direction (joint orientation head on the road U-Net).
- **Generated:** `ridge_orient` in `_build_extra_channels.py` + future linker.
- **Local PDF:** `literature/papers/batra_2019_road_connectivity_cvpr.pdf`.

### Shit et al. 2021 — clDice topology-preserving loss
- **Citation:** Shit, S., et al. (2021). "clDice – a Novel Topology-Preserving Loss Function for Tubular Structure Segmentation." *CVPR 2021*. arXiv:2003.07311.
- **About:** Similarity measure on the intersection of masks with their morphological skeleta; the differentiable soft-clDice preserves connectivity/topology, benchmarked on vessels, neurons, and **roads**.
- **Used for:** The `ClDiceFocal` loss (focal + w·(1−soft_clDice)) used to train the road U-Net — the current best road model.
- **Generated:** `notebooks/wellsight_v2/s3_train/_road_sweep_202607.py`; `cldice` and `cldice_mkf` `road_prob` rasters under `data/derivatives/tiles/9t/road_sweep_202607/`.
- **Local PDF:** `literature/papers/cldice_shit_2021.pdf`.

### Savitzky & Golay 1964 — Least-squares polynomial smoothing
- **Citation:** Savitzky, A., Golay, M.J.E. (1964). "Smoothing and Differentiation of Data by Simplified Least Squares Procedures." *Analytical Chemistry* 36(8): 1627–1639.
- **About:** Local polynomial (Savitzky-Golay) regression — smooths a signal by fitting a low-order polynomial in a moving window, preserving peak shape and width that plain averaging flattens.
- **Used for:** The 2D SavGol **quadratic residual** channels. Fitting `a+bx+cy+dx²+ey²+fxy` and subtracting removes the local slope *and* curvature, so only departures from a smooth hillslope (anthropogenic benches) survive. Fixes the curvature contamination of the LRM unsharp mask (`DEM − focal_mean` leaks ~`(σ²/2)·∇²z`).
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_savgol`, `_sg2d_kernel`).
- **Provenance note:** the bench-detection *application* recipe (quadratic residual + top-hat on detrended elevation, slope-normal frame) was proposed by the user's Claude agent; this paper is the underlying smoothing method.
- **Local PDF:** `literature/papers/savitzky_golay_1964.pdf`.

### Wood 1996 — Multiscale quadratic-surface DEM geomorphometry
- **Citation:** Wood, J. (1996). "The Geomorphological Characterisation of Digital Elevation Models." Ph.D. Thesis, University of Leicester, 466 pp.
- **About:** Parameterises DEMs by fitting quadratic surfaces over a *range of window sizes* and taking first/second derivatives, characterising landform at any scale rather than a fixed 3×3.
- **Used for:** Methodological basis for the local quadratic land-surface fit behind the SavGol residual and multiscale approach; also underpins profile curvature.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_savgol`, multiscale stack).
- **Source:** https://lra.le.ac.uk/handle/2381/34503 ; https://figshare.le.ac.uk/articles/thesis/10152368 — cite-only (466-pp thesis).

### Soille 2004 — Mathematical morphology (top-hat)
- **Citation:** Soille, P. (2004). *Morphological Image Analysis: Principles and Applications*, 2nd ed. Springer.
- **About:** Standard reference for grayscale morphology. The white top-hat (`f − opening(f)`) isolates bright structures smaller than the structuring element; the black/bottom top-hat (`closing(f) − f`) isolates dark ones.
- **Used for:** The `tophat_white` (fill lip) and `tophat_black` (cut) bench channels, run on the SavGol residual with a disk SE just wider than the tread. The offset white/black pair is a selective bench signature.
- **Generated:** `notebooks/wellsight_v2/s1_build/_build_extra_channels.py` (`ch_tophat`).
- **Source:** Springer (book) — cite-only.

---

## Pit U-Net refinement survey (2026-07-27)

Surveyed in response to two review observations on `pit_prob_floor.tif` — pit
probabilities lower than expected, and fragmented/partial floors. **These are
candidates, not yet implemented.** The survey, the ranking, and the reasoning
tying each paper to a specific symptom live in
`docs/iterations/pit_refinement_options.md`, which is the file these citations
generated. Move each entry's "Generated" field to the real code path when the
change is actually made.

### Guo, Pleiss, Sun & Weinberger 2017 — Temperature scaling
- **Citation:** Guo, C., Pleiss, G., Sun, Y., Weinberger, K.Q. (2017). "On Calibration of Modern Neural Networks." *Proc. ICML 2017*, PMLR 70: 1321–1330. arXiv:1706.04599.
- **About:** Modern deep nets are badly miscalibrated. Fitting a single scalar temperature `T` on a validation set and dividing the logits by it before softmax fixes most of it. Monotonic, so accuracy and ranking are untouched.
- **Candidate use:** Put `pit_prob_floor` on a calibrated scale so a stated threshold means what a reader assumes, and so thresholds transfer between tiles. Explicitly cannot change recall at a re-tuned threshold.
- **Generated:** `docs/iterations/pit_refinement_options.md` (Fix A).
- **Local PDF:** `literature/papers/guo_2017_calibration_temperature_scaling.pdf`.

### Mukhoti, Kulharia, Sanyal, Golodetz, Torr & Dokania 2020 — Focal loss and calibration
- **Citation:** Mukhoti, J., Kulharia, V., Sanyal, A., Golodetz, S., Torr, P.H.S., Dokania, P.K. (2020). "Calibrating Deep Neural Networks using Focal Loss." *Advances in Neural Information Processing Systems 33 (NeurIPS 2020)*. arXiv:2002.09437.
- **About:** Focal-loss models calibrate better than cross-entropy models, and the mechanism is that focal loss is empirically **under-confident**, offsetting overfitting-induced over-confidence.
- **Candidate use:** Explains symptom 1 directly. Our pit U-Net trains on `FocalCE` with `gamma=2.0` and no region term, so compressed peak probabilities are the documented behaviour of the chosen loss, not evidence of weak pit signal.
- **Generated:** `docs/iterations/pit_refinement_options.md` (symptom 1 diagnosis).
- **Local PDF:** `literature/papers/mukhoti_2020_calibrating_focal_loss.pdf`.

### Wang, Li, Aertsen, Deprest, Ourselin & Vercauteren 2019 — Test-time augmentation
- **Citation:** Wang, G., Li, W., Aertsen, M., Deprest, J., Ourselin, S., Vercauteren, T. (2019). "Aleatoric uncertainty estimation with test-time augmentation for medical image segmentation with convolutional neural networks." *Neurocomputing* 338: 34–45. arXiv:1807.07356.
- **About:** Predict over transformed copies of the input, invert each transform, aggregate. Improves segmentation accuracy and yields an aleatoric uncertainty estimate for free.
- **Candidate use:** D4 TTA at inference. Our inputs are nadir terrain rasters with no canonical orientation, so the equivariance assumption holds exactly. Should lift confidence on true pits while suppressing direction-dependent artifacts such as swath seams. Targets both symptoms.
- **Generated:** `docs/iterations/pit_refinement_options.md` (Fix B).
- **Local PDF:** `literature/papers/wang_2019_test_time_augmentation.pdf`.

### Salehi, Erdogmus & Gholipour 2017 — Tversky loss
- **Citation:** Salehi, S.S.M., Erdogmus, D., Gholipour, A. (2017). "Tversky loss function for image segmentation using 3D fully convolutional deep networks." *MLMI 2017*, LNCS 10541: 379–387. arXiv:1706.05721.
- **About:** Generalises Dice with tunable `alpha`/`beta` on false positives and false negatives, letting precision and recall be traded explicitly in the loss.
- **Candidate use:** Add a region term to the pit loss with `beta > alpha` to buy recall, and restore the incentive to saturate confident pixels that pure focal removes.
- **Generated:** `docs/iterations/pit_refinement_options.md` (Fix C).
- **Local PDF:** `literature/papers/salehi_2017_tversky_loss.pdf`.

### Abraham & Khan 2019 — Focal Tversky loss
- **Citation:** Abraham, N., Khan, N.M. (2019). "A Novel Focal Tversky Loss Function with Improved Attention U-Net for Lesion Segmentation." *IEEE ISBI 2019*: 683–687. arXiv:1810.07842.
- **About:** Focal modulation on top of Tversky, concentrating gradient on hard, small regions. Reported strong on small-lesion delineation.
- **Candidate use:** Same slot as Tversky. Pit floors are small and hard, which is the regime this targets.
- **Generated:** `docs/iterations/pit_refinement_options.md` (Fix C).
- **Local PDF:** `literature/papers/abraham_2019_focal_tversky_loss.pdf`.

### Kervadec, Bouchtiba, Desrosiers, Granger, Dolz & Ben Ayed 2019 — Boundary loss
- **Citation:** Kervadec, H., Bouchtiba, J., Desrosiers, C., Granger, E., Dolz, J., Ben Ayed, I. (2019). "Boundary loss for highly unbalanced segmentation." *Proc. MIDL 2019*, PMLR 102: 285–296. arXiv:1812.07032.
- **About:** A distance metric on contours rather than regions. Integrating over the interface avoids the ill-conditioning of region integrals when foreground is a tiny fraction of the image.
- **Candidate use:** Pit floors are well under 1% of the 9t tile (4.33 ha at thr 0.20, 0.214%), which is the imbalance regime this was built for. Complements a region term rather than replacing it.
- **Generated:** `docs/iterations/pit_refinement_options.md` (cause 2c).
- **Local PDF:** `literature/papers/kervadec_2019_boundary_loss.pdf`.

### Hu, Fuxin, Samaras & Chen 2019 — Topology-preserving segmentation
- **Citation:** Hu, X., Fuxin, L., Samaras, D., Chen, C. (2019). "Topology-Preserving Deep Image Segmentation." *Advances in Neural Information Processing Systems 32 (NeurIPS 2019)*.
- **About:** A differentiable loss built on persistent homology that forces the prediction to match the ground truth's Betti numbers. Betti-0 counts connected components, Betti-1 counts holes.
- **Candidate use:** The pit-shaped counterpart to what clDice did for roads. clDice targets tubular skeleton connectivity and is wrong for blobs. A Betti-0 penalty encodes "one annotated pit is one component", which is exactly the fragmentation symptom.
- **Generated:** `docs/iterations/pit_refinement_options.md` (cause 2b).
- **Local PDF:** `literature/papers/hu_2019_topology_preserving_segmentation.pdf`.

### Stucki, Paetzold, Shit, Menze & Bauer 2024 — Betti matching
- **Citation:** Stucki, N., Paetzold, J.C., Shit, S., Menze, B., Bauer, U. (2024). "Efficient Betti Matching Enables Topology-Aware 3D Segmentation via Persistent Homology." arXiv:2407.04683.
- **About:** Makes persistent-homology topology losses tractable at practical image sizes, which was the main barrier to using Hu et al. 2019 in production.
- **Candidate use:** The implementation route if the Betti-0 loss is pursued.
- **Generated:** `docs/iterations/pit_refinement_options.md` (cause 2b).
- **Local PDF:** `literature/papers/stucki_2024_efficient_betti_matching.pdf`.

### Suh, Anderson, Ouimet, Johnson & Witharana 2021 — Relict charcoal hearths from lidar with U-Net
- **Citation:** Suh, J.W., Anderson, E., Ouimet, W., Johnson, K.M., Witharana, C. (2021). "Mapping Relict Charcoal Hearths in New England Using Deep Convolutional Neural Networks and LiDAR Data." *Remote Sensing* 13(22): 4630. doi:10.3390/rs13224630.
- **About:** U-Net over airborne-lidar derivatives to find relict charcoal hearths, which are small circular platform features under closed forest canopy in the northeastern US. Best F1 95.5% in localised test regions, 86% at town scale. Slope, hillshade and VAT were the best-performing input rasters. Accuracy was higher in deciduous forest on slopes above 15 degrees.
- **Candidate use:** Closest published analogue to WellSight — same region type, same canopy problem, same small-circular-feature target, same architecture. Motivates testing VAT and sky-view factor as channels.
- **Caveat:** must be redundancy-checked against existing channels before use, the same test that caused RRIM to be rejected as a model input.
- **Generated:** `docs/iterations/pit_refinement_options.md` ("Channels we do not have").
- **Source:** https://doi.org/10.3390/rs13224630 — cite-only (MDPI blocks automated download).

### Fiorucci, Verschoof-van der Vaart, Soleni, Le Saux & Traviglia 2022 — new evaluation measures
- **Citation:** Fiorucci, M., Verschoof-van der Vaart, W.B., Soleni, P., Le Saux, B., Traviglia, A. (2022). "Deep Learning for Archaeological Object Detection on LiDAR: New Evaluation Measures and Insights." *Remote Sensing* 14(7): 1694. doi:10.3390/rs14071694.
- **About:** Argues Intersection-over-Union is inadequate for small discrete archaeological objects, because a few pixels of boundary disagreement on a feature metres across dominates the overlap ratio and scores a correctly located object as a miss. Proposes centroid-based and pixel-based measures instead.
- **WellSight used it for:** Replacing the pit/pad IoU-strictness sweep with centroid matching. Our existing `containment` / `locate` columns were already this criterion under another name; this paper is why they became the reported metric rather than a side column. IoU is retained for roads, where outline overlap is the right measure.
- **Generated:** `docs/iterations/centroid_matching_pit_pad_9t.md`; `notebooks/wellsight_v2/s5_eval/_cv5_centroid_precision_pit_pad_9t.py`; `notebooks/wellsight_v2/s5_eval/_match_rules_pit_pad_9t.py`; the results paragraph of `docs/agu_abstract_2026.md` (v14 onward).
- **Source:** https://doi.org/10.3390/rs14071694 — cite-only (MDPI blocks automated download).

### Lidberg, Westphal, Brax, Sandström & Östlund 2024 — hunting pits from ALS
- **Citation:** Lidberg, W., Westphal, F., Brax, C., Sandström, C., Östlund, L. (2024). "Detection of Hunting Pits using Airborne Laser Scanning and Deep Learning." *Journal of Field Archaeology* 49(6): 395–405. doi:10.1080/00934690.2024.2364428.
- **About:** U-Net over topographical indices from Swedish national ALS (1–2 pts/m²) to map 2,519 hunting pits across 1,275 km². Best model F1 0.76, recall 70%, precision 85%, on profile curvature from a 0.5 m DEM. Evaluation quotes Fiorucci et al. 2022 directly: *"A centroid-based approach described by Fiorucci and colleagues (2022) was used to calculate the number of true positive, false positive, and false negative predicted hunting pits."* No IoU is used anywhere.
- **WellSight used it for:** The closest published analogue to our pit task — small circular depressions, forest canopy, ALS, U-Net, 0.5 m vs 1 m DEM. Its protocol (recall / precision / F1 from centroid matching) is now ours, and its Table 1 is the band we compare into. Our centroid F1 of 0.75–0.81 sits alongside their 0.76 at roughly 3x their point density.
- **Generated:** `docs/iterations/centroid_matching_pit_pad_9t.md`; comparison band in `docs/iterations/benchmark_context_what_counts_as_good.md`.
- **Local PDF:** `literature/papers/lidberg_2024_hunting_pits_als_deep_learning.pdf` (open access via SLU Epsilon).

### Zakšek, Oštir & Kokalj 2011 — Sky-View Factor
- **Citation:** Zakšek, K., Oštir, K., Kokalj, Ž. (2011). "Sky-View Factor as a Relief Visualization Technique." *Remote Sensing* 3(2): 398–415. doi:10.3390/rs3020398.
- **About:** Portion of visible sky above a point. Illumination-independent, and unlike hillshade it does not suppress features aligned with the light azimuth. A VAT component.
- **Candidate use:** Candidate new channel. Related to our `openness_pos` but not identical, so it needs an explicit correlation check against it before a training run is spent.
- **Generated:** `docs/iterations/pit_refinement_options.md` ("Channels we do not have").
- **Source:** https://doi.org/10.3390/rs3020398 — cite-only (MDPI blocks automated download).

### Verschoof-van der Vaart & Lambers 2019 — WODAN, R-CNN on lidar
- **Citation:** Verschoof-van der Vaart, W.B., Lambers, K. (2019). "Learning to Look at LiDAR: The Use of R-CNN in the Automated Detection of Archaeological Objects in LiDAR Data from the Netherlands." *Journal of Computer Applications in Archaeology* 2(1): 31–40. doi:10.5334/jcaa.32.
- **About:** Faster R-CNN workflow (WODAN) for barrows, Celtic fields and charcoal kilns in Dutch lidar.
- **Used for:** Benchmark context in `docs/iterations/benchmark_context_what_counts_as_good.md`.
- **Source:** https://doi.org/10.5334/jcaa.32 — cite-only (download endpoint returned non-PDF).

### Verschoof-van der Vaart & Lambers 2022 — Evaluation measures, and the curated-vs-random test gap
- **Citation:** Verschoof-van der Vaart, W.B., Lambers, K. (2022). "Deep Learning for Archaeological Object Detection on LiDAR: New Evaluation Measures and Insights." *Remote Sensing* 14(7): 1694. doi:10.3390/rs14071694.
- **About:** Argues there is no standard evaluation protocol for buried-feature detection and proposes centroid-based and pixel-based measures encoding how an archaeologist actually judges a detection. Reports WODAN2.0 at ~70% on a small non-random test set and **~50% barrows, ~46% Celtic fields, ~18% charcoal kilns on a large random test set.**
- **Used for:** The central cherry-picking argument. This is the strongest published evidence that a curated test region inflates these scores by 20–50 points, and it is why WellSight's held-out-blocks-inside-the-training-tile numbers are treated as an upper bound.
- **Generated:** `docs/iterations/benchmark_context_what_counts_as_good.md`.
- **Source:** https://doi.org/10.3390/rs14071694 — cite-only (MDPI blocks automated download).

### Archaeoscape 2024 — ALS archaeology benchmark dataset
- **Citation:** Archaeoscape: Bringing Aerial Laser Scanning Archaeology to the Deep Learning Era (2024). arXiv:2412.05203.
- **About:** Large open ALS archaeology dataset with benchmarked segmentation baselines, framed around detecting subtle human-made structures under dense canopy.
- **Used for:** Cited as evidence that standardised benchmarks for this task now exist. **No numbers quoted from it** — the PDF would not text-extract cleanly and the baselines were not verified.
- **Generated:** `docs/iterations/benchmark_context_what_counts_as_good.md`.
- **Local PDF:** `literature/papers/archaeoscape_2024_als_archaeology_benchmark.pdf`.

### Gallwey et al. 2019 — Historic mining pits by transfer learning
- **Citation:** Gallwey, J., Eyre, M., Tonkins, M., Coggan, J. (2019). "Bringing Lunar LiDAR Back Down to Earth: Mapping Our Industrial Heritage through Deep Transfer Learning." *Remote Sensing* 11(17): 1994. doi:10.3390/rs11171994.
- **About:** Fine-tunes a crater-detection network (DeepMoon) onto lidar DTM to segment historic mining pits, reporting F1 up to ~0.87.
- **Used for:** Benchmark comparand for the WellSight pit U-Net.
- **Source:** https://doi.org/10.3390/rs11171994 — cite-only (MDPI blocks automated download).

### Guyot, Hubert-Moy & Lorho 2018 — Combined detection and segmentation of archaeological structures
- **Citation:** Guyot, A., Hubert-Moy, L., Lorho, T. (2018). "Combined Detection and Segmentation of Archeological Structures from LiDAR Data Using a Deep Learning Approach." *Journal of Computer Applications in Archaeology* 1(1): 1–10. doi:10.5334/jcaa.64.
- **About:** Feeds a multi-visualization lidar derivative stack to a CNN for buried structures under forest.
- **Candidate use:** Supporting evidence for the multi-visualization channel-stack approach we already use, and for adding VAT-family layers.
- **Generated:** `docs/iterations/pit_refinement_options.md` ("Channels we do not have").
- **Source:** https://doi.org/10.5334/jcaa.64 — cite-only (download endpoint returned non-PDF).

### Wiedemann et al. 1998 — Empirical evaluation of automatically extracted road axes
- **Citation:** Wiedemann, C., Heipke, C., Mayer, H., Jamet, O. (1998). "Empirical Evaluation of Automatically Extracted Road Axes." In *Empirical Evaluation Techniques in Computer Vision*, IEEE Computer Society Press, pp. 172-187.
- **About:** Defines the standard evaluation protocol for road extraction. Extracted and reference road axes are matched inside a buffer of width rho, then scored as completeness (matched reference length / total reference length), correctness (matched extracted length / total extracted length), and quality (comp * corr / (comp - comp*corr + corr)), a single figure that penalises both misses and false road.
- **Used for:** The scoring triple for the 613590 out-of-domain road test. Buffer rho = 5 m, matching the tolerance already used by `_road_threshold_products_9t.py` on 9t. Correctness is measured on predicted PIXELS rather than extracted line length, because a probability raster has no honest line length; it is labelled `correctness_px` in every output so the deviation from the paper stays visible.
- **Generated:** `notebooks/wellsight_v2/s5_eval/_score_road_pred_vs_roads_shp_613590.py`; `data/derivatives/eval_613590_roads/road_score_vs_roads_shp_613590_1m.csv`.
- **Source:** https://www.researchgate.net/publication/2378378 — cite-only (conference volume, no open PDF).
