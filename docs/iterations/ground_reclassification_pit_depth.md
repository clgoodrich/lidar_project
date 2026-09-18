# Is the vendor withholding ground inside our pits?

**Date** 2026-09-18
**Verdict** No. The hypothesis is wrong, and the DEM is sound.
**Script** `notebooks/wellsight_v2/s7_analysis/_reclaim_ground_pit_depth_experiment.py`

---

## Goal

A sniff test earlier the same day found that points sitting *below* the
interpolated ground surface are 2.6x more common inside annotated pit floors than
elsewhere. That is the classic signature of a ground classifier bridging over a
small depression.

The mechanism is well understood. Every production ground filter in use —
TerraScan's routine, LAStools' `lasground`, PDAL's SMRF and PMF — is a variant of
Axelsson (2000) progressive TIN densification. It seeds a coarse TIN on the lowest
point in each cell of a grid, then iteratively adds points that pass an angle and
distance test against the growing surface. A pit a few metres across and a metre
deep can be smaller than the seed grid. If it never earns a seed, the TIN spans
rim to rim and the real floor returns sit below it, failing the iteration test.
They end up unclassified.

If that had happened here it would matter a great deal. Every terrain product in
this project is built from class 2. A bridged pit reads shallower than it is, and
`dem`, `slope`, `lrm`, `tpi`, `openness_neg` and `rrim` are all damped together.

## Inputs

| | |
|---|---|
| point clouds | `data/_source/lidar/westernpa/USGS_LPC_PA_WesternPA_2019_D20_17TPF{621594,616591,615591,613591}.laz` |
| | 40,970,303 points total, USGS 3DEP QL2, EPSG:6346 + NAVD88 Geoid12B |
| truth | `qgis/annotations/annotations_proj.gpkg`, layer `pit_inside` — 216 of the 712 annotated floors fall in these four tiles |
| tile choice | the four tiles holding the most annotated pit floors; 613591/615591/616591 are 9t training tiles, 621594 is the tile the sniff test flagged |

## Method

One PDAL pass per tile (CLI via `subprocess`, pipeline JSON — the Python bindings
do not work here):

```
readers.las -> filters.hag_nn (count=8, allow_extrapolation) -> writers.las
```

`filters.hag_nn` measures every point against the nearest **class 2** returns, so
it does not care how the non-ground points are labelled. Inside a bridged pit the
nearest ground is the rim, so a genuine floor return reads strongly negative.
Everything after that pass is numpy. Full point density — no decimation.

Pit floors were grouped into 187 crops, each padded 40 m so the rebuilt TIN has
real rim around it. Three zones per crop:

- **floor** — inside the annotated polygon
- **ring** — 2 m to 8 m outside it. Rim and shoulder. The control.
- **far** — more than 20 m from any annotated floor. The second control.

### The reclamation rule

Modelled on the low-point filter it is meant to undo, and run backwards. A
candidate is accepted only if it is *not* an isolated low outlier:

```
class 1, not withheld, not overlap          the vendor left it undecided
HAG < -0.05 m                               below the current ground surface
ReturnNumber == NumberOfReturns             a terminal return
>= 3 neighbours within 2.0 m are also       coherent, not a stray
    candidates
vertical spread of those neighbours         a surface, not a noise plume
    < 0.50 m
```

A **permissive** variant (`--permissive`) drops the last two tests and accepts
every terminal class-1 return below the surface. It exists so the result cannot be
dismissed as an artefact of a strict rule.

### Why this is not circular

Reclassifying points *because* they sit below the TIN and then showing the DEM
gets deeper is true by construction and proves nothing. So the test runs three
independent lines of evidence, weakest assumption first.

---

## Results

### Part 1 — ground-point density. Pure counting, no model, no threshold.

| zone | area m² | class 2 | per m² | class 1 | per m² |
|---|---|---|---|---|---|
| floor | 7,693 | 20,734 | **2.695** | 12,343 | 1.604 |
| ring | 69,085 | 202,160 | **2.926** | 123,047 | 1.781 |
| far | 877,275 | 2,518,392 | **2.871** | 1,532,437 | 1.747 |

**Ground density inside pit floors is 92% of the ring.** Per tile: 0.921, 0.961,
0.893, 0.873. A bridged pit would show a hole, not an 8% dip.

**Zero of 216 pit floors contain no class-2 points.** The median floor holds 84 of
them, the sparsest holds 5. The TIN is not spanning these pits — it is sitting on
real ground inside every single one.

That is the finding. Parts 2 and 3 only quantify what is left over.

### Part 2 — are the withheld points ground-like?

Local planar residual, each point fitted against its own cohort — class 2 against
class 2, reclaimed against ground-plus-reclaimed.

| zone | planar residual, class 2 | planar residual, reclaimed | median intensity, class 2 / reclaimed | median abs. scan angle |
|---|---|---|---|---|
| floor | 0.090 m | 0.198 m | 18,880 / 18,816 | 10.2 / 9.8 |
| ring | 0.036 m | 0.162 m | 21,432 / 15,128 | 10.2 / 10.5 |
| far | 0.022 m | 0.120 m | 20,816 / 17,184 | 10.1 / 10.0 |

