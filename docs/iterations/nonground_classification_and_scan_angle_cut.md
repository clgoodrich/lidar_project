# The unassigned third of the point cloud, and the 18-degree cut

**Date** 2026-09-18
**Verdict** The delivery discards ~1 M accurate ground returns per tile at a hard
18° scan-angle threshold. It is not a standard — the McKean acquisition does not
do it. Fixing it is a reprocessing job, not a flag patch.

**Scripts**
```
notebooks/wellsight_v2/s7_analysis/_classify_nonground_returns_9t.py
notebooks/wellsight_v2/s7_analysis/_audit_nearground_unassigned_9t.py
notebooks/wellsight_v2/s7_analysis/_scan_angle_vs_ground_classification.py
notebooks/wellsight_v2/s7_analysis/_are_excluded_returns_accurate.py
notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py
notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py
```

---

## Where this started

A ground-classification sniff test raised, and then closed, the question of
whether the vendor was bridging over our pits (it is not —
`ground_reclassification_pit_depth.md`). The follow-up question was simpler: the
delivery leaves **43.7% of all returns in class 1, "unassigned"**. What are they,
and can we do better?

## What the delivery actually contains

Across 10 tiles, 113,556,364 points:

| code | class | points | share |
|---|---|---|---|
| 1 | unassigned | 49,599,030 | 43.678% |
| 2 | ground | 63,939,708 | 56.307% |
| 7 | low noise | 514 | 0.000% |
| 9 | water | 9,518 | 0.008% |
| 17 | bridge deck | 395 | 0.000% |
| 18 | high noise | 3,408 | 0.003% |
| 20 | vendor-defined | 3,791 | 0.003% |

**Correction to an earlier claim.** I previously said the delivery held "only
classes 1 and 2, no vegetation at all". Water, bridge deck, the noise flags and a
vendor class do exist. They total 0.016%, so the substance stands — there are **no
vegetation classes** — but the original statement was too absolute.

**Acquisition: 5–18 March 2020, leaf-off.** Checked from GpsTime, not assumed.
This governs every canopy number below: pulses reach the ground through bare
deciduous crowns, so ground share runs high and first-return canopy cover runs
low. Not comparable to a leaf-on survey.

## Part 1 — the unassigned points are classifiable

Point format 6, LAS 1.4. Everything needed is populated: `ReturnNumber`,
`NumberOfReturns` (up to 15), `Intensity`, `ScanAngleRank`, `ScanChannel`,
`GpsTime`, `PointSourceId`.

Return structure over four tiles, 40,970,303 points: **56.4% single-return,
43.6% multi-return.**

Class 1 cross-tabulated by height above ground against return position
(17,048,018 points):

| height band | only | first | intermediate | last | total | share |
|---|---|---|---|---|---|---|
| below ground | 115,774 | 93 | 48 | 81,603 | 197,518 | 1.2% |
| **at ground ±0.15 m** | 4,214,040 | 364 | 190 | 1,401,202 | **5,615,796** | **32.9%** |
| low veg 0.15–2 m | 273,808 | 297,482 | 78,145 | 127,498 | 776,933 | 4.6% |
| medium veg 2–5 m | 25,394 | 597,433 | 183,701 | 29,958 | 836,486 | 4.9% |
| high veg > 5 m | 335,810 | 7,093,397 | 1,605,848 | 586,230 | 9,621,285 | 56.4% |

**1,867,932 of them (11.0%) are intermediate returns** — the pulse was
intercepted both above *and* below them. Those are inside a canopy as a matter of
recorded fact, not inference.

Banding class 1 by height (USGS 3DEP Lidar Base Specification, ASPRS 3/4/5 split
at 2 m and 5 m) resolves it:

| | before | after |
|---|---|---|
| 1 unassigned | 41.6% | **13.7%** |
| 2 ground | 58.4% | 58.4% |
| 3 low vegetation | — | 1.9% |
| 4 medium vegetation | — | 2.0% |
| 5 high vegetation | — | 23.5% |
| 7 low noise | 0.0% | 0.5% |

**Two-thirds of the unassigned points get a real class.** What remains is the
±15 cm at-ground band, where a rock and a low return genuinely are not separable
by height.

## Part 2 — the vegetation remembers the disturbance

Per-cell structure metrics at 5 m, ≥30 returns per cell, compared inside
annotated features against a 2–15 m ring of forest around them. Cliff's delta is
the rank-based effect size.

