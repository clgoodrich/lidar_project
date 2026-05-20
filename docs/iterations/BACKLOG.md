# Pit / Plat / Road Iteration Backlog

Things to explore in future iterations. Not committed plans — just notes so they don't drop on the floor.

## Architecture

### ConvNet alternatives to the custom U-Net
The current "iter 01" model is a plain custom U-Net (~8M params, base width 32, 4 levels, BatchNorm + ReLU). It's the detection-rate champion (20/20) but isn't a serious modern ConvNet. Worth swapping for:

- **A bigger / deeper plain ConvNet head** — same UNet skeleton but more channels per level, residual connections, GroupNorm instead of BatchNorm so it's more stable at small batches.
- **ResNet-style encoder + UNet decoder** but with the encoder NOT pretrained on ImageNet — train from scratch on LiDAR features, no semantic mismatch from RGB→7-channel-terrain transfer. ImageNet pretraining was the *whole point* of iter 02; this is the opposite experiment.

### ConvNeXt
Liu et al. 2022 — modernized ConvNet that competes with vision transformers on ImageNet. Available as a `segmentation_models_pytorch` encoder (`convnext_*` family) and `timm`.

Why it's interesting here:
- Larger receptive field than ResNet34 because of the depthwise-7×7 + LayerNorm design — could help the "shallow pit" problem iter 02 had with ResNet34's aggressive stem.
- LayerNorm is more stable at very small batch sizes (we're at batch 16 with only 74 train pits per epoch).
- ImageNet-pretrained ConvNeXt-Tiny is ~28 M params (close to ResNet34's 24 M) so VRAM cost on the 1070 Ti should be fine.

Risk: same RGB→7-channel pretraining mismatch as iter 02. May fix shallow-pit detection or may regress just like iter 02 did.

Action: try `smp.Unet(encoder_name="timm-convnext_tiny", encoder_weights="imagenet", in_channels=11, classes=3)` as an iter 06 candidate. Same trainer template as iter 03.

## Data + preprocessing

### Using TerraScan for ground classification
TerraScan (Terrasolid) is the industry-standard commercial tool for LiDAR ground classification — different algorithm family from PDAL's `smrf`/`pmf` filters. Worth investigating if:

- The current DEM has visible classification errors (e.g., low vegetation misclassified as ground → bumpy DEM in pit floors that fuzzes the pit signature).
- TerraScan licenses are available through a collaborator or institution. Not free; commercial license.
- Comparing TerraScan-classified ground vs the current PDAL `Classification[2:2]` filter on a small test extent would tell us how much DEM quality is currently leaving on the table.

Action items to actually use this:
1. Identify whether a TerraScan license is available.
2. Reclassify a small AOI (the 9t tile or just a few hundred meters around 5 known pits) with TerraScan.
3. Rebuild the DEM + features stack from that reclassified LAS.
4. Train a single iter (same config as iter 03) on the new stack; compare.

If TerraScan isn't available, the equivalent experiment is to try alternative open-source ground filters: `whitebox.LidarGroundPointFilter`, `lasground` (LAStools, commercial but cheap-ish), or PDAL's `filters.pmf` with tuned parameters instead of `smrf`.

### Getting better data
Several axes here, ranked by expected impact:

1. **Higher point density.** Current `output2.las` density should be characterized (`pdal info --metadata`). Modern PA 3DEP collections are 8+ pts/m²; older ones are 1-2. If we're on a low-density vintage, terrain detail is fundamentally limited.
2. **Newer collection date.** PA 3DEP has multiple collection eras. Newer flights have higher point density AND a smaller gap between collection and present-day ground truth. Lots of pits may have changed appearance over 10+ years.
3. **Leaf-off vs leaf-on.** Leaf-off LiDAR (winter / early spring) gives much better ground-return density under deciduous canopy. If `output2.las` is a leaf-on collection, swapping for leaf-off would help directly.
4. **More tiles.** The 9t tile has 110 labeled pits. Expanding labeling to McKean / Potter / Elk counties (the methane super-emitter region from Kang 2014) would 3-5x the training set. This is the project's stated next major effort.
5. **Independent validation tiles.** Right now we evaluate on test pits from the same tile as training. An untouched tile with independently-known pits is the honest generalization test.

Action items:
- Run `pdal info` on `output2.las` and write a one-page "what data do we have" doc capturing density, vintage, leaf-status, scan angle range, point classes present.
- Use `notebooks/wellsight/data/_download_lidar.py` to query TNM for available McKean / Potter tiles, check their metadata, identify the best-vintage collection.

### ICP co-registration: 2018 LiDAR ↔ 2004 LiDAR
We have two vintages of LiDAR over (some subset of) the same ground: a 2018 collection and a 2004 collection. Co-registering them opens up **temporal change detection**, which is genuinely valuable here:

- Pits / pads present in 2018 but not 2004 → modern (post-2004) wells, narrowing the search space.
- Pits present in both → at least a decade-and-a-half old; likely matches the "abandoned" set that field crews care about.
- Pits in 2004 but not 2018 → reclaimed or buried sites; useful negative evidence and worth flagging for ground truth audits.

But raw 2004 and 2018 collections are **not aligned by default.** Different IMU/GNSS calibrations, different processing pipelines, and a decade-plus of datum / geoid revisions mean a meter-scale horizontal offset and a centimeter-to-decimeter vertical offset are normal. Differencing them naively gives noise plus systematic bias, not real change.

ICP (Iterative Closest Point) is the standard fix. Two variants worth knowing:

- **Point-to-Point ICP** — classic Besl & McKay 1992. Each iteration: nearest-neighbor pair the two point clouds, find the rigid transformation minimizing sum-of-squared distances, apply it, repeat to convergence. Simple, robust, slow on dense clouds.
- **Point-to-Plane ICP** — Chen & Medioni 1991, used by Barlow's McMurdo Dry Valleys dissertation (see `docs/articles/barlow_dissertation_explained.md`). Each source point's residual is measured to the **tangent plane** at the target's nearest neighbor, not the point itself. Converges 5–10× faster on smooth surfaces like ground, more accurate, and handles small terrain micro-relief gracefully. **This is the variant we should use for ground-surface co-registration.**

Recommended approach for this project:

1. **Clip both vintages to ground returns only** (Classification = 2). Co-registering full point clouds is dominated by canopy variability; ground-only is the stable signal.
2. **Coarse alignment first.** If horizontal offset > 5 m, ICP may not converge from cold start. Do a global registration first — `open3d.pipelines.registration.registration_ransac_based_on_feature_matching` with FPFH features, or manual CRS-level offset estimation from known landmarks (road centerlines, building corners).
3. **Point-to-Plane ICP refinement** on the ground-only clouds (e.g., `open3d.pipelines.registration.registration_icp(..., TransformationEstimationPointToPlane())`). Limit search to a stable subregion — flat areas without trees or buildings give the cleanest tangent planes.
4. **Apply transformation** to the 2004 cloud, then build the DEM stack against it.
5. **Validate** by computing the residual DEM-of-difference statistics over known-stable regions (road surfaces, exposed bedrock). Mean should be ≈ 0; NMAD should be in the noise (decimeters at worst). If not, the registration didn't converge — iterate.
6. **Difference for change detection.** Subtract 2018 DEM from 2004 DEM. Stable areas → ~0. Pit excavation → positive (2004 ground higher than 2018). Reclaimed pit → negative.

Software options: `open3d` (best Python API, point-to-plane built-in), PDAL (`filters.icp` — point-to-point only), CloudCompare GUI (good for one-off interactive alignment + visualization).

Cite-worthy reference for the methodology: the Barlow dissertation already on disk. Their NMAD / LOD95 framework for honest change detection thresholds is the right thing to copy here — small "change" values within the alignment noise floor must be rejected, not reported.

Action items:
1. Identify and characterize the 2004 LAS — vintage, density, classification quality. Drop into a `docs/pipelines/multi_vintage_data.md` once known.
2. Spike a small (1 km²) test extent: register 2004 to 2018 via point-to-plane ICP, validate against known-stable surfaces, compute DEM-of-difference, eyeball it in QGIS.
3. If the spike looks honest, scale to the full 9t tile and integrate the differenced DEM as either (a) an extra feature channel for the pit U-Net, or (b) a candidate-generation layer in its own right.

## Other things to revisit later

- **Iter 04 (maxpit ensemble) road-FP problem** — partially addressed by iter 05/05b/05c filters but not perfectly. Multitask training (shared encoder, pit + road heads) is the principled fix; band-aid filters are the practical one.
- **Probability calibration.** Iter 04 mean ensemble's argmax is the operational output, but the underlying probs are uncalibrated. Platt scaling or isotonic regression on the val set would let "≥0.7 confidence" mean what it claims. Important before field-deploying candidates.
- **Confidence-conditioned output.** Maybe the right operational deliverable isn't argmax, but ranked candidate points by probability with a clean precision-recall curve to choose the operating point.
