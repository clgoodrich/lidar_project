# Known-well validation (PA DEP O&G vs instance models)

- Ground truth: PA DEP Oil & Gas locations, clipped to 9t extent = **1069 wells**.
- Match radius: detection centroid within **25.0 m** of a known well.

| Model | Detections | Wells matched | Well recall | Median nearest (m) |
|---|---|---|---|---|
| pit_07_maskrcnn | 2979 | 373 / 1069 | 0.35 | 42.0 |
| pit_08_yolo | 3602 | 397 / 1069 | 0.37 | 35.1 |
| pad_05_maskrcnn | 3127 | 521 / 1069 | 0.49 | 26.4 |
| pad_06_yolo | 1291 | 337 / 1069 | 0.32 | 48.3 |
