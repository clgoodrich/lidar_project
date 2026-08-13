# UNet scored with the instance-model metric (apples-to-apples)

Semantic UNet prob rasters thresholded -> connected components -> polygons -> identical `per_instance_metrics` (greedy 1:1 matching + precision as of 2026-07-02).


## Pits (65 test instances)

Threshold selected on VAL (F1@0.3); test scored once at the frozen threshold.

| Threshold (val sweep) | # pred | val F1@0.3 | val R@0.3 | val P@0.3 |
|---|---|---|---|---|
| 0.3 | 1184 | 0.000 | 0.00 | 0.000 |
| 0.5 | 932 | 0.002 | 0.02 | 0.001 |
| 0.7 **(chosen)** | 1105 | 0.063 | 0.59 | 0.033 |

**Test @ thr=0.7** (1:1 matching): R@0.3 = 0.55, P@0.3 = 0.033, F1@0.3 = 0.062, R@0.5 = 0.32, mean best IoU = 0.314, loose R@0.3 = 0.55 (legacy definition), n_pred = 1105.

## Pads (93 test instances)

Threshold selected on VAL (F1@0.3); test scored once at the frozen threshold.

| Threshold (val sweep) | # pred | val F1@0.3 | val R@0.3 | val P@0.3 |
|---|---|---|---|---|
| 0.3 | 1564 | 0.068 | 0.56 | 0.036 |
| 0.5 **(chosen)** | 1222 | 0.138 | 0.90 | 0.074 |
| 0.7 | 904 | 0.100 | 0.50 | 0.055 |

**Test @ thr=0.5** (1:1 matching): R@0.3 = 0.91, P@0.3 = 0.070, F1@0.3 = 0.129, R@0.5 = 0.76, mean best IoU = 0.595, loose R@0.3 = 0.92 (legacy definition), n_pred = 1222.
