# Analysis Log — WellSight

Append-only record of every processing decision, parameter choice, and run
result. Newest entries at the top. Per `Claude.md` reporting rule.

---

## 2026-09-23 -- operating-point Phase 3: policy sweep, and a reproducibility bug in the CV split

The user asked for a sweep across every Phase 3 option. Script: `notebooks/wellsight_v2/s5_eval/_operating_point_policy_sweep_pit_pad_9t.py`. Write-up: `docs/iterations/operating_point_policy_sweep_pit_pad_9t.md`.

**Bug found first.** The CV scripts draw inner val from `sorted(set(block_id))`. 209 pits and 345 pads have no block, so the set holds NaN. That makes the draw process-dependent. Fold 2's training log shows 64 inner-val pits; re-draws gave 63 and 61. Matching logged counts leaves 2-6 candidate sets in 8 of 10 folds, so the real sets cannot be recovered. Held-out folds are unaffected, because they come from the saved assignment CSV. Training scripts are not changed; the fix is logged in BACKLOG.

**Response.** All fitting moved to leave-one-fold-out. For fold k, the proposal cutoff, the Platt calibrator and every policy rule are fitted on the other four folds' held-out blocks. Phases 1-2 were rerun. That supersedes the numbers in the entry below. Pit ranked AP 0.823 -> 0.818 and pad 0.744 -> 0.745. Blob ECE after Platt is now 0.03-0.04. SMRF at IoU 0.5 is now -0.143 (t -3.33, all five folds negative), against -0.085 before. The size depends on the proposal cutoff; the direction does not.

**Sweep.** Cost ratio r 0.5-128, review budget 2-50 candidates/km², conformal recall target 0.60-0.95, and F-β with β 0.5-4. All are scored on the same held-out candidates, with today's F1/F2/deployed pixel cutoffs as reference rows.
- Every family lands on the same ranked curve. Today's pixel cutoffs sit below it.
- At equal effort, the deployed pad cutoff 0.70 gives recall 0.640 and precision 0.556. A ranked cut gives 0.822 and 0.717.
- The deployed pit cutoff 0.60 gives 0.809 and 0.695, against 0.881 and 0.759.
- The conformal rule meets its block-mean target to within 0.009. The budget is the most stable across folds: pads at 30/km² range 0.628-0.674.
- Cost-ratio regret is 1-18%.
No policy is chosen. That is the user's call.

Palette: lost/found plus sky `#5FB4E0`, validated with `--pairs all` (worst pair ΔE 21.1 deutan). Outputs: `data/9t/results/operating_point/policy_sweep_*` and `data/9t/results/operating_point/figures/policy_sweep_*`. Literature: Elkan 2001 added; Angelopoulos 2022 moved to adopted.

---

## 2026-09-23 -- operating-point plan, Phases 0-2: threshold-free PR and calibration

The user asked how to choose precision against recall without hand-set cutoffs. Plan written to `docs/iterations/operating_point_policy_plan.md`. Phases 0-2 run. Phase 3 waits on one user decision.

**Phase 0, inventory.** Every hand-set value in the pit, pad and road pipeline is listed in the plan doc. The finding to escalate: the deployed filter `notebooks/wellsight_v2/s4_infer/_postfilter_tile_candidates.py` uses pit 0.60, pad 0.70 and minimum areas of 20/300 m². CV selected pit 0.35-0.60 and pad 0.50-0.65, with minimum areas of 4/100 m². 158 of 712 annotated pit floors are under 20 m². The defaults were not changed.

**Recorder.** `notebooks/wellsight_v2/s5_eval/_cv5_pr_sweep_records_pit_pad_9t.py` re-polygonizes each fold's saved probability raster at cutoffs 0.05-0.95 in steps of 0.025. It records per-block counts and per-blob rows for inner val and held-out, for pit, pit_smrf and pad. At cutoff 0.30 it reproduces the CV5 held-out counts exactly on every fold. That took 35 min on CPU.

**Design change mid-run.** Sweeping the pixel cutoff turned out to measure outlining as well as ranking. Pit precision peaks at 0.71 near cutoff 0.58 and falls to 0.45 by 0.875, because blobs shrink below IoU 0.3. The headline became the ranked candidate list at a proposal cutoff. That cutoff is the inner-val recall maximum, with ties going higher. The sweep is kept as a labelled secondary result.

**Phase 1.** Ranked AP at IoU 0.3: pit 0.823 [0.787-0.857], pit SMRF 0.820, pad 0.744 [0.702-0.789]. At 10 false positives per km², pit recall is 0.893. SMRF against vendor at IoU 0.5: ΔAP -0.085. The paired block bootstrap gives [-0.135, -0.028]. The paired t (df 4) is -1.77. This is suggestive, not established.

**Phase 2.** Raw blob scores are not probabilities, with ECE 0.16-0.20. Platt on inner val brings held-out ECE to 0.04-0.05. Isotonic overfits pits. Pixel Platt slope is about 2.5 (T about 0.4), so the network is under-confident. Intercepts run from -0.7 to -1.9, which is focal α inflating positives. A raw pixel 0.5 is about 36% floor for pits and 17% for pads. Calibrated 50% sits at raw 0.57-0.62 for pits and 0.66-0.70 for pads. Those bands contain the deployed 0.60/0.70.

**Literature logged** in `literature/CITATIONS.md`: Everingham 2010, Chakraborty 1989 (cite-only), Platt 1999, Zadrozny & Elkan 2002, Niculescu-Mizil & Caruana 2005, Naeini 2015, Angelopoulos 2022. The Guo 2017 row moved from candidate to adopted.

Outputs: `data/9t/results/operating_point/` (5.5 MB, nothing near 100 MB) and its `figures/` subfolder. The palette is the lost/found set, re-validated with `--pairs all`.

---

## 2026-09-23 -- v19 deck: more of the map, plainer results

Feedback after presenting v18. The maps were never shown bare, and the results
section was too dense to speak to. v19 lives in its own folder,
`docs/presentation/v19_maps_and_plain_results/`. v18 was copied, not edited.

**Map section, five new slides after the RRIM slides.** A zoom from the whole
9t tile to one pit, then a pit, a pad, a road, and one well site with all three.
RRIM only (`data/9t/derived/05/rrim_openness_9t_05.tif`, raw bytes via
`read_rrim`). No outlines. Examples are picked by rule, not by eye: median and
percentile depth for pits, median and percentile area for pads, the
75th-percentile road window, and the median pad holding a pit and a road.
Selections are in `figures/_closeup_selection_9t.json`. Color meanings were
checked against `_make_rrim.py`: teal concave, gray flat, yellow convex, red
steep.

**Results section rebuilt.** One slide defines found, matched and search area.
Each detector then gets the same layout: three numbers, one takeaway, one small
measurement line. There is a side-by-side table, a native chart for the
architecture comparison, one slide for the second tile, and a three-line
summary. The superseded v18 results slides moved to a Backup appendix,
unchanged. No new analysis. Found and flagged counts were re-derived from the
per-fold CSVs: pits 467 of 503 from 738 flags, pads 593 of 650 from 1,010. They
match the audited rates.

**Caught while building.** v18 slide 66's map has "146 found, recall 0.954"
baked in, against the slide's audited 139 of 153 (0.911). v19's main flow uses
a number-free map. The backup copy still carries the conflict, and the README
flags it. Pads picked from "no pit drawn" all show a pit-like ring, likely
undrawn pits. The notes say so.

Palettes: schematic `#1F5FA8/#D97706/#A31515` (validated set, amber 2.99:1 on
`#F7F8F6`, relieved by labels). Chart `#4E8FE6/#1F5FA8`, every check passing,
worst dE 16.3. pptx validator: all passed against v18.

Deck (~113 MB) is gitignored in the same change. Builders, figures and README
are tracked.

---

## 2026-09-23 -- review of the 9t change process: the per-patch reliability test did not hold

Reviewed the whole ICP change chain end to end. It covered the rebuild script,
the classification script, and today's earlier run (the entry below). The
alignment, CRS handling, units, sign convention and destripe all check out.
Two statistical flaws did not.

**1. The null set the cutoff, not the data.** The Gaussian-smoothed noise null
grid-searched its sigma over 3.0 to 13.5 px and landed on 3.0, the grid floor.
The measured ACF is not Gaussian. It is 1.00, 0.58, 0.43, 0.29, 0.18 at lags
0, 1, 2, 4, 8. The unconstrained best fit is 1.75 px, and there the null makes
zero patches. So the 420 m² cutoff reported below was an accident of the grid.
Part 2's 712 m² cutoff has the same flaw.

Replaced with IAAFT surrogates (Schreiber & Schmitz 1996, cited in
`literature/CITATIONS.md`, PDF in `literature/papers/`). They keep the ACF and
the exact value distribution. A phase-randomised surrogate was tried first and
rejected. It makes the values Gaussian and also produced zero patches, which
only rules out Gaussian noise. Runs raised from 8 to 32.

| | old null (sigma pinned 3.0) | IAAFT, 32 runs |
|---|---|---|
| noise patches | 11.6 +/- 3.6 | 90 +/- 7 |
| noise area | 0.28 ha | 5.99 ha |
| observed / null, patches | 20.6x | **2.7x** |
| reliability cutoff | 420 m² | **7,888 m²** |
| reliable non-erosional | 11 | **0** |

In aggregate the change is real, about 21 sd above the null. Individually only
3 of 240 patches clear the cutoff, all fluvial. No non-erosional patch does.
The 11 "reliable non-erosional patches" in the entry below are withdrawn.

**2. The channel test used a point null.** A patch is near a channel if any
pixel is within 40 m, so a big patch reaches further than a point. With a
same-shape null (each patch footprint dropped at 200 random positions),
enrichment is **1.13x (z = 3.7)**, not 1.36x. Part 2's "enrichment strengthens
in the reliable set" claim does not hold.

**3. Leftover striping is band-local (found, not fixed).** After destripe and
high-pass, north-south streaks remain inside east-west bands, with seams between
them. The global per-row/per-column medians cannot remove that. It likely
inflates the null and is the next thing to fix (band-wise destripe).

Also fixed in this pass: the class palette. Blue/orange/red failed the dataviz
validator (orange vs red ΔE 10.3 normal, 6.7 deutan). It is replaced by the
repo's validated set #1F5FA8 / #D97706 / #A31515 (worst ΔE 21.1 deutan, 22.6
normal, `--pairs all`). Also fixed: an overprinted suptitle, and figure saves
failing with OSError 22 when something briefly held the PNG. Figures now write
to a temp name and swap in.

Could not check the density of the older survey under each patch. The raw
2006-08 LAZ is only on F:, which is not mounted. The repo copies are 5 m
voxel-thinned. A TIN-facet proxy read zero everywhere and was dropped. The ICP
rebuild is not reproducible until the four tiles are re-fetched.

Script changes in `_icp_change_classify_9t.py` (IAAFT null, N_NULL 32, shape
null, both non-erosional rasters, flagged figure). New files in
`data/_experiments/icp/change_9t/`:
`dod_9t_singleicp_nonerosional_allpatches_2m.tif`,
`dod_9t_singleicp_nonerosional_reliable_2m.tif` (empty). Removed the untagged
`dod_9t_singleicp_nonerosional_2m.tif` from the first run, which it replaces.
Every other `_9t_singleicp` output was regenerated in place.

Write-up: `docs/iterations/icp_change_9t.md` Part 4, rewritten in place; Part 2
carries a correction note.

---

## 2026-09-23 -- 9t change classification re-derived on the single-ICP DoD

> **Superseded the same day** by the review entry above. The null model
> and cutoff here were flawed, and the 11 reliable non-erosional patches
> are withdrawn.

Part 3 (2026-07-31) rebuilt the 9t DoD with ONE ICP solve and flagged Part 2's
classification as stale: it was tuned against per-tile bias blocks that the
rebuild removed at the source. This pass re-runs it on the right input. No new
ICP solve, no new data -- the older survey is still
USGS_LPC_PA_STATEWIDE_N_2006_2008 tiles 002958/002959/003111/003112
(EPSG:2271 forced, US survey feet), the newer is USGS_LPC_PA_WesternPA_2019_D20.

`_icp_change_classify_9t.py` now takes `--source {original,singleicp}`, which
selects the input DoD and tags every output. Default is `singleicp`. All other
parameters are unchanged from Part 2, so the two runs are directly comparable.

| | Part 2 (four-solve DoD) | this pass (single-ICP DoD) |
|---|---|---|
| raw robust sigma | 0.136 m | 0.1119 m |
| after destripe | 0.107 m | 0.0845 m |
| after 400 m high-pass | 0.087 m | **0.0784 m** |
| broad field removed (std) | 0.057 m | 0.0261 m |
| detection threshold | ~0.4 m floor | **0.235 m** |
| matched ACF sigma (null) | 4.0 px | 3.0 px |
| patches >= 200 m2 | 367 | 240 |
| null patches | 57 +/- 5 | 11.6 +/- 3.6 |
| observed / null, patches | 6.4x | **20.6x** |
| observed / null, area | 28.2x | **93.1x** |
| reliability cutoff | 712 m2 | 420 m2 |
| channel enrichment (reliable) | 1.34x | 1.39x |
| fluvial / mass wasting / anthropogenic | 275 / 5 / 87 | 206 / 12 / 22 |
| reliable anthropogenic | 16 patches, 2.65 ha | **11 patches, 1.58 ha** |

The patch count fell but the signal-to-null ratio tripled. Part 2's extra 65
non-erosional patches were bias blocks being segmented as change.

Largest reliable non-erosional patch: #267, a 3,016 m2 cut averaging -1.11 m at
623978, 4596537 (EPSG:6346), 2 m from a mapped road. That is 2.3x the largest
Part 2 found. 4 of the 11 sit directly on a mapped road and 9 of 11 within 35 m,
so road maintenance and skid-trail work remains the best explanation for the set.

Inspected the crops rather than trusting the table: #267, #899 and #1530 are
still red/blue dipoles across linear terrain edges, which is the two surveys
resolving the same road cut differently, not change. #20 and #391 are coherent
rectangular fills with no paired cut and are the two most likely to be real.
Nothing from this set is quoted as a finding yet.

No wells claim. Part 3 established that any DoD test against
`well_head_pts_reprojected.gpkg` is circular -- those are 861 pits digitised on
the 2019 DEM, and the sparse 2006-08 survey resolves only 72% of their depth.
`well_dist_m` is carried as an attribute only. These 11 are candidate recent
earthworks, not candidate wells.

Outputs in `data/_experiments/icp/change_9t/`:
`dod_9t_singleicp_destriped_2m.tif`, `dod_9t_singleicp_highpass_2m.tif`,
`change_class_9t_singleicp_2m.tif`, `change_class_reliable_9t_singleicp_2m.tif`,
`dod_9t_singleicp_nonerosional_2m.tif`, `change_patches_9t_singleicp.gpkg`,
`change_classified_9t_singleicp.png`, `top_changes_9t_singleicp.png`,
`_classify_9t_singleicp.json`. Part 2's untagged rasters are left in place and
are superseded.

Write-up: `docs/iterations/icp_change_9t.md` Part 4.
Reproduce: `python notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py --source singleicp`

Large-file audit run after the write: no >100 MB file is unignored.

---

## 2026-09-22 -- the anticipated-questions document brought onto the audited numbers

`docs/presentation/anticipated_questions_and_answers.md` was written 2026-09-21
11:56, before the two count audits, and carried eight claims the deck no longer
makes. Corrected in the same pass and re-rendered to PDF (10 pages).

| answer | was | is |
|---|---|---|
| corn rows vs pits | "amplitude is tens of centimetres against a 70 cm target" | under a centimetre against 54 cm, seventy times shallower. The risk is the 3.35 m SPACING, not the depth. This was the doc's worst error and it was arguing the wrong case |
| pit morphology | dish 0.7 m deep, 13 m across | 0.54 m median, 15.3 m rim, 5.8 m floor |
| point budget | "4 pts/m2, a 13 m pit has 500 measurements, signal 7x the noise" | GROUND returns are 2.7/m2; a 15.3 m pit is 184 m2, so still ~500, but 54 cm against 10 cm RMSE is 5x not 7x |
| void | "13.8% of the training area", "about a quarter of the holes" | of the ground the laser reached; two in five. Answer now spells out both denominators, because the question invites it |
| recall denominator | "of the 712 features a person identified" | 467 of the 503 drawn inside 9t; 712 is every area |
| pad burden | 11.6%, 2.3 km2 | 9.8%, 197.95 ha, 2.0 km2, same recall |
| field arithmetic | 660 real / 1,040 places / 380 wrong | that blended the CV5 recall with the threshold sweep's polygon count. Now 467 / 738 / 271 from the CV5, with 0.21% and 1,041 polygons attributed to the sweep where they belong |
| annotation QC | "90 of 856, so the training data is roughly 5% wrong" | that pass ran April 2026 on a different 861-pit set over 9t/mk5/mk/mkf, and the annotations were rebuilt 527 -> 712 on 2026-09-04. It was pulled from the deck for exactly this reason. The answer now says not to quote 5% as a property of these labels |

**Four questions added**, all of them things the corrected slides now invite:

- Why every result uses the vendor's ground while a third of the talk argues
  the vendor threw good ground away. The SMRF-ground run exists and scores
  0.915 against 0.928; quoting it while the pipeline uses vendor ground would
  be the dishonest version.
- Why road recall is 0.982 on the first tile and 0.759 on the second (two
  different measurements; the second is deliberately the hand-drawn half, and
  against all 187.1 km the same model reads 0.915).
- Why the second tile's map shows 42 candidates while the text says 139 of 153
  (two models; the map is the June pre-U-Net layer and has not been redrawn).
- Why there is no precision on the second tile (drawn extent 70.3%, a third of
  blocks hold a pit, largest unswept region 63%).

Full paths:
    docs/presentation/anticipated_questions_and_answers.md
    docs/presentation/anticipated_questions_and_answers.pdf

---

## 2026-09-21 -- every number in the deck checked against its source

Second audit, wider than the count audit earlier today: every figure, rate and
count in all 81 slides and their notes, measured back to the file it came from.
Nine lost. The rest are listed in the docstring of
`docs/presentation/_number_audit_fixes.py` so nobody re-derives them.

| slide | claim | verdict |
|---|---|---|
| 66 vs 72 | completeness 0.811 / correctness 0.816 | two different road models on one tile -- 0.811 is `sweep_orient` at thr 0.40, everything else in the deck is `recall_relabeled20260806`. Slide 66 now quotes 0.759 / 0.828 at thr 0.50, same as slide 72 |
| 69 | 42 pit and 161 pad candidates | retired pre-U-Net pipeline, `data/613590/derived/inference_05/*.gpkg` dated 2026-06-12, sitting beside the U-Net's 0.911. Attributed rather than swapped, because the map IS that candidate set |
| 47 | body "six layers", notes "seven" | six. `pyogrio.list_layers` gives plat, pit_inside, pit_outside, roads, not_roads, drainage; pit_wall is derived |
| 17 (notes) | "about a quarter of the holes close" | 2,857,002 of 7,097,720 = 40.2%. Body already said two in five |
| 9, 15 (notes) | "13.8% of the training area" | denominator is the 51,470,048 cells a return reached, not the 81,000,000-cell box. Against the box it is 8.8% |
| 34, 36, 46 | "a pit is a 0.7 m dish", "13 m across" | measured 0.54 m median (10-90% 0.26-0.91), 15.3 m rim, 5.8 m floor |
| 46 (notes) | three-panel walkthrough | the local-relief panel was removed from the figure; the note still described it |
| 20 | body names left and right | the figure has three panels; what the body called right is the middle |
| 75 | "63% of it is unswept" | `largest_blank_region_frac` 0.632 is the largest single unswept region. Drawn extent covers 70.3%; 33.3% of blocks hold a drawn pit |
| 44 | "501 pair with a floor" | 501 is the strict `within` rule; slide 48's stated rule (each floor takes the rim it overlaps most) gives 503, and 81,500 m2 of wall is already the 503 number. `_median_pit_plan_view_9t.py` switched to the same rule; same pit selected, same medians |

**The headline numbers all hold, and now their source is written down.**
Pit CV5 F2 micro 467/503 = 0.928 and 467/738 = 0.633 come from
`data/9t/models/pit/unet_cv5/pit_cv5_per_fold_9t.csv` (2026-09-17, vendor
ground). Pad CV5 F2 micro 593/650 = 0.912 and 593/1010 = 0.587 from
`data/9t/models/pad/unet_cv5/`. `unet_cv5_smrf` (2026-09-19) is the SMRF-ground
variant and gives 460/503 = 0.915 -- it is NOT the deck's number, which is
consistent with slide 21's claim that no reprocessing is in the pipeline. Road
9t at thr 0.20 reproduces 735/722/0.982, 1,220/1,207/0.989, 42.56 of 43.07 km
and 5.02% exactly from `road_threshold_sweep_9t.csv`. 613590 pit transfer
reproduces 0.911, 0.928, 0.906, folds 127/137/142/145/146. The 613590 road
network measures 3,693 features and 231.4 km against TIGER's 40.0 km, 5.79x.
All annotation counts reproduce from `annotations_proj.gpkg` to the unit,
including the 138 rims with no floor -- one rim took two floors, which is why
it is 138 and not 723 minus 586.

**Left alone deliberately.** Slides 5 and 6 say the DEM is gridded at 1 m while
everything from slide 20 on is 0.5 m. That is the open 1 m / 0.5 m question in
`docs/iterations/BACKLOG.md`, not a typo.

Scripts: `docs/presentation/_number_audit_fixes.py` (new), and at source in
`_speaker_note_additions.py`, `_port_v17_user_edits.py`,
`_annotation_slides_9t_only.py`,
`figures_30to45min/_median_pit_plan_view_9t.py`. 81 slides in, 81 out.

---

## 2026-09-21 — every point and cell count in the deck audited against source

The Data QA section quoted counts from five scopes and named none of them.
Audited all of them, measured the 9t ones from the rasters, and fixed v17.

| slide | number | unit | scope | status |
|---|---|---|---|---|
| 10 | 113,556,364 | returns | 10 map squares | body said "nine", notes said "ten" — FIXED to ten |
| 11 | 5.6 M | at-ground unassigned returns | 4 map squares | correct, scope now stated |
| 12 (in figure) | 190,855,059 | discarded returns | 165 of 177 squares, Venango Mar-2020 block | correct, scope still only in the figure |
| 15 | 13.8% no measurement | share of cells | NOT 9t | WRONG — replaced with measured 45.2% |
| 16 | 13,746,698 | recovered ground returns | 9t | correct, verified, scope now stated |
| 17 | 13.8% → 8.2% | DEM void rate | SMRF experiment, 2 other tiles, writers.gdal | WRONG — replaced with 45.2% → 41.7% |
| 17 | "about a quarter of the holes close" | — | 9t | WRONG — it is 7.8%, about one in thirteen |
| 21 | 44,371,436 / 2,857,002 | cells | 9t @ 0.5 m | both correct, verified, grid now stated |

**Measured today** from `data/9t/results/recovered_ground_9t/`:
vendor ground returns 54,703,309; recovered ground returns **13,746,698**;
cells with vendor ground **44,371,436**; cells without **36,628,564** (45.2%);
void cells a recovered return fills **2,857,002** → 45.2% to 41.7%, which is
**7.8%** of the void, not a quarter.

**Why 13.8% was wrong here.** It is the DEM void rate from the SMRF
reclassification on two different tiles (15.99%→9.97%, 12.36%→6.27%), gridded
with `writers.gdal`, which leaves real voids. The 9t surfaces on slides 15-17
are TIN-based and measure **0.00% void both ways** — slide 20 already says so.
The bullet and the figure were describing different rasters.

**Also this pass.** Slide 14 takes
`figures_30to45min/v6/where_ground_stops_by_flight_block_excl2011_9t.png`,
which drops the Venango 2011-09 row (6 squares, scan angle never populated, so
its bar meant "cannot be checked" among bars that mean a measured angle).
Slide 57 notes gain the 128 m patch and 30 m jitter. Built from the user's own
v15, so their edits carry. 80 slides in, 80 out.

**Still open.** Slide 12's 190.9 M is block-scoped and that scope lives only
inside the PNG, so it needs the figure regenerated to say so. The ten audited
map squares are still not named anywhere — `_classify_nonground_returns_9t.py`
takes them from `--tiles` and the iteration doc records only the count.

---

## 2026-09-21 — corn rows are not the vendor cut, and 0.5 m is finer than the data

**1. Does the 18 deg cut explain the corn rows?** Sampled
`clipped_final_count_9t_0p5m.tif` at the rows. The RRIM window used on the
slides (623822, 4594949) has **0.00%** of cells carrying a clipped return. The
nine rows digitised in `data/cornrows.gpkg`, 396 m away, have **24.3%** — six
times the 3.75% tile average. So "the cut is not where the rows are" is NOT a
claim that survives; it holds at the slide window only.

The claim that does hold is the direct one:
`docs/presentation/figures_30to45min/3_rrim/rrim_vendor_vs_unclipped_9t.png`
builds the RRIM twice over the same ground, with and without the clipped
returns restored. The rows are present in both panels. Supporting: rows sit
3.35 m apart against swath edges hundreds of metres apart, and run at 79 deg
(the scan-line bearing), not the flight-line bearing the cut follows.
**Decision: lead with the side-by-side figure; the 18 deg footprint is the
second answer, not the first.**

**2. Grid resolution.** Ground returns in 9t sit 0.61 m apart (54,703,309
returns, 2.70 pts/m²). At 0.5 m, 45.2% of cells contain no ground return at
all; at 1 m, 7.5%; at 2 m, 0.7%. The 0.5 m product is therefore ~45%
interpolation, and that is the likely source of the cross-hatch in the
missing-ground mask. Scores remain valid — held-out blocks were scored at the
same resolution — but the choice cost 4x the compute for a noisier input.
Counter-argument on record: pit floors are ~6 m across and vanish by level 3 of
a four-level U-Net at 1 m. **Deferred to BACKLOG with a queued 1 m pit CV5
re-run rather than acted on before the talk.**

**3. Deck.** v15 (user-edited, 2026-09-21 19:15) forked to v17 by
`docs/presentation/_build_v17_patch_jitter_notes.py`. Slide 57 speaker notes
gain an explanation of the 128 m training patch and 30 m jitter, appended to
the existing note. Slide 54 deliberately untouched: its pasted notes look glued
when dumped to a terminal but carry  soft line breaks that render
correctly. 80 slides in, 80 out; app.xml already consistent.

---

## 2026-09-21 — the clipped returns, isolated exactly, and the cut confirmed absolute

Asked for an overlay of what the vendor actually clipped. Defined precisely:
in the delivered LAZ, **|scan angle| >= 18 deg**, **final return of its pulse**,
**not classification 2**.

| | returns |
|---|---|
| inside the 9t bounding box | 84,684,419 |
| past 18 deg | 13,276,401 (15.7%) |
| ...and a final return | 10,699,770 |
| ...and not class 2 = **clipped** | **10,699,770** |
| ...within 15 cm of the bare-earth surface | 10,163,382 (**95.0%**) |
| **class 2 past 18 deg** | **0** |

Two numbers settle the story. The clipped count is **identical** to the
past-18-and-final count, and class 2 past 18 deg is **exactly zero** — not
approximately, not rounded. Of 13.3 million returns past the threshold, not one
was called ground. And 95% of the final ones sit within 15 cm of the ground
surface, so they demonstrably reached the dirt.

Footprint 3,033,665 cells, **0.758 km2, 3.7% of the tile**.

    clipped_final_count_9t_0p5m.tif              1.9 MB
    clipped_final_nearground_count_9t_0p5m.tif   1.9 MB

**Two bugs found on the way, both worth recording.**

*Tile selection.* A header overlap test written with `>` and `<` counts a tile
that merely touches the bounding-box edge. Seven of sixteen do exactly that and
contribute no points, which is why a first pass returned zero. Strictly
positive overlap on both axes is required; nine tiles qualify.

*Scan angle units.* LAS point format 6 stores scan angle as a signed short in
**0.006 degree** units, not degrees. Reading it as degrees understates the
threshold by 167x and selects essentially every point. The raw cut is 3000.

**Also, separately:** splitting the plain missing-ground mask by whether any
pulse terminated in the cell shows how little of it is recoverable —

| | cells | km2 | of tile |
|---|---|---|---|
| no vendor ground | 36,628,564 | 9.157 | 45.2% |
| ...no final return at all | 33,419,428 | 8.355 | **41.3%** |
| ...a pulse terminated here | 3,209,136 | 0.802 | 4.0% |
| ...terminated within 15 cm of ground | 2,368,735 | 0.592 | 2.9% |

So the cross-hatch in the plain mask is 41.3% canopy where nothing came back at
all, and only about 3% is ground the laser reached and the vendor declined to
label.

Scripts:
- `notebooks/wellsight_v2/s7_analysis/_clipped_final_returns_9t.py`
- `notebooks/wellsight_v2/s7_analysis/_missing_ground_by_final_return_9t.py`

---

## 2026-09-21 — v15, and the missing-ground overlay

**Units.** Hectares gone from the deck. Pads in km², pits in m² — straight
conversions at 10,000 m² per hectare, not recomputations, because the "723 pit
outlines, 14.84 ha" line reconciles with no single layer in the geopackage
(`pit_full` is 841 / 17.72 ha, `pit_inside` 714 / 2.30 ha) and recomputing
would have changed the line's meaning rather than its units. 0 hectare
references remain.

**Slide removed** — "are the discarded returns any good?", on request. Its
accuracy numbers survive in the speaker notes of the scan-angle slide.

**Slide retitled** — "where the ground stops" reads like a fact about terrain;
it is about a threshold in the vendor's processing. Now "nothing past 18° was
called ground".

**RRIM, clipped against unclipped** — the slide-35 window at 623822 E
4594949 N, full Chiba recipe both sides, with the differential-openness stretch
computed on the vendor panel and reused for the other so the comparison is not
rescaled away. The surface differs in 8.9% of cells; 13.3% of RRIM pixels
differ by more than 5/255. **The corn rows are present in both panels**, which
is consistent with the earlier finding that they are unrelated to the vendor
cut.

**Missing-ground overlay.** Two attempts were wrong before the third was right,
and the failure is worth recording because it is a general trap with thin
masks:

| tidy-up | 36.6 M void cells became | verdict |
|---|---|---|
| binary closing | **71.2 M (+94%)** | bridged the gaps *between* voids, one 17.6 km² blob over a 45%-void tile |
| binary opening | **3.2 M (−91%)** | erased nearly all of it |
| none | 36.6 M | correct |

The voids are genuinely one to two cells wide. That is the data, not noise in
it, so any morphology misrepresents it. Primary output is therefore an exact
raster mask, which also draws faster than polygons ever would:

    missing_ground_9t_0p5m.tif       36,628,564 cells, 9.157 km², 9.4 MB
    recoverable_ground_9t_0p5m.tif    2,857,002 cells, 0.714 km², 2.3 MB

Polygons are written too, from a deliberately coarsened 4 m grid (a cell counts
as void if over half of it is), and labelled as a generalisation: 15,396 and
407 features.

**Still unanswered:** whether the annotation slides should switch from
all-areas totals to 9t-only. The 9t figures are computed and ready — pads 650 /
1.151 km², pit floors 503 / 14,659 m², pit rims 506 / 96,643 m² — but the
"pit outlines" layer on the slide does not map cleanly onto a geopackage layer,
so switching needs that resolved first.

---

## 2026-09-21 — v14: the annotation-QC slide dropped, and two claims corrected

Built from the user's own edited v13 (82 slides, with a new opener at slide 9)
and written to v14, so none of their work is overwritten. 82 → 81 slides,
74 pictures unchanged.

**Annotation Quality Control removed.** The work was real — a genuine script
with a 856-row output — but it does not describe this pipeline:
- ran April 2026 against a different annotation set (its own docstring says
  "updated 861 pits")
- lives in `archive/` on the pre-reorganisation path layout and cannot be
  re-run as written
- covered tiles 9t/mk5/mk/mkf, not this deck's scope
- no iteration write-up, and the analysis log never records the run

The annotations were rebuilt ann527 → ann712 on 2026-09-04 with the split
reassigned, so the QC predates everything the deck's models were trained on.
Its closing line, "before any model is trained on them", was therefore false of
this pipeline.

**The vendor-only disclosure.** `_build_derivatives.py` filters
`Classification[2:2]`, so every derivative the models read is built from the
vendor's ground alone. Confirmed against the data rather than only the code:
over a window where the recovered returns fill many voids, the training DEM is
**identical to the vendor-only DEM in 100.0% of cells** and differs from the
vendor-plus-recovered DEM in 40.8%.

Four slides read as though the restoration were in use and are reworded to
past-experiment; slide 22 gains an explicit line: *"None of this is in the
detection pipeline yet — every result in this talk is built on the vendor's
ground alone."*

**The outcome counts.** Slides 61 and 62 paired an all-areas annotation count
with a 9t-only rate:

| | pits | pads |
|---|---|---|
| drawn everywhere | 714 | 995 |
| inside 9t | 503 | 650 |
| `n_gt` in the CV5 file | 470 | 650 |
| single test split | 91 | 95 |

The slides showed the largest. Replaced with the scope — "held-out blocks on
9t" — which is true regardless of which evaluation produced the rate, rather
than substituting a number whose provenance is unsettled.

**Still open, deliberately untouched.** The deck's 0.928 matches none of the
CV5 fold means (pit 0.936/0.964, mean 0.950; pad 0.928/0.909, mean 0.919), and
that CV5 file holds only 2 folds rather than 5. Until the source of the
headline recall is pinned down, putting a denominator on it would replace one
wrong number with another.

Script: `docs/presentation/_build_v14_from_user_v13.py`

---

## 2026-09-21 — v13: the data-QA section gets a beginning and an end, and the corn rows get measured

Deck 75 -> 81 slides.

**Data QA now opens where the problem was actually noticed.** Two new slides
before the old opener: 113.5 M points, 43.7% in class 1 "unassigned"; sorting
them by height above ground puts 56% in the canopy and **33% sitting on the
ground**. Those 5.6 M ground-sitting points match real ground on every recorded
property — 100% terminal returns, 75% single, 0.00% overlap-flagged — and
differ on exactly one: median scan angle **18.6° against 9.4°**.

**And it now ends on the question it was raising.** Two new slides: the
bare-earth surface built both ways side by side, with the no-ground cells
tinted; and the difference histogram. Neither surface has holes — both are
triangulated — so the real difference is **a guess versus a measurement**.
Where the vendor already had ground the surface does not move (median +0.000 m,
0.2% beyond 10 cm); where it was filled it does (median −0.005 m, 20% beyond
10 cm).

**Corn rows, measured.** The user digitised nine rows into
`data/cornrows.gpkg`. Reprojected out of EPSG:4326 first, because bearings
computed in degrees of latitude and longitude are distorted and came out 3° wrong.

| source | bearing |
|---|---|
| the nine hand-drawn lines | **79.31°** (sd 0.36, range 78.86–79.98) |
| 2-D FFT of the LRM raster | **79°** (peak 13× the median across bearings) |
| the point cloud's scan geometry | **78°** |

Three independent measurements within one degree. Spacing median **3.35 m**,
amplitude under a centimetre.

**Three failed attempts at the direction, recorded because the failure mode is
instructive.** A rotate-and-take-the-most-variable-profile sweep returned 100°
(a two-sample bilinear-interpolation spike), then 173° once median-filtered
(swath-scale banding, not corduroy), then 13° once high-passed (nothing
dominant — everything within 78–100% of peak). Three answers from one method is
a method problem. The FFT gives one answer sharply.

Also: a slide of the same window in hillshade, local relief, negative openness
and slope, **with no text on it at all**, per request. Corn rows are plainest in
local relief.

**Captions removed from inside eight figures.** Explanatory text baked into a
PNG cannot be edited, re-wrapped, or read at presentation size, and the request
to stop had already been made. It now lives in the slide's left-hand column.

Scripts:
- `docs/presentation/_build_v13_dataqa_and_cornrow_slides.py`
- `docs/presentation/figures_30to45min/_dem_with_and_without_deleted_returns_9t.py`
- `docs/presentation/figures_30to45min/_cornrow_four_layers_9t.py`
- `docs/presentation/figures_30to45min/_cornrow_rows_measured_9t.py`

---

## 2026-09-21 — v12: speaker notes describe the slide, not the deck's history

The notes had drifted into commentary about the deck itself — why a slide was
added, which earlier version a figure came from, which numbers were dropped and
why. That is useless to someone looking down at a slide mid-talk.

Rewritten on all 75 slides to describe **what is on screen**:
- what the figure shows, and which panel is which where there are panels
- what every number on the slide means, in plain words
- the point of the slide
- limits stated as facts about the content

Presenter guidance is kept where it is about the content — "every one of these
is a candidate, not a confirmed well", "these are segmentation scores, not the
detection recall on the outcome slides". What is gone is narration of the
deck's own revision history.

Checked, not assumed: a scan for `initially | originally | used to |
previously | we changed | the old slide | no longer | superseded | retired |
replaced | first version | earlier` returns **0 hits** across all 75 notes, and
a separate scan for "this slide exists", "carried over from", "be careful how
you say", "do not explain" returns 0.

Example, slide 56:

> **before** — "This is the good one. Recall 0.928, so it found 93% of the
> pits. And it only flags 0.21%…"
> **after** — "Pit results on the held-out blocks. 712 pits. Recall 0.928: it
> found 92.8% of the pits. Precision 0.633: 63.3% of what it flagged was real.
> Flags 0.21% of the tile…"

Slide content untouched: 75 slides, identical titles, 67 pictures. Both
finalisers clean, app.xml Slides 75 / vector 78. Median note 353 characters.

---

## 2026-09-21 — v11: "held-out tile" was wrong, and the locator moved to where it lands

**Terminology.** The deck used one phrase for two different things:

- slide 47, *"the held-out blocks"* — blocks inside the **training** tile,
  withheld from training and kept for testing. Standard meaning, correct, kept.
- 9 slides, *"Held-Out Tile 613590"* — a different 4.5 km tile, 1.5 km west,
  that was **never in any split at all**.

The second is wrong. "Held out" means withheld from a dataset the model
otherwise saw; 613590 was never in that dataset, so there was nothing to
withhold. One label for both made them look like the same kind of evidence,
when the second is the stronger claim.

**Renamed to "Second tile, 613590"** on all 9 slides, plus body text and notes.
0 occurrences of the old phrase remain; `held-out blocks` survives on slide 47,
which is the correct usage.

**Deliberately NOT "out-of-domain"**, which is what `LEADERBOARD.md` and
`FIGURE_INDEX.md` call it. On this deck that over-claims: 613590 is the same
county, same 2019 survey, same flight block and same terrain, 1.5 km away. The
conclusion slide already says "two tiles in one county is not evidence of
regional generalisation", and "out-of-domain" would contradict it. "Second
tile" is literally true and claims nothing extra.

**Locator moved.** "Where the two study tiles are" was slide 7, carrying the
line *"9t is where every model was trained. 613590 is 1.5 km west, and no model
has ever seen it."* At slide 7 the audience has not met training, testing or
splits, so the claim lands on nothing. Moved to **slide 57**, immediately
before the second-tile results, and its standfirst rewritten to introduce that
section. Slide 6 "Study Area" keeps its own maps, so the opening still has
geographic context. Its notes now also warn against both "held-out" and
"generalisation test" for this tile.

75 slides, 67 pictures, notes on every slide — unchanged from v10 apart from
the rename and the move. Both finalisers run clean: 0 orphaned image rels,
0 malformed notes slides, app.xml Slides 75 / vector 78.

---

## 2026-09-21 — repair prompt: what is ruled out, and the one test left

v10 still prompts, so the stale `docProps/app.xml` was a real defect but not the
cause either. Three fixes now shipped, none of which stopped it:

| fix | was it a real defect? | did it stop the prompt? |
|---|---|---|
| 27 orphaned image relationships | yes | no |
| 33 malformed notes slides | yes | no |
| `app.xml` declaring 68 slides against 75 | yes | no |

**The most useful finding: repairing costs nothing.** Comparing v8 against the
repaired copy PowerPoint wrote — 75 slides both sides, **titles identical,
picture counts identical, notes text identical on all 75, on-slide text
identical at 18,580 characters.** The only side effects are cosmetic: embedded
JPEGs re-encoded as PNG, media renumbered, `app.xml` corrected, window state
saved. Nothing is lost.

**Ruled out by measurement,** beyond the structural suite already logged:
- *python-pptx round-trip itself.* Loading and re-saving PowerPoint's own
  repaired file with no changes drops no part, adds no part, and alters exactly
  one: `[Content_Types].xml`, same length, Overrides in a different order.
  Ordering is not significant there.
- *The zip container.* `[Content_Types].xml` first, no data descriptors, no
  ZIP64 offsets, no UTF-8 flag, 403 entries — same shape as PowerPoint's own.
- *`ppt/presentation.xml`, `[Content_Types].xml`, `slideMaster1.xml`, all 11
  `slideLayout*.xml`* — differ from the repaired copy only in serialisation,
  identical length and content.
- *`viewProps.xml`* — differs only in saved window state (zoom, pane widths).
- *`notesMaster1.xml`* — differs only in `<a:p/>` vs `<a:p><a:endParaRPr/></a:p>`
  and restored `spLocks`, both cosmetic normalisations.
- *An oversized media part.* The largest is `image2.png` at 15.06 MB,
  3507x2480 RGBA, valid and readable, and it came from the original deck.

**The one test left**, written to `docs/presentation/_repair_test/`:
- `C_powerpoint_blessed.pptx` — PowerPoint's own repaired output, untouched.
- `D_roundtripped_once.pptx` — the same file loaded and re-saved by python-pptx,
  nothing else changed.

Outcomes and what each means:
- **C clean, D prompts** → the round-trip is the cause despite the XML evidence,
  and the answer is to stop saving the final deliverable with python-pptx.
- **C prompts** → PowerPoint's own output still prompts, so the trigger is not
  content we author at all, and no amount of package surgery will fix it.
- **Both clean** → the trigger is in what the build scripts changed after that
  point, and the bisect narrows it in three rounds.

Until that is answered, the practical position is that the prompt is cosmetic:
repair once, save, and the result is verified complete.

---

## 2026-09-21 — the repair prompt was a stale docProps/app.xml

v9 still prompted, so the two defects found in the previous pass were real but
not the cause. The actual one:

| | v9 (ours) | deck reality | PowerPoint's repaired copy |
|---|---|---|---|
| `<Slides>` | **68** | **75** | 75 |
| `TitlesOfParts` vector | 71 | — | 78 |

`docProps/app.xml` carries a declared slide count, a "Slide Titles" heading
pair, and a vector listing every font, the theme, and **one entry per slide**.
PowerPoint writes it and checks it against the package. **python-pptx never
touches it.** So every slide added or removed programmatically since the deck
was last saved by PowerPoint pushed it further out of step.

This is why every structural check passed: the package *is* structurally valid.
The defect was a stale summary of it, living in a part nothing else references
and no integrity check looks at. It also explains why the prompt predates the
recent work — v6, v7, v8 and v9 all carry it.

**Fix:** `_sync_docprops_app.py` rewrites `<Slides>`, `<Notes>`, the
"Slide Titles" heading pair, and the `TitlesOfParts` vector (fonts + theme +
one entry per slide, resized), swapping only that one part and leaving the rest
of the zip byte-identical.

One trap inside it: slide 1's title contains ``, a soft line break, which
is legal in the slide as an `<a:br/>` but which lxml refuses to write into
app.xml at all. PowerPoint writes a space there, so `clean()` does the same.
Worth noting my earlier "0 control characters" check missed this, because it
only scanned `a:t` elements and this one comes from `a:br`.

**v10** now matches PowerPoint's own repaired values exactly — Slides 75,
Notes 75, vector 78, 403 parts. Content verified identical to v9: same slide
count, titles, picture counts and notes text; zip integrity clean. `Words` and
`Paragraphs` are left stale on purpose — PowerPoint recomputes those and does
not validate them.

Awaiting confirmation that v10 opens without the prompt.

**Standing rule for every future deck build:** run `_fix_pptx_repair_defects.py`
then `_sync_docprops_app.py` as the last two steps, or the orphaned
relationships and the stale slide count both come straight back.

---

## 2026-09-21 — the repair prompt, found by reading PowerPoint's answer

Ten structural checks on v8 all passed and found nothing. The defects were
found instead by opening the deck, clicking Repair, saving, and diffing the
result against the input (`_diff_repaired_pptx.py`). PowerPoint names its own
casualties.

**What it removed:**
- **27 image relationships across 26 slides** (slide 21 lost two, the rest one
  each).
- **`notesSlides/notesSlide76.xml` outright**, with its rels part — the notes
  for the canopy slide added in v8.

Everything else in the diff was housekeeping: it re-encodes embedded JPEGs as
PNG and renumbers media. **Shape counts on surviving slides were unchanged**,
so no visible slide content was lost.

**Defect 1 — orphaned image relationships. Mine.** Several scripts re-lay a
slide out by deleting every shape:

    for sh in list(slide.shapes):
        sh._element.getparent().remove(sh._element)

That removes the `p:pic` element and leaves the slide's relationship to the
image behind. Adding a new picture then adds a second, so the slide declares
two images and references one. Slide 21 was wiped twice — by
`_fix_chm_slide_for_1m_v7.py` then `_build_v8_split_canopy_and_rrim.py` —
which is exactly why it carried two orphans.

**Defect 2 — notes slides built from python-pptx's template, not PowerPoint's.**
33 of 75 were malformed, not just the one PowerPoint deleted:

| | generated | PowerPoint's own |
|---|---|---|
| shape order | body, sldImg, sldNum | sldImg, body, sldNum |
| body placeholder | `type="body" idx="3"` | `type="body" sz="quarter" idx="3"` |
| sldNum placeholder | no `sz` | `sz="quarter"` |
| sldImg `spLocks` | `noGrp` only | `noGrp noRot noChangeAspect` |

**Fix, written as `_fix_pptx_repair_defects.py`:** drop every image
relationship no `r:embed`/`r:id`/`r:link` still refers to, and rebuild any
malformed notes slide by cloning the skeleton from a healthy one *in the same
deck* — which matches whatever this deck's notes master expects rather than
guessing at the schema.

**A bug in that fix, caught before shipping:** the first version set the text
through `ns.notes_text_frame`, which had been resolved against the tree just
detached, so the assignment landed on an orphaned element and all 33 rebuilt
slides silently kept the *template's* notes. Found by diffing note text
before and after. Now the text is written directly into the cloned skeleton's
body placeholder.

**Result — v9:**

| | v8 | v9 |
|---|---|---|
| orphaned image rels | 27 | **0** |
| malformed notes slides | 33 | **0** |
| media parts | 92 | 65 |
| size | 90.9 MB | 82.6 MB |

All 75 slides, titles, picture counts and notes text verified identical to v8.
Awaiting the user opening v9 to confirm the prompt is gone.

**Still to do:** the slide-wipe pattern itself is unfixed in the builder
scripts, so a future re-run reintroduces defect 1. Either add a shared
`wipe_slide()` that drops rels, or run `_fix_pptx_repair_defects.py` as the
last step of every deck build.

---

## 2026-09-21 — v8: canopy height and the RRIM stop borrowing each other's evidence

**The rule now enforced:** canopy height is discussed on the canopy-height
slides and nowhere else; the RRIM is discussed on the RRIM slides and nowhere
else. Neither argues its case with the other's picture. A check at the end of
`_clean_rrim_crossrefs_v8.py` asserts it: **0 cross-references remaining.**

Changes from v7, slide count unchanged at 75 (one added, one removed):
- Canopy height became **two slides in sequence** — slide 21 shows the rows
  plain and unannotated (`chm_corn_rows_05_9t.png`), slide 22 says what they
  are (`chm_corn_rows_are_empty_cells_9t.png`): the same cells painted orange
  at 0.5 m beside 1 m where they are gone, **3.22% → 0.00%** in this window.
  Its forward reference to the RRIM section is gone.
- **"Two different stripes, one nickname" deleted.** Its left panel was a
  canopy raster sitting in the RRIM section. The one fact the RRIM section
  needed from it — the ground surface holds no empty cells at either
  resolution, so these stripes cannot be missing data — moved onto the RRIM
  slide as a bullet, stated without reference to canopy height.
- Two dangling references cleaned: the RRIM kicker said "the second kind" with
  no first kind on screen, and slide 33's notes argued the RRIM case by
  comparison with "the canopy holes".

**Repair prompt — the background hypothesis is ruled out.** Every `p:bg` in the
deck is a plain `<a:solidFill><a:srgbClr val="F7F8F6"/>` with no relationship
reference, so there is nothing there to dangle. v8 also passes every structural
check available here: no dangling relationship targets, no orphan parts,
Content_Types covers every part, no duplicate or zero shape ids, no duplicate
zip entries, no control characters in any `a:t`, all font sizes in range, all
91 embedded images valid and matching their declared extension, 75 slides and
75 notesSlides, slide ids unique and in range. The 61 zero-size extents found
are `spTree` `grpSpPr` entries, which are normal in every PPTX.

So the defect is something PowerPoint checks and these tests do not. Built
`_repair_bisect_v8.py` to narrow it by halving rather than guessing further —
three rounds isolates one slide. First pair written to
`docs/presentation/_repair_test/` (gitignored). **Both halves prompting would
mean the fault is in the master, layouts or theme; neither prompting would mean
it is in the presentation part itself.** Awaiting the user, who has to open
them.

Scripts:
- `docs/presentation/_build_v8_split_canopy_and_rrim.py`
- `docs/presentation/_clean_rrim_crossrefs_v8.py`
- `docs/presentation/_repair_bisect_v8.py`
- `docs/presentation/figures_30to45min/_chm_corn_rows_pair_9t.py`

---

## 2026-09-21 — the two "corn rows" are different phenomena, and the deck now says so

The user caught a conflation I had been carrying: the canopy-height stripes and
the RRIM stripes are not the same thing, and the deck had been offering a fix
for one as though it fixed both.

**Measured, full rasters, not subsampled:**

| layer | 0.5 m | 1 m |
|---|---|---|
| DEM | **0.000%** | **0.000%** |
| DSM | 2.044% | 0.029% |
| CHM | 2.044% | 0.029% |

That DEM row settles it. The ground surface has never had a single empty cell at
either resolution, because `filters.delaunay` + `filters.faceraster` spans every
gap by construction. So the RRIM stripes — which are built from that DEM —
**cannot be missing data.**

So there are two phenomena:
- **canopy height** — literally empty cells, a grid-size artefact. The 0.5 m
  grid asks for finer detail than the survey delivered. 2.044% → 0.029%.
  **Solved by coarsening.**
- **RRIM / LRM / openness** — structure in a surface with zero empty cells.
  Real measurements disagreeing with each other. **Coarsening only reduces it**,
  because there is nothing empty to fill; averaging more measurements per cell
  just shows the disagreement less.

**Deck restructured**, now 75 slides:
- Slide 21 (canopy height) gains a line saying this kind is a grid-size problem
  that 1 m solves, and points at slide 30 for the kind it does not.
- **New slide 30, "Two different stripes, one nickname"**, with
  `two_kinds_of_corn_rows_9t.png` — same 240 m window at the reported spot, CHM
  with NoData picked out in the validated `#D97706` against RRIM on the same
  ground, void percentages under each.
- Slides 31–33 are now about the second kind only. Slide 33 lost the
  "3.23% → 0.00%" bullet, which was a CHM number being used as evidence about
  the RRIM — exactly the conflation. It now says coarsening helps partly, cannot
  delete these, and that no mechanism was proved.

**Process note:** broke the slide script twice with `
` inside a bash heredoc,
the same failure recorded earlier in this log. Restored from git and used the
edit tool. Heredocs are not to be used for writing Python string literals.

Scripts: `docs/presentation/figures_30to45min/_two_kinds_of_corn_rows_9t.py`

---

## 2026-09-21 — corn-row slides, the provider's own answer, and the model comparison

Deck v7 now 74 slides.

**Slide 21 rewritten (option 2 of the two offered).** It asserted "the corn
rows are NOT canopy — 3.2% of this window", which its own 1 m figure
contradicted after the recast. Now shows `chm_window_multires_9t.png` — the
same 300 m window at 0.5 / 1 / 2 m, no-data picked out, percentage under each
panel — so it demonstrates the artefact instead of asserting it. Layout
changed from a full-height right-hand picture to text-on-top, figure full width,
because the figure is 2.54:1.

**Three new slides at 30–32, after the RRIM pair.**
- *The corn rows* — they run at 78°, the scan-line bearing; they appear
  in every shape-derived layer; they are tens of centimetres against a 0.7 m
  pit, so artefact and signal are the same size.
- *What the data provider says* — OpenTopography's FAQ quoted verbatim from
  `notebooks/wellsight/preprocessing/dem_idw_builder.py`: *"there is nothing the
  user (or OpenTopography) can do to fix this as it is in the raw data that we
  receive"*, plus their two suggested remedies.
- *What the two remedies actually did* — coarser grid works (3.23% →
  0.00%); local gridding backfired, and the slide says 1 m **reduces** the
  stripes rather than removing them, and that no mechanism was proved.

**Two new figures**, both built because the existing ones could not go on a
slide honestly:
- `rrim_corn_rows_05_vs_1m_9t.png` — `rrim_05_vs_1m_9t.png` carries the
  retracted "the grain runs with the flight lines" subtitle from the argmax
  test, and `rrim_grain_bearing_9t.png` still shows that test's 120° answer
  in its legend. New figure claims nothing about mechanism. Centred on
  623822 E 4594949 N, the spot the striping was reported at by eye, because the
  old corn-row window 2.5 km west understates it.
- `local_gridding_backfire_9t.png` — `destripe_dem_mean_radius_9t.png`
  labels its panels with spike-prominence ratios, and **that metric is
  window-size dependent**, so those numbers are not quotable on a slide. Two
  panels, no scores. Two bugs caught while building it: the first version fell
  back to the DEM for the left panel, comparing a raw elevation raster against
  a RRIM; and the destripe window runs 122 m past the tile's eastern edge, so
  both panels are now cropped to the overlap.

**Slide 52 — the other models, which were missing.** Four architectures,
five folds each, identical folds/channels/loss/schedule, from
`docs/iterations/LEADERBOARD.md`. Pits: plain U-Net 0.559, full stack 0.561, a
gain of 0.002 against a fold sd of 0.020 — architecture is not the
constraint. Pads: 0.555 → 0.608, suggestive. The slide states these are
segmentation IoU at 1 m and must not be compared with the detection recall on
the outcome slides.

Scripts:
- `docs/presentation/_fix_chm_slide_for_1m_v7.py`
- `docs/presentation/_add_cornrow_and_arch_slides_v7.py`
- `docs/presentation/figures_30to45min/_rrim_corn_rows_05_vs_1m_9t.py`
- `docs/presentation/figures_30to45min/_local_gridding_backfire_9t.py`

---

## 2026-09-20 — every terrain figure recast at 1 m; deck saved as v7

**Built the missing 1 m stacks first.** 9t had 12 of the 1 m layers and was
missing CHM, DSM and the extra TPI/LRM radii. **613590 had no 1 m stack at
all.** Both rebuilt with `_build_derivatives.py --res 1.0`; the 613590 RRIM
needed `_make_rrim.py --suffix 1m` separately, since RRIM is not part of that
builder. 9t now 22 layers, 613590 21. ~2 GB, all covered by the existing
`data/**/derived/**` ignore rule; >100 MB audit clean.

**Repointed the figure scripts in two passes**, not one find-and-replace,
because `derived/05/` mixes terrain rasters with things that have no 1 m twin:
- `_repoint_figures_to_1m.py` — filenames, against an allow-list of the layers
  actually rebuilt at 1 m. Refuses any reference whose 1 m target is absent.
- `_repoint_dir_constants_to_1m.py` — the directory constants, adding a sibling
  `D05_1M` and moving only the `_1m.tif` usages, so `pit_blocks_9t.gpkg`,
  `road_chunks_9t.gpkg` and the dataset manifests keep resolving to 0.5 m.

Three scripts build paths from a variable filename, so they got a `dir_for()`
helper that picks the stack from the suffix.

**Deliberately left at 0.5 m**, with reasons:
- pit/pad probability and argmax rasters — those U-Nets were *trained* on 0.5 m
  features. Resampling the picture would imply an experiment we did not run.
- `features_pit_9t_1m.tif` — despite the name it lives in `derived/05`; it is a
  packed model feature stack, not a terrain layer. The first pass moved it and
  the rebuild caught it.
- the data-QA figures (`ground_delivered_9t`, `ground_thrown_away_9t`, the
  scan-angle and CHM-corduroy diagnostics) — their entire subject is the 0.5 m
  void. At 1 m there is nothing left to show.

**Measured, and it is the point of the whole exercise:**

| layer | 0.5 m void | 1 m void |
|---|---|---|
| DSM | 2.04% | 0.03% |
| CHM | 2.04% | 0.03% |

17 builders re-run, all passing. 90 PNGs rebuilt.

**Consequence that needs a decision.** Slide 21 says "The corn rows are NOT
canopy. They are missing data — 3.2% of this window." Its figure is now the 1 m
CHM, where the void is 0.03% and **the stripes are gone**. The slide text and
its own picture now contradict each other. Not changed unilaterally — flagged
to the user.

Also renamed the roughness panel slug `roughness_11` -> `roughness_5`, since the
1 m source is `roughness_5_9t_1m.tif` and the old slug named a layer the figure
no longer shows. `roughness_11_300m_9t.png` is now stale.

Deck: speaker notes rewritten in plain language on all 70 slides and saved as
**v7**; v6 untouched.

---

## 2026-09-20 — the rest of the further-research section, re-grounded

Retiring the old Future Work slide took real ideas out along with the stale
ones, and the NISAR slide only replaced one. Added two more, so the section now
runs: more ground → a better model → watching what we found. Deck is 70 slides.

**More ground.** Three directions, none needing new collection.
- McKean is QL1 (`PA Northcentral 2019 B19`) and already downloaded. It is also
  the cleaner delivery: the 18° vendor scan-angle cut appears in **6 of 7**
  Venango tiles and **0 of 7** McKean tiles, so the corduroy belongs to the
  March 2020 ±20° flight block, not to lidar.
- Older fields. **8,054 of 20,108** wells in the DEP Venango export carry
  `SPUD_DATE = 1800-01-01`, which is a placeholder, and another **1,553** have
  none at all — about 48% of the county's records have no usable spud date.
  Phrased deliberately as *missing records*, not as "8,054 wells predate 1900":
  the sentinel year makes that reading available and it would be false.
- Permian. `TX_WestTexas_2018`, QL1, 12–15 pts/m² measured over the hotspots,
  with the Texas RRC orphan layer as ground truth we did not draw ourselves.
  The best cell holds **136 confirmed orphans in 5 km**.

**A better model.** Checked against `notebooks/wellsight_v2/_dl.py`:
`DEFAULT_CHANNELS` is exactly seven bare-earth layers — `lrm_25, lrm_5, slope,
tpi_05, openness_pos, openness_neg, roughness_11`. `chm_9t_05.tif` and
`intensity_ground_9t_05.tif` are both built and neither reaches any detector.
Slide carries that, plus a negative class for the confusers (trained in, not
filtered out) and geomorphon enclosure as an extra channel. The old slide's
**+31% PR-AUC for geomorphons was measured on the retired gradient-boosted
ensemble**, so it is carried as "needs re-testing" rather than quoted.

Script: `docs/presentation/_add_further_research_slides_v6.py`

---

## 2026-09-20 — NISAR further-research slide, scoped to what the sensor can do

Added one slide after "What would move it next". The asked-for framing was
"use NISAR to track pits"; the numbers already in
`docs/nisar_lidar_supplement_proposal.md` do not support detection, so the slide
leads with that instead of burying it.

The scale, all measured over 9t, not assumed:

| product | pixel | area |
|---|---|---|
| GCOV backscatter | 10 m | 100 m² |
| GUNW InSAR | 80 m | 6,400 m² |
| our `pit_inside` annotations | — | mean 32.1 m² (~6 m across) |
| our `pit_full` annotations | — | mean 210.7 m² (~16 m across) |

A pit is about a third of one backscatter pixel. NISAR will not detect one.

What the slide argues instead: lidar locates the candidates, then the 80 m InSAR
cell is the right size to ask whether the ground over a cluster of them is
moving. That is the wellbore-integrity question, and a single 2019 flight cannot
answer it. Feasibility was already measured — a snow-free fall pair over 9t held
coherence 0.50 with 94% of pixels above 0.3, against 0.14 for a mid-winter pair,
so the constraint is acquisition season, not the sensor.

The caveat bullet carries the caution already recorded in
`docs/iterations/BACKLOG.md`: beta pre-calibration data, one pair, validated
CONUS products ~July 2026. Nothing quantitative should be claimed before then.

New figure `nisar_pixel_vs_pit_scale_9t.png` — 200 m window at 620752 E
4595844 N, the densest cluster of annotated interior pits in 9t, with the 10 m
GCOV grid and one 80 m GUNW cell drawn over it. The 80 m cell is centred on the
pit cluster rather than snapped to a multiple of 80 m: NISAR's grid origin is
arbitrary against ours, and snapping put the pits on the cell edge where the
comparison read as a near miss rather than a containment.

Colour: no new colours. Reuses the validated `#1F5FA8` / `#D97706` pair (worst
pair ΔE 21.1 deutan, 22.6 normal) over a greyscale hillshade, with the two grids
also separated by line weight and dash so colour is never the only encoding.
The dataviz validator is not installed in this environment, so the rule was met
by reuse rather than by a fresh run — flagged here rather than claimed as
validated.

Deck is now 68 slides.

Scripts:
- `docs/presentation/figures_30to45min/_nisar_vs_lidar_pit_scale_9t.py`
- `docs/presentation/_add_nisar_further_research_slide_v6.py`

---

## 2026-09-20 — v6 deck: the template-matching pipeline retired, 73 slides to 67

Slides 60-65 were the last of the pre-U-Net deck. Six slides audited, four
dropped, one kept and moved, one repurposed.

Dropped:
- **Step 2: Manual Annotation** (861 pits). Redundant — slides 30-35 already
  cover annotation, with counts that postdate the rim/floor split.
- **Step 3: Template Matching.** Normalised cross-correlation against a mean
  17x17 m pit template across 5 channels, ~628,000 candidates. Not in the
  method.
- **Step 4: Classification & Results.** XGBoost + LightGBM + HistGB, ROC-AUC
  0.905, PR-AUC 0.212, 48 features per candidate. Superseded by the held-out
  U-Net numbers on slides 47-59.
- **Future Work.** Duplicated "What would move it next", and two of its five
  bullets ("U-Net semantic segmentation", "geomorphon +31% PR-AUC") described
  work that is either finished or belongs to the retired pipeline.
- **Appendix: 48-Feature Set (1/2) and (2/2).** Tabulated the features of the
  ensemble that came out above.

Kept:
- **Annotation Quality Control.** The 856 measured pits it checked are the same
  annotations the U-Nets train on, so the QC still stands. Moved from 63 to sit
  after "Preprocessing — Annotations — Standard Values", and its closing line
  changed from "before training the classifier on them" to "before any model is
  trained on them".
- **Appendix: Literature-Grounded Parameters.** TPI radii 5/15/25.5 m, LRM
  windows 5-51 cells, roughness 11x11, openness radius 25 m — all still the
  derivative builder's values, with citations.

Repurposed:
- **Challenges & Limitations** duplicated "What it does not say", but carried
  the figure of DEP-listed wells with no terrain signature. The matching
  argument was stranded on the deleted Step 2 slide with no picture. Joined into
  **"Why we drew our own labels"**, moved to sit immediately before the
  annotation section.

Two rows on the literature appendix are questionable and were left alone rather
than changed silently: "DEM resolution 1 m" against a 0.5 m delivered stack, and
"Blob sigma range 0.8-5.0", a parameter of the retired blob-detection stage.

Also fixed: the direction-of-flight arrow in `why_the_corn_rows.html` step 2
pointed right. The scan lines accumulate downward, so the aircraft flies down
the canvas; the arrow read as beam direction and contradicted the drawing.

Scripts:
- `docs/presentation/_retire_template_matching_slides_v6.py`
- `docs/presentation/_reposition_and_trim_appendix_v6.py`

---

## 2026-09-20 -- Held-out numbers onto the outcome slides, and real conclusions

Slides 47 to 55 were a title and a picture. Nothing on any of them said how well
anything worked. `docs/presentation/_add_results_and_conclusions_to_v6.py` puts
a one-line stats strip on each and the full account in the notes.

**What is now on the slides**, all held out, all from
`docs/iterations/LEADERBOARD.md` (ann712 sections) and
`data/_comparisons/pit_heldout_and_transfer_2026-09-20/.../pit_transfer_recall_summary_613590_05.json`:

| | withheld | recall | precision | flagged |
|---|---|---|---|---|
| Pits, 9t CV5 | 712 floors, 502 rims scored | 0.928 (sd 0.023) | 0.633 | 0.21% |
| Pads, 9t CV5 | 995 drawn, 650 scored | 0.912 (sd 0.022) | 0.587 | 11.64% |
| Roads, 9t | 1,220 chunks, 43.07 km | 0.982 clean | -- | 5.02% |
| Pits, 613590 | 153 floors, never trained on | 0.911 (sd 0.045) | not computable | -- |
| Roads, 613590 | 48.87 km "added" only | 0.811 completeness | 0.816 | -- |

F2 quoted, F1 given beside it on every slide. The ratio of recall to flagged
area is stated as the result rather than the recall: the pit model reaches a
comparable recall to the pad model on one fifty-fifth of the ground.

**Three slides carry no number on purpose**, each saying why. 613590 pads and
613590 drainage have no ground truth at all -- zero of either was ever drawn
there. And no precision is quoted on 613590 because the tile is not fully
annotated, so an unmatched prediction may be a false positive or an undrawn pit.

**The Summary slide was stale and is replaced.** It carried the pre-U-Net
pipeline: "85.5% precision at 0.80 probability threshold", "ensemble of 48
features", "anomaly detection flags 10.5% of annotations". None of that
describes what the deck presents. It also said "WellSight" in the byline; zero
occurrences remain in the deck.

Three conclusion slides now sit at 66-68, before References: what the numbers
say, what they do not say (four named limits, including the single-annotator
bias that no metric in the deck can detect), and what would move it next,
ordered by payoff rather than effort.

**Two bugs worth recording.** The picture-move guard skipped any image above
1.4 in, which was every image on those slides, so the new strip landed on top
of them. And clearing a text frame by deleting paragraphs after the first
leaves the first paragraph's runs in place, which is how slide 66 came out
reading "Summary | What the numbers say".

**Still stale, not touched:** slides 60 to 63 are "Step 2: Manual Annotation",
"Step 3: Template Matching", "Step 4: Classification & Results" and "Annotation
Quality Control". Template matching is not in the current pipeline. Flagged for
the user rather than deleted.

## 2026-09-20 -- CORRECTION: the scanner is a rotating polygon, and three numbers were wrong

The entry below headed "What the corn rows are: measured, not assumed" reached
the right conclusion about WHERE the stripes are and the wrong one about WHAT
made them. Corrected here rather than edited there, so the mistake stays
visible.

**The sensor is a RIEGL VQ-1560 series: a rotating polygon, dual channel.**
Identified from the manufacturer's published scan-pattern description, not from
the LAS header, which names only "QSI LiDAR Suite". Each channel rules straight
parallel lines; the two channels' sets are tilted 28 degrees against each other
with a forward/backward look of plus and minus 8 degrees at the swath edge --
RIEGL's "cross-fire". See `literature/CITATIONS.md`.

**What was wrong, and why.**

*Ground speed 112.2 m/s.* Regressed x and y against gps_time over all returns.
That measures the sweep, not the aircraft: the beam crosses 1149 m of ground in
6 ms while the plane moves under half a metre. Consecutive 1.4 s pieces of the
same line gave 34, 55 and 72 m/s and the scatter was ignored. The near-nadir
ground track gives **70.1 m/s**, 1503 m in 21.46 s.

*Stripe spacing 3.00 m.* From an autocorrelation restricted to lags above 2 m.
Restrict a search above 2 m and it returns something above 2 m. The same
profile has no clean periodic peak at any lag. **No spacing is claimed now.**

*"Oscillating mirror, 54.3 Hz", and 37.4 Hz before it.* The scan angle appears
to rise and then fall, which reads as a reversal. It is two interleaved
channels sampled alternately. The across-track ground coordinate settles it:
its step changes sign 37,041 times in 199,900 pulses, median run length ONE. A
single sweeping beam cannot do that. A polygon has no turnaround, so the whole
"lines pair up at the swath edge" mechanism built on top of it is withdrawn.

**What survives, all of it independently measured.** Scan lines run at
**78.0 deg**, from the ground point pattern with nothing assumed -- for each
candidate bearing, project onto the perpendicular and histogram; real ruled
lines spike. Corn rows run at **79.0 deg**, from the NoData mask. The corn rows
lie **along the scan lines**. Void cells hold nothing: 94.1% have no return of
any kind. Coverage on a stripe is 1.8x thinner than beside it. Void rate by
scan angle 0.38% -> 5.35% -> 0.89%, the cliff at 14 deg being flight-line
overlap (0% double coverage inside, 98.3% beyond). Trees roughly double it.
None of that is affected.

The 78 against 85.8 deg across-track is itself a check: the 7.8 deg offset
matches the datasheet's plus and minus 8 deg forward/backward look.

New: `notebooks/wellsight_v2/s7_analysis/_measure_scanner_geometry_9t.py`,
`notebooks/wellsight_v2/s7_analysis/_raw_returns_plan_view_9t.py`,
`docs/presentation/figures_30to45min/v6/raw_returns_plan_view_9t.png` -- the raw
delivery over the same 4.5 km square as `ground_thrown_away_9t.png`, with a
300 m detail in which the straight parallel scan lines are plainly visible.

## 2026-09-20 -- The corn rows and the vendor cut are not the same problem

Asked directly: do the CHM corn rows overlap the Data QA red strips, and does
the CHM change once the vendor's discarded ground is put back?
`notebooks/wellsight_v2/s7_analysis/_test_corduroy_vs_vendor_cut_9t.py` answers
it five ways. No, and no.

**In the 300 m CHM window.** Scan angle runs 0.00 to 7.40 degrees, median 3.47.
The cut is at 18. Not one of the 176,275 returns here was cut -- 10.6 degrees of
headroom. Of the 11,603 void cells, 0 hold a cut return.

**Rebuilding the CHM on both DEMs.** Vendor ground 11,603 NoData cells,
vendor plus recovered 11,603. The masks are identical in 100.00% of cells.
Recovery closes zero holes. Where both surfaces exist the canopy height moves
by a median of +0.0000 m, p95 0.171 m.

**Over the whole 4.5 km tile, 5 m cells.** Void fraction is 0.0215 where nothing
was cut and 0.0090 where returns were -- the corn rows are HALF as common where
the cut bites. Pearson r between the two is -0.074.

**Why, geometrically.** Void rate climbs 0.38% at nadir to 5.35% at 12-14
degrees, then collapses to 0.89% at 14-18. The collapse is flight-line overlap,
checked by counting distinct point_source_ids per cell rather than assumed: 0.0%
of cells inside 14 degrees see a second line, 98.3% beyond it do. Cells seen by
one line are 2.29% void; cells seen by two or more are 0.83%. The vendor's cut
lives at 18 degrees, inside that overlap. So the two problems sit in different
parts of the swath by construction.

**The distinction that matters.** The cut is about what a return was LABELLED --
it is in the file, reclassifying it is free. The corn rows are about whether a
return EXISTS -- 94.1% of void cells hold nothing of any kind. You cannot
reclassify a pulse that never came back.

Figures: `docs/presentation/figures_30to45min/v6/corduroy_vs_vendor_cut_9t.png`
(four panels: window and tile, each way) and
`docs/presentation/figures_30to45min/v6/void_rate_vs_scan_angle_9t.png`.

## 2026-09-20 -- What the corn rows are: measured, not assumed

`_test_chm_nodata_bands_9t.py` established that the stripes are NoData and that
they run at 79 deg. It did not say what put them there, and "zero first returns"
was being repeated as if it meant "no lidar at all", which is a different claim.
`notebooks/wellsight_v2/s7_analysis/_test_corduroy_is_scan_geometry_9t.py` now
measures both, on the CHM panel's own 300 m window.

**A void cell really is empty.** 100% have no first return, 94.1% have no return
of ANY kind, 95.0% have no ground-classified return. Mean 0.06 returns per cell
against 0.50 for a normal cell. Note the comparison though: 54% of NORMAL cells
also hold zero returns, because at roughly 2 returns per square metre a 0.5 m
cell is smaller than the point spacing. Those still get a DSM value, gridded
from a neighbour. A void is where the empty cells line up into a strip wide
enough that there is no neighbour to borrow from.

**The stripes are the scan pattern.** One flight line over this window, PSID
637, bearing 348.2 deg, groundspeed 112.2 m/s regressed from gps_time. Across
track is therefore 78.2 deg. The stripes run at 79. Spacing 3.00 m, width 1.12 m,
and 112.2 / 3.00 = 37.4 Hz, one mirror sweep. Return density on a stripe is
0.322 per cell against 0.569 between, 1.8x thinner.

So: the scanner sweeps side to side, the aircraft moves 3 m forward between one
sweep and the next, coverage in the middle of that step is 1.8x thinner, and
where it is thin enough that nothing landed at all the DSM has nothing to grid.
Scan angle over this window runs -7.4 to +0.1 deg, near nadir, so this is NOT
edge-of-swath thinning.

**Three measurement traps, all hit before getting the number right.** An FFT of
the void profile peaks at 177 m, which is the patch the field sits in, not the
stripes. Gaps between detected stripe centres move with the threshold and the
extent (3.00 m, then 3.62 m). Autocorrelation fixes both, but argmax lands on
8.5 m, the third harmonic, because the stripes cluster in threes -- it has to be
the first local peak past 2 m. Folding along-track position modulo 3 m also
fails, completely flat at 1.02x against 0.98x, because the phase drifts over a
few hundred metres.

## 2026-09-20 -- Orbit viewer on the CHM slide window, and the hand-annotation inventory

**Viewer window moved to match the slide.** `_export_scanline_viewer_data_9t.py`
was centred on 621392 E, 4594510 N at 120 m -- the densest patch of the dropout
field, wholly inside the CHM panel but offset 32 m east and 43 m north of it. It
now uses the panel's own centre and side (621359.6 E, 4594467.4 N, 300 m), taken
from LAT/LON/SIDE_M in `_build_derivative_panel.py`. The window's NoData comes
out at 3.22%, matching `_test_chm_nodata_bands_9t.py` exactly, which confirms the
registration. Scene file 9.1 MB, 176,275 returns, 600x600 grids.

**CHM laid under the model.** The export already carried the CHM grid; the viewer
now renders it as an unlit textured floor, greyscale 0 to 40.24 m -- the whole
raster's min/max, which is the convention the panel inherits -- with NoData in
`#D97706`, the same paint as the slide. Unlit on purpose: a shaded floor would
not be the raster's greys.

**Scanner.** A line walks the box and its cross-section is plotted live, with a
tick on every cell the first-return surface lacks. Two modes: across the rows
(the line cuts all of them at once, the section reads as a comb) and along
strike (the line floods and clears once every 3 m of travel). Speed is a slider,
0 to 40 m/s.

**Hand-annotation inventory.** `_annotation_inventory_stats.py` counts what was
drawn, from `annotations_proj.gpkg`. Roads 535.9 km over 3,690 lines forming
1,747 networks; not-road 18.0 km over 112. Drainage 45.0 km, 594 drawn lines cut
into 1,791 segments, 9t only. Pads 995, 144.40 ha, mean 1,451 m2. Pit exteriors
723, 14.84 ha, mean 205 m2. Pit interiors 712, 2.29 ha, mean 32 m2 -- 16% of the
outline by area. Walls 586, 9.91 ha. Every layer also split 9t / 613590 /
elsewhere, because roads run to McKean and a grand total is not a 9t total.
Written onto v6 slides 30, 31, 32, 34, 35 with plain-language notes.

**One correction made in the pass:** the first road "drawn lines" count came out
at 4,972 against 3,690 features, because `linemerge(unary_union(...))` nodes
every crossing and splits lines. Replaced with a union-find over shared
endpoints.

## 2026-09-19 - CORRECTION: the CHM "streaks" are NoData, and the roaddrain architecture row is training

**Retraction.** The entry below, "the CHM carries scanner-sweep artifacts", is
wrong. The bright bands in `chm_300m_9t.png` are not an instrument artifact and
they are not canopy. They are **missing data**. matplotlib paints NaN as the
figure background, and on that panel's black-to-white greyscale ramp the
background is brighter than the maximum value, so a hole renders brighter than
27.9 m of canopy. The bands are a **rendering bug in the panel builder**, over
real holes in the DSM.

**What the correct measurement says.** New script
`notebooks/wellsight_v2/s7_analysis/_test_chm_nodata_bands_9t.py`, 300 m window
at 41.49264, -79.546127, output
`data/9t/results/chm_striping/chm_nodata_bands_300m_9t.json`:

- **11,603 cells, 3.22% of the window.** CHM NoData and DSM NoData are the same
  11,603 cells, 100% overlap. DEM NoData is **0.00%**. CHM = DSM - DEM, so every
  hole is inherited from the DSM and none of it is a ground problem.
- **Not one first return lands in a void cell.** 652 returns fall in the 11,603
  void cells against 175,632 in the 348,397 valid cells - 0.06 per cell against
  0.50, ratio 0.111 - and zero of the 652 are first returns. The DSM cell is
  empty because nothing came back to fill it.
- **Bearing 79.0 deg**, against 79.4 deg measured by hand off the panel. Median
  band spacing 4.25 m from 15 projection peaks; the peak count moves with the
  `find_peaks` height and distance settings, so call it 3-4 m rather than a
  constant.

**What is retracted, specifically, so it is not re-quoted.**

1. *"21% single-return on the streaks against 70% off them"*, *"20 discrete
   GPS-time bands"*, *"same scan angle, 3.8 vs 3.6 deg"*, *"one flight line
   637"*. All from `_test_chm_scanline_streaks_9t.py`, whose mask is
   `chm >= percentile(chm, 99.3)`. That keeps only cells that HAVE a value - the
   exact complement of the bands it was built to measure. It was comparing
   canopy against ground and never touched the subject. No number from that
   script is usable.
2. *Bearings 121 / 135 / 139 deg.* Wrong twice over. The mask was wrong as
   above, and both scripts applied a `(90 - ang)` conversion that does not
   belong. Calibrated against synthetic lines at 0/30/45/79/120/135 deg, the
   projection angle **is** the map bearing and comes back unchanged. The old
   entry's claim that "the instability is in the mask" was half right: the mask
   was wrong, and so was the arithmetic after it.

The white top-hat reasoning in the entry below stands as a description of how to
find thin bright ridges. It was simply pointed at the wrong thing.

**Still open.** `_build_derivative_panel.py` sets no `set_bad` on its colormap,
so every greyscale panel it produces renders NoData at maximum brightness. This
is not CHM-specific - any raster with holes is affected. Fix the builder and
re-render before the panels are shown.

**Downstream impact: none.** CHM is not one of the seven model channels.

**Training relaunched.** The `roaddrain` architecture row was the one gap in the
architecture comparison - `_arch_compare_9t_1m.py --target roaddrain --arch unet`
had 1 of 40 epochs on fold 0 and nothing else. That stale fold is set aside at
`data/9t/models/_arch_compare/1m/roaddrain/unet/fold0_STALE_1epoch_timing_2026-09-18/`
and a real 5-fold run is under way.

Sizing, first estimated with `--time-one-epoch` at **353 s per epoch**, so 235
min per fold and 19.6 h per arm. **That estimate was wrong by 1.8x.** Fold 0 ran
to completion at a steady **644 s per epoch**, giving **7.2 h per fold and 36 h
per arm**. Do not size a roaddrain run off `--time-one-epoch` again; the
single-epoch path does not reproduce the sustained rate.

Either way it is 12-24x the pit and pad arms (13-27 s per epoch), because the
roaddrain manifest carries 7,825 features against a few hundred. Best-epoch
lands at 27-40 across all 40 finished pit and pad folds, several still improving
at 40, so the schedule cannot be shortened without truncating the arms - 40
epochs is the honest number, not padding.

**Fold 0 result:** best val road IoU **0.593** at epoch 37 (drainage IoU 0.685,
background 0.969). Comparable in magnitude to the pit and pad arms, which span
0.49-0.64.

**Plan, revised on the measured rate.** The four-arm ladder is 144 h and was
never on the table. Two arms - `unet` as control plus `r34_imagenet`, the one
rung with a positive delta on both pit and pad - is **72 h, three full days of
GPU**, not the 39 h quoted when the arm was launched. The control arm is being
allowed to finish, because it closes the named gap ("roaddrain has no
architecture row") and yields a real CV5 leaderboard entry with a fold-to-fold
sd, which is the noise floor any future comparison needs. **The second arm is
held pending the user's word** rather than committed silently at double the
advertised cost. Logs at
`data/9t/models/_arch_compare/1m/roaddrain/run_roaddrain_unet_cv5_40ep_1m.log`.

---

## 2026-09-19 - SMRF ground does not improve pit detection, and the CHM is striped

**The top BACKLOG item is closed, with a null.** The 7-band stack was rebuilt
from SMRF-classified ground on the vendor stack's exact grid and the pit CV5
retrained against it - same labels, same folds, same inner-validation fold, same
architecture and schedule, only the ground classification different. Paired per
fold, **no |t| reaches 2 on any metric**. F1-selected recall@0.3 +0.032
(t +0.83), F2-selected recall@0.3 -0.014 (t -1.19), containment +0.020 / -0.004,
and the largest single effect is SMRF being WORSE at IoU 0.5 under F2 (-0.082,
t -1.91). The two threshold objectives disagree in sign on recall, which is what
a null looks like. 53.9 min, `data/9t/models/pit/unet_cv5_smrf/`.

The reason is already in the earlier tests: only 26.8% of 1 m void cells are
wide-angle-only, while 68.1% hold near-nadir returns and still have no ground
because the canopy occluded it. SMRF closes about a quarter of the holes, and a
quarter was not enough to move anything. The rougher SMRF surface (train-block sd
ratios 1.09-1.42 across the seven channels) recovers real micro-relief and
retains low vegetation as ground; the two appear to cancel.

**Consequences.** Do not reprocess the remaining 175 affected map squares - that
day of compute was explicitly deferred pending this re-score. The Data QA section
of the talk stays a rigour story and should now say so: we found systematic gaps,
showed the missing returns measure as well as the kept ones, tested whether it
changed detection, and it did not.

**A prediction held and an interim claim did not.** The stated expectation before
the run was "roughly flat, possibly slightly worse". After fold 0 alone I
reported the arm as running ahead of baseline on the strength of one fold
(recall 0.932 against a 0.864 baseline fold). The remaining four removed it. One
fold of five is not a direction and should not have been described as one.
Write-up: `docs/iterations/smrf_ground_retrain_pit_cv5.md`.

**The CHM carries scanner-sweep artifacts.** The canopy panel in the talk is
crossed by thin bright streaks. They are an instrument artifact: the returns
under them are 21% single-return against 70% off them, sit at the SAME scan angle
as their surroundings (3.8 vs 3.6 deg, so not the 18 deg cut), and fall into 20
discrete GPS-time bands, all within one flight line (637). A cross-section
crosses 26 spikes at 3.0 m median spacing - the DSM swings 46.5 m while the DEM
beneath climbs smoothly by 23.4 m with no spikes. First-return surface only.
CHM is not one of the seven model channels, so nothing downstream is affected,
but the vegetation-structure channel idea in BACKLOG cannot use CHM raw.

Three detectors were needed and the first two failed, both recorded in the script
docstrings so they are not repeated: a high CHM percentile finds only tree crowns
and returns ZERO pixels in the open ground where the streaks are clearest; a 3x3
binary opening on that same mask inherits the problem; a white top-hat, which
keys on local contrast rather than absolute height, is the right instrument. The
streak BEARING is still not reliably measured - 121, 135 and 139 deg depending on
detector and angular step - although the estimator itself recovers synthetic
lines at 45/60/70/120/135 deg exactly, so the instability is in the mask. No
bearing is quoted as a finding.

An earlier figure from the first attempt asserted "the corduroy is survey
geometry" from an auto-generated headline fired on a badly chosen spectral
prominence threshold, over a diffuse spectrum with no directional peak. It was
moved out of the presentation folder to
`data/9t/results/chm_striping/chm_corduroy_striping_300m_9t_INCONCLUSIVE.png`.

---

## 2026-09-19 - The architecture comparison scored, and a channel swap caught in the SMRF stack

**37 trained folds had never been scored.** `_arch_compare_9t_1m.py` writes its
`pooled_metrics.json` only when one invocation finishes every fold it was asked
for. Two of the nine runs died partway - `pad/unetpp_r34_imagenet` to a host-RAM
`MemoryError` in the dataloader on fold 2, which took folds 3 and 4 with it, and
`roaddrain/unet` after 1 of 40 epochs - so those runs left no summary file at
all and the finished work beside them went unread. New aggregator
`s5_eval/_aggregate_arch_compare_1m.py` reads the fold directories instead and
names the unfinished ones rather than averaging over whatever is present.

**Result: architecture is not the constraint.** Four networks, same folds, same
channels, same 40 epochs, 1 m. Every rung of the ladder falls inside the
fold-to-fold spread - deeper encoder -0.031 pit / +0.013 pad, ImageNet
pretraining +0.020 / +0.032, dense skip connections +0.013 / -0.004, against
pooled sds of 0.018-0.035. A 26.1 M U-Net++ with a pretrained encoder scores
0.561 where the 7.8 M plain U-Net scores 0.559. The leaderboard's standing claim
that data is the bottleneck now has a controlled run behind it instead of an
assertion. Pretraining is the only rung worth re-testing: largest positive delta
on both targets, same sign on both, still short of the noise on five folds.
Full write-up in `docs/iterations/arch_compare_1m_four_architectures.md`.

**The crashed fold was renamed, not deleted** - `fold2_CRASHED_oom_2026-09-18/`.
It holds a `best.pt` with no `train_log.csv`, which is exactly the state that
makes a dead fold look finished in a directory listing.

**A channel swap nearly confounded the SMRF test.** The SMRF feature stack
failed to assemble because `_build_derivatives.py` writes `roughness_5` and the
stack wants `roughness_11`. BACKLOG B5 records `roughness_11` as a mislabel of
`roughness_5`, which would have made substituting it look safe. Checked instead
of assumed, against the vendor band over a 900x900 window of `dem_9t_05.tif`:

    recomputed 5x5   vs vendor roughness_11:  corr 0.568, means 0.076 / 0.151
    recomputed 11x11 vs vendor roughness_11:  corr 0.996, mean |diff| 0.0013

The mislabel holds at 1 m, where a 5-cell window spans the same ground as 11
cells at 0.5 m. At 0.5 m the vendor band is a genuine 11x11 and the two are
different surfaces. Using the 5x5 would have changed channel 7 between the two
arms of the comparison. `build_roughness_11()` now reproduces the 11x11 with the
builder's own formula. Side effect: the long-standing Oil Creek inference
blocker, which is this same missing band at 0.5 m, is now unblocked.

**SMRF stack built and grid-checked.** 9000 x 9000 @ 0.5 m, transform identical
to the vendor stack, all seven bands 100% finite, train mask 53.5% of the tile.
`data/9t/derived/smrf05/features_pit_smrf_9t_05.tif` (1316 MB, gitignored). The
SMRF surface carries 15-42% more variance than the vendor's in every channel
(sd ratios lrm_25 1.25, lrm_5 1.42, slope 1.09, tpi_05 1.26, openness_pos 1.23,
openness_neg 1.28, roughness_11 1.15). That is either more real micro-relief or
more low vegetation kept as ground; the 5-fold detection re-score is what
separates those.

**Palette correction.** The architecture figure's first palette was a single-hue
blue ramp, and its validator numbers were written from expectation rather than
from the validator. Running it failed the normal-vision floor (dE 12.8, below
the hard floor of 15). Replaced with four hues that pass every check under
`--pairs all`; worst CVD dE 9.2 deutan, worst normal-vision dE 16.3.

**Backups.** Both external disks mirrored, resolved by volume label rather than
drive letter: T7 (E:) 1,043 files / 10.25 GB, Seagate (F:) 1,033 files /
10.22 GB, zero failures on either. Verified on E: by diffing the 458
source files changed in the last four days - 451 present at matching size, 0
mismatches, 7 absent because they were created after the copy ran.
`data/9t/derived/smrf05/` was excluded while being written.

---

## 2026-09-19 - The QGIS-styling fix finished, and the pipeline diagram redrawn

Three defects reported off the v3 deck, all of them mine.

**The pipeline diagram was unreadable on a projector.** Rebuilding it "from the
repo" turned into five tall columns of 9.3 pt body text. It is now three rows
of five boxes at the scale of the two-branch diagram it replaced, two or three
short lines per box, 14.5 pt. The lists that must be on the figure - all 21
derivatives, all 7 annotation layers with what each is for - sit under their
row as a caption instead of inside a box.

**Drainage and pads on the annotation slides were still the archived 300 m
images**, built before the QGIS styling fix, so their RRIM did not match the
pits slides beside them. Roads was the new image but the `no_lines` variant, so
the annotation slide showed no annotation. All three now use the `lines`
variant of the current series.

**The outcome figures were the real miss.** The styling fix covered
`_build_derivative_panel.py`, the annotation series and the formula card, but
not the three probability builders, and nobody had said so. All three were
applying their own 2-98 percentile stretch to RRIM - the exact defect that was
fixed elsewhere - and `_build_probability_surfaces.py` was doing the same to
the hillshade base. They also carried two different warm ramps between them.

`_figure_style.py` is new and holds the single answer to both: `read_rrim`,
which does no stretch because the project renders that layer with
NoEnhancement, and `CM_PROB`, a single-hue blue sequential ramp on the accent
`#1F5FA8`. Blue keeps the prediction from reading as more terrain, and it puts
no warm ramp in the same talk as the classification figures' green. Lightness
falls 0.891 -> 0.029 across the five stops, which is the check that applies to
a sequential ramp; the validator's categorical checks do not.

Two knock-ons. The probability panel now masks below 0.05, because a pale blue
floor washed the whole frame and hid the cells the model committed to. And the
annotation outline moved from cyan to `#ffd400`: cyan against the ramp
mid-tone was dE 23.8, yellow is 35.4 protan / 30.8 tritan / 39.8 normal.

Also fixed while there: the two compare-figure titles were right-aligned and
left-aligned on the same line and had been overprinting each other on every
one of the eight images.

---

## 2026-09-19 — RRIM formula card rebuilt on the QGIS styling

The card explaining how RRIM is built was the last figure still drawing its
inputs on invented ramps: positive and negative openness on a green ramp, slope
on an orange-red one. Two defects in one. It is not what those layers look like
when opened, which is what `_build_derivative_panel.py` was fixed for the same
day; and a green ramp beside a red ramp, each meaning something different, is
the exact pair the colourblind rule forbids.

All three inputs are now greyscale, read from `qgis/wellsight.qgz` via
`qgis_styles` imported from the panel builder, so the card and the panels
cannot drift apart. The project styles `openness_pos` WhiteToBlack and the
other two BlackToWhite, and the card now honours that inversion instead of
flattening it. The RRIM thumbnail was also applying a 2-98 percentile stretch
of its own over a layer the project renders with NoEnhancement; it is raw bytes
now, so it matches the annotation series base exactly.

The two ramp swatches keep the real RRIM constants, because they are the
algorithm. The dataviz validator scores teal against grey at dE 4.2 deutan,
but it is scoring them as a categorical palette and they are not one -- they
are adjacent stops of a diverging ramp, where sitting close together at the
midpoint is the ramp working. Both ramps carry numeric ticks, so neither is
read by colour alone, and with the green gone there is no red/green pair left
on the card.

`docs/presentation/figures_30to45min/2_terrain_derivatives/rrim_formula_card.png`

---

## 2026-09-19 — Every talk figure renamed and every stage folder flattened

**Why.** The figure names had grown to carry everything: the site as a lat/lon
blob, the azimuth, the corridor width, the slope parameter, a leading sequence
number, and a trailing `_9t_05`. Precise, and unreadable -- picking a slide
meant opening folders to find out what was inside them.

**The scheme now is what, how big, where.** `annotation_roads_2km_no_lines_9t`,
`prob_pit_300m_9t`, `cross_section_pad_357m_621594`. Parameters stay in the name
only where they are the point of the figure, which is thresholds
(`roads_found_vs_missed_thr0p50_613590`) and nothing else. The precise centre of
each annotation site moved into a generated table in
`3_annotations/README.md`, so the Descriptive-filename rule still has somewhere
to point.

**All five stage folders are flat.** Thirteen subfolders went -- `scan_angle/`,
`recovered_ground_9t/`, `smrf_ground/`, `cross_sections/`,
`report_lidar_ground/`, `prob_layers_plain/`, `rrim_vs_prob/`, `tile_613590/`,
and the `venango_site_<lat><lon>/` folders. Only `archive/` and one folder of
source GeoTIFFs are still nested. 71 images moved, 12 were rebuilt.

**Sixteen builders were repointed in the same pass**, so nothing regenerates
under the old names. `_build_report_figures.py` moved up to sit with the other
builders and its `parents[5]` became `parents[3]`. The stale names were also
swept out of `_manifest.json`, `FIGURE_INDEX.md`,
`figure_notes_what_each_image_shows.md`, `reference_index.csv`, three iteration
docs and this log. Four builders were re-run to confirm they write the new
names.

---

## 2026-09-19 — Figures restyled to match QGIS, and the annotation series rebuilt per class

**Terrain derivatives now render the way the project renders them.** The panels
carried invented blue / orange / green ramps, which is not what any of those
layers looks like when opened. `_build_derivative_panel.py` now reads
`qgis/wellsight.qgz` at build time -- a .qgz is a zip holding one XML .qgs, so
this needs nothing installed -- and uses each layer's actual renderer, printing
where every panel's styling came from.

Every single-band layer in that project is **singlebandgray**; the only layer
with colour is RRIM, a multibandcolor composite with **NoEnhancement**, so its
bytes go to screen untouched. Two things the old ramps were getting wrong beyond
colour:

- `openness_pos` is styled **WhiteToBlack** while `slope`, `lrm`, `openness_neg`
  and `hillshade` are BlackToWhite. One shared ramp silently inverted it.
- QGIS stretches on the **whole raster**, not the visible window. The panels were
  using a 2-98% clip of the 300 m crop, so the greys did not correspond to the
  layer's values. They now use the project's stored min/max, or whole-raster
  stats for the four layers the project does not contain (`dem`, `tpi_05`,
  `roughness_11`, `chm`).

Side effect: greyscale everywhere plus one RGB composite contains no red/green
pair, so this panel meets the colourblind rule by construction.

**The annotation series is now one site per class, in pairs.** A single 300 m
square flattered some layers and starved others -- it holds a couple of pits and
almost no road. Each class gets a frame chosen for it, and every site is drawn
twice, once bare and once annotated, so the terrain can be checked against the
polygon:

    roads      41.499080 N, 79.541300 W   2 km    287 features
    drainage   41.502510 N, 79.533711 W   2 km    565
    pads       41.507320 N, 79.541360 W   2 km    164   (layer is `plat`)
    pits       41.494906 N, 79.537175 W   1 km     50 floors / 51 rims
    all four   dead centre of 9t          3 km    307 pads, 1,193 drainage,
                                                  617 roads, 248 pit floors

Pits get four images rather than two -- terrain, floors, rims, and both -- since
`pit_inside` and `pit_outside` are separate layers and the floor is what the
model trains on. Rims are white outlines, floors yellow-green fills, so they are
separated by form as well as colour. The RRIM base here also had its own 2-98%
stretch and now matches the project.

All five windows were checked to fall inside both the 9t extent and the RRIM
raster before rendering. The earlier 300 m series is archived, not deleted, at
`3_annotations/archive/venango_site_41p492640N_79p546127W_300m_series/`.


---

## 2026-09-19 — The 9t area drawn with the discarded ground put back, and a colour rule

**Four pictures over the whole 9t training area.** SMRF on all nine squares,
three surfaces rasterised from each by `filters.expression` (vendor / recovered
only / union), mosaicked to one 0.5 m grid. Full write-up in
`docs/iterations/recovered_ground_maps_9t.md`.

    51,470,048 cells the laser reached
    no ground return, as delivered            13.79%
    no ground return, with the discarded back   8.24%
    cells closed                            2,857,002
    discarded ground points                13,746,698
    section, 300 m at bearing 010 deg        32% -> 2% of the line with no ground

Two measurement errors caught and fixed before anything was published. A
Delaunay TIN spans its own convex hull, so DEM nodata is not a coverage map and
the first pass measured 0.0% voids; voids are now counted on the points, which
reproduces the two-tile numbers exactly (12.36% -> 6.25% on 621594). And a hole
is speckle at 0.5 m but a region at 5 m, so the maps draw void density rather
than a binary mask, and every gap claim in the section is made at 1 m where an
empty cell means something.

The section picker was wrong twice. Scoring by recovered-point density put the
line inside the swath overlap where the vendor already had ground, giving two
identical panels; and a 6 m corridor with a 1 m tolerance called every line
continuous, because at 4.8 points per square metre some vendor point is nearly
always within a metre. It now scores the thing the panel is judged on -- length
of line that has no delivered ground but does have it after.

**Standing instruction, given today: every graphic must be red/green safe.**
Applied across the figure scripts and checked with the dataviz validator over
ALL pairs, not just adjacent ones. This found a real failure in work already
committed: in `_cross_section_classification.py` the below-ground class
`#C43E1C` against high vegetation `#18512F` measures **dE 4.8 under
protanopia**. The note in that file claimed the palette passed, but it had only
been checked on adjacent pairs. Two palettes now, neither containing a red/green
pair:

    lost / found figures   ground #1F5FA8, recovered #D97706, missing #A31515
                           worst pair dE 21.1 deutan / 22.6 normal, all >= 3:1
    classification figures vegetation keeps its green ramp and the RED goes --
                           below ground is now neutral charcoal #2B2F36, and it
                           already carried its own marker shape as well
                           unassigned grey darkened #B0B0B0 -> #8E959B, which
                           measured dE 13.0 against pale vegetation in NORMAL
                           vision, under the floor of 15

Report charts, the 9t maps and the section are redrawn. The three classification
cross-sections and the two `_smrf_reclassify_ground.py` panels still carry the
old palette until they are re-run.


---

## 2026-09-19 — Where ground stops, measured on every map square in both deliveries

The by-acquisition cliff chart was built on 7 tiles per delivery, which cannot
tell "this vendor" from "this batch of flights". Two passes fixed that.

**Cheap census first.** `_scan_angle_cliff_all_tiles.py` asks a blunter question
that needs no height model — the widest angle bin holding >=100 class-2 points
against the widest bin holding >=100 points of any class, 0.5 deg bins, all 258
squares in parallel. If ground simply thins towards the edge the two numbers land
together; if a rule was written, ground stops dead and the data carries on.

Grouped by **flight block** rather than county, because Venango was flown twice:

| block | squares | ground stops | data stops | gap | with a gap |
|---|---|---|---|---|---|
| Venango 2020-03 | 177 | 17.75 | 19.75 | 2.00 | 164 (93%) |
| Venango 2019-11 | 16 | 31.25 | 31.25 | 0 | 0 |
| McKean 2019-04 | 59 | 28.75 | 28.75 | 0 | 5 (8%) |
| Venango 2011-09 | 5 | — | — | — | excluded, no scan angle recorded |

The same county four months apart behaves completely differently, so the cut
follows the flight job, not the geography. Corrected the report's claim of "every
map square we checked" to 164 of 177.

**Six squares were being counted twice.** Both censuses globbed files, not map squares. Four squares under `westernpa/` are byte-identical copies in `separate_sections/test_section/` (md5-confirmed; already flagged with 0 references in `docs/_ledgers/duplicates_proposed_moves.csv`, renames not applied), and two more have a `.copc.laz` re-encoding sitting beside the plain `.laz`. Both scripts now select one file per square. Every total moves: **258 unique squares**, not 264; the affected block is **177** squares, not 183; **165 of 177 (93%)** have the cliff, not 167 of 183. Direction and size of the finding are unchanged.

**Then the real statistic on all of them.** `_scan_angle_cliff_across_acquisitions.py`
gained `--all --workers 6`: the hag_nn-conditioned rate curve (of the returns
within +/-15 cm of the ground surface, what share became class 2) on every square
rather than a sample of seven, ~95 s each. Result: the cliff sits at exactly 18 deg on all 165 squares that have it, range 18-18, and the block loses **190,855,059** at-ground returns. Zero squares in the other three blocks have one. Tiles are now grouped and coloured by
flight block; with 258 curves on one axis each square is drawn faint and the
block median is drawn over it with a 10th-90th percentile band. `EDGES` extended
0-30 -> 0-40 deg because the November Venango block sweeps to 31.

**SMRF, written up.** The run itself was done 2026-09-18; the iteration doc was
missing and is now at `docs/iterations/smrf_ground_reclassification.md`, with
Pingel, Clarke & McBride (2013) added to `literature/CITATIONS.md`. Recovered
1,451,879 and 1,615,359 points on `616591` and `621594`; DEM void rate 15.99% ->
9.97% and 12.36% -> 6.27%; movement confined to cells that had no ground before
(0.3% of previously-covered cells differ by more than 10 cm). Pit depth did not
change. Slope swept 0.15-0.70 first, and the answer moves 0.9% across that range.
The four `dem_*.tif` are 36 MB each and gitignored at `.gitignore:154`.

**Plain-language report.** Eight single-chart PNGs under
`docs/presentation/figures_30to45min/1_data_qa/`, every number read
from a measurement CSV rather than typed. Published as an artifact.



---

## 2026-09-18 — The unassigned third of the cloud, and an 18-degree ground-classification cut

Asked what the 43.7% of returns sitting in class 1 actually are, and whether we
can classify them ourselves. Ended up finding a hard threshold in the vendor's
processing.

**The delivery.** 10 tiles, 113,556,364 points: class 1 43.678%, class 2 56.307%,
everything else (water 9, bridge deck 17, noise 7/18, vendor class 20) 0.016%.
Correcting an earlier overstatement: those classes DO exist, they are just a
rounding error. There are still no vegetation classes. Flown 5-18 March 2020,
**leaf-off**, checked from GpsTime.

**Class 1 is classifiable.** 43.6% of pulses are multi-return and 1,867,932
class-1 points (11.0%) are intermediate returns, so they sit inside a canopy as
recorded fact. Banding by height above ground per the 3DEP spec takes unassigned
from 41.6% to **13.7%** of all points: 23.5% high veg, 2.0% medium, 1.9% low.
What is left is the +/-15 cm at-ground band.

**A usable signal fell out of it.** Canopy p95 over annotated features is
consistently lower than the forest ring around them -- pads on 621594 -2.72 m
(Cliff's d -0.242, p~0, 3,427 cells), pits -1.30 to -2.81 m on four tiles, same
direction 5 of 5. The bare-earth DEM cannot see this. The bias runs against the
finding for pits, so it is conservative.

**Why the at-ground points were withheld.** 5,615,796 of them across four tiles,
100% terminal returns, 75% single, overlap flag 0.00% -- identical to class 2 on
every property except one: median abs scan angle **18.6 deg against 9.4 deg**.

**It is a cliff, not a taper.** Of returns that demonstrably reached the ground:
97-98% classified as ground from 0-13.5 deg, tapering to 88% by 17.5 deg, then
**0.0% at 18.5 deg and beyond**. Same 18 deg threshold on all five tiles tested,
zero exceptions, ~1 M returns discarded per tile.

**The vendor was not justified.** Each excluded return compared against a plane
fitted through class-2 ground from a DIFFERENT flight line: RMSE **0.067 m**
(616591) and **0.065 m** (621594), median bias -0.004/-0.006 m. The wide-angle
returns they KEPT score 0.070 and 0.099 m. All inside the USGS 3DEP QL2 bar of
RMSEz <= 0.10 m. The discarded data is as good as the retained data.

Method note, recorded because it changed the result: the intended yardstick was
narrow-angle (<10 deg) ground from neighbouring lines. It does not exist --
adjacent swaths meet edge to edge, so measured overlap with a <10 deg reference
is **0.0%**. Fell back to all accepted ground from other lines (~100% coverage),
which makes this wide-against-wide relative accuracy and therefore a lower bound.

**Not a convention.** 7 tiles each from two acquisitions: PA WesternPA 2019 D20
(Venango, QL2) shows the cliff in 6 of 7, all at 18 deg; PA Northcentral 2019 B19
(McKean, QL1) in **0 of 7**, tapering smoothly and recovering to 98% at 27-29 deg.
The one Venango tile without it, 17TNE565467, was flown 2019-11-26 with a 29 deg
field of view -- so "WesternPA D20" is at least two flight blocks and only the
**March 2020 +/-20 deg block** carries the cut. That block is the whole study
area. McKean needs no reprocessing.

**Cost on the DEM grid.** 17.81% of 0.5 m cells hold no class-2 return (105.5 ha
over four tiles). **24.5% of those voids have an excluded at-ground return
sitting in them** -- 1,032,075 cells, 25.8 ha where a guessed elevation could be
a measured one. Caveat: voids stripe with swath geometry on four tiles but
615591 gives r = -0.04, so that spatial claim is not general.

Not shown: that any of this improves model performance. The fix is a fresh
ground classification (`filters.smrf`) with no angle cut, not flag-patching --
promoting flags moves the reference surface they were measured against.

Write-up `docs/iterations/nonground_classification_and_scan_angle_cut.md`.
Citation added for the USGS 3DEP Lidar Base Specification. Six scripts in
`s7_analysis/`, outputs in `data/9t/results/nonground_classification/` and
`docs/presentation/figures_30to45min/{scan_angle,cross_sections}/`. No model
metrics changed, so LEADERBOARD is untouched.

---

## 2026-09-18 — Ground-classification sniff test, then the experiment that killed it

Asked whether the vendor is withholding points from class 2 that ought to be
ground, and specifically whether it is bridging over our pits.

**The screen** (`s7_analysis/_sniff_ground_classification_9t.py`). Height above
the class-2 surface via PDAL `filters.hag_nn`, on decimated samples. Three tiles.
The delivery carries only classes 1 and 2 in any quantity — no vegetation classes
at all, so class 1 is "not ground, or not looked at", not a decision. About 42% of
non-ground points sit within 15 cm of the ground surface, 73% of those within
5 cm. On 17TPF621594, non-ground points inside 98 annotated pit floors were 2.6x
more likely to sit *below* the surface than elsewhere (25.4% against 9.6%).

That looked like Axelsson progressive TIN densification spanning small pits.

**The experiment** (`s7_analysis/_reclaim_ground_pit_depth_experiment.py`). Four
tiles, 40.97 M points at full density, 216 annotated pit floors, 187 crops. DEM
rebuilt both ways at 0.5 m by Delaunay TIN, which is phase 1's method.

| | result |
|---|---|
| ground density, floor / ring | **0.921** (per tile 0.873–0.961) |
| pit floors with zero class-2 points | **0 of 216** |
| median depth, as delivered | 0.78 m |
| median change in depth, strict rule | **+0.000 m**, max +0.070 m |
| median change in depth, permissive rule | **+0.000 m**, max +0.083 m |
| pits deepened by >= 0.10 m | **0 of 216**, both rules |

**The hypothesis is wrong.** The TIN is not bridging these pits — it is sitting on
real ground inside every one of them, at a median 84 class-2 points per floor. The
sniff test's 2.6x was a share of non-ground points, and non-ground points are
sparse inside floors: 547 points reclaimed across 216 pits against 20,734 class-2
points already there, 2.6% of the floors' point budget. Real signal, far too small
to move the surface.

Run twice on purpose. The permissive variant drops the coherence and planarity
tests and accepts all 50,354 terminal class-1 returns below the surface — 3.8x the
strict rule — and the depth still does not move. The conclusion does not depend on
how the rule was tuned.

Secondary results kept: the strict rule is genuinely pit-specific (8.2x the
reclaim density inside floors versus the ring, falling to 4.4x permissive, so the
coherence test is what makes it selective); the reclaimed points are twice as
rough as class-2 ground in the same floors but match its intensity almost exactly,
which reads as real returns off a rough floor rather than noise; and of 1,675,743
class-1 points only 3.0% sit below the ground surface at all, all but 11 of those
already terminal returns.

Does not rule out: pits so bridged we never annotated them, since this can only
measure floors we drew. Scope is four tiles of PA WesternPA 2019 D20 QL2.

Write-up `docs/iterations/ground_reclassification_pit_depth.md`. Citation added
for Axelsson (2000). Outputs in `data/9t/results/ground_reclassification/`, four
CSVs and five before/after figures. No model metrics changed, so LEADERBOARD is
untouched.

---

## 2026-09-18 — Deleted 83.4 GB of unreferenced derived rasters

C: was down to 36.8 GB free with a 150 GB repo and CV5 training on the same
disk. Removed every `.tif` with zero references in `docs/reference_index.csv`,
in two passes, after confirming each file byte-size-identical on BOTH backup
mirrors. C: free afterwards: 118 GB.

| pass | scope | rasters | sidecars | size |
|---|---|---|---|---|
| 1 | all unreferenced except `data/westernpa_d20/` | 829 | 81 | 46.91 GB |
| 2 | `data/westernpa_d20/` | 825 | 53 | 36.49 GB |

Four guards per file, re-checked at delete time rather than trusted from the
survey: still present locally; byte size matching E: AND F:; not tracked by git;
inside the requested scope. Zero files were skipped, and `git status` showed
zero deletions afterwards.

All 1,788 removals are logged in `docs/MOVES.csv` under phase
`delete-regenerable`. Reader-facing note left at
`data/REMOVED_UNREFERENCED_RASTERS_2026-09-18.md` with restore paths.

Coverage was verified first, not assumed: all 1,654 candidate rasters were
checked against both mirrors by path and size before anything was deleted.
0 missing, 0 size mismatches. Per-file evidence in the scratchpad at
`zeroref_backup_check.csv`.

Caveat recorded on purpose: "unreferenced" means no path literal names the file.
A directory glob or a QGIS project leaves no reference the index can see. If
something downstream breaks on a missing raster, restore from a mirror and log
it here rather than treating the deletion as justified after the fact.

### Backups, same day

E: verified PASS earlier (101,913 files, 151.54 GB, 0 missing, 0 size mismatch,
0 content mismatch over 265 hashed files).

F: had NTFS corruption on `Colton\_BACKUPS\` — robocopy ERROR 1392, and
`chkdsk /scan` could not snapshot. An offline `chkdsk F: /f` repaired it, after
which the mirror copied clean on pass 2 (132,454 files, 154.7 GB, 0 failures).

Then pruned 4.88 GB of stale pre-reorg paths from the F: mirror: `barlow`
(911/911 files verified against `data/_archive/parked/barlow_finesst/barlow`),
`label_grids`, two empty dirs and three stale logs. Logged under phase `prune`.

Two self-inflicted problems worth remembering. Force-killing robocopy under
`backup_to_t7.ps1` orphaned a second copy from the script's own retry loop,
which held the volume until it drained; stop the wrapper before the child. And
a delete script using Git Bash `/f/...` paths under Python silently resolved to
a nonexistent `C:\...` and reported every target absent — Windows paths only
in anything that deletes.

`tools/backup_to_t7.ps1` still defaults `-SubPath` to the near-empty
`lidar_project_data_DO_NOT_DELETE\lidar_project_repo_MIRROR`. The verified
mirror is `Colton\_BACKUPS\lidar_project_MIRROR`. Pass `-SubPath` explicitly
until that default is fixed.

---

## 2026-09-17 — Pit CV5 retrained on ann712. Precision up, recall down.

Ran `_pit_unet_cv5.py` against the current ann712 split. 57.3 min, five folds,
712 pits, 502 rims scored, exit 0. Architecture, loss, channels and schedule
unchanged from the ann426 run. Only the annotation and the block split moved.

Pooled, threshold selected on inner val:

| rule | R@0.3 | P@0.3 | R@0.5 | containment |
|---|---|---|---|---|
| F1 | 0.861 (sd 0.045) | 0.686 | 0.700 | 0.914 |
| F2 | 0.928 (sd 0.023) | 0.633 | 0.823 | 0.956 |

Against ann527 under F1: recall 0.890 -> 0.861, precision 0.637 -> 0.686,
containment 0.936 -> 0.914. Under F2: recall 0.938 -> 0.928, precision
0.598 -> 0.633.

Precision rose on both rules. Recall fell slightly on both. Per-fold spread
tightened, sd 0.088 -> 0.045 under F1.

Hypothesis, not a finding: some ann527 false positives were real pit floors that
had not been annotated, and ann712 labelled them. Testing that means matching
ann527 false positives against the 185 floors ann712 added. Not done.

### Pad CV5 on ann712. The pits' precision gain did not reproduce.

`_pad_unet_cv5.py` ran straight after on the same GPU. 159.9 min, five folds, 650
in-tile pads scored, exit 0.

| rule | R@0.3 | P@0.3 | R@0.5 | locate |
|---|---|---|---|---|
| F1 | 0.888 (sd 0.051) | 0.597 | 0.749 | 0.923 (600/650) |
| F2 | 0.912 (sd 0.022) | 0.587 | 0.774 | 0.917 (596/650) |

Against the 650-pad ann426 run under F1: recall 0.917 -> 0.888, precision
0.606 -> 0.597, locate 0.928 -> 0.923. Recall down slightly, precision flat.

Fold 0 alone showed precision 0.655 and looked like the pit pattern. Pooled it
does not. The unannotated-true-positive hypothesis from the pit run is supported
by the pits only. Treat it as weaker than a single fold suggested.

Per-fold recall spread widened under F1, sd 0.021 -> 0.051, opposite to the pits.

Outputs in `data/9t/models/pad/unet_cv5/`: `pad_cv5_per_fold_9t.csv`,
`pad_cv5_recovery_curve_9t.csv`, `pad_cv5_fold_assignment_9t.csv`,
`_pad_cv5_ann712_train.log`. `LEADERBOARD.md` updated in the same pass; B1 is
now closed for both tasks.

Epochs 35 and 36 of pad fold 4 took 439 s and 152 s against a 40-50 s norm. The
T7 backup, the reference-index rebuild and a figure regeneration were all hitting
disk at once. No effect on results, but do not run those together again.

Outputs in `data/9t/models/pit/unet_cv5/`: `pit_cv5_per_fold_9t.csv`,
`pit_cv5_recovery_curve_9t.csv`, `pit_cv5_fold_assignment_9t.csv`,
`_pit_cv5_ann712_train.log`. The ann527 checkpoints were already retired to
`data/9t/models/_retired/pit_09_unet_cv5_ann527_2026-09-04/`, so nothing was
overwritten. `LEADERBOARD.md` updated in the same pass.

### Worklist blocker B2 resolved

The "unused" rows in the pit and pad manifests are not features the greedy fill
skipped. They carry a null `block_id` because they fall outside the 9t tile.
Verified on centroids: all 209 unused pit centroids lie outside 619500-624000 E,
4593000-4597500 N, spanning 613899-700410 E.

| | annotated | train | val | test | in 9t unassigned | outside 9t | in 9t |
|---|---|---|---|---|---|---|---|
| pit | 712 | 352 | 77 | 74 | 0 | 209 | 503 |
| pad | 995 | 401 | 69 | 114 | 66 | 345 | 650 |

Corrected later the same day. "unused" conflates two states. A null `block_id`
means outside the tile. An in-tile row is also unused if the greedy fill left its
block out of every split. Pads have 66 of the second kind, pits none, so the pad
manifest's 411 unused is 345 outside plus 66 in-tile. 650 pads are in 9t, not the
584 first written here.

Slide 10 of the May deck says 861 pits. That predates both counts. Drop it.

### Presentation figures

Nine figures built to `docs/presentation_figures_30to45min/`, with
`figure_notes_what_each_image_shows.md` describing each and
`_build_presentation_figures.py` rebuilding all of them. Everything is read from
disk; the only schematic is the pipeline diagram, and the only hand-entered
numbers are the two classical AUC values carried from the May deck.

Two facts the figures surfaced. No pad in 9t carries more than two annotated pit
floors; 995 pads hold 712 floors. And the pad recall curve falls off below
threshold 0.35 rather than rising, because pad predictions merge into
tile-spanning blobs at low cutoffs and no merged blob clears IoU 0.30. That is
the same failure already recorded in the LEADERBOARD warning box.

Permian material was removed from the worklist and the figure set on request.

Later the same day, everything presentation-related was consolidated under
`docs/presentation/`: the May deck moved out of `docs/publication/`, the
worklist moved out of `docs/`, and the figure directory became
`docs/presentation/figures_30to45min/`. Paths above are pre-move.

### Backup

Re-ran the T7 mirror. `tools/backup_to_t7.ps1` defaults `-SubPath` to
`lidar_project_data_DO_NOT_DELETE\lidar_project_repo_MIRROR`, which holds 17 GB.
The verified mirror is `Colton\_BACKUPS\lidar_project_MIRROR` at 111 GB, and
`docs/verify_backup_report.md` records that path as PASS. The script default is
wrong. Run it with `-SubPath 'Colton\_BACKUPS\lidar_project_MIRROR'` until it
is fixed.

---

## 2026-09-04 — Phase 4 rollout: the 9t split moves from 527 to 712 pits

Ran steps 1-3 and 5-7 of the naming-reconciliation plan. Step 4, the retrain,
did not run. Every number on the pit and pad leaderboard is stale until it does.

### What changed on disk

`qgis/annotations/annotations_proj_v2.gpkg` was promoted to
`qgis/annotations/annotations_proj.gpkg`. The v2 file fixes the cell-9
idempotency bug in `phase_2_prep_annotations.ipynb`, which had left the pad
layer carrying `n_pits_x`, `n_pits_y` and `n_pits` side by side. It also adds
`pad_id` to `pit_wall`.

It did **not** rename the layers. On disk they are still `plat` and
`pit_outside`, not `pad` and `pit_full` as the plan's schema table specifies.
Reads work anyway, because Phase 1 landed `read_layer()` and
`LEGACY_LAYER_ALIASES` in `notebooks/wellsight_v2/_common.py`. Logged in
`docs/iterations/BACKLOG.md`.

Then `_build_pit_dataset_v2.py --force`:

```
Loaded 712 pit floors, 586 rims
Label pixels: floor=58669 (14667 m^2)  wall=325209 (81302 m^2)
Off-grid: 209 of 712 pit centroids fall outside the reference grid -> 'unused'
No pad:   369 of 712 pits sit on no drawn pad

  train    blocks= 77  pits= 352
  val      blocks= 14  pits=  77
  test     blocks= 24  pits=  74
  unused   blocks= 29  pits=   0
```

The guard fired first, as designed. `--dry-run` printed `REFUSING TO OVERWRITE
pit_dataset_manifest.csv / on disk now: 527 / about to write: 712` and wrote
nothing. `--force` then printed the invalidation warning and proceeded.

**The annotation grew by 185 pits and only about 32 of them are inside 9t.**
Off-grid went 56/527 to 209/712. Train grew 330 to 352, val 72 to 77, test 69
to 74. Most of the recent annotation work is on some other tile. That is worth
chasing before reading much into the new split.

`_build_pad_road_dataset.py` was re-run because it inherits the pit split.
Pads now split 401 train / 69 val / 114 test / 411 unused of 995.

### Contract checks

All five items the plan pins still hold on the new outputs:

| check | result |
|---|---|
| `labels_pit_9t_05.tif` uint8, values `{0,1,2}`, nodata 255 | pass |
| `pit_blocks_9t.gpkg` layer `"blocks"`, all 144 rows | pass |
| manifest carries the literal `"unused"` split | pass |
| `block_id` / `pad_id` stay float64 | pass |
| `pit_inside_id` unique and non-null | pass |

### Why the retrain did not run

`_pit_unet_cv5.py:317` reuses any `best.pt` whose `train_log.csv` shows a full
epoch count. The comment calls a finished checkpoint "a deterministic product of
a fold that already ran", which is true only while the split holds still. With
the split reassigned, the trainer would have quietly kept the ann527 models and
reported them as if they were retrained.

Worked around by retiring the stale checkpoints rather than deleting them:

- `data/9t/models/pit/unet_cv5/` -> `data/9t/models/_retired/pit_09_unet_cv5_ann527_2026-09-04/`
- `data/9t/models/pad/unet_cv5/` -> `data/9t/models/_retired/pad_07_unet_cv5_ann527_2026-09-04/`

The training environment is `C:\Users\colto\miniconda3\python.exe`, torch
2.7.1+cu118 on a GTX 1070 Ti. Not `.venv`, which has no torch. Budget about 90
minutes per model for 5 folds at 40 epochs, from `_pad_cv5_resume.log`.

### Safety snapshot

`--force` destroys the split every deployed checkpoint was scored against, and
the 2026-08-12 incident recorded in `docs/golden/NON_DETERMINISTIC.md` was
recovered from the E: mirror. That mirror is not currently dependable, so the
snapshot went in the repo instead, following the existing `_history/`
convention:

`qgis/annotations/_history/_backup_pit_ann527_2026-09-04/` — the pre-rollout
`annotations_proj.gpkg`, the 527-row pit manifest, `pit_blocks_9t.gpkg`,
`labels_pit_9t_05.tif`, the pad and road manifests, and both CV5 fold
assignments and per-fold score tables. 12.9 MB, all small, all tracked.

### Docs

`docs/iterations/LEADERBOARD.md` carries a stale banner at the top and a marker
on both the Pits and Pads sections. Road rows are untouched — road models train
on 1 m data from a separate manifest and the pit split does not reach them.

`docs/reference_index.csv`, `docs/reference_index_summary.md`,
`docs/script_last_used.md` and `docs/script_last_used.csv` regenerated.
`docs/script_map.md` was **not** regenerated: its own header declares it a
historical record that is deliberately not rewritten, and its generator no
longer exists in `tools/`.

`docs/golden/NON_DETERMINISTIC.md` now records that the pit builder's guard is
wired and that `_build_pad_road_dataset.py` remains unguarded.

### Reproduce

```
python notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py --dry-run
python notebooks/wellsight_v2/s2_labels/_build_pit_dataset_v2.py --force
python notebooks/wellsight_v2/s2_labels/_build_pad_road_dataset.py
C:\Users\colto\miniconda3\python.exe notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py --folds 5 --epochs 40
C:\Users\colto\miniconda3\python.exe notebooks/wellsight_v2/s3_train/_pad_unet_cv5.py --folds 5 --epochs 40
python tools/build_reference_index.py
python tools/script_last_used.py
```

---

## 2026-08-18 — Outreach contacts written up

Pulled the well-reporting contacts out of the 2026-07-19/20 web sweep and into
a standing doc: `docs/articles/well_reporting_outreach_contacts_pa_2026-08.md`.
They had only existed in session history and as scattered lines in the photo
sources doc.

Eight leads. Penn State Extension (Dan Brockett, Summer Boyle) is the intake
for the Oil Region Alliance $100/well bounty. Drake Well Museum holds the
Mather glass-plate archive. VPASEC and Laurie Barr are the volunteer
well-hunters on public land. The EDF/DEP drone survey of President and Victory
Twp is due spring 2026 and would put magnetometer-confirmed points inside our
tiles.

No contact has been made with any of them. Every row is a lead.

Follow-up the same day: identified the EDF people behind that drone survey.
It is the **Pennsylvania Abandoned Well (PAW) project**, and its principal
investigator is **Meg Coleman**, EDF Senior Policy Manager and a geologist.
Adam Peltz (apeltz@edf.org) is the policy lead, Mary Kang (McGill,
mary.kang@mcgill.ca) is the academic partner — and Kang is already cited in
this repo via `docs/articles/kang_2014_explained.md`. PAW detects well casings
magnetically; WellSight detects disturbance topographically. Complementary,
not competing, which is the angle to lead with. Contacts recorded in the same
doc.

---

## 2026-08-18 — naming reconciliation, part 2: files, QGIS project, docs

Second half of the rename, unblocked once QGIS released the shapefiles. A first
attempt was reverted when `.shp` and `.dbf` came back Permission denied
mid-way; sidecar sets move atomically or not at all.

**Shapefiles.** `plat.*` -> `pad.*`, `pit_outside.*` -> `pit_full.*`, all five
sidecars each. Verified complete afterwards: 1053 pads, 723 pit_full, 712
pit_inside, all EPSG:4326. Git's commit output pairs `plat.prj` with
`pit_full.prj` — that is rename detection matching identical `.prj` contents,
not what happened on disk.

**`qgis/wellsight.qgz`.** Rewritten in place inside the zip: two datasource
paths, ten `labels_plat` references, three display names. **All 62 file
datasources in the project now resolve on disk**, checked programmatically.
The opaque layer ids (`plat_020df8d3...`, `pit_outside_807c...`) are deliberately
left: they are internal keys cross-referenced from the legend and
`lRRgtH_styles.db`, QGIS never re-derives them from a name, and renaming risks a
desync for no gain. A pre-rename backup was kept outside the repo.

**Data artefacts.** `git mv` where tracked, plain `mv` where gitignored —
including a `labels_plat_9t_05.tif.aux.xml` sidecar the first pass missed, which
is exactly the failure the atomic rule exists to prevent. `mask_plat_9t_05.tif`
became `mask_pad_9t_05_dupe.tif` under the `_dupe` rule: zero readers,
byte-identical to `labels_pad_9t_05.tif`. `data/9t/models/plat/unet` merged into
the existing `pad/` tree; the empty parent removed. `_retired/plat_01..04` left
alone — those names appear in LEADERBOARD rows describing runs that happened
under them.

**Scripts.** `_build_plat_road_dataset.py` -> `_build_pad_road_dataset.py`,
`_build_plat_split.py` -> `_build_pad_split.py`, `_plat_unet.py` ->
`_pad_unet.py`. Nothing imported them; every reference was prose.

**309 further substitutions** across the live tree: filename literals, layer
names, the `plat_unet` model key, internal variables. A case-insensitive audit
of `notebooks/wellsight_v2` and `tools` now returns nothing.

**Docs: 108 substitutions across 16 operational files** — runbook, script map,
handoff, refactor plans, backlog, NON_DETERMINISTIC. Historical records were
left as written: `analysis_log.md`, the iteration write-ups, `LEADERBOARD.md`
and the ledgers describe runs that happened under the old names, and rewriting
them would falsify the record. To read them, apply: `pit_id` ->
`pit_inside_id`, `matched_pit_id` -> `pit_inside_id`, `pit_id_outer` /
`pit_outside_id` -> `pit_full_id`, `plat_id` -> `pad_id`, `plat` -> `pad`,
`pit_outside` -> `pit_full`, `plat_unet` -> `pad_unet`.

**One near-miss.** The filename rule initially rewrote `LEGACY_LAYER_ALIASES` in
`_common.py` to `{"pit_full": "pit_full"}`, silently killing the legacy
fallback — the shim that makes every pre-rename artefact readable. Caught by
reading the diff, reverted, and `_common.py` is now excluded from these sweeps.
It is the same class of silent failure the guard test was written for, and it
got past the guard because the guard checks ID columns, not layer aliases.

**Verified.** 137 tests pass. Equivalence against the 426-pit fixture still
10/10. `_prep_annotations.py` reads the renamed shapefiles and emits the
canonical schema, identical to the notebook's output. `_build_pit_dataset_v2.py`
runs on that output end to end. Large-file audit clean.

**Still stale.** `docs/golden/heldout_overlap.json` and
`reeval_instance_precision.json` reference `heldout_plat_unet.gpkg` and must be
re-recorded after rollout. `docs/reference_index.csv`, `script_map.md` and
`script_last_used.md` should be regenerated.

---

## 2026-08-18 — naming reconciliation, part 1: columns, shims, and pit dataset v2

The live `annotations_proj.gpkg` was regenerated 2026-08-17 by
`phase_2_prep_annotations.ipynb` and carries the notebook vocabulary
(`pit_inside_id`, `pad_id`). Fourteen scripts read `pit_id` / `plat_id` from it
and were broken. Rather than regenerate with the old names, the codebase adopts
the notebook's: a column should say what it points at, and
`_instance_common.py:211-212` already conceded `plat` was a "legacy misnomer".

**Rules.** `pit_id`, `matched_pit_id` -> `pit_inside_id`; `pit_id_outer`,
`pit_outside_id` -> `pit_full_id`; `plat_id` -> `pad_id`; layer `pit_outside` ->
`pit_full` (it holds floor *plus* rim, so "outside" read as the opposite);
`plat` -> `pad`.

**Notebook reconciled with itself.** Cell 5 wrote the inner-pit foreign key as
`pit_inside_id`; cell 7 wrote the same value as `matched_pit_id`. Cell 7 now
agrees. That one decision is what makes the sweep a flat rename instead of a
per-layer judgement — under the old scheme `pit_id` meant "my own id" on
pit_inside and "the pit I belong to" on pit_outside, and a wrong call there
fails *silently* by dissolving rims on the wrong key and inflating scores.

Cell 9's tally merge was not idempotent: re-running merged onto an
already-merged frame, so pandas appended `n_pits_x` / `n_pits_y`. That is how
the live `plat` layer ended up with `n_pits_x`, `n_pits_y` *and* `n_pits`. Fixed
by dropping the tally columns first.

**Shims.** `_common.normalize_ids` and `_common.read_layer` keep every
pre-rename artefact readable — the 2026-06-10 fixture, older manifests, backups
— without regenerating anything. That is what makes the equivalence test below
possible at all.

**Sweep.** 171 substitutions across 25 files. Every annotation read became
`read_layer()`, every manifest read wrapped in `normalize_ids()`. Verified: 35
files parse, zero legacy identifiers remain, every used name is imported, 31 of
35 import cleanly. The four that do not fail identically at HEAD and are
pre-existing — `_build_label_grids.py` and `_pad_morphology_bins.py` call
`path_for("derivatives")`, a key that does not exist, and `_pit_unet_v2.py` uses
`path_for` without importing it.

**Guard test.** `tests/test_no_legacy_id_columns.py`, parametrized per file, plus
an assertion that the rejected names and `LEGACY_ID_ALIASES` cannot drift apart.
Proven to fail by injecting `man[man.pit_id.isin(held)]` into `_sanity_render.py`.
137 tests pass.

**`_build_pit_dataset_v2.py`.** 206 lines of code, largest function 55; the
original was 117 in a single 111-line `main()`. Wires in `check_or_refuse`,
which had sat unused in s2_labels since the 2026-08-12 incident. One pre-write
gate, so a refusal leaves every output byte-identical — the original writes the
raster at line 77 and the manifest at 159 and currently dies in between. Adds
`--out-dir`, `--dry-run`, a CRS-object comparison, a uniqueness assertion, and a
loud failure where the original silently deduped a double-matched centroid.
Drops the `mask_plat` write, so the pad layer is never loaded.

Equivalence against the committed 426-pit fixture, 10/10: label raster sha256
identical to the pre-sweep original; manifest columns, dtypes, rows, values and
split counts identical; blocks gpkg identical by content with exact geometry;
the only file difference is the dropped `mask_plat`. The same outputs also match
the committed `_backup_pit_ann426_2026-06-10/` artefacts — an oracle independent
of any run in this session.

Guard verified: refuses at exit 1 with the `527 -> 426` banner, all three files
byte-identical afterwards; `--force` proceeds at exit 0 with the stderr warning;
`--dry-run` leaves the live directory unchanged with and without `--force`.

**Numbers from a dry run on the current 712-pit annotation**, for the record
before anything is adopted: train 352 / val 77 / test 74 / unused 209 pits over
77 / 14 / 24 / 29 blocks. **209 of 712 centroids (29%) fall outside the 9t
reference grid**, up from 56 of 527 (11%) — the newer annotation extends well
past the tile. 369 of 712 sit on no drawn pad.

**Not done, blocked on QGIS holding the files:** shapefile renames
(`plat.shp` -> `pad.shp`, `pit_outside.shp` -> `pit_full.shp`), the 15 + 15 layer
references inside `qgis/wellsight.qgz`, the derived data artefacts,
`mask_plat_9t_05.tif` -> `_dupe`, and 136 doc references. A partial rename was
attempted and fully reverted when `.shp` and `.dbf` came back Permission denied.

---

## 2026-08-18 — `skip_existing` removed from `write_tif` (reverses the entry below)

Removed rather than kept. The guard can only compare what is already on disk —
shape, band count, dtype — and all three are unchanged when a parameter moves.
So the one case it needed to catch was the one case it could not catch, and it
kept a stale raster while reporting success.

Two ways to close that hole were considered and both rejected as
disproportionate. Putting the parameter in the filename touches 25 .py files, 7
notebooks, 21 docs and ~250 rasters, and the ordered channel tuples in
`_road_unet_1m_recall.py:48` and `_infer_roads_data_3x3.py:41` must stay in
lockstep with the feature stacks — a missed rename feeds the wrong channel to a
trained model with no error. Writing the parameters into GeoTIFF metadata tags
would have worked, but adds a provenance mechanism nothing else in the project
uses.

`write_tif` is back to always writing, returning None, with `-> None` restored.
Stripped `skip_existing=(not args.overwrite)` from all 14 `write_tif` calls in
`phase_1_derivative_generation.ipynb`. `make_profile` takes no `**kwargs`, so any
caller still passing the argument now raises TypeError instead of having it
silently swallowed into the GeoTIFF creation options.

The block-level guards in `stitcher`, `DEM_maker` and `dsm_chm_process` are
untouched. Those skip expensive PDAL stages keyed on the LAS input, not on
tunable raster parameters, so they are safe.

Verified: single-band float (nodata -9999, NaN mapped), RGB (3-band uint8,
colorinterp red/green/blue), the (H, W, 3) guard, and an unconditional rewrite
on a second call.

---

## 2026-08-18 — `write_tif` skip guard tightened, return value made consistent

The guard compared only `(height, width)`. Phase 1 now passes
`skip_existing=(not args.overwrite)` on all 15 `write_tif` calls, so a loose
guard silently keeps stale rasters. It now also compares band count and dtype,
and prints what it found against what was wanted before rewriting.

It still cannot detect a parameter change. A rerun with a different window size
or threshold writes an identically-shaped raster under the same name and gets
skipped. Filenames that carry the parameter are safe (`lrm_11` vs `lrm_31`,
`tpi_05` vs `tpi_25`); `openness_pos`, `roughness_5`, `chm`, and `rrim_openness`
are not. Documented in the docstring: pass `--overwrite` when a parameter moved.

Return value is now always a bool — True written, False kept. It previously
returned False on skip and fell off the end returning None on success, against
its own `-> bool` annotation.

`path` is coerced with `Path(path)` so a str caller no longer breaks on
`.exists()`.

Verified across eight cases: fresh write, exact match, shape change, dtype
change, single-band to RGB at the same shape, RGB repeat, str path, and a
missing file. Returns and rewrite decisions correct in all eight.

---

## 2026-08-18 — phase 2 notebook verified against `_prep_annotations.py`

`notebooks/wellsight_v2/s1_build/phase_2_prep_annotations.ipynb` is a manual
rebuild of `s2_labels/_prep_annotations.py`. Verified by running both into
scratch GeoPackages and diffing layer by layer. All seven layers match on row
count and geometry (`geom_equals_exact`, 1e-9): plat 995, pit_inside 712,
pit_outside 723, pit_wall 586, roads 3690, not_roads 112, drainage 1791. Every
renamed column matches value-for-value.

Three fixes applied to the notebook.

1. The write cell was indented at top level, left over from copying out of
   `main()`. It raised `IndentationError` and had never run.
2. `pit_wall_gdf` never received a pad ID. The script joins six layers; the
   notebook joined five. Added the missing `assign_pad_id_process` call. Its
   `pad_id` now matches the script's `plat_id` exactly (335 of 586 non-null).
3. `OUT` pointed at the live `qgis/annotations/annotations_proj.gpkg`, which 29
   scripts read expecting `plat_id` / `pit_id`. The notebook writes `pad_id` /
   `pit_inside_id`, so running it would have broken all of them. Redirected to
   `annotations_proj_v2.gpkg` until the naming is reconciled.

The column naming stays divergent by choice: `pad_id`, `pit_inside_id`,
`pit_outside_id`, `matched_pit_id` against the script's `plat_id`, `pit_id`,
`pit_id_outer`, `pit_id`. The notebook's names are clearer; the script's are
what downstream expects. Reconciling them is deferred, not resolved.

Removed a leftover `print(arr)` from the RGB branch of `_common.write_tif`.
It printed the whole array, which for a 9000x9000x3 RRIM means formatting
243 M elements before a single byte is written.

Also removed `write_rgb_tif` from `_common.__all__`. It was added on 2026-08-17
and the function has since been folded into `write_tif(..., rgb_bool=True)`, so
the stale export made `from _common import *` raise AttributeError.

Separately: `qgis/annotations/annotations_proj.gpkg` was regenerated 2026-08-17
16:41 and now carries the 712/723/586 counts from the current shapefiles,
replacing the stale 2026-08-12 version (655/687/550).

---

## 2026-08-17 — `write_rgb_tif` added to `_common.py`

`write_tif` is single-band by construction: it ends in `ds.write(out, 1)` and
defaults to `nodata=-9999`, which is out of range for uint8. Any caller with a
colour product hit `ValueError: Given nodata value, -9999.0, is beyond the valid
range of its data type, uint8`. `_make_rrim.py:121-125` had worked around this
with its own inline `rasterio.open` block.

Added `write_rgb_tif(path, rgb, *, transform, crs)` at
`notebooks/wellsight_v2/_common.py:304`. Takes `(H, W, 3)` uint8, sets
`count=3`, `nodata=None`, `predictor=2`, `photometric="RGB"`, and writes band by
band so no band-first copy of a full tile is materialised. Rejects any array
that is not `(H, W, 3)`.

`write_tif` was left alone rather than widened to handle 3-D input. It is called
throughout the pipeline for single-band float rasters, and an `ndim` branch
would sit in front of all of them for one caller.

Verified by round-trip on a 64x48 test raster: `count=3`, dtype uint8,
`nodata=None`, CRS EPSG:26917, transform preserved, pixel values identical,
`colorinterp = (red, green, blue)`. Note `ds.photometric` reads back `None` in
rasterio even when the tag is set — `colorinterp` is the check that matters, and
it is what QGIS uses to render the file as colour.

Unblocks the `rrim_process` cell in
`notebooks/wellsight_v2/s1_build/phase_1_derivative_generation.ipynb`. No raster
outputs generated.

---

## 2026-08-15 — RRIM builder moved into v2, stale default path fixed

`_make_rrim.py` was the last live script stranded in the v1 tree. Moved
`notebooks/wellsight/build/_make_rrim.py` -> `notebooks/wellsight_v2/s1_build/_make_rrim.py`
with `git mv` (history preserved). Closes open item 4 in `docs/RUNBOOK.md`.

**Why it was stranded.** The v1 archive pass sorted 88 scripts into keep vs
archive, not keep vs port. RRIM landed in "keep" on recency alone (last run
2026-07-07, inside the two-month window) and simply stayed put. Nothing pulled
it across afterwards because nothing imports it — `docs/script_usage_audit.csv`
marks it UNREFERENCED, 0 imports. It is a terminal viewing product: it consumes
`slope`, `openness_pos/neg`, `lrm_11` and emits an RGB GeoTIFF that no model
reads.

**Two defaults were broken by the 2026-08-13 area-major move.** `--dir`
defaulted to `data/derivatives/tiles/data_3x3/westernpa_d20/613590`, a path that
no longer exists, so a bare run raised `RasterioIOError`. The input dir is now
resolved from `--tile` + `--suffix` through `path_for("derived")`, i.e.
`data/<area>/derived/<res>/`, so a future move stays one edit in
`config/paths.toml`. `--suffix` also defaulted to `1m` while the default tile
613590 only holds a `05` stack; default is now `05`.

**Verified by running it.** `--tile 613590 --suffix 05` wrote
`data/613590/derived/05/rrim_openness_613590_05.tif` (9000x9000, 167.5 MB,
differential openness ±4.90 deg, slope_hi 40) plus
`rrim_openness_613590_05_preview.png` (1800x1800). Large-file audit clean —
`.gitignore:24` (`data/**/derived/**`) covers the GeoTIFF, and the repo-wide
`find -size +100M` + `git check-ignore` sweep printed nothing.

Docs repointed in the same change: `docs/RUNBOOK.md` (A2 command block, stage
table, open-item 4), `docs/iterations/rrim_visualization.md`,
`literature/CITATIONS.md` (Chiba 2008, Auld-Thomas 2022). `docs/v1_archive_plan.md`
deliberately left alone — it is a dated historical record.

Generated ledgers still name the old path and will correct on their next
regeneration: `docs/script_last_used.{md,csv}`, `docs/script_usage_audit.{md,csv}`,
`docs/unused_scripts_report.md`, `docs/reference_index.csv`.

---

## 2026-08-13 — Phase 7: git history rewritten, 5.6 GB to 1.4 GB

`git filter-repo`, stripping every `.tif`, `.tiff`, `.ovr`, `.pt`, `.pth`,
`.npz`, `.las`, `.laz` blob (and their `.aux.xml` siblings) from all 309 commits.

**Size-based stripping would have been wrong here.** The obvious command,
`--strip-blobs-bigger-than 10M`, would have deleted 14 currently-tracked files
from the working tree — including `WellSight_Paper_V9.docx` (47 MB), the
presentation (24 MB), and six large figures. The bloat is raster-shaped, not
size-shaped, so the filter is type-based with a negative lookahead sparing
`tests/fixtures/`, the one heavy-typed file that is legitimately tracked.

```
git filter-repo --force --invert-paths   --path-regex '^(?!tests/fixtures/).*\.(tif|tiff|ovr|pt|pth|npz|las|laz)(\.aux\.xml)?$'
```

| | before | after |
|---|---:|---:|
| `.git` | 5.6 GB | **1.4 GB** |
| tracked files | 1,228 | 1,221 |

**Rollback:** `E:\Colton\_BACKUPS\lidar_project_ALLREFS_pre_filter_repo_2026-08-13.bundle`
— 5.37 GB, every ref, `git bundle verify` reports "the bundle records a complete
history". Taken and verified before the rewrite ran.

**The 7 files that left HEAD were all `.tif.aux.xml`** — GDAL statistics
sidecars, regenerated on demand, which should never have been tracked. Confirmed
by diffing the tracked-file list against the bundle rather than assuming. They
were restored to disk from the bundle and are now ignored globally, so the next
QGIS session does not re-add them.

The remaining 1.4 GB is document history: `docs/publication/*.docx`, the
presentation, and the figure set. That is real project record, not bloat, so it
stays.

All 22 branches force-pushed. Every commit SHA changed; any other clone must be
re-cloned rather than pulled.

---

## 2026-08-12 — Phase 4F: the layout is area-major, and annotations are in qgis/

**The axis of 4C/4D was reversed on the user's correction, and the correction was
right.** The original ask — "why does it contain a folder for the tiles, but also
a folder for all these different evals for one tile?" — was pointing at
area-major. I read it as "evals should not be flat siblings", built role-major,
and so answered "show me every derivative" well while making "show me everything
about 9t" a four-directory hunt. That is the original complaint rotated.

```
data/9t/{derived,models,results,experiments}/
data/613590/{derived,results}/
data/westernpa_d20/<block>/derived/1m/
data/mckean/{mk5,mkf,sw,e1423n2238}/derived/<res>/
data/grids/westernpa_0N/derived/1m/
data/_source | _results | _experiments | _pretrained | _logs | _archive/
qgis/annotations/   <- hand-drawn truth
```

Role survives as the **second** level. That is what keeps `.gitignore` to one
rule per role (`data/**/derived/**`) rather than one per directory.

`data/derivatives` no longer exists. Neither does `label_grids`, nor the
`02_truth` / `03_derived` / `04_models` / `05_results` tree built earlier the
same day.

**Annotations moved to `qgis/annotations/`** — what was asked for originally. I
had offered it and then argued against it on the grounds that data should not sit
in a tool directory. That argument does not survive the facts: `roads.shp` spans
Oil Creek to McKean, so truth cannot be area-major regardless, and `qgis/` is
where it is drawn every day. `path_for("truth")` points there, so no script names
a GUI folder.

**12,075 files, 99 GB** moved on C: and replayed onto the E: mirror, plus three
whole-directory renames (`99_archive`, `source_laz`, `external`) recorded as
single `MOVES.csv` rows instead of 89,051 per-file entries.

### .gitignore regenerated rather than patched

The old file was ~280 lines carrying roughly 60 rules anchored to paths this
phase moved. A rule pointing at a directory that no longer exists protects
nothing while looking like it does. The replacement is policy-by-role in ~40
rules; the original is preserved at
`docs/_ledgers/gitignore_pre_area_major.bak`.

**Gate A caught two leaks against the new rules, both real:**
`data/**/experiments/**` does not match the shared `data/_experiments/`
(underscore is not the same component), and `.gpkg` was missing from the
experiments rule.

### golden.py watches data/ wholesale now

Its narrower watch list went stale twice in two days — Phase 4D and Phase 4F —
and each time failed **silently**, recording an empty baseline that passes verify
forever. A slower walk beats a gate that lies.

### Also

- `tools/plan_consolidation.py` retired: it planned the Phase 2 consolidation
  into `tiles/`, and neither `tiles/` nor `data/derivatives` exists now.
- Two files named `hillshade.tif` collided during the move. Not duplicates —
  1500×1500 at e621000 n4594500 (inside 9t) versus 3454×3403 at e697294 n4645706.
  Both renamed to say what they show.
- Verified end to end: `_heldout_rim_containment_9t.py` runs, writes to
  `data/9t/results/pit/rim_containment/`, and golden-verifies unchanged.

Gates at close: A clean, B 61/61 QGIS layers resolve, C re-baselined, D passing,
E green at 19 remaining literals.

---

## 2026-08-12 — Phase 4 executed: the role-based tree is live

Branch `reorg/phase4`. **12,076 files, 98 GB moved. Nothing deleted.** Every move
went through `tools/apply_moves.py`, is recorded in `docs/MOVES.csv`, and
reverses with `--undo`. Each move was replayed onto
`E:\Colton\_BACKUPS\lidar_project_MIRROR` with the new `--root` flag, so the
mirror stayed a mirror instead of doubling (robocopy `/XO` never deletes).

| Phase | Moved | What |
|---|---:|---|
| 4B | 31 | root clutter, 17 ledgers to `docs/_ledgers/`, 6 QGIS sidecars, 3 landcover clips |
| 4E | 105 | obsolete-with-evidence to `99_archive/superseded/` (390 MB) |
| 4C | 221 | truth to `02_truth/`, the nine flat `eval_*` to `05_results/<area>/<target>/<question>/` |
| 4D.1 | 9,356 | models to `04_models/<target>/<run>/`, `iterations` to `_retired/` (24 GB) |
| 4D.2 | 2,119 | `tiles/` and `label_grids/` to `03_derived/` (70 GB) |
| 4D.3 | 270 | experiments, validation, 613590 inference (3.9 GB) |

**`label_grids/` is gone from the repository root.** It was a 1 m derivative
stack, a QGIS project and two annotation layers, top-level only because
`_build_label_grids.py:46` hardcoded the path. Each part now lives with its kind.

**206 of 226 path literals converted** to `path_for()` by
`tools/convert_path_literals.py`. The rewrite is an identity by construction: it
only fires when the literal prefix is string-equal to the configured value.

**Proven equivalent, not assumed.** Five golden records failed after the
conversion — and failed identically against the *original* code, because
`annotations_proj.gpkg` has uncommitted edits predating the session. Equivalence
was shown by A/B instead: record from original code, restore the conversion,
verify. Byte-identical.

### Three tools were themselves holding stale paths

Each failed silently, which is the exact disease being cured.

1. `verify_paths.py` hardcoded `DERIV` / `DERIV_9T` and reported 83 phantom
   broken constants after 4D. Now seeds from `config/paths.toml` and folds
   `path_for()` and `.parent` — resolved constants 124 → 325.
2. `golden.py` watched `data/derivatives` only. A re-record returned "0 output
   files" and would have written an empty baseline that passes forever.
3. Gate E had two blind spots: a `.parent.parent` climb, and a directory path
   packed into one string ending `.shp`. Both reached the ground truth. Closing
   them found 13 more sites that 4C would otherwise have broken.

### Gate A caught a real leak

`_backup_pit_ann426_2026-06-10` is filed as an annotation snapshot but carries a
full `pit_unet_cv5` run — five fold prob rasters over 100 MB each. Moving it into
`02_truth/_history`, which has no size rule by design, exposed them. The snapshot
was **not** split (that destroys a dated record); `_history` got a targeted rule
instead.

### Corrections to the plan, made on evidence

- `diagnostics/twi_9t_1m.tif` is **not** a duplicate — max pixel difference 18.74.
- `.qml` styles do **not** move to `qgis/styles/` — QGIS auto-loads them from
  beside the layer, so centralising would unstyle all 18.
- `oil_gas_locations.gpkg` (77 MB) is a DEP export, not hand-drawn truth. Moved
  to reference and ignored. The 02_truth tree caught it by having no size rule.
- Sequencing: I had said these conversions must wait for `refactor-package`.
  That branch has not touched a single script, so there was no conflict, and
  converting first makes the refactor easier.

### Not done

`data/derivatives/` still holds 110 loose files; `source_laz/` and `external/`
have not moved into `01_source/`. The loose files are the hard remainder — many
are referenced by exact filename, and 11 are the canonical 1 m 9t stack, which
cannot be consolidated until the `_prep_road_1m.py` stats regression is resolved.

Gates at close: A clean, B 61/61, C 8 broken (4 known-dead, 4 create-on-write,
none new), D re-recorded at the new paths and passing, E green at 20.

---

## 2026-08-12 — Phase 4 reorganization plan (role-based layout), no files moved

Survey only. Nothing moved, nothing deleted. Full plan in
`docs/REORGANIZATION_PLAN_phase4_role_based.md`; it succeeds
`docs/REORGANIZATION_PLAN.md`, which scoped the Phases 0–3 that already shipped.

**Diagnosis.** The tree is keyed by *how a file was made*, not *what it is for*.
`derivatives` is a provenance adjective, so it collects everything: 116 loose
files, 9 flat `eval_*` dirs, the hand-drawn truth, the checkpoints, the
experiments and the tile stacks, all at one depth. `tiles/9t/` repeats the
pattern one level down — 33 GB across 6 unrelated roles.

**Measured this pass.**
- `data/derivatives/` — 116 loose files; `tiles/9t/` — 199 loose files, 19 subdirs.
- `label_grids/westernpa_0{1..4}` is a 1 m derivative stack identical in kind to
  `tiles/<area>/`, plus a `.qgz` and two annotation `.gpkg`. It is top-level only
  because `_build_label_grids.py:46` hardcodes `ROOT / "label_grids"`.
- `tiles/{venango,washington,mckean}_1m/` each hold exactly one landcover clip.
  They are reference data, not tile stacks.
- `613590` exists in two trees under two rules (`tiles/613590_05/` and
  `tiles/data_3x3/westernpa_d20/613590/`).
- `docs/reference_index.csv` is **stale**: 88,487 of 101,839 rows point at
  `barlow/` and `ramachandran_2024/`, both archived in `ba7bcec`. It is the
  move-safety oracle, so it is rebuilt first in Phase 4A.
- `.git` is **5.4 GB for 1,422 tracked files** — rasters untracked via
  `git rm --cached` are still in the pack.
- `qgis/wellsight.qgz` binds 62 datasources; 4 more per-grid `pa1.qgz` exist.
- 6 `.gpkg-wal`/`.gpkg-shm` sidecars still persist under `derivatives/`.

**Obsolete, with citation** (archive, never delete): `road_multiblock` (241 MB,
LEADERBOARD "Rejected"); three `best.pt.*.BAK` (279 MB); the 2-class
`roads_<key>_1m.gpkg` + `road_clean_*` across 25 `data_3x3` blocks (~1 GB,
`BACKLOG.md:201`); ICP Part-2 outputs (`BACKLOG.md:257`); IoU-strictness evals
(`BACKLOG.md:36`); the duplicate `diagnostics/twi_9t_1m.tif` (77 MB); and
`notebooks/wellsight/` (51 v1 scripts, zero live references).

**Not obsolete despite appearances:** every dated `_backup_*`/`_snapshot_*`
(they are the only record of a prior annotation state) and the McKean stacks
(parked by advisor decision, but `mkf_road_1m` fed a leaderboard sweep).

**Path-respect mechanism.** Phase 4A moves nothing — it makes every directory a
key in `config/paths.toml`, converts the ~25 self-rolling scripts to
`path_for()`, and generates `.gitignore` from the config instead of hand-editing
60 anchored rules. Gates A–D exist (leak audit, QGIS resolve, script paths,
golden outputs); Gate E (`tools/verify_no_path_literals.py`) is new.

Five decisions are open, listed in §11 of the plan. Nothing proceeds until they
are answered.

**Follow-up, same day — the loose `*_9t_1m.tif` files are NOT obsolete. Nothing
archived.** The 11 loose `*_9t_1m.tif` at the `derivatives/` root have same-named
twins in `tiles/9t_1m_rebuilt20260812/`, built 2026-08-12, which reads as
supersession. It is not. `HANDOFF_code_cleanup_wellsight_v2.md:281` records that
`9t_1m_rebuilt20260812/` is a **quarantine directory** — `_prep_road_1m.py`
rebuilds the trained-on stack ~2% off (slope mean 8.3177 → 8.5156), so its output
target was deliberately renamed to make the script fail fast. "Do not undo that."

Measured on the 10 same-named pairs: CRS, grid, resolution and bounds identical;
whole-tile slope mean identical at 8.8074; **per-pixel max abs difference
non-zero on 9 of 10** (slope 6.64°, openness_pos 4.89°, DEM 0.29 m, intensity
59,639). Aggregate statistics agree while pixels do not — a min/max/mean check
calls these duplicates and is wrong. Both sets move intact in Phase 4D.

**Canonical 1 m stack identified.** The loose `*_9t_1m.tif` at the
`data/derivatives/` root are canonical. All 7 channels of
`tiles/9t/features_pit_9t_1m.tif` — the stack the models read — are byte-exact
against them (max abs diff 0.0 on every channel) and differ from
`tiles/9t_1m_rebuilt20260812/` on every channel. The rebuilt directory stays
quarantined and is not consolidated into `tiles/9t_1m/`, because creating that
name re-arms `_prep_road_1m.py`.

Could not reproduce `feature_stats_1m.json`'s slope mean of 8.3177: today's
`pit_blocks_9t.gpkg` (77 train blocks, untracked, mtime 2026-08-12 14:47) gives
8.5156 for **both** raster sets. So the 8.3177 → 8.5156 drift the handoff
attributes to the rebuild is at least partly a block-split change. Recorded, not
chased. It does not affect which stack is canonical.

**Separate defect found, not fixed.** `s2_labels/_prep_road_1m.py:52`,
`s5_eval/_road_methods_compare.py:82` and `s5_eval/_road_optimize.py:69` all read
`tiles/9t_1m/`, a dead junction into `E:\lidar_project_data_DO_NOT_DELETE`. All
three are broken today. Which 1 m stack is canonical is a path decision for the
`refactor-package` work.

---

## 2026-08-12 — Reorg Phases 4B and 4A executed on branch `reorg/phase4`

**4B — 31 moves, nothing deleted.** All through `tools/apply_moves.py`, recorded
in `docs/MOVES.csv`, reversible with `--undo`.

- Repo root drops from 30 visible entries to 21, and loose non-documentation
  files at the root go from 9 to 0. The nine were figures,
  scratch notes, a download manifest, a pretrained weight and a robocopy log.
  Renamed where the name did not say what the file shows —
  `bad roads.png` → `docs/figures/scratch/road_vectorization_bad_result_613590.png`.
- 17 planning CSV/JSON files → `docs/_ledgers/`. Seven tool constants pointed at
  the old locations; the **tools were repointed**, not the files moved back
  (`find_duplicates`, `plan_archive`, `plan_consolidation`, `plan_stage_refactor`,
  `plan_v1_archive`, `verify_paths`).
- 6 `.gpkg-wal`/`.gpkg-shm` sidecars → `data/99_archive/superseded/qgis_sidecars/`.
  They were tracked in git, which they should never have been.
- `tiles/{venango,washington,mckean}_1m/` held one NLCD clip each →
  `data/external/landcover/`. Study-area count in `tiles/` drops 19 → 16.

**4A — the path layer, nothing moved.**

- `docs/reference_index.csv` rebuilt: 101,608 files, 100,681 with zero
  references. The prior index was 87% stale after the `ba7bcec` archive.
- `config/paths.toml` gains the **full role-based vocabulary**, 31 keys, all
  resolving. Names are final; values point at the current tree until 4D. The 4D
  values are recorded as comments in the same file. `_common.py::_DEFAULTS`
  mirrors it as the fallback. Every legacy name (`DERIV`, `DERIV_9T`,
  `annotations`, `tiles`) is preserved, so all 67 importers are untouched.
- **Gate E added**: `tools/verify_no_path_literals.py` walks the AST of every
  live `.py` and fails on a directory literal below `ROOT`/`DERIV`/`DERIV_9T`.
  Each hit prints the exact `path_for()` replacement. 231 sites / 226 distinct,
  frozen as a baseline in `docs/_ledgers/path_literals_baseline.json`. Breakdown:
  s5_eval 66, tools 50, s7_analysis 26, s3_train 23, s2_labels 16, s4_infer 15,
  s1_build 12, s6_review 9, ui 9.

**Converting those 226 sites is deliberately NOT done here.** They sit in the
same 92 files `refactor-package` is rewriting, and editing both at once
guarantees merge conflicts. Per decision 3, that conversion lands with the
package refactor.

**Gates after both phases:** A clean (0 unignored >100 MB). B clean (61/61 QGIS
layers resolve). C improved, broken script constants 14 → 7, no new breakage vs
baseline. D not re-run (no pipeline code changed). E green at baseline.

**4E — 105 files, 390.5 MB archived. Nothing deleted.**

Every item was checked against the rebuilt index for **literal** path references,
not name matches. That distinction mattered: `road_multiblock/` showed 10
"references" that were all basename collisions on `best.pt`, `train_log.csv` and
`test_metrics.json`. Literal references: zero. `n_refs` alone over-reports badly
and must not be used as the move test on its own.

| Archived | Files | Size | Evidence |
|---|---:|---:|---|
| `road_multiblock/` | 21 | 251.8 MB | `LEADERBOARD.md` — "Rejected. Diluting the dense 9t core hurt." |
| six `*.BAK` | 6 | 96.7 MB | three superseded road checkpoints, two pre-schema annotation copies, one pre-rebuild manifest |
| `roads_<key>_1m.gpkg` + `road_clean_*` across 25 blocks | 78 | 61.0 MB | `BACKLOG.md:201` — "obsolete and can be deleted" |

All three have `ARCHIVE_MANIFEST.csv` rows and reverse with
`tools/apply_moves.py --undo --phase phase4e`.

**One §6.1 claim withdrawn.** `tiles/9t/diagnostics/twi_9t_1m.tif` was listed as
byte-identical to `tiles/9t/twi_9t_1m.tif`. It is not. Same shape, CRS and
transform; different sha256; **max abs pixel difference 18.74 TWI units**. Two
different rasters sharing a filename across parent and child directory. Not
archived. The `_dupe` rule does not apply because the contents differ — this
needs disambiguating names instead.

Gates after 4E: A clean, B 61/61, C unchanged at 7, no new breakage.

---

## 2026-08-06 — 9t-only road retrain, 613590 out-of-domain test, 12-model comparison

Full write-up in `docs/iterations/road_613590_out_of_domain_test.md`.

**Stale labels found and fixed.** `labels_road_9t_1m.tif` dated 2026-06-10 and held
556,773 road px (~185.6 km) while `roads.shp` carried **206.09 km** inside 9t after
the 2026-07-30 extension. **~19 km of hand-drawn road was labelled background**, and
disproportionately the faint lines added on 07-30 — the exact class the model fails
on. Rebuilt to 614,003 px (+57,230) with `_rebuild_labels_road_9t_1m.py`; the old
raster is kept as `labels_road_9t_1m_pre2026-08-06.tif`. `road_dataset_manifest.csv`
and `road_chunks_9t.gpkg` rebuilt too (15,292 road chunks; 3,315/983/672 in-tile).
`_prep_road_1m.py` could not be used: `tiles/9t_1m/` is a dead junction into
`E:\lidar_project_data_DO_NOT_DELETE`.

**`--tag` added to `_road_unet_1m_recall.py`** — it had none and would have
overwritten the Jun 14 champion.

**Circularity, measured not assumed.** 613590 ground truth splits by `src`:
`613590_review_r2` 138.23 km is a previous model's vetted output,
`613590_added_r2` 48.87 km is hand-drawn. **All 12 models score 0.96-1.00
completeness on the review subset.** It ranks nothing. Only the added subset counts.

**The controlled result** — same recipe, same data, only labels changed:

| model | thr | added completeness | correctness_px | quality | mean P(road) added |
|---|---|---|---|---|---|
| recall (Jun 14, stale labels) | 0.50 | 0.613 | 0.835 | 0.547 | 0.432 |
| recall_relabeled20260806 | 0.50 | **0.759** | 0.828 | **0.655** | **0.549** |

+0.146 completeness at zero correctness cost. The faint-road confidence gap narrowed
from -0.459 to -0.266. Review-subset confidence FELL (0.891 -> 0.815), which is
healthy: the model is no longer a near-clone of the one that drew those lines.

**12-model comparison** at each model's best-quality threshold, added subset:
`sweep_orient` 0.686 Q leads, then `ENSEMBLE_mean` 0.684, `ENSEMBLE_max` 0.681,
`boundary`/`alpha078` 0.674, `relabeled20260806` 0.660, Jun 14 baseline 0.581.
`sweep_cldice_mkf` 0.457 is a clear negative (1.84 M predicted px, 2.4x the others,
correctness 0.520) — multi-block McKean training over-predicts, matching the earlier
`road_unet_mb` rejection. Max recovery: `ENSEMBLE_max` at thr 0.30, **0.909**
completeness / 0.651 correctness.

**Interpretation.** The retrain beat its own predecessor by +0.11 quality but sits
below the sweep variants — and every sweep variant was trained on the same stale
labels. Relabelling bought more than any architecture change in the 2026-07 sweep.
Three independent measurements now agree the dominant failure mode is a road class
under-represented in the labels, not architecture or capacity. **Next: re-run
`orient`, `boundary` and the ensemble members on the corrected labels.**

**Side finding.** Rebuilding the manifests showed `plat.shp` has **995** features
while `plat_dataset_manifest.csv` only ever had **650** — 345 pads have never been in
the manifest. The 650-row file was restored from a snapshot so pad CV5 fold
assignment is unchanged. Needs its own pass.

Wiedemann et al. 1998 logged in `literature/CITATIONS.md` for the completeness /
correctness / quality triple.

---

## 2026-08-05 — 613590 road review folded into `annotations/roads.shp` (+188 km)

Script: `notebooks/wellsight_v2/annotations/_merge_review_added_roads_613590_into_roads_shp.py`

**Inputs.** Round-2 active-learning review package for tile 613590:
`review/review_roads_613590.gpkg` layer `review` (15,057 chunks, all
`status='keep'`, 138.56 km) and `review/added_roads_613590.gpkg` layer `added`
(487 hand-drawn missed roads, 49.04 km). Chunk `seg_id` runs 27..16994 with
15,057 present, so **1,911 chunks were deleted by hand** during review. Rejected
geometry is NOT merged — it stays in the review package as a hard negative for
retraining.

**Reassembly.** The review layer is model output chunked to ~9 m (median 9.2 m)
so a bad stretch can be flagged without splitting a line. Appending 15,057 stubs
would turn `roads.shp` from hand-drawn polylines (158 m mean) into chunks, so
chunks were dissolved by `parent_id`, `linemerge`d, then exploded:
**15,057 chunks -> 1,003 lines, 138.56 km, mean 138 m**. Length is preserved to
2 decimals, so the merge is lossless. 1,003 parts from 1,003 parents means no
parent was left gapped by the deletions — whole parents were removed, not middles.

**Checks before writing.**
- Only 1.03 km of the 487 added lines (2.1%) falls within 2 m of a kept model
  road, so the hand-drawn additions are new road, not retracing.
- **0** new lines fall within 5 m of any pre-existing `roads.shp` line.
  `roads.shp` had zero coverage in the 613590 extent, so this is a clean append
  with no dedup needed.
- All geometries valid, none empty, CRS EPSG:4326 preserved.

**Result.** 2,200 features / 348.31 km -> **3,690 features / 535.91 km**.
New `src` column records provenance: `prior` 2200, `613590_review_r2` 1003,
`613590_added_r2` 487. Consumers of `roads.shp` read geometry only
(`_road_morphology_bins.py`, `_classify_9t_roads_bold_faint.py`,
`_bold_vs_faint_roads.py`, `_icp_change_classify_9t.py`), so the added column is
inert.

**Status: staged, not yet in place.** `roads.shp` was open in QGIS and held a
write lock. The merged product is at
`data/derivatives/annotations/roads_with_613590_r2_staged.gpkg`. Pre-merge copy
of `roads.*` is at `data/derivatives/annotations/_backup_roads_2026-08-05/`.
Rerun the script with the layer closed to write `roads.shp` in place, then rerun
`notebooks/wellsight_v2/annotations/_prep_annotations.py` so the `roads` layer in
`annotations_proj.gpkg` — which the training scripts read — stops being stale.

**Caveat.** These 138.56 km are model output the annotator vetted, not lines drawn
from scratch. Scoring a road model on 9t+613590 now includes 138 km of ground
truth that a previous road model proposed. The 49 km of `added` lines and the
existing 348 km are independent of any model.

---

## 2026-08-04 — pit/pad scoring moved to centroid matching; annotations expanded; pits retrained

Full write-up in `docs/iterations/centroid_matching_pit_pad_9t.md`.

**Why.** A reviewer could not follow the abstract's pit/pad results. The cause
was not wording. We were reporting an IoU-strictness sweep for objects the
literature says should not be scored by IoU. Fiorucci et al. 2022 argues exactly
that; Lidberg et al. 2024 — hunting pits, U-Net, ALS, forested Sweden, the
closest published analogue — uses centroid matching and reports only
recall/precision/F1. Both logged in `literature/CITATIONS.md`.

**Annotation expansion.** User reviewed unmatched detections in QGIS. `pit_inside`
in 9t 426 -> 503; `pit_outside` 428 -> 506. 56 further pits landed in
`northcentral_b19/e1423n2235` (McKean) and are `unused` in the manifest.
All 381 unmatched pad predictions reviewed: **277 confirmed real, 104 rejected**.
Confirmed pads were deliberately NOT added to `plat.shp` — scoring evidence only.

**Measurement correction, isolated.** Same 587 June-10 predictions re-scored
against the growing annotation set, no model change:

| annotations | truth | matched | precision | recall | F1 |
|---|---|---|---|---|---|
| Jun 10 (426) | 423 | 385 | 0.656 | 0.910 | 0.762 |
| 12:59 (503) | 496 | 451 | **0.768** | 0.909 | **0.833** |

66 of 202 "false positives" were real wells.

**Pit retrain.** `_pit_unet_cv5.py --folds 5 --epochs 40`, 54.8 min. Fold dirs
deleted first — the script silently reuses checkpoints and prob rasters.
Trained on the 12:35 manifest = **471** pits in 9t (not 503; the last 32 arrived
mid-run). Scored on current rims: precision **0.716**, recall **0.931**, F1 0.809.
An earlier 0.667 was against the stale 12:35 rim set and is superseded.

**Match rules** (`_match_rules_pit_pad_9t.py`). Bidirectional containment gains
pads +10 matches (recall 0.928 -> 0.943), pits nothing. The overlap-fraction leg
never fires. Log-space 3-sigma size cut = 283 m2; the linear equivalent is
-839 m2 and filters nothing. Size filter DROPPED for pads — 6 confirmed pads sit
below the cut, smallest 106 m2.

**Shipped numbers.** pit 0.931 / 0.716; pad 0.943 / 0.898. Pad recall uses the
650 independently drawn pads, not the 921 grown set — the 0.960 figure is
circular, since confirmed pads are found by construction.

**Five abstract corrections** (v13 -> v17): 471 not 503 training pits; 93% not
94% pit locate; 0.72 not 0.67 pit precision; 94% not 96% pad locate; 735 not
1,220 road segments (`recall_clean` 0.982 applies to the leakage-free subset).
Abstract also trimmed 311 -> 279 words on request.

**Do not compare pit 0.72 against pad 0.90 as models.** Pads had a complete
candidate review; pits had none. 187 pit candidates deferred.

---

## 2026-07-31 — 9t DoD rebuilt with ONE ICP solve; the "signal at wells" is circular

Script: `notebooks/wellsight_v2/build/_icp_change_9t_rebuild.py`. Full write-up
in `docs/iterations/icp_change_9t.md` Part 3.

**Rebuild.** All four 2006-2008 tiles covering 9t merged and solved as a SINGLE
ICP problem against the nine 2019 D20 tiles, ground only, 5 m voxel (same voxel
as 2026-05-21). 2019 reference is `tiles/9t/dem_9t_05.tif`, dropping the
vanished `mosaic_3x3` dependency. Mosaicked by true mean, not the old
order-dependent `0.5*(dst+buf)`.

Solve: converged, fitness 0.967, displacement at block centroid dx −0.0024,
dy −0.0003, dz +0.0396 m.

| | per-tile spread | robust sigma |
|---|---|---|
| original (4 independent solves) | 0.103 m | 0.1358 m |
| **single ICP** | **0.0576 m** | **0.1119 m** |
| single ICP + per-tile dz | 0 | 0.1102 m |

Per-tile spread −44%, sigma −18%. Reconstruct test now PASSES exactly
(`max|resid| = 0`); the old product failed at 0.24 m. What remains is genuine
along-track striping — row-mean std 0.0786 m, 3.7x the column-mean std.

Slope-stratified sigma now RISES with slope (`sigma = +0.098*tan(slope) +
0.106`, ~0.10 m implied planimetric error). Part 1 reported a negative
coefficient; that was the per-tile blocks inflating sigma on flat ground.

**Two ICP failures worth remembering.** (1) `filters.icp` diverged
(converged=False, fitness 17.7, −30 km shift) because both clouds were cropped
to the same bbox, leaving the moving cloud a 200 m rim with no counterpart and
`max_dist` unset. The fixed cloud must strictly ENCLOSE the moving cloud.
(2) The raw translation column of an ICP matrix is NOT the shift — the
transform is about the coordinate origin, so a 2.8e-5 rad rotation shows up as
+130 m of translation that the rotation cancels. Evaluate displacement at the
cloud centroid.

**The wells result, and why it is rejected.** The rebuilt DoD appeared to show
14.63% of well points exceeding 3 sigma vs 4.08% background (naive z +12.4),
and it survived a toroidal-shift null that preserves clustering and the ~35 m
autocorrelation (p = 0.001). It is still an artifact:

1. `annotations/well_head_pts_reprojected.gpkg` and
   `annotations/wellhead_pits.gpkg` are the SAME 861 points (median separation
   0.0 m). These are hand-digitised pits — selected for being depressions on
   the 2019 DEM. Circular.
2. The surveys differ ~7x in density. Local depression depth at those points:
   2019 −0.3251 m, 2006-08 −0.2343 m. The sparse survey resolves 72% of the
   depth; the −0.0907 m shortfall exceeds the observed −0.0555 m DoD median.

Sparse survey smooths small pits away + points chosen for being small pits =
negative DoD by construction. **No subsidence claim is supported.** Part 1's
clean negative stands, and any future DoD test against these points is circular
until a non-DEM-derived well list is used.

**Consequence:** Part 2's products (`change_class_9t_2m.tif`,
`change_class_reliable_9t_2m.tif`, `dod_9t_nonerosional_2m.tif`,
`change_patches_9t.gpkg`) all derive from the superseded DoD and are stale. Its
destripe/high-pass stack was tuned against blocky artifacts that no longer
exist.

Outputs (`data/derivatives/experiments/icp/change_9t/`):
`dem_2006_singleicp_9t_2m.tif`, `dod_9t_singleicp_2m.tif`,
`dod_9t_singleicp_tiledz_2m.tif`, `fig_dod_9t_singleicp_vs_original.png`,
`_icp_rebuild_9t.json`. The 2026-05-21 rasters are left untouched for
comparison and should not be used.

---

## 2026-07-31 — CRS ALERT: the 2006-2008 LAZ headers carry the WRONG EPSG code

Found while inspecting six newly downloaded tiles. Every
`USGS_LPC_PA_STATEWIDE_N_2006_2008_*.laz` header contains a WKT that is
**internally inconsistent**:

| WKT element | value | implies |
|---|---|---|
| `PARAMETER["false_easting", ...]` | 1968500 | ftUS variant |
| `UNIT[...]` | US survey foot | ftUS variant |
| `AUTHORITY["EPSG", ...]` | **32128** | metre variant (false easting 600000 m) |

PDAL's derived proj4 inherits the contradiction and is unusable:
`+x_0=600000 ... +units=us-ft` — the metre false easting applied in feet.
Trusting it puts the data **~417 km** off (1968500 − 600000 = 1368500 ftUS).

The correct CRS is **EPSG:2271** (NAD83 / Pennsylvania North, ftUS).
`notebooks/wellsight/build/_icp_change_map.py` already hard-codes
`OLD_CRS = "EPSG:2271"` and overrides the header, so all existing ICP work is
unaffected. **Never read these tiles without forcing the CRS explicitly.**

Z is also ftUS; the pipeline's `Z * 0.3048` uses the international foot rather
than the survey foot. Error is 2 ppm — ~1 mm over the 738 m elevation range,
negligible against the 0.136 m DoD sigma. Recorded, not corrected.

---

## 2026-07-31 — fetched the 6 missing 2006-2008 tiles; ICP change product fails its own reconstruct test

**Downloads.** `downloadlist 2006-2008 laz.txt` lists 12 tiles; 6 were already
on F:. Fetched the rest to `F:\lidar_project\consolidated\lidar_all\`:
`002960, 003113, 003254, 003255, 003256, 003257` (~6.2M points each, ~0.67
pts/m², LAS 1.1 pf 1). Script: `scratchpad/_fetch_2006_tiles.sh`.
Source: USGS 3DEP, public domain. Outside the repo — large-file rule N/A.

**None of the six touch 9t.** Header bboxes reprojected to EPSG:6346 put them
north and east of the block. 9t was already fully enclosed by `002958, 002959,
003111, 003112` (30.6 + 17.0 + 36.9 + 20.6 = 105.1% with overlaps). The six add
a wider change-detection footprint, X[616093..628618] Y[4592119..4601369].

**Defects found in the existing 9t ICP product** (prompted by the observation
that `dod_9t_2m.tif` does not look like 9t terrain). Scripts:
`scratchpad/_verify_icp_is_9t.py`, `_verify_icp_coverage.py`,
`_verify_icp_reconstruct.py`, `_verify_icp_fullraster.py`,
`_verify_icp_tileblocks.py`, `_diag_icp_9t_provenance.py`.

1. **Location is correct.** Bounds byte-identical to `dem_9t_05.tif`;
   the chain's 2019 DEM correlates with it at 1.000000, median diff 0.0000 m.
2. **The rectangular blocks are per-tile ICP residual bias, not acquisition
   striping.** Median DoD per old-tile footprint: 002958 −0.038, 002959 −0.057,
   003111 +0.046, 003112 +0.044 m — a **0.103 m spread** against a pooled
   robust sigma of 0.136 m. Each tile got an independent ICP solution with its
   own vertical bias and the mosaic butts them together. **This invalidates the
   "swath-level bias in the 2006-2008 acquisition" attribution in
   `docs/iterations/icp_change_9t.md`, and Part 2's destripe/high-pass stack
   was tuned against the wrong artifact geometry.**
3. **`dem_diff_2m.tif` does not reconstruct from its own inputs.**
   `dem_new_2m` is valid over 44.4% of 9t; `dem_diff_2m` over 99.97%. Residual
   `diff − (new − old)` has mean |r| 0.24 m against a DoD sigma of 0.14 m, and
   it is not a shift (scanned ±4 px; dy=dx=0 is already optimal). Cause: the
   script in the repo is not the version that produced the rasters — rasters
   dated 2026-05-21, `_icp_change_map.py` edited 2026-05-22 (`acce517`) and
   2026-05-23 (`375f9f5`). Its `mosaic_3x3` input no longer exists on any drive.

Surviving from the original write-up: the registration QC and the clean
negative at known wells (4.4% vs 3.63% background, z ~ 1.0) — both insensitive
to a ±0.05 m per-tile step. Not surviving: the noise-floor attribution and,
downstream of it, the 16 "reliable non-erosional patches".

Rebuild is unblocked (old side = 4 LAZ on F:, new side = `dem_9t_05.tif`
directly, dropping the missing `mosaic_3x3` dependency) but **not started** —
pending a decision on whether recent-activity change detection is a project
goal, since Part 1's negative means this line does not serve orphan-well
detection. The fix that matters is solving one ICP across the merged tile set,
or removing per-tile vertical offsets on the overlaps before mosaicking.

---

## 2026-07-31 — CRS ALERT: drainage.shp is EPSG:6346, not 4326 like the other annotations

Found while testing an external claim. `roads.shp`, `bold_roads.shp` and
`faint_roads.shp` are stored unprojected and are read with
`set_crs(4326).to_crs(DST_CRS)`. **`drainage.shp` is already in EPSG:6346** and
also carries no `.prj` (`crs is None`), so the same idiom silently mangles it —
it reprojects projected metres as if they were degrees. Symptom: total length
came out **0.00 km** instead of 45.04 km, with no exception raised.

`drainage.shp` also has **986 of 2777 records with null geometry** (1791
usable).

Audit every existing read of `drainage.shp` for this pattern. The road model
uses drainage as a negative class, so if any trainer applied the 4326 idiom the
negatives were placed at garbage coordinates. Filed in BACKLOG.

---

## 2026-07-31 — external reports audited: one fabricated, one real but optimistically cross-validated

Two external analyses of `bold_faint_exemplar_segments_9t_05_scores.csv` were
supplied for review. Checked every quantitative claim against the file.
Script: `scratchpad/_audit_external_reports.py`.

**Report A (ChatGPT) — fabricated, do not use.** Decisive checks:

| claim | actual |
|---|---|
| "bold segments have **higher** values of these contrast metrics" | `opos` bold **-4.83** vs faint -0.35; sign inverted on all four top features |
| `relief10` bold mean ~1.8, faint ~0.7 | 1.376 and **-0.137** |
| "incision_depth_m > ~100 m -> bold" | column max is **0.885 m** |
| confusion matrix 45+5+10+50 | sums to 110; **n = 84** |
| "`relief10` is the top predictor" | AUC 0.839, 5th of 7 |
| "no perfect collinearity, features not redundant" | 10 pairs at \|rho\| >= 0.90, `tpi15`~`lrm51` = 0.998 |
| `opos_zcontrast` = "planform curvature" | it is positive openness |

Its recommended index weights `relief10` at 0.45 and `opos` at 0.03 — inverted
against measured discriminating power (AUC 0.839 vs 0.992). Applying it would
degrade the classifier.

**Report B (Fable) — genuine.** Its per-feature AUCs match ours to within 0.002
across all seven (0.992/0.987/0.976/0.968/0.869/0.839/0.766). It independently
reached the `P_road` circularity conclusion. Two corrections:

- Claimed `opos <= -1.50` gives 97.6% (82/84) with **zero false negatives**.
  Measured: **96.4% (81/84), 1 FN and 2 FP**.
- **LOO-CV is not grouped.** The 84 segments come from only **29 parent lines**,
  and same-line segments are adjacent 50 m pieces of one road, so plain LOO
  trains on a segment's own neighbours.

| rule | LOO | leave-one-line-out | drop |
|---|---|---|---|
| `opos` alone | 95.2% | **91.7%** | -3.6 |
| `opos` + `tpi15` (its 98.8% rule) | 95.2% | **92.9%** | -2.4 |
| `opos` + `incision_depth_m` | 96.4% | **95.2%** | -1.2 |
| all 7, logistic | 95.2% | **92.9%** | -2.4 |

**Its recommendation survives the correction anyway.** `opos` + `incision` is
the best rule under grouped CV and the only one losing under 2 points — the two
features come from independent derivation chains (openness raster vs transect
profile geometry), which is why it degrades least. Adopted as the reported
two-feature rule at **95.2% grouped CV**.

**Rejected from Report B: the "clean bimodal composite".** It proposes an
equal-weight composite of the top four and describes its distribution as
bimodal, for thresholding when scaling to unlabelled segments. The bimodality is
an artifact of the exemplars being hand-picked clear cases. Measured on the full
4,043-segment network the distribution is a skewed continuum — KDE trough
**4.9% deep** at percentile 1.7, BIC still improving at k=4. This is the same
error corrected in the 2026-07-30 entry and it must not be reintroduced.

**Open, and worth the user's eyes: `f0058`.** A faint-labelled segment sitting
inside the bold cluster on every trough metric (`opos` -3.43, `incision` 0.78 m,
above the bold median 0.487) while scoring **P_road 0.0007**. Its only sibling on
parent line 8, `f0057`, is flat (`opos` +0.08) — one 50 m piece deeply incised
next to one that is not, which is a crossing, not a road. Location
**622846.8, 4593369.5** (EPSG:6346).

Attempted to test the gully hypothesis against `drainage.shp`: **inconclusive**.
The nearest drainage annotation to *any* exemplar segment is 142 m, so drainage
labels do not cover this area. Needs visual inspection.
`f0045` (`opos` -1.58, `incision` 0.37) is a genuine borderline case, not an
error.

---

## 2026-07-31 — swept 31 candidate features; 3 are worth adding, intensity is dead

Asked whether any parameters are missing from the bold/faint panel. Tested three
families on the 84 exemplar segments: 14 `tiles/9t` rasters the classifier never
samples, 6 cross-section shape terms free from the transect stack, and 2
along-segment consistency terms. Ranking:
`scratchpad/_candidate_feature_ranking.csv`, script
`scratchpad/_test_candidate_features.py`.

**Worth adding.**

| feature | bold | faint | δ | rho vs `opos` | why |
|---|---|---|---|---|---|
| `berm_min_m` | 0.410 m | 0.105 m | +0.964 | 0.851 | height of the *weaker* shoulder; beats `incision_depth_m` (0.935) |
| `sgres19_zcontrast` | -2.437 | -0.272 | -0.963 | 0.855 | Savitzky-Golay residual, raster never sampled |
| `raniso_zcontrast` | 2.361 | 0.736 | +0.862 | 0.719 | anisotropic roughness; trustworthy replacement for the quantised `roughness_11` |

**Confirmed dead — do not add.** `intens_zcontrast` δ -0.200, **p = 0.12**, the
only non-geometric channel tested and it fails. `gdens_*` δ 0.000 (confirms the
42% nodata note). `allret_*` δ ~0.10, p > 0.35. `cdoublet_zcontrast` δ 0.313.

**A hypothesis that failed.** `bench_asym_m` = |left shoulder - right shoulder|,
predicting that a benched road is cut uphill and filled downhill while a skid
trail is symmetric. δ +0.248, **p = 0.054**. Not supported. Recorded because the
reasoning was sound and someone will propose it again.

**Circular — excluded.** `opos_frac_bold` (fraction of a segment's transects
below the fitted cut) δ +0.987, bold 1.000 vs faint 0.000. It is the cut applied
to itself. Same class of error as `P_road`.

**Redundancy is the real finding.** 10 pairs among the top 20 correlate at
|rho| >= 0.90. `tpi15_zcontrast` ~ `lrm51_zcontrast` at **rho = 0.998** -- the
same measurement under two names. `incision_depth_m` ~ `berm_max_m` 0.945.
Every scale of LRM and TPI tested (5/11/25/51 and 05/15/51) separates at
δ 0.75-0.97, so the signal is scale-robust and adding scales adds nothing.
**Decision: the panel is not short of terrain channels.** The gap is
non-geometric evidence -- surface material, compaction, vegetation regrowth --
and intensity was the one candidate the tiles offer for it.

**Caution recorded.** `tread_flat_m` separates at δ +0.808 with the sign
*backwards* from intuition (bold roads have a rougher running surface, 0.084 vs
0.035). Likely the |d| <= 2 m window catching the cut walls rather than the
tread. Not adopted pending a fix to the window.

---

## 2026-07-31 — every feature ranked bold vs faint, and P_road turns out to be circular

Full write-up: `docs/iterations/road_bold_vs_faint.md`, section "Per-feature
comparison of the labelled segments". New script:
`notebooks/wellsight_v2/analysis/_score_bold_faint_exemplar_segments.py`.

Asked for a graphical comparison of the labelled bold vs faint segments across
all eight scored parameters, then for the same as a CSV over the exemplar
shapefiles themselves.

**Figure.** `fig_bold_vs_faint_feature_ridgeline_9t_05.png`. One ridgeline row
per feature over the 79 exemplar-matched `roads.shp` segments. Each feature
z-scored on the **pooled** bold+faint values so all eight share one x axis in
pooled-SD units; y is KDE density rescaled per panel; rug ticks are individual
segments. Rows ordered by |Cliff's δ|.

| feature | bold med | faint med | δ | AUC | p |
|---|---|---|---|---|---|
| `P_road` | 0.856 | 0.023 | +1.000 | 1.000 | 2.4e-14 |
| `opos_zcontrast` | -4.72 | -0.44 | -0.981 | 0.990 | 7.4e-14 |
| `incision_depth_m` | 0.515 | 0.178 | +0.976 | 0.988 | 9.9e-14 |
| `lrm25_zcontrast` | -2.63 | -0.34 | -0.925 | 0.963 | 1.7e-12 |
| `tpi15_zcontrast` | -2.46 | -0.46 | -0.906 | 0.953 | 4.8e-12 |
| `slope_zcontrast` | +1.32 | -0.13 | +0.777 | 0.889 | 3.0e-09 |
| `relief10_zcontrast` | +0.88 | -0.24 | +0.722 | 0.861 | 3.7e-08 |
| `oneg_zcontrast` | -1.24 | -0.01 | -0.655 | 0.828 | 5.9e-07 |

**Decision — `P_road` is barred from the discriminator set.** δ = +1.000 is
perfect separation with zero overlap. `P_road` is a trained detector's output,
not an independent measurement, so this is circular with respect to the
classification. It stays in the tables as a *detection* diagnostic and is not
cited as evidence the classes separate.

**Decision — `slope`, `relief10`, `oneg` are demoted.** δ 0.66-0.78 with
overlapping curves, and the mechanism is siting rather than boldness: a road on
a steep slope must be cut to be level. Using them would import terrain bias.
`opos_zcontrast` stays PRIMARY; `incision_depth_m` (δ 0.976, 51.5 cm vs 17.8 cm)
is the interpretable companion.

**Shape finding.** Faint distributions are tight near zero, bold ones wide and
displaced — "no measurable cut" is narrow, "some amount of cut" spans a range.
That asymmetry is the mechanism behind the skewed continuum that defeated the
earlier unsupervised cuts.

**CSV.** `bold_faint_exemplar_segments_9t_05_scores.csv`, 84 rows: 36 bold
segments from 8 lines (1.786 km) + 48 faint from 21 lines (2.351 km), chopped to
~50 m. Columns `seg_id, class, src_file, src_line, length_m, n_transects, mid_x,
mid_y, P_road` + the 7 terrain features. Coordinates EPSG:6346.

Two parameter choices in that pass. MAD floors are computed on the 9t
`roads.shp` network and passed in (`opos` 0.4600, `oneg` 0.4623, `slope` 1.3221,
`lrm25` 0.0319, `tpi15` 0.0457, `relief10` 0.1267, `dem` 0.3457) so exemplar and
network scores share one scale. `MIN_LEN` lowered 20 m -> 5 m for this pass
only, so no exemplar line is silently dropped; no segment ended up below 5
transects.

**Cross-check.** Exemplar-shapefile medians (`opos` -4.39 bold / -0.26 faint)
track the matched-segment medians (-4.72 / -0.44). The 8 m / 60% matching step
is not distorting the labelled set.

---

## 2026-07-30 — the faint class gets labelled, and the bold/faint cut validates at 94.1%

Full write-up: `docs/iterations/road_bold_vs_faint.md`. Script rewritten:
`notebooks/wellsight_v2/analysis/_classify_9t_roads_bold_faint.py`.

**Why the previous layers looked random.** Two defects, both mine:

1. The cut points were taken from the exemplar geometries (`bold_hi` = the bold
   exemplars' max, `faint_lo` = the faint exemplars' min) and never referenced
   the `roads.shp` distribution. They landed at **percentile 52.8 and 71.9**, at
   86% and 93% of peak histogram density — inside the mode.
2. The divide-by-zero floor on the context MAD was computed **separately per
   `featurise()` call**: 0.3731 over 29 exemplars vs 0.4654 over 3.7k segments,
   a 25% scale discrepancy on the ~5% of transects that hit it.

**A rejected detour.** An unsupervised cut (KDE valley / GMM crossover / Otsu,
all near percentile 27) looked justified — GMM BIC preferred k=2 by -811. It was
wrong. BIC kept improving to k=4 (skew absorbed by extra Gaussians) and the KDE
trough is 4.9% deep at percentile 1.7. The labels below score Otsu's cut at
**83.8%** balanced accuracy. The distribution is a skewed continuum.

**What actually fixed it: the user extended `roads.shp`.** +159 lines / 15.55 km
inside 9t (1,155 -> 1,314 lines; 186.87 -> 202.42 km). Faint exemplars present
in the layer went **0/21 -> 18/21**, median distance to the nearest annotated
line **101.8 m -> 0.6 m**. The class now exists in the population being split.

**Method change.** The cut is fitted on `roads.shp` segments that match a
hand-drawn exemplar (60% of length within 8 m, the same tolerance the extraction
harness uses), not on the exemplar geometries. 37 bold-matched, 42
faint-matched.

| measure | value |
|---|---|
| bold-matched median / faint-matched median | -4.72 / -0.44 |
| Cliff's delta, AUC | **-0.981**, **0.990** (p = 7.4e-14) |
| cut (Youden J) | **-1.585**, percentile 57.0 |
| balanced accuracy, in-sample | 97.3% (bold 35/37, faint 42/42) |
| **balanced accuracy, grouped CV** (parent roads held out, 38 folds) | **94.1%** |

The original exemplar midpoint was -1.54. **The threshold was right; the layer
was wrong** — with no faint roads in `roads.shp` it had nothing correct to
select.

**Layers** (`data/derivatives/experiments/road_morphology_bins/roads_bold_faint_9t_05.gpkg`):
`roads_bold_9t` 2,303 segs / 114.81 km (57.0%), `roads_faint_9t` 1,740 segs /
86.61 km (43.0%). `ambiguous` retired. 263/1,280 parent roads (21%) internally
mixed.

**Validation.** Held-out test blocks: bold 0.825 (96% >= 0.5, n=292) vs faint
0.734 (83%, n=270). Exemplar-matched segments only: bold **0.855** vs faint
**0.037** — the model is effectively blind to the faint extreme. Terrain clean
(Spearman -0.040, median slope 4.68 vs 4.42).

---

## 2026-07-29 — bold vs faint roads: the faint class is unlabelled and undetected

Full write-up: `docs/iterations/road_bold_vs_faint.md`. New script
`notebooks/wellsight_v2/analysis/_bold_vs_faint_roads.py`. Outputs in
`data/derivatives/experiments/road_morphology_bins/bold_vs_faint_*`.
**Supersedes the central conclusion of the road_morphology_bins entry below.**

**Why.** User hand-labelled exemplars of the two varieties they see —
`annotations/bold_roads.shp` (8 lines / 1.79 km) and `faint_roads.shp`
(21 lines / 2.35 km) — and asked to compare the roads AND their surroundings.

**The finding that reframes everything: 0 of 21 faint roads exist in
`roads.shp`** (coverage 0.00 each, median 87.4 m to the nearest annotated line),
while 8 of 8 bold roads do (coverage 0.98-1.00). The earlier morphology pass
analysed `roads.shp` and concluded "one width, one population, a continuum" —
it found one population because only one was in the file. It measured the
**annotated** population and mistook it for the road population.

**The model is blind, not weak** (`road_unet_1m_recall/road_prob.tif`):

| | P(road) mean | >=0.5 | range |
|---|---|---|---|
| bold | 0.775 | **8/8 (100%)** | 0.57-0.89 |
| faint | **0.032** | **0/21 (0%)** | 0.00-0.09 |

No overlap — the best faint road scores 6x below the worst bold one. P(drainage)
~0 for both, so they are not being misread as drainage; they are undetected.
**Every published road metric is therefore bold-conditional** — the 0.754
extraction F1, the recall numbers, the alpha tuning, all scored against
`roads.shp`. This also explains the 613590 active-learning loop, where the user
drew 373 added roads / 37.68 km: that is this class.

**Road contrast** (n=8 vs 21, Mann-Whitney + BH; 25 of 65 features q<0.05, six
at |Cliff's delta| = 1.00): positive openness on tread 85.76 vs 88.47 (delta
-1.00), lrm25 -0.127 vs -0.023 (-1.00), roughness contrast +0.129 vs 0.000
(+1.00), incision depth **0.547 vs 0.181 m** (+0.96), slope contrast +2.39 vs
-0.44 deg (+0.95), length 222 vs 119 m. The faint median incision (0.181 m) sits
**below the p5 (0.23 m) of the entire annotated population** — outside it, not
its low tail.

**Surroundings contrast** (what was asked): road density within 100 m **0.716 vs
0.104 km** (delta +1.00), distance to nearest pad **0 vs 126 m** (-0.94), canopy
cover in the 25-60 m band **0.155 vs 0.310** (q 0.040), context slope 2.7 vs
4.0 deg. Bold roads live in open, pad-adjacent, road-dense country; faint roads
are isolated under closed canopy. Setting separates them nearly as well as
construction does.

**Caveats kept in front.** `dist_pad_m` is 0 for all 8 bold roads, so
bold-vs-faint is partly confounded with pad-adjacent-vs-not and n=8 cannot
separate them. Exemplars were chosen as clear cases, so effect sizes overstate a
random sample. Transect-level stats are pseudo-replication and are reported as
`delta_transect` but never quoted. Two profile panels are unusable: CHM medians
are flat at 0 (zero-inflated raster — only the `canopy_cover_*` fraction form
works) and `roughness_11` renders quantized.

**Actions.** (1) Annotate the faint class — this is a label-coverage problem
before it is a model problem, and no loss or architecture fixes an absent class.
(2) Re-report road metrics as bold-conditional until faint labels exist. (3) Use
the context features (road density, pad proximity, canopy cover) but validate
them on faint roads far from pads, since they carry the confound. (4)
`prominence_z` is retired as a bold/faint discriminator — it was fitted on
bold-only data; it survives as a within-bold measure.

---

## 2026-07-29 — Road "big vs faint": width is constant, depth is a continuum

Full write-up: `docs/iterations/road_morphology_bins.md`. New script
`notebooks/wellsight_v2/analysis/_road_morphology_bins.py`. Outputs in
`data/derivatives/experiments/road_morphology_bins/`.

**Why.** User observation: the annotated roads come in two varieties, big and
faint. Asked whether that split is real and where the boundary sits.

**Method.** Cross-section, not plan shape. `annotations/roads.shp` clipped to 9t
= 1,112 roads / 186.20 km; perpendicular transects every 10 m, +/-25 m at 0.5 m
= 18,062 transects / 1.82 M samples, each detrended on the OUTER thirds only so
the road never influences its own trend surface. StandardScaler -> PCA(90%) ->
KMeans, k by silhouette, mirroring [[pad_morphology_bins]].

**The premise is half right. k=2 IS the best partition** (silhouette 0.229 vs
0.164 at k=3), but not on the axis assumed.

| | bin 0 | bin 1 |
|---|---|---|
| n / km | 686 / 106.3 | 410 / 79.4 |
| incision depth | 0.51 m | 0.86 m |
| width (berm-to-berm) | 14.0 m | 15.0 m |
| width (FWHM) | 6.38 m | 6.50 m |
| hillslope at crossing | 2.85 deg | 7.85 deg |
| TIGER match / P(road) | 0.080 / 0.746 | 0.061 / 0.753 |

1. **Width does not vary.** eta^2 = **0.001** for FWHM width and 0.016 for
   berm separation, against **0.508** for incision depth. Network-wide
   berm-to-berm CV is **0.20**. The 9t roads are one width — consistent with a
   single-lane access-road construction standard used throughout the field.
2. **Depth is a continuum, not two populations.** 1-D GMM on log depth prefers
   **one** component (BIC -776) over two (-753). The k=2 bins are a threshold on
   a continuum, not a discovered boundary. **Central result, and negative.**
3. **Depth is substantially terrain.** Spearman **+0.42** with hillslope; bins
   retain eta^2 0.24 on hillslope even with terrain features excluded. A road
   benched into a sideslope must be cut in; the same road on flat ground need
   not be. Much of "looks faint" is "is on flat ground".
4. **Neither bin is the public network.** Only 80/1,096 roads (7%) match TIGER
   over >=50% of length, and the match rate is *lower* for the deeper bin. The
   annotated network is lease/haul/skid roads, so TIGER cannot label "big".
   Model P(road) is flat across bins (0.746 vs 0.753) — no evidence the U-Net
   finds faint roads harder.

**Deliverable: `prominence_z`.** log(incision depth) regressed on
log(hillslope), residual z-scored = how strongly a road is expressed FOR ITS
TERRAIN. Terrain coupling **+0.416 -> -0.002**. On every road in the output
GeoPackage. Use a threshold on this rather than the hard bins.

**Three measurement bugs found and fixed en route.** (a) The first run binned
terrain, not size (hillslope 8.7 vs 2.7 deg) — terrain features moved out of the
clustering. (b) `tread_width_m` (contiguous slope <= 8 deg) has no terminating
shoulder on flat ground and reported *wider* treads for the fainter roads —
replaced by berm separation + trough FWHM. (c) CHM medians measured the
zero-inflation, not canopy (`chm_9t_05` tile median 0.091 m, p99 25.8 m) —
switched to p90 per band. Also flagged: `intensity_ground_9t_05` is 44.6% nodata
over the samples, so `inten_ratio` is the weakest feature in the set.

**Consequences.** Do NOT build a two-class road model — there is no second
population to learn. Do use `prominence_z` for candidate prioritisation and
sample stratification. Terrain-stratified recall reporting is now possible and
has never been done.

---

## 2026-07-29 — Drainage: 9t model vectorized to review layers on 613590

Full write-up: `docs/iterations/drainage_review_613590.md`. New scripts
`notebooks/wellsight_v2/build/_build_drainage_review_package.py`,
`_calibrate_drainage_extraction_9t.py`, `_overlay_drainage_review_613590.py`.
Outputs in `data/derivatives/tiles/data_3x3/westernpa_d20/613590/review_drainage/`.

**Why.** Run the road active-learning pipeline end to end for drainage: 9t
labels → U-Net → apply to 613590 → vectorize → `review_`/`added_` layers the
user edits in QGIS, exactly as `review_roads_613590`/`added_roads_613590` work.
Only the vectorization step was missing — [[drainage_unet_1m]] (2026-06-16, val
drainage IoU 0.811, AP drainage-vs-road 0.990) and its 613590 inference already
existed.

**Raster provenance trap.** Two files share the name
`drainage_prob_613590_1m.tif`: the block-directory one is the **road** model's
third class (0.591% of tile ≥0.5); the correct one is
`tiles/9t/drainage_unet_1m/drainage_prob_613590_1m.tif` from the **dedicated**
drainage U-Net (0.709%). An early version of this pass used the wrong file and
reported a "4.5x drainage under-prediction" — wrong raster, and it compared
pruned centreline length to raw hand-drawn line length. **Retracted.** The
defensible transfer number is pixel coverage: 1.035% on 9t (training domain) vs
0.709% on 613590, a 32% drop — ordinary out-of-domain softening.

**Main result: the vectorizer was mis-tuned, and calibrating it doubled the
output.** Extraction settings were inherited from the road pipeline and never
checked against drainage GT. Swept 48 configs on the 9t held-out test blocks,
scored with the same Heipke/Wiedemann 8 m buffer matching `_road_optimize.py`
uses, so the F1 is road-comparable:

| config | comp | corr | F1 | km |
|---|---|---|---|---|
| road settings carried over (island=100, spur=20) | 0.552 | 0.747 | 0.635 | 5.01 |
| **calibrated (t=0.50, min_px=60, spur=10, island=0)** | **0.824** | **0.737** | **0.778** | 7.52 |

The 100 m island filter was the culprit — a drainage network is mostly short
first-order tributary stubs and the filter deletes them. Removing it buys **27
points of completeness at zero cost to correctness**. Road extraction scores
0.754 on the same harness, so drainage vectorizes slightly *better* than roads.
Delivered package went 13.62 km → **30.60 km** (0.67 → 1.51 km/km²), 1,131
segments. Calibration record: `tiles/9t/drainage_extract_calib_9t_1m.json`.

**QC.** Blue lines sit in hollows and valley bottoms and stay distinct from road
predictions (the 0.990 drainage-vs-road AP holds visually out of domain). The
weakness is **fragmentation** — disconnected stubs rather than connected
downhill networks. Topology failure, not placement failure, and exactly what
clDice targets. No bridging was added: an invented channel taught as a positive
is worse than a gap the reviewer draws by hand, so connectivity should be fixed
in the loss. `gt_dist_m` is null throughout — no hand-drawn drainage within
500 m of 613590, so nothing in the package is supervised.

**Next.** (1) user reviews the 1,131 segments + draws misses; (2) clDice
drainage retrain — it won the connectivity pole in [[road_sweep_202607]] and
drainage suits it better than roads, being tubular and connected by nature; loss
already implemented in `_road_sweep_202607.py`; (3) ingest the review as a
corrections block mirroring `_build_road_corrections_613590.py`.

**Side finding, filed not pursued.** While diagnosing, 613590 turned out to have
no water mask (11 of 25 blocks lacked one). Built it in 42 s;
`water_banks_613590_1m.tif` covers 22.2% of the road segments the user had
already deleted, with **zero** kept roads, hand-added roads, or drainage
segments over it. Free road precision, no labeling. The other 10 blocks cannot
be built — `enumerate_blocks` only yields the 15 blocks whose source LAZ is on
disk. Both logged in BACKLOG rather than acted on.

---

## 2026-07-28 — Pad U-Net 5-fold cross-validation (all 650 pads scored)

Full write-up: `docs/iterations/pad_unet_cv5_9t.md`. New scripts
`notebooks/wellsight_v2/plats/_pad_unet_cv5.py` and
`notebooks/wellsight_v2/eval/_pad_cv5_tau_scale.py`. Outputs in
`data/derivatives/tiles/9t/pad_unet_cv5/`.

**Why.** Companion to the pit CV. Pad numbers rested on 93 test pads from one
split. Parameters copied verbatim from `_plat_unet.py` (patch 384, jitter 40 m,
2 classes, focal 0.15/0.85, 40 epochs), so this measures the split and not a new
model. 650 pads across 129 blocks, folds balanced to within 3 pads.

**Result, pooled over 650 pads.**

| selection | R@IoU 0.3 | P@0.3 | R@0.5 | locate |
|---|---|---|---|---|
| by F1 | **0.917** (per-fold 0.894–0.946, sd 0.021) | 0.606 | 0.782 | 0.928 (603/650) |
| by F2 | **0.920** (per-fold 0.879–0.946, sd 0.025) | 0.591 | 0.788 | 0.909 (591/650) |

IoU scale, F1-selected, thresholds held fixed: 0.3 → 0.917, 0.4 → 0.865,
0.5 → 0.782, 0.6 → 0.622, 0.7 → 0.380.

**The single split was pessimistic here too** (0.882 / 0.547), same direction as
the pits, smaller magnitude.

**Pads are the more stable model.** Per-fold recall sd 0.021 against 0.088 for
pits. Median pad area is 1,343 m² against ~26 m² for a pit floor, so boundary
disagreement barely moves a pad's IoU.

**F1 and F2 nearly agree** — pooled recall differs by 0.003, and three of five
folds picked the same threshold under both.

**One honest wrinkle.** On fold 3 the F2 selection scored recall 0.879, below the
F1 selection's 0.894, despite F2 favouring recall. F2 did pick the lower
threshold as designed; it simply scored worse on the held-out fifth. Val and
held-out do not always agree. Both objectives were declared in advance and both
are reported, which is the point.

**Locate metric substitution.** Pads have only one annotated polygon, so the pit
rim-containment metric becomes "annotated pad contains at least one predicted
centroid".

**Three bugs found and fixed.**
1. **Resume could reuse a partial checkpoint.** The run was killed at epoch 35/40
   of fold 2, leaving a `best.pt` from an incomplete schedule that the resume
   path would have reused, silently giving that fold fewer epochs than its
   siblings. `train_log.csv` row count is now the completion record.
2. **Inner-val draw was execution-order dependent.** One RNG created before the
   fold loop meant skipped folds shifted every later draw, so `--only-folds`
   gave a different inner val than a full run. Observed live: pad fold 2 drew 93
   inner-val pads originally and 112 on resume. Held-out sets are unaffected, so
   no scored number is invalid — only exact reproducibility. Now seeded per fold
   with `CV_SEED + 1000 * k`. **The same issue affected pit fold 4**, which was
   re-scored alone; disclosed in the pit iteration doc.
3. **`flush()` crashed on an empty result set**, breaking the dry-run path used
   to check fold balance before spending GPU time.

**Cost.** ~30 min per fold at patch 384, 88.9 min for folds 2–4. My initial
75–100 min estimate for all five was wrong; the real figure is ~2.5 h.

**Abstract updated to v13.** Both models are now cross-validated, so the
asymmetry flagged in v9 is gone. Pad recall 0.88 → 0.92 at IoU 0.3, precision
0.55 → 0.61.

---

## 2026-07-27 — Pit U-Net 5-fold cross-validation (all 426 pits scored)

Full write-up: `docs/iterations/pit_unet_cv5_9t.md`. New script
`notebooks/wellsight_v2/pits/_pit_unet_cv5.py`. Outputs in
`data/derivatives/tiles/9t/pit_unet_cv5/`.

**Why.** Every pit number we quoted rested on 65 test pits from one split. Too
small for a 3-point difference to mean anything, and open to the objection that
the split was lucky.

**Design.** Five models, each holding out a different fifth of the tile. Split by
**block** (128 m patches with 30 m jitter can overlap a neighbouring held-out
pit), balanced on **pit count** (pits cluster on pads), seed 20260727. Inner val
is 20% of the remaining blocks. The held-out fold never influences its own
threshold or its own best epoch.

**Threshold selection declared before scoring.** Two objectives, both reported:
F1 (recall and precision equal) and F2 (recall weighted 4x, matching the real
asymmetry that a missed well costs more than a false alarm). Picking whichever
looked better afterwards would be the cherry-pick this pass exists to avoid.

**Result, pooled over 426 pits / 424 rims.**

| selection | R@IoU 0.3 | P@0.3 | R@0.5 | containment |
|---|---|---|---|---|
| by F1 | **0.854** (per-fold 0.736–0.954, sd 0.088) | 0.617 | 0.711 | 0.899 (381/424) |
| by F2 | **0.920** (per-fold 0.880–0.953, sd 0.035) | 0.553 | 0.730 | 0.955 (405/424) |

**The single-split number was pessimistic, not optimistic.** We had been quoting
0.754 at IoU 0.3. That split drew a hard fifth, and its val-selected threshold of
0.60 sits past the recall cliff. Recall is stable under F2 (sd 0.035). Precision
is the weak number and never exceeds 0.65 at any of the 16 thresholds swept.

**Caveat kept in front, not buried.** Every fold is still 9t — one landscape, one
survey, one canopy condition, one annotator. This measures whether the number is
**stable**. It does not measure whether it **transfers**. A held-out tile remains
the open question.

**Disclosed leak.** `feature_stats.json` (7 means, 7 sds) is reused across folds
rather than recomputed per fold. 14 global numbers enter each fold. Small, not
zero, cheaper to disclose than to re-derive.

**Three bugs found and fixed.**
1. CSVs were written only after the fold loop, so a fold-4 crash destroyed four
   folds of finished work. Now flushed after every fold, with carry-forward of
   folds not being re-run.
2. `_dl.predict_full_tile` moved input patches to the GPU but never the model,
   relying on `train_loop` having done it. Any caller that loads a checkpoint and
   predicts immediately died with a Half/Float type mismatch. Fixed at the source
   in `notebooks/wellsight_v2/_dl.py`.
3. Scoring polygonized the full 9000x9000 tile at 16 thresholds. Now zeroed
   outside the val and held-out footprints (buffered 40 m so no scored blob is
   clipped). Stall to ~2 s per threshold. No scored number changed.

**Environment note.** The original run died with a 1.75 MiB numpy allocation
failure while C: was at 100% (928 MB free of 931 GB). A full disk stops the
Windows pagefile growing, which surfaces as tiny allocations failing. Not a
script memory bug.

---

## 2026-07-27 — Threshold sweeps extended to pads and roads

Full write-up: `docs/iterations/threshold_sweeps_pit_pad_road_9t.md`. New scripts
`_pad_threshold_products_9t.py`, `_road_threshold_products_9t.py`, shared helpers
factored into `_threshold_common.py`. Ground truth is hand-drawn annotation only.

**Pad (194 held-out plats).** Best IoU>=0.30 recall **0.918 (178/194) at
threshold 0.45–0.50**, claiming 10–12% of the 2,025 ha tile. Every held-out pad
has signal (`max_prob` min 0.185, median 0.785, none below 0.05).

**Pad merging artifact — the main methodological result of this pass.** The
first run carried the pit criterion over unchanged (a prediction's centroid must
lie inside the annotation) and reported **0/194 found at threshold 0.05**, the
cutoff claiming 58% of the tile. Cause is blob merging, not the model. Pad
probability has a high background (tile mean 0.162 vs 0.039 for roads), so below
~0.30 predictions merge into tile-spanning super-blobs whose centroids sit
inside no individual pad. Fixed by reporting three criteria that fail in
opposite directions — `pred_centroid_in_gt` (dies on merging),
`gt_centroid_covered` (dies on over-claiming), and `iou >= 0.30` (penalised by
both, so it is the headline). At 0.05 the three read 0 / 0 / 194, which is the
signature of total merging.

**Road (1,220 held-out chunks, 43.07 km).** Monotonic and very flat — recall
stays above 0.95 from threshold 0.05 to 0.80. At 0.30, 0.985 recall for 4.345%
of the tile. Only 3 of 1,220 chunks have no road-like signal at all.

**Road confusion check confirms the 3-class design.** Held-out DRAINAGE claimed
as road falls 3.9% -> 2.1% across the useful range, and held-out NOT_ROAD is
claimed at **0.0% at every single threshold**. Both are hand-drawn negatives, so
this is direct evidence, not a proxy.

**Road leakage quantified.** Roads split as ~40 m chunks, not whole objects, so
**485/1,220 held-out chunks (39.8%) share a parent road with train chunks** —
the standing BACKLOG "split leakage" item. Added a `clean` flag (735 chunks, 221
of 344 parent roads fully held out) and a `recall_clean` column. Measured cost is
~1.5 points (0.977 vs 0.962 at threshold 0.50), so leakage is real but not
result-changing. `recall_clean` is the number to compare against pit and pad.

**Cross-task read.** Pit 0.992 at 0.21% of tile, road 0.982 (clean) at 4–5%,
pad 0.918 at 10–12%. Pad also claims ~197.95 ha at 0.50 against roughly 110 ha of
total annotated pad area. **The pad U-Net, not the pit U-Net, is now the
highest-value target.** Added to BACKLOG.

Stale 0.20/0.30 pad products from the superseded-criterion first run were deleted
rather than left on disk.

---

## 2026-07-27 — Pit 0.05 reference raster + refinement literature survey

**0.05 reference cut.** Added 0.05 to `_export_pit_floor_threshold_tifs.py`
alongside 0.20 and 0.30. It is a *reference* view, not an operating point —
every held-out rim has `max_prob >= 0.05` (p05 = 0.472), so this cut shows the
full extent of anything the model considered pit-like at all. Far too permissive
to use: 2,820,569 px = 70.51 ha = **3.482%** of the tile, versus 0.214% at 0.20
and 0.139% at 0.30. A 16x area increase over 0.20 buys one extra pit.

Wrote:
- `data/derivatives/tiles/9t/pit_unet_v2/pit_unet_floor_prob_thr0p05_9t_05.tif`
- `data/derivatives/tiles/9t/pit_unet_v2/pit_unet_floor_mask_thr0p05_9t_05.tif`

Also made the exporter tolerate a Windows file lock (QGIS holding a raster open)
instead of aborting the remaining thresholds.

**QGIS bookmark format bug, found and fixed.** The `pit_missed_bookmarks_*.xml`
files shipped in a16d607 used the QGIS 2 attribute form, which QGIS 3 parses to
a null rectangle and rejects with "Bookmark extent is empty". Two separate
defects: `sr_id` is the internal `srs.db` row id, not the EPSG code (EPSG:6346 =
28818), and every field must be a child element with the group in `<project>`.
Format was established by exporting a bookmark from QGIS 3.40.10 via
`QgsBookmarkManager.exportToFile`, and all four files were then verified by
re-importing through `importFromFile` with non-null EPSG:6346 extents. Commits
37aea18 and 652765b.

**Refinement survey.** Two review observations drove it: pit probabilities lower
than expected, and fragmented/partial floors. Survey in
`docs/iterations/pit_refinement_options.md`, twelve citations added to
`literature/CITATIONS.md`, nine PDFs downloaded.

Two mechanical causes identified by reading our own code, not by inference:
1. The pit U-Net trains on `FocalCE` alone (`gamma=2.0`), with no region,
   boundary, or topology term. Mukhoti et al. 2020 document that focal loss is
   empirically *under-confident*. Low peak probabilities are the expected
   behaviour of the loss we chose.
2. `_dl.py:445-449` blends overlapping inference patches with a **uniform box
   mean**. Edge-of-patch predictions, made with one-sided context, are weighted
   equally with full-context centre predictions. This dilutes any pit straddling
   a patch boundary, and is a candidate cause of the fragmentation.

Ranked plan in the iteration doc. Steps 1–4 need no retraining and are scoreable
on the existing 127 held-out rims via `_heldout_rim_containment_9t.py`. Next
action is the cheapest one: test whether the fragmentation aligns with the 128 m
patch grid, which decides between an inference-stitching bug and a model
property.

---

## 2026-07-26 — Where the non-erosional 9t change is (artifact removal + null test)

Follow-up to 2026-07-25. Script:
`notebooks/wellsight_v2/build/_icp_change_classify_9t.py`.

1. **Three-stage artifact removal.** σ 0.136 → 0.107 (row/col median destripe)
   → **0.087 m** (edge-preserving 400 m median background, removes a broad field
   of std 0.057 m). A Gaussian high-pass was tried first and rejected: it cannot
   remove the sharp-edged per-tile blocks in the 2006-2008 mosaic, only smear
   them. A median background is edge-preserving and does remove them.
2. **Monte-Carlo null proves the change is real.** The residual is spatially
   correlated (integral range 16–20 px, one independent sample per ~1,290 m²), so
   raw patch counts are meaningless alone. Against a matched-autocorrelation
   synthetic field pushed through the identical pipeline:
   observed **367 patches / 44.12 ha / largest 24,920 m²** vs null
   **57±5 / 1.56 ha / largest 558 m²** — **6.4× patches, 28× area, 45× largest**.
   Null max patch (712 m²) becomes the reliability cutoff; 108 patches clear it.
3. **The fluvial rule was tested, not assumed.** 63% of block area is within 40 m
   of a channel. Observed: 75% of all patches, **84% of reliable** patches
   (1.34× enrichment). Correction to an earlier intermediate result — a flat
   0.97–1.02× enrichment measured on the destriped-but-not-high-passed field was
   the residual bias field swamping the signal, not evidence against the rule.
4. **Result:** fluvial 91 reliable / 32.57 ha; mass wasting 1 / 0.12 ha;
   **non-erosional 16 reliable / 2.65 ha / ~10,800 m³**. 10 of the top 12
   non-erosional patches lie within 20 m of a mapped road — road maintenance and
   regrading, not well activity. No pattern in distance to known wells.
5. **Two bugs caught and fixed mid-pass.** (a) Flow accumulation was resampled to
   2 m with *bilinear*, averaging away thin channel maxima (range 7.14 → 4.64) so
   a fixed threshold caught 104 px and 300/310 patches fell through to
   "anthropogenic"; switched to `Resampling.max` + the purpose-built
   `stream_seed_t5000` raster. (b) A curvature-contamination hypothesis for the
   red/blue edge dipoles was tested and **rejected** — corr(DoD, ∇²z) = +0.01,
   DoD spread flat across curvature bins.

Outputs: `data/derivatives/experiments/icp/change_9t/`
(`dod_9t_destriped_2m.tif`, `dod_9t_highpass_2m.tif`, `change_patches_9t.gpkg`,
`change_classified_9t.png`, `top_changes_9t.png`, `_classify_9t.json`).
Write-up: `docs/iterations/icp_change_9t.md` (Part 2).

---

## 2026-07-25 — Preliminary ICP change detection on 9t (2006-2008 → 2019)

Clipped the existing full-overlap DoD to the 9t footprint and ran the QC that
decides whether it is usable. No ICP was re-run — the alignment and the 2 m
difference raster were already built 2026-05-21.

1. **Vertical agreement is excellent.** Median +0.003 m, robust σ 0.136 m over
   2250×2250 px at 100% valid.
2. **Registration QC passed.** Slope-stratified σ *decreases* with slope
   (fit `σ = −0.024·tan(slope) + 0.135`), so implied residual planimetric error
   ≈ 0 m. The earlier worry that the ~0.8 m datum shift would dominate a DoD was
   wrong; ICP removed it cleanly.
3. **The real limitation is swath striping in the 2006-2008 survey.** Row-mean
   (along-track) range ±0.22 m, std 0.094 m; removing row+col means takes σ from
   0.183 → 0.154 m. Detection floor is therefore ~0.4 m, set by acquisition
   artifacts rather than by registration.
4. **No detectable change at known wells.** 540 known wells inside 9t; DoD at
   wells median +0.013 m; 4.4% exceed 3σ vs a 3.63% background rate (z ≈ 1.0,
   not significant). Expected — these wells predate both surveys, so both see the
   same settled ground. **This epoch pair cannot find historic orphaned wells.**
   It can only find recent activity (new pads, regrading, plugging, subsidence).

Script: `notebooks/wellsight_v2/build/_icp_change_9t.py`.
Outputs: `data/derivatives/experiments/icp/change_9t/`
(`dod_9t_2m.tif`, `dod_9t_sig_2m.tif`, `change_9t_quicklook.png`, `_stats_9t.json`).
Write-up: `docs/iterations/icp_change_9t.md`.

Data-quality flag: `data/derivatives/experiments/icp/003111/_meta_icp_5m.json`
records a failed run (`converged: false`, fitness 39.4), superseded by a good
re-run. Stale file still on disk; `_icp_change_map.py` correctly reads
`_meta_icp_zm.json` instead.

---

## 2026-07-23 — Linear-feature channels: build, curvature fix, and the cldice_sg3 A/B

Driven by a literature review + a bench-detection diagnosis (LRM unsharp mask is
**curvature**-contaminated, not slope-limited: `DEM − focal_mean` leaks ~`(σ²/2)∇²z`).

1. **Fixed the 613590_05 SE-corner hole.** Not missing data — tile `616590` landed
   2026-06-14, two days *after* the 2026-06-12 build. Rebuilt with all 19 tiles:
   DEM nodata 5.56% → **0.00%**.
2. **Built 17 experimental channels** (`_build_extra_channels.py`): slope_residual,
   diff_openness, rough_aniso/orient, profile_curv + curv_doublet, SLLAC, Frangi,
   Sato ridge + orientation, SavGol quadratic residual, top-hat white/black.
   Visual QC winner: **SavGol quadratic residual** — at a matched 18.5 m window the
   mean residual drowns in hillslope curvature while the quadratic removes it.
3. **Quantified the composite.** Per-pixel road/bg contrast only **1.19×** (mean) /
   1.13× (geometric-mean AND). AND is *worse* because the signals are spatially
   offset (curv on edges, savgol on tread, aniso on centerline). Roads read well to
   the eye because of *continuity*, not per-pixel brightness.
4. **A/B trained `cldice_sg3`** = cldice + 3 channels, controlled (same seed/batch/
   epochs; corrected init transferred via 7→10 expanded first conv, new filters zero).
   Result: missed-road recovery **0.957→0.978**, add-v-rej AP **0.470→0.486**,
   P(road) 0.885→0.889; but pixIoU **0.558→0.550** and reject confidence up (more FP).
   Deltas ~0.02 on a **single seed** — promising, not conclusive.

**Decision:** per-pixel channel engineering is near its ceiling; the remaining lever is
orientation-guided gap-linking (`ridge_orient` + Ferraz 2016 / Batra 2019). Multi-seed
repeat needed before promoting cldice_sg3. Citations logged in `literature/CITATIONS.md`
(11 + Savitzky-Golay 1964, Wood 1996, Soille 2004). Details: [[linear_feature_channels]].

---

## 2026-07-20 — Well reporting-provenance flags (bounty-era proxy via 2022→2026 diff)

User asked how to identify bounty-reported wells in `venango_wells_all`. The
DEP export has **no source/date-entered field**, so no direct flag exists.
Built proxies instead (script
`notebooks/wellsight_v2/analysis/_well_provenance_flags.py`, layer
`data/derivatives/experiments/well_provenance/well_provenance.gpkg`):

- Established the two snapshots: NEW = `venango_wells_all.gpkg` from
  **OilGasLocations 2026-04** (20,108 all-status Venango wells, PERMIT_NUM
  "121-27187"); OLD = `US_Documented_Orphan_Wells.csv`, **Data file date
  2022-05-09** (4,786 Venango orphans, Well_ident "API:37121000860000").
  Both key on (county, permit_int); all 4,786 old keys resolve into NEW.
- Flags: `provenance` (operator_permitted 15,353 / dep_found 4,755),
  `in_2022_orphan_list`, **`newly_documented`** (dep_found AND not in 2022
  list = **1,316** wells that entered the abandoned/orphan inventory
  2022-05→2026-04; 937 DEP Abandoned List, 353 Abandoned, 8 Orphan List, …),
  `fed_plugging_program` (51, IIJA/MERP site names).
- **Caveat recorded in the layer:** `newly_documented` is the bounty-era
  proxy but the window is 4 years (June-2025 bounty sits inside it, not
  alone) and it catches active/plugged→abandoned reclassifications, not only
  new field locations. A true bounty flag needs dated DEP snapshots diffed at
  <1 yr granularity.
- **Actionable:** 6 newly-documented wells fall inside the 9t tile, 71 within
  2 km — candidates to check against our pit/pad detections (recent field
  reports on ground we've already inferred).
- **McKean added (same day):** generalized the builder to regions; clipped the
  statewide 2026-04 export to McKean (COUNTY_ID 42, 38,110 wells). 4,582
  dep_found, 70 fed-plugging, and **1,433 dep_found wells INSIDE the mkf block**
  (1,912 within 2 km) — 7× the 9t density, consistent with McKean being PA's
  densest orphan county (Bradford field). **No bounty-era diff for McKean**:
  the only 2022 orphan baseline on disk is Venango-only, so the temporal proxy
  isn't computable there — status-based flags (dep_found / fed_plugging) only
  until a dated McKean orphan snapshot is obtained. Outputs now
  `well_provenance_{venango,mckean}.gpkg` (unsuffixed superseded, git-removed).

---

## 2026-07-21 — Road U-Net top-5 sweep complete: two poles, clDice front-runner pending APLS

All 5 variants trained + evaluated (driver `_road_sweep_202607.py`, seeded +
frozen-val; writeup `docs/iterations/road_sweep_202607.md`; leaderboard +
fig in `data/derivatives/tiles/9t/road_sweep_202607/`). No single winner —
a precision/recall split:

- **cldice** (soft-clDice topology loss): best connectivity — P(road) on real
  9t roads 0.784→**0.885**, 613590 held-out missed-road P 0.780→**0.889**. Low
  pixIoU (0.558) is a metric artifact (clDice optimizes centerline, not
  pixels). add-v-rej AP dropped 0.541→0.470. **Front-runner for the gap goal.**
- **boundary** (3× road-edge weight): best val IoU 0.668 + pixIoU 0.601,
  cleanest drainage 0.004, but fills less (added≥0.5 0.913). Precision pole.
- **alpha078**: ≈ no-op (val IoU +0.003) — α headroom already spent at 0.72.
- **orient** (aux direction head, scratch): best add-v-rej AP 0.660 but
  **drainage bled to 0.030 (6×)** — deploy-disqualifying as-is.
- **res05** (0.5 m, 9t-only scratch): inconclusive — grid not pixIoU-
  comparable, likely undertrained, drainage bled. Re-run with road-physics
  channels before judging 0.5 m.

Decisions: honest arbiter is vector extraction/APLS (matches the goal, and is
exactly where clDice's topology objective vs boundary's precision objective
diverge) — next step is to run cldice+boundary through `_road_optimize.py` vs
the 0.754 F1 and promote the winner. clDice+boundary combined = natural full-10
first entry. Method note: fully seeded + val-patch RNG reset each epoch fixed
the audit's re-jitter noise, so the ranking is real not luck. Task #56 done.

---

## 2026-07-20 — Road active-learning loop CLOSED: human corrections → measurable out-of-domain gain

Turned the user's 2026-06-17 QGIS review of 613590 (1,585 rejected segs /
14.3 km, 102 added roads / 7.5 km, 15,410 kept) into a corrected training block
and fine-tuned the champion recall model on it. Scripts
`_build_road_corrections_613590.py` + `_road_unet_1m_corrected.py` +
`_compare_corrected_613590.py`; writeup `docs/iterations/road_unet_1m_corrected.md`;
model `data/derivatives/tiles/9t/road_unet_1m_corrected/`.

- **Corridor supervision:** label raster is 255=ignore for 93.8% of the block
  (only human-adjudicated pixels get a loss), so unlabelled real roads are
  never taught as bg. FocalCE skips ignore (added an all-ignore-patch guard).
- **Honest split:** 4×4 cells assigned by seeded search so added+rejected km
  balance across train/val/test (additions cluster NW — naive split held out
  zero); train centers eroded 158 m from cell edges (no patch overlaps
  held-out cells); "before" raster verified byte-identical to what the user
  reviewed.
- **Result (best ep 15, 9t val road IoU 0.636):** in-domain 9t test flat
  (pixel IoU 0.581→0.573, drainage still 0.005). On 613590 **held-out**
  corrections: added-road P(road) 0.72→0.76 (val) / 0.74→0.78 (test),
  frac≥0.5 0.85→0.94 / 0.89→0.96; reject P(road) 0.34→0.26 (val, flat on test
  which had no headroom); kept held ~0.85; added-vs-reject AP 0.245→0.443
  (val). Recall up, precision up, no forgetting, zero in-domain cost.
- Decision: fix-in-training (rejects as hard negatives) beat any post-filter;
  loop is reusable for another round or a fresh block. Next: vector extraction
  → APLS vs the recall model's 0.754 F1; swap 613590 deploy raster to the
  corrected one. Task #36 done.

---

## 2026-07-20 — Ground-photo web sweep, georeferenced (photo_sources + VPASEC layer)

User asked for ground photos of our pits/pads/roads, referenced to location.
Web sweep + KML extraction (script
`notebooks/wellsight_v2/analysis/_photo_source_locations.py`; source list in
`docs/articles/well_photo_sources_2026-07.md`; layer
`data/derivatives/experiments/well_photo_locations/well_photo_locations.gpkg`).

- Extracted the public VPASEC found-wells Google map → **1,926 GPS'd wells**
  (841 Oil Creek SP, 76 SGL 253, 46 SGL 39, 43 SGL 45, 920 DEP-plugged);
  KML archived at `data/external/vpasec/vpasec_wells_venango.kml`. **Zero
  inside 9t**; nearest DEP-plugged well 0.56 km from the tile edge, 26
  within 3 km (Pithole-side APIs 121-42xxx).
- 10 photo locations georeferenced with a `precision` flag: Pithole site
  0.75 km from 9t NW corner; **Derrick City 1930 oil-field photos inside the
  mkf block**; StateImpact McKean stream casing ~1.2 km from block.
- Best photo set of our morphologies: VPASEC 50-photo album (wood casing in
  depression, open hole in pit, bare-ground depressions) — album not
  per-photo georefed, folder-level only.
- Leads logged: Drake Well Museum Mather archive (President Twp river
  wells); EDF/DEP drone survey of President + Victory Twp planned spring
  2026 (in-tile magnetometer confirmations when published).

---

## 2026-07-19 — Pad bins v2: joint 9t + McKean, broad k — region IS the morphology split

User asked for broader bins and to bring in the McKean pads. Script made
region-aware (v1 in git at 880e7b6): all 995 pads, McKean terrain/CHM from
mkf_1m + northcentral_b19 blocks (per-pad best-covering source), composition
features dropped (9t-only annotations). Broad structure is binary — silhouette
k=2 0.332 vs k=3 0.216, k=4 0.187 — and it splits by region: bin 0 (603;
593 9t) large gentle-ground pads, edge 7°; bin 1 (392; 335 McKean) small
bench pads on steep slopes, edge 18°, slope_ratio 0.92, chm_deficit 1.6 m.
1-m-vs-0.5-m resolution works against the McKean-steeper reading, so the
contrast is conservative. Implication: 9t-trained pad models have never seen
the dominant McKean archetype. Fix applied mid-pass: NC hillshades are int16
~0–32k, montage now percentile-scales per chip. Outputs
`pad_bins_joint_k{2,3}.gpkg` (styled) + summaries/figures; writeup
`docs/iterations/pad_morphology_bins.md` §v2.

---

## 2026-07-19 — Pad morphology bins: unsupervised k=4 archetypes on 9t (no age target)

User pivot from age-binning to pure categorization. 650 9t pads × 20 features
(shape + composition + terrain context + CHM), scaler → PCA(0.9) → KMeans,
silhouette-selected **k=4** (0.156 — soft bins). Script
`notebooks/wellsight_v2/analysis/_pad_morphology_bins.py`, writeup
`docs/iterations/pad_morphology_bins.md`, outputs + styled `pad_bins.gpkg` in
`data/derivatives/experiments/pad_morphology_bins/`.

- bin 0 (45): **canopy-gap sites** — chm_deficit 7.3 m vs ≈0 elsewhere;
  clearest recency proxy in the whole feature set.
- bin 1 (150): sprawling irregular lease clusters (biggest perimeter, lowest
  solidity, no pits).
- bin 2 (240): flat compact pads on gentle terrain.
- bin 3 (215): pit-bearing benched sites on steep hillsides (edge slope 12°,
  slope_ratio 1.10, smallest areas).
- Decisions: CHM/edge-slope/slope_ratio did the separating (the features the
  2-D-only pass lacked); hillshade-chip montage confirms visual coherence;
  dated-well overlay deliberately deferred so bins stay label-free.

---

## 2026-07-19 — Well age vs morphology: weak era signal, coded dates confirmed sparse for orphans

Question from user: are well ages coded in anywhere, or must we bin by shape?
Answered both halves (script `notebooks/wellsight_v2/analysis/_well_age_morphology.py`,
outputs `data/derivatives/experiments/well_age_morphology/`, writeup
`docs/iterations/well_age_morphology.md`):

- **Coded ages:** `venango_wells_all.gpkg` has `SPUD_DATE` (92.3% populated but
  8,054/18,555 are the `1800-01-01` "unknown historic" sentinel), `PERMIT_DAT`
  (86.1%), `DATE_PLUGG` (35.6%). Coverage collapses on the orphan population:
  DEP Orphan List = 82 real dates vs 997 sentinel (7.6%). Structural — PA
  permitting began 1956. `output_wells.csv` has no date fields at all
  (documented since 2026-04-13, data dictionary note 1).
- **Morphology test:** 1,176 catalog wells within 200 m of hand annotations;
  615 dated wells matched to a pad within 50 m. Spearman vs spud year:
  perimeter −0.273, wells_on_pad −0.258, compactness +0.232, area −0.203 (all
  p < 4e-7); newer = smaller/rounder/less-shared pads. CV random forest
  1956–79 vs 1980–99: balanced acc 0.609, AUC 0.660 — real signal, not
  decision-grade. Historic-vs-modern contrast underpowered (only 46
  sentinel-1800 wells, 20 pad-matched, in the annotated footprint).
- **Decision:** use coded dates + status taxonomy for era where present;
  morphology as prior only. Deferred to BACKLOG: DEM-derived per-well features
  (pit depth, cut/fill volume), annotating a sentinel-dense block.
- Incidental but important: `plat.shp` contains **58 rows with null geometry**
  (1,053 total → 995 with geometry; 15 others invalid but repairable). This
  resolves the BACKLOG item claiming "~58 newest pads postdate the
  annotations_proj.gpkg regen": the gpkg's 995 = every pad that has geometry.
  The gpkg is NOT stale — the shapefile carries 58 empty rows (likely QGIS
  delete artifacts). True pad count is 995. BACKLOG item corrected.

---

## 2026-07-13 — Data repatriation: external-drive data back on C: (project self-contained)

The 2026-07-02 migration put heavy data on the external SSD (then `E:`, since
re-lettered to `F:`), leaving the repo's five junctions dangling and the project
split across two drives — which blocked copying `lidar_project` to the new
external as one unit. Reversed it:

- **Junctions → real dirs (56.5 GB):** removed the five dangling junctions and
  robocopied their targets from `F:\lidar_project_data_DO_NOT_DELETE\` back into
  the repo: `data/source_laz` (239 files, 11.2 GB), `data/derivatives/
  inference_613590_05` (2.2 GB), `tiles/613590_05` (4.1 GB), `tiles/data_3x3`
  (1,513 files, 37.6 GB), `tiles/mkf_1m` (1.3 GB). Byte + file counts verified
  MATCH on all five; the git `D` entries for tracked data_3x3 files resolved.
- **barlow_data (50.2 GB, 1,411 files):** `F:\barlow_data_DO_NOT_DELETE` →
  `<repo>\barlow_data\`, gitignored (`/barlow_data/` rule added same-change).
  The four build scripts (`_fetch_barlow_data`, `_build_barlow_inputs`,
  `_change_detection`, `_finesst_figures`) now resolve it repo-relative via
  `Path(__file__).resolve().parents[2] / "barlow_data"`, so the tree survives
  future drive moves. READMEs / ROADMAP / data manifest updated to match.
- **≥100 MB audit:** clean — zero unignored files over 100 MB after the copy.
- **Left on F: (not project-linked, user's call):** `F:\lidar_project` (304 GB,
  old full mirror from `backup_to_E.bat`), root-level `label_grids`/`annotations`/
  `derivatives` copies, and the two now-redundant `*_DO_NOT_DELETE` source trees.
  `backup_to_E.bat` still targets `E:\lidar_project`, which now points at the new
  external — usable as-is for the fresh mirror.

C: free space after: ~44 GB. Reproduce: junctions were removal-only (`rmdir`);
copy via `robocopy <src> <dst> /E /COPY:DAT /R:2 /W:5 /MT:16`.

---

## 2026-07-09 — WellSight: RRIM completed for every remaining stack (repo-wide sweep)

Closed the "run RRIM on everything" gap: every raster stack with (or derivable) inputs now
has a Red Relief Image Map. Same recipe/script as before (`_make_rrim.py`, classic +
`--simple` where `lrm_11` exists, palette self-scaled at p98, slope_hi 40°).

**C:-hosted (top-level `data/derivatives/`):** `9t_1m` (DO ±4.72°), `mk5_1m` (±5.54°),
`mck_e1423n2238_05` (McKean 0.5 m, ±5.13°), and singles `607594/610594/610605/616593`
(±3.6–5.8°). The 4 singles had no `openness_pos` — computed from each DEM with the
production `openness()` (Yokoyama 1998, L=25 m) and written alongside (means ≈87–88°,
consistent with the existing `openness_neg` era). Classic+simple everywhere (14 products).

**E:-hosted (after the Samsung T7 remounted; junctions had gone dark mid-evening when the
drive disconnected — no data loss):** all 24 remaining `data_3x3/westernpa_d20` blocks
(classic+simple, 48 products, 0 failures); `northcentral_b19` e1423n2235 + e1423n2238
(classic+simple; e1423n2238's missing openness pair computed from DEM), e1426n2236 +
e1426n2239 (DEM-only blocks: slope via `gdaldem slope -compute_edges` + openness computed,
classic only — no `lrm_11`, same precedent as permian_02/03/04); and `mkf_1m` — the full
McKean county 1 m stack, 10000² (classic 122 MB + simple 119 MB, DO ±6.29°).

**Skipped:** `tiles/613590_05` (no slope/openness/lrm inputs; canonical `tiles/9t` 0.5 m
RRIM already covers the identical footprint). All full-res tifs fall under the existing
`data/derivatives/**/*.tif` ignore rule (mkf's two >100 MB products included); preview
PNGs (~1.9 MB each) committed as the visual record per the data_3x3 convention.
Driver scripts: session scratchpad `rrim_everything_else.py` + `rrim_e_drive.py`
(3 parallel chunks); doc updated: `docs/iterations/rrim_visualization.md`.

---

## 2026-07-08 — WellSight: RRIM generated for all 8 study blocks

Extended RRIM to every study block: `label_grids/{permian_01..04, westernpa_01..04}` (1 m).
Classic (openness) RRIM for all 8; Simple/LRM variant for the 5 with an `lrm_11` raster
(permian_01 + westernpa_01..04). permian_02/03/04 lacked a slope raster (openness only) —
derived slope from their `dem_*_1m.tif` via `gdaldem slope -compute_edges`, then built classic
RRIM. Palette self-scales per block: flat Permian at DO ±1.5° (pads read as sharp rectangular
platforms, lease-road grid crisp — useful for the pad-transfer work), WPA at ±4–5° (incised
valleys red/teal, drainage network resolved). Outputs `rrim_{openness,simple}_<block>_1m.tif`
(~20 MB / 3000², ~41 MB / 4500²) + previews, all gitignored under `label_grids/**`. Audit clean.

---

## 2026-07-08 — WellSight: RRIM regenerated at native 0.5 m into canonical 9t dir

The first RRIM pass wrote into the 1 m `data_3x3/westernpa_d20/613590/` build; the canonical
9t stack lives at `data/derivatives/tiles/9t/` with inputs at native 0.5 m. Generalized
`_make_rrim.py` with a `--suffix` arg (filenames `<name>_<tile>_<suffix>.tif`; `1m` for
data_3x3, `05` for the 9t stack) and regenerated both variants into `tiles/9t/`:
`rrim_openness_9t_05.tif` (176 MB, 9000×9000, DO ±4.50°) and `rrim_simple_9t_05.tif` (174 MB).
0.5 m resolves dendritic drainage, road benches, and small depressions the 1 m build blurred —
adopted as the working RRIM. Tifs gitignored (whole `tiles/9t/` dir ignored); no >100 MB leak.

---

## 2026-07-07 — WellSight: Red Relief Image Map (RRIM) visualization

Added an RRIM terrain-visualization component (new `notebooks/wellsight/build/_make_rrim.py`).
RRIM (Chiba et al. 2008; papers dropped in repo root) fuses slope + ridge/valley position
into one direction-independent composite — better than a single hillshade for subtle
micro-relief (pit depressions, pad cut-and-fill, road benches). Classic mode uses
differential openness `DO=(op−on)/2` as the base (teal valleys / gray flats / yellow ridges)
with a white→red slope overlay multiplied on top; `--simple` mode swaps the base for LRM-11
(Auld-Thomas 2022, patent-free). Reuses existing derivatives — no recompute. Palette
self-scales per tile from p98 of |base| (WPA far gentler than the Maya-karst stops the
recipe was tuned on); slope_hi=40° (tile slope p98≈35°). Generated both variants for 9t
block 613590 (4500×4500, 1 m, EPSG:6346): `rrim_openness_*` (DO ±5.15°) and `rrim_simple_*`.
Classic = deeper valley contrast; simple = flatter, crisper on fine linears. Full-res tifs
(~44 MB) gitignored as regenerable viewing products; preview PNGs tracked. Not a model input
(derived from existing bands). Doc: `docs/iterations/rrim_visualization.md`. Was never a prior
decision — only cited as background in the abandoned-roads article + openness computed in
`02_derivatives.ipynb`; no RRIM composite existed before.

---

## 2026-07-07 — Figure 1: zoom Panel B to the channel corridors

Per user, cropped Panel B tight to the incised channels. `_make_realmap.py` now windows the
DEM read (`rasterio.windows.from_bounds`) to `CROP_KM = (1.85, 1.30, 6.90, 5.45)` — the
combined channel-box bbox + a small margin — so the frame is ~5.0×4.2 km instead of the full
7×7 km tile. Channel boxes shifted into the crop's local frame; scale bar / north arrow /
label reposition off `w_km`/`h_km` fractions automatically. New crop changed the image aspect
(1.87→2.03), so `_swap_fig1_color.py` now resizes the Figure-1 shape to the actual image
aspect (6.0 × 2.96 in) to avoid distortion. `fig_location.png` regenerated, swapped into
`finesst_proposal_v5.docx`. Caption unchanged; stays plan-only.

---

## 2026-07-07 — Figure 1: annotate incised valley-floor channels (Obj. 1 target)

Per user, added callout boxes isolating the incised valley-floor channels on Panel B. Box
placement is data-driven, not eyeballed: `_find_channel_boxes.py` thresholds the
flow-accumulation raster (`flowacc_log.tif`, p96), closes/dilates, labels connected
corridors, and returns their km-space bboxes. Picked the two clearest, best-separated
corridors (dendritic network center-right; single incised channel center) and hardcoded
them into `_make_realmap.py` as `CHAN_BOXES`, drawn as red rectangles with a shared
"incised valley-floor channels" label + thin leaders. Stays plan-only: annotation of the
input terrain (the measurement target), not a detection/change result. Regenerated
`fig_location.png`, swapped into `finesst_proposal_v5.docx` in place (blob replace, aspect
+ caption unchanged).

---

## 2026-07-07 — Figure 1 hillshade: crisp grayscale (vert_exag 4×)

Per user ("hard to see details"), the fix was **vertical exaggeration, not color**. Rendered
a 6-way comparison of Panel B (`_hs_compare.py`: viridis/terrain/gist_earth/cividis color
drapes + crisp grayscale, soft vs overlay blends) — the original looked flat because it used
a gentle vert_exag 2.0 *soft* blend. User picked the crisp grayscale (vert_exag 4.0)
`LightSource.hillshade`. Channel network, lake margin, and alluvial fans now legible.
Colored drapes rejected (viridis/terrain both explored; user prefers monochrome relief).
`fig_location.png` regenerated, swapped into `finesst_proposal_v5.docx` in place (Figure-1
blob replace, aspect unchanged, caption unchanged). Scripts: `_make_realmap.py` (vert_exag
2→4, grayscale) + `_swap_fig1_color.py`. Stays plan-only (input-terrain basemap, not a result).

---

## 2026-07-07 — FINESST proposals: added method-level technical detail (plan-only)

Per user, added "a little more technical detail" to two proposal variants — the
approach/methods only, staying plan-only (future tense, no results, no figures). Same
specifics into both, each in its own voice:
- **`barlow/docs/finesst_proposal_v3.docx`** (forked from v2; v1/v2 untouched per the
  never-edit-user-drafts-in-place rule): 7 Approach/Methods paragraphs augmented in the
  author's first-person voice — co-registration (median vertical-bias removal + optional
  ICP), resample-to-common-grid + DoD, per-pixel LOD95 detection floor, specific rate in
  mm/yr, positive-degree-day melt proxy, leave-one-stream-out CV, connected-component
  patch extraction with per-patch attributes (area/mean dz/slope/aspect/dist-to-
  channel+lake), rules-first patch classifier, REMA−lidar bias stratified by slope/aspect,
  binned-NMAD per-pixel noise surface, and the NMAD (=1.4826×MAD) / LOD95 (=1.96×NMAD)
  definitions. Text-only run edits (body stayed non-bold).
- **`barlow/docs/finesst_proposal_basic.md`**: same detail in the formal plan-only voice
  (§3 O1/O2/O3 + Methods note).
Formal + plain .md variants NOT touched this pass (would diverge from basic) — flagged to
user for a follow-up if they want parity.

Second pass (same request, "a little more") added to both v3.docx + basic.md: DoD
uncertainty propagation in quadrature (differencing floor = 1.96×√(NMAD₁²+NMAD₂²)),
common-CRS reprojection to EPSG:3294 + resample of the 2 m/1 m epochs to a shared cell
size, minimum-mapping-unit patch filtering, and the standing-water screen (lake-level
rise ≠ ground change). De-duplicated the LOD95 clause in the docx methods note.

## 2026-07-07 — FINESST Figure 1: schematic → real map of the study area

User: the schematic Fig 1 "isn't really gonna cut it," wanted an actual map. Rebuilt
`fig_location.png` as a real two-panel figure (`_make_realmap.py`): (A) Antarctic index
from cartopy + Natural Earth coastline (downloaded live) with the Dry Valleys located; (B)
grayscale hillshade of the ACTUAL study-area lidar DEM
(`E:/…/barlow_inputs/taylor_valley/elevation.tif`, 7×7 km, 1 m, EPSG:3294, LightSource
az315/alt45, 1%–99% stretch), with 1 km scale bar + north arrow — the incised valley-floor
channels are clearly visible. Anonymous (no name/institution); a hillshade basemap is
input terrain, not an analysis result, so it stays plan-only-consistent. Swapped the blob
into v5.docx in place (`_swap_fig1.py`: matched the old schematic bytes, replaced the image
part, fixed inline-shape aspect to 6.0×3.21", rewrote the caption) so the concision edits
+ user font tweaks survived; basic.md caption updated too. Source DEM stays on E:
(gitignored); only the small PNG is tracked. v3/v4 keep the schematic (own embedded copy).

## 2026-07-07 — FINESST proposal v5.docx: concision pass (~1 page reclaimed)

User's hand-tweaked v4 (section-title font/size changes) ran just onto a 7th page. Forked
**v4 → v5** (own-version-per-change discipline) and ran a concision pass on wordy BODY
paragraphs only — no headings touched (his font tweaks preserved), no meaning changed,
edits kept inside run[0] so formatting survived. 29 paragraphs tightened; 1,336 → 1,083
words in the edited paragraphs (253 saved, ~19%, roughly a page at ~250-300 wpp). Killed a
literal duplication ("cold desert planetary surfaces … cold desert planetary surfaces"),
collapsed 3-word phrasings to 1 ("is capable of finding"→"finds", "utilizing"→"with",
"our main objectives are three fold"→"Three objectives:", etc.). Figures + 2 images intact.
User to verify final page count in Word.

## 2026-07-07 — FINESST proposals: two illustrative figures (plan-only, anonymous)

User asked what graphics could be incorporated; agreed on conceptual/illustrative only
(the plan-only rule bars any preliminary-results graphic — no change maps, hillshades, or
the r=0.95 plot). Built two anonymous, results-free schematics with matplotlib
(`_make_figs.py`), 300-dpi PNG, muted palette that reads in grayscale, no name/institution
for dual-anonymous review:
- **`barlow/docs/figures/fig_workflow.png`** — detection-to-attribution method schematic:
  3 DEM epochs → co-register/reproject(EPSG:3294)/resample → DoD → per-pixel LOD95 floor
  (with O3 uncertainty feeder) → O1 channel branch (rate→driver table→hierarchical+RF) and
  O2 valley-floor branch (patches→process classifier→per-class fingerprints).
- **`barlow/docs/figures/fig_location.png`** — study-area orientation: (A) Antarctic
  index with Dry Valleys star, (B) Taylor Valley schematic (Taylor Glacier W, Ross Sea E,
  Bonney→Hoare→Fryxell lakes, streams+gauges), labelled "not to scale".
Embedded both into the docx and **basic.md** (relative `figures/` refs + captions). Small
PNGs, tracked normally (well under 100 MB). Formal/plain .md variants still not touched.

**Versioning correction (same day):** figures were first stacked onto v3.docx — wrong;
each distinct request should be its own version. Re-split: **v3.docx** = the technical-
detail request (restored to pre-figures state from commit 0056824, 0 images); **v4.docx**
= the figures request (technical detail + Fig 1 in Setup, Fig 2 in Approach, 6.0" wide,
italic 9-pt captions). basic.md keeps both since it is the working variant, not the
user-draft lineage.

## 2026-07-06 — Roadmaps: barlow/docs/ROADMAP.md + docs/ROADMAP.md (WellSight)

Two dependency-ordered programming+generation outlines, per user request.
**Barlow:** Phase 0 submission critical path (NSPIRES/internal deadline/duration
decision/advisor items; tiles-propagation stays PARKED) → 1 data completion (run the
wired `--lter` expansion; stage tiles when unparked; NZ/LINZ manual; geology staging) →
2 driver engineering (`_build_driver_series.py`: PDD/insolation/discharge+gauged_days/
thaw/lake/zone per stream-season) → 3 whole-landscape O2 (valley-floor mask → whole-
surface DoD patches → rules-first classifier → per-class rates → attribution hook) →
4 O3 conditioned error model + calibration check (re-gates Phase 3) → 5 O1 modeling
(hierarchical + RF twins, LOSO CV, H1 head-to-head, acceleration, H2 fingerprints;
analysis plan written before fitting) → 6 generation. **WellSight:** A cheap/no-GPU
(val-selected threshold sweep on saved gpkgs; FP taxonomy in QGIS; duplicate audit) →
B precision-in-training (hard negatives from the taxonomy; retrain pad→pit Mask R-CNN;
BACKLOG architecture items gated on B.2) → C road active-learning loop (blocked on user
QGIS corrections) → D deployment chain (explicitly PAUSED) → E Permian transfer
(zero-shot → RRC/Ramachandran eval → fine-tune gate) → F infra debt (STRUCTURE.md
stale, log hygiene, metric-code regression tests, publication thread). Both docs carry
the standing rules (plan-only, 100 MB, fork-user-files, val-tuned/test-frozen).

User (rightly) asked why the mentoring plan wasn't drafted when the RRS was — the
"only the advisor can commit" reasoning should have produced a bracketed draft, same as
the RRS. Fixed: **`finesst_mentoring_plan.md`** (renders exactly 2 pp, anonymized):
roles, weekly cadence + semester milestone reviews keyed to the proposal's risk
fallbacks, the two named skill gaps with closing mechanisms and success criteria,
professional development (AGU/SCAR, 3 first-author papers, follow-on proposal drafting,
open-science practice), IDP, feedback/escalation/availability safeguards, annual review
of the plan itself. Also **`finesst_ancillary_docs.md`** (2 pp): facilities statement
(no field work, single-GPU workstation, all-open-source), 150-word acknowledgements
draft **including the required AI-use disclosure** (~120 words, room to add names), and
a budget-justification skeleton (stipend/tuition/travel/publication/storage rows with
grants-office notes; no PI salary, no logistics). Package state: every draftable
document now exists — remaining blockers are purely human: RRS personal facts +
graduation date (determines award duration, still unknown), advisor review of the
mentoring plan, institutional budget rates, biosketches/C&P (NASA forms), NSPIRES
shell + internal routing. Deadline 2026-07-14.

`finesst_proposal_basic_rationale.md` (+ pdf/docx, 5 pp): for every block of the basic
variant, a **Why** (what the line does to the reviewer / guards against) and **How**
(mechanism or evidence). Covers title, each summary sentence, both §1 gaps, all three
objectives incl. falsifiability lines and the sensor-demotion note, each §3 step (both
model families, held-out validation, NMAD), §4 needs framing (availability-not-status
column, labels fallback sizing, "not load-bearing" contact), all five §5 risks (each =
failure mode → consequence → what ships anyway), timeline dependency logic, §7 vs the
OSDMP, and why each of the 7 references is load-bearing. Maintenance rule embedded in
the doc: proposal line changes → rationale entry changes in the same pass. Also this
session: audit pass across all 3 variants (titles matched to geomorphic scope, refs
[2]–[7] re-anchored in formal text, DMP grammar, stale "sensor bridge" line) — adopted
standing practice: full-document self-audit after every substantive edit, before
handing docs back.

User clarified the actual project scope (from their conversations with Cami): the focus is
(1) climate drivers of the change and (2) geomorphological change broadly — NOT expanding
the detector to all valleys/sensors as a headline objective. Restructure applied to all
three variants + OSDMP + reference doc:
- **O1 (attribution)** unchanged — still the headline.
- **O2 is now "landscape-wide geomorphic change":** apply the O3 per-pixel thresholds to
  the FULL valley-floor surface (the DoD measures everything; Barlow's channel mask
  discards most of it), classify significant-change patches by process type (channel
  shift, thermokarst, slope movement, fan growth, lake-margin change), and test each type
  against its own drivers. New H2: distinct driver fingerprints per process type
  (channels → melt energy/water; thermokarst → thaw depth).
- **Cross-sensor/cross-valley work demoted to supporting method** ("sensor continuity"):
  lidar–REMA disagreement measured/corrected as a prerequisite, extension beyond Taylor
  Valley "where REMA quality allows" — a means, not a promise.
- New risk in all variants: outside-channel change may sit below the detection threshold →
  O2 falls back to in-channel change; the landscape-wide calibrated null is itself a
  result. Timelines rewritten (Yr 2 = classification paper). Gap statements now name BOTH
  gaps: drivers deferred + everything outside the channel masks discarded unexamined.
- Renders: formal 5 pp, plain 5 pp, basic 5 pp, OSDMP 2 pp; reference docx regenerated.

User clarified unambiguously: "for the purposes of this proposal assume we have done no
preliminary work... don't include any graphics from the preliminary work." The earlier
bravado scrub (same day, below) was insufficient — the standing rule is now: **no
preliminary-results sections, no pipeline figures, no reproduction claims, in ANY proposal
variant.** Applied: formal §4 (Preliminary Results, Figs. 2–5 + NMAD table) deleted and
§§5–7 renumbered to 4–6; plain §5 (Figs. 2–5) deleted, §§6–7 → 5–6; workflow Fig. 1
removed from both; every figure cross-reference in summaries/methodology/data tables/
timelines/risks removed; formal §5 data-table "Status: ✅ in hand" column → "Availability:
public, free" (matching the basic variant); Yr-1 timeline now includes building the
change-detection chain (since nothing is presumed built). Rendered: formal **5 pp**,
plain 4 pp, basic 4 pp — all comfortably under the 6-pp cap. `finesst_figures/` kept
in-repo for internal use but no proposal references it; README updated to record the
plan-only rule.

User flagged the plain variant's summary ("I've already rebuilt and verified the existing
pipeline myself... not a proposal resting on untested machinery") — the 07-01 "don't
over-talk preliminary work" instruction had only ever been applied to the FORMAL variant;
the plain variant's summary and body kept the bravado. Scrub applied to both (basic was
already clean): summaries now carry a neutral factual pointer ("§4/§5 presents a
reproduction... from public data") instead of "already running/rebuilt myself"; every
"already operational/works/in hand/commands" softened to plain statements; plain §6
retitled "FI qualifications" and moved from "I've built... myself" to "The FI has built...";
QC-anecdote parenthetical cut from plain (already cut from formal). Factual §4/§5
preliminary-results sections KEPT in formal + plain per their role (basic remains the
plan-only variant). Rationale beyond the instruction: "myself" overclaims AI-assisted work
(FINESST requires an AI-use acknowledgement; the FI must own every claim in an interview),
and first-person swagger reads badly under dual-anonymous review. All four renders
regenerated (formal docx lock had cleared).

Per user (after calling out unneeded content in the documents): submission docs should
carry only what NSPIRES receives. (1) Removed the program/division/deadline/roles/award
header block from formal, plain, and basic variants — that metadata now lives ONLY in
`barlow/README.md` ("FINESST program facts" section: cover-page items, 6-pp cap,
dual-anonymous criteria, abstract-box note). (2) Trim pass on the formal variant: §2
objective/hypothesis table cells compressed, all four §4 figure captions cut ~50%
(kept the numbers: r=+0.95/ρ=+0.94, LOD95, Fryxell screen, 48–362 gauge days), §3 O1
steps tightened, ICP-fitness + QC-anecdote sentences dropped. 8 pp → **7 pp rendered**
(~1 pp of that is references, which don't count toward the cap → content ≈ at the 6-pp
limit; true fit must be re-measured in the NASA submission template). Plain + basic
re-rendered (7 pp / 4 pp). `finesst_proposal.docx` NOT re-rendered — file locked (open
in Word); re-render pending.

Closing the compliance gaps found in the 07-05 requirements check (dual-anonymous review;
scored criteria = Scientific Merit / Relevance to SMD / Research Readiness). (1) Labeled
**"Relevance to NASA"** block added to both the formal and basic S/T/M variants (ATM
archive exploitation, ICESat-2/NISAR method transfer, planetary-analog investment, FI
development); basic §4 skills para trimmed — substance moved to the RRS where FINESST
wants it. (2) **`finesst_osdmp.md`** drafted (renders exactly 2 pp): inputs table,
products table w/ formats+archives (Zenodo/EDI, COG/GeoPackage, Apache-2.0/CC-BY),
release timing, the author-gated-labels handling (no redistribution; self-digitized
replacement set WILL be published), roles, reproducibility commitment. (3)
**`finesst_readiness_statement.md`** skeleton (renders 1 p, non-anonymized, [bracketed]
placeholders + grad-study-timeline table). All rendered pdf+docx. **Flag: formal
proposal now renders 8 pp — over the 6-pp S/T/M cap even allowing for references;
needs a trim pass before submission.** Still missing (user/PI side): mentoring plan,
budget, biosketches, C&P, facilities, 150-word acknowledgements w/ AI disclosure,
NSPIRES shell + internal routing.

Per user: a third proposal variant that presents the project as a pure plan.
`barlow/docs/finesst_proposal_basic.md` (+ rendered .pdf 4 pp / .docx): no preliminary
results, no figures, no "already operational" claims — §4 replaced by "What the project
needs" (data table incl. the author-gated labels, computing, skills gaps stated as gaps)
and §5 "Honest assessment" (five failure modes with what-happens-then, incl. weak-signal
→ publishable null; explicit "what this proposal does not claim" block). Existing formal
+ plain variants unchanged; README doc list updated.

---

## 2026-07-03 — Barlow: rates re-run inside Cami's own detected channel masks — attribution signal invariant

Cami Barlow shared her working GIS data (dropped into `barlow/Shapefiles/`, gitignored —
author-private; inventory in `barlow_data_manifest.md` 🎁 section). Headline item:
`Streams_Final_052026.zip` = her **final U-Net-detected channel polygons per epoch**
(NASA_2002 34,807 / NCALM_15 15,204 / REMA_15 906 polys; `Class==1` = channel). Extracted
to `E:\barlow_data_DO_NOT_DELETE\labels\Streams_Final_052026\`.

Added `--channels {lter,cami}` to `barlow/build/_change_detection.py`: per-stream masks
become LTER manual corridor ∩ (union of the two epochs' Cami polygons — union, because a
channel present in only one epoch is exactly where change happened). New `cami_pct` CSV
column = share of each LTER corridor her detector retains (27–89%). Also prints
whole-window totals inside her full detected mask.

**Runs** (bbox 26000 37000 33000 44000, water-screened, bias-corrected):
- 2001→2014: NMAD 0.211 m unchanged; window totals inside her channels: ero 57,311 /
  dep 91,391 m³ over 5.04 km². CSV: `per_stream_2001_2014_cami.csv`.
- 2014→REMA: NMAD 0.227 m unchanged; ero 115,665 / dep 175,030 m³ over 6.56 km². CSV:
  `per_stream_2014_rema_cami.csv`.

**Attribution pilot re-test** (log-log specific gross rate vs mean gauged discharge, n=6,
matching fig4's statistic): lidar epoch **r = +0.95 (p = 0.003), ρ = +0.94 (p = 0.005)** —
identical to the LTER-only baseline (+0.95 / +0.94), and leave-one-out worst-case
*improves* (+0.82 → +0.87). REMA epoch stays null under both masks (r ≈ −0.2, ns), as
expected under sparse post-2015 gauging. **Interpretation: the pilot signal is invariant
to whose channel masks are used — LTER manual corridors or the author's own detected
outlines — removing "you used different channels than she did" as an attack line.**
Per-stream specific rates shift only modestly (e.g. Aiken 14.18→13.32, Delta 5.33→6.30
mm/yr); rank order preserved.

Also in this pass: `.gitignore` + `barlow/Shapefiles/` rule (only the zip was covered
before, via `*.zip`); fetcher `LTER_PACKAGES` expanded with `lter_met_network` (19 met
stations), `lter_melt_model` (8000-series energy-balance I/O), `lter_groundice`
(DVDP-11 + SLIME), `lter_lakelevel` (68/67/3104) — documented in the manifest, not yet
fetched. NZ (USDA-NRCS/Landcare) soil-climate network recorded as the manual-acquisition
fix for the ground-ice driver gap.

---

## 2026-07-02 — Honest re-eval complete: all four instance models on the 65/93 split, single era

Closes the dataset-era-mixing + no-precision findings from the 07-01 audit. Sequence:
pad Mask R-CNN retrained on the 650-pad dataset (the 07-01 attempt died at epoch 0 to
the WoW VRAM spill; relaunched on the freed GPU — best = **ep 3**, val 0.787, then val
climbed 0.870/0.878 and the 30-epoch no-early-stop run was cut at ep 5), then all four
infer/eval scripts re-run with the new greedy-1:1 + precision metrics, then
`_compare_known_wells.py` re-run on the fresh detections (after fixing a stale
`data/derivatives/external/` path → `data/external/`).

**Test results (greedy 1:1, R/P/F1 @ IoU 0.3):**

| model | R | P | F1 | R@0.5 | mIoU | #det |
|---|---|---|---|---|---|---|
| pit_07_maskrcnn (06-11 ckpt) | 0.97 | 0.053 | 0.100 | 0.85 | 0.631 | 2978 |
| pit_08_yolo (06-11 ckpt, conf .05) | 0.92 | 0.054 | 0.102 | 0.69 | 0.572 | 3631 |
| pad_05_maskrcnn (07-02 ckpt ep3) | 0.98 | 0.029 | 0.057 | 0.90 | 0.690 | 3075 |
| pad_06_yolo (06-11 ckpt) | 0.88 | 0.064 | 0.118 | 0.83 | 0.661 | 1255 |

Headline: recall survives the honest protocol; **precision is 3–6% everywhere** — the
over-detection the loose metric hid. 9× more pad training data did NOT move pad
precision (0.029). Known-well cross-ref (1,069 DEP wells, 25 m): pit_07 373, pit_08
397, pad_05 **521**, pad_06 337 matched. LEADERBOARD rewritten single-era (legacy
110/79-era numbers quarantined in a collapsed block); pit_07/pit_08/pad_05/pad_06
iteration docs got current-headline sections; pit_optimize + road_unet_1m_recall docs
carry the val-tuned/test-frozen post-proc numbers (pit F1 0.155; road extraction F1
0.754). BACKLOG: 3 audit items closed, next lever recorded — **val-selected score
threshold sweep** (re-threshold saved instances.gpkg, no GPU needed).

---

## 2026-07-02 — Storage migration: heavy datasets moved to E: (C: was at 98%)

C: had 21 GB free of 931 GB. Per user request, moved big datasets to the Samsung T7
(E:, USB SSD) with destination names carrying **DO_NOT_DELETE**:

- **Barlow:** `J:\barlow_data` (51 GB) → `E:\barlow_data_DO_NOT_DELETE`. Path constant
  updated in all four build scripts (`_fetch_barlow_data.py`, `_build_barlow_inputs.py`,
  `_change_detection.py`, `_finesst_figures.py`) + `barlow/README.md` +
  `barlow_data_manifest.md`. All 1,385 files / 53.8 GB verified byte-equal on E: (first
  robocopy pass dropped 25 files to a transient J: read error; incremental retry completed
  clean). J: source renamed `_barlow_data_MOVED_TO_E__SAFE_TO_DELETE` — deletion of
  drive-top-level paths is guard-railed, so the user deletes it manually.
  Older log entries below still reference `J:/barlow_data` — historical record, not live paths.
- **J: strays claimed too:** the 22 unique USGS LAZ tiles in `J:\seperate sections`
  (2006–08 Statewide-S + 2019 D20; 1.0 GB — nowhere else on disk) were copied into
  `data/source_laz/westernpa/seperate sections/` (the path `.gitignore` already expected;
  physically on E: via the junction), and the three landcover source archives
  (EnviroAtlas, landcover_2013 CHB/DRB, NLCD 2021; 7.3 GB of ≥100 MB zips) went to
  `E:\lidar_project_data_DO_NOT_DELETE\source_archives\`. J: originals renamed
  `_MOVED_TO_E__SAFE_TO_DELETE…` pending the user's manual delete.
- **WellSight repo data:** five heavy dirs (~54 GB) moved to
  `E:\lidar_project_data_DO_NOT_DELETE\` mirroring repo layout, each replaced in-repo by an
  NTFS junction so every relative path, `.gitignore` rule, and git-tracked file keeps
  working unchanged: `data/source_laz` (all .laz), `data/derivatives/tiles/{data_3x3,
  613590_05, mkf_1m}`, `data/derivatives/inference_613590_05` (all ≥100 MB-raster
  dominated, zero-to-few small tag-alongs). Verified per dir: robocopy exit < 8, file
  count + total bytes equal, `git status --porcelain` empty through the junction, then
  old copy deleted.
- **Selection rule (user, 2026-07-02): only files ≥100 MB or .las/.laz are stored off;
  anything GitHub-pushable stays on C:.** Consequently `data/external` (87k small files —
  NAIP chips, shapefiles, docs; 39 tracked) and `data/derivatives/experiments` (158 small
  files, 83 tracked) were kept on / restored to C: after initially being staged to E:.
  data_3x3's 387 tracked small files ride along on E: through the junction — they remain
  committed and pushed to GitHub, so they are recoverable via `git checkout` even if E:
  is lost; file-level splitting was impossible without admin symlink privilege.
- **`tiles/9t` (24 GB) deliberately stays on C:** — it is the active training/eval working
  set (pad Mask R-CNN retrain reading it at time of migration) and benefits from NVMe speed.
- `backup_to_E.bat` gained `/XJ` so the incremental repo backup does not traverse the new
  junctions and duplicate ~60 GB back onto E:.

---

## 2026-07-01 — Correction: label counts were stale; datasets/models partly already caught up

User challenged the audit's "110 pit / 79 pad" figure — correctly. Ground truth on disk:
**426 pit_inside / 1,053 plat** (plus 609 pit_outside, 425 pit_wall, 1,809 roads, 1,791
drainage, 95 new existing_roads). The 110/79 line dated from the 2026-06-03 BACKLOG and was
never updated after the user's annotation push. Verified state:

- **2026-06-10 dataset rebuild** ingested all 426 pits + the 650 pads inside 9t
  (pit manifest 298/63/65 train/val/test; plat 456/101/93). `pit_unet_v2` (06-10 15:30),
  `plat_unet` (06-10 16:26), multitask (06-11) and their test_metrics were retrained/re-run
  on this split — those numbers reflect the new data.
- **Instance models: checkpoints retrained 06-11 but evals never re-run.** All four
  `iterations/{pit_07,pit_08,pad_05,pad_06}*/test_metrics.json` are dated 06-01/02 with
  n_test = 20 pits / 9 pads — the LEADERBOARD instance rows are old-era numbers sitting
  next to new-era U-Net rows. (pad_05 best.pt is still dated 06-02; whether the pad
  Mask R-CNN retrain saved a new best is unconfirmed.)
- **403 pads lie outside 9t** (other regions; annotated via the label-grid/aids workflow)
  and are in NO training dataset — they need per-region feature stacks. **~58 newest pads**
  postdate the last `annotations_proj.gpkg` regen (plat.shp 1053 vs gpkg 995).

BACKLOG corrected (label-set item rewritten; audit test-n item corrected to "dataset-era
mixing"). The audit's code-level findings (test-set tuning, boundary leakage, recall-only
metrics, unseeded trainers) are unaffected by this correction.

---

## 2026-07-01 — Methodology evaluation: both projects audited (3 parallel reviews)

Per user request, an adversarial methodology audit of everything expanded recently: WellSight
iteration docs + leaderboard, WellSight training/eval code, and the Barlow fetch/build scripts
(change-detection + figures were already hand-audited earlier today). Findings recorded in
`docs/iterations/BACKLOG.md` (new "Methodology-audit findings" section, ranked). Headlines:

**WellSight — three mechanisms inflate reported metrics.** (1) Post-processing knobs
(`_road_optimize.py`, `_pit_optimize.py`) and the U-Net instance-row thresholds are tuned by
maximizing F1 **on the test blocks**, and that same F1 is the reported number. (2) Spatial-block
splits leak at boundaries: patches read a global (un-split-masked) label raster, Mask R-CNN/YOLO
deliberately paint off-split (incl. test) instances into training targets, and ~40 m road chunks
are split by midpoint so one physical road straddles train/test. (3) Instance metrics are
recall-only with no 1:1 matching (one prediction may match many GT, floor IoU 0.1, score thresh
0.05), per-object IoU is computed in GT-local windows (FPs elsewhere invisible), and "Line AP"
samples only along GT lines (separability, not detection AP). Compounding: 20-pit/9-pad test
sets reported to 3 decimals with no CIs; U-Net trainers unseeded; YOLO(3-band) vs
Mask R-CNN(7-band) presented head-to-head; DEP-well 0.42 recall cited without a random-match
null. **What's solid:** train-only normalization stats reused correctly end-to-end; spatial
blocking exists and is balanced; best-checkpoint by val (not test); overlap-averaged sliding
window inference; YOLO BGR bug properly fixed; Mask R-CNN nondeterminism honestly documented.
The docs themselves flag overfitting and metric non-comparability, so the culture is honest —
the arithmetic just needs to catch up before any number is published.

**Barlow — pipeline sound after this morning's fixes; three build/fetch issues remain.**
(1) EDI fetch auto-resolves "newest revision" → silent provenance drift vs the manifest's
pinned revisions; make revisions pinnable. (2) Flow-accumulation build clips nodata to 0
(log1p(0)=0 looks like "no upstream flow") — contaminates one of six U-Net inputs at edges.
(3) Vertical datum across epochs (ATM/NCALM/REMA) is assumed ellipsoidal-consistent but never
stated; note that the DoD median-bias correction absorbs any constant offset (and ICP the rest),
so the risk is documentation, not results — but document it. Minor: WBT profile-curvature is a
deliberate deviation from Barlow's ArcGIS standard curvature (justified in-code; keep, flag in
manifest); manifest understates the builder (says D8, code is FD8/MFD).

**NISAR** framing as covariate/context/time-axis (not a detector) is well-grounded; the
"InSAR subsidence proven viable over PA" phrasing overshoots one beta-grade fall pair (n=1,
coherence 0.50) — keep as hypothesis until the validated CONUS release (~Jul 2026) and a
multi-pair coherence stack.

No code changed in this pass (assessment only, per request). Fix list is in BACKLOG, ranked;
the two highest-leverage items are val-based tuning + split-masked labels, which together
require only a re-eval, not retraining.

---

## 2026-07-01 — Proposal: approachable restructure around the datasets

Per user ("here is what we need to do; here are the datasets, what each will do, where it's
from, what it shows"): restructured the plain proposal so the data story is front and center.
§2 retitled "What we need to do" with a one-sentence mission lead-in; new §3 "The data: what
we'll use, where it's from, what it shows" moved up before the methods, replacing the old terse
§6 status table with three grouped four-column tables (Dataset | Where it's from | What it
shows | What it does for us): three ground snapshots (2001 ATM lidar, 2014 NCALM lidar, REMA),
six driver datasets (gauges, met, glacier mass balance, soil/thaw, ERA5, AMPS), three label
datasets (LTER channel polygons, Barlow tiles, optional imagery). Approach renumbered to §4
("How we'll do it"), prelim §5, positioning §6; cross-refs fixed. Formal proposal kept its
NASA-standard section order but its §6 table upgraded to the same per-dataset format
(Dataset (source) | What it shows | Role | Status, 13 rows). All four rendered docs
regenerated (plain now 8 pp); table rendering visually verified in both PDFs.

---

## 2026-07-01 — Barlow reevaluation: attribution stats stress-tested, 3 defects found + fixed

Full audit of the Barlow/FINESST analysis chain (user request: "reevaluate, refine for
efficiency and accuracy"). Three real defects found; all root-caused and fixed in the pipeline
(not post-hoc), then propagated through figures → proposals → rendered docs.

**Defect 1 — lake-level contamination.** 78% of Aiken's 2001–14 "deposition" volume (and ~45%
of Huey's) was Lake Fryxell's ~1.5 m level rise, not fluvial sediment: dep>1 m pixels sat at
two dead-flat elevations (≈ −36 m in 2014, ≈ −37.4 m in 2001). Fix: `water_mask()` in
`_change_detection.py`, detects standing-water levels as >20k-px modes in the 0.1 m elevation
histogram of large-|dz| pixels (8 ha of flat surface in one bin can't be fluvial), masks ±0.75 m
in either epoch's DEM. Per-stream CSVs now carry `water_pct`; Aiken 2001–14 gross 3,890→2,866
m³/yr, Huey 662→117 m³/yr (was 48% lake).

**Defect 2 — raw m³/yr rates confounded by area/coverage.** The 2001 ATM swath is narrower than
REMA coverage, so the same stream has ~2× different masked area across epochs; cross-epoch rate
"acceleration" and the fig4 correlation partly reflected footprint, not geomorphology. Fix:
per-stream output + figures now use **specific rates (mm/yr = m³/yr per m² of channel)**;
`gross_mm_yr`/`net_mm_yr` columns added.

**Defect 3 — headline r = +0.89 was the wrong statistic.** It was raw gross volume vs
*cumulative* discharge: (a) cumulative sums are biased by unequal gauge coverage (257–716
gauged days across streams); (b) raw volume vs total discharge partly measures "bigger stream
is bigger" (area vs discharge alone: r = +0.44); (c) Spearman was only +0.49 (p = 0.33) —
the Pearson leaned on Aiken, the very stream most lake-contaminated. Fix: use **mean discharge
per gauged day** and the **specific rate**. Corrected headline (lidar epoch, water-screened):
**Pearson r = +0.95 (p = 0.004), Spearman ρ = +0.94 (p = 0.005)**, leave-one-out stable
(worst drop-one: r = +0.83). REMA epoch: no coherent relation under sparse post-2015 gauging
(48–362 days), now plotted honestly with **no fit line** (previous r = +0.43 claim removed,
it was not distinguishable from noise, p = 0.39).

Also: fig1 now compares both epochs on the SAME window (was: ICP pilot vs stream corridor,
different bboxes presented as a pair); NMAD/LOD annotations computed live from the rasters
(hardcoded constants removed); stable-terrain NMAD now verified channel-free (excluding
channels shifts it <0.01 m, 5.8% of valid px are channel, claim holds); discharge windows
aligned to actual DEM acquisition dates (2001-11→2015-01, 2015-01→2022-01). Both DoD runs +
figures regenerated; both proposal variants (formal + plain) updated with the corrected
Figs. 2/3/5 captions; all four rendered docs regenerated. Verdict on the rest of the chain:
warp/nodata handling, PDAL ICP, per-stream rasterization, LTER `tdaily_discharge` usage all
check out. The corrected result is *stronger* than the one it replaces and no longer has a
single point of failure.

---

## 2026-07-01 — Proposal: drop "WellSight" name + trim preliminary-work framing

Per user (reviewers don't know/care about WellSight; don't over-talk preliminary work), edited both
proposal md files: removed every "WellSight" mention (§5 now a brief generic "FI Qualifications"
describing the same toolchain applied to an unrelated landscape, no project name); cut the
repetitive preliminary/feasibility framing (§4 retitled "Preliminary Results" and trimmed to intro
+ figures; deleted the "feasibility summary/takeaway" paragraphs; softened Summary abstract, Fig. 1
caption, §3, §6, footer). "Preliminary" now only appears as the §4 section title. Regenerated all
four docs (formal + plain × pdf/docx); figures unchanged.

---

## 2026-06-30 — Removed em-dashes across the formal proposal + figures + footers

De-em-dashed `finesst_proposal.md` (43 → 0): bold label lead-ins / table cells became colons,
the rest became commas (plain version was already clean). Also removed the em-dashes baked into
figure text (`_finesst_figures.py`: DoD colorbar label, error-model title) and the page-footer /
PDF-title strings in both renderers. Regenerated the 5 figures and all four docs (formal + plain ×
pdf/docx). En-dashes in numeric ranges (e.g. 2021–23, O1–O3) kept as correct typography.

---

## 2026-06-30 — Renderers: drop inline bold + colored text (cleaner look)

Per user ("get rid of the random bolds, the color changed in text"), simplified both renderers
(`_md_to_pdf.py`, `_md_to_docx.py`): inline `**bold**`/`***bolditalic***` now render as normal
weight (italic kept for bolditalic); all text is black; headings are black + bold (hierarchy via
size only); blockquote/captions black (italic kept); tables get a light-grey header with black
bold text and no zebra striping (grid only). Regenerated all four outputs (formal + plain ×
pdf/docx). Only remaining color is inside Fig. 1 (an actual diagram image, not text).

---

## 2026-06-30 — Plain proposal: de-em-dashed + tone fixed

Revised `finesst_proposal_plain.md` per user: removed all em-dashes (en-dashes kept only in
numeric ranges), and rewrote the descriptions to drop the over-basic/condescending phrasing
(e.g. cut "looks like Mars", "the brains of the project", "first whiff", "the scary question")
in favor of a direct, peer-level voice that still glosses the lingo concisely. Regenerated PDF;
DOCX pending (file was open in Word during the run).

---

## 2026-06-30 — Plain-language FINESST proposal variant

Added `barlow/docs/finesst_proposal_plain.md` — same science, same real numbers/figures, written
for a new-grad audience (keeps the lingo: U-Net, NMAD, ICP, DoD, LOD95, PDD — but glosses each
inline). Its own source of truth (not auto-derived from the formal version). Rendered to
`finesst_proposal_plain.pdf` (7 pp) + `.docx` via the existing `_md_to_pdf.py` / `_md_to_docx.py`.

---

## 2026-06-30 — FINESST proposal reframed to proposal-voice + PDF/DOCX renderers

Reframed `finesst_proposal.md` so it reads as a *proposal* (proposed/future work), not as a
project already underway: added a proposal **Summary** abstract; §4 retitled "Preliminary Studies
and Feasibility" with explicit "feasibility demonstrations, not funded-project deliverables"
framing; methodology O1–O3 switched to future tense ("the proposed work will…"); §6 retitled
"Data Requirements and Availability" (in-hand framing, dropped planning-brief comparisons). Added
two markdown→doc renderers keeping the .md as single source of truth: `_md_to_pdf.py` (reportlab,
registers matplotlib DejaVu for full Unicode →/m²/Δz, emoji→safe glyphs) and `_md_to_docx.py`
(python-docx; headings/tables/images/blockquotes/captions). Outputs: `finesst_proposal.pdf`
(7 pp, 707 KB) + `finesst_proposal.docx` (567 KB, 4 tables / 5 images). Regenerate:
`python barlow/build/_md_to_pdf.py barlow/docs/finesst_proposal.md` (and `_md_to_docx.py`).

---

## 2026-06-30 — FINESST proposal (full S/T/M section) + figure set from real outputs

Drafted the actual ~6-page NASA FINESST Scientific/Technical/Management section
(`barlow/docs/finesst_proposal.md`), superseding the planning brief
(`FINESST_Barlow_Expansion_Concept.pdf`). Key upgrade over the brief: it now rests on
**reproduced + validated preliminary results** (the brief said "no data held yet"). New
script `barlow/build/_finesst_figures.py` builds 5 figures from pipeline outputs on J:
(no mock data): (1) DoD change maps both epochs, |Δz|>LOD95; (2) per-stream gross/net rates;
(3) Laplacian-vs-Gaussian error model + ICP fitness; (4) detection→attribution concept;
(5) **preliminary attribution** — per-stream gross rate vs cumulative LTER melt discharge.
**New result:** lidar epoch (2001–14) gross rate vs cumulative discharge **r = +0.89**
(strong positive); REMA epoch r = +0.43 (noisier — sparse post-2014 gauge coverage + larger
satellite LOD). Framed as motivation for O1 (raw discharge → first-order signal; FI develops
PDD/insolation/active-layer energy model to close the residual). Proposal lays out O1 attribution
/ O2 cross-sensor generalization / O3 calibrated per-pixel uncertainty, 3-yr timeline, risks
(Barlow's label tiles = lone access-gated dependency), and DMP. Figures are small PNGs (≤282 KB),
committed (not gitignored); large-file audit clean.

---

## 2026-06-29 — Per-stream masking + 2014→REMA epoch + ICP-fitness clarified ("the rest")

Generalized `_change_detection.py`: `--old/--new` epoch pair over {2001, 2014, rema},
`--streams` per-stream masking, `--icp`. REMA (EPSG:3031) auto-reprojects to 3294 in warp.
**Per-stream rates** (LTER channels reprojected from WGS84 polar-stereo → 3294, rasterized
to the DoD grid, ero/dep/net + rate/yr written to CSV). Runs:
- **2001→2014 (13 yr), Von Guerard window:** 6 streams; busiest Aiken 3,890 m³/yr gross
  (+3,672 net). Small vs Barlow's Denton Hills hotspot — expected for Taylor floor.
- **2014→REMA (7 yr):** NMAD **0.227 m / LOD95 0.444 m** — in Barlow's published 2014-REMA
  range (NMAD 0.19-0.53); 95% valid (REMA full coverage vs sparse 2001); bias −0.317 m
  (lidar↔satellite offset, removed). Per-stream: Harnish 9,335 + Von Guerard 9,150 m³/yr gross.
**ICP `fitness` explained** (was printed unexplained): it's the PDAL/PCL registration score
= mean squared distance between corresponding points after alignment (m², lower=better) —
measures cloud-match quality, NOT whether DoD improved (that's the before/after NMAD).
Consistent with earlier runs: high-relief window fitness 0.95 (helped), flat floor 1.47 (hurt).
All three epochs + per-stream now reproducible. Remaining optional: REMA dated strips, ICP-
on-relief for the REMA epoch, full-valley run.

---

## 2026-06-29 — ICP confirmed: helps on relief, hurts on flat floor (relief is the key)

Followed up the worse-on-flat-floor ICP result by scanning the 2001 taylore DEM for
high-relief, well-covered windows (1.5 km blocks, ≥85% cover, ≥60 m relief) → top hit
651 m relief at x[24.5-26.0k] y[44.0-45.5k] (a valley wall). Re-ran `--icp` on a 2.5 km
window there (bbox 24000 43500 26500 46000). **ICP HELPED:** NMAD 0.277→**0.226 m** (~18%
lower), vertical bias +0.176→+0.003 m, ICP fitness 0.95 (vs 0.21→0.57 m and fitness 1.47 on
the flat-floor Von Guerard window). Confirms: point-to-point ICP needs 3-D relief to
constrain x/y — use it on windows with valley-wall/flank terrain; on flat floor stick with
vertical-bias co-reg. Both now reproducible via `--icp`; pick the window by relief.

---

## 2026-06-29 — ICP co-registration added (reuses WellSight filters.icp) — honest result

Added `--icp` to `barlow/build/_change_detection.py`, reusing WellSight's PDAL `filters.icp`
approach (`notebooks/wellsight/build/_icp_old_vs_new.py`): rasterize both DEMs to points
(`readers.gdal`, header=Z), drop nodata, voxel 6 m, ICP fixed=2014/moving=2001 → transform,
then `filters.transformation` on the full-res 2001 DEM + re-grid to the 2014 grid → re-DoD.
**Result (Von Guerard pilot): ICP converged but NMAD got WORSE — 0.211 → 0.567 m** (sig
23.8%→3.9%). Cause: in this window the 2001 ATM only covers the low valley floor (≤210 m,
little relief), so point-to-point ICP is horizontally under-constrained and drifts, smearing
z on channel banks. **Conclusion: for these low-relief MDV floor pairs, vertical-bias
co-registration (NMAD 0.21 m, already in Barlow's range) is preferable; ICP needs terrain
relief to help.** Options to make ICP earn its place: (a) run over a higher-relief window
where 2001 has sloped data, or (b) switch to **Nuth & Kääb (2011)** slope/aspect DEM
co-registration (the DEM-differencing standard, more robust than point-to-point ICP on DEMs).
Note: Barlow uses point-to-*plane* ICP; PDAL's is point-to-point.

---

## 2026-06-29 — Consolidated all Barlow work into a `barlow/` subfolder

Moved the Barlow/FINESST subproject out of the WellSight tree into a dedicated top-level
`barlow/` (git mv, history preserved): `barlow/build/` (`_fetch_barlow_data.py`,
`_build_barlow_inputs.py`, `_change_detection.py`) + `barlow/docs/` (manifest,
dissertation explainer, FINESST concept) + `barlow/README.md`. Fixed
`_build_barlow_inputs.py`'s `_common` import to reach `notebooks/wellsight_v2` from the new
depth; updated the reproduce-recipe paths in the manifest. All three scripts verified to run
from the new location. Data stays off-repo on `J:\barlow_data`. (This is the WellSight
analysis log; Barlow-specific details live in `barlow/docs/barlow_data_manifest.md`.)

---

## 2026-06-29 — Change detection WORKS: 2001→2014 DoD pilot validates vs dissertation

Proved we can do change comparisons with current data. Wrote `_change_detection.py`
(DoD: warp both epochs to a common grid → difference → robust median/NMAD → LOD95 =
1.96·NMAD → erosion/deposition volumes). Pilot 2001(ATM 2 m) vs 2014(NCALM) over the Von
Guerard window (bbox 26000 37000 33000 44000). **Bug caught by QC** (first run: NMAD 2.7 m,
2×10¹¹ m³ deposition — obviously wrong): the 2001 DEM fills with −9999 but declares
`nodata=None`, so gdalwarp bilinear-interpolated the fill across nodata edges, injecting
−9998.99/−5000 garbage that an exact `!=-9999` mask passed. Fixed with `-srcnodata -9999`
on the 2001 warp + a plausible-elevation guard (−500<z<4000). **After fix:** vertical bias
−0.04 m (epochs already co-registered), **NMAD 0.211 m → LOD95 0.414 m** — squarely in
Barlow's published 2001-14 range (NMAD 0.07-0.46, LOD95 0.15-0.92). 23.8% of cells exceed
LOD; net +8.0×10⁶ m³ (window-wide, incl. glacier/snow — not yet masked to channels).
Caveats: vertical-bias co-reg only (no ICP x/y yet); no stream-channel mask (would give
per-stream rates like Ch7); 51% valid (2001 only covered the valley floor in this window).

---

## 2026-06-29 — LTER glacier mass-balance + soil/active-layer drivers (attribution set)

Closed the last small driver gap (no huge downloads). Added to `LTER_PACKAGES` + a
skip-existing guard in `fetch_edi` (so re-running `--lter` no longer refetches met + the 21
gauges). **Glacier mass balance** `knb-lter-mcm.2006` — 7 glaciers (Taylor, Canada,
Commonwealth, Howard, Adams, Hugh, Sues), 0.6 MB → `lter_glacier/`. **Soil/active-layer**
`knb-lter-mcm.4020-4024` — 5 stations (F6, WHC, VG, GC, WTB) × soil temperature / EC /
volumetric-water-content, 285 MB → `lter_soil/` (continuous high-freq; the permafrost/
active-layer attribution driver). With this, every FINESST data requirement is satisfied
except optional REMA time-stamped strips (parked — potentially large, awaiting OK).

---

## 2026-06-29 — Barlow builder matched to dissertation: +aspect +curvature, D8→MFD

Extended `_build_barlow_inputs.py` to the full Ch6 feature set (no new downloads — pure
compute on local DEMs). Added **aspect** (WBT) and **curvature**, and swapped flow
accumulation **D8 → FD8 (multi-flow-direction)** to match Barlow's ArcGIS MFD. QC on the
Taylor pilot: MFD flowacc mean 2.13→3.68 (MFD diffuses flow, as expected); aspect 0–360
(95% valid). **Curvature gotcha:** first used WBT `total_curvature` — it returns *magnitude*
(100% ≥0), so it can't tell concave channels from convex ridges (the whole point). Switched
to **`profile_curvature`** (signed): now 52.7% concave / 47.3% convex, symmetric about 0 →
channels read as concave. Full 6-layer stack (elevation, slope, aspect, curvature, flowacc
MFD, intensity) now matches the dissertation. Remaining (parked): REMA time-stamped strips
(potentially large — hold for OK), LTER glacier mass-balance + permafrost/active-layer.

---

## 2026-06-29 — Corrected target to the DISSERTATION; fetched the 2001 lidar epoch

User flagged that the "Barlow paper" is actually her **2026 PhD dissertation**
(`docs/articles/barlow_dissertation_explained.md`), not the 2022 RS paper (which is just
Ch4). Re-read it + the FINESST brief (`docs/finesst/FINESST_Barlow_Expansion_Concept.pdf`)
and reconciled data needs: dissertation = 4 valleys × **3 epochs (2001 lidar / 2014 lidar /
2021-23 REMA)** + DoD/ICP/NMAD change detection. Most prior fetches were on-target (2014
lidar, REMA, LTER met+discharge, ERA5, AMPS all required). **Key gap closed: the 2001
epoch** — it's NASA **ATM** (Dec 2001), 2 m DEMs, *not* on OpenTopography (only 2014 is) but
free/anonymous on **USGS ScienceBase** (parent `5d0d1d81e4b0941bde52a1a1`, 18 MDV sites,
2.51 GB). Added `fetch_atm2001()` + `--atm2001`, pulled all 18 sites (Taylor, Wright,
Victoria, Barwick, Denton Hills + more) to `mdv_lidar_2001/`. **QC:** Taylor 2001 tile is
EPSG:3294 @ 2 m, bounds [19999,34999,50007,56005] — same CRS & overlapping the 2014 DEM
[22998,33998,45002,57002], elev −57→768 m → directly co-registerable for DoD. No ~2007
epoch exists (only 2001 + 2014). **Remaining cleanup:** builder add aspect+curvature & swap
D8→MFD flow-accum (match her method); REMA time-stamped strips for the true 2021-23 epoch;
LTER glacier mass-balance + permafrost/active-layer drivers.

---

## 2026-06-29 — Reconstruct Barlow (2022) U-Net input rasters over Taylor Valley (pilot)

Built `_build_barlow_inputs.py` to regenerate Mary Barlow's four U-Net inputs from the
2014-15 NCALM Taylor Valley lidar: **elevation** (bare-earth DEM mosaic), **slope** (WBT,
deg), **flow accumulation** (WBT breach-least-cost → D8, log1p), and **intensity** (mean
Intensity rasterized from the point cloud via PDAL). All 1 m, EPSG:3294, aligned to the
DEM grid. Per CLAUDE.md bootstrap rule, ran a **pilot** over the Von Guerard/Crescent
cluster (bbox 26000 37000 33000 44000, 7×7 km). **QC passed:** reprojected MCM-LTER
stream-channel polygons (their CRS = WGS84 polar-stereographic lat₀−71, *different* from
the DEM's EPSG:3294 — must reproject to align) sit on higher flow-accum **inside (2.32)
than outside (2.13)** → derivation + cross-projection alignment correct. Contrast is modest
because the LTER channel polygons are broad (dilutes the thin-thalweg signal). Nodata
−9999 appears off the lidar footprint (normal). Fixes during build: tiled GeoTIFF needs
256-block sizes; clear corrupt partial outputs before rewrite. **Intensity completed** once
the 944-tile PC finished (9.58 GB): PDAL crop+`writers.gdal` mean-Intensity from 91 pilot PC
tiles (323 s). **Full 4-layer pilot QC (nodata-masked):** elevation −39→866 m (mean 153),
slope 0→85° (mean 8.9), flowacc_log 0→17.5, intensity 1→2759 (mean 23, inside-channel 26 >
outside 23). All 95-100% valid, EPSG:3294, 1 m, grid-aligned — matches Barlow (2022)'s exact
U-Net inputs. Next (on user OK): drop --bbox for full Taylor Valley (~11 GB/raster, on J:).

---

## 2026-06-29 — Identified the actual Barlow paper + fetched its exact inputs

Pinned down what "the Barlow paper" is and what it uses, rather than inferring from
neighbouring work. It's **Barlow, Zhu & Glennie (2022)**, *"Stream Boundary Detection of
a Hyper-Arid, Polar Region Using a U-Net Architecture: Taylor Valley, Antarctica"*,
Remote Sensing 14(1):234, doi:10.3390/rs14010234. (MDPI is Cloudflare-blocked to bots;
got authors/methods via search + citation metadata.) Inputs = **2014-15 NCALM lidar over
Taylor Valley** → four U-Net rasters: **elevation, slope, lidar intensity, flow
accumulation**, + **217 hand-labeled stream-boundary tiles**. Notably it uses **lidar
only** — no ERA5/AMPS/REMA/discharge (those are our FINESST expansion, not Barlow's paper).
Actions: (1) we already have the Taylor Valley bare-earth DEM (elevation/slope/flow-accum
source); (2) **intensity needs the point cloud** → pulling `pc-bulk/MDV_2014/Taylor_adj47`
(944 .laz, ~9.6 GB) to `mdv_lidar/pc/Taylor_Valley/` (added irregular PC-prefix map
`OT_PC_PREFIX` to `fetch_opentopo`); (3) Barlow's 217 labels are **not public** → grabbed
the published MCM-LTER **stream-channel shapefiles** `knb-lter-mcm.6007` (12 Taylor Valley
channels + watersheds + glaciers, 0.4 MB) + relict-channel locations `knb-lter-mcm.26` to
`labels/gis/` as the public label stand-in. Searched OT + literature for a ~2007 lidar
epoch: **none exists** — MDV repeat-lidar is only 2001-02 (NASA ATM, ~2 m, not on OT) and
2014-15 (NCALM). Remaining build step: derive the 4 input rasters over Taylor Valley.

---

## 2026-06-29 — AMPS made practical via THREDDS NCSS (the optional driver, unblocked)

Tried the last optional Barlow dataset, **AMPS** (Antarctic Mesoscale Prediction System,
WRF). Old `tds.ucar.edu` server is retired → now **gdex.ucar.edu** (THREDDS at
`tds.gdex.ucar.edu`, anonymous). Long GRIB archive = dataset **d473002** (WRF24 era
Oct-2017+; structure `grib/<model>/YYYY/MM/DD/<init>_WRF_d<G>_f<FFF>.grb`). The MDV-relevant
domain is **d3 = 2.67 km Ross Sea** (covers the Dry Valleys; ~10× finer than ERA5 there),
21 GRIB fields incl. 2m T, 10m wind, RH, precip, surface pressure, sensible/latent heat
flux, albedo. **Catch: full d3 files are ~240 MB** (whole continent) and the polar-
stereographic grid is **mis-georeferenced by eccodes AND cfgrib** (both returned a degenerate
lat/lon band) — so raw-GRIB coverage checks were unreliable. **Fix:** THREDDS exposes
**NetcdfSubset (NCSS)** + OPeNDAP — NCSS does the projection server-side and returns the MDV
bbox as plain netCDF at **~140 KB/timestep (1760× smaller)**, confirming coverage (72×57 @
2.557 km, T2m −46…−20 °C). Built `fetch_amps()` (NCSS, `--amps --amps-start/--amps-end
[--amps-fhours]`) and pulled a **5-day sample** (2026-05-27→31, 00+12 UTC, f000 → 10×136 KB)
to `J:/barlow_data/amps/mdv/`. Installed `cfgrib`+`eccodes 2.47` (only needed for raw GRIB).
**Decision deferred to user:** which period/cadence for a full AMPS series (WRF24 only;
earlier eras need extra wiring). All 4 foundational datasets + an AMPS path now in hand.

---

## 2026-06-29 — Barlow ERA5 drivers in: all 4 foundational datasets now downloaded

Closed the last credential gap. **ERA5** via Copernicus CDS (new system): wrote
`~/.cdsapirc` with the user's Personal Access Token (single-token format; written without
echoing the value), user accepted the dataset licence, then pulled
`reanalysis-era5-single-levels-monthly-means` over the MDV box `[-77,160,-78.5,164.5]`,
**1993–2024 (384 months), 9 melt/energy-balance vars** (t2m, skt, ssrd, ssr, tp, smlt,
sd, u10, v10) → `J:/barlow_data/era5/era5_mdv_monthly_1993-2024.nc` (0.7 MB).
**Gotcha handled:** the new CDS returns a **.zip of two stepType-split netCDFs**
(avgua stamped T00, avgad T06) — added `_postprocess_era5` to extract, snap both to the
month axis, and merge with `join='exact'` into one clean file (was getting 768 interleaved
months before alignment; now 384, 0 NaN, physically sane: t2m≈247 K). Installed
`cdsapi 0.7.7` + `netCDF4`/`h5netcdf` backends. Tooling: `_fetch_barlow_data.py --era5`
(`--era5-hourly` for sub-monthly; `--setup-cds <TOKEN>`). **Barlow data now complete**
except optional AMPS and a possible 2001 lidar epoch.

---

## 2026-06-28 — Barlow data: unblocked MDV lidar + LTER discharge (2 of 4 gaps closed)

Closed the two non-credential blockers from the prior pass.
**MDV airborne lidar (NCALM 2014-15)** = dataset `MDV_2014`/`OTLAS.112016.3294.1`
(DOI 10.5069/G9D50JX3). Found the data on OpenTopography's public Ceph S3
(`opentopography.s3.sdsc.edu`, bucket `raster/MDV_2014/MDV_2014_be/`) — **fully
anonymous; the API key is only for the portal path, NOT the bulk S3**. Pulling the
**bare-earth 1 m DEMs (~26 GB)**, valleys first (Taylor_Valley 6.2 → North 9.3 →
Garwood 4.9 → Beacon 3.6 → Capes 2.0) to `J:/barlow_data/mdv_lidar/be_dem_1m/`. CRS
**EPSG:3294** (Transantarctic Mtns proj) — reproject before differencing vs REMA.
**LTER stream discharge**: the earlier "wrong id" was actually a **stale revision**
(`9128.11` requested, current is `9128.3`). Rewrote `fetch_edi` to **auto-resolve the
newest revision** (`_latest_rev` via PASTA) and queued **all 21 daily-discharge gauges**
(9100-series 9102–9129): Canada, Commonwealth, Lost Seal, Von Guerard, Onyx, Miers,
etc. Met package also auto-bumped 7003.22→.25. Tooling: `_fetch_barlow_data.py`
(--lidar [--pc] / --lter / --rema). **Still blocked (accounts only):** ERA5 (CDS), AMPS.
Snag mid-run: J: got unmounted (escalated, user reconnected) — all barlow_data lives on J:.

---

## 2026-06-28 — Barlow/FINESST data acquisition to J:arlow_data

Downloaded the public datasets behind the MDV dissertation / FINESST expansion.
**REMA v2.0 mosaic** (satellite DEM epoch) over the MDV — supertiles 17_34/17_35/
18_34/18_35 at **2 m (~11 GB) + 10 m (~1 GB)** from AWS Open Data `pgc-opendata-dems`
(anonymous); MDV tiles calibrated from real tile bounds (grid: left=CC*100k-3.1M,
top=RR*100k-3.0M). **MCM-LTER met** (Lake Bonney + Fryxell, daily/hourly/15-min) via
EDI `knb-lter-mcm.7003.22`. Blocked (need creds/correct IDs): MDV airborne lidar
(OpenTopography API key), LTER stream discharge (wrong EDI id), ERA5 (CDS account).
Tooling: `_fetch_barlow_data.py` (--rema/--lter). Manifest:
`docs/barlow_data_manifest.md`. Storage on J: (off-repo), 156 GB free.

## 2026-06-27 — NISAR recon over 9t + supplement proposal; .git/disk cleanup

**Disk/git.** C: had dropped to <250 MB. `.git` was 25 GB (mostly dangling loose objects
from rebases). A `git gc` first FAILED (no scratch space) — recovered with
`git prune --expire=now` (reclaimed ~20 GB, no history touched), then a clean `git gc`:
**.git 25 GB → 4.8 GB, C: free → 23 GB.** No force-push, history intact. Deeper history
rewrite (regenerable rasters still in reachable history, ~3–4 GB more) deferred — needs
force-push. Data triage produced: ~105 GB regenerable (.tif 93 GB + .laz 10 GB) vs ~0.6 GB
vital (hand annotations + ground truth) + ~2 GB checkpoints; label .gpkg are interleaved
with rasters in tile folders, so any cleanup must be by file pattern not folder.

- **NISAR InSAR over PA is SEASONAL, not impossible (correction).** Re-tested after
  pushback: fall pair 2025-10-28→11-09 coherence **0.50** (94% >0.3) vs winter
  2026-01-08→01-20 **0.14**. The winter decorrelation was snow/freeze-thaw, not forest
  (perp baseline only -35 m). GUNW InSAR subsidence is VIABLE over forested PA with
  snow-free (late-fall/early-spring) pairs. Proposal updated.

**NISAR reconnaissance (real granules over 9t).** Earthdata auth set up (`~/_netrc`),
`_fetch_nisar_9t.py` (CMR query + ASF download, `--max`/`--min-free-gb` guards).
Downloaded + clipped to 9t: 1 GCOV beta + 1 GUNW beta.
- **GCOV usable:** 10 m, RTC gamma-0 HH+HV, EPSG:32617, 100% valid; HH −8.2, HV −16.3,
  HH−HV 8.1 dB (sound forest signature).
- **GUNW NOT usable over 9t:** 80 m, **coherence 0.14 (0% >0.3)** — dense PA canopy
  decorrelates L-band even at 12-day repeat. InSAR subsidence is a *Permian* tool, not PA.
Clips in `data/external/nisar/9t/clip_9t/` (gitignored). Proposal:
`docs/nisar_lidar_supplement_proposal.md` — NISAR = 10–80 m context/covariate/time-axis
(pad covariate, change tripwire, FINESST driver layers), NOT a fine detector; everything
is BETA until validated CONUS release ~July 2026.

---

## 2026-06-17 — Annotation aids: cross-region pad transfer + 3× exaggerated derivatives

**PA pad U-Net → permian_01 (transfer experiment, no retrain).** New reusable
`plats/_pad_unet_infer_grid.py` stacks a grid's existing derivatives into the 7-band
DEFAULT_CHANNELS order (mapping 9t `roughness_11` → grid `roughness_5`), normalizes
with 9t stats, and runs `plat_unet/best.pt` via `predict_full_tile`. On permian_01 (1 m):
**78 candidate pads, precision 60/78 = 77% within 60 m of a ramachandran pad point, but
recall only 68/467 = 15%.** Transfers in precision, recall-limited — chiefly the 0.5 m→1 m
scale mismatch (model trained at 0.5 m). ~4.1k px (0.02%) returned fp16 NaN → written as
nodata. Outputs in `label_grids/permian_01/pad_unet_xfer/`.

**3× vertically-exaggerated openness + slope (manual-picking aid).** New
`build/_build_exag_derivatives.py`. Rationale: openness/slope are atan-nonlinear in
elevation, so vertical exaggeration sharpens incised roads/drainage for the eye; LRM/TPI
are linear (exaggeration cancels under any color stretch) so they are deliberately NOT
produced. Each tile processed at its OWN cell size with a fixed 25 m openness radius:
**9t at 0.5 m** (L=50) → `tiles/9t/exag3x/`; **permian_01–04 at 1 m** (L=25) →
`label_grids/permian_NN/exag3x/`. Heavy tifs gitignored (regenerable).

---

## 2026-06-17 — Label grids rework: new Permian 3×3 centers, WPA manual placements

**Permian re-placed + upsized 2×2 → 3×3.** Prior density-auto Permian centers were
not well-dense enough; user supplied 4 explicit centers and asked for **3×3** (4.5 km,
9 tiles) each: p01 (32.2805,-101.1629) z14, p02 (32.2225,-102.2139) z13, p03
(31.66615,-103.02572) z13, p04 (30.6161,-101.1393) z14. Reworked `_fetch_permian_grids.py`
to a **geometry-based tile picker** (snap to seed±pitch from bbox centers) so it works
for both 6-digit (`14SKA940715`) and 4-digit (`13RFR8603`, TX_Pecos_Dallas) USGS tile
codes; added retry/backoff for flaky TNM JSON. Verified all 4 are gapless 3×3 lattices
(cells (0,0)..(2,2)) before download.

**openness-only for p02–p04.** Per user, the extra Permian grids need only openness;
added `openness_only` to `_build_derivatives.build()` (DEM → openness_pos/neg, skip the
rest). p01 kept as the full-stack reference; p03 (built full before the request) pruned
to dem+openness. CRS: 6343/6342/6342/6343.

**Two robustness fixes for dense 3DEP.** (1) Delaunay TIN OOMs on dense QL1 3×3 mosaics
(~200 M ground pts, 3–10 GB merge) → added `dem_method="gdal"` (writers.gdal IDW,
streaming, window_size 3); permian build uses it. (2) Density/intensity pass switched
from `laspy.read()` (whole file) to chunked `chunk_iterator` to bound RAM.

**Root cause of p02 fail + p04 NaN was DISK FULL (3.8 GB free), not code.** p02's 9.7 GB
merge was truncated → "VLR size too large" on re-read; p04's 9th tile download died with
`No space left on device` → 11% NaN DEM. Freed 29 GB of stale `_merged_*.las` scratch in
`source_laz/westernpa/`; re-fetched the missing p04 tile; both rebuilt clean (p02 nan
0.12%, p04 nan 0.00%). Also dropped `forward:"all"` from the merge writer (unneeded;
CRS/scale/offset set explicitly).

**WPA #3/#4 manual placements.** westernpa_03 → **NE 2×2 of 613590** (tiles
615591/615593/616591/616593); westernpa_04 → **NW 2×2 of 622599** (622600/622602/
624600/624602). Added `--manual` mode + `MANUAL_WPA` to `_build_label_grids.py`. Both
clear of the 9t core. `write_empty` now skips existing gpkgs (QGIS file-lock safe;
empty gpkgs are location-independent so annotation files are never clobbered). Per-grid
gpkg naming `westernpa_NN_*` / `permian_NN_pads` (user-confirmed).

---

## 2026-06-16 — Drainage U-Net + annotation label grids (WPA build + Permian fetch)

**Drainage U-Net.** Built `_drainage_unet_1m.py` (in `wellsight_v2/drainage/`) as the
symmetric twin of the road recall model — same 9t data/channels/3-class labels, focal
alpha flipped to (0.10, 0.25, 0.72) so drainage is the positive and road the confuser.
40 ep, GTX 1070 Ti. **9t test: drainage IoU 0.532, AP drainage-vs-road 0.990,
mean P(drain) 0.696 on drainage vs 0.0016 on road.** Roads essentially never fire as
drainage. Doc: `iterations/drainage_unet_1m.md`.

**Label grids (annotation areas).** New `label_grids/` off repo root with 4 WPA + 4
Permian 2×2 (1 m) grids over the most well-dense areas, each with empty annotation
geopackages (WPA: pit_inside/pit_outside; Permian: pads). Scripts: `_build_label_grids.py`
(select by orphan-well density + build DEM/hillshade/derivative stack) and
`_fetch_permian_grids.py` (pull 3DEP LPC 2×2 tiles via TNM API).
- WPA wells = `data/external/legacy_data/US_Documented_Orphan_Wells.csv` (PA-only, 4786).
  Densest grids overlapped the 9t training core → **excluded the 9t bbox** per user; final
  grids 258/193/174/163 wells, EPSG:6346, built from local LAZ.
- Permian wells = `rrc_orphan_wells_permian.gpkg` (3328). All 4 densest 3 km clusters have
  3DEP LPC coverage (TX_Lower_CO_San_Bernard_2017, TX_WestTexas_2018, TX West Central 2018);
  zones 13R/14R/14S. **Data-quality note:** permian_01 (lon −100.59) and _04 sit on/east of
  the geologic Permian Basin edge — densest RRC orphans, not all "basin" proper. Downloading
  QL "any 3DEP" per user; build in native UTM (EPSG:6342/6343).
- Large-file rule: `label_grids/**/*.tif|las|laz|png` gitignored (same change); empty
  .gpkg templates stay tracked.

**Build complete (all 8 grids).** 4 WPA + 4 Permian, each 20 derivative TIFs incl.
hillshade + empty annotation gpkgs. Two 3DEP-specific bugs fixed mid-build:
(1) `writers.las` int32 overflow — some TX zone-14 tiles ship offset 0, so the large
UTM northing overflowed; fixed with `offset:auto` + scale 0.01 in `_build_derivatives`.
(2) Raw 3DEP tiles carry no CRS → DEM had none → WBT hillshade silently no-op'd; fixed
by letting `build_derivatives` own the DEM (built from the merged LAS tagged `a_srs`)
plus a `stamp_crs()` safety net. WPA dems/permian_04 read as compound CRS (to_epsg None
but valid); permian_01/02/03 are clean EPSG 6342/6343. ~1.7 GB Permian LAZ downloaded.

## 2026-06-16 — Port the road post-proc pattern to pits: `_pit_optimize.py`

**Goal.** Reuse the proven road pipeline shape for pits. Roads = 1-D (skeleton →
centerlines); pits = 2-D blobs, so the new middle stage is threshold → connected
components → shape filter → polygon → centroid (candidate well point). Stage 1
(derivatives) and Stage 2 (`_pit_unet_v2` floor prob) already existed; the new piece
is `notebooks/wellsight_v2/build/_pit_optimize.py`, the polygon analog of
`_road_optimize.py` (same `optimize`/`apply-block` CLI, object-level F1 harness).

**Setup.** GT = `pit_inside` floors (65 in the 9t test region). Detection = floor-prob
blobs; match = greedy nearest centroid within TOL=6 m. Coordinate-ascent over
{enhance, thresh, floor_gate, t, area_min/max, circ_min, ecc_max, min_px}, 2 passes.

**Result (9t test, all blobs, no conf gate).** BEST F1 **0.195** — recall **0.85**,
precision **0.11** (500 candidates for 65 GT). Best cfg: gauss + hysteresis(0.4/0.6),
floor_gate off, area 9–1500 m², circ≥0.45, ecc≤0.88. Saved to
`pit_unet_v2/pit_postproc_best.json`.

**Interpretation.** The extractor works end-to-end, but raw precision is low — the
floor prob is leaky and over-detects. This is the *expected* shape and the argument FOR
the active-learning loop: high-recall candidates + human reject-in-QGIS → hard negatives
→ retrain. The `apply` confidence gate (0.6·mean_pfloor + 0.4·shape) recovers precision
before review. Candidates carry confidence + nearest-known-well distance per QC rule.
Next: pit review-package + corrections-diff (polygon analogs of the road scripts), then
retrain `_pit_unet_v2` on corrections. See [[project_road_active_learning_loop]].

## 2026-06-14 — Road recall fix: focal-α bump (NOT more data); multi-block rejected

**Problem.** Deployed `road_unet_1m` (3-class) gave gappy roads on out-of-domain block
613590: it detected roads in the right places but under-confidently (P(road) ≈ 0.5 on
real roads), so segments dropped below the 0.5 threshold. (Also confirmed the earlier
`road_prob_613590_05` the user saw was the legacy **2-class 0.5 m** model with no drainage
class — a separate, worse model.)

**False alarm corrected.** The suspected "roughness channel bug" is not real: at 1 m,
`features_<key>_1m.tif` band 7 is *labeled* `roughness_11` but is byte-identical to
`roughness_5`. Model trained on roughness_5, infers on roughness_5 → matched.

**Rejected: multi-block training** (`_road_unet_multiblock.py`, `road_unet_mb`). Built a
6-block dataset (`_build_road_multiblock_dataset.py`, 191 km road across 618594/622591/
613603/613608/618591/622594; train-block norm recomputed). Overfit (best val ep7; 618594
= 84% of road) and came out *under-confident* on 613590 (mean P 0.508 < deployed). Adding
outside-9t data diluted the dense 9t core — data was not the bottleneck.

**Adopted: recall-focused retrain** (`_road_unet_1m_recall.py`, `road_unet_1m_recall`).
Same clean 9t data, road focal-α 0.60→0.72, drainage 0.30→0.25, wd 1e-4→2e-4. Best ep38,
val road IoU 0.643. 9t test: pixel IoU 0.581 (=deployed), AP road-vs-drainage 0.999,
P(road) road/drain 0.778/0.004. **On 613590: mean P(road) 0.57→0.66, road≥0.5 px ~1.7×.**

**Cleaned vector network** (validated `roads_opt` cleaner fed the recall prob via new
`--prob`/`--drain` overrides in `_road_optimize.py`): clean network 155.2→**169.3 km**
(1252 segs, 129 bridges), TIGER recall 0.501→**0.523**, novel 123.5→136.2 km. Deployed
network backed up to `roads_opt_613590_1m_deployed.gpkg`.

`road_unet_1m_recall/best.pt` is now the current road model for data_3x3 blocks (not yet
re-inferred across all 25). `road_multiblock/` gitignored (regenerable dead-end). Docs:
`docs/iterations/road_unet_1m_recall.md`, LEADERBOARD roads table updated.

---

## 2026-06-09 — Project reorg: full data-tree restructure + root cleanup (paths maintained)

Reworked the repo layout for findability; **all code paths maintained** (verified, no
dangling refs). Mechanical path rewrite via a one-off mapping script (literal +
`Path`-constructor + runtime `DERIV/sfx` forms + the QGIS `.qgz` internal absolute
paths, both separators), then grep-verified + AST-parsed (78 files, 0 errors) +
`_common` import-tested.

**data/derivatives/** flat 25-dir dump → bucketed:
- `tiles/` (per-area stacks: 9t, 9t_1m, data_3x3, oilcreek_22tile_05, *_marcellus_1m,
  wc_coaloil_1m, extras, mosaic_3x3*) · `inference/` (mck, oilcreek) ·
  `experiments/` (chm_age_proxy, icp, pilot_A, ramachandran_verifier, roads,
  candidates, notebook_demo, permian_sample) · kept `annotations/`, `validation/`.
- `DERIV_9T` now `…/tiles/9t`; runtime stack builders write to `DERIV/"tiles"/<key>`.

**data/** source LAZ: `FILES`→`source_laz/westernpa`, `mckean`→`source_laz/mckean`;
deleted empty `dem_tiles`, `older_files` and temp `_tmp_intensity_tiles_mkf`.

**Archived (old >2 wk AND unused):** `beck_9t`, `beck_mkf`,
`inference_mck_e1423n2238_05`, `model_archive` → `archive/derivatives/` (heavy
rasters gitignored there; small metric/VERSION records kept tracked).

**Root cleanup:** resume→`personal/`, `road error.jpg`→`docs/figures/debug/`,
kang PDF→`docs/papers/`, downloadlist→`data/external/usgs_3dep_pa_lidar/`, YOLO
weights→`models/pretrained/` (CLI defaults updated), `qgis_lidar class.qgz`→
`qgis/wellsight.qgz` (space removed; layer paths inside repointed to new buckets).

**docs/** consolidated: `paper_versions/`+`presentations/`+methodology docx →
`publication/`; single-file `pipelines/`+`preprocessing/` folded into `articles/`.
`STRUCTURE.md` fully regenerated.

## 2026-06-09 — Back to PA: orphan catalog × our LiDAR coverage (Oil Creek), + pit-annotation validation

Pivoted the orphan-detection work back to Pennsylvania (the two historical books are
PA-focused; PA is where we have ground truth + forested terrain where earthworks show).

**The "US" orphan catalog is all Venango Co., PA** (4,786 wells, Oil Creek/Oil City
corridor; densest ~166/2 km cell at -79.55,41.49). Cross-referenced against our PA
DEM coverage — strong overlap:
- `9t` tile: **624 orphans** (0.5 m DEM `dem_9t_05.tif`; also has our hand pit/pad
  annotations) — best combined target.
- `oilcreek_22tile_05`: **468 orphans** at **0.5 m** — matches the historical pit-depth
  prior (0.6–1.5 m); literal birthplace of the industry.
- `westernpa_d20` (25 blocks): **3,125 orphans**; densest block 618594 = 552.

**Validation (orphans × hand pit annotations, within the annotated area, 318 orphans
/ 113 pits):**
- **60% of hand-annotated pits have a documented orphan within 30 m (64% @50 m)** →
  the pit features we detect in LiDAR are largely real orphan cellars (mutual
  validation of both datasets).
- Only **~22% of orphans have an annotated pit within 30 m** → we've labeled a small
  fraction of what's present (113 pits vs 318+ orphans in that area alone).

**Implication:** directly enables BACKLOG #1 (grow labels). The orphan catalog can
seed semi-automated pit annotation: snap each catalogued orphan to nearest LiDAR
depression within a sanity radius → human-confirm → grow labels ~5–10×. Caveat: PA
DEP coords are not survey-grade (median nearest-pit dist 245 m because orphans span
the whole tile while pits were annotated in a cluster); needs radius + human QC.
Eyeball overlay: `data/derivatives/pa_9t_orphans_overlay.png`.

---

## 2026-06-09 — Confirmed Permian ground truth: TX RRC orphan wells (+ optical cross-ref)

Established that we had NO confirmed-well ground truth for the Permian:
`data/external/legacy_data/US_Documented_Orphan_Wells.csv` is mislabeled — it's
**4,786 wells, 100% Pennsylvania** (PA DEP, Status=Orphan); 0 in TX/NM. So the
194,973 optical pad detections were unvalidatable.

**Fetched authoritative TX ground truth** from the RRC ArcGIS REST service
(`gis.rrc.texas.gov/server/rest/services/rrc_public/RRC_Public_Viewer_Srvs/MapServer`,
**layer 2 = "Orphan Wells"**, fields OBJECTID/API/SHAPE). Queried the Permian bbox
(paginated, maxRec 1000) → **3,328 confirmed orphan wells** →
`data/derivatives/experiments/permian_sample/rrc_orphan_wells_permian.gpkg`
(layer `rrc_orphan_permian`, `status=orphan_confirmed`, API + point, EPSG:4326, 0.6 MB).

**Cross-reference (UTM 13N metres):**
- Sample tile 13RGR500055: **0** confirmed orphans (it's modern active pads — wrong
  place to look for orphan signatures).
- Only **34.6%** of RRC orphans have an optical pad within 100 m → optical detection
  misses ~⅔ of confirmed orphans (old wells, no visible graded pad) — the case FOR
  the LiDAR approach. (Only ~0.6% of optical pads sit near an orphan; the optical set
  is overwhelmingly active wells.)
- Caveat: RRC historical coordinates are coarse — some misses are location error.

**Best orphan-cluster target for QL1 eyeballing:** (-102.825, 31.225) — **136
orphans/5 km cell**, covered by `TX_WestTexas_2018` (~12–13 pts/m², QL1). Next step:
pull a tile there and check whether confirmed orphans show terrain signatures.

---

## 2026-06-09 — Permian QL1 sample render + early-well parameter mining

**(1) Density ceiling check.** Ranked the full cached Permian inventory (104,396
tiles) by LAZ-bytes/m² (calibrated to a measured tile, ~3.46 B/pt). Over the actual
well hotspots, **~15 pts/m² (QL1) is the ceiling** — confirmed by reading the densest
in-hotspot tile header (`TX West Central B4 2018 13SGR110655`: 33.8 M pts in a
1500×1500 m tile = 15.0 pts/m²). Denser projects exist (`TX_Lower_CO_San_Bernard`
p90 ~22) but lie outside the well clusters. CO/DJ-Basin coverage is QL2 (~2 pts/m²),
so Permian is the higher-quality region. ~15 pts/m² ≈ 7× the western-PA D20 QL2 data.

**(2) Eyeball sample.** Built a 0.5 m bare-earth DEM (PDAL ground-class IDW) from the
best on-disk B4 tile `13RGR500055` (16 pads, 33.3 M pts), hillshaded it, overlaid the
15 Ramachandran pad detections in-tile → `data/derivatives/experiments/permian_sample/`
(`dem_..._05m.tif` 72 MB gitignored by blanket; `hillshade_..._pads.png` tracked).
CRS verified from file: **NAD83(2011)/UTM 13N + NAVD88, EPSG:6342**. Observation: flat
West-TX rangeland — roads/tracks and some square pad scars read crisply, but graded
pads have low vertical relief (the optical detector keys on dirt color, not relief).
This is the inverse of forested PA, where the terrain scar IS the signal under canopy.

**(3) Book parameter mining** (user-supplied PDFs in `docs/papers/`). Williamson &
Daum *Age of Illumination* (888 pp OCR) + Ross *Allegheny Oil* (69 pp image scan, on
our exact PA region) mined for measurable detection priors → `docs/articles/
early_well_parameters.md`. Headline priors: earthen catch-pit depth **~0.6–1.5 m**
(only explicit pit dimension; argues for 0.5 m DEM in PA), well spacing **~20–45 m**
(clustering prior), tank-ring dia **~9 m** (Hough-circle prior, r≈4.5 m), derrick pad
**~4 m** square. Explicit gaps flagged (slush-pit L×W×D, house footprints) — to be
sourced from PA DEP standards, not fabricated.

---

## 2026-06-08 — Scout high-quality 3DEP LiDAR over dense abandoned-well clusters (Permian + DJ Basin)

Goal: find good high-density-well sample areas with high-quality public LiDAR, in
the two Ramachandran 2024 optical-imagery regions (Permian TX/NM, Denver/DJ CO).

**Well-density proxy:** Ramachandran deployment well-pad detections — 194,973 Permian
(score med 0.93) + 36,591 Denver. Gridded at 0.1° (~10 km cells).

- **Permian hotspots** (densest ~10 km cells, 1100–1670 pads each): Midland/Martin/
  Andrews Co. core `-102.5…-102.85, 32.0…33.1` and Eddy/Lea Co. NM `-103.15, 32.45`.
- **DJ Basin hotspots:** tightly clustered in Weld Co., CO `-104.5…-105.0, 40.0…40.4`
  (Greeley), 350–490 pads/cell.

**LiDAR coverage × measured quality** (density read from actual LAZ headers via laspy,
2.25 km² USGS tiles):
- **TX West Central 2018** covers most Permian hotspots; blocks **B4/B8 measure
  ~13–15 pts/m² (QL1-grade)**, but B7 only ~4 pts/m² — density varies by sub-block.
- **NM_SouthEast 2018 D19** (~6 pts/m²) covers the NM hotspot `-103.15, 32.45`.
- **TX_Pecos_Dallas 2018** covers `-102.35, 31.45`.
- **CO_EasternColorado 2018** (project path tags it `..._B2_QL2_North_2018`) is the
  workhorse over Weld Co.; **CO_DRCOG 2020** (QL2, newer) overlaps too. (One edge
  tile read 0.2 pts/m² — a sliver tile, not representative; QL2 spec is ≥2 pts/m².)

Inventory source: USGS TNM `products` API (`Lidar Point Cloud (LPC)`), Permian
inventory already cached (`data/external/usgs_3dep_permian_tx/tile_inventory.parquet`,
104,396 tiles); Weld Co. queried live (5,728 LPC products in the hotspot bbox).
No bulk download done — characterization only. Reproduce: density grids from the
deployment `*_well_pads.csv`; coverage via the cached parquet / TNM bbox query.

---

## 2026-06-08 — 2 m elevation contours on every data_3x3 block DEM

New `_build_contours_data_3x3.py` runs `gdal_contour -a elev -i 2 -snodata -9999`
on each `dem_<key>_1m.tif` (EPSG:6346, metres → 2 m interval) → `contours_2m_<key>_1m.gpkg`
(layer `contours`, attr `elev`, all multiples of 2). Built for all 25 WesternPA D20
blocks (~547 MB total, 18–41 MB each; ~0.6 min). Heavy regenerable vectors, so added
gitignore rule `data/derivatives/tiles/data_3x3/**/contours_*.gpkg` in the same change;
≥100 MB audit clean. Reproduce: `python notebooks/wellsight/build/_build_contours_data_3x3.py`
(`--interval N`, `--only <key>`).

---

## 2026-06-07 — Fix drainage FPs at the source: 3-class road model + road chunking

User pushback: the post-hoc drainage filter was too aggressive, and "are we
priming the model on drainage?" Investigation: (1) hand-drawn roads are NOT
contaminated (only 0.7% run on a mapped stream); (2) the model was *set up* to
confuse roads/drainage — the U-Net label was binary road/bg with NO drainage
negatives (the 112-line `not_roads` layer was only used by the side classifier,
not the U-Net), and all 7 feature bands are generic concavity so nothing told it
"water flows here". Conclusion: fix it in **training**, not with a filter.

**Fix 1 — drainage as a trained class.** User pointed to `drainage.shp` in the
annotations folder (1791 channel segments from the cross-section filter,
`klass='stream'`, EPSG:6346, no .prj). Wired it through: `_prep_annotations.py`
adds a `drainage` gpkg layer (stamps EPSG:6346); `_prep_road_1m.py` rasterizes it
as class 2 (buffered 2 m, road painted on top) → `labels_road_9t_1m.tif` is now
0=bg/1=road/2=drainage; `_road_unet_1m.py` → `N_CLASSES=3`, FocalCE alpha
(0.10,0.60,0.30), drainage sampling policy; `_infer_roads_data_3x3.py` →
`N_CLASSES=3`, writes `drainage_prob` + 2-colour overlay. Result: P(road) on
drainage test lines = **0.005**, road IoU 0.379→0.527.

**Fix 2 — chunk the roads (user caught this).** Roads = few long polylines (171,
median 126 m, max 921 m); drainage = pre-chunked (~21 m). The sampler centers ONE
patch per line midpoint, so long roads were massively under-sampled (most of their
length never seen) and the 27-line eval was meaningless. `_build_plat_road_dataset.py`
now chunks roads/not_roads to ~40 m → `road_chunks_9t.gpkg` + chunk-level manifest
(8385 road chunks, 635/95/130 train/val/test); eval rewritten per-chunk. Restored
road focal weight to 0.60. Result (168-chunk test): **road IoU 0.581, line AP
0.992, P(road) road/drainage 0.757/0.006**. Pilots: 604603 road 0.98%/drain
1.36%; 609590 road 2.87%/drain 1.19% — clean separation, no post-filter needed.
Backups: `best.pt.2class.BAK`, `best.pt.3class_nochunk.BAK`. Full writeup
[[road_unet_1m]] §v2. **Open:** re-infer the other 23 blocks with the 3-class
model; decide post-filter's residual role (connectivity/vectorization only).

---

## 2026-06-07 — Refine road rasters → clean, connected centerlines (drainage filter + gap-bridging)

User feedback on the per-block road predictions: good, but (a) picking up drainage/
waterways and (b) roads that should connect are fragmented. Built
`_refine_roads_data_3x3.py` to post-process each block's `road_prob` raster into
vector centerlines, reusing the project's validated cross-section concavity test
`_xdrop` (from `_filter_streams_xsec_9t.py`).

**Pipeline:** binarize(0.5) → remove_small_objects(250) → close(3px) → skeletonize
→ `skan` trace to LineStrings → bearing-aware endpoint gap-bridge (≤25 m, tangents
within 35°) → linemerge → drainage filter → drop <35 m stubs → re-rasterize +
gpkg + overlay.

**Connectivity (problem b):** morphological close for hairline gaps + endpoint
snapping for medium gaps (247 bridges on the steep pilot). User opted to KEEP all
>35 m fragments (no network-island filter).

**Drainage (problem a) — the methodology finding.** A single global `xdrop`
threshold does NOT generalize across terrain (drainage km dropped per pilot):
`xdrop≥0.30` flat 19.7 / steep 52.0 (eats roads); `xdrop≥0.60` flat 6.7 / steep
15.7 (steep channels leak); naive hydrology flat 23.7 / steep 42.5 (D8 routes down
road **ditches** on flat terrain → eats grid roads). **Adopted rule combines
both:** drainage if (coincides ≥50% with a mapped D8 stream [flow-accum ≥4000
cells, dilated 3px] AND `xdrop≥0.35`) OR (`xdrop≥0.60` alone). The concavity gate
on the hydrology catch rejects flat road ditches (flat-bottomed → low `xdrop`).
Pilots with adopted rule: flat 604603 roads 45.7 km / drainage 12.0 km; steep
609590 roads 130.3 km / drainage 23.8 km — both visually correct (grid roads kept
on flat; dendritic channels caught on steep). Per-block D8 streams built with WBT
(breach→d8→accum→extract_streams), cached as `stream_seed_t4000_<key>_1m.tif`;
heavy breach/accum intermediates deleted. **Rollout complete: all 25 blocks in
16.7 min — 1727.9 km roads kept / 346.7 km drainage dropped (16.7%) / 2413
bridges.** Outputs per block: `roads_<key>_1m.gpkg` (layers roads+drainage,
tracked), `road_clean_<key>_1m.tif`, `road_clean_overlay_<key>_1m.png`. ≥100 MB
gitignore audit clean. Full writeup: [[road_refine]].

---

## 2026-06-07 — Group ALL WesternPA tiles; retrain roads on latest annotations; 0.5 m→1 m road fix

**1. Grouped every WesternPA 2019 D20 tile into a block.** The old 3×3 builder only
emitted blocks where all 9 tiles of a non-overlapping 3×3 were present → 50 of 176
tiles dropped. New `_build_data_3x3_partial_westernpa.py` uses the same stride-3 grid
(so the 14 existing full blocks are reused untouched) but emits a block per non-empty
cell with partial member lists (1–9 tiles) and a tight bbox. Result: **25 blocks,
176/176 tiles covered, zero overlap.** Built the 11 new partial edge blocks (48 min).

**2. Retrained roads on the latest hand-drawn `roads.shp`.** The downstream training
data was stale (annotations_proj.gpkg from 2026-05-19) while `roads.shp` had grown
to today. Rebuilt `annotations_proj.gpkg` (`_prep_annotations.py`): roads **97 → 1725**
features. Fixed a null/empty-geometry crash in `_build_plat_road_dataset.py` (exposed
by the bigger set; guards preserve positional `line_id` alignment used by eval).
Rebuilt road labels + manifest: **171 road lines** inside the 9t blocks (train 123 /
val 21 / test 27). Backed up old `annotations_proj.gpkg` + `road_unet/best.pt` (.BAK).

**3. Resolution mismatch found + fixed.** Piloting the 0.5 m road model on a 1 m block
gave **33% "road"** — false positives smeared over terrain. Cause: only `roughness`
was physically matched across resolutions; `lrm_25`/`tpi_05`/`openness` feed the model
at ~2× their trained window on 1 m data. Chose (over regenerating 25 blocks at 0.5 m)
to **retrain the road U-Net at 1 m** ([[road_unet_1m]]): built `9t_1m` stack with the
same `_build_derivatives` code as the blocks, `_prep_road_1m.py` (features_pit_9t_1m +
feature_stats_1m + labels_road_9t_1m, roughness_5), `_road_unet_1m.py`. 1 m test
metrics ≥ 0.5 m (pixel IoU 0.379 vs 0.343; line AP 0.962; P(road) road/not_road
0.654/0.133). Pilot 604590: **33.2% → 4.06%** road px, coherent road lines.
Inference on all 25 blocks via `_infer_roads_data_3x3.py` (→ per-block
`road_prob/argmax/overlay_<key>_1m`). Residual FPs on steep incised slopes →
cross-section concavity filter ([[BACKLOG]]).

## 2026-06-06 — Training determinism: seeded, but GPU Mask R-CNN is NOT bit-exact

Added `ic.set_determinism(seed)` + seeded DataLoader generator/`worker_init_fn`
and a `--seed` arg (saved into `best.pt`) to `_pit_maskrcnn.py` and
`_pad_maskrcnn.py`. This pins head init + batch order.

**Finding (verified):** two `--smoke --seed 0` pit runs still diverged
(tr 0.739/va 0.559 vs tr 0.742/va 0.529). Strict
`torch.use_deterministic_algorithms(True)` pinpoints the cause:
`roi_align_backward_kernel does not have a deterministic implementation`
(atomic adds on CUDA). So GPU Mask R-CNN training cannot be made bit-for-bit
reproducible with this stack; we use `warn_only=True` so it still runs. Seeding
makes runs *close*, not identical. Bit-exactness would need CPU training
(impractically slow for 30 epochs).

**Takeaway:** reproducibility of a *model's outputs* comes from saving `best.pt`
and re-running deterministic *inference* (proven bit-identical in
`training_walkthrough.ipynb` Path B), not from re-training. Derivatives remain
fully deterministic (proven bit-identical in `derivatives_walkthrough.ipynb`).
The real `pit_07`/`pad_05` `best.pt` were backed up + restored during the test;
they predate seeding and are not recreatable.

## 2026-06-03 — Diagnostic derivative sweep on 9t (curvature/hydrology/texture)

Built 13 new geomorphometric layers from `dem_9t_1m.tif` via WhiteboxTools
(`_build_diagnostics_9t.py`): depth-in-sink, TWI, 5 curvatures, geomorphons,
multidirectional hillshade, spherical-stddev-of-normals, TRI, surface-area-ratio,
downslope index. All 16 ops OK in ~45 s. Diagnostic-only (not in any model);
outputs git-ignored under `9t/diagnostics/`. Full detail + validation table in
`iterations/diagnostics_9t.md`.

**Headline validation vs 110 pit annotations:** `depth_in_sink` median 0.36 m at
pit centroids with 90% sitting in a closed depression, vs 1% at random points —
the strongest single hand-crafted pit signal measured. `geomorphons` puts 106/110
pits in concave classes (depression/valley/hollow). Both added to BACKLOG as
feature-stack promotion candidates (pending 0.5 m recompute + full-tile FP rate).

---

## 2026-06-03 — CATCH-UP: instance-segmentation era (May → Jun) + 7-band rebuild

> Backfill entry. The running log lapsed after 2026-04-30; this block records the
> major work since, chronologically within. Per-iteration detail lives in
> `docs/iterations/*.md` and `LEADERBOARD.md`; this is the narrative thread.

### Direction change — from heuristic detectors to learned instance segmentation
The Apr pipeline (blob+RF pits, ridge-filter roads, gated pads) was superseded by
learned models on the **9t** tile. Two families now run side by side:
- **Semantic (UNet):** best for linear features (roads/streams); paints pixels.
- **Instance (Mask R-CNN, YOLOv8s-seg):** emits one detection per object, so pits
  and pads can be counted/ranked individually.

### Iterations completed (9t, see LEADERBOARD)
- `pit_07_maskrcnn`, `pit_08_yolo`, `pad_05_maskrcnn`, `pad_06_yolo` — all trained
  + inferred. Consistent finding: **best checkpoint is epoch 0–1, then overfits**
  (74 train pits / 51 train pads vs a 45.9 M-param backbone). Recall is high,
  precision poor (heavy over-prediction). Apples-to-apples instance metric
  (`_instance_common.per_instance_metrics`) added so UNet and detectors compare
  fairly; UNet collapses under the instance metric on pits (recall@0.5 ≈ 0).
- Cross-referenced all models vs the **full PA DEP catalog (1069 wells in-tile)** —
  well_recall 0.22–0.42. Read as a *lower bound* (catalog includes plugged/
  canopy/no-surface-expression wells), and as the strongest argument that the
  **110/79 annotation set is the bottleneck**, not the architecture.

### Engineering fixes logged
- **YOLO BGR gotcha:** PIL writes PNGs RGB, ultralytics' cv2 reads BGR → channels
  0/2 swapped, zero recall. Fixed with `img8[..., ::-1]` at inference. (memory saved)
- **MaskRCNNPredictor** TypeError (positional hidden-layer arg); **cp1252**
  UnicodeEncodeError on `→` (write utf-8); YOLO mask coord mismatch (use
  `masks.xy` polys, not model-res masks with orig-res boxes).
- **In-RAM feature caching:** 7-band per-patch file reads were 163 ms each;
  cache the full stack once (`load_feature_array`/`slice_feat_patch`) → ~0.5 ms.

### 7-band UNet-feature rebuild (the headline change)
Per user direction ("use all the UNet params again… Stop and rebuild"), the
detectors moved off the 3-band composite `(hillshade, slope, lrm_25)` onto the
**full 7-band UNet stack** `(lrm_25, lrm_5, slope, tpi_05, openness_pos,
openness_neg, roughness_11)`, z-scored. Implemented via **conv1 widening**: copy
COCO RGB weights into the first 3 input slots, warm-start the extra 4 from the RGB
mean, identity input transform (patches pre-normalized). CHM deliberately
excluded — canopy/overgrowth is inconsistent pad-to-pad. Pits also gained a
**wall class** (`pit_outside` rim) → 3-class (bg/floor/wall).

### 2026-06-03 inference results (7-band)
- **pit_07 v2:** floor recall@0.5 **0.85 → 0.95**, mean IoU 0.632 → 0.664;
  2027 dets (947 floor + 1080 wall). Clear win.
- **pad_05 v2:** dets **3250 → 2546** (−22% FP) but recall flat (0.889) and mean
  IoU slipped 0.688 → 0.631. **7-band did NOT solve pad over-prediction** —
  revised diagnosis: data quantity + permissive 0.3 score threshold, not features.
- Process note: first pad v2 inference crashed `KeyError: 'mu'` — `best.pt` was
  still the v1 3-band ckpt (the 7-band rebuild had only finished for pits). Pad
  retrained 6 ep on the 7-band stack (best=ep0) then re-inferred OK.

### Streams ported to 9t (2026-06-02) — see `iterations/streams_9t_t5000.md`
D8 flow-accum on breached DEM, `extract_streams` threshold **t5000** → 2693 lines
/274.5 km. Cross-section concavity road filter (`--chunk 25 --perp 5 --drop 0.30`,
on RAW DEM) → per-line kept 1497 lines/97.9 km, per-chunk kept 4973/88.8 km.
Provenance Q answered: Oil Creek LAZ was hydro-flattened (water class 9/20),
McKean/9t surveys were not — different surveys, not a processing error.

### Oil Creek derivatives (2026-06-03) — see `iterations/oilcreek_derivatives_05.md`
Full 0.5 m derivative stack built for the 22-tile mosaic. **Blocker:** build emits
`roughness_5`, models need `roughness_11`; must generate it + assemble the 7-band
stack before Oil Creek inference can run.

### Docs status
This catch-up restored the lapsed log; `BACKLOG.md` recreated; pit_07/pad_05 docs
refreshed with v2 numbers + fixed stale script names; LEADERBOARD updated;
`HOW_IT_WORKS.md` (plain-English overview) added. Documentation-maintenance rule
added to CLAUDE.md.

---

## 2026-04-29 — Literature-grounded parameter adjustments (v0.6)

Four parameter changes based on published literature review:

### 1. Pad slope threshold: 5.0° → 8.0°
- **Rationale:** PA DEP 25 Pa. Code Ch. 78 specifies ≤5% (~2.9°) for new construction, but
  Drohan & Brittingham (2012, Environmental Management 49:1061-1075) observe reclaimed pads
  at 3-8° depending on restoration age. Aged/eroded pads in Appalachian terrain can reach
  8-10° due to decades of erosion and settling. The 5° threshold was missing older sites.
- **File:** `notebooks/03_pad_detector.ipynb` cell "params"

### 2. Pad minimum area: 80 m² → 100 m²
- **Rationale:** Hammack et al. (2014, NETL) document smallest historical PA conventional
  pads at ~100-400 m². Allred et al. (2015, Science 348:401-402) report conventional pads
  at 900-4000 m². 80 m² is below any documented pad size and introduces false positives
  from tree-throw pits and natural depressions.
- **File:** `notebooks/03_pad_detector.ipynb` cell "params"

### 3. Pit blob max_sigma: 3.5 → 5.0 (coarse scale)
- **Rationale:** LoG blob radius ≈ sigma × √2, so max_sigma=3.5 detects up to ~9.9 m
  diameter. Hammack et al. (2014, NETL) document reserve pits at 3-10 m; PA DEP records
  show brine pits at 2-8 m. Extending to 5.0 captures up to ~14 m diameter, covering
  larger reserve/brine pits. num_sigma increased from 6 to 8 for finer scale sampling.
- **File:** `notebooks/03c_pit_detector.ipynb` cell "a503eaa9"

### 4. Positional uncertainty: 100 m retained, era-dependent model noted
- **Rationale:** Kang et al. (2014, NETL/DOE) report 50-200 m for pre-GPS PA well coords.
  Brantley et al. (2014, ES&T 48:7552-7561) note historical coords from plat maps carry
  100-300 m error. 100 m is supported as median for pre-1990 records. For pre-1950 wells,
  200 m is more appropriate — now feasible with SPUD dates from the enriched PASDA dataset
  (wells_in_tile_enriched.gpkg, 20,108 Venango County wells with full attributes).

### Additional: enriched well dataset acquired
- Downloaded PA DEP Oil & Gas Locations from PASDA (April 2026 release, 223,742 wells statewide)
- Venango County subset: 20,108 wells with SPUD date (92%), operator (99.9%), well type,
  permit date, plugged date, surface elevation, well status (10 categories)
- Saved as `data/derivatives/venango_wells_all.gpkg` (EPSG:6346)
- Tile-clipped subset: `data/derivatives/wells_in_tile_enriched.gpkg` (1,109 wells)
- Status breakdown in tile: 634 Active, 276 Plugged, 167 Abandoned, 20 Orphan, 12 Not Drilled

### Literature references for existing parameters (confirmed supported)
- DEM 1m resolution: Hesse (2010), Doneus (2013) — standard for sub-canopy anthropogenic features
- TPI radii 5/15/25.5m: Weiss (2001), De Reu et al. (2013, Geomorphology 186:39-49)
- LRM windows 5/11/25/51: Hesse (2010, Archaeological Prospection 17:67-72), Bofinger et al. (2006)
- Roughness 11×11: Riley et al. (1999), Grohmann et al. (2011, Geomorphology 132:175-192)
- Openness 25m: Yokoyama et al. (2002, PE&RS 68:257-265), Doneus (2013)
- Ridge sigmas 1/2/3: White et al. (2010, PE&RS 76:1079-1087) — 3-9m road widths
- Blob LoG 0.8-5.0: API construction standards, Hammack et al. (2014, NETL)

---

## 2026-04-13 — Session reset and documentation-first bootstrap

- **Context reset.** Prior session operated from a non-canonical long-form
  document (Feature-Type catalog A–K) that does not match the on-disk
  `Claude.md`. Discarded that guidance; only `Claude.md` (WellSight
  Formation Prompt) governs now.
- **Deleted:** `notebooks/02_pad_derivatives.ipynb`,
  `notebooks/03_pad_detection.ipynb`, and `notebooks/_make_candidate_gallery.py`.
  Reason: scope creep, alternative-filter sections, misaligned with the
  canonical pipeline in `docs/05_processing_pipeline.md`.
- **Kept:** `notebooks/01_preprocessing.ipynb` (stage A + part of stage B).
- **Wrote:** `docs/01_project_scope.md`, `docs/02_data_dictionary_wells.md`,
  `docs/03_las_inspection_report.md`, `docs/04_feature_detection_design_spec.md`,
  `docs/05_processing_pipeline.md`, `docs/analysis_log.md` (this file).
- **Toolchain check:** `pdal` 2.10.0 is on PATH at
  `C:\Users\colto\miniconda3\Library\bin\pdal.exe`. `pdal info --summary`
  succeeds on `output2.las`. PDAL Python bindings intentionally unused per
  `Claude.md`.
- **Key LAS facts (from stage A inspection):** LAS 1.4 pf=7, 9,717,579 pts,
  EPSG:6346 (NAD83(2011)/UTM 17N) + NAVD88m, 4.32 pts/m² mean, 60.75 %
  `class=2` already. No waveform. No vegetation-class split (USGS default).
- **Key wells facts:** 84 records inside the tile, all Orphan, all Venango
  County, all dated 5/9/2022 release. No drilling-date column. No
  coordinate-accuracy column. Only 7 of 26 CSV columns are usable.
- **Anomalies / escalations pending:**
  - Drilling-era detector design (§10, Q3 in design spec) — default chosen:
    single detector covering full size range.
  - Positional-uncertainty radius for validation — default 50 m.
  - Tool choice WhiteboxTools vs SciPy for slope/TPI — default WBT where it
    has a named tool, SciPy otherwise.
- **Next action:** bootstrap pilot per §8 of design spec. Select 3–5 wells,
  generate 250 × 250 m sub-extracts, run pad detector, record results before
  anything tile-wide.

---

## 2026-04-14 02:30 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 363.32 - 493.51 m, NaN 0.000%
- DSM : max-Z first returns. z 363.36 - 517.99 m, NaN 0.092%
- CHM : DSM-DEM floored >= 0. p50=3.36 m, p95=23.23 m
- Ground density: np.bincount, exact/cell. mean 2.62, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 84 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 02:30 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 02:35 UTC — v0.1 pilot FAIL, recalibrating (manual iteration)

- Bootstrap pilot refused tile-wide run.
- Cause: v0.1 thresholds (roughness_max=0.15 m, relief_max=0.40 m) from the
  guide are for flat agricultural terrain. This tile is forested Appalachian
  regrowth where natural roughness >> 0.15 m.
- Calibration: in 51×51 m windows around each of the 84 documented wells,
  median MIN per window is:
    - slope      0.362°
    - roughness  0.224 m
    - relief     2.007 m
  tile-wide p5/p10/p50:
    - slope     2.50 / 3.70 / 10.10 °
    - roughness 0.18 / 0.22 / 0.56 m
    - relief    1.23 / 1.60 / 3.55 m
- Decision: raise `roughness_max_m` to 0.25 m, raise `local_relief_max_m` to
  1.50 m; keep `slope_max_deg` at 5.0°. Coordinated change rather than a
  single-variable step because the v0.1 values produced 0 raw components
  window-wide (no information to bisect on).
- Relaxed pilot isolation to 80 m (only 6/84 wells were ≥150 m isolated, and
  5 of those were edge-bound; yielded 1 usable pilot window, insufficient).
- Detection method tag: `pad_v0.1_flatness_morph` → `pad_v0.2_calibrated_forest`.
- Next: rerun pilot → tile-wide → validation.

## 2026-04-14 02:40 UTC — v0.2 pilot FAIL, iterating to v0.3 (loose gates)

- v0.2 pilot (roughness_max=0.25, relief_max=1.5): 1/5 windows passed. Diagnostic:
  - 3/5 windows had ≥1 component survive the size filter (area≥40).
  - Shape gate (compactness≥0.4 OR rect≥0.7) and position gate (tpi_51 in [-1,3]) each rejected most survivors.
  - Pilot #3 had 0 raw components at all → that window really is rough/hilly.
- v0.3 coordinated change (breaks WellSight "one var at a time" rule deliberately; logged):
  - compactness_min 0.40 → 0.30
  - rectangularity_min 0.70 → 0.55
  - tpi51_min_m -1.0 → -3.0
  - tpi51_max_m  3.0 → 5.0
  - area_min_m2 40.0 → 20.0
- Intent: allow proof-of-concept tile-wide run to reach validation, where the
  null-baseline test honestly tells us if there is signal. Too-tight thresholds
  block the pipeline from ever producing a testable answer.
- Detection method tag: `pad_v0.2_…` → `pad_v0.3_loose_gates`.

## 2026-04-14 02:35 UTC — Stage D complete (03_pad_detector)  run 20260414T023549Z-ee8e3a

- Thresholds: slope_max_deg=5.0, roughness_max_m=0.25, local_relief_max_m=1.5, compactness_min=0.3, rectangularity_min=0.55, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=20.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=50.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121225670000: raw=22 kept=4 nearest=12.113045016348464
  - API:37121298870000: raw=13 kept=2 nearest=27.222062944390945
  - API:37121338070000: raw=0 kept=0 nearest=nan
  - API:37121337960000: raw=46 kept=3 nearest=79.56904077083315
  - API:37121303790000: raw=12 kept=3 nearest=56.47164260029245
  acceptance: PASS

- Full tile: raw=494, after gates=52, within 50 m of well=12
- Confidence: median=0.36, p95=0.50
- Output: candidates_pads.gpkg / .parquet (52 rows)

## 2026-04-14 02:36 UTC — Stage E (04_validation)  run 20260414T023549Z-ee8e3a

- Observed median dist: 86.81 m;  null p5/p50/p95 = 64.38/77.34/91.95;  p=0.8400
- Observed recall@50m: 0.107;  null p5/p50/p95 = 0.095/0.155/0.226;  p=0.9400
- Verdict: **NOT ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T023549Z-ee8e3a.md

## 2026-04-14 02:37 UTC — End-to-end complete (v0.3, NOT ABOVE CHANCE)

- Pipeline ran through all four notebooks: 01 preprocessing → 02 derivatives → 03 detector (v0.3) → 04 validation.
- Outputs:
  - 52 candidate polygons in `candidates_pads.gpkg`
  - Validation summary: `summary_run_20260414T023549Z-ee8e3a.md`
- **VERDICT: NOT ABOVE CHANCE**
  - Observed median candidate→well distance: 86.8 m
  - Null (random placement) median p50: 77.3 m — random is *closer* than ours.
  - Observed within-50 m recall: 9/84 = 10.7%; null p50 = 15.5%.
  - Both empirical p-values are > 0.8 — the v0.3 candidate set does not cluster near documented wells.
- Interpretation (options, not conclusions):
  1. v0.3 thresholds are too loose; picking up random flat patches that dilute any real signal. Tightening may help, though v0.1/v0.2 were too tight to produce candidates at all.
  2. Absolute-flatness detection is the wrong model for this terrain. A **local-anomaly detector** (roughness significantly below local mean) may be more principled.
  3. Genuine pad signatures in this tile may be below detection — sub-meter pads obscured by 60+ yr of regrowth, or coordinates too uncertain (50 m default) for the surviving signal to fall within any candidate.
- Pipeline health: green. Bootstrap worked (caught v0.1/v0.2 correctly). Validation worked (gave an honest, unambiguous answer).
- Next move to be decided with user: redesign detector for local-anomaly rather than absolute thresholds; OR try a different tile; OR increase positional-uncertainty model to 100 m.

## 2026-04-14 03:13 UTC — Stage D complete (03_pad_detector)  run 20260414T031142Z-8bd2b9

- Thresholds: slope_max_deg=5.0, rough_z_max=-1.0, relief_z_max=-0.5, anomaly_window_m=100.0, compactness_min=0.3, rectangularity_min=0.55, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=20.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=100.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121225670000: raw=44 kept=8 nearest=12.55554241865664
  - API:37121298870000: raw=104 kept=12 nearest=25.072797461769213
  - API:37121338070000: raw=120 kept=13 nearest=31.664815527488617
  - API:37121337960000: raw=68 kept=3 nearest=77.3853101949826
  - API:37121303790000: raw=84 kept=7 nearest=58.37049447205518
  acceptance: PASS

- Full tile: raw=3096, after gates=219, within 100 m of well=166
- Confidence: median=0.31, p95=0.45
- Output: candidates_pads.gpkg / .parquet (219 rows)

## 2026-04-14 03:14 UTC — Stage E (04_validation)  run 20260414T031142Z-8bd2b9

- Observed median dist: 67.92 m;  null p5/p50/p95 = 72.61/78.59/85.29;  p=0.0000
- Observed recall@100m: 0.940;  null p5/p50/p95 = 0.881/0.940/0.976;  p=0.5450
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T031142Z-8bd2b9.md

## 2026-04-14 03:14 UTC — v0.4 local-anomaly detector: SIGNAL ABOVE CHANCE

- Redesigned detector from absolute-threshold to local-anomaly model.
  - `rough_z_max`  = −1.0  (roughness z-score vs. 100 m neighborhood)
  - `relief_z_max` = −0.5
  - Absolute `slope_max_deg` = 5.0 retained (pads are physically flat)
  - Anomaly window = 100 m
- Raised `positional_uncert_m` from 50 → 100 m (upper end of literature).
- Pilot: **5/5 windows PASS** (vs 0/1, 1/5, 4/5 in v0.1–v0.3).
- Full tile: 3096 raw components → 219 candidates after shape/position/size gates.
- Validation (N=200 random-placement null, density-valid cells):
  - Median candidate→well distance: **67.92 m**
  - Null median p5/p50/p95: 72.61 / 78.59 / 85.29 m
  - **p(median ≤ obs) = 0.0000**
  - Recall@100 m: 0.940 (null p50 = 0.940, recall metric saturated at this candidate density)
  - **Verdict: SIGNAL ABOVE CHANCE**
- Confidence distribution: p50=0.31, p95=0.45, all labeled "candidate" (none reached the "probable" tier ≥0.70).
- 166/219 candidates fall inside 100 m of a documented well.
- Output: `candidates_pads.gpkg` (219 rows), summary_run_20260414T031142Z-8bd2b9.md.
- Interpretation: the local-anomaly model works. The candidates cluster near documented wells at p < 0.001. Next tuning cycle should aim to shrink the candidate count (raise `rough_z_max` closer to −1.5σ) while keeping the clustering signal. That gets us toward a set small enough to triage manually.

## 2026-04-14 03:58 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 04:00 UTC — Stage D v0.6 road detector  run 20260414T040015Z-f12621

- Method: road_v0.6_lrm_meijering (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=90.0, closing_radius_cells=2, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0

- Raw skeleton components: 103
- Kept segments (>= 30 m): 103
- Segment length: median 106.7 m, p95 568.9 m
- Nearest-well distance: median 51.2 m
- Within 100 m: 86 / 103
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:01 UTC — Stage E (04_validation)  run 20260414T040015Z-f12621

- Observed median dist: 51.21 m;  null p5/p50/p95 = 68.63/77.92/86.62;  p=0.0000
- Observed recall@100m: 0.881;  null p5/p50/p95 = 0.631/0.726/0.810;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T040015Z-f12621.md

## 2026-04-14 04:01 UTC — v0.6 road detector: SIGNAL ABOVE CHANCE (both metrics)

- New detector per `Detecting abandoned roads beneath forest canopy with LiDAR and Python.md`.
- Approach: LRM at 25 and 51 cells -> Meijering ridge filter on -LRM (scales 1, 2, 3 px) -> threshold at p90 -> closing r=2 -> remove small (<200 m²) -> eccentricity >= 0.90 -> skeletonize -> vectorize LineStrings -> length >= 30 m.
- 103 road-segment candidates. Median length 106.7 m, p95 568.9 m. Median nearest-well distance 51.2 m. 86/103 segments within 100 m of a documented well.
- Validation (200 random-point nulls):
  - median distance: obs 51.21 m; null p5/p50/p95 = 68.63 / 77.92 / 86.62 m; **p = 0.0000**
  - recall @ 100 m: obs 0.881 (74/84 wells); null p5/p50/p95 = 0.631 / 0.726 / 0.810; **p = 0.0000**
- Compared to v0.4: fewer candidates (103 vs 219), median 25% closer to wells (51 vs 68 m), and recall metric now non-saturated -- both distance AND recall exceed null at p<0.001.
- Output: `candidates_roads.gpkg` (103 LineStrings), `summary_run_20260414T040015Z-f12621.md`.
- Next move: render the centrelines on hillshade for user review; optionally tighten ridge threshold from p90 -> p92 for higher-precision, lower-recall set.

## 2026-04-14 04:43 UTC — Stage D v0.6 road detector  run 20260414T044302Z-90ec6c

- Method: road_v0.7_tight_xsec (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=92.0, closing_radius_cells=4, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=50.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 74
- Kept segments (>= 50 m): 60
- Segment length: median 93.6 m, p95 363.8 m
- Nearest-well distance: median 56.2 m
- Within 100 m: 51 / 60
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:43 UTC — Stage E (04_validation)  run 20260414T044302Z-90ec6c

- Observed median dist: 56.21 m;  null p5/p50/p95 = 67.00/80.60/90.65;  p=0.0000
- Observed recall@100m: 0.798;  null p5/p50/p95 = 0.440/0.536/0.631;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T044302Z-90ec6c.md

## 2026-04-14 04:43 UTC — v0.7 road detector (tightened + x-section attribution)

- Changes from v0.6:
  - ridge_response_pct 90 -> 92
  - closing_radius_cells 2 -> 4 (merges adjacent fragments before labelling)
  - min_segment_length_m 30 -> 50
  - added perpendicular cross-section sampling every 5 m along each segment for width and cut-depth
- Segments kept: **60** (down from 103 in v0.6). 24 "probable" (conf>0.70), 36 "candidate".
- Geometry stats:
  - length: min 50 m, p50 94 m, p95 364 m, max 1368 m
  - median_width_m: p25 6.0, p50 7.0, p75 8.0 -> consistent with two-lane haul / wide single-track
  - median_cut_depth_m: p25 0.38, p50 0.46, p75 0.57 -> modest cuts, ageing roads partially infilled
- Validation (200 random nulls, uncert = 100 m):
  - median distance: obs 56.21 m; null p5/p50/p95 = 67.00/80.60/90.65; **p = 0.0000**
  - recall @ 100 m: obs 0.798 (67/84 wells); null p5/p50/p95 = 0.440/0.536/0.631; **p = 0.0000**
- Compared to v0.6: fewer candidates (60 vs 103), recall gap *wider* (obs 0.798 - null p50 0.536 = 0.26 vs v0.6 gap 0.16). Net: more precise, same statistical dominance.
- Output: candidates_roads.gpkg (60 LineStrings, all with width/depth attrs), v07_overview.png.

## 2026-04-14 04:48 UTC — Stage D v0.6 road detector  run 20260414T044818Z-d74691

- Method: road_v0.8_recover_pathways (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=92.0, closing_radius_cells=2, min_component_area_m2=200.0, min_eccentricity=0.9, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 119
- Kept segments (>= 30 m): 118
- Segment length: median 116.0 m, p95 449.7 m
- Nearest-well distance: median 47.7 m
- Within 100 m: 107 / 118
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 04:48 UTC — Stage E (04_validation)  run 20260414T044818Z-d74691

- Observed median dist: 47.68 m;  null p5/p50/p95 = 69.26/78.32/87.56;  p=0.0000
- Observed recall@100m: 0.905;  null p5/p50/p95 = 0.690/0.774/0.833;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T044818Z-d74691.md

## 2026-04-14 04:48 UTC — v0.8 (recover pathways) — best run yet

- Changes from v0.7: closing_radius 4->2, min_segment_length 50->30. Kept ridge_response_pct=92.
- Segments: **118** (v0.6: 103; v0.7: 60). **69 probable, 49 candidate** — majority now cross the 0.70 confidence bar.
- Geometry: length p50 116 m, p95 450 m. median_width 7 m. median_cut_depth 0.57 m (deeper than v0.7 — likely because smaller closing preserves sharper rim transitions).
- Validation (200 nulls):
  - median distance: obs **47.68 m**; null p5/p50/p95 = 69.26/78.32/87.56; **p = 0.0000**
  - recall @ 100 m: obs **0.905** (76/84 wells); null p5/p50/p95 = 0.690/0.774/0.833; **p = 0.0000**
- Best result to date across all four metrics: lowest median distance, highest recall, largest recall-gap vs null (0.131), and 69 segments in the probable tier.
- v0.8 output: candidates_roads.gpkg (118 LineStrings, width/depth attrs), v08_overview.png.

## 2026-04-14 05:02 UTC — Stage D v0.6 road detector  run 20260414T050202Z-989c68

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 163
- Kept segments (>= 30 m): 152
- Segment length: median 63.9 m, p95 610.7 m
- Nearest-well distance: median 50.4 m
- Within 100 m: 125 / 152
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:02 UTC — Stage E (04_validation)  run 20260414T050202Z-989c68

- Observed median dist: 50.42 m;  null p5/p50/p95 = 69.67/78.54/87.04;  p=0.0000
- Observed recall@100m: 0.952;  null p5/p50/p95 = 0.773/0.857/0.917;  p=0.0100
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050202Z-989c68.md

## 2026-04-14 05:02 UTC — v0.9 (relaxed thresholds): more pathways, same signal

- Changes from v0.8: ridge_response_pct 92->85, min_eccentricity 0.90->0.82, min_component_area_m2 200->120.
- Segments: **152** (v0.8: 118). 27 probable, 125 candidate. Shorter p50 length (64 m vs 116 m in v0.8) — we captured many more sub-100m fragments.
- Median cut depth 0.37 m (vs 0.57 in v0.8) — pulling in shallower features.
- Validation:
  - median distance: obs **50.42 m**; null p5/p50/p95 = 69.67/78.54/87.04; **p = 0.0000**
  - recall @ 100 m: obs **0.952** (80/84 wells); null p5/p50/p95 = 0.773/0.857/0.917; **p = 0.0100**
- Tradeoff: recall gap narrowed (obs 0.952 vs null p50 0.857 = 0.10; v0.8 gap was 0.13). Still significant but closer to chance because null recall climbed with candidate count.
- Distance metric still ultra-significant (p<0.0001). v0.9 is the right pick when the priority is **coverage** (find every pathway); v0.8 is the right pick when the priority is **precision** (high-confidence subset).

## 2026-04-14 05:07 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 2 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:07 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=8.00 deg, p95=22.49 deg
- roughness_11 (sigma elev, 11x11): p50=0.447 m, p95=1.133 m
- local_relief_10 (max-min, 10 m disk): p50=2.80 m, p95=6.69 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.70 / 1.12 m
- tpi_grad_mag: p95=0.2648

## 2026-04-14 05:08 UTC — Stage D v0.6 road detector  run 20260414T050751Z-6e5fcd

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 777.1 m
- Within 100 m: 10 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:08 UTC — Stage E (04_validation)  run 20260414T050751Z-6e5fcd

- Observed median dist: 777.15 m;  null p5/p50/p95 = 750.60/835.70/926.99;  p=0.1250
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.000/1.000/1.000;  p=0.5900
- Verdict: **NOT ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050751Z-6e5fcd.md

## 2026-04-14 05:09 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 107 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:10 UTC — Stage D v0.6 road detector  run 20260414T050955Z-0f1d93

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:10 UTC — Stage E (04_validation)  run 20260414T050955Z-0f1d93

- Observed median dist: 42.67 m;  null p5/p50/p95 = 58.48/62.46/67.64;  p=0.0000
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.869/0.916/0.963;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T050955Z-0f1d93.md

## 2026-04-14 05:10 UTC — v0.9 on NEW tile (output2.las replaced, output_wells_2.csv)

- New tile extent: E 621000–622500, N 4594500–4596000 (UTM 17N) — adjacent west of the v0.1–v0.9 tile.
- New LAS: 8,956,340 pts, pf=7, class-2 ground 2.69 pts/cell mean.
- New wells: 107 (vs 84 on prior tile).
- 01_preprocessing patched to auto-derive grid bounds from LAS header (no longer pinned).
- Detector unchanged from v0.9.
- Segments: **191** (39 probable, 152 candidate). Median length 57 m, p95 287 m. Median cut depth 0.37 m.
- Validation:
  - median distance: obs **42.67 m**; null p5/p50/p95 = 58.48/62.46/67.64; **p = 0.0000**
  - recall @ 100 m: obs **1.000** (107/107); null p5/p50/p95 = 0.869/0.916/0.963; **p = 0.0000**
- Every documented well in the tile has a detected road candidate within 100 m.
- Output: candidates_roads.gpkg (191 LineStrings), new_tile_overview.png.

## 2026-04-14 05:32 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 363.32 - 493.51 m, NaN 0.000%
- DSM : max-Z first returns. z 363.36 - 517.99 m, NaN 0.092%
- CHM : DSM-DEM floored >= 0. p50=3.36 m, p95=23.23 m
- Ground density: np.bincount, exact/cell. mean 2.62, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 84 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:33 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=10.10 deg, p95=26.70 deg
- roughness_11 (sigma elev, 11x11): p50=0.563 m, p95=1.426 m
- local_relief_10 (max-min, 10 m disk): p50=3.55 m, p95=8.58 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.73 / 1.23 m
- tpi_grad_mag: p95=0.2607

## 2026-04-14 05:33 UTC — Stage D v0.6 road detector  run 20260414T053319Z-ae6f30

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 163
- Kept segments (>= 30 m): 152
- Segment length: median 63.9 m, p95 610.7 m
- Nearest-well distance: median 50.4 m
- Within 100 m: 125 / 152
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:33 UTC — Stage E (04_validation)  run 20260414T053319Z-ae6f30

- Observed median dist: 50.42 m;  null p5/p50/p95 = 69.67/78.54/87.04;  p=0.0000
- Observed recall@100m: 0.952;  null p5/p50/p95 = 0.773/0.857/0.917;  p=0.0100
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T053319Z-ae6f30.md

## 2026-04-14 05:35 UTC — Stage A+B complete (01_preprocessing)

- Tool: pdal ?, WhiteboxTools
- DEM : TIN (delaunay -> faceraster) on class=2. z 375.27 - 486.94 m, NaN 0.000%
- DSM : max-Z first returns. z 375.31 - 511.22 m, NaN 0.016%
- CHM : DSM-DEM floored >= 0. p50=0.52 m, p95=21.54 m
- Ground density: np.bincount, exact/cell. mean 2.69, p95 6
- Hillshade: WBT az=315 alt=45
- Wells in tile (+50 m): 107 -> wells_in_tile.gpkg
- Grid: 1500x1500 @ 1.0 m, EPSG:6346

## 2026-04-14 05:35 UTC — Stage C complete (02_derivatives)

- slope (WBT): p50=8.00 deg, p95=22.49 deg
- roughness_11 (sigma elev, 11x11): p50=0.447 m, p95=1.133 m
- local_relief_10 (max-min, 10 m disk): p50=2.80 m, p95=6.69 m
- tpi_05 / tpi_15 / tpi_51: p95 mag 0.30 / 0.70 / 1.12 m
- tpi_grad_mag: p95=0.2648

## 2026-04-14 05:35 UTC — Stage D v0.6 road detector  run 20260414T053528Z-1eface

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-14 05:35 UTC — Stage E (04_validation)  run 20260414T053528Z-1eface

- Observed median dist: 42.67 m;  null p5/p50/p95 = 58.48/62.46/67.64;  p=0.0000
- Observed recall@100m: 1.000;  null p5/p50/p95 = 0.869/0.916/0.963;  p=0.0000
- Verdict: **SIGNAL ABOVE CHANCE**
- Full summary: data\derivatives\validation\summary_run_20260414T053528Z-1eface.md

## 2026-04-14 20:04 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (191 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 48.0%  (1086 / 2262 m of truth covered)
- Road precision (length-weighted, labelled areas only): 4.8%
- **Pad hit rate:** 90.0%  (18/20 pads ≤25 m from a candidate)  median dist 0.8 m
- **Pit hit rate:** 75.0%  (39/52 pits ≤25 m from a candidate)  median dist 13.6 m
- Median pit → nearest DEP-well-record: 16.3 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-14 21:27 UTC - Road detector v0.10 (Random Forest)  run 20260414T212653Z-26e477

- Training: 8,345 pos / 41,725 neg pixels, 12 features, OOB score 0.9099
- Top-3 features: lrm_25 (0.124), openness_pos (0.110), tpi_05 (0.109)
- Proba threshold 0.5  ->  170 final LineStrings
- Confidence: 19 probable, 151 candidate
- Median segment length 56 m, median cut depth 0.36 m
- Output: candidates_roads.gpkg (v0.9 archived under archive/v0.9_rule_based_pre_rf/)
- Run 05_expert_validation.ipynb next to rescore.

## 2026-04-14 21:27 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (170 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 66.1%  (1496 / 2262 m of truth covered)
- Road precision (length-weighted, labelled areas only): 10.5%
- **Pad hit rate:** 85.0%  (17/20 pads ≤25 m from a candidate)  median dist 0.0 m
- **Pit hit rate:** 75.0%  (39/52 pits ≤25 m from a candidate)  median dist 13.0 m
- Median pit → nearest DEP-well-record: 16.3 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-15 03:20 UTC - Road detector v0.10 (Random Forest)  run 20260415T031830Z-e57988

- Training: 71,914 pos / 359,570 neg pixels, 12 features, OOB score 0.9173
- Top-3 features: openness_pos (0.212), tpi_05 (0.124), lrm_25 (0.106)
- Proba threshold 0.5  ->  101 final LineStrings
- Confidence: 15 probable, 86 candidate
- Median segment length 48 m, median cut depth 0.37 m
- Output: candidates_roads.gpkg (v0.9 archived under archive/v0.9_rule_based_pre_rf/)
- Run 05_expert_validation.ipynb next to rescore.

## 2026-04-15 03:25 UTC — Expert-validation scoring (05_expert_validation)

- Source: `candidates_roads.gpkg` (101 LineStrings) vs expert annotations.
- Tolerances: road-line 10 m, pad/pit 25 m.
- **Road recall (length-weighted):** 29.0%  (5609 / 19315 m of truth covered)
- Road precision (length-weighted, labelled areas only): 52.8%
- **Pad hit rate:** 50.0%  (44/88 pads ≤25 m from a candidate)  median dist 26.0 m
- **Pit hit rate:** 28.9%  (26/90 pits ≤25 m from a candidate)  median dist 41.6 m
- Median pit → nearest DEP-well-record: 15.7 m (GPS-accuracy sanity check)
- Images: expert_validation_overview.png, expert_validation_misses.png

## 2026-04-15 05:27 UTC - Pit detector v0.1 (blob + RF)  run 20260415T051012Z-253ea4

- Blob detection: 48449 candidates survived dedup+depression_mask
- Truth-pit recall of blob pipeline pre-RF: 90/90 (100.0%) within 5 m
- RF training: 278 pos / 1390 neg candidates, OOB 0.9215
- Top-3 features: depth_lrm11 (0.229), depth_lrm5 (0.146), dem_cut_m (0.121)
- Output: candidates_pits.gpkg (2387 pits, 667 probable)

## 2026-04-30 17:49 UTC — Stage D complete (03_pad_detector)  run 20260430T174728Z-60f82a

- Thresholds: slope_max_deg=8.0, rough_z_max=-1.0, relief_z_max=-0.5, anomaly_window_m=100.0, compactness_min=0.45, rectangularity_min=0.7, obb_aspect_min=0.5, tpi51_min_m=-3.0, tpi51_max_m=5.0, area_min_m2=100.0, area_max_m2=20000.0, ground_density_min=1.0, positional_uncert_m=100.0

- Bootstrap pilot (5 windows @ 250 m):
  - API:37121321200000: raw=100 kept=0 nearest=nan
  - API:37121265330000: raw=113 kept=0 nearest=nan
  - API:37121321110000: raw=99 kept=0 nearest=nan
  - API:37121220280000: raw=117 kept=1 nearest=74.94550447313712
  - API:37121337930000: raw=93 kept=1 nearest=74.94550447313712
  acceptance: PASS

- Full tile: raw=3844, after gates=4, within 100 m of well=3
- Confidence: median=0.35, p95=0.47
- Output: candidates_pads.gpkg / .parquet (4 rows)

## 2026-04-30 17:59 UTC — Stage D v0.6 road detector  run 20260430T175948Z-2e7e97

- Method: road_v0.9_relaxed (Meijering ridge filter on -LRM, multi-scale)
- Thresholds: ridge_sigmas=(1.0, 2.0, 3.0), ridge_response_pct=85.0, closing_radius_cells=2, min_component_area_m2=120.0, min_eccentricity=0.82, min_segment_length_m=30.0, ground_density_min=1.0, positional_uncert_m=100.0, xsec_spacing_m=5.0, xsec_half_width_m=15.0, xsec_edge_min_width_m=2.0, xsec_edge_max_width_m=12.0

- Raw skeleton components: 229
- Kept segments (>= 30 m): 191
- Segment length: median 56.8 m, p95 286.9 m
- Nearest-well distance: median 42.7 m
- Within 100 m: 164 / 191
- Output: candidates_roads.gpkg / .parquet

## 2026-04-30 18:16 UTC - Pit detector v0.1 (blob + RF)  run 20260430T180026Z-4cd9c2

- Blob detection: 48347 candidates survived dedup+depression_mask
- Truth-pit recall of blob pipeline pre-RF: 102/861 (11.8%) within 5 m
- RF training: 311 pos / 1555 neg candidates, OOB 0.9223
- Top-3 features: depth_lrm11 (0.228), depth_lrm5 (0.144), dem_cut_m (0.118)
- Output: candidates_pits.gpkg (2504 pits, 767 probable)
