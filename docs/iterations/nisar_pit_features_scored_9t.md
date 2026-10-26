# NISAR pit-feature scoring (9t)

## Goal
Same test as for pads (`docs/iterations/nisar_pad_features_scored_9t.md`), with pits as the target.

## Setup
- Positives: 723 `pit_outside` rim polygons (median 197 m2, about 8 pixels at 5 m). 495 usable, 488 with matched decoys. Value = median of the up to 9 pixels nearest the centre (no core shrink).
- Decoys: 9-pixel discs (radius 1.5 px), 10 per pit, at least 100 m from any pad, pit, road or DEP well, cover within 0.05 and slope within 1 degree. Same 351 bands, same model, same block CV, same placebo.
- Extra split: the 88 pits at least 50 m from any pad (`auc_farpad`), since pits beside a pad inherit the pad's signature.
- Run: `TARGET=pit python notebooks/wellsight_v2/s5_eval/_nisar_feat_score_9t.py` then `TARGET=pit python notebooks/wellsight_v2/s5_eval/_nisar_feat_model_9t.py`.

## Results
- Single bands: 198 of 348 pass q < 0.05. Strongest matched AUCs 0.74-0.75: local contrast (`spatial:sd15_hh_t090` 0.752, `sd11_hh_t090` 0.741) and dual-pol volume measures (`dualpol:rfdi_t162` 0.741, RVI 0.259 mirrored: pits show less volume scattering). Dual-pol had no signal for pads and is the strongest group for pits.
- Pits at least 50 m from a pad (88): the same bands hold or rise (`sd15_hh_t090` 0.818, `rfdi_t090` 0.773). So it is not just the neighbouring pad.
- Lidar controls: cover 0.51, slope 0.51, roughness 0.43.
- Model, block CV:

| Feature set | AUC |
|---|---|
| lidar baseline (cover, slope, roughness) | 0.858 |
| all NISAR (337 bands) | 0.910 |
| SAR only without geometry | 0.886 |
| NISAR + lidar baseline | 0.949 |
| placebo, decoy against decoy | 0.491 |
| road context only (annotated roads, circular) | 0.999 |

## Interpretation
- The lidar baseline alone separates pits at 0.86, because pits are depressions and roughness is not matched between pits and decoys. NISAR beats it by only 0.052 (gate 0.05, barely passed), and 0.886 without geometry is below the gate.
- NISAR adds information beyond lidar: the pair together reaches 0.949, 0.09 above lidar alone.
- Pits are 1-3 pixels wide and the registration error is about 10 m, so the signal is most likely the pit's surroundings (disturbed ground, wetness, clearing) and not the pit floor.

## Limits
- Pit polygons are the lidar-derived rims. A pit found by lidar roughness is also what the lidar baseline finds, so the comparison favours the baseline.
- Decoys are not matched on roughness. Matching on it would remove most of the baseline and most of what makes a pit a pit.
- One area. Pits beside pads are 82% of the sample.

Result files: `data/9t/results/nisar/nisar_pit_feature_auc_per_band_9t.csv`, `nisar_pit_model_auc_by_set_9t.csv`, `nisar_pit_feature_auc_summary_9t.json`, `nisar_pit_model_summary_9t.json`.
