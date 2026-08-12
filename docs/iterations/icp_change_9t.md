# Preliminary ICP change detection on the 9t block (2026-07-25)

## Goal
Establish whether the two available Venango-area LiDAR surveys can support
surface-change detection over the 9t block — and, specifically, whether any
elevation change is detectable at known well locations.

## Inputs / provenance
- **Older:** USGS_LPC_PA_STATEWIDE_N_2006_2008, tiles 002958, 002959, 003111,
  003112 (EPSG:2271, NAD83 / PA State Plane North, US survey feet; Z also feet).
- **Newer:** USGS_LPC_PA_WesternPA_2019_D20 (QL2, EPSG:6346), the same source as
  every other 9t derivative.
- **Alignment:** already computed 2026-05-21 by
  `notebooks/wellsight/build/_icp_old_vs_new.py` (PDAL `filters.icp`, ground-class
  only, 5 m voxel, fixed = 2019, moving = 2006-2008 after reprojection and
  Z × 0.3048). Summary:
  `data/derivatives/experiments/icp/icp_all_summary.md`.
- **Full-overlap DoD:** already computed 2026-05-21 by
  `notebooks/wellsight/build/_icp_change_map.py` →
  `data/derivatives/experiments/icp/change_map/dem_diff_2m.tif`.
- **Ground truth:** `data/derivatives/annotations/well_head_pts_reprojected.gpkg`
  (540 known wells fall inside the 9t footprint).

This pass **did not re-run ICP**. It clipped the existing DoD to 9t, ran the
quality checks that decide whether the surface is usable, and wrote the products.

## What was built
Script: `notebooks/wellsight_v2/s7_analysis/_icp_change_9t.py`.
Outputs in `data/derivatives/experiments/icp/change_9t/`:

| file | content |
|---|---|
| `dod_9t_2m.tif` | difference of DEMs, 2019 − 2006/08, metres, EPSG:6346, 2 m |
| `dod_9t_sig_2m.tif` | same, masked to \|d − median\| > 3σ (candidate change) |
| `change_9t_quicklook.png` | hillshade / DoD / candidate-change triptych |
| `_stats_9t.json` | every number quoted below |

Footprint 619500–624000, 4593000–4597500 (EPSG:6346). 2250 × 2250 px, **100% valid**.

## Results

### Vertical agreement
| statistic | value |
|---|---|
| median | **+0.003 m** |
| robust σ (MAD-scaled) | **0.136 m** |
| raw std | 0.183 m |
| p01 / p99 | −0.442 / +0.541 m |
| \|d\| > 0.5 m | 1.94% |
| \|d\| > 1.0 m | 0.14% |

Median offset is 3 mm. The vertical datum agreement between the two surveys is
effectively perfect after the Z-unit conversion.

### Registration QC (the test that matters)
A DoD is only meaningful if residual horizontal misregistration is small — a
leftover shift `dx` becomes a fake elevation difference `dx·tan(slope)`, so
registration error masquerades as terrain change on steep ground. Stratifying
by slope separates the two causes:

| slope (deg) | n | median | robust σ |
|---|---|---|---|
| 0–5 | 1,897,434 | +0.004 | 0.152 |
| 5–10 | 1,651,978 | +0.007 | 0.134 |
| 10–15 | 836,496 | +0.002 | 0.125 |
| 15–20 | 376,966 | −0.003 | 0.122 |
| 20–30 | 239,354 | −0.012 | 0.108 |
| 30–90 | 58,684 | −0.013 | 0.098 |

Fit: `σ = −0.024·tan(slope) + 0.135`. The slope coefficient is **negative** —
σ *decreases* on steeper ground. Implied residual planimetric error ≈ **0 m**.

**The ICP registration is sound.** Whatever limits this product, it is not
misregistration. (σ being *highest* on flat ground is consistent with flat
ground being where the real change is — valley bottoms, fields, pads, roads.)

### The actual limitation: acquisition artifacts in the older survey
The DoD shows visible **flight-line striping and tile-seam steps**:

