# NISAR feature study, corrected and re-scored (9t, 2026-10-26)

> Update 2026-10-27: `skew7` and `kurt7` were fixed and every design re-scored. All numbers below moved by 0.005 or less (pads, decoys anywhere: all NISAR 0.640; local decoys 0.479; pits 0.829; placebo 0.482, 0.527, 0.495). The follow-up checks are in `nisar_checks_9t.md`. Most of the limits listed at the end of this doc are addressed there.

This doc **supersedes the headline numbers** in `nisar_pad_features_scored_9t.md` and `nisar_pit_features_scored_9t.md`. Those docs keep their first-pass numbers, marked as superseded.

## Why re-run

Two outside reviews arrived on 2026-10-26: an outside methods reviewer, and a Codex audit (`docs/iterations/nisar_methodology_audit_20261026.md`). I checked their claims against the code and data first. These held:

| Claim | Check | Effect |
|---|---|---|
| About half the pads land in the wrong CV block (median of flattened pixel indices) | 13.9% of the 649 pads sat in a different block from their centroid's | Block labels now come from the pad centroid. |
| Pads are not scored on 49 pixels | 76% of pads at the 5 m core have fewer than 49 pixels (median 35). At the 15 m core the median is 9. | Each pad is scored on the largest of 9, 16, 25, 36, 49 pixels that fits its core. Its decoys use the same count, and the same finite-value rule. |
| Bad dates are not removed on the GSLC stack | Track 26 on 2026-09-08 (listed in `BAD_DATES`) was in every GSLC product. | `usable_stack()` drops `BAD_DATES` on every stack. |
| The study runs on NASA's GSLC, not the lidar-placed stack | Default `STACK` is `gslc`. | All 12 products rebuilt with `NISAR_STACK=slc` (tag `_9t_slc`, 8 / 11 / 14 dates per track). Sub-aperture already used lidar placement, so its file was copied under the `_slc` tag. |
| Preprocessing uses labels before the split | Band filter and imputation ran on all rows. | Both now run inside each training fold (`C.oof_probs`). |
| Train and test neighbours share footprints | Unbuffered GroupKFold. | Training rows within 250 m of any test row are dropped. |
| Height product unit bug, wrong wavelength | `ak = abs(k) * 0.01` where `/ 0.01` was meant. Wavelength 0.2384 m, indexed frequency 1.239 GHz gives 0.2420 m. | Both fixed. The rebuilt product then failed the plausibility check (forest median height 0.1 to 0.8 m, sign forced per track), so it is **dropped from the scored set**. |
| The lidar baseline cannot fail (matched on its own variables) | True by construction. | Added a **rich lidar baseline** (26 bands): the same operators as the SAR spatial product (local sd at 3, 7, 11, 15 px, gradient, difference of Gaussians, mean at 15 px) run on lidar cover, slope and roughness, plus forest fraction at 75 m and 155 m. |
| A coordinate-only classifier beats NISAR | Reproduced in the audit (0.738 against 0.713). | Added a **map x/y only** control to every model run. |

Reviewer claims **not** upheld: the range bandwidth is 40 MHz (not 20 MHz), so the 5 m posting is close to the true resolution.

## Design of the corrected run

- Scorer `_nisar_feat_score_9t.py`: variable-size cores and decoys, block from centroid, `lidartex` bands, heightresid dropped.
- Model `_nisar_feat_model_9t.py`, ablation `_nisar_feat_ablate_9t.py`, twins `_nisar_feat_hhhv_9t.py`: all use `C.load_samples` and `C.oof_probs` (`_nisar_feat_common.py`).
- Run with `NISAR_STACK=slc`. Outputs carry `_9t_slc` in their names, so the first-pass files are intact.
- Gate: NISAR + rich baseline must beat the rich baseline by 0.05. The summary JSONs hold `passes_gate_over_rich_baseline` and `passes_gate_over_rich_plus_xy`.

## Results (model AUC, 5-fold block CV, 250 m buffer)

| Feature set | Pads, decoys anywhere (633 pads) | Pads, decoys 100 m to 1,500 m away (297 pads) | Pits (489) |
|---|---|---|---|
| simple lidar baseline (cover, slope, roughness) | 0.465 | 0.435 | 0.849 |
| **rich lidar baseline** | **0.917** | **0.923** | **0.968** |
| **map x/y only** | 0.815 | 0.517 | 0.955 |
| rich baseline + map x/y | 0.942 | 0.917 | 0.988 |
| **all NISAR** | **0.635** (0.55 to 0.71) | **0.476** (0.40 to 0.55) | **0.832** (0.77 to 0.88) |
| NISAR without geometry (SAR only) | 0.624 | 0.483 | 0.781 |
| NISAR + simple baseline | 0.633 | 0.462 | 0.871 |
| NISAR + rich baseline | 0.921 | 0.904 | 0.967 |
| NISAR + rich baseline + map x/y | 0.930 | 0.890 | 0.987 |
| placebo, decoy against decoy | 0.477 | 0.519 | 0.498 |
| road context (circular) | 0.996 | 1.000 | 0.999 |

Gate over the rich baseline: not passed in any column.

**Fold spread** (mean of the five fold AUCs, spread): all NISAR 0.600 (0.107), 0.472 (0.081), 0.837 (0.059). Folds differ a lot, so the pooled AUC hides instability.

### What changed the old numbers

Re-scoring the **old GSLC samples** with only the new CV (buffer and fold-local preprocessing):

| | Old pipeline, old CV | Old samples, new CV | Corrected data and new CV |
|---|---|---|---|
| Pads, decoys anywhere, all NISAR | 0.815 | 0.699 | 0.635 |
| Pads, local 1,500 m decoys, all NISAR | 0.713 | 0.587 | 0.476 |