Mixed, and honestly so. The reclaimed points are **twice as rough** as class-2
ground in the same floors — surface-like, but not a clean surface. Their intensity
inside floors matches ground almost exactly (18,816 against 18,880), which it does
*not* in the ring or far field. Scan angle matches everywhere.

The reading that fits all of it: these are real returns off a rough pit floor —
spoil, slumped rim material, debris, standing water edges — and the classifier
declined them because the floor is rough, not because it could not see it.

### Part 3 — what the DEM actually does

DEM rebuilt both ways at 0.5 m by Delaunay TIN with linear interpolation across
facets, which is what `phase_1_derivative_generation.ipynb` does. Depth is the
median ring elevation minus the 5th-percentile floor elevation.

| | strict rule | permissive rule |
|---|---|---|
| points reclaimed, all zones | 13,299 | 50,354 |
| points reclaimed inside floors | 547 | 1,200 |
| as a share of the floors' point budget | 2.6% | 5.5% |
| median depth as delivered | 0.78 m | 0.78 m |
| median depth after reclamation | 0.78 m | 0.78 m |
| **median change in depth** | **+0.000 m** | **+0.000 m** |
| largest change, any of 216 pits | +0.070 m | +0.083 m |
| pits deepened by ≥ 0.10 m | **0 of 216** | **0 of 216** |
| median surface change inside floors | +0.000 m | +0.000 m |
| median surface change in the rings *(control)* | +0.000 m | +0.000 m |

**Not one pit in 216 got 10 cm deeper, under either rule.** The deepest *single
cell* moved 0.43 m, but that is one cell in one floor and the pit's depth is
unchanged, because the surrounding floor was already pinned by real ground.

`figures/dem_before_after_reclaim_615591_c4_0p5m.png` shows why. The two hillshades
are indistinguishable. The difference map is scattered ±5 cm speckle across the
whole crop, in both directions, concentrated nowhere — local retriangulation
noise, not a pit getting deeper.

## Interpretation

**The ground classification is fit for this project's purpose, and the sniff
test's alarming ratio was a ratio with a small denominator.**

The 2.6x figure was a share *of non-ground points* inside pit floors. Non-ground
points are sparse inside floors, so a large share of them is a small absolute
number — 547 points across 216 pits under the strict rule, against 20,734 class-2
points already there. The signal was real. It was just never big enough to move a
surface that 2.7 ground returns per square metre had already fixed.

Two secondary results worth keeping:

- The strict rule *is* pit-specific — 8.2x the reclaim density inside floors
  versus the ring. Under the permissive rule that specificity falls to 4.4x. The
  coherence and spread tests are what made it selective; without them it eats low
  vegetation everywhere.
- Of 1,675,743 class-1 points across four tiles, only 50,365 (3.0%) sit below the
  ground surface at all, and **all but 11 of those are already terminal returns.**
  The vendor's class 1 is not hiding a second ground surface.

### What this does not rule out

- Pits with *no* annotation are not in this sample. If a pit is invisible in the
  DEM because it was bridged, we never drew it, and it cannot appear here. This
  test can only say that the pits we can see are rendered at their true depth.
- Four tiles of one delivery (PA WesternPA 2019 D20, QL2). It says nothing about
  the McKean QL1 data or any future acquisition.
- Depth is measured against annotated polygons at 0.5 m. A pit under 2 m across
  would be at the edge of what this can resolve.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_reclaim_ground_pit_depth_experiment.py \
    --tiles 621594 616591 615591 613591 --figures 3
python notebooks/wellsight_v2/s7_analysis/_reclaim_ground_pit_depth_experiment.py \
    --tiles 621594 616591 615591 613591 --permissive
```

Roughly 12 minutes per variant. `hag_nn` is 23–35 s per tile; the rest is the
per-crop TIN rebuilds.

## Outputs

```
data/9t/results/ground_reclassification/
    pit_depth_reclaim_strict_per_pit.csv          216 rows, one per pit
    pit_depth_reclaim_permissive_per_pit.csv      216 rows, one per pit
    ground_reclaim_strict_per_zone.csv            561 rows, one per crop-zone
    ground_reclaim_permissive_per_zone.csv        561 rows, one per crop-zone
    figures/
        dem_before_after_reclaim_615591_c4_0p5m.png
        dem_before_after_reclaim_616591_c17_0p5m.png
        dem_before_after_reclaim_616591_c1_0p5m.png
        dem_before_after_reclaim_613591_c8_0p5m.png
        dem_before_after_reclaim_613591_c10_0p5m.png
```

Every file is small; nothing here approaches the 100 MB threshold. The
intermediate height-above-ground clouds are written to the system temp directory
and deleted, and never enter the repository.

## Related

- `notebooks/wellsight_v2/s7_analysis/_sniff_ground_classification_9t.py` — the
  screen that raised the question. Its conclusion is superseded by this document.
- `literature/CITATIONS.md` — Axelsson (2000), added in the same change.
