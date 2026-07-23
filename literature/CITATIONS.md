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
| Yokoyama et al. | 2002 | Topographic openness | `openness_pos/neg` channels | `notebooks/wellsight_v2/build/_build_derivatives.py` | cite-only |
| Chiba et al. | 2008 | Red Relief Image Map (RRIM) | `diff_openness` channel + RRIM viz products | `_make_rrim.py`; `diff_openness_*` in `_build_extra_channels.py` | ✓ `chiba_2008_red_relief_image_map.pdf` |
| Auld-Thomas (blog) | 2022 | "Simple Red Relief" (LRM-base RRIM) | RRIM variant (LRM as base layer) | `notebooks/.../_make_rrim.py` | ✓ `auldthomas_2022_simple_red_relief.pdf` |
| Hesse | 2010 | LiDAR Local Relief Model (LRM) | `lrm_{3,5,11,25}` channels | `notebooks/wellsight_v2/build/_build_derivatives.py` | cite-only |
| Sofia, Marinello & Tarolli | 2014 | SLLAC (slope local autocorrelation length) | `sllac_len`, `sllac_aniso` channels | `notebooks/wellsight_v2/build/_build_extra_channels.py` | cite-only |
| Frangi et al. | 1998 | Multiscale vesselness (Hessian) | `frangi_lrm`, `frangi_slresid` channels | `notebooks/wellsight_v2/build/_build_extra_channels.py` | cite-only |
| Sato et al. | 1998 | Multi-scale line filter (tubeness) | `ridge_sato` channel | `notebooks/wellsight_v2/build/_build_extra_channels.py` | cite-only |
| Steger | 1998 | Unbiased curvilinear-structure detector | `ridge_orient` (Steger-family ridge/orientation) | `notebooks/wellsight_v2/build/_build_extra_channels.py` | ✓ `steger_1998_curvilinear_detector.pdf` |
| Ferraz, Mallet & Chehata | 2016 | Forest-road detection from lidar (elongated planar model + graph gap-linking) | Motivates `slope_residual`, `rough_aniso`; blueprint for the planned gap-linking pass | `_build_extra_channels.py` + future road linker | cite-only |
| Batra et al. | 2019 | Orientation learning for road connectivity | Orientation field for gap-linking | `ridge_orient` in `_build_extra_channels.py` + future linker | ✓ `batra_2019_road_connectivity_cvpr.pdf` |
| Shit et al. | 2021 | clDice topology-preserving loss | `ClDiceFocal` road-segmentation loss | `notebooks/wellsight_v2/roads/_road_sweep_202607.py`; `cldice`/`cldice_mkf` `road_prob` rasters | ✓ `cldice_shit_2021.pdf` |
| Savitzky & Golay | 1964 | Least-squares polynomial smoothing/differentiation | 2D SavGol quadratic residual (detrends slope+curvature) | `savgol_resid_*` in `_build_extra_channels.py` | ✓ `savitzky_golay_1964.pdf` |
| Wood | 1996 | Multiscale quadratic-surface DEM geomorphometry | Basis for local quadratic land-surface fitting (SavGol residual, curvature) | `savgol_resid_*`, `profile_curv` in `_build_extra_channels.py` | cite-only |
| Soille | 2004 | Mathematical morphology (top-hat transform) | White/black top-hat cut/fill bench channels | `tophat_white/black` in `_build_extra_channels.py` | cite-only |

---

## Detailed entries

### Yokoyama, Shirasawa & Pike 2002 — Topographic openness
- **Citation:** Yokoyama, R., Shirasawa, M., Pike, R.J. (2002). "Visualizing topography by openness: A new application of image processing to digital elevation models." *Photogrammetric Engineering & Remote Sensing* 68(3): 257–265.
- **About:** Positive/negative openness — angular measure of how enclosed a point is, looking out to a distance L over 8 azimuths. Convex forms → high positive openness; concave (channels, cuts) → high negative openness. Illumination-independent.
- **Used for:** The `openness_pos` / `openness_neg` terrain channels (8-direction Yokoyama, L = 25 cells) — 2 of the 7 road-model input channels.
- **Generated:** `notebooks/wellsight_v2/build/_build_derivatives.py` (`openness()` function).
- **Source:** https://scispace.com/papers/visualizing-topography-by-openness-a-new-application-of-1e2fefq450 — cite-only (ASPRS paywall).

