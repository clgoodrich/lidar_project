# Framework 4.9. More radar (pre-specified test of what would be different)

**Tier B.** Full design. Assumes other SAR data exist and can be obtained. Nothing here has been run, fetched or priced.
**Evidence level.** (a) drawn feature. Radar here is scored against drawn pits and pads only. It says nothing about wells.
**Depends on.** P1 split repair, P2 audit set, 3.0 scorer (for block folds and the ranking metric). 5.1 supplies the downstream gain margin.
**Blocks.** Any purchase or tasking of SAR data for this project.

## 1. Problem and objective
The tested NISAR L-band features did not add to a rich lidar texture model. The risk is to read that as "radar fails". The opposite risk is to repeat the same test with the same ceiling problem.

**Stated negative result (only this).** Tile 9t, NISAR plus rich lidar against rich lidar. Pit gain -0.004 (95% -0.009 to -0.000) and pad gain -0.008 (95% -0.025 to +0.003) in AUC after dropping repeated decoy locations. Tile 613590 held-out pits (36 pits, 8 blocks), gain -0.017 with every resampling giving an upper 95% bound at or below +0.018, so +0.05 is excluded. Pad evidence is 9t only. No pad held-out test exists.

**Ceiling caveat.** The 9t pit baseline AUC is 0.968, so a +0.05 gain would need an AUC of 1.018. On 9t pits, "no gain" and "no room" cannot be told apart. The 613590 test is the one that can.

**Objective.** Pre-specify a test in which a gain is arithmetically possible, in which the radar differs from the tested NISAR product in resolution, band, polarimetry or time depth, and in which success, failure and inconclusive are fixed before any data are scored.

**Hypotheses.** H1. At least one new SAR arm adds at least the useful gain δ_gain to the lidar baseline, scored on matched decoys in blocks the baseline model did not train on. H0. No arm does. The primary arm is named in section 3 and every other arm is exploratory.

## 2. Scope
In. Power analysis, arm definitions, acquisition specification, feature extraction for new products, scoring against drawn pits and pads.
Out. Change detection, displacement products, steel or reflector detection and anything about wells (levels b to d). Any restatement of NISAR results beyond the numbers in section 1. Any claim that all coarse sensors fail.

## 3. Definitions
- **Baseline.** The rich lidar texture model of `nisar/docs/iterations/nisar_corrected_rescoring_9t.md`, same folds, same 250 m buffer, same decoys.
- **Arm.** One SAR product family added to the baseline. Arms are listed in the table below.
- **Gain.** AUC of (arm plus baseline) minus AUC of baseline, paired on the same decoy set and the same blocks.
- **Headroom.** 1 minus baseline AUC in the stratum being scored.
- **Eligible stratum.** A stratum where headroom is at least δ_gain plus the half-width of the projected interval (section 7). Only eligible strata count toward success or failure.
- **Lidar-weak stratum.** The quartile of targets with the lowest baseline score. This is the place where a complementary sensor has room. It is chosen by the baseline score before any SAR feature is built.
- **Primary arm.** A1, the high-resolution X-band arm on pits, because pit width (about 5 to 20 m) is at or below the NISAR posting and resolution is the one factor the tested product could not vary.

| Arm | Sensor | What differs from tested NISAR | Targets |
|---|---|---|---|
| A1 primary | Commercial X-band spotlight or stripmap, 1 m or finer, 3 or more looks | Resolution, band | pits, pads |
| A2 | NISAR L-band, longer repeat-pass series and dual-pol plus any quad-pol modes | Time depth, polarimetry | pits, pads |
| A3 | Sentinel-1 C-band IW stack, 12-day, ascending and descending | Band, time depth (cheap, dense) | pads, roads |
| A4 | ALOS-2 PALSAR-2 L-band fine mode, 3 m | Resolution at L-band | pits, pads |
| A5 | SAOCOM L-band quad-pol | Polarimetry | pads, pits |