| pattern | amplitude |
|---|---|
| row-mean (along-track) | range ±0.22 m, std 0.094 m |
| column-mean (across-track) | range ±0.08 m, std 0.026 m |
| raw σ | 0.183 m |
| σ after removing row + column means | **0.154 m** |

Removing a simple row/column mean recovers ~16% of the variance. These are
swath-level vertical biases and mosaic seams in the 2006-2008 acquisition, not
terrain change. They are the dominant systematic error and they set the current
detection floor at roughly 0.4 m.

### Change at known wells — a clean negative
| | value |
|---|---|
| known wells inside 9t | 540 |
| DoD at wells, mean | +0.028 m |
| DoD at wells, median | +0.013 m |
| wells exceeding 3σ | 24 / 540 = 4.4% |
| background rate | 3.63% |

The enrichment is 1.2×; with n = 540 that is z ≈ 1.0, **not significant**.

**There is no detectable elevation change at known well locations between 2006-2008
and 2019.** This is the expected result and it is worth stating plainly: these are
overwhelmingly century-old wells whose pits and pads were cut long before 2006.
Both surveys see the same settled, revegetated ground. Change detection over this
epoch pair cannot find them.

## Interpretation
Three separate findings, and they point in different directions:

1. **The alignment is good.** Sub-centimetre median bias, no slope-dependent
   inflation. The earlier concern that a DoD here would be dominated by the ~0.8 m
   horizontal datum shift was wrong — ICP removed it cleanly.
2. **The older survey's swath biases, not registration, set the noise floor.**
   ±0.22 m of striping means the practical detection threshold is ~0.4 m. A
   per-swath / per-tile bias correction is the obvious lever and is cheap.
3. **This epoch pair is the wrong tool for finding old wells.** The wells predate
   both surveys. What a 2006→2019 DoD *can* find is recent activity — new pads,
   new access cuts, regrading, plugging operations, subsidence. That is a different
   and possibly useful question, but it is not "detect historic orphaned wells".

The candidate-change mask (3.63% of pixels) does contain coherent real features —
large accumulation patches in the NW, incision along drainages — but these are
geomorphic and land-use change, not well signatures.

## Reproduce
```
python notebooks/wellsight_v2/s7_analysis/_icp_change_9t.py
```
Prerequisite artifacts (already on disk, built 2026-05-21):
`data/derivatives/experiments/icp/change_map/dem_diff_2m.tif` and
`data/derivatives/experiments/icp/<tile>/_meta_icp*.json`.

## Data-quality note
`data/derivatives/experiments/icp/003111/_meta_icp_5m.json` records a **failed**
run (`converged: false`, fitness 39.4). It was superseded by a good re-run — the
summary table reports 003111 converged at RMSE 0.915, and `_icp_change_map.py`
correctly reads `_meta_icp_zm.json` for that tile. The stale file is still on disk
and would mislead anyone reading it directly.

---

# Part 2 — Where the non-erosional change actually is (2026-07-26)

Script: `notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py`.

## Removing the artifacts, in three stages

| stage | robust σ | what it removes |
|---|---|---|
| raw DoD | 0.136 m | — |
| + row/column median destripe | 0.107 m | along-track swath bias (row-median std 0.083 → 0.0001 m) |
| + edge-preserving background (400 m median) | **0.087 m** | broad 2D field, std 0.057 m: smooth swath blobs **and** sharp-edged per-tile blocks |

The second stage matters and is easy to get wrong. A Gaussian high-pass removes
the smooth blobs but **cannot remove a step edge** — it smears the tile seam into
a halo. The background is therefore estimated with a large *median* filter
(block-median downsample → median filter → bilinear upsample), which is
edge-preserving: it tracks the step, so subtracting it deletes the block.

Cost, stated plainly: this cannot distinguish a genuine >400 m change from bias.
Accepted — no plausible single earthwork here is that large.

Rasters: `dod_9t_destriped_2m.tif`, `dod_9t_highpass_2m.tif`.

## Is any of it real? A Monte-Carlo null

