# NISAR outstanding checks, run on 9t and 613590 (2026-10-27)

This closes the list in `docs/iterations/BACKLOG.md` ("NISAR outstanding checks after the 2026-10-26 reviews"). It follows `nisar_corrected_rescoring_9t.md`. The headline did not change. **NISAR does not add to lidar on this tile, in any design tested.** Several checks also sharpen what NISAR does and does not see.

## Summary by backlog item

| # | Item | Result |
|---|---|---|
| 1 | Shape-matched decoys, local-incidence matching | NISAR still adds nothing to lidar. The pit NISAR score falls from 0.829 to 0.568. |
| 2 | Shifted pseudo-pad placebo | Pseudo-pads are found by map coordinates (0.89) and not by NISAR (0.50). |
| 3 | Confuser clearings | NISAR separates pads from other clearings (0.80). Lidar separates them better (0.99). NISAR adds nothing. |
| 4 | DEP status split | No status group shows a NISAR signal beyond lidar. Only 9 pads sit on orphan-list wells, too few to score. |
| 5 | Frozen run on 613590 | All three pre-registered predictions held. Gate failed. Pits only. |
| 6 | Repeated CV, cluster-aware tests | Gain of NISAR over lidar is -0.01 to +0.003 with sd 0.004 to 0.012. Clustered tests cut the significant pad bands from 229 to 20. |
| 7 | U-Net retrain with whole-window isolation, fusion | Isolation costs 2 points of recall. NISAR adds nothing to the U-Net (0.995 against 0.999). |
| 8 | Effective looks, impulse response, RFI, noise floor, per-date normalisation | Single-look speckle, no RFI, normalisation changes nothing. |
| 9 | Precision at fixed recall, pad false-positive screen | NISAR alone separates true from false candidates (0.72) but adds nothing to the detector score. |
| 10 | LOS motion | Kept as exploratory. It carries no weight in any result. |

## Fixes made on the way

- `skew7` and `kurt7` were not window central moments. The first version subtracted the local mean of one pixel only. They are now true window moments (`_nisar_feat_spatial_9t.py`). The spatial product was rebuilt for 9t and 613590. Every design was re-scored. All headline numbers moved by 0.005 or less (pads, decoys anywhere: all NISAR 0.635 to 0.640, local decoys 0.476 to 0.479, pits 0.832 to 0.829).
- Before that change the refactored scorer was run once in its old default mode and reproduced the committed per-band file exactly.
- One definition of the output tag (`C.suffix`) and one definition of the model (`C.fit_predict`) now serve every script.
- A scorer run now saves the pixel footprints of its samples. `C.sample_values` reads a new raster on exactly those pixels.

## 1. Shape-matched and incidence-matched decoys (`SHAPE=1 INC_MATCH=1`)

Each decoy now has the exact pixel footprint of its pad, translated onto matched ground. Decoys are also matched, within 0.5 dB, on the terrain illumination gain of each track (`geometry:sim_db`, a function of the local incidence angle). Matching uses the footprint pixels, not a disc.

| Model AUC | Pads, decoys anywhere (516 pads) | Pads, local decoys (103 pads) | Pits (173) |
|---|---|---|---|
| rich lidar baseline | 0.907 | 0.893 | 0.933 |
| map x/y only | 0.877 | 0.498 | 0.920 |
| all NISAR | 0.657 | 0.490 | 0.568 |
| NISAR + rich lidar baseline | 0.907 | 0.908 | 0.910 |

- Fewer targets survive the stricter match (516 of 645, 103 of 645 and 173 of 723).
- Pits: the NISAR score drops from 0.829 to 0.568. Two things changed at once, the decoy match and the pit subset (173 of 723 pits against 489). I did not separate them.
- Pads: little changes. The gate fails in every column.
- Files: `data/9t/results/nisar/nisar_{pad,pit}_model_auc_by_set_9t_slc_shape_inc[_local1500].csv`.

## 2. Shifted pseudo-pad placebo (`PLACEBO=1`)

The "pad" is the pad's footprint moved 150 to 300 m onto matched ground (at least 50 m from pads, pits and wells, 15 m from roads, because the strict 100 m exclusion left only 30 of 645 pads a site). The decoys are those of the ordinary design, never within 60 m of the pseudo-pad.

| Model AUC | Decoys anywhere (572 pseudo-pads) | Local decoys (257) |
|---|---|---|
| map x/y only | 0.890 | 0.566 |
| rich lidar baseline | 0.620 | 0.528 |
| all NISAR | 0.504 | 0.536 |
| NISAR + rich lidar baseline | 0.639 | 0.570 |