Features per arm. Backscatter mean and texture (GLCM), local contrast against a 20 to 60 m ring, temporal coefficient of variation, mean coherence if a repeat series exists, and polarimetric decomposition terms (entropy, alpha, Pauli channels) where polarimetry exists. The feature list is frozen in the preregistration. Feature sets are never chosen on the scoring blocks.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Rich lidar baseline rows and folds | `nisar/results/9t/nisar_pit_dedupe_auc_9t_slc.csv`, `nisar_pad_dedupe_auc_9t_slc_local1500.csv` | held |
| Baseline builders | `nisar/code/s5_eval/_nisar_feat_common.py`, `_nisar_feat_dedupe_9t.py`, `_nisar_feat_heldout_9t.py` | held |
| Held-out pit scores 613590 | `nisar/results/613590/nisar_pit_heldout_scores_613590_slc.csv` | held |
| Prior prereg and addendum | `nisar/docs/iterations/nisar_heldout_613590_prereg.md` | held |
| Review response with G1 to G3 | `docs/iterations/outside_review_response_20261103.md` | held |
| NISAR methods and checks | `nisar/docs/iterations/nisar_checks_9t.md`, `nisar_corrected_rescoring_9t.md` | held |
| Drawn pits and pads | `qgis/annotations/annotations_proj.gpkg` | held |
| New SAR products | `data/_source/sar_new/<sensor>/` | proposed, see section 5 |

## 5. Assumed data
Each item is assumed to exist. Each is tagged VERIFY with the check that would confirm it.

| Assumption | Tag | How to verify |
|---|---|---|
| Commercial X-band (Capella, ICEYE or Umbra class) archive or tasking covers the 9t footprint (619500 to 624000 E, 4593000 to 4597500 N, EPSG:6346) with at least 5 acquisitions in one leaf-on and one leaf-off season | VERIFY | Query each vendor catalogue for footprint overlap. Record the count, dates, look angle, polarisation and resolution in `docs/iterations/sar_catalogue_check.md` (proposed). A catalogue hit is not a delivered product |
| The licence permits internal research use and figures, with no redistribution of imagery | VERIFY | Read the licence text. Escalate to the user before purchase |
| Tasking or archive cost for 9t and 613590 fits the user budget | VERIFY | Written quote. Nothing is bought without the user |
| NISAR L-band repeat passes beyond the tested stack exist for 9t and 613590 | VERIFY | Count granules by track, frame and date from the NISAR catalogue. List what the tested stack already used |
| NISAR quad-pol or compact-pol modes exist over the area | VERIFY | Read granule metadata for polarisation. The tested product was dual-pol (HH, HV) |
| Sentinel-1 IW SLC stacks exist for both tiles and orbits (open data, 12-day) | VERIFY | Query the Copernicus catalogue. Count scenes per orbit |
| ALOS-2 or SAOCOM acquisitions are available for research use | VERIFY | Check agency catalogues and access terms. Both may be proposal-gated |
| Registration to the 0.5 m lidar DEM can be checked independently of the lidar | VERIFY | Use at least 10 permanent point scatterers (building corners, bridges) with known positions, not the lidar-based check used before. The earlier check was internal only |
| 613590 or a third tile has pit labels made without the radar visible | VERIFY | Confirm annotation provenance. The pad held-out gap (G3) needs a tile with drawn pads |
| A second tile with at least 60 drawn pads exists or can be drawn blind | VERIFY | Count pads per tile in `annotations_proj.gpkg`. 613590 holds 0 pads |

## 6. Prerequisites and decisions
User decisions block the preregistration and nothing else.
1. **δ_gain.** The useful AUC gain. The prior gate used +0.05. Keep it or replace it with a value derived from the decision a radar feature changes (reviewer minutes saved per km², cost of the data). Source of the margin is the burden tradeoff, never the fold spread.
2. **Budget ceiling** for data purchase.
3. **Which targets.** Pits only, pads only or both. Pads need a second labelled tile.

## 7. Procedure
**S0. Observability gate (no scoring).**
- Script `notebooks/wellsight_v2/s7_analysis/_sar_observability_9t.py` (proposed). For each arm compute the share of a pit footprint (about 80 m²) that fills one resolution cell, the number of usable acquisitions, the effective spatial support, registration residual and the expected signal relative to speckle variability. Write `data/9t/results/sar_new/sar_observability_by_arm_9t.csv`.
- An arm whose pit footprint fills under 25% of a cell and has no sub-cell texture is labelled "cannot see pits at this resolution" and is dropped for pits only. This is a measurement, not a failure of the hypothesis. A smaller delivered pixel is not more target information.

