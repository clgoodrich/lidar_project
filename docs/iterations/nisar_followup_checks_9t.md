# NISAR follow-up checks after two outside reviews of NISAR_FINDINGS.md (2026-10-27)

Goal. Run the seven checks the reviews asked for, one after the other. They follow `nisar_checks_9t.md`. Scope was "run them, do not go beyond". Area 9t, lidar-placed SLC stack (`NISAR_STACK=slc`), 5 m grid, EPSG:32617, unless stated.

## Summary

| # | Check | Result |
|---|---|---|
| 1 | Radar where lidar is weak | No gain on pads the U-Net missed (47) or on pads in canopy. A +0.015 gain in the lidar-weak quartile (tile-wide design only) is far below the +0.05 gate and does not appear in the local design. |
| 2 | Radar alone against Sentinel-2 alone | Against matched decoys Sentinel-2 wins (0.84 against 0.62). Against other clearings, with 60 pads, they tie (0.78 and 0.80). Radar adds nothing to Sentinel-2. |
| 3 | Why 0.64 tile-wide and 0.48 local | Explained. The radar score rises with decoy distance (0.44 at 100 to 500 m, 0.71 beyond 3.5 km). Map x/y and Sentinel-2 rise the same way. It is a place effect. |
| 4 | Terrain flattening, registration | HV flattened by the simulated facet gain changes no score. A point-target registration test found no peak, so no shift was applied. Raw HV in closed forest is mostly illumination. |
| 5 | Pit drop on one fixed subset | The drop is about one third sample attrition and two thirds decoy design. NISAR stays above chance (0.64) on the fixed pits. |
| 6 | Pad test on a second tile | Blocked by missing labels. A review package and a plan are written. |
| 7 | Audit of the optical comparison | Metadata confirms no reflectance offset. Held-out R2 keeps the optical lead. In closed forest the terrain gain explains most of raw HV. |

Reading note. Scores in checks 1, 2, 3, 5 and the HV-flat run are AUCs of probabilities averaged over repeated CV runs (3 to 10 repeats). Averaging lifts near-chance models a little, because single runs are noisy (the 10-repeat spread of local-design NISAR AUC is 0.36 to 0.63). Compare numbers inside a table, not against single-run numbers elsewhere. Example: pits under shape and incidence matching read 0.568 in the single-run leaderboard and 0.643 here.

## 1. Radar where lidar is weak

Script `notebooks/wellsight_v2/s5_eval/_nisar_weak_lidar_9t.py`. Models are rich lidar, all NISAR, NISAR + rich lidar, and a control with the NISAR rows shuffled across samples ("permuted"). A subset chosen for low lidar score makes any added model look better by regression to the mean, so the gain that counts is the combined gain minus the permuted gain. Five repeats, 500 m block bootstrap.

"U-Net missed" means no out-of-fold candidate at probability 0.5 overlaps the pad at IoU 0.3 (47 of 633, 7.4%, close to the 0.87 to 0.92 recall of the U-Net CV). The first attempt used probability 0.3. At 0.3 neighbouring pads merge into one blob and fall below IoU 0.3, so 30% looked missed. That definition was wrong and is kept only in `nisar_pad_weak_lidar_auc_9t_slc_cv5_iso_tau0p30.csv`.

Pads against matched decoys anywhere (633 pads):

| Subset | Pads | Rich lidar | All NISAR | NISAR + rich | Gain (95% CI) | Gain net of permuted (95% CI) |
|---|---|---|---|---|---|---|
| all | 633 | 0.931 | 0.650 | 0.933 | +0.002 (-0.010, +0.018) | +0.005 (-0.004, +0.021) |
| U-Net missed | 47 | 0.907 | 0.679 | 0.908 | +0.001 (-0.014, +0.026) | +0.006 (-0.007, +0.029) |
| U-Net found | 586 | 0.933 | 0.647 | 0.935 | +0.002 (-0.010, +0.016) | +0.005 (-0.004, +0.019) |
| lidar-weak quartile | 159 | 0.880 | 0.675 | 0.895 | +0.015 (+0.003, +0.036) | +0.016 (+0.003, +0.035) |
| covered by canopy (cover > 0.5) | 277 | 0.980 | 0.642 | 0.980 | 0.000 (-0.007, +0.006) | +0.001 (-0.005, +0.008) |
| weak and covered | 79 | 0.942 | 0.682 | 0.951 | +0.009 (-0.002, +0.024) | +0.010 (-0.002, +0.027) |