### Chiba, Kaneta & Suzuki 2008 — Red Relief Image Map (RRIM)
- **Citation:** Chiba, T., Kaneta, S., Suzuki, Y. (2008). "Red Relief Image Map: New Visualization Method for Three-Dimensional Data." *Int. Archives of Photogrammetry, Remote Sensing and Spatial Information Sciences* 37(B2): 1071–1076.
- **About:** Composite terrain visualization = red-chroma slope × brightness from differential openness (positive − negative). Steep = vivid red, ridges bright, channels/cuts dark; illumination-independent.
- **Used for:** The `diff_openness` channel (openness_pos − openness_neg, the RRIM brightness base) and the RRIM viewing products.
- **Generated:** RRIM builder `_make_rrim.py`; `diff_openness_*.tif` in `_build_extra_channels.py`.
- **Local PDF:** `literature/papers/chiba_2008_red_relief_image_map.pdf`.

### Auld-Thomas 2022 — "A Recipe for Simple Red Relief" (methods note)
- **Citation:** Ancient Maya Settlement project (Auld-Thomas et al.), "A Recipe for Simple Red Relief," 2022-02-12 (technical blog / methods note, not peer-reviewed).
- **About:** A simplified RRIM that swaps Chiba's differential-openness base for a Local Relief Model base — cheaper to compute, similar linear-feature legibility.
- **Used for:** The LRM-base RRIM variant.
- **Generated:** `_make_rrim.py` (simple-red-relief mode).
- **Source:** https://ancientmayasettlement.com/2022/02/12/a-recipe-for-simple-red-relief/
- **Local PDF:** `literature/papers/auldthomas_2022_simple_red_relief.pdf`.

### Hesse 2010 — LiDAR Local Relief Model (LRM)
- **Citation:** Hesse, R. (2010). "LiDAR-derived Local Relief Models – a new tool for archaeological prospection." *Archaeological Prospection* 17(2): 67–72. doi:10.1002/arp.374
- **About:** LRM = DEM minus a smoothed (low-pass) DEM, isolating small shallow features (sunken roads, earthworks, terraces) independent of illumination angle.
- **Used for:** The `lrm_{3,5,11,25}` multi-scale channels (road-model inputs `lrm_5`, `lrm_25`).
- **Generated:** `notebooks/wellsight_v2/build/_build_derivatives.py`.
- **Source:** https://onlinelibrary.wiley.com/doi/abs/10.1002/arp.374 — cite-only (Wiley paywall).

### Sofia, Marinello & Tarolli 2014 — SLLAC
- **Citation:** Sofia, G., Marinello, F., Tarolli, P. (2014). "A new landscape metric for the identification of terraced sites: The Slope Local Length of Auto-Correlation (SLLAC)." *ISPRS Journal of Photogrammetry and Remote Sensing* 96: 123–133.
- **About:** Anthropogenic earthworks (terraces, roads) leave an *organized* topographic signature. SLLAC measures the length over which the slope field stays auto-correlated in a direction; natural terrain is noisy (short length), engineered surfaces are persistent (long, directional).
- **Used for:** The `sllac_len` / `sllac_aniso` channels. **Note:** our implementation is a documented 4-direction *approximation* of the method, not a faithful reproduction of the paper's normalized-cross-correlation formulation.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_sllac`).
- **Source:** https://www.sciencedirect.com/science/article/abs/pii/S0924271614001786 — cite-only (Elsevier paywall).

### Frangi et al. 1998 — Multiscale vesselness
- **Citation:** Frangi, A.F., Niessen, W.J., Vincken, K.L., Viergever, M.A. (1998). "Multiscale vessel enhancement filtering." *MICCAI 1998*, LNCS 1496: 130–137.
- **About:** Hessian eigenvalue filter that responds to elongated (tubular) structures across scales; returns a vesselness magnitude per pixel.
- **Used for:** `frangi_lrm`, `frangi_slresid` — enhancing linear road/trail treads as dark ridges. Via `skimage.filters.frangi`.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_frangi`).
- **Source:** https://research.manchester.ac.uk/en/publications/multiscale-vessel-enhancement-filtering/ — cite-only.

### Sato et al. 1998 — Multi-scale line filter (tubeness)
- **Citation:** Sato, Y., et al. (1998). "Three-dimensional multi-scale line filter for segmentation and visualization of curvilinear structures in medical images." *Medical Image Analysis* 2(2): 143–168.
- **About:** Hessian-based line-enhancement filter (tubeness); companion to Frangi, different eigenvalue combination.
- **Used for:** `ridge_sato` channel. Via `skimage.filters.sato`.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_ridge`).
- **Source:** Medical Image Analysis — cite-only (Elsevier paywall).