| feature | canopy p95 inside | ring | delta | Cliff's d | p | cells |
|---|---|---|---|---|---|---|
| 621594 / **pad** | 14.25 m | 16.96 m | **−2.72 m** | −0.242 | ~0 | 3,427 |
| 621594 / pit | 14.19 m | 15.50 m | −1.30 m | −0.141 | 2.6e−2 | 86 |
| 616591 / pit | 19.58 m | 21.25 m | −1.67 m | −0.203 | 4.8e−3 | 67 |
| 615591 / pit | 19.97 m | 22.14 m | −2.17 m | −0.256 | 6.4e−3 | 39 |
| 613591 / pit | 17.37 m | 20.18 m | −2.81 m | −0.362 | 5.8e−3 | 20 |

**The canopy is 1.3–2.8 m shorter over every annotated feature, on every tile,
same direction five times out of five.** The pad result carries the weight: 3,427
cells and p indistinguishable from zero.

This is a signal the bare-earth DEM cannot see, from points the project currently
discards. Worth noting the bias runs *against* the finding for pits: canopy
height over a depression is measured against ground that dips into it, which
would make the canopy read taller, not shorter.

Pads also show more mid-story — multi-return share +0.046, canopy cover +0.021,
both small but consistent. Understory (0.5–3 m) is near zero everywhere: mature
leaf-off forest with no shrub layer, so the median is a true 0.000.

## Part 3 — why the at-ground points were withheld

5,615,796 points across four tiles sit within 15 cm of the ground surface and
were left unassigned. Measured against class 2 in the same tiles:

| | class 2 | at-ground class 1 |
|---|---|---|
| terminal return | 100% | 100% |
| single return | 76% | 75% |
| overlap flag | 0.00% | 0.00% |
| edge of flightline | 0.00% | 0.17% |
| **median abs. scan angle** | **9.4°** | **18.6°** |
| 95th percentile | 17.3° | 19.2° |
| median intensity | 20,816 | 17,952 |

Every property matches except where in the swath the return came from.

### The cliff

Of returns that *demonstrably reached the ground*, the share classified as
ground, binned by scan angle — this conditions on the return having got there,
so canopy occlusion is controlled for:

```
 0.5° – 13.5°   97–98%      flat
14.5°           92.7%
15.5°           89.9%
16.5° – 17.5°   88%         gentle taper
────────────────────────────────────────────
18.5°            0.0%   ← 847,751 returns, none
19.5°            0.0%   ← 171,863 returns, none
```

**A physical process does not produce a cliff.** Across five tiles, the same
threshold at exactly 18°, zero exceptions:

| tile | cutoff | at-ground returns excluded | DEM voids | r(void, angle) |
|---|---|---|---|---|
| 616591 | 18° | 1,019,614 | 15.99% | +0.32 |
| 621594 | 18° | 1,163,382 | 12.36% | +0.29 |
| 615591 | 18° | 915,233 | 24.55% | **−0.04** |
| 613591 | 18° | 1,337,861 | 17.17% | +0.37 |
| 622593 | 18° | 902,194 | 15.69% | +0.22 |

**The cliff is universal. The spatial correlation is not.** Voids stripe with
swath geometry on four tiles; 615591 has the worst void rate and no correlation
at all, so its holes come from canopy or terrain instead. Do not state "DEM voids
are swath stripes" as general.

### What it costs on the DEM grid

At the DEM's own 0.5 m resolution, across four tiles, 23,693,968 covered cells:

| | cells | share |
|---|---|---|
| holding ≥1 class-2 return | 19,473,371 | 82.19% |
| **no ground return — interpolated across** | **4,220,597** | **17.81%**, 105.5 ha |
| ...of those, an at-ground class-1 point is sitting in it | **1,032,075** | **24.5% of voids**, 25.8 ha |

49.4% of the withheld at-ground points land in cells that have no ground
measurement at all.

## Part 4 — was the vendor right to drop them?

The only thing that matters is whether the discarded returns are *accurate*.
Flight lines overlap, so the same ground is measured twice. Each excluded return
was compared against a plane fitted through class-2 ground **from a different
flight line**, so no line validates its own work; the plane removes terrain
slope.

| tile | group | n | median | RMSE | p95 abs | vs QL2 |
|---|---|---|---|---|---|---|
| 616591 | **excluded, >18°** | 39,967 | −0.004 m | **0.067 m** | 0.139 | within spec |
| 616591 | accepted, 10–18° | 15,219 | −0.001 m | 0.070 m | 0.151 | within spec |
| 621594 | **excluded, >18°** | 39,966 | −0.006 m | **0.065 m** | 0.137 | within spec |
| 621594 | accepted, 10–18° | 13,600 | −0.003 m | 0.099 m | 0.119 | within spec |

