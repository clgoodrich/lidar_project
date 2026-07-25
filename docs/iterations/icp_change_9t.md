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

## Deferred
- Per-swath / per-tile bias correction of the 2006-2008 DEM (removes the ±0.22 m
  striping; would drop the detection floor from ~0.4 m toward ~0.2 m).
- Vegetation/canopy masking before differencing.
- Decide whether recent-activity change detection is a project goal at all — if
  so, this product is already usable; if not, this line stops here.
See `BACKLOG.md` → "ICP / change detection".
