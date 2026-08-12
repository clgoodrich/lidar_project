# Roads Studio

An interactive knob board for road extraction. Pick a block and a model, turn
the parameters, watch the roads redraw over the hillshade, and export the layer
you like to GeoPackage for QGIS. No retraining — it tunes the *post-processing*
of an existing road-probability raster.

## Run

Double-click **`Roads Studio.bat`** (repo root), or:

```
python -m roads_studio.main
```

Opens at <http://127.0.0.1:8095/>. Close the console window to stop.

## What the knobs do

The engine is the existing pipeline in
`notebooks/wellsight_v2/s5_eval/_road_optimize.py`
(`enhance -> threshold -> path-open -> skeleton -> prune -> reconnect -> island`).

| Knob | Effect |
|---|---|
| **Block / Model** | which road-probability raster to extract from (613590 has all sweep variants) |
| **Preview res** | Half is snappy (~1-2 s) and ~faithful; export is always full-res |
| **Suppress drainage** | masks pixels where the drainage head out-scores the road head |
| **Ridge enhance** | Sato/Frangi/Meijering vesselness to sharpen thin linear roads |
| **Threshold** | global cutoff, Otsu (auto), or hysteresis (low seeds + high grow) |
| **Slope gate** | drop road pixels on slopes steeper than N degrees |
| **Path-open** | erase blobs/texture, keep pixels on a straight run of >= N m |
| **Min blob area** | remove connected clumps smaller than N m^2 |
| **Skeleton** | centerline method (zhang / lee / medial axis) |
| **Prune spurs** | trim dead-end twigs shorter than N m |
| **Reconnect gaps** | bridge broken roads along least-cost paths (lcp / mst) |
| **Drop short networks** | delete whole road components shorter than N m |

Area/length knobs are in **map units** (m / m^2), so a half-res preview behaves
like the full-res export.

## Export

Writes to `roads_studio/exports/roads_<block>_<model>_<timestamp>.{gpkg,shp}`
plus a `.cfg.txt` sidecar recording the exact knob settings, so any layer is
reproducible. Load the `.gpkg` in QGIS.