- Pseudo-pads are found by location (0.89), higher than real pads (0.815). Location is a strong confound.
- NISAR does not find them (0.50). So the 0.64 that NISAR reaches on real pads against tile-wide decoys is not a neighbourhood effect.
- With local decoys the pseudo-pads score near chance, as they should.
- The real-pad score against local decoys is also at chance (0.479). The two designs disagree, and the block confidence intervals (about 0.07 wide each side) overlap. I could not resolve this. It is not a subset effect: the pads kept by the local design score 0.626 and the others 0.653 in the tile-wide design (`nisar_pad_subset_effect_auc_9t_slc.csv`).

## 3. Confuser clearings (`CONFUSER=1`)

Decoys come only from other clearings: connected open ground (smoothed canopy cover under 0.30) of at least 1,000 m², at least 50 m from any annotated pad, pit and well and 15 m from a road. The second run keeps only 30 to 100 m beside roads (`ROAD_NEAR=1`). The clearings include house lots, fields, landings and corridors. They also include any pad that was never annotated.

| Model AUC | Confusers (60 pads) | Confusers beside roads (59 pads) |
|---|---|---|
| rich lidar baseline | 0.990 | 0.990 |
| map x/y only | 0.462 | 0.429 |
| all NISAR | 0.801 | 0.816 |
| NISAR + rich lidar baseline | 0.989 | 0.993 |

- Only about 60 pads have enough matched clearing ground. The result is underpowered.
- NISAR separates pads from other clearings (0.80). The best band is `spatial:grad_hh_t026` (0.81). 40 of 337 SAR bands pass a block-clustered test at q < 0.05.
- Lidar separates them much better. NISAR adds nothing (repeated-CV gain -0.001, sd 0.004).
- Meaning for a false-positive screen: the radar can tell a pad from a field, but the lidar already does.

## 4. DEP status split (`_nisar_feat_status_9t.py`)

Pads take the status of a DEP well within 50 m of the polygon (order orphan, abandoned, active, plugged, other). DEP positions are unreliable, so the split is coarse. Nine pads had an orphan-list well and two an "other" status. Groups with fewer than 10 pads are not scored.

| Pads (decoys anywhere) | n | all NISAR | rich lidar | NISAR + rich |
|---|---|---|---|---|
| all | 633 | 0.640 | 0.917 | 0.921 |
| abandoned | 77 | 0.657 | 0.921 | 0.929 |
| active | 326 | 0.625 | 0.912 | 0.916 |
| plugged | 86 | 0.710 | 0.931 | 0.938 |
| no well recorded | 133 | 0.616 | 0.920 | 0.918 |

With local decoys every group is near 0.5 for NISAR (0.45 to 0.54). No group is a place where NISAR works. Files: `nisar_pad_status_auc_9t_slc[_local1500].csv`.

## 5. Frozen held-out test on 613590 (pre-registered)

The pre-registration, `nisar_heldout_613590_prereg.md`, was committed before any 613590 sample was scored. The model was trained on all 9t pit samples. The 613590 tile has 36 annotated pits and **no annotated pad**, so pads could not be tested.

| Model AUC on 613590 pits (36 pits, 360 decoys, 51 blocks) | AUC (block bootstrap 95%) |
|---|---|
| simple lidar baseline | 0.753 (0.66 to 0.86) |
| rich lidar baseline | 0.881 (0.81 to 0.94) |
| all NISAR (293 bands) | 0.658 (0.47 to 0.82) |
| NISAR + rich lidar baseline | 0.865 (0.78 to 0.93) |

- Prediction 1 (NISAR alone between 0.50 and 0.75): held, 0.658.
- Prediction 2 (gate fails): held. The gain is -0.017 (bootstrap -0.055 to +0.020).
- Prediction 3 (rich lidar above 0.80): held, 0.881.
- Missing on 613590: `amp`, `coherence`, `rainfreeze` (no weather file for that tile) and `subaperture` (script is 9t-only). They were removed from both sides.
- Only 6 usable dates on track 162 there, against 14 on 9t. NISAR alone has a wide interval (0.47 to 0.82).
- Files: `data/613590/results/nisar/nisar_pit_heldout_auc_613590_slc.csv`, `nisar_pit_heldout_summary_613590_slc.json`. Products: `data/613590/derived/nisar_features_5m/` (git-ignored). Build log: `data/613590/results/nisar/nisar_feature_products_run_613590_slc.log`.

## 6. Repeated cross-validation and cluster-aware tests (`_nisar_feat_repeat_9t.py`)