Same, local decoys (100 to 1,500 m, 297 pads): all -0.002; U-Net missed (17 pads) +0.002 (-0.034, +0.059); lidar-weak quartile (75) +0.003 (-0.026, +0.029); covered -0.007; weak and covered (41) -0.003. Files: `nisar_pad_weak_lidar_auc_9t_slc_local1500_cv5_iso_tau0p50.csv`.

Reading.
- The one interval that excludes zero is the lidar-weak quartile in the tile-wide design (+0.015). It is 30% of the gate. It is one of six subsets, unadjusted. It vanishes in the local design. Check 3 shows the tile-wide design rewards place, so this gain is not credited to the radar.
- Rich lidar still scores 0.907 on the pads the U-Net missed. The U-Net misses them as a region detector. The lidar texture model still tells them from matched decoys.
- The test cannot say anything about pads under canopy that lidar cannot see at all. Our annotations come from lidar, so such pads are not in the labels.

## 2. Radar alone against Sentinel-2 alone (no lidar features)

Script `_nisar_radar_vs_optical_pads_9t.py` with helper `_nisar_optical_feats_9t.py`. Sentinel-2 set: NDVI, NDMI, red, NIR for 3 Jun 2026, 7 Sep 2026 and 27 Oct 2025, June minus October NDVI, and a 15 m box mean, a contrast and a 25 m standard deviation for three layers (22 layers). "Radar basic" is the six date-mean HH/HV layers. The decoys are still matched with lidar cover and slope, so the design, not the model, uses lidar. Ten repeats.

| Feature set | Pads against matched decoys (633) | Pads against other clearings (60) |
|---|---|---|
| NISAR all bands | 0.622 | 0.795 |
| NISAR basic (6 layers) | 0.462 | 0.524 |
| Sentinel-2 (22 layers) | 0.840 | 0.781 |
| NISAR + Sentinel-2 | 0.834 | 0.809 |
| rich lidar (reference) | 0.932 | 0.988 |
| map x/y only | 0.863 | 0.427 |

Differences, block-bootstrap 95%:
- NISAR all minus Sentinel-2: -0.218 (-0.259, -0.111) against matched decoys; +0.014 (-0.068, +0.137) against clearings.
- NISAR + Sentinel-2 minus Sentinel-2: -0.006 (-0.020, +0.020) and +0.029 (-0.046, +0.118).

Reading.
- Against matched decoys free optical is clearly better than radar. Radar adds nothing to it.
- Against other clearings the two tie, and 60 pads cannot separate them. Radar has a niche there only if a larger sample shows a gain over optical. This one cannot.
- The 0.80 radar score comes from the many texture bands. The six plain backscatter layers score 0.52.
- The best single Sentinel-2 layers against matched decoys are June texture (NDVI 25 m standard deviation 0.79, red 0.75). The tile-wide optical score is partly location, since map x/y alone scores 0.86 (check 3).

## 3. Tile-wide 0.64 against local 0.48

Script `_nisar_pad_distance_bands_9t.py`. Decoys from the tile-wide and local matched-decoy files (same protocol) are pooled and binned by distance to their own pad. In each bin the pads with a decoy there are scored against the decoys in the bin. Three repeats.