### Steger 1998 — Unbiased detector of curvilinear structures
- **Citation:** Steger, C. (1998). "An unbiased detector of curvilinear structures." *IEEE TPAMI* 20(2): 113–125. doi:10.1109/34.659930
- **About:** Scale-space line model that extracts sub-pixel line position, width, and **orientation** without the bias Gaussian smoothing introduces on asymmetric profiles.
- **Used for:** `ridge_orient` — the per-pixel along-ridge orientation field (Steger-family; we compute the Hessian orientation directly). This orientation field is what enables the planned connectivity/gap-linking step.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_ridge`).
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
- **Generated:** `notebooks/wellsight_v2/roads/_road_sweep_202607.py`; `cldice` and `cldice_mkf` `road_prob` rasters under `data/derivatives/tiles/9t/road_sweep_202607/`.
- **Local PDF:** `literature/papers/cldice_shit_2021.pdf`.

### Savitzky & Golay 1964 — Least-squares polynomial smoothing
- **Citation:** Savitzky, A., Golay, M.J.E. (1964). "Smoothing and Differentiation of Data by Simplified Least Squares Procedures." *Analytical Chemistry* 36(8): 1627–1639.
- **About:** Local polynomial (Savitzky-Golay) regression — smooths a signal by fitting a low-order polynomial in a moving window, preserving peak shape and width that plain averaging flattens.
- **Used for:** The 2D SavGol **quadratic residual** channels. Fitting `a+bx+cy+dx²+ey²+fxy` and subtracting removes the local slope *and* curvature, so only departures from a smooth hillslope (anthropogenic benches) survive. Fixes the curvature contamination of the LRM unsharp mask (`DEM − focal_mean` leaks ~`(σ²/2)·∇²z`).
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_savgol`, `_sg2d_kernel`).
- **Provenance note:** the bench-detection *application* recipe (quadratic residual + top-hat on detrended elevation, slope-normal frame) was proposed by the user's Claude agent; this paper is the underlying smoothing method.
- **Local PDF:** `literature/papers/savitzky_golay_1964.pdf`.

### Wood 1996 — Multiscale quadratic-surface DEM geomorphometry
- **Citation:** Wood, J. (1996). "The Geomorphological Characterisation of Digital Elevation Models." Ph.D. Thesis, University of Leicester, 466 pp.
- **About:** Parameterises DEMs by fitting quadratic surfaces over a *range of window sizes* and taking first/second derivatives, characterising landform at any scale rather than a fixed 3×3.
- **Used for:** Methodological basis for the local quadratic land-surface fit behind the SavGol residual and multiscale approach; also underpins profile curvature.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_savgol`, multiscale stack).
- **Source:** https://lra.le.ac.uk/handle/2381/34503 ; https://figshare.le.ac.uk/articles/thesis/10152368 — cite-only (466-pp thesis).

### Soille 2004 — Mathematical morphology (top-hat)
- **Citation:** Soille, P. (2004). *Morphological Image Analysis: Principles and Applications*, 2nd ed. Springer.
- **About:** Standard reference for grayscale morphology. The white top-hat (`f − opening(f)`) isolates bright structures smaller than the structuring element; the black/bottom top-hat (`closing(f) − f`) isolates dark ones.
- **Used for:** The `tophat_white` (fill lip) and `tophat_black` (cut) bench channels, run on the SavGol residual with a disk SE just wider than the tread. The offset white/black pair is a selective bench signature.
- **Generated:** `notebooks/wellsight_v2/build/_build_extra_channels.py` (`ch_tophat`).
- **Source:** Springer (book) — cite-only.
