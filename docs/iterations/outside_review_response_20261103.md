# Response to the outside review of the NISAR and change-detection decisions (2026-11-03)

An outside evaluator reviewed the project read-only and sent two memos. This doc records each point, what we checked ourselves, what we fixed, and what we now state more narrowly.

Status words. **Reproduced** means we re-ran the check and got the same number. **Confirmed in code** means we read the code or files and the defect is there. **Reviewer only** means we have not re-run it. **Fixed**, **Disclosed** or **Open** say what happened next.

## 1. The two decisions, as the reviewer put them

- **NISAR.** Leaving it out holds for pits (tile 613590 held-out, 36 pits in 8 blocks, gain -0.017, every resampling gives an upper 95% bound of +0.018 or less, so +0.05 is excluded). For pads it holds only inside tile 9t. No pad held-out test exists.
- **Change detection.** The two surveys can see decimetre change at pad size on gentle ground. The project has not shown well-related change. Pad "changed" flags occur at about the false-alarm rate.

We agree with both. Our own wording was wider than this in places. Section 5 gives the narrowed wording.

## 2. Change detection

| # | Point | Status | What we did |
|---|---|---|---|
| C1 | Pad flags (4.5%) match a placebo rate (4.7%). `expected_false = 0.025 n` was an assumption. | Reviewer only. The assumption is **confirmed in code**. | **Fixed.** `_change_features_9t.py` now measures a placebo rate (each feature's controls flagged against the others, leave one out) and matches controls on slope (within 3 deg). The summary reports `placebo_rate` and `expected_false_measured`. Re-run on both surfaces. See section 4. |
| C2 | The "change is real in aggregate (~21 SD)" claim fails once noise is scaled for slope. 205 patches against a 339 +/- 10 null. | **Reproduced** from `_classify_9t_lineadj_z.json` (205 observed, null 339 +/- 9.9, ratio 0.6, area 1.34x, 12 fluvial patches above 4,092 m2, 0 non-erosional). | **Disclosed.** Part 4's aggregate claim is withdrawn. Part 5 of `icp_change_9t.md`. |
| C3 | The preliminary surface `dod_9t_2m.tif` shares no structure with the rebuilt ones. | **Reproduced.** Raw correlation with the single-ICP surface is r = -0.07. | **Disclosed.** Part 1's "no change at wells" and the 367-patch product are marked invalid. The well test is circular (Part 3) and the preliminary surface is anti-correlated, so there is no valid wells test in either direction. |
| N1 | Link to well activity rests on one lease (Kornman RK). 8 of 18 flagged pads belong to 2 complexes. | Reviewer only. | **Disclosed.** No well attribution is claimed. |
| N2 | Detection floor 0.16 to 0.22 m at pad size on slopes under 15 deg, 0.4 to 0.6 m above. | Reviewer only. Direction agrees with our slope noise fit (0.062 m flat, 0.181 m above 25 deg). | **Disclosed.** |
| N3 | Residual horizontal offset about 0.2 m, not 0.10 m. | Reviewer only. | **Open.** Would add about 0.06 m bias at 15 deg. |
| E1 | The per-pass correction can erase pass-wide real change (an injected +0.25 m rise came back as 0.004 m). | By construction. The offset is the median over gentle ground of the whole pass. | **Disclosed.** The 400 m high-pass does the same for anything wider than 400 m. Neither step can see broad change. |
| E2 | Column seams (9,505 cells) are not fixed by the per-pass correction (9,502). | **Reproduced.** We reported it ourselves on 2026-11-03. | **Open.** Source not found. The 2019 flight lines are the first candidate. |
| E3 | Patch outlines are incomplete. `shapes()` is 4-connected and only the first polygon was kept. | **Confirmed in code.** Outline area is under 90% of the attribute area in 47 of 367, 12 of 240, 15 of 205 patches. | **Fixed.** 8-connected, all pieces unioned. Patch sets rebuilt. The seam, evidence-sheet and land-cover tables that read the outlines were re-run or flagged. |
| E4 | `threshold_m = 3.079` in the lineadj_z JSON is in z units. | **Confirmed in code.** | **Fixed.** The JSON now has `threshold`, `threshold_units` and `threshold_m_on_flat_ground`. |
| E5 | Pit flags (134 of 501) are the sparse 2006 survey flattening rims, not change. | Reviewer agrees with our "artifact" reading. Our later test did not support it. At near-equal point density the flags stay (129 of 436). | **Corrected.** Pits are unassessable and the cause is open. Section 8. |
| E6 | `lineadj_z` outputs appeared at 09:25 from "another process". | That was us. The run was started from the call you interrupted, and it ran anyway. | **Disclosed.** The outputs are ours and are reproducible with `--source lineadj --zscale`. |
| E7 | Vertical datum. Old heights are NAVD88 (GEOID03), new are GEOID12B. The code converts units only. | Confirmed in code. | **Open.** Geoid realizations differ by centimetres. A median near zero after fitting cannot validate the datum. |
| E8 | Flight dates unknown. The header date is a processing date. Point times are GPS week seconds. | Reviewer only. Our 2003-06 aerial date was already flagged as unconfirmed. | **Open.** Blocks any before/after test of a dated well. |

## 3. NISAR

| # | Point | Status | What we did |
|---|---|---|---|
| G1 | The +0.05 gate cannot be met on 9t pits (rich lidar 0.968, needs 1.018). | **Reproduced** by arithmetic. | **Fixed in wording.** `nisar/writeup/README.md` now says "no gain" and "no room" cannot be told apart on 9t pits. The held-out test is the one that can. |
| G2 | The held-out test excludes +0.05 for pits on 613590. Radar alone 0.658 (95% 0.47 to 0.82). | Reviewer only, but our reported 0.658 matches their 0.658. | Cited in the pre-registration addendum. |
| G3 | No pad held-out test. | Agree. 613590 has 0 annotated pads. | **Open.** Needs a second tile with pad labels made without the radar. |
| N4 | The test is less independent than described. 613590 pits were scored on 2026-10-14 and 2026-10-19. The pre-registration rule contradicts itself. The 9t samples were regenerated after the commit. | **Confirmed.** `git diff a8a38c00..HEAD` shows a refactor of `_nisar_feat_common.py` (model moved into `fit_predict`, same settings) and a new held-out script. | **Disclosed** in an addendum to `nisar_heldout_613590_prereg.md`. The original text is untouched. The rule is restated. |
| N5 | The documented registration figure "about 10 m" is wrong both ways. | **Confirmed.** Our log has 46 of 48 within 2.5 m on 9t and 31 of 48 on 613590 (worst 29.7 m). | **Fixed** in `nisar/docs/NISAR_METHODS.md`, `nisar_checks_9t.md`, `nisar_corrected_rescoring_9t.md` and `nisar/writeup/README.md`. The check is internal (same lidar), so it is still not independent. |
| N6 | Radar (2025-10 to 2026-10) cannot date or corroborate a 2006 to 2019 earthwork. | Agree. | **Disclosed.** |
| R1 | Reproducibility. The held-out run saved no per-row scores. 3,879 of 4,890 9t decoys lie within 10 m of another decoy. Counts disagree across docs (8/11/14 against 10/11/15 dates, 4.9 against 4.5 km tile). `nisar/docs/NISAR_METHODS.md` still said "no held-out area". | Partly confirmed. The 8/11/14 and 10/11/15 figures are two different stacks (SLC after the bad-date drop, GSLC before). `nisar/docs/NISAR_METHODS.md` is **fixed**. | **Open.** Save per-row scores in the next held-out run. Reconcile the tile size (the lidar box is 4.5 km, the NISAR window is wider). |

## 4. Results of the re-runs

Pad, road and pit "changed" flags, slope-matched controls, measured placebo rate (`data/9t/results/change/change_features_summary_9t.json` for the rebuilt surface, `data/9t/results/change/change_features_summary_lineadj_9t.json` for the per-pass-corrected one).

| Feature | Surface | Measured | Flagged | Placebo rate | Expected by chance (measured) |
|---|---|---:|---:|---:|---:|
| Pads | rebuilt | 404 | 18 (4.5%) | 4.0% | 16.3 |
| Pads | per-pass corrected | 404 | 18 (4.5%) | 4.0% | 16.1 |
| Roads | rebuilt | 674 | 31 (4.6%) | 3.2% | 21.4 |
| Roads | per-pass corrected | 680 | 30 (4.4%) | 3.1% | 20.9 |
| Pits (unassessable, cause open) | rebuilt | 438 | 120 (27%) | 3.9% | 17.2 |
| Pits (unassessable, cause open) | per-pass corrected | 438 | 126 (29%) | 3.8% | 16.5 |

Pad and road flags sit at the false-alarm rate. About 16 of the 18 flagged pads and about 21 of the 31 flagged roads are what chance gives. The reviewer's 4.7% placebo is reproduced (we get 4.0%). Slope matching leaves a median of 18 controls per pad (24 per road), down from 40, so each test is coarser. The earlier summary (`expected_false` = 0.025 n) understated chance by about half.

Patch outlines after the fix. Zero outlines are under 90% of their attribute area (it was 12 of 240 and 15 of 205). Patch counts and nulls did not change (240 patches, null cutoff 7,888 m2 for the rebuilt surface. 205 patches, null 339 +/- 10, cutoff 4,092 m2 for the slope-normalised one). Land-cover read of the corrected outlines: 22 of 26 "anthropogenic" patches are deciduous forest on the slope-normalised set. 15 to 17 patches are mostly non-forest. Patch 1026 was read as forest to developed from a 64 m2 fragment. With the full outline it is forest in both years.

Visual read of five "anthropogenic" patches on `data/9t/results/change/sheets/change_evidence_sheet_anthropogenic_1_9t.png` (one reader, not validated):

| Patch | What the photos and hillshades show |
|---|---|
| 267 | Bare graded ground with a loop road in 2020. But the patch abuts the edge of the 2006 lidar coverage (the grey void and black edge in the 2006 hillshade). Edge effect cannot be excluded. Unvalidated. |
| 836 | A farmstead with a pond and a yard. Same layout in both aerials. Not an earthwork. Likely tree removal or a ground-class change. |
| 899 | A bare patch in forest in 2020 that is not visible in the 2003-06 aerial. A cut with a fill below it, and a pit in the 2019 hillshade. The most convincing candidate of the five. |
| 20 | A broad, diffuse change tint with no edge, no morphology in either hillshade and nothing in the 2020 aerial. Reads as noise or a regional bias. This agrees with Gemini's expectation. |
| 1530 | A cut at a trail junction. New linear trace in the 2019 hillshade. Plausibly skid-trail work. Unvalidated. |


## 5. Narrowest defensible wording, adopted

**NISAR.** On tile 9t and on 36 pits in 8 blocks of tile 613590, adding beta and provisional NISAR temporal and texture features at 5 m to a 26-band lidar texture model did not improve pit detection (gain -0.017). A gain of +0.05 is excluded for pits there. Radar alone separates held-out pits from tile-wide decoys at 0.66. Pad conclusions are within 9t only. Registration is checked internally only (46 of 48 blocks on 9t, 31 of 48 on 613590).

**Change detection.** On 9t the 2006-08 and 2019 surveys can detect pad-sized mean change of about 0.16 to 0.22 m on slopes under 15 deg, and are near-blind below about 0.4 to 0.6 m on steeper ground. Pad flags occur at about the placebo rate. The survey pair cannot recover change wider than about 400 m, cannot assign a patch to well activity from proximity, and cannot assess pits. The earlier claim that change exceeds noise in aggregate is withdrawn.

## 6. Decisive next tests (the reviewer's, adopted)

1. **NISAR pad transfer.** A second tile with pads labelled without the radar. Local decoys. Model, bands and decoy rule frozen and committed before scoring. Pass if the gain is at least +0.05 and the lower bound is above 0. Save per-row scores.
2. **Dated-well change test.** Get the real 2006-08 flight dates. Freeze the rule (slope-normalised field, footprint, threshold, placebo controls). Compare wells with DEP activity confirmed after the flight against slope- and cover-matched wells with only pre-2000 activity, at the complex level, over several tiles. 9t has only 2 qualifying complexes.
3. **Pads 926 to 928.** Site-dated imagery or grading records, reviewed blind to the flags, against the full raster components.

## Files changed in this pass

- `notebooks/wellsight_v2/s7_analysis/_icp_change_classify_9t.py` (polygon export, threshold units)
- `notebooks/wellsight_v2/s7_analysis/_change_features_9t.py` (slope-matched controls, placebo rate, `--field`)
- `notebooks/wellsight_v2/s7_analysis/_change_landcover_9t.py` (both patch sets, z-field columns)
- `nisar/docs/iterations/nisar_heldout_613590_prereg.md` (addendum), `nisar/docs/NISAR_METHODS.md`, `nisar/docs/iterations/nisar_checks_9t.md`, `nisar/docs/iterations/nisar_corrected_rescoring_9t.md`, `nisar/writeup/README.md`

## 7. A second review, by Gemini (`ADVERSARIAL_AUDIT_DECISION_MEMO.md`, dated 2026-11-03)

It reaches the same two verdicts. Exclude NISAR. Do not use the epoch pair for well change. Most of it repeats the first review. Where it differs we checked it.

| Gemini point | Check | Result |
|---|---|---|
| NISAR tests with no headroom are uninformative (U-Net fusion 0.999, clearing confusers 0.988). Only pit held-out, pad local 1,500 m and lidar-weak pads can speak. | Agree. Same as G1 above. | Adopted. The section 5 wording already limits the claim to those tests. |
| Radar pad skill is a place effect (AUC rises with decoy distance 0.44 to 0.71, x/y 0.38 to 0.96). | Agree. It is in our docs. | No change. |
| The ~10 m registration residual could blur pits. | Partly. The internal check says 46 of 48 within 2.5 m on 9t and 31 of 48 on 613590. The first reviewer's shift test peaked at zero offset. | See N5. Not independently confirmed. |
| Raw 2006-08 LAZ are unmounted (C1). | **Out of date.** All four tiles are now local in `data/9t/derived/lidar_2006_2008/`. | Stale. |
| Minimum detectable change at pad or pit scale exceeds 1.5 to 2.0 m. | **Disagree.** The first reviewer measured 0.16 to 0.22 m for a median pad on slopes under 15 deg (80% power), and an injected +0.25 m on a pad footprint was flagged 93% of the time. Our slope fit gives sigma 0.062 m on flat ground. | Not adopted. The memo gives no test for the 1.5 to 2.0 m figure. |
| False-alarm density is 1.1 to 1.3 per km2. | **Mislabelled.** 22 to 26 is the count of observed "anthropogenic" patches, not false alarms. The IAAFT null gave 4.4 per km2 (rebuilt) and 16.7 per km2 (slope-normalised) of components of 200 m2 or more. | Not adopted as stated. |
| Patches 267 and 20 are "invented", and 267 is a dipole across a road cut. | The preliminary surface is anti-correlated with the rebuilt one (r = -0.07), so anything seen only there, or flipped by it, is not evidence. We cannot confirm "dipole" from the sheet. 267 sits at the edge of the old coverage. | Partly adopted. 267 and 20 stay unvalidated. |
| Decisive test: aerial triage of #20 and #391 with NAIP. | NAIP is leaf-on. We already hold the 2003-06 statewide aerial and the 2020 leaf-off PEMA, which are better for earthwork. #20 is done above. #391 is on `change_evidence_sheet_anthropogenic_2_9t.png` and has not been read. | #20 shows nothing at its footprint. #391 open. |
| Residual horizontal offset about 0.10 m. | The first reviewer measured about 0.2 m. | We use 0.2 m (N3). |

## 8. Second pass: the open items, worked through (2026-11-03)

The first pass fixed the code defects and the wording. This pass worked the items that were only disclosed. Script for the change fixes: `notebooks/wellsight_v2/s7_analysis/_change_rebuild_v2_9t.py`. Summary: `data/9t/results/change/change_v2_summary_9t.json`. Offsets: `data/9t/results/change/change_v2_offsets_9t.csv`.

| Item | What was done | Result |
|---|---|---|
| N3 horizontal offset | Fitted d = a_e dz/dE + a_n dz/dN + c on slopes of 3 to 30 deg, per flight pass, and moved every 2006 point by its pass value. | The all-points shift is +0.15 m east and +0.22 m north (the reviewer's 0.2 m). It hides a larger spread. North is +0.34 to +0.45 m on passes 17, 18 and 20 and -0.06 to -0.11 m on 16, 19 and 21. The flight lines alternate direction. After the move every pass refits to within 0.006 m. The slope-noise coefficient fell from 0.31 to 0.22 m, so noise at 25 deg fell from 0.157 to 0.123 m. |
| E1 per-pass correction erases real change | Replaced the 2019-referenced pass medians with offsets from pairwise overlaps between neighbouring passes (real change cancels in an overlap, an instrument offset does not). Tested with +0.25 m injected over a 1 km disc. | The old method removed 12.4% of the injected change. The overlap method removed 0.2%. Caveats. Overlaps are narrow (100 to 450 shared 4 m cells per pair), the five pairs form one chain so the solve has no loop check, and the offsets run in a ramp from +0.21 to -0.12 m north to south. The raw-surface row bias is therefore worse than the old method (0.090 against 0.047 m), because the old method also removed the regional tilt. On the high-passed field, which is the one used for detection, the overlap version is slightly better. See the table below. |
| E7 vertical datum | Fitted a plane to 2006 minus 2019 on gentle ground. | Tilt is +25 mm/km north and +3 mm/km east, about 115 mm across the tile. It mixes the geoid difference with pass geometry. It is a smooth plane, so the 400 m high-pass removes it. The geoid grids were not applied. Absolute levels in the raw difference map are uncertain by about 0.1 m across the tile. The detection field is not affected. |
| E2 column seams | Checked four sources. | None matched. They are not at the 2006 tile edges (those tilt 2 deg in UTM, the seams are vertical). The 2019 survey has 4 flight lines with offsets under 0.0001 m, so it is not the 2019 flight lines. They are irregularly spaced, so not 2019 tile edges. They sit near mapped roads, drainage and pads no more than ground in general (38.6% against 34.2%). **Cause not found.** They cover 9,186 of 5.06 million cells (0.18%). |
| Equal sampling | 2019 ground points were thinned to 0.68 per m2 (the 2006 survey has 0.42). | Both surfaces are now 2 m TINs from raw points with the same code. |
| E8 flight dates | Not fixable here. The older files hold GPS week seconds and a processing date in the header. | Open. Needs a USGS flight log. |

How the three surfaces compare, on the same detection steps (destripe, 400 m high-pass):

| Surface | Robust sigma, high-passed | Row seam cells | Column seam cells | Cells beyond 3 sigma |
|---|---:|---:|---:|---:|
| One global offset | 0.0783 | 4,623 | 9,505 | 284,375 |
| Per-pass offsets against 2019 (old) | 0.0782 | 2,848 | 9,502 | 283,724 |
| **v2: per-pass shift, overlap offsets, equal sampling** | **0.0763** | **2,085** | **9,186** | **277,099** |

The gain is real but small. Row seams fall by 27% against the old per-pass method. Sigma falls by 2.4%.

Classification on the v2 surface (`--source v2 --zscale`, `data/_experiments/icp/change_9t/_classify_9t_v2_z.json`). 204 patches against a noise null of 325 +/- 11 (0.6x). Area 1.4x. 12 fluvial patches clear the 3,368 m2 noise cutoff. No non-erosional patch does (23 anthropogenic, 5 mass wasting). The conclusion of section 5 does not change.

Pad, road and pit flags on the v2 surface (`data/9t/results/change/change_features_summary_v2_9t.json`). Pads 19 of 404 against about 15 by chance (placebo 3.8%). Roads 27 of 679 against about 20 (3.0%). Pits 129 of 436 (30%, placebo 3.6%). **The pit flags did not go away when the 2019 points were thinned to near the 2006 density.** So the explanation that the sparse 2006 survey alone creates them is not enough. Other candidates are the 2006 ground classification flattening berms, or real settling. Pits stay unassessable and are not called an artifact any more.

Patch 899 and the sheets. New evidence sheets were made from the v2 patches, with complete outlines. They are `data/9t/results/change/sheets/change_evidence_sheet_<anthropogenic|mass_wasting|fluvial_top>_<k>_9t_v2z.png`. The older sheets without the `_v2z` suffix use the old fragment outlines and the old patch ids. Patch ids differ between patch sets (the old 267 is 251 in v2).

### NISAR items worked in this pass

| Item | What was done | Result |
|---|---|---|
| R1 per-row scores | `_nisar_feat_heldout_9t.py` now saves them. Re-ran. | Numbers identical to the first run (rich lidar 0.881, all NISAR 0.658, NISAR + rich 0.865, gain -0.017, bootstrap -0.055 to +0.020). Scores: `nisar/results/613590/nisar_pit_heldout_scores_613590_slc.csv`. |
| Duplicate decoys | New `_nisar_feat_dedupe_9t.py` drops every repeated decoy location and re-scores with the same folds. | **Pits** (4,890 rows, 4,392 distinct). Rich lidar 0.968 to 0.973. NISAR alone **0.829 to 0.765**. Gain -0.001 to -0.004 (95% -0.009 to -0.000). **Pads, local 1,500 m** (2,970 rows, 2,498 distinct). Rich lidar 0.923 to 0.925. NISAR alone **0.479 to 0.601**. Gain -0.016 to -0.008 (95% -0.025 to +0.003). Radar-alone AUCs move by 0.06 to 0.12 with the decoy set. The gain over lidar does not. Files: `nisar/results/9t/nisar_pit_dedupe_auc_9t_slc.csv`, `nisar_pad_dedupe_auc_9t_slc_local1500.csv`. |
| Tile size, dates per track | Reconciled. The lidar tile is 4.5 km (the DEM bounds). The NISAR window is 4.9 km. The corrected stack has 8, 11 and 14 dates. The 10, 11 and 15 belong to the GSLC stack before the bad-date drop. | Fixed in `nisar/docs/NISAR_METHODS.md`, `nisar/docs/NISAR_FINDINGS.md`, `nisar_checks_9t.md`, `nisar_corrected_rescoring_9t.md`, `nisar_pad_features_scored_9t.md`. |

The radar-alone headline numbers in `nisar/docs/NISAR_FINDINGS.md` and the write-up (0.83 for pits, 0.48 to 0.64 for pads) should be read with the de-duplicated values beside them. They are unstable, which is one more reason they are not used for any decision.

## 9. Still open

- 2006-08 flight dates (needs USGS or a flight log).
- Column-seam cause (0.18% of cells).
- Pit flags at near-equal density (cause unknown).
- No pad held-out test for NISAR, and no independent confirmation of NISAR registration.
- The overlap offsets rest on narrow overlaps and a single chain.
- The 2019 header did not parse a CRS. The points fall in the tile's UTM range and match the existing 2019 DEM, so UTM 17N is assumed.

## 10. Read of the v2 evidence sheets (one reader, not validated)

Sheets: `data/9t/results/change/sheets/change_evidence_sheet_anthropogenic_1_9t_v2z.png` and `..._2_9t_v2z.png`. Patch ids changed with the rebuild. The mapping below is by outline overlap.

| Old id | v2 id | What it shows on the v2 sheet |
|---|---|---|
| 899 | 810 | Persists (96% overlap). A bare patch in 2020 that the 2003-06 photo does not show. A cut with a fill below it, and a pit in the 2019 hillshade. Still the best candidate. |
| 1530 | 1277 | Persists. A cut at a trail junction, new linear trace in the 2019 hillshade. Plausible skid-trail work. |
| 267 | 251 | Persists. Abuts the edge of the 2006 coverage. Unvalidated. |
| 836 | 762, 767 | Persists. A farmstead and yard. Not an earthwork. |
| 20 | (33, 12% overlap) | Mostly gone. The diffuse tint no longer reaches the threshold. |
| 114 | none | Gone. |
| 109, 786 | 129, 696 | Partly gone (27% and 41% overlap). |
| 391 | 387 (now fluvial) | **Persists** (100% overlap). Not fixed by the rebuild. Its straight-edged block read as a seam. |
| new | 372, 802, 817, 49, 664 | Broad diffuse tints without morphology. Not earthwork. |

So the rebuild removed some of the seam patches (20, 114, most of 109 and 786) and not others (391). It did not create new convincing earthwork. Patches 810 and 1277 are the two to send for independent confirmation.


## Correction 2026-11-09 (second outside review, `nisar/reviews/nisar_adversarial_20261109/REPORT.md`)

- **Duplicate decoys row.** `_nisar_feat_dedupe_9t.py` keys on centre plus footprint size, not centre alone, and calls `GroupKFold` again after dropping rows, so folds were not held fixed (1,327 changed same-fold pit block pairs). The AUC shifts it reports (pits 0.829 to 0.765, local pads 0.479 to 0.601) are real but cannot be attributed to duplicate removal alone. Gains over lidar stay small and negative in both versions.
- **Held-out bound.** "Every resampling gives an upper 95% bound of +0.018 or less" is documented only. The reproducible block bootstrap from saved predictions gives +0.0198. The conclusion that +0.05 is excluded for these 36 pits stands.
- **Bad dates.** The wet/dry table, the three-sensor illustrative mean and the signal-quality table still read 2026-09-08. Fixed 2026-11-09.
