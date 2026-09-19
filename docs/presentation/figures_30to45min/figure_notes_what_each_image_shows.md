# What each figure shows

Nine figures for the new sections of the 30-45 minute talk. Companion to
`docs/presentation/presentation_update_worklist_30to45min.md`, section 6.

Everything here is drawn from data on disk. The only schematic is the pipeline
diagram. No number in any figure was typed in by hand except the two classical
AUC values, which are cited below.

Rebuild all nine with:

```
python docs/presentation/figures_30to45min/_build_presentation_figures.py
```

Palette is the light-mode categorical set, validated all-pairs before use
(worst CVD delta-E 9.2, worst normal-vision delta-E 24.0). Blue is train, orange
is val, aqua is test, grey is neither. Sequential ramps are single-hue.

---

## 1. `locator_study_areas_pa.png`

**Slide:** revised slide 6, Study Area.

Three panels. **a** is the six Venango County tiles in EPSG:6346, with 9t in blue
and 613590 in orange because those two carry every trained model. 616593 sits
inside 613590 — that nesting is real, not a drawing error. **b** is the McKean
tile on its own, because it is 80 km northeast and putting it in panel a
collapses the Venango cluster to a smudge. **c** is a table of all seven areas:
CRS, resolution, grid size, extent, and centre longitude/latitude.

Every bound comes from the DEM header on disk. There is no basemap — cartopy and
contextily are not installed and no state or county boundary shapefile is in the
repo — so the panels are plain projected coordinates and panel c carries the
geographic reference instead.

**Reads:** seven tiles across two counties at two resolutions, and only two of
them are fully modelled.

## 2. `pipeline_diagram_classical_and_unet_branches.png`

**Slide:** Act II, slide 9. **NEEDS REDRAWING.** The outline cut the classical
branch on 2026-09-17, so the two-branch schematic below no longer matches the
talk. Redraw as one path: point cloud, ground classification, DEM, derivatives,
annotation, the 7-channel stack, the block split, the three U-Nets, probability
rasters.

A schematic, not measured. One shared base — 3DEP QL2 point cloud, ground
classification through PDAL, DEM at 0.5 m and 1 m, then the terrain derivatives.
Derivatives and hand annotation both feed two branches. Branch A is the May
work: mean 17x17 m pit template, NCC scan to ~628k candidates, 48 features,
XGBoost + LightGBM + HistGB with spatial CV and isotonic calibration, ending at
ROC-AUC 0.905 and PR-AUC 0.212. Branch B is everything since: the 7-channel
stack, the 12x12 spatial-block split, the pit/pad/road U-Nets, 5-fold CV and the
nine-threshold held-out sweep, ending at probability rasters.

The AUC pair is carried over from the existing slide 12. Nothing else on the
diagram is a measurement.

**Reads:** the deck's four-step story is now one of two branches, and both score
against the same hand annotation.

## 3. `annotation_growth_pits_9t.png`

**Slide:** new, Act II.

Stacked bars for the three annotation versions, split by train/val/test and
"outside 9t". Sources:

| version | manifest | total | train | val | test | outside 9t |
|---|---|---|---|---|---|---|
| ann426, 2026-06-10 | `qgis/annotations/_history/_backup_pit_ann426_2026-06-10/pit_dataset_manifest.csv` | 426 | 298 | 63 | 65 | 0 |
| ann527, 2026-09-04 | `qgis/annotations/_history/_backup_pit_ann527_2026-09-04/pit_dataset_manifest.csv` | 527 | 330 | 72 | 69 | 56 |
| ann712, current | `data/9t/derived/05/pit_dataset_manifest.csv` | 712 | 352 | 77 | 74 | 209 |

**This figure answers blocker B2 in the worklist.** The manifest's "unused" rows
are not pits the greedy fill skipped. They are rows with a null `block_id` — pit
floors that fall outside the 9t tile entirely. Verified directly: all 209 current
"unused" centroids lie outside 619500-624000 E, 4593000-4597500 N, spanning
613899-700410 E, which is the other Venango tiles plus McKean.

So the reconciliation is **712 annotated pit floors project-wide, 503 of them
inside 9t**. The slide should say it that way.

