# 4.3 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review 4.3-01. Reflectance is (DN + BOA_ADD_OFFSET) / BOA_QUANTIFICATION_VALUE. The constants come from the stack tags or a declared `radiometry` per scene with a `source`. Nothing is assumed. For processing baseline 04.00 or later an offset of 0 refuses unless upstream removal is declared. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.3-01. Indices are computed on native grids. The held 5 m stacks are exact copies of native pixels (checked on all three stacks. At least 99% of 2 by 2 blocks are constant for green, red and nir at a 1 pixel offset, and 4 by 4 for swir). V2 puts them back on 10 m and 20 m. Bands finer than a grid are averaged onto it. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.3-01. SCL keeps 4 (vegetation) and 5 (not vegetated) only. The code refuses a list that keeps water, snow, cloud, cirrus or shadow. This replaces the 2026-11-05 list 4, 5, 6, 11. A stack without SCL refuses unless `extract.allow_unmasked`. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.3-02. V3 is measured on an unmatched population (every pad and every eligible control). On the matched set it returns `not_identifiable`, because lidar is uninformative there by design. Made by the review-fix agent, change freely.
- 2026-11-06. Review 4.3-03. V0 counts records only from the first scene date minus `labels.visible_lookback_days` to the last scene date. It refuses while `labels.codes_status` is not `dep_verified`, so placeholder codes cannot close Question B. Made by the review-fix agent, change freely.
- 2026-11-06. Held stack dates are set from the script that wrote them. 2026-06-03 (S2A_17TPG_20260603_0_L2A), 2026-09-07 (S2B_17TPG_20260907_0_L2A) and 2025-10-27 (S2C_17TPG_20251027_0_L2A). This replaces the mid-month placeholders. Made by the review-fix agent, change freely.
- 2026-11-06. Reviews P2-01 and SH-01. The audit set is read through `ek.require_audit` with the 4.2 helper. Undefined bootstrap draws are counted and reported, with `max_undefined` 0 in config. Made by the review-fix agent, change freely.


- 2026-11-05. Generic helpers are imported from the 4.2 module `../4_2_thermal/src/_thermal_shared_io.py` rather than duplicated. Made by the build agent, change freely.
- 2026-11-05. Added a matching script `_vegstress_match_controls_9t.py`. The framework needs controls fixed before indices are read but named no script for it. Made by the build agent, change freely.
- 2026-11-05. Pads are restricted to the 9t CHM extent (650 of 995). The full 9t CHM at 1 m replaces the 300 m `multires_chm_window` test window. Made by the build agent, change freely.
- 2026-11-05. A clean measurement counts as a strong non-leak label, as a clean inspection counts as a weak one. Made by the build agent, change freely.
- 2026-11-05. Leak and clean code lists in config are placeholders, not DEP codes. They must be replaced when R1 returns. Made by the build agent, change freely.
- 2026-11-05. An interior pixel is open when at least half its 1 m CHM cells are under 2 m. The index is read only from open pixels with a valid SCL class (4, 5, 6, 11). Made by the build agent, change freely.
- 2026-11-05. With one year of scenes the stress anomaly is referenced to the site's mean over all scenes and the output says so. V4 then uses per-season site minus ring differences as stress features. Made by the build agent, change freely.
- 2026-11-05. Held Sentinel-2 stack dates are mid-month placeholders until the acquisition dates are confirmed. Made by the build agent, change freely.
- 2026-11-05. Outputs go to the expansion `results/` run folders, not `data/9t/results/vegstress/`, because the build brief allowed writes only inside the expansion folder. Made by the build agent, change freely.

## Needs user decision

- Radiometry of the held stacks. They have no L2A tags. The DN look offset-free (red minimum 148 in June and 1 in October, both below 1000). Scenes from 2025 and 2026 are baseline 05.xx and carry the -1000 offset. So the Element 84 Earth Search delivery most likely removed it. Check the STAC item property `earthsearch:boa_offset_applied` for the three items. Then declare `scenes[*].radiometry` in `src/config_4_3.json` with add_offset -1000, quantification 10000, the processing baseline, offset_removed_upstream true, and the source.
- `labels.visible_lookback_days`. How long before a scene a DEP record can still describe what it shows. It is null now, and V0 refuses.
- `added_value.max_undefined` and `leak_test.max_undefined`. The share of undefined bootstrap draws V3 and V4 may tolerate. Both are 0 now.
- Whether the September scene belongs to leaf_on (the writing script calls it leaf-on) or shoulder (the config). It is shoulder now.
- Sensor scaling to verify. The constants live in `src/_vegstress_shared_io.py` (`OFFSET_BASELINE` 4.0 and `SCL_FORBIDDEN`) and in `src/config_4_3.json` (`band_native_m` and `scl_valid`). Verify against the ESA Sentinel-2 L2A product specification that BOA_ADD_OFFSET is -1000 from baseline 04.00, that quantification is 10000, that B2, B3, B4 and B8 are 10 m, that B5, B11 and SCL are 20 m, and the SCL class numbers.