**The discarded returns are as accurate as the ones kept — slightly better.**
Both are inside the USGS 3DEP QL2 bar of RMSEz ≤ 10 cm, with essentially zero
bias. There is no accuracy argument for the cut.

**A design failure worth recording.** The intended yardstick was narrow-angle
(<10°) ground from neighbouring lines — the survey's best data. It does not
exist: adjacent swaths meet **edge to edge**, so a wide-angle return's
neighbouring coverage is *also* wide-angle. Measured overlap with a <10°
reference: **0.0%**. With <14°: 29–50%. With all accepted ground: ~100%. So this
is wide-against-wide agreement, and the final number is relative accuracy within
one survey — a shared systematic error would cancel, making 6.7 cm a lower bound.
It retains power against a scan-angle-dependent error, since two lines view the
same ground from opposite sides, but the flight directions were not verified.

## Part 5 — is it a convention?

No. Seven tiles from each of two acquisitions:

| acquisition | tiles | cliff | widest angle flown | ground share |
|---|---|---|---|---|
| **PA WesternPA 2019 D20** (Venango, QL2) | 7 | **6 of 7, all at 18°** | 19.4–19.9° | 51–68% |
| **PA Northcentral 2019 B19** (McKean, QL1) | 7 | **0 of 7** | 29.0° | 34–49% |

McKean tapers the way physics predicts — ~97% at nadir, easing to ~80% by 25°,
recovering to 98% at 27–29°. No threshold anywhere.

**The one Venango tile without the cliff is the tell.** `17TNE565467` was flown
**2019-11-26**, not March 2020, and its widest angle is 29.0° — the same sensor
configuration as McKean, and no cliff. "PA WesternPA 2019 D20" is therefore **not
one acquisition**: it contains at least two flight blocks with different sensor
setups and different ground processing, and only the **March 2020 block with the
±20° field of view** carries the cut.

That block is the entire study area. 9t, 613590, 621594 — all of it.

Loss across the seven sampled Venango tiles: **6,798,669 at-ground returns,
971,238 per tile.**

**McKean needs no reprocessing.** Its ground surface is already complete. Its
ground share is lower (34–49%) because QL1 at ~9 ppsm under Allegheny National
Forest canopy puts proportionally more returns in vegetation — a sampling
difference, not a classification problem. Void rates should not be assumed to
transfer between the two areas.

## What this does and does not justify

**Justified:** the March 2020 Venango ground classification is incomplete by
roughly a million accurate returns per tile, and a quarter of the DEM's
interpolated area has a real measurement sitting unused in it.

**Not justified:** that fixing it would improve model performance. Nothing here
measures that. The pit-depth experiment already showed that adding points where
ground already exists changes nothing; the void cells are the untested case.

**Not the way to fix it:** promoting flags. The reference surface is built *from*
class 2, so promoting points moves the surface and re-opens the question — one
pass does not converge. The correct approach is a fresh ground classification
(PDAL `filters.smrf`) with no angle cut, then a like-for-like DEM comparison.

## Reproduce

```bash
python notebooks/wellsight_v2/s7_analysis/_classify_nonground_returns_9t.py --tiles 621594 616591 615591 613591 --figure
python notebooks/wellsight_v2/s7_analysis/_audit_nearground_unassigned_9t.py --tiles 621594 616591 615591 613591 --profile
python notebooks/wellsight_v2/s7_analysis/_scan_angle_vs_ground_classification.py --tile 616591
python notebooks/wellsight_v2/s7_analysis/_are_excluded_returns_accurate.py --tiles 616591 621594
python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py --n-per-area 7
python notebooks/wellsight_v2/s7_analysis/_cross_section_classification.py --pit --tile 616591
```

Roughly 25–35 s of `hag_nn` per tile; the cross-acquisition sweep is about
20 minutes for 14 tiles.

## Outputs