**S1. Power analysis (before purchase).**
- Script `notebooks/wellsight_v2/s5_eval/_sar_power_baseline_9t.py` (proposed). Inputs are the saved baseline scores per row and the folds.
- Compute for each stratum the baseline AUC, headroom and the block-bootstrap standard error of a paired AUC difference. The paired SE of a new arm is unknown, so simulate. Draw paired scores for (baseline, baseline plus arm) with an assumed true gain g from 0 to 0.10 in steps of 0.01 and an assumed within-pair correlation ρ_pair of 0.90, 0.95 and 0.98. The simulation shifts the score of true targets by the amount that yields gain g given the baseline score distribution. Resample blocks as in section 8.
- Output power as a table. Rows are stratum and g. Columns are blocks available and the share of simulations with interval lower bound above δ_gain.
- **Eligibility rule.** A stratum is eligible if power at g = δ_gain plus 0.01 is at least 0.80 and headroom is at least δ_gain plus the median interval half-width. If no stratum is eligible, the test is **not run** and the result is recorded as "no room, untestable at current baseline", which is a statement about the ceiling and not about radar.
- Known inputs for this arithmetic. 9t pits headroom 0.032 (ineligible for a +0.05 gain). 9t pads local decoys headroom 0.075. Lidar-weak pad quartile baseline 0.880 so headroom 0.120. These numbers come from the saved CSVs and the LEADERBOARD section on NISAR. Recompute them from the files before use.
- Alternative metric for room. Recall at K = 40 per km² on the baseline, which has more headroom than AUC where candidates are rare. Report it as a secondary, with the gain margin δ_gain_K from 5.1.

**S2. Acquisition and ingest (after the user approves cost).**
- Script `notebooks/wellsight_v2/s1_build/_fetch_sar_new.py` (proposed), resumable and logged like the lidar fetch scripts. Each source in its own folder `data/_source/sar_new/<sensor>/`. Hash every file. No script from a download is ever run.
- Process with the sensor vendor's documented geocoding or open tools (ISCE, SNAP, GDAL). Record software versions in `_PROVENANCE.json`.
- Geocode to EPSG:6346 on the 0.5 m DEM grid with terrain correction from the lidar DEM. Radiometric terrain flattening on. Record the incidence angle and layover/shadow mask per pixel.

**S3. Registration check.**
- Locate at least 10 permanent scatterers per tile and per track. Measure the offset in metres between SAR peak and lidar structure. Report median and maximum. A track with maximum offset above one resolution cell is shifted by a fitted translation, and the shift is logged. No feature is built before this check.

**S4. Feature build.**
- Script `notebooks/wellsight_v2/s5_eval/_sar_new_features_9t.py` (proposed). Output `data/9t/derived/sar_new/<arm>/` rasters at the arm's native grid, resampled to 1 m only for sampling and with the native grid recorded. Use the 5 m summary at pit and pad locations plus the native-resolution statistics inside the footprint.
- Frozen decoys as before. Matched on cover and slope, repeated locations dropped, 100 to 1,500 m local decoys for pads, footprint-shaped and incidence-matched decoys as a second set.

**S5. Scoring.**
- Script `notebooks/wellsight_v2/s5_eval/_sar_new_score_9t.py` (proposed). Same logistic or gradient-boosted model family as the baseline, same 5-fold block CV, 250 m buffer or the derived buffer from P2 if larger. Normalisation fitted inside the training folds. Ten repeats. Placebo arm with shuffled labels within block.
- Held-out test. Fit on 9t, freeze, score 613590 pits (36) and, if a second pad tile exists, its pads. Report the same gain. The held-out test is the confirmatory one.
- Output `data/9t/results/sar_new/sar_new_gain_by_arm_9t.csv`, `sar_new_heldout_gain_613590.csv`.

**S6. Report.**
- Figure `data/9t/results/sar_new/figures/sar_new_gain_by_arm_9t.png`. Gain with interval per arm and stratum. Blue observed, grey baseline, orange the margin line. The margin is also labelled directly.