Ten repeats of a shuffled StratifiedGroupKFold (500 m block groups, 250 m buffer). Pooled AUC, mean (sd over repeats):

| Design | rich lidar | all NISAR | NISAR + rich | gain over rich (sd) | block bootstrap of gain |
|---|---|---|---|---|---|
| pads, anywhere | 0.932 (0.005) | 0.622 (0.055) | 0.935 (0.008) | +0.003 (0.004) | -0.006 to +0.018 |
| pads, local | 0.912 (0.014) | 0.505 (0.081) | 0.906 (0.016) | -0.006 (0.009) | -0.018 to +0.019 |
| pads, shape + incidence | 0.896 (0.014) | 0.573 (0.081) | 0.892 (0.023) | -0.004 (0.012) | -0.008 to +0.019 |
| pads, shape + incidence, local | 0.864 (0.013) | 0.445 (0.077) | 0.861 (0.014) | -0.003 (0.007) | -0.014 to +0.016 |
| pads, confusers | 0.988 (0.005) | 0.795 (0.026) | 0.987 (0.005) | -0.001 (0.004) | -0.010 to +0.004 |
| pits | 0.974 (0.003) | 0.789 (0.018) | 0.971 (0.003) | -0.003 (0.002) | -0.007 to +0.001 |

- No gain reaches the 0.05 gate in any repeat of any design. The share of repeats at or above 0.05 is 0 everywhere.
- The all-NISAR AUC varies by 0.05 to 0.08 between repeats. A single fold assignment can move it that much.
- **Cluster-aware band tests.** Whole 500 m blocks are resampled (400 times). Bands passing q < 0.05:

| Design | Naive (all / SAR) | Block-clustered (all / SAR of 337) |
|---|---|---|
| pads, anywhere | 229 / 204 | 20 / 6 |
| pads, local | 137 / 115 | 0 / 0 |
| pads, shape + incidence | 218 / 195 | 20 / 10 |
| pads, shape + incidence, local | 55 / 38 | 0 / 0 |
| pads, confusers | 114 / 91 | 63 / 40 |
| pits | 223 / 197 | 147 / 124 |

The naive tests overstated the pad evidence tenfold. For pits many bands survive clustering, so NISAR does carry pit information. It is the same information the lidar baseline carries.

## 7. U-Net retrained with whole-window isolation, and the fusion redone

**Retrain.** `notebooks/wellsight_v2/s3_train/_pad_unet_iso_cv5.py` is a copy of the pad U-Net CV with one change. A training patch is accepted only if its whole 384 px window lies outside every held-out block, and training patches also avoid the inner-validation blocks (up to 300 redraws). Same folds, seed, architecture, loss, channels and 40 epochs. A test on 400 draws found 0 windows touching a held-out or validation block at full resolution. Run time 157 minutes. Output: `data/9t/models/pad/unet_cv5_iso/` (weights and probability rasters are git-ignored; `pad_cv5_per_fold_9t.csv`, `pad_cv5_recovery_curve_9t.csv`, `pad_cv5_fold_assignment_9t.csv` and `run_pad_unet_iso_cv5_9t.log` are kept).

| Pooled held-out, 650 pads | Original sampler | Isolated sampler |
|---|---|---|
| F1-selected: recall at IoU 0.3 / precision / recall at IoU 0.5 / locate | 0.888 / 0.597 / 0.749 / 0.923 | 0.872 / 0.592 / 0.718 / 0.915 |
| F2-selected: recall at IoU 0.3 / precision / recall at IoU 0.5 / locate | 0.912 / 0.587 / 0.774 / 0.917 | 0.891 / 0.564 / 0.738 / 0.909 |

Isolation costs 1.6 to 2.1 points of recall at IoU 0.3 and about 3 points at IoU 0.5. The leak in the original sampler was real but small. The original numbers were slightly optimistic.

**Fusion** (`_nisar_feat_fusion_9t.py`). The U-Net out-of-fold score is read at every pad core and decoy. The NISAR and lidar models use the U-Net's five folds as their outer folds, so no row is in a test fold of one model and a training fold of the other. Decoys in blocks without a pad have no U-Net fold and are dropped (3,134 of 6,963 rows, 633 pads).

| AUC, tile-wide decoys | Original U-Net | Isolated U-Net |
|---|---|---|
| U-Net score alone | 1.000 | 0.999 |
| rich lidar baseline | 0.980 | 0.980 |
| map x/y only | 0.796 | 0.796 |
| all NISAR | 0.516 | 0.516 |
| U-Net + rich lidar baseline | 0.999 | 0.997 |
| NISAR + U-Net | 0.999 | 0.995 |
| NISAR + U-Net + rich lidar baseline | 0.999 | 0.997 |