| Decoy distance (m) | Pads | Decoys | NISAR | Sentinel-2 | map x/y | rich lidar | NISAR + S2 minus S2 (95% CI) |
|---|---|---|---|---|---|---|---|
| 100 to 500 | 43 | 237 | 0.440 | 0.722 | 0.381 | 0.915 | -0.104 (-0.213, +0.016) |
| 500 to 1,000 | 196 | 1,324 | 0.491 | 0.557 | 0.385 | 0.914 | +0.007 (-0.037, +0.053) |
| 1,000 to 1,500 | 255 | 2,197 | 0.531 | 0.602 | 0.651 | 0.933 | +0.007 (-0.049, +0.050) |
| 1,500 to 2,500 | 347 | 1,409 | 0.632 | 0.807 | 0.838 | 0.956 | +0.011 (-0.031, +0.049) |
| 2,500 to 3,500 | 478 | 2,059 | 0.680 | 0.852 | 0.919 | 0.919 | +0.015 (-0.023, +0.042) |
| 3,500 to 6,000 | 358 | 2,074 | 0.710 | 0.910 | 0.961 | 0.929 | 0.000 (-0.013, +0.024) |

Reading.
- The radar score climbs from chance to 0.71 as decoys move away. Map x/y climbs from 0.38 to 0.96, and Sentinel-2 from 0.56 to 0.91.
- Pads sit in particular parts of the tile. Ground far from a pad differs in stand type and setting. The radar sees that difference. It does not see the pad.
- Sentinel-2 explains at least as much as the radar at every distance, and the radar adds nothing to it (all intervals include zero).
- This closes the open item "unexplained 0.64 against 0.48". The 0.64 is a regional effect.
- Not done: adding stand type as an explicit covariate in a single model. The distance curve and the optical comparison make the same point.

## 4. Terrain flattening and registration

Terrain flattening. The NISAR set already holds flattened HH (`geometry:flat_db`, HH minus the simulated facet gain) and the gain (`geometry:sim_db`) per track, on 9t and on 613590, and the incidence-matched designs match decoys on that gain. HV was not flattened. Script `_nisar_hvflat_9t.py` adds three layers, date-mean HV minus `sim_db` per track (five repeats).

| Design | All NISAR | + HV flat | NISAR + rich lidar | + HV flat | Rich lidar |
|---|---|---|---|---|---|
| Pads, tile-wide (633) | 0.615 | 0.613 | 0.932 | 0.932 | 0.932 |
| Pits, matched (489) | 0.777 | 0.776 | 0.969 | 0.969 | 0.972 |
| Pits, shape + incidence (173) | 0.619 | 0.618 | 0.895 | 0.896 | 0.909 |

HV flat alone scores 0.41 to 0.51. Terrain-flattened HV changes no score by more than 0.002. The 613590 held-out pit test was not rerun, since it already uses the geometry product and HV flat adds nothing on 9t.

Registration. Script `_nisar_registration_points_9t.py`. Radar points are the single-track steady bright targets. Lidar objects are 9,592 compact canopy-height components (3 m or more, 6 to 150 m2) in open surroundings. For shifts within 40 m the hit rate (a radar point within 7.5 m) was compared with a null at 60 to 150 m. No peak appears. Zero-shift z-scores are -1.4 to +0.6. The best z-scores, 2.1 to 3.7, are what the maximum of 1,089 shifts gives by chance. Hit rates are 0.1% to 1.5%, equal to the null.
- This does not confirm or refute the 10 m residual. The object set is probably mostly shrubs, equipment and tree edges, and the radar rarely records them as steady points. The earlier well-based search also found no peak.
- No shift was applied. The pit held-out test was therefore not rerun for registration.

## 5. Pit drop on one fixed subset

Script `_nisar_pit_fixed_subset_9t.py`. 173 pits survive both designs. Five repeats.

| Design, scored on | Pits | Rich lidar | All NISAR | NISAR + rich | Gain (95% CI) |
|---|---|---|---|---|---|
| matched decoys, own full set | 489 | 0.976 | 0.811 | 0.973 | -0.003 |
| matched decoys, the 173 fixed pits (retrained) | 173 | 0.970 | 0.756 | 0.965 | -0.005 (-0.013, 0.000) |
| matched decoys, the 173 fixed pits (trained on all 489, pooled) | 173 | 0.970 | 0.744 | 0.966 | -0.004 (-0.010, +0.001) |
| shape + incidence decoys, the 173 pits | 173 | 0.923 | 0.643 | 0.909 | -0.014 (-0.037, +0.002) |

