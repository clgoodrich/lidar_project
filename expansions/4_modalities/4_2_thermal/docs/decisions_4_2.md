# 4.2 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review 4.2-01. Added value over lidar is measured on an unmatched population (every pad and every eligible clearing clear of pads and audit blocks). The caliper-matched set stays for T3 only. On the matched set T4 returns `not_identifiable`, because matching on the lidar covariates makes lidar uninformative by design. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.2-02. Tie points are a QC gate. T1 cannot give success without tie points or with a median RMSE above `max_registration_frac_pixel` times the native pixel. T2 drops scenes over the limit and refuses a sensor whose T1 run had no tie points. A diluted contrast below delta_T can still give failure, because misregistration only lowers contrast further. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.2-03. `latest_run` picks the run with the latest `written` time in `_PROVENANCE.json`. Runs without provenance never finished and are skipped. Made by the review-fix agent, change freely.
- 2026-11-06. Cloud QA note. T2 masks pixels by the instrument per-pixel QA band (`qa_band`, `qa_rule` per sensor in config) and refuses a sensor without one. Scene-level `cloud_frac` stays as a scene filter only. Made by the review-fix agent, change freely.
- 2026-11-06. Review P2-01. The P2 audit CSV is read only through `ek.require_audit`. Its integer block ids are mapped to this module's `bx_by` ids through the `ix` and `iy` columns of `nine_t/pit_blocks_9t.gpkg` (block_id is iy times 12 plus ix). A missing file refuses unless `--allow-no-audit`, and the output then says exploratory. Made by the review-fix agent, change freely.
- 2026-11-06. Review SH-01. Bootstrap draws that are undefined are counted and reported as `undefined_share`. `added_value.max_undefined` is 0, so any undefined draw gives an undefined interval and an inconclusive verdict. Made by the review-fix agent, change freely.

- 2026-11-05. Generic helpers (fill fraction, area-weighted extraction, caliper matching, solar position, added value) live once in `src/_thermal_shared_io.py`. 4.3 imports them. Made by the build agent, change freely.
- 2026-11-05. Pads are restricted to the 9t CHM extent (`nine_t_1m/chm_9t_1m.tif`). The pad layer spans several areas (995 pads, 650 inside 9t). Made by the build agent, change freely.
- 2026-11-05. The framework's CHM path `multires_chm_window/chm_chmwindow_9t_1m.tif` is a 300 m test window. The full 9t CHM, DEM and slope at 1 m are used instead. Made by the build agent, change freely.
- 2026-11-05. Fill fraction is the largest share of one native pixel the pad covers, averaged over 16 random grid offsets. The fixed-grid value is kept beside it. Made by the build agent, change freely.
- 2026-11-05. Without a measured proxy_dT the T1 gate reports the break-even dT and stays inconclusive. No assumed contrast is entered. Made by the build agent, change freely.
- 2026-11-05. T3 uses scene fixed effects in place of a scene random effect because statsmodels is not installed. The lidar null is fitted on clearings and forest only. Made by the build agent, change freely.
- 2026-11-05. Forest controls are the pad outline moved 150 to 400 m to ground with mean CHM of 10 m or more, clear of pad buffers. Made by the build agent, change freely.
- 2026-11-05. Outputs go to the expansion `results/` run folders, not `data/9t/results/thermal/`, because the build brief allowed writes only inside the expansion folder. `--out-root` moves them. Made by the build agent, change freely.
- 2026-11-05. T4 refuses to run without the 3.0 block folds unless `--fallback-folds` is given. Fallback folds are labelled exploratory. Made by the build agent, change freely.

## Needs user decision

- `added_value.max_undefined`. The share of undefined bootstrap draws T4 may tolerate. It is 0 now.
- Sensor scaling must be verified against the product guides. The constants live in `src/config_4_2.json` under `sensors`. Landsat TIRS uses `lst_scale` 0.00341802 and `lst_offset` 149.0 (Collection 2 Level 2 ST_B10). ECOSTRESS uses `lst_scale` 1.0 and `lst_offset` 0.0. That holds only for an already scaled delivery. The raw ECO2LSTE product stores LST as uint16 with scale 0.02. Native pixels are 100 m (Landsat) and 70 m (ECOSTRESS). They are read in `src/_thermal_extract_samples_9t.py` (`scene_lst`) and `src/_thermal_gate_contrast_9t.py`. T2 refuses LST outside `lst_plausible_K`, which catches a wrong scale but not a small offset error.
- Cloud QA bit layouts must be verified. Landsat `qa_rule` treats QA_PIXEL bits 0 to 5 as bad (fill, dilated cloud, cirrus, cloud, cloud shadow, snow). ECOSTRESS `qa_rule` keeps QC bits 0 and 1 equal to 0 or 1 (best or nominal). The band index `qa_band` assumes LST in band 1 and QA in band 2 (Landsat) or 3 (ECOSTRESS). They live in `src/config_4_2.json` and are applied in `qa_bad` in `src/_thermal_extract_samples_9t.py`.
- Whether the unmatched population for T4 should also include the forest controls. It holds pads and clearings now.