## 8. Statistical analysis plan
- **Primary estimand.** Paired AUC gain of the A1 arm over baseline on 613590 held-out pits plus 9t out-of-fold pits in the lidar-weak stratum, pooled by blocks. One primary only.
- **Resampling.** Blocks with replacement (375 m on 9t), B = 2000, same blocks for both arms, percentile 95%. Fewer than 15 blocks gives a permutation interval as well, and the bootstrap is called unreliable. 613590 has 8 blocks, so its interval is reported with a permutation interval.
- **Decision.** Success if the lower bound exceeds δ_gain. Failure if the upper bound is below δ_gain and the stratum is eligible. Else inconclusive. One threshold serves both.
- **Secondary.** Every other arm and target. Recall at K gain. Gain by decoy distance. All labelled exploratory. Multiple arms mean a Holm adjustment is shown beside every exploratory interval.
- **Calibration** reported apart from ranking.
- **Placebo and location controls.** Map x and y only, placebo labels. The earlier work showed location alone reaches 0.955 on pits, so a radar gain over lidar is never claimed from radar-alone AUC. Radar-alone AUCs moved 0.06 to 0.12 with the decoy set, so only the paired gain over the baseline is reported as the finding.
- **Effective sample.** Blocks, not pits or pixels. Repeated acquisitions are not independent.

## 9. Quality control and leakage checks
1. Row counts asserted at each join. Distinct decoy locations counted before scoring and repeated ones dropped.
2. CRS and transform asserted for every raster. Incidence angle and layover masks present.
3. No training window touches a held-out or audit block (whole-window isolation).
4. Normalisation fitted inside the training fold only.
5. No SAR feature, threshold or arm is chosen after seeing scores in the test blocks.
6. A second run gives identical outputs.
7. Registration check done before features. Offsets logged.
8. Annotators did not see the new radar. Confirm for each drawn target used.
9. Hash every input and the config.
10. Sanity render of each new raster over hillshade for two known pits.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | At least one arm passes S0 and one stratum is eligible in S1 | Proceed to purchase request |
| No room | No stratum eligible | Record "untestable". Do not buy data. Revisit if the baseline changes |
| Success | Primary lower bound above δ_gain | Radar adds to detection for drawn features in the tested stratum. Plan a second tile |
| Failure | Primary upper bound below δ_gain in an eligible stratum | A genuinely different radar test also found no gain. State the arm, resolution, band and polarisation |
| Inconclusive | Interval spans δ_gain | Report. State blocks needed from S1 |
Margin source. The burden tradeoff in section 6 item 1. Not fold spread.

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\radar_scope_note.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\sar_new_prereg.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\sar_catalogue_check.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\_sar_observability_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_sar_power_baseline_9t.py`, `_sar_new_features_9t.py`, `_sar_new_score_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s1_build\_fetch_sar_new.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\sar_new\` (CSV, JSON, figures)
- A `.gitignore` rule for `data/_source/sar_new/` and `data/9t/derived/sar_new/` in the same change that creates them.

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| No eligible stratum | Report as no room. Use the lidar-weak stratum or recall at K |
| Commercial pixel unaffordable or unlicensed | Drop A1, keep A2 to A5 as exploratory, name the change in an Amendment |
| Registration offset blurs pits | S3 gate. Drop the track |
| Decoys leak location (radar alone looks strong) | Report paired gain only |
| Few held-out blocks | Permutation interval. Say bootstrap is unreliable |
| Overreading a null at one resolution | State arm, band, resolution and polarisation in every sentence about the result |
| A failed implementation read as no signal | Say which it is |

## 13. Resources
Power analysis about 8 hours, no GPU. Observability about 6 hours. Ingest and registration about 20 hours per sensor plus disk (X-band SLC scenes may be several GB each, put on F:). Features and scoring about 12 hours on CPU. Data cost unknown and a user decision. Calendar dependency is tasking lead time for X-band.

## 14. Handoff and open questions
- Confirm δ_gain, budget and targets (section 6).
- Confirm a second pad tile.
- Confirm the licence.
- Stop and report if no stratum is eligible.

## 15. Documentation updates
`radar_scope_note.md`, `sar_new_prereg.md`, `analysis_log.md`, LEADERBOARD (new section for any model result), master plan, BACKLOG, `literature/CITATIONS.md` for any polarimetric or SAR method cited. Add a pointer from the NISAR write-up.