**Reads:** every expansion reassigns the split, so no earlier checkpoint stays
held-out. That is the honest setup for the stale-numbers problem.

## 4. `split_blocks_12x12_9t.png`

**Slide:** new, Act IV, the spatial-block splitting slide.

Source: `data/9t/derived/05/pit_blocks_9t.gpkg`, layer `blocks`.

**a** is all 144 blocks coloured by split, each labelled with its pit-floor count.
Blank blocks hold none. **b** is the payoff: share of blocks against share of pit
floors, per split.

| split | blocks | pit floors |
|---|---|---|
| train | 77 | 352 |
| val | 14 | 77 |
| test | 24 | 74 |
| unused | 29 | 0 |

Note that val gets 14 blocks and test gets 24, yet they hold 77 and 74 pits.

**Reads:** pits cluster, so balancing block count would give a "70%" train split
holding the wrong share of the data. This is the one-slide justification for the
greedy fill on feature count.

## 5. `classical_vs_unet_pits_9t.png`

**Slide:** NONE. **Unused as of 2026-09-17.** The outline cut the classical
branch, so the slide this served no longer exists. The figure is kept on disk
because it is good and because deleting a correct, reproducible figure to tidy up
is the wrong trade. Do not manufacture a reason to show it.

The same 400 x 400 m window, two branches. **a** is the classical ensemble's
scored candidates from `data/_results/candidates/candidates_pits.gpkg` — 180 in
this window, with size and colour both carrying `confidence_score`. **b** is
`data/9t/models/pit/unet_v2/pit_prob_floor.tif`, masked below the 0.20 operating
threshold. Green outlines on both panels are the 14 hand-annotated floors from
`qgis/annotations/annotations_proj.gpkg`, layer `pit_inside`. Basemap is
`hillshade_9t_05.tif` at 0.5 m.

The window is not hand-picked. It is the densest 400 m box, found by a 50 m-step
search over annotated floor centroids inside the candidate extent.

**Reads:** the classical branch scatters 180 candidates across the scene and its
high-confidence ones do land on annotated pits, but plenty do not. The U-Net puts
tight blobs on the floors and almost nothing elsewhere. Count the green outlines
without a blue blob to see what 0.20 still misses — that is the threshold
conversation, on screen.

## 6. `nisar_radar_10m_9t.png`

**Slide:** new, Act V, the NISAR slide.

Three panels from the granule downloaded this week:
`data/_source/reference/nisar/9t/NISAR_L2_GCOV_BETA_V1/NISAR_L2_PR_GCOV_010_162_A_023_4005_DHDH_A_20260120T101554_20260120T101629_X05010_N_F_J_001.h5`

**a** co-pol HH gamma-0, median -8.1 dB. **b** cross-pol HV, median -16.2 dB.
**c** HH minus HV, median 8.0 dB, which is a sound forest signature.

Read straight from `/science/LSAR/GCOV/grids/frequencyA`, converted to dB, and
clipped to the 9t bbox: 450 x 450 px at 10 m out of a 36,216 x 35,784 px swath.
**9t is 0.016% of the granule area** — the caption says so, because that ratio is
the actual NISAR story for this project.

These medians independently reproduce the June reconnaissance figures logged as
HH -8.2, HV -16.3, HH-HV 8.1 dB. The June clips were deleted; this is a fresh
granule and it agrees to 0.1 dB.

**Reads:** GCOV is usable over PA at 10 m. Pair it with the GUNW coherence of
0.14 from the log to make the point that L-band InSAR subsidence does not survive
Pennsylvania canopy.

---

## 7. `annotation_schema_pad_and_pit_9t.png`

**Slide:** new, Act II slides 2-3. The schema, and why floor/rim/full are three
layers.

Two panels over `hillshade_9t_05.tif` at 0.5 m. **a** is one pad with its floors
and its access road, labelled directly. **b** is the largest depression on that
pad with all three pit layers drawn.

Nothing is hand-picked. The pad is the one lying entirely inside 9t with the most
annotated floors, ties broken by area. The pit is the `pit_outside` polygon on it
with the largest area.

A fact the figure surfaced: **no pad in 9t carries more than two annotated pit
floors.** 995 pads hold 712 floors. If you expected a pad to be a cluster of
pits, it is not, and the slide should say so.