```
data/9t/results/nonground_classification/
    return_structure_census.csv
    class1_height_by_return_position.csv
    reclassified_class_counts.csv
    delivered_class_counts.csv
    acquisition_windows.csv
    veg_structure_pad_pit_vs_ring.csv
    nearground_vs_ground_properties.csv
    dem_void_cells_by_tile.csv
    nearground_points_by_cell_ground_count.csv
    excluded_returns_vertical_accuracy.csv
    scan_angle_cliff_by_acquisition.csv
    canopy_height_over_pads_pits_vs_ring_5m.png
    classification_cross_section_pit_616591_55m.png

docs/presentation/figures_30to45min/scan_angle/
    scan_angle_vs_ground_classification_616591.png
    excluded_returns_vertical_accuracy.png
    ground_classification_cliff_by_acquisition.png

docs/presentation/figures_30to45min/cross_sections/
    cross_section_pit_616591_72m_az172_w2p0.png
    cross_section_pad_621594_357m_az5_w2p0.png
    cross_section_venango_41p484384N_79p518911W_622593_200m_az90_w3p0.png
```

Nothing approaches the 100 MB threshold. Intermediate height-above-ground clouds
go to the system temp directory and are deleted.

## Related

- `docs/iterations/ground_reclassification_pit_depth.md` — the pit-bridging
  hypothesis, tested and rejected.
- `literature/CITATIONS.md` — USGS 3DEP Lidar Base Specification, added in the
  same change for the QL2 accuracy bar and the ASPRS vegetation bands.

---

## Update 2026-09-19 — the census, and what it changed

The sections above rest on seven map squares per delivery. Seven cannot separate
"this vendor does it" from "this batch of flights does it", so the measurement
was re-run on every map square. Both passes are in
`docs/analysis_log.md` under 2026-09-19.

**Six squares were being counted twice.** The first census globbed `*.laz` files
rather than map squares. Four squares under `data/_source/lidar/westernpa/` are
byte-identical copies in `separate_sections/test_section/` — md5-confirmed, and
already flagged with zero references in
`docs/_ledgers/duplicates_proposed_moves.csv`, though the `_dupe` renames it
proposes have not been applied. Two more (`17TPF621594`, `17TPG619600`) have a
`.copc.laz` cloud-optimised re-encoding sitting beside the plain `.laz` of the
same tile. Both scripts now pick one file per square via `unique_tiles()`.

Every total below is the corrected, per-square one. The counts in the first
version of this run were 264 files / 183 squares / 167 with the cliff.

**It is one batch of flights, not a county and not a convention.**

| flight block | squares | ground stops | widest flown | with the cliff | at-ground returns lost |
|---|---|---|---|---|---|
| **Venango, March 2020** | **177** | **18.0°** | 19.6° | **165 (93%)** | **190,855,059** |
| Venango, November 2019 | 16 | 30.0° | 30.0° | 0 | 0 |
| McKean, April 2019 | 59 | 29.0° | 29.0° | 0 | 0 |
| Venango, 2011 | 6 | — | — | — | excluded, records no scan angle |

The same county flown four months apart behaves completely differently. The
November block sweeps wider (30° against 19.6°) and classifies ground all the way
to the edge of it. So the cut tracks the flight job — the sensor configuration
and the processing run that went with it — not the terrain, the county, or the
industry.

Every one of the 165 affected squares cuts at **exactly 18°**, range 18–18. A
threshold that repeats to the bin across 165 independently processed squares is a
line in a script, not an accuracy limit.

The 12 squares inside the March-2020 block that have *no* cliff are the ones
flown with the wider sweep, and they classify ground to the edge like the
November block does. That is the explanation agreeing with itself rather than an
exception to it.

### Reproduce

```
python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_all_tiles.py --workers 6
python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py --all --workers 6
python notebooks/wellsight_v2/s7_analysis/_scan_angle_cliff_across_acquisitions.py --all --redraw
```

The third redraws the figure from the CSVs without re-measuring — the census
costs about 90 minutes and figure edits must not.

### Outputs added by this pass

```
data/9t/results/nonground_classification/
    scan_angle_ground_stops_all_tiles.csv        257 squares, cheap statistic
    scan_angle_cliff_by_acquisition_all_tiles.csv 258 squares, full statistic
    scan_angle_rate_curves_all_tiles.csv          per-bin curves, redraw input

docs/presentation/figures_30to45min/scan_angle/
    ground_classification_cliff_by_acquisition_all_tiles.png

docs/presentation/figures_30to45min/report_lidar_ground/
    chart_1_the_cliff.png        now all 177 squares, not one
    chart_2_two_surveys.png      one row per flight block
```

### Open

`data/_source/lidar/westernpa/separate_sections/test_section/` holds four
duplicate source tiles. `tools/find_duplicates.py` has already proposed the
`_dupe` renames and `tools/apply_moves.py` would apply them reversibly. Not
applied here — that is a change to source data and belongs in its own pass.
