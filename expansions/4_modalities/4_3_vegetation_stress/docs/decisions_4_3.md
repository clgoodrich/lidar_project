# 4.3 decisions

Newest first. One line per decision, with the date and who made it.


- 2026-11-05. Generic helpers are imported from the 4.2 module `../4_2_thermal/src/_thermal_shared_io.py` rather than duplicated. Made by the build agent, change freely.
- 2026-11-05. Added a matching script `_vegstress_match_controls_9t.py`. The framework needs controls fixed before indices are read but named no script for it. Made by the build agent, change freely.
- 2026-11-05. Pads are restricted to the 9t CHM extent (650 of 995). The full 9t CHM at 1 m replaces the 300 m `multires_chm_window` test window. Made by the build agent, change freely.
- 2026-11-05. A clean measurement counts as a strong non-leak label, as a clean inspection counts as a weak one. Made by the build agent, change freely.
- 2026-11-05. Leak and clean code lists in config are placeholders, not DEP codes. They must be replaced when R1 returns. Made by the build agent, change freely.
- 2026-11-05. An interior pixel is open when at least half its 1 m CHM cells are under 2 m. The index is read only from open pixels with a valid SCL class (4, 5, 6, 11). Made by the build agent, change freely.
- 2026-11-05. With one year of scenes the stress anomaly is referenced to the site's mean over all scenes and the output says so. V4 then uses per-season site minus ring differences as stress features. Made by the build agent, change freely.
- 2026-11-05. Held Sentinel-2 stack dates are mid-month placeholders until the acquisition dates are confirmed. Made by the build agent, change freely.
- 2026-11-05. Outputs go to the expansion `results/` run folders, not `data/9t/results/vegstress/`, because the build brief allowed writes only inside the expansion folder. Made by the build agent, change freely.