The new CV accounts for about half to two thirds of the drop (64% and 53%). The corrected data (SLC stack, bad date removed, per-pad pixel counts, block fix) accounts for the rest. Files: `data/9t/results/nisar/nisar_pad_model_auc_by_set_9t_oldsamples_newcv.csv` and `..._9t_local1500_oldsamples_newcv.csv`. The old-samples runs still carry the block bug in their group labels, so they are a bound, not a clean attribution.

### Other corrected results

- **HH against HV twins** (89 pairs). Pads, local decoys: strength HH 0.037, HV 0.035, signed-rank p 0.47. HH twins 0.449, HV twins 0.478, both 0.469 (below chance). Pits: strength HH 0.073, HV 0.050, p 5.7e-06 (bands are correlated, so p is optimistic). HH twins 0.783, HV twins 0.705, both 0.788. Shuffled-label null (within block): 0.444 (pads, local) and 0.754 (pits).
- **Ablation, pads, decoys anywhere** (all NISAR 0.635): removing any group changes AUC by 0.012 or less. HH-only 0.601, HV-only 0.575, ascending-only 0.665, descending-only 0.478.
- **Ablation, pads, local decoys** (0.476): removing spatial costs 0.036, texture 0.012. Every other change is within noise.
- **Ablation, pits** (0.832): removing geometry costs 0.051, spatial 0.014. HH-only 0.788, HV-only 0.726.
- **Single bands, pads, local decoys.** 135 of 365 bands pass q < 0.05, but the p-values treat decoys as independent and are optimistic (audit finding). The strongest are lidar texture (`lidartex:slope_sd3` 0.933, `rough_sd3` 0.916). The best SAR bands are about 0.63 to 0.66 (`texture:ent_db_t026`, `spatial:grad_hh_t026`).
- **Pad-area terciles** (decoys anywhere): 0.591, 0.659, 0.657. No longer a decreasing pattern.

## Interpretation

- **Pads.** NISAR does not separate annotated pads from ground in their own neighbourhood (0.476, chance). With decoys anywhere it reaches 0.635, below map coordinates alone (0.815). The earlier "signal" of 0.71 to 0.88 was location, optimistic CV and a pipeline that mismatched sample sizes. Adding NISAR to the rich lidar baseline does not help (0.921 against 0.917, 0.904 against 0.923).
- **Pits.** NISAR alone reaches 0.832, but coordinates alone reach 0.955 and the rich lidar baseline 0.968. NISAR adds nothing to them (0.967, 0.987). Pits sit at pads, so location predicts them.
- **Lidar sees pads trivially.** Local slope variation at 3 pixels scores 0.93. Pads are smooth graded surfaces and the decoys are not matched on that.
- **HH.** There is no HH advantage for pads. For pits there is a modest one, but pits are not separable from location once coordinates are in the model.
- **What this does not show.** It does not show NISAR can never help. It shows that in this 4.9 km tile, with this feature set and 5 m posting, NISAR does not add to lidar or location for pad or pit detection.

## Limits that remain

- Local decoys keep 297 of 645 usable pads (those with at least 10 matching candidates within 1,500 m). The subset is not random.
- The coordinate control is a point estimate. It is not a tested difference.
- Pad-size matching is per-bin on pixel count, not on shape. A translated target footprint, as the reviewer proposed, is not built.
- Decoys are not matched on local incidence angle.
- No shifted pseudo-pad placebo, no confuser set (other clearings), no DEP-status split, no held-out area (613590), no repeated CV with a spread over seeds.
- Sample-level inference is still unreliable: single-band p-values and the signed-rank test across bands assume independence.
- The registration is about 10 m and not independently confirmed.
- **The fusion with the pad U-Net** was redone on 2026-10-27 with an isolated retrain (`nisar_checks_9t.md`, section 7). NISAR adds nothing to it.
- The LOS-motion bands are not measured displacement (zero-filled steps, disconnected gaps). Treat them as exploratory predictors. Season and processing release are confounded (all winter acquisitions are beta, all summer ones provisional).
- `skew7` and `kurt7` were moments of a demeaned residual image, not window central moments. Fixed 2026-10-27.

## Files

- Corrected results: `data/9t/results/nisar/nisar_pad_model_auc_by_set_9t_slc.csv`, `nisar_pad_model_auc_by_set_9t_slc_local1500.csv`, `nisar_pit_model_auc_by_set_9t_slc.csv`, with `..._summary_...json` beside each.
- Ablations and twins: `nisar_{pad,pit}_ablation_auc_9t_slc[_local1500].csv`, `nisar_{pad,pit}_hhhv_{pairs,models}_9t_slc[_local1500].csv`.
- Single-band: `nisar_{pad,pit}_feature_auc_per_band_9t_slc[_local1500].csv`.
- Samples (git-ignored): `data/9t/derived/nisar_features_5m/nisar_{pad,pit}_samples_9t_slc[_local1500].npz`.
- Rebuilt products (git-ignored): `data/9t/derived/nisar_features_5m/nisar_feat_<product>_9t_slc_5m.tif`.

## Reproduce

```
export NISAR_STACK=slc
for p in dualpol texture spatial amp_trend temporal events geometry los_motion coherence rain_freeze road_context height_resid; do
  python notebooks/wellsight_v2/s5_eval/_nisar_feat_${p}_9t.py; done
python notebooks/wellsight_v2/s5_eval/_nisar_features_vs_flatness_9t.py
# sub-aperture: run once without NISAR_STACK, then copy nisar_feat_subaperture_9t_5m.tif to ..._9t_slc_5m.tif
python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py     # LOCAL_M=1500 for the local design, TARGET=pit for pits
python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_ablate_9t.py
python notebooks/wellsight_v2/s5_eval/_nisar_feat_hhhv_9t.py
```