The DoD residual is spatially **correlated** — integral range 16–20 px, i.e. one
independent sample per ~1,290 m² (~35 m). Thresholding a correlated field
produces sizeable blobs *with no real change at all*, so raw patch counts mean
nothing on their own. The null is a synthetic Gaussian field with a matched
autocorrelation (σ = 4.0 px), pushed through the identical pipeline.

| | patches ≥200 m² | area | largest patch |
|---|---|---|---|
| **observed** | **367** | **44.12 ha** | **24,920 m²** |
| noise-only (8 sims) | 57 ± 5 | 1.56 ha | 558 m² (max 712) |
| ratio | **6.4×** | **28.2×** | **45×** |

**The change is real.** It is not a thresholding artifact.

The null also fixes the reliability cutoff: noise never produced a patch above
**712 m²**, so patches at or above that are treated as reliable and smaller ones
are not. 108 of 367 patches clear it.

## Does erosional change actually follow the channels?

Rather than assume the rule, test it. 63% of the block area lies within 40 m of a
channel, so that is the null expectation for a patch placed at random.

| set | within 40 m of a channel | enrichment |
|---|---|---|
| all patches | 75% | 1.20× |
| **reliable only** | **84%** | **1.34×** |

Real change *does* concentrate toward channels, and the effect strengthens when
the unreliable patches are dropped — which is what should happen if the cutoff is
doing its job. The enrichment is modest, so the fluvial label is supported but not
decisive for any single patch.

⚠️ An earlier version of this test, run on the destriped-but-not-high-passed
field, showed **flat** enrichment (0.97–1.02× in every distance band). That was
the residual bias field swamping the signal, not evidence against the rule.

## Results

| class | patches | reliable | area (ha) | \|volume\| (m³) |
|---|---|---|---|---|
| fluvial | 275 | 91 | 32.57 | 113,461 |
| mass wasting | 5 | 1 | 0.12 | 201 |
| **anthropogenic (non-erosional)** | 87 | **16** | **2.65** | **10,766** |

### The 12 largest non-erosional changes

All are off-channel and gentle-to-moderate slope. Coordinates are EPSG:6346.

| id | type | mean Δz | area m² | \|vol\| m³ | slope | chan | road | well | centroid |
|---|---|---|---|---|---|---|---|---|---|
| 2282 | cut | −0.53 | 2,908 | 1,542 | 17.1° | 42 m | 0 m | 101 m | 621491, 4593066 |
| 1064 | fill | +0.38 | 3,744 | 1,427 | 13.0° | 45 m | 0 m | 72 m | 620963, 4595976 |
| 768 | fill | +0.40 | 3,476 | 1,377 | 5.0° | 48 m | 20 m | 95 m | 619974, 4596236 |
| 939 | fill | +0.43 | 2,236 | 966 | 2.3° | 60 m | 0 m | 128 m | 619977, 4596084 |
| 511 | fill | +0.40 | 1,688 | 668 | 7.6° | 74 m | 0 m | **8 m** | 623987, 4596497 |
| 2128 | cut | −0.40 | 1,464 | 589 | 7.9° | 72 m | 72 m | 952 m | 623811, 4593331 |
| 479 | fill | +0.48 | 1,224 | 584 | 8.4° | 76 m | 0 m | 139 m | 620381, 4596563 |
| 1800 | cut | −0.37 | 1,416 | 526 | 13.7° | 47 m | 16 m | 344 m | 623872, 4593995 |
| 315 | cut | −0.40 | 1,304 | 515 | 5.2° | 60 m | 18 m | 256 m | 620236, 4596833 |
| 1860 | cut | −0.38 | 1,232 | 469 | 2.8° | 53 m | 8 m | 291 m | 623231, 4593838 |
| 2202 | cut | −0.35 | 1,184 | 415 | 11.4° | 45 m | 420 m | 446 m | 623203, 4593230 |
| 2212 | cut | −0.33 | 1,212 | 399 | 7.5° | 116 m | 364 m | 384 m | 623118, 4593228 |

### Raster outputs

All EPSG:6346, 2 m, aligned to every other 9t raster.