The U-Net is at the ceiling even with isolation, so this design cannot show any gain. NISAR does not raise it (0.995 against 0.999). The all-NISAR score here (0.516) differs from the main design (0.640) because the rows are the decoys that sit in pad-bearing blocks. The fusion tests add-on value where the detector is near perfect. The false-positive screen below is the better test.

## 9. NISAR as a false-positive screen, and precision at fixed recall (`_nisar_pad_fp_screen_9t.py`)

Candidates are the connected regions of the isolated U-Net's out-of-fold probability above a threshold, each fold read only inside its held-out blocks. A candidate is a true positive (TP) at IoU 0.3 with an annotated pad. Features are the median of every band over the candidate core. Repeated grouped CV (10 repeats, 500 m blocks). Recall below means the share of TP candidates kept, since a screen cannot recover pads the detector missed.

| | tau 0.3 | tau 0.5 |
|---|---|---|
| candidates (TP / FP, strict FP with no pad overlap) | 1,131 (453 / 678, 555) | 1,042 (598 / 444, 418) |
| detector score, AUC of TP against FP | 0.849 | 0.801 |
| NISAR alone | 0.718 | 0.651 |
| rich lidar texture alone | 0.674 | 0.615 |
| score + NISAR, gradient boosting (gain over score) | 0.831 (-0.018, boot -0.011 to +0.012) | 0.751 (-0.050, boot -0.039 to -0.013) |
| score + NISAR, 10 principal components, logistic (gain) | 0.839 (-0.010, boot -0.011 to -0.003) | 0.785 (-0.016, boot -0.019 to -0.004) |
| score + rich lidar texture, 10 PCs, logistic (gain) | 0.836 (-0.013) | 0.782 (-0.018) |
| precision at 50 / 70 / 90% recall, detector score | 0.764 / 0.687 / 0.613 | 0.840 / 0.776 / 0.712 |
| same, score + NISAR (gradient boosting) | 0.767 / 0.721 / 0.614 | 0.808 / 0.763 / 0.689 |
| same, score + NISAR (10 PCs, logistic) | 0.752 / 0.690 / 0.614 | 0.821 / 0.773 / 0.708 |

- **NISAR alone does separate true from false candidates** (0.72 at tau 0.3, 0.65 at tau 0.5). A candidate that is a real pad looks different in the radar from one that is not.
- **It does not improve the detector.** Every combination scores at or below the detector score alone. The low-capacity combiner (10 components, logistic) loses 0.010 to 0.016, so the loss is not only overfitting by the 337-band boosted model.
- **Precision at fixed recall.** At tau 0.3 the boosted combiner reaches 0.721 at 70% recall against 0.687, a gain of +0.034 with a block-bootstrap interval of -0.008 to +0.061. The low-capacity combiner shows +0.003. At tau 0.5 every combination is at or below the detector. I read the single +0.034 as noise.
- **So the answer to "can NISAR filter the model's probability areas?" is no, on this tile.** The signal NISAR carries about a candidate is already in the detector's score.
- Single bands, block-clustered (q < 0.05): 25 of 365 at tau 0.3 (13 SAR) and 0 at tau 0.5. The circular `context` bands are in that count and are not evidence.
- Files: `data/9t/results/nisar/nisar_pad_fp_screen_{auc,precision,bands,candidates}_9t_slc_cv5_iso_tau0p30.csv` and `..._tau0p50.csv`.

## 8. Signal quality (`_nisar_signal_checks_9t.py`, `_nisar_feat_radnorm_9t.py`)

Measured on the 35 RSLC windows and the lidar-placed stack. Files: `nisar_signal_checks_per_window_9t_slc.csv`, `nisar_signal_checks_by_track_9t_slc.csv`, `nisar_radnorm_*_9t_slc*.csv`.

| Quantity | Track 26 | Track 90 | Track 162 |
|---|---|---|---|
| range sample spacing (m) / azimuth (m) | 3.12 / 4.47 | 3.12 / 4.47 | 3.12 / 4.47 |
| incidence (deg) | 41.3 | 39.0 | 47.3 |
| occupied range bandwidth, HH (MHz) | 31.8 | 32.5 | 31.1 |
| HH speckle CV² (ENL per sample) | 1.16 (0.86) | 1.21 (0.83) | 1.22 (0.82) |
| lag-1 correlation, range / azimuth | 0.39 / 0.38 | 0.38 / 0.38 | 0.40 / 0.36 |
| impulse response, range / azimuth (m) | 3.9 / 5.8 | 3.8 / 5.6 | 3.9 / 5.6 |
| largest range-spectrum spike (dB over its median) | 2.3 | 2.3 | 2.2 |
| azimuth lines above 3 dB of their running median | 0 | 0 | 0 |

