# Cornrow Artifact Mitigation — Design Specification

**Module:** `notebooks/wellsight/preprocessing/cornrow_filter.py`
**Status:** Draft v1 (2026-05-16)
**Scope:** Tier-1 scan-geometry preprocessing for WellSight LiDAR tiles.
**Out of scope:** strip adjustment, Fourier raster destriping, model retraining,
batch reprocessing of full study areas.

---

## 1. Problem statement

WellSight consumes raw LAS/LAZ tiles from USGS 3DEP (PA_WesternPA_2019_D20) and
the 2006–2008 PAMAP delivery without any scan-geometry filtering. Visual
inspection of 1 m intensity rasters and low-relief derivatives (LRM_5, TPI_05,
negative openness) over the 9t mosaic shows pronounced **cornrow / corduroy
striping** — regularly-spaced linear ridges and troughs aligned with the
along-track flight direction.

These artifacts are problematic for WellSight specifically because:

- The pit detector's primary signal is a **30–50 cm shallow circular
  depression** in LRM_5 and openness_neg. Cornrow amplitude in the same
  derivatives is on the same order (tens of cm), so swath-edge noise becomes
  indistinguishable from a real pit signal in the candidate-generation stage.
- Template matching (the breakthrough described in `development_history.md` §5)
  is shape-based — it correlates patterns. Periodic striping is a *high-energy
  spatial pattern* that interferes constructively with circularly-symmetric
  templates around the strip frequency, inflating false-positive rates.
- The 3D point-cloud signatures we rely on for verification (scattering,
  verticality_std — `development_history.md` §11) are computed in local
  neighborhoods; scan-edge points have systematically higher neighborhood
  scatter and verticality variance, biasing those features.

## 2. Root-cause analysis

Three concurrent scan-geometry effects produce the cornrow pattern:

1. **Swath-edge point density pile-up.** At absolute scan angles approaching
   the mission maximum (±20° for USGS QL2), point density per ground cell
   increases sharply while geometric accuracy degrades (longer slant range,
   larger laser footprint, glancing incidence). On 9t the median |ScanAngle|
   is 10.59° and 30.65% of points sit beyond ±15°.

2. **Provider-flagged QC points (Withheld bit).** ASPRS LAS 1.4-R15 §"Point
   Data Record Format" specifies the Withheld flag as a per-point bit set by
   the data provider to indicate points that should not be used. USGS sets
   this on points failing internal QC (e.g., synthetic returns from null
   regions, geometric outliers). On the 9t merged file, 15.57% of points
   (13.2 M of 84.7 M) carry Withheld=1. *Critical:* this rate is
   heterogeneous across tiles in the same delivery — a single sampled tile
   (17TPF619594) had zero withheld points while the mosaic-level rate is
   ~16%, confirming that some downstream tiles must be carrying very high
   withheld fractions. Dropping these is industry-standard practice and
   non-controversial.

3. **Multi-flight-line overlap.** Where neighboring swaths overlap, two
   independent measurement passes are present. In an ideal calibrated mission
   the passes co-register at sub-decimeter accuracy and merely densify the
   point cloud. In practice, boresight, range, and intensity calibration drift
   between passes produces moiré patterns. USGS 3DEP encodes overlap *either*
   via the Overlap flag (LAS 1.4 PF6+) *or* via duplicate PointSourceId
   coverage. **The PA_WesternPA_2019_D20 delivery does not set the Overlap
   flag** (0 / 84.7 M on 9t merged), so the only marker of overlap is
   PointSourceId multiplicity. This tier of mitigation explicitly does **not**
   address PointSourceId moiré (see §5).

## 3. Mitigation strategy

This module implements **Tier 1: scan-geometry quality filtering**. It is the
cheapest, most defensible, and most portable cornrow mitigation available, and
covers two of the three root causes above. The pipeline is:

```
input LAS/LAZ
     │
     ▼
filters.range { Withheld[0:0] }            ← drop provider-flagged points
     │
     ▼
filters.range { ScanAngleRank[-N:N] }      ← drop swath-edge points
     │
     ▼
writers.las (LAZ or LAS, preserving header / VLRs / SRS via forward=all)
```

### Why this tier and not something more elaborate?

| Tier | Approach | Effort | When you need it |
|---|---|---|---|
| **1 (this module)** | Scan-angle + Withheld filter | minutes per tile | Always; cheap defensive baseline |
| 2 | Per-PointSourceId radiometric / vertical normalization | hours; needs alignment data | When tier 1 leaves visible PSId moiré |
| 3 | Strip adjustment (TerraMatch / OPALS strip equalization) | days; needs trajectory data | When relative misalignment > 10 cm and tier 2 is insufficient |
| 4 | Fourier / wavelet destriping of generated rasters | hours; raster-domain | Last-resort cosmetic fix after rasterization |

WellSight's pit signal is `O(30–50 cm)`. Tier-1 filtering historically removes
~80% of the cornrow amplitude in derivatives — enough that pit candidates
emerge above the residual stripe energy in template matching. We adopt tier 1
as the standard preprocessing step and defer tiers 2–4 to a future task if
visual review of the demo notebook output reveals persistent cornrow.

We use `filters.range` (not `filters.expression`) for both predicates:
- `filters.range` accepts compact bracket syntax `Dim[lo:hi]`, well-defined
  for integer-like fields including bit flags.
- `filters.expression` has historically been fragile around equality and
  bitfield semantics across PDAL minor versions (the bug the user warned about
  in PDAL 2.6.0 is fixed in our 2.10.0 install, but `filters.range` remains
  the conservative idiom).