| file | type | content |
|---|---|---|
| `change_class_9t_2m.tif` | uint8 + colour table | all 367 patches: 1 = fluvial, 2 = mass wasting, 3 = anthropogenic; 0 = nodata |
| `change_class_reliable_9t_2m.tif` | uint8 + colour table | same, ≥712 m² patches only (the trustworthy set) |
| `dod_9t_nonerosional_2m.tif` | float32 | Δz in metres, masked to reliable non-erosional patches (5,692 px, −3.28 … +1.07 m) |

The two class rasters carry an embedded colour table (blue / orange / red) and
`nodata = 0`, so they render correctly in QGIS on drag-and-drop with no styling
step. Class names are stored as band tags `CLASS_1..CLASS_3`.

Pixel counts — all / reliable: fluvial 62,527 / 48,135; mass wasting 565 / 312;
anthropogenic 11,666 / 5,692.

Full attributed set: `change_patches_9t.gpkg`, layer `change_patches`
(fields include `cls`, `reliable`, `mean_dz_m`, `volume_m3`, `slope_deg`,
`chan_dist_m`, `road_dist_m`, `well_dist_m`, `compactness`, `reason`).

## Interpretation
Most detected change is fluvial — 91 of 108 reliable patches, and 32.6 of 35.3 ha.
That is the expected outcome for a forested Appalachian block over 11–13 years.

The non-erosional residue is small: **16 reliable patches, 2.65 ha, ~10,800 m³**
across a 2,025 ha block. Nearly all sit on or beside mapped roads (10 of the top
12 are within 20 m of one), which is consistent with road maintenance, regrading,
and skid-trail work rather than well activity.

Two caveats that limit how hard these can be pushed:
- Visual inspection of the crops (`top_changes_9t.png`) shows several patches are
  **red/blue dipoles straddling a linear terrain edge** — the two surveys
  resolving the same road cut or bank slightly differently. Those are artifacts,
  not change. I tested the obvious global cause (older survey lower density →
  smoother DEM → curvature-correlated bias) and **it is not that**: corr(DoD,
  ∇²z) = +0.01 to +0.02, and DoD spread is flat across curvature bins
  (0.124–0.138 m). So the dipoles are local, not a systematic field, and the
  patch list needs manual triage before any individual entry is trusted.
- `well_dist_m` shows no meaningful pattern. Patch 511 sits 8 m from a known
  well, but with 540 wells in the block that is unremarkable — consistent with
  Part 1's finding of no significant DoD signal at wells.

## Reproduce
```
python notebooks/wellsight_v2/s7_analysis/_icp_change_9t.py           # Part 1
python notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py  # Part 2
```

## Deferred
- Per-swath / per-tile bias correction of the 2006-2008 DEM (removes the ±0.22 m
  striping; would drop the detection floor from ~0.4 m toward ~0.2 m).
- Vegetation/canopy masking before differencing.
- Decide whether recent-activity change detection is a project goal at all — if
  so, this product is already usable; if not, this line stops here.
See `BACKLOG.md` → "ICP / change detection".

---

# Part 3 — Rebuilt with ONE ICP solve (2026-07-31)

Script: `notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py`.

Triggered by a simple observation: `dod_9t_2m.tif` does not look like 9t. The
location was right, but two defects were found and both are fixed here.

## What was wrong with the 2026-05-21 product

1. **Each older tile got its own independent ICP solve**, then the results were
   mosaicked. Median DoD inside each tile footprint: 002958 −0.038, 002959
   −0.057, 003111 +0.046, 003112 +0.044 m — a **0.103 m spread** against a
   0.136 m pooled sigma. Part 1 called this "swath-level vertical bias in the
   2006-2008 acquisition". About half of it was our own alignment residual.
2. **`dem_diff_2m.tif` did not reconstruct from its own inputs.** Its 2019 side
   covered 44.4% of 9t while the diff covered 99.97%, and `diff − (new − old)`
   had mean |r| 0.24 m (not a shift; ±4 px scanned, dy=dx=0 optimal). The repo
   script is not the version that produced the rasters — rasters 2026-05-21,
   `_icp_change_map.py` edited 2026-05-22 (`acce517`) and 2026-05-23
   (`375f9f5`) — and its `tiles/mosaic_3x3` input no longer exists on any drive.

