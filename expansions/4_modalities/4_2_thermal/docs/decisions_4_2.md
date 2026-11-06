# 4.2 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Generic helpers (fill fraction, area-weighted extraction, caliper matching, solar position, added value) live once in `src/_thermal_shared_io.py`. 4.3 imports them. Made by the build agent, change freely.
- 2026-11-05. Pads are restricted to the 9t CHM extent (`nine_t_1m/chm_9t_1m.tif`). The pad layer spans several areas (995 pads, 650 inside 9t). Made by the build agent, change freely.
- 2026-11-05. The framework's CHM path `multires_chm_window/chm_chmwindow_9t_1m.tif` is a 300 m test window. The full 9t CHM, DEM and slope at 1 m are used instead. Made by the build agent, change freely.
- 2026-11-05. Fill fraction is the largest share of one native pixel the pad covers, averaged over 16 random grid offsets. The fixed-grid value is kept beside it. Made by the build agent, change freely.
- 2026-11-05. Without a measured proxy_dT the T1 gate reports the break-even dT and stays inconclusive. No assumed contrast is entered. Made by the build agent, change freely.
- 2026-11-05. T3 uses scene fixed effects in place of a scene random effect because statsmodels is not installed. The lidar null is fitted on clearings and forest only. Made by the build agent, change freely.
- 2026-11-05. Forest controls are the pad outline moved 150 to 400 m to ground with mean CHM of 10 m or more, clear of pad buffers. Made by the build agent, change freely.
- 2026-11-05. Outputs go to the expansion `results/` run folders, not `data/9t/results/thermal/`, because the build brief allowed writes only inside the expansion folder. `--out-root` moves them. Made by the build agent, change freely.
- 2026-11-05. T4 refuses to run without the 3.0 block folds unless `--fallback-folds` is given. Fallback folds are labelled exploratory. Made by the build agent, change freely.