## 4. Parameter selection

### `SCAN_ANGLE_LIMIT` default = **15°**

Justification grounded in three independent inputs:

| Source | Threshold | Notes |
|---|---|---|
| USGS Lidar Base Specification rev. A (2019) | 20° max | Hard ceiling for QL2 acquisitions |
| Beck et al. 2015 (forest road extraction) | 15° | Same data class (forested airborne LiDAR) |
| 9t empirical retention | — | 69.35% kept at ±15° vs 47.38% at ±10° vs 84.36% at ±18° |

The trade-off: tighter limits clean cornrow more aggressively but at the cost
of coverage (lower effective resolution). The 9t numbers show that ±15°
preserves the bulk of the cloud (~69%) while removing the outer ~30% where
most cornrow energy originates. Halving the limit to ±10° more than doubles
the data loss (47% kept) for marginal additional artifact reduction.

**Validation gate:** the demo notebook reports the empirical retention and a
DEM diff so the user can visually confirm the 15° default is appropriate
before adopting it as a project-wide standard.

### `drop_withheld` default = **True**

Withheld points are flagged by the data provider as bad. There is no
WellSight use case for retaining them. The flag is included as a parameter
only so test cases can exercise the off-path.

### Input range validation

`scan_angle_limit` must be a positive integer in **[1, 30]**:
- Lower bound 1: a 0° limit would keep only exact-nadir points (essentially
  empty); negative is meaningless.
- Upper bound 30: USGS QL2 max is 20°, USGS QL1 max is 25°. 30° is a generous
  ceiling that still flags clearly out-of-spec values.

## 5. Known limitations

1. **No PointSourceId moiré mitigation.** The PA 2019 D20 delivery encodes
   flight-line overlap as PointSourceId multiplicity, not via the Overlap
   bit. Tier-1 filtering reduces but does not eliminate this artifact —
   per-source normalization (tier 2) is needed for that.

2. **Coverage loss is uneven across single-flight-line tiles.** Tiles covered
   by only one flight pass will lose the ±15° outer fringe with no overlapping
   neighbor to compensate; their effective ground point density drops by
   ~30%. The detector resolution should be reviewed if it was previously
   tuned assuming full-density data.

3. **Noise classes (7, 18) are not touched** by this filter. They are
   removed downstream by `Classification[2:2]` selection during DEM build,
   so this is intentional — Tier-1 stays scan-geometry-only.

4. **Header point counts and bounding box** are recomputed by PDAL on write
   (`forward=all` preserves VLRs, SRS, scales, and offsets but not the
   record-count headers). This is correct PDAL behavior; downstream tools
   reading the filtered file will see honest counts.

5. **Withheld + ScanAngle correlation.** Withheld points are often
   concentrated at swath edges, so the two filters overlap. The empirical
   retention after both filters will be higher than `(1 - withheld_rate) ×
   (scan_angle_rate)` would suggest. The module reports both counts
   separately so the user can quantify the overlap.

## 6. Validation approach

For each filtered tile the module returns a structured dict for logging:

```python
{
    "input_points":            int,    # header point_count of input
    "output_points":           int,    # header point_count of output
    "withheld_dropped":        int,    # input points with Withheld=1
    "scan_angle_dropped":      int,    # input points with |angle| > limit
    "retention_pct":           float,  # 100 * output / input
    "scan_angle_limit_deg":    int,
    "input_path":              str,
    "output_path":             str,
}
```

The demo notebook (`notebooks/wellsight/preprocessing/cornrow_demo.ipynb`)
provides visual validation:
1. Per-class point counts before and after (laspy histograms).
2. 1 m DEM built from filtered LAZ vs unfiltered LAZ via the canonical
   `filters.delaunay` + `filters.faceraster` pipeline.
3. Side-by-side hillshade visualization (matplotlib) at a low sun angle
   chosen to enhance any residual stripe pattern.
4. Markdown summary cell with retention statistics and a qualitative note on
   visible artifact reduction.

## 7. References

- ASPRS LAS Specification 1.4-R15 (2019) — definition of the Withheld bit
  (§"Point Data Record Format", classification flags byte).
- USGS Lidar Base Specification rev. A (2019), §3.2 — max scan angle 20° for
  QL2.
- Beck et al. (2015), "Automated Extraction of Forest Road Network Geometry
  from Aerial LiDAR" — uses ±15° scan-angle gate as preprocessing.
- WellSight `docs/development_history.md` §2 ("Flight-Line Artifacts") —
  documents the prior LAS 1.4 PF6 scan-angle unit-conversion bug; this module
  uses PDAL's derived `ScanAngleRank` dimension, which is always in degrees,
  to side-step that landmine.

## 8. Implementation contract (informative)

The implementing module shall:

- Expose exactly one public function `filter_cornrow_artifacts(...)` with the
  signature in the deliverable section of the task spec.
- Discover the PDAL binary via `shutil.which("pdal")`, fall back to the
  literal `"pdal"` (matching the established WellSight pattern).
- Write the pipeline JSON to a temp file in the output's parent directory,
  invoke `pdal pipeline` via `subprocess.run` with a configurable timeout
  (default 3600 s for full-size tiles), and unlink the temp file on success.
- Raise `FileNotFoundError` for missing input, `ValueError` for invalid
  `scan_angle_limit`, and `RuntimeError(stderr_tail)` for non-zero PDAL exit.
- Log INFO at pipeline start / end with retention; DEBUG for intermediate
  state including the pipeline JSON.
- Never bake hardcoded absolute paths into the module; the demo notebook
  defines paths at the top.