Selected: pad 896, 0.41 ha, 2 floors. Target depression 255 m2, its floor 63 m2.
Panel b shows both of the pad's floors, so the "one object, two annotations"
problem is visible rather than described.

Layer counts in the legend are live from the gpkg, not typed.

**Reads:** a point can only be right or wrong about where this is. A polygon can
be right in the wrong place, the right place at the wrong size, or one object
split in two. That is the whole argument for Act II.

## 8. `threshold_sweep_9t.png`

**Slide:** new, Act IV. The headline pair. Currently one row in one table.

Sources, all three read directly:

```
data/9t/results/pit/thresholds/pit_threshold_found_vs_missed_summary_9t.csv
data/9t/results/pad/thresholds/pad_threshold_sweep_9t.csv
data/9t/results/road/thresholds/road_threshold_sweep_9t.csv
```

**a** is flagged area as a share of the 2,025 ha tile, log scale because pit and
pad are two orders of magnitude apart and a linear axis hides the pit curve
entirely. **b** is recall on withheld hand annotation. Dots mark the operating
points: pit 0.20, road 0.20, pad 0.45.

| task | flagged at the operating point | recall there |
|---|---|---|
| pit floors | 4.33 ha = 0.21% | 126/127 rims = 0.992 |
| roads | 101.65 ha = 5.02% | 0.982 `recall_clean` |
| pads | 235.77 ha = 11.64% | 0.918 at IoU >= 0.30 |

Two honest caveats are on the figure. The pit sweep was only run at four cutoffs,
0.20-0.50, so its lines are short; road and pad ran at nine. And the pad recall
curve **falls off below 0.35** rather than rising, because pad predictions merge
into tile-spanning blobs at low cutoffs and no merged blob clears IoU 0.30. That
dip is a real property of the metric, not a plotting error.

**Reads:** a crew searches 0.21% of the tile and finds 126 of 127. The pad model
needs 55x the ground to find fewer of its targets, which is the cleanest way to
name the weak model without arguing about F1.

## 9. `annotation_growth_pads_9t.png`

**Slide:** new, Act II slide 5, beside the pit growth chart.

| version | manifest | total | train | val | test | in 9t unassigned | outside 9t |
|---|---|---|---|---|---|---|---|
| plat650, 2026-08-06 | `qgis/annotations/_history/_snapshot_plat_artifacts_2026-08-06/plat_dataset_manifest.csv` | 650 | 456 | 101 | 93 | 0 | 0 |
| pad995, 2026-09-04 | `qgis/annotations/_history/_backup_pit_ann527_2026-09-04/pad_dataset_manifest.csv` | 995 | 397 | 100 | 87 | 66 | 345 |
| pad995, current | `data/9t/derived/05/pad_dataset_manifest.csv` | 995 | 401 | 69 | 114 | 66 | 345 |

The figure splits "unused" into its two real states, which the pit version does
not need to. A null `block_id` means the pad is outside 9t. An in-tile pad is
also unused when the greedy fill left its block out of every split. Pads have 66
of the second kind and pits have none.

The point of the third bar is that **it holds the same 995 pads as the second**.
Only the block split moved, and test went 87 to 114 while val went 100 to 69 with
no new annotation at all. That is the B1 hazard in one picture, and it is more
convincing than the pit version because the count is held fixed.

650 pads are inside 9t, of 995 project-wide. Not 584 — that number counts
only the 584 in a split and drops the 66 unassigned in-tile pads.

**Reads:** a checkpoint scored against the middle bar is not held out under the
right one.


---

## Not built

Two things in the figure set are thinner than the others and worth knowing about.

- **The pit U-Net quantitative slide has no figure here.** Blocked on worklist
  blocker B1, which is being cleared: `_pit_unet_cv5.py` and `_pad_unet_cv5.py`
  are retraining on ann712 as of 2026-09-17. Build it from
  `pit_cv5_per_fold_9t.csv` once the pooled numbers land.
- **The road figures were not rebuilt** because usable ones already exist. Use
  `data/9t/models/road/unet_1m_corrected/compare_corrections_full.png` and
  `compare_corrections_zoom.png` as they are.
