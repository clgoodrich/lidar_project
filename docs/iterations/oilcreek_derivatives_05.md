# oilcreek_22tile_05 — Oil Creek DEM derivatives (0.5 m)

**Status:** built 2026-06-03 (`build/_build_derivatives.py`). Terrain-derivative stack for the 22-tile Oil Creek mosaic at 0.5 m/px, intended as inference inputs for the 9t-trained pit/pad models.

**Goal.** Generate the same family of DEM derivatives used on 9t for the Oil Creek study area, so the trained Mask R-CNN / YOLO models can be run there.

**Source / params.** `_build_derivatives.py` over the Oil Creek tile set, `--suffix oilcreek_22tile_05`, `--res 0.5`, `--crs EPSG:6346`. Output dir: `data/derivatives/tiles/oilcreek_22tile_05/`.

**Derivatives produced (each as a single mosaic GeoTIFF, `*_oilcreek_22tile_05.tif`):**
- Elevation: `dem`, `dsm`, `chm`
- Slope: `slope`
- Local relief: `lrm_3`, `lrm_5`, `lrm_11`, `lrm_25`, `local_relief_10`
- Position: `tpi_05`, `tpi_15`, `tpi_25`, `tpi_grad_mag`, `tpi_grad_dir`
- Openness: `openness_pos`, `openness_neg`
- Texture: `roughness_5`
- Other: `hillshade`, `ground_density`, `intensity_ground`
- QA: `tile_overview_oilcreek_22tile_05.png`

## ⚠️ Gap blocking inference: `roughness_11`

The 9t feature stack the models consume is the 7-band set
`(lrm_25, lrm_5, slope, tpi_05, openness_pos, openness_neg, roughness_11)`.
The Oil Creek build emitted **`roughness_5`, not `roughness_11`** (`_build_derivatives.py` emits roughness at radius 5). Before Oil Creek inference can run, that one band must be generated and the 7-band `features_oilcreek_22tile_05.tif` stack assembled with matching channel order, then z-scored.

**Remaining steps to enable Oil Creek inference:**
1. Generate `roughness_11_oilcreek_22tile_05.tif`.
2. Stack the 7 channels in the canonical order into `features_oilcreek_22tile_05.tif`.
3. Run `_pit_maskrcnn_infer.py` / `_pad_maskrcnn_infer.py` pointed at the Oil Creek stack (the checkpoints carry their own `mu`/`sd` from 9t — confirm those normalization stats transfer acceptably, or recompute per-region).

See [[BACKLOG]].
