# NISAR L-band radar: findings (9t, Venango County, Pennsylvania)

Written 2026-10-27. Methods and file lists are in `NISAR_METHODS.md`. Full tables are in `docs/iterations/nisar_checks_9t.md`.

## Bottom line

The results do not justify adding NISAR to the lidar detector. No design we tried showed a reliable gain.

That is a narrower claim than "NISAR adds nothing". Some of the tests could not have shown a gain, because the lidar baseline was already near 1.0 (pads against other clearings, the U-Net fusion). The tile-wide pad design (lidar 0.93) and the held-out pit test (lidar 0.88) had room. Neither showed a gain. A small benefit is not excluded.

On its own the radar does carry some signal. It separates pads from other clearings at 0.80 and held-out pits from decoys at 0.658. That signal is redundant where lidar exists.

The follow-up checks of 2026-10-27 tested the cases where it might matter:
- **Where lidar is weak.** On the pads the U-Net missed (47) the gain over lidar is +0.001. In the lidar-weak quartile it is +0.015 in one design and +0.003 in the other. Both are far below the +0.05 gate.
- **Where lidar is absent.** Free Sentinel-2 imagery does as well as the radar, or better. Against other clearings they tie (0.78 and 0.80, 60 pads). Against matched decoys Sentinel-2 wins (0.84 against 0.62). The radar adds nothing to Sentinel-2.
- **The tile-wide pad score.** The 0.64 against decoys anywhere is a place effect. The radar score rises from chance to 0.71 as decoys move from 100 m to over 3.5 km away. Map x/y and Sentinel-2 rise the same way.

The radar varies more with optical vegetation indices than with lidar canopy height. In closed forest, raw HV is mostly terrain illumination. We did not separate the ground and canopy contributions, so we do not know where the returns originate.

## What we tested

- **Question.** Does NISAR carry a signal that identifies well pads, pits, wells and pumpjacks, and can it help the lidar detector?
- **Radar.** NISAR L-band (24 cm wavelength, 1.257 GHz), left-looking. No S-band data is used.
- **Products.** L2 GSLC and SLC at 5 m, HH and HV polarisation. Tracks 26, 90 and 162, with 8, 11 and 14 dates.
- **Area.** Tile 9t, Venango County, 4.9 km, EPSG:32617. A second tile, 613590, was used for one held-out test.
- **Status of the data.** Beta and provisional products. They are not validated or fully calibrated.
- **Registration.** The radar sits about 10 m off the lidar.

## How results are scored

- Each target pad or pit is compared with decoy locations that match its canopy cover (±0.05) and slope (±1°).
- AUC is the chance that a target scores higher than a decoy. 0.5 is chance.
- The model is gradient boosting with 5-fold spatial block cross-validation (500 m blocks, 250 m buffer).
- Controls are a lidar-only model, a richer lidar model (26 texture bands), a map-coordinates-only model and a placebo.
- The gate was set in advance. NISAR plus rich lidar must beat rich lidar alone by 0.05.

## Findings

### 1. Pads

| Design | NISAR AUC | Note |
|---|---|---|
| Decoys drawn anywhere on the tile | 0.64 | Looks like a signal |
| Decoys drawn near their own target | 0.48 | Chance |
| Same footprint and matched incidence, tile-wide | 0.657 | |
| Same footprint and matched incidence, local | 0.490 | Chance |
| Pad footprint moved 150 to 300 m (placebo) | 0.504 | Chance |
| Placebo scored by map coordinates alone | 0.890 | The coordinates find the fake pads |
| Decoys only from other clearings (60 pads) | 0.80 | Rich lidar 0.99, combined 0.99 |

