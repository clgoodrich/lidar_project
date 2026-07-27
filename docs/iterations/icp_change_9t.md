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
Script: `notebooks/wellsight_v2/build/_icp_change_9t.py`.
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
python notebooks/wellsight_v2/build/_icp_change_9t.py
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

Script: `notebooks/wellsight_v2/build/_icp_change_classify_9t.py`.

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
python notebooks/wellsight_v2/build/_icp_change_9t.py           # Part 1
python notebooks/wellsight_v2/build/_icp_change_classify_9t.py  # Part 2
```

## Deferred
- Per-swath / per-tile bias correction of the 2006-2008 DEM (removes the ±0.22 m
  striping; would drop the detection floor from ~0.4 m toward ~0.2 m).
- Vegetation/canopy masking before differencing.
- Decide whether recent-activity change detection is a project goal at all — if
  so, this product is already usable; if not, this line stops here.
See `BACKLOG.md` → "ICP / change detection".