## What the rebuild does differently

| | 2026-05-21 | rebuild |
|---|---|---|
| ICP solves | 4 independent | **1**, all four tiles merged |
| 2019 reference | `tiles/mosaic_3x3/*/dem_1m.tif` (gone) | `tiles/9t/dem_9t_05.tif` |
| mosaicking | running `0.5*(dst+buf)`, order-dependent | true mean (sum/count) |
| Z scale | 0.3048 (international ft) | 1200/3937 (US survey ft) |
| ICP `max_dist` | unset | 5.0 m |

Inputs: 2006-2008 tiles `002958, 002959, 003111, 003112` (the four that cover
9t: 30.6 + 17.0 + 36.9 + 20.6 = 105.1% with overlaps) against all nine 2019 D20
tiles, ground class only, 5 m voxel — the same voxel as the original so the
comparison is apples-to-apples.

### Two failures worth recording

**The first attempt diverged**: `converged=False`, fitness 17.7, shift
−30431 / +4219 / +3687 m. Cause: both clouds were cropped to the same bbox, but
the 2019 tiles stop at the block edge, so the older cloud kept a 200 m rim with
no counterpart. `filters.icp` leaves `max_dist` unset, so those orphan points
were still paired with their nearest 2019 neighbour hundreds of metres away and
dominated the solve. **The fixed cloud must strictly enclose the moving cloud.**
This is the same failure mode as the stale `003111/_meta_icp_5m.json`
(`converged: false`, fitness 39.4) — not a one-off.

**The second attempt tripped a guard that was itself wrong.** ICP returns a
rigid transform about the coordinate ORIGIN. UTM northings are ~4.6e6 m away, so
the 2.8e-5 rad rotation in the solution appears as a +130 m translation term
that the rotation immediately cancels. The raw translation column is not the
shift. The guard now evaluates displacement at the moving cloud centroid.

## The solve

`converged=True`, fitness 0.967, rotation ~2.8e-5 rad. Displacement at the block
centroid: **dx −0.0024, dy −0.0003, dz +0.0396 m**. The two surveys were already
very nearly co-registered — consistent with Part 1, but now as one transform for
the whole block rather than four that could disagree.

## Results

| | per-tile spread | robust sigma | row-mean std | sigma after row+col removal |
|---|---|---|---|---|
| original (4 solves) | 0.103 m | 0.1358 m | 0.0939 m | 0.1124 m |
| **single ICP** | **0.0576 m** | **0.1119 m** | 0.0786 m | 0.0877 m |
| single ICP + per-tile dz | 0 by construction | 0.1102 m | 0.0740 m | 0.0874 m |

The single solve cut the per-tile spread by **44%** and sigma by **18%**. So
roughly half the rectangular stepping was our own alignment residual. The
remainder is in the 2006-2008 data, but removing it explicitly buys only another
1.5% of sigma — it is a small-amplitude step, not a dominant term.

**Reconstruct test: PASS**, `max|resid| = 0.000e+00`. The 2026-05-21 product
failed this at 0.24 m.

**What is left is genuine along-track striping.** With the tile blocks gone it is
plainly visible in the figure as east-west banding, and row-mean std (0.0786 m)
is now 3.7x the column-mean std (0.0213 m). Part 1 described the artifact
correctly even though it attributed the cause half wrong.

### Registration QC — and a correction to Part 1

| slope (deg) | n | median | robust sigma |
|---|---|---|---|
| 0–5 | 1,589,413 | −0.0072 | 0.0923 |
| 5–10 | 1,751,418 | −0.0089 | 0.1075 |
| 10–15 | 917,661 | −0.0036 | 0.1250 |
| 15–20 | 435,084 | +0.0038 | 0.1488 |
| 20–30 | 292,607 | +0.0134 | 0.1794 |
| 30–90 | 75,992 | +0.0693 | 0.2683 |