- The tile-wide 0.64 disagrees with the local 0.48. The distance-band test (section 5) explains it. The radar separates a pad from ground far away because far ground is a different place, not because the pad looks different.
- The placebo shows that a model can score well by location alone. The radar does not.
- The clearing test separates pads from other clearings at 0.80. Lidar does the same job at 0.99, and adding the radar does not change that.
- That test is ceiling-limited. With lidar at 0.99, the largest possible gain is +0.01, so the +0.05 gate could not be met. It is uninformative about a gain, not evidence against one.
- Only 60 pads are in the clearing test, so it has little power.
- DEP well status (for example orphan-list wells) shows no radar signal beyond lidar. Only 9 pads sit on orphan-list wells, too few to score.

### 2. Pits

- NISAR against decoys scores 0.829 with the first design. It falls to 0.568 once decoys take the pit's own footprint and matched incidence.
- That drop mixes two changes. The match changed, and the pit subset shrank from 489 to 173. On one fixed set of 173 pits the NISAR score reads 0.811 on the full set, 0.756 on the 173 pits with the original decoys and 0.643 with the shape and incidence decoys (repeat-averaged scores). About one third of the drop is sample, two thirds is decoy design. The radar stays above chance, and adds nothing to lidar in any row.
- A frozen model trained on 9t pits was tested on 36 pits of tile 613590. NISAR alone scored 0.658, rich lidar 0.881 and the combination 0.865. The gate failed.
- The gain over rich lidar was -0.017, with a bootstrap interval of -0.055 to +0.020. The gate of +0.05 was not met, and a smaller gain is not excluded.
- Rich lidar at 0.881 left room for the gate, so this is the one test that could clearly fail.
- The three predictions written before the run all held. The pre-registration is `docs/iterations/nisar_heldout_613590_prereg.md`.
- There is no pad held-out test, because 613590 has no pad annotations.

### 3. Combining radar and lidar