Reading.
- NISAR falls 0.811 to 0.756 on the smaller pit set (attrition, -0.055) and 0.756 to 0.643 from the decoy design (-0.113). About one third is sample, two thirds is design.
- The pits that find strict footprint and incidence matches are the easier-to-confuse ones for the radar. Rich lidar falls too (0.976, 0.970, 0.923).
- NISAR stays above chance (0.64), so the radar is not empty. It adds nothing to lidar in any row.
- Not done: separate runs with footprint matching alone and incidence matching alone. The split between those two inside the design step is not known.

## 6. Pad test on a second tile

Blocked. Tile 613590 has no annotated pad polygons, and there is no independently verified pad set on any other NISAR tile. DEP positions are unreliable, and `qgis/annotations/pads_truth.gpkg` is an early 88-polygon set on 9t.

Prepared. `data/613590/results/nisar/nisar_pad_review_candidates_613590.gpkg` holds the 161 pad candidates of the 9t-trained U-Net on 613590 (EPSG:6346), with empty `verdict` and `notes` columns. Mark each `confirmed`, `rejected` or `unsure` in QGIS. Candidates are not truth. The reviewer should also add pads the U-Net missed, as new polygons in the same layer with `verdict = added`.

Plan, fixed before any label exists. Train on all 9t pad samples (tile-wide matched decoys, same bands as the pit held-out test, bands present on both tiles). Score the confirmed and added 613590 pads once. Gate: NISAR + rich lidar beats rich lidar by 0.05 with the lower block-bootstrap bound above 0. Report also the subset of pads under canopy (cover above 0.5). The script is a copy of `_nisar_feat_heldout_9t.py` with `pad` samples. It has not been written, since there are no labels.

## 7. Audit of the optical comparison

Script `_nisar_vs_optical_heldout_9t.py`.

Metadata (`nisar_optical_scene_metadata_9t_slc.csv`). All three scenes have `earthsearch:boa_offset_applied` True (processing baseline 05.12, 05.12, 05.11). The offset is already removed, so reflectance is DN / 10,000. The earlier choice was right.

Cirrus (`nisar_optical_cirrus_check_9t_slc.csv`). The June scene has no cirrus pixels in the tile, so keeping or masking cirrus gives the same June correlation (HV against NDVI +0.46). The September scene has 63% of tile pixels flagged cirrus (1.1% over the whole scene) and its NDVI is saturated, so it carries no weight either way. Same-year optical (June and September 2026 only, no October 2025) gives held-out R2 0.446 against 0.443, so mixing years is not driving the result.

Held-out R2. 50 m blocks grouped in 1 km squares (25 squares), 5-fold grouped CV, pooled R2. OLS / gradient boosting. Table is date-mean HV (all three tracks):

| Subset | Cover alone | Lidar (4 layers) | Optical (6) | Lidar + optical | Lidar + terrain gain |
|---|---|---|---|---|---|
| whole tile (8,100 blocks) | -0.08 / -0.09 | -0.13 / -0.01 | 0.44 / 0.55 | 0.45 / 0.60 | 0.15 / 0.27 |
| closed canopy (1,382) | -0.06 / -0.09 | 0.07 / 0.08 | 0.09 / 0.21 | 0.17 / 0.31 | 0.57 / 0.56 |
| open ground (1,128) | -0.37 / -0.31 | -0.33 / -0.24 | 0.68 / 0.68 | 0.69 / 0.65 | -0.13 / -0.02 |

Terrain-flattened HV (HV minus `sim_db`, mean of tracks), OLS / gradient boosting:

| Subset | Lidar | Optical | Lidar + optical |
|---|---|---|---|
| all | -0.13 / 0.02 | 0.48 / 0.59 | 0.50 / 0.66 |
| closed canopy | 0.19 / 0.19 | 0.16 / 0.24 | 0.35 / 0.43 |
| open ground | -0.31 / -0.20 | 0.70 / 0.64 | 0.70 / 0.63 |