- **Looks.** Speckle is single-look (ENL about 0.8 to 0.9 per sample, so CV² a little above 1). There is no multilooking. Neighbouring samples are correlated at 0.38, so a 3 by 3 average holds fewer than 9 independent looks.
- **Bandwidth.** The occupied range bandwidth is 31 to 33 MHz, not 20 MHz. It is below the nominal 40 MHz because of the spectral taper and the half-plateau definition. The reviewer's 20 MHz claim stays not upheld.
- **Impulse response.** About 3.9 m in slant range (5.9 m on the ground at 41 degrees) and 5.7 m in azimuth. Estimated from bright uncontrolled scatterers, so these are upper bounds. A 5 m posting is close to the resolution, not far below it.
- **RFI.** No range-spectrum spikes above 3 dB, no bad azimuth lines. A robust outlier rule flagged 5 of 35 windows (0 to 2 per track), but their spikes are 2 to 2.7 dB. They are the tail of a tight distribution and not interference.
- **Noise floor.** The windows carry no noise-equivalent-backscatter table. Empirically, pad cores sit 5.7 to 7.4 dB above the 1st percentile of the tile in HV and 6.6 to 7.1 dB in HH. At most 1.3% of pad cores fall below the tile's 5th percentile. Pads are not at the darkest ground, but the calibrated floor is not measured.
- **Per-date normalisation.** Date offsets against closed-canopy flat ground are large in HV (sd 1.1 to 1.8 dB per track, one date 4.7 dB low) and moderate in HH (0.3 to 1.0 dB). Normalising each date to that reference changes nothing that matters:

| Model AUC, 15 raw against 15 normalised per-track mean and spread bands | raw | normalised | raw + rich lidar | normalised + rich lidar |
|---|---|---|---|---|
| pads, anywhere | 0.479 | 0.472 | 0.923 | 0.923 |
| pads, local | 0.426 | 0.440 | 0.918 | 0.912 |
| pits | 0.631 | 0.624 | 0.967 | 0.968 |

The mean single-band strength (|AUC - 0.5|) is 0.032 against 0.029 (pads), 0.033 against 0.032 (local) and 0.065 against 0.066 (pits).

## 10. LOS motion

The LOS-motion bands are not measured displacement. A rebuild as connected-network displacement was not attempted. They stay labelled exploratory. They carry no weight: removing the group changes the all-NISAR AUC by -0.005 (decoys anywhere) and +0.010 (local decoys), and the group alone scores 0.539 (pads, anywhere).

## Limits

- One 4.9 km tile for training and scoring, plus 36 pits on a second tile. No pad could be tested on a second tile.
- The shape, incidence, placebo and confuser designs keep only the pads that find enough matched ground (516, 103, 572, 60 of 645). The results for those subsets are weaker evidence than the main design.
- The placebo and the local design disagree about NISAR on real pads (0.64 against 0.48). Unresolved.
- Registration is still about 10 m and still not independently confirmed.
- Confusers may contain unannotated pads.
- Everything tested is NISAR in single-pass and temporal-mean features at 5 m. Change detection through time, and areas without lidar, are not tested.

## Reproduce

```
export NISAR_STACK=slc
S=notebooks/wellsight_v2/s5_eval
python $S/_nisar_feat_spatial_9t.py                       # rebuild after the skew/kurtosis fix
# design variants: any of SHAPE=1 INC_MATCH=1 PLACEBO=1 CONFUSER=1 ROAD_NEAR=1 LOCAL_M=1500 TARGET=pit
python $S/_nisar_feat_score_9t.py; python $S/_nisar_feat_model_9t.py
python $S/_nisar_feat_repeat_9t.py                        # repeated CV, clustered band tests
python $S/_nisar_feat_status_9t.py                        # pads only
python $S/_nisar_feat_subset_9t.py
python $S/_nisar_feat_radnorm_9t.py build; python $S/_nisar_feat_radnorm_9t.py score
python $S/_nisar_signal_checks_9t.py
# held-out: build 613590 products with NISAR_AREA=613590, score pits there, then
NISAR_AREA=613590 TARGET=pit python $S/_nisar_feat_score_9t.py; python $S/_nisar_feat_heldout_9t.py
```