- Repeated cross-validation (10 repeats) gives a gain over lidar of -0.01 to +0.003.
- Block-clustered band tests cut the pad bands that look significant from 229 to 20, and the local-decoy bands from 137 to 0.
- The lidar U-Net was retrained with an isolated sampler so it cannot read held-out pixels. At the F1-selected threshold its recall at IoU 0.3 is 0.872 and its precision is 0.592, which gives an F1 of about 0.705. (An earlier version of this file called 0.888 the F1. That is the original sampler's recall.)
- Fusion with the U-Net score gives NISAR plus U-Net 0.995 against U-Net alone 0.999. This is ceiling-limited. The largest possible gain is +0.001.
- The radar alone separates the U-Net's true pad candidates from its false ones at AUC 0.72. The score alone does this at 0.849. Score plus radar gives 0.831, which is lower. That may be overfitting on a small sample. It does not show the radar has zero information.
- Precision at 70% recall changes by +0.034, with an interval from -0.008 to +0.061. The honest reading is no detectable gain, with a gain of up to about 0.06 not excluded.
- Repeated cross-validation puts the gain near zero, which argues against the +0.05 gate. It does not exclude a smaller benefit.

The radar carries some information by itself. These tests found no reliable extra information beyond lidar. They do not prove the radar is fully redundant.

### 4. What the radar sees

The question was whether returns come from the ground, the tree tops or the vegetation in between. We compared whole-tile 50 m block averages of the radar with lidar and Sentinel-2 optical layers.

Share of HV variance explained (R²). These are descriptive fits. Each is an ordinary least squares fit scored on the same blocks it was fitted on, so they are not validated predictive performance. The lidar terms are canopy height, canopy cover, ground slope and ground elevation, all entered linearly. The optical terms are NDVI for June, September and October, the June-minus-October NDVI change, a moisture index and near-infrared.

| Area | Optical only | Lidar only | Both |
|---|---|---|---|
| Whole tile | 0.52 | 0.04 | 0.54 |
| Closed canopy (cover > 0.8) | 0.22 | 0.17 | 0.33 |
| Open ground (cover < 0.25) | 0.82 | 0.26 | not reported here |

- HV correlates with June NDVI at +0.47 overall, +0.35 in closed canopy and +0.66 in open ground.
- HV also correlates with the June-minus-October NDVI change at +0.39. That change marks leaf-dropping stands.
- HH shows the same pattern, weaker. Optical explains 0.42 and lidar 0.03.
- Shifting the optical by 4 pixels (40 m at 10 m pixels) moves the correlation by only 0.03. This is a weak check. The 50 m block averaging absorbs most of such a shift, so it cannot show that small features are aligned.
- Lidar canopy height explains almost none of the radar variance in this analysis.
- In closed canopy, adding lidar to the optical layers raises R² from 0.22 to 0.33. That is a meaningful descriptive contribution. It is not proof of ground scattering.
- Ground elevation was the strongest lidar term in closed canopy. The follow-up audit (section 5) shows this was terrain illumination. Adding the simulated terrain gain to the lidar layers lifts held-out R² in closed canopy from 0.07 to 0.57. An earlier version of this file guessed it meant stand type. That guess was wrong.

What this supports: HV co-varies more with optical vegetation indices than with lidar canopy height, at 50 m, on this tile.

What it does not support:
- It does not show that the return comes mostly from vegetation or that the radar cannot see the forest ground. The ground and canopy contributions were not separated, and correlation with optical does not give an energy split. Shared moisture, land cover and terrain effects can create the same association.
- It does not show the radar ignores canopy height in general. L-band HV is known to saturate at moderate biomass. Mature hardwood stands are probably past that point, so height would explain little inside closed canopy whatever the scattering mechanism. The height result may be saturation, not a response to vegetation type.
- The whole-tile lidar R² of 0.04 was checked. On unseen 1 km squares, canopy cover alone gives a negative R² with both a linear and a gradient-boosting fit. A nonlinear cover effect is not hiding in it.
- Optical NDVI also carries an open-versus-forest signal, so "optical only" partly measures structure.
- June 2026 minus October 2025 mixes seasonal and interannual differences.

### 5. Follow-up checks (2026-10-27, after two outside reviews)

Tables, scripts and reproduce commands: `docs/iterations/nisar_followup_checks_9t.md`. Scores here are averaged over repeated cross-validation runs. Near-chance scores read slightly higher than single runs.

**Where lidar is weak (pads, 633 against matched decoys).**

| Subset | Pads | Rich lidar | NISAR + rich lidar, gain (95% interval) |
|---|---|---|---|
| U-Net missed | 47 | 0.907 | +0.001 (-0.014, +0.026) |
| In canopy (cover > 0.5) | 277 | 0.980 | 0.000 (-0.007, +0.006) |
| Lidar-weak quartile | 159 | 0.880 | +0.015 (+0.003, +0.036) |

- The lidar-weak gain is one of six subsets and is 30% of the gate. In the local-decoy design it is +0.003 (-0.026, +0.029). A control with shuffled radar rows gives -0.001. The tile-wide design rewards place (below), so this gain is not credited to the radar.
- A first definition of "missed" at probability 0.3 was wrong. Neighbouring pads merge into one blob and fall below IoU 0.3, so 30% looked missed. At 0.5, 7.4% are missed.
- Pads that lidar cannot see at all are not in the labels, so none of this covers them.

**Radar against optical, no lidar features.**

| Feature set | Against matched decoys (633) | Against other clearings (60) |
|---|---|---|
| NISAR all bands | 0.622 | 0.795 |
| Sentinel-2 | 0.840 | 0.781 |
| NISAR + Sentinel-2 | 0.834 | 0.809 |
| NISAR six plain backscatter layers | 0.462 | 0.524 |

- Radar adds nothing to Sentinel-2 (-0.006, interval -0.020 to +0.020, and +0.029, interval -0.046 to +0.118).
- Against clearings the two tie. 60 pads cannot separate them.
- The radar's 0.80 comes from its texture bands. The plain backscatter layers score near chance.
- The matched-decoy design still uses lidar cover and slope to choose decoys.

**Why the tile-wide score is 0.64.**

| Decoy distance | 100 to 500 m | 1 to 1.5 km | 2.5 to 3.5 km | over 3.5 km |
|---|---|---|---|---|
| NISAR | 0.44 | 0.53 | 0.68 | 0.71 |
| Sentinel-2 | 0.72 | 0.60 | 0.85 | 0.91 |
| Map x/y | 0.38 | 0.65 | 0.92 | 0.96 |

- Pads sit in particular parts of the tile. Far ground differs in stand type and setting. The radar sees that difference, not the pad.
- Sentinel-2 explains at least as much at every distance. The radar adds nothing to it.

**Terrain and registration.**
- The radar set already holds terrain-flattened HH and the simulated terrain gain for each track. Adding flattened HV changes no score by more than 0.002.
- A test of registration from lidar objects (9,592) against steady bright radar points found no peak. This neither confirms nor refutes the 10 m residual. The object set is probably mostly shrubs and tree edges. No shift was applied.
- In closed forest the terrain gain explains most of raw HV (held-out R² 0.57 with lidar). After flattening, lidar explains 0.19, optical 0.16 to 0.24, both 0.35 to 0.43. More than half stays unexplained.

**Optical audit.**
- The scene metadata confirm the reflectance offset is already removed (boa offset applied, all three scenes). The June scene has no cirrus. Same-year optical gives the same R² as the version with October.
- On unseen 1 km squares, optical explains 0.44 to 0.55 of HV over the tile. Lidar layers alone explain under 0.02. The optical lead holds.

**Pad test on a second tile.** Blocked by missing labels. 161 candidates for review are in `data/613590/results/nisar/nisar_pad_review_candidates_613590.gpkg`. The plan is fixed in section 6 of the iteration doc.

### 6. Signal quality

- The data are single-look speckle (equivalent number of looks about 0.85). Neighbouring pixels correlate at 0.38.
- The impulse response is 3.9 m in slant range by 5.7 m in azimuth.
- Occupied bandwidth is 31 to 33 MHz against a nominal 40 MHz. We found no radio interference.
- Per-date HV offsets have a standard deviation of 1.1 to 1.8 dB between dates. Normalising each date changes no AUC by more than 0.015.
- Line-of-sight motion was kept exploratory. Removing it changes AUC by -0.005 and +0.010.

## Caveats

- The tile-wide pad score (0.64) is a place effect (distance bands, section 5). It should not be quoted as a NISAR result.
- Pad and clearing tests have small samples (about 60 pads in the clearing test, 47 pads the U-Net missed).
- The weak-lidar subsets are six looks at the same data with no multiplicity correction.
- The optical comparison uses one scene per season. September NDVI is saturated (above 0.95) and carries no information, so the signal comes from June.
- The radar and optical both reflect vegetation. The comparison shows correlation, not cause.
- The data are beta and provisional, with per-track brightness offsets.
- There is no calibrated HV noise floor.
- The annotations were drawn from lidar, and the lidar dates to 2019. The tests show recovery of lidar-visible features. They are weaker evidence about independently verified wells or features changed since 2019.
- A registration error of about 10 m is two radar pixels. It is substantial for pit-scale targets, and we have not corrected it. The point-target test to confirm it was null and uninformative.
- Several tests are ceiling-limited. The pad clearing test (lidar 0.99) and the U-Net fusion (0.999) could not have met the +0.05 gate.

## Mistakes caught along the way

- The pad and pit scores were first inflated by decoys that differed from targets in more than location. The corrected design is the one reported here.
- The U-Net sampler could read held-out pixels. It was fixed and the fusion rerun.
- `skew7` and `kurt7` were not true window moments. They were fixed, and the headline moved by 0.005 or less.
- In the optical test we first masked thin cirrus, which removed most of the September scene. We then subtracted a reflectance offset these scenes do not use, which pushed NDVI above 1. Both were fixed.
- We first said the radar "follows the terrain" and then that it "looks like trees". Neither held up against the numbers.
- The first version of this file called 0.888 the isolated U-Net's F1. It is the original sampler's recall. The isolated F1 is about 0.705.
- A first "U-Net missed" definition at probability 0.3 counted merged blobs as misses (30% missed). It was redone at 0.5 (7.4%).
- We guessed that the ground-elevation term in closed forest meant stand type. The audit shows it was terrain illumination.

## Not done

The seven follow-up checks are run (section 5). What remains:

- A pad held-out test on a second tile with independently verified pads. It needs labels. Review the 161 candidates in `data/613590/results/nisar/nisar_pad_review_candidates_613590.gpkg`.
- A registration estimate that works. The lidar-object test was null. It needs surveyed structures or corner reflectors.
- A larger set of pads against other clearings. At 60 pads, radar and Sentinel-2 tie.
- Pit decoys with footprint matching alone and incidence matching alone.
- Pads that lidar cannot see at all (the labels come from lidar), and old or revegetated pads with known ages.
- A split of ground and canopy return. R² does not give one.
- A calibrated HV noise floor, and line-of-sight motion as connected-network displacement.
- Change detection through time, and spring dates (flooded-forest double bounce).
- Any S-band data.

## Files

- Methods and file list: `NISAR_METHODS.md`
- All check tables: `docs/iterations/nisar_checks_9t.md`
- Follow-up checks, all tables and reproduce commands: `docs/iterations/nisar_followup_checks_9t.md`
- Follow-up results: `data/9t/results/nisar/nisar_pad_weak_lidar_auc_9t_slc_cv5_iso_tau0p50.csv`, `nisar_pad_radar_vs_optical_auc_9t_slc.csv`, `nisar_pad_distance_bands_auc_9t_slc.csv`, `nisar_pit_fixed_subset_auc_9t_slc.csv`, `nisar_vs_optical_heldout_r2_9t_slc.csv`, `nisar_registration_points_shift_9t_slc.csv`
- Follow-up scripts: `notebooks/wellsight_v2/s5_eval/_nisar_weak_lidar_9t.py`, `_nisar_radar_vs_optical_pads_9t.py`, `_nisar_pad_distance_bands_9t.py`, `_nisar_pit_fixed_subset_9t.py`, `_nisar_vs_optical_heldout_9t.py`, `_nisar_hvflat_9t.py`, `_nisar_registration_points_9t.py`
- Held-out pre-registration: `docs/iterations/nisar_heldout_613590_prereg.md`
- Radar against canopy and terrain: `data/9t/results/nisar/nisar_vs_canopy_corr_9t_slc.csv`
- Radar against optical: `data/9t/results/nisar/nisar_vs_optical_corr_9t_slc.csv`
- Figure, radar against canopy height: `data/9t/results/nisar/figures/nisar_vs_canopy_hexbin_9t_slc.png`
- Figure, one 1 km window (NDVI, HV, canopy height, hillshade): `data/9t/results/nisar/figures/nisar_vs_optical_window_9t_slc.png`
- Cross sections: `data/9t/results/cross_sections/figures/cross_section_line4_ground_canopy_nisar_9t.png` and `cross_section_nisar_all_lines_hh_hv_canopy_9t.png` in the same folder
- 613590 held-out pit results: `data/613590/results/nisar/nisar_pit_heldout_*_613590_slc`
- Scripts: `notebooks/wellsight_v2/s5_eval/_nisar_vs_canopy_9t.py`, `_nisar_vs_optical_9t.py`, `_nisar_pad_fp_screen_9t.py`, `_nisar_feat_heldout_9t.py`
- Commits on `reorg/phase4`: `30cccb8` (checks), `80d6a1b` (canopy test), `ed5ba4a` (optical comparison)