Fit: `sigma = +0.098*tan(slope) + 0.106`, implying ~**0.10 m** residual
planimetric error. Part 1 reported a *negative* coefficient and "implied
planimetric error ≈ 0 m". A DoD noisier on steep ground is the physically
expected behaviour; Part 1's inverted result was the per-tile blocks inflating
sigma on flat ground, where they were most visible. The alignment is still
excellent — 0.10 m is a twentieth of a 2 m cell.

## Change at known wells — the negative HOLDS

The rebuilt DoD initially appeared to show a strong signal:

| | >3 sigma at wells | background | naive z |
|---|---|---|---|
| original | 4.44% | 3.63% | +1.02 |
| single ICP | **14.63%** | 4.08% | +12.39 |

It survives a properly specified null too — toroidal shifts of the whole point
pattern, which preserve clustering and the ~35 m autocorrelation (p = 0.001,
observed 14.63% vs null 2.41–5.74%). **It is still an artifact.**

Two facts kill it:

1. **The "known wells" layer is circular.**
   `annotations/well_head_pts_reprojected.gpkg` and
   `annotations/wellhead_pits.gpkg` are the SAME 861 points (median separation
   0.0 m, 100% within 5 m). These are hand-digitised *pits* — points placed
   where a depression is visible on the 2019 LiDAR DEM. They are selected for
   being depressions in the newer survey.
2. **The two surveys differ ~7x in density** (2019 D20 QL2 ~4.8 pts/m2;
   2006-2008 ~0.67 pts/m2). Local depression depth at those same points:

   | survey | median local relief |
   |---|---|
   | 2019 (~4.8 pts/m2) | −0.3251 m |
   | 2006-08 (~0.67 pts/m2) | −0.2343 m |

   The sparse survey resolves only **72%** of the depth. The shortfall,
   **−0.0907 m**, is the same sign as and larger than the observed DoD median at
   those points (−0.0555 m).

So the sparse older survey smooths small pits away, the annotation points were
chosen for being small pits, and `2019 − 2006` therefore goes negative at
exactly those locations. The artifact alone more than accounts for the
observation. **No claim of subsidence at wells is supported.** Part 1's
conclusion stands: this epoch pair cannot find historic orphaned wells.

This also means any future DoD test against these points is circular. A
non-DEM-derived well list (DEP permit coordinates) is required.

## Outputs

All EPSG:6346, 2 m, 2250x2250, aligned to every other 9t raster, in
`data/derivatives/experiments/icp/change_9t/`:

| file | content |
|---|---|
| `dem_2006_singleicp_9t_2m.tif` | aligned 2006-2008 DEM, one ICP solve |
| `dod_9t_singleicp_2m.tif` | 2019 − 2006/08, m — **the product to use** |
| `dod_9t_singleicp_tiledz_2m.tif` | same, per-tile residual dz removed |
| `fig_dod_9t_singleicp_vs_original.png` | three-panel comparison |
| `_icp_rebuild_9t.json` | every number quoted above |

The 2026-05-21 rasters are left in place, unmodified, for comparison. They
should not be used for analysis.

## Reproduce
```
python notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py
python notebooks/wellsight_v2/s7_analysis/_icp_change_9t_rebuild.py --reuse-icp
```
QC scripts (scratchpad, not repo-tracked): `_qc_icp_rebuild_9t.py`,
`_test_wells_signal_9t.py`, `_test_wells_resolution_artifact.py`,
`_diag_icp_9t_provenance.py`.

## Deferred
- **Destriping is now the only lever left.** Row-mean std 0.0786 m; removing
  row+col means takes sigma 0.1119 → 0.0877 m (22%). Part 2's stack was tuned
  against blocky artifacts that no longer exist and must be re-derived on
  `dod_9t_singleicp_2m.tif` before its patch classification means anything.
- **Part 2's outputs are stale.** `change_class_9t_2m.tif`,
  `change_class_reliable_9t_2m.tif`, `dod_9t_nonerosional_2m.tif` and
  `change_patches_9t.gpkg` all derive from the superseded DoD.
- A non-DEM-derived well list, so the wells test stops being circular.
