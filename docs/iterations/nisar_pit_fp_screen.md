# Can NISAR separate the pit detector's true positives from its false positives? (9t, 2026-10-20)

## Goal

Find a use for the NISAR stack that helps the lidar work. The pit detector (U-Net v2) has 104
scored detections on 9t, 69 true positives and 35 false positives. If NISAR backscatter differs
between the two groups, it can screen false positives at no cost.

## Inputs

- Detections: `data/9t/results/instance_precision/scored_pit_unet_v2.gpkg`, layer `detections`
  (columns `score`, `verdict`). Reprojected from EPSG:6346 to EPSG:32617.
- Stack: lidar-placed 9t GSLC stack (`--slc`), no registration shift, 34 dates over 3 tracks
  (the new October 2026 windows are not in the lidar-placed index yet).
- Metrics: the eight seasonal backscatter metrics of `nisar_gslc_stack_pad_pit_seasonal_9t.md`
  (HH and HV, leaf-off fall, winter, leaf-on, leaf-on minus fall), detection minus its 10-30 m ring,
  dB, mean over tracks.
- 90 of 104 detections have all metrics (61 TP, 29 FP). The rest have a ring with under 10 valid pixels.

## Method

Script: `notebooks/wellsight_v2/s5_eval/_nisar_pit_fp_screen_9t.py`.
- AUC of each metric for TP against FP, with a label-permutation p (5,000 shuffles, two-sided).
- The detector's own score as a scale reference.
- Repeated stratified 5-fold CV (20 repeats) of a logistic regression, score alone against score
  plus the eight NISAR metrics. The statistic is the CV AUC gain. 200 label shuffles of the whole
  procedure give its null.
- NISAR is not an input to the detector, so training does not leak into the test.

## Results

`data/9t/results/nisar/nisar_pit_fp_screen_auc_9t_slc.csv`,
`nisar_pit_fp_screen_summary_9t_slc.json`, `nisar_pit_fp_screen_per_detection_9t_slc.csv`.

| Metric | AUC (TP over FP) | Permutation p |
|---|---:|---:|
| Detector score | 0.849 | 0.0002 |
| HH leaf-off fall | 0.559 | 0.37 |
| HH winter | 0.596 | 0.15 |
| HH leaf-on | 0.553 | 0.42 |
| HH change, leaf-on vs fall | 0.481 | 0.77 |
| HV leaf-off fall | 0.587 | 0.19 |
| HV winter | 0.457 | 0.51 |
| HV leaf-on | 0.548 | 0.46 |
| HV change, leaf-on vs fall | 0.419 | 0.21 |

Cross-validated AUC: score alone 0.843, score plus NISAR 0.817. Gain -0.026, permutation p 0.58.
Adding NISAR made the model slightly worse.

## Interpretation

- No NISAR metric separates true from false detections. The best single AUC is 0.60, with p 0.15.
- The detector score alone separates them well (0.85), and NISAR adds nothing to it.
- Power is limited. With 61 TP and 29 FP, an AUC near 0.55-0.60 (the size the 9t pit-versus-decoy
  difference would give) cannot be told from chance. The test shows NISAR does not help at this size
  of effect. It does not show the effect is zero.
- The earlier pit-versus-decoy difference (+0.25 dB HH leaf-off fall) is real but too small to act on
  one detection at a time.

## Reproduce

```
python notebooks/wellsight_v2/s5_eval/_nisar_pit_fp_screen_9t.py --slc
```