Reading.
- The optical lead holds out. Optical R2 on unseen squares is 0.44 to 0.55 over the tile, against the in-sample 0.52.
- In closed forest, adding the simulated terrain gain to lidar lifts held-out R2 from 0.07 to 0.57. Raw HV there is mostly terrain illumination (local incidence), not vegetation. This replaces the earlier guess that the ground-elevation term meant stand type. It was illumination.
- After flattening, closed-canopy HV is explained about equally by lidar (0.19) and optical (0.16 to 0.24), and together 0.35 to 0.43. Over half is still unexplained.
- Canopy cover alone does not predict HV on unseen squares (negative R2). The in-sample 0.04 of lidar layers was not hiding a strong nonlinear cover effect that gradient boosting could find across squares.
- Lidar alone is negative over the tile and in open ground. A fit on 20 squares does not carry to the other 5 for elevation-driven terms. In-sample R2 hid that.
- Still not separated: ground against canopy energy. R2 does not give an energy split.

## Files

New scripts (`notebooks/wellsight_v2/s5_eval/`): `_nisar_weak_lidar_9t.py`, `_nisar_radar_vs_optical_pads_9t.py`, `_nisar_optical_feats_9t.py`, `_nisar_pad_distance_bands_9t.py`, `_nisar_hvflat_9t.py`, `_nisar_registration_points_9t.py`, `_nisar_pit_fixed_subset_9t.py`, `_nisar_vs_optical_heldout_9t.py`.

Results (`data/9t/results/nisar/`):
- `nisar_pad_weak_lidar_auc_9t_slc_cv5_iso_tau0p50.csv`, `nisar_pad_weak_lidar_auc_9t_slc_local1500_cv5_iso_tau0p50.csv`, `nisar_pad_weak_lidar_auc_9t_slc_cv5_iso_tau0p30.csv` (superseded definition), `nisar_pad_unet_found_per_pad_9t_slc_cv5_iso_tau0p50.csv`, `..._tau0p30.csv`
- `nisar_pad_radar_vs_optical_auc_9t_slc.csv`, `nisar_pad_radar_vs_optical_auc_9t_slc_confuser.csv`
- `nisar_pad_distance_bands_auc_9t_slc.csv`
- `nisar_pad_hvflat_auc_9t_slc.csv`, `nisar_pit_hvflat_auc_9t_slc.csv`, `nisar_pit_hvflat_auc_9t_slc_shape_inc.csv`
- `nisar_registration_points_shift_9t_slc.csv`, `nisar_registration_points_grids_9t_slc.npz`
- `nisar_pit_fixed_subset_auc_9t_slc.csv`
- `nisar_vs_optical_heldout_r2_9t_slc.csv`, `nisar_optical_scene_metadata_9t_slc.csv`, `nisar_optical_cirrus_check_9t_slc.csv`
- `data/613590/results/nisar/nisar_pad_review_candidates_613590.gpkg`

Reproduce (each from `notebooks/wellsight_v2/s5_eval/` with `NISAR_STACK=slc`):
```
UNET_DIR=unet_cv5_iso TAU=0.5 REPEATS=5 python _nisar_weak_lidar_9t.py          # add LOCAL_M=1500 for the local design
REPEATS=10 python _nisar_radar_vs_optical_pads_9t.py                            # add CONFUSER=1 for clearings
REPEATS=3 python _nisar_pad_distance_bands_9t.py
TARGET=pit SHAPE=1 INC_MATCH=1 REPEATS=5 python _nisar_hvflat_9t.py             # also TARGET=pit, TARGET=pad
python _nisar_registration_points_9t.py
REPEATS=5 python _nisar_pit_fixed_subset_9t.py
python _nisar_vs_optical_heldout_9t.py
```

## What these checks do not settle

- Pads that lidar cannot see at all. The labels come from lidar.
- The split between ground and canopy return.
- Registration. The point-target test was null and uninformative.
- A larger sample of pads against other clearings, where radar and Sentinel-2 tie.
- A pad held-out test on a second tile (labels needed).
- Footprint matching against incidence matching, as separate factors, for pits.
