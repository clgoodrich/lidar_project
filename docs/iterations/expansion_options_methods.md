# Expansion options and methods

**Date:** 2026-11-04
**Status:** Plan only. Nothing in this file has been run.
**Source:** The expansion list pasted by the user on 2026-11-04, plus six items marked (added) that came from the project records.
**Related:** `docs/iterations/BACKLOG.md`, `docs/iterations/operating_point_policy_plan.md`, `docs/iterations/outside_review_response_20261103.md`

## 0. How to read this

Each option has a goal, the data it needs, a method that can be run, a test that can fail, and the risks. Effort is my estimate. S is days, M is weeks, L is months.

Terms used below.

- **QL2.** USGS Quality Level 2 lidar. It sets a nominal aggregate pulse density of 2 points per m² (check the exact wording in the USGS specification). It does not guarantee ground returns under forest. Our measured ground density on 9t is 2.70 points per m².
- **AP and AUC.** Average precision and area under the ROC curve. Both score a ranked list of candidates.
- **K.** The review budget. The number of candidates per km² a person can check. The operating-point plan recommends fixing K and cutting the ranked list there.
- **Platt scaling.** A logistic fit that turns raw model scores into calibrated probabilities.
- **Block.** A spatial block used to split training and test data so neighbours never sit on both sides.
- **Placebo rate.** The share of control locations that a test flags. It is the false-alarm rate measured on the data, not assumed.
- **AoR.** Area of review. The region a storage project must check for old wellbores.

## 1. What our results already constrain

These findings decide which options come first. Sources are in the related docs.

| Finding | Consequence for expansion |
|---|---|
| Every pad and pit label was drawn on lidar. | Scores against them measure terrain-feature detection. They do not establish well identity. Independent evidence comes first. |
| Ranked AP at IoU 0.3 is 0.818 for pits and 0.745 for pads, cross-validated on 9t. | The model has real skill at finding the terrain features we drew. It is a score against drawn features, not against confirmed wells. |
| Cross-validation scores 503 of 712 pits and 650 of 995 pads. The rest sit off the block grid (29% of pits, 35% of pads). | How the model does on those excluded areas is unmeasured. |
| A saved transfer test exists on tile 613590 with 153 annotated pit floors. With F2-selected cutoffs, mean recall is 0.911 against 0.928 on held-out 9t. With F1-selected cutoffs it is 0.792 against 0.861. The tile is not fully annotated, so no precision was reported. The cutoffs are not a fixed-K comparison. | Pit transfer to a second tile already has a first answer. The gaps are pad transfer, precision, a fixed-K comparison and independent well validation. |
| Feature precision is a lower bound until detections are reviewed blind (Phase 5 of the operating-point plan). | Any new area needs a blind review step. That step measures agreement about morphology. Well precision needs outside evidence. |
| The tested NISAR features added nothing over the lidar baseline. Gain is −0.004 for pits and −0.008 for pads after de-duplicating decoys. | Deprioritise those radar features. This does not show that every coarse sensor fails. Test each modality on its own evidence. |
| The 2006–08 against 2019 change surface has a high-passed noise level of 0.076 m. Three sigma is 0.235 m on flat ground. The patch cutoff is 3,368 m². Flight dates are unknown. | Change detection cannot see well-scale change. It can test pad-scale change on gentle ground. |
| A lidar intensity rule for pumpjacks did not work. Wells scored 37% and controls 53%. | Do not build infrastructure detection on raw intensity. |
| Pad and pit shape carries a weak era signal. 92% of the DEP orphan list in Venango has the 1800 sentinel date. | Era classification has no labels. |
| DEP positions are tens of metres off. The default match radius is 50 m. | Every match to agency wells needs a stated radius and a shuffled-location control. |
| In the Permian, only about 35% of Texas RRC orphan wells sit within 100 m of an optical pad detection. | Optical imagery over open ground is not a cure. |
| Pit flags in the change study persist at near-equal point density. Cause unknown. | Do not use the change study to label pits. |

The pasted list says "your ~200 labels". The repo holds 712 pits and 995 pads on 9t. The 217 figure belongs to the Barlow paper.

## 2. Rules every item inherits

1. **Pre-register.** One file per experiment in `docs/iterations/`, written before scoring. Model it on `nisar_heldout_613590_prereg.md`. State the metric, the margin, the expected failure and the decision rule.
2. **Freeze first.** Weights, thresholds, preprocessing and the operating point are fixed and the commit hash is recorded before the new data is touched.
3. **Separate feature from well.** Track four levels of evidence and never merge them. (a) A terrain-feature match to a drawn polygon. (b) Historical evidence such as a map symbol or photo. (c) A steel anomaly. (d) A confirmed well by record or visible wellhead. Blind review of the same lidar measures agreement about morphology. It does not establish well identity.
4. **Independent labels.** No label may come from the model being tested, from the radar, or from the same lidar the model reads. If a label does, say so next to the number.
5. **Unmatched is not negative.** A candidate with no record nearby may be an undocumented well. It becomes a negative only after outside adjudication. Keep an uncertain category.
6. **Spatial splits.** Split by block or by whole area. Bootstrap over blocks, not over rows.
7. **Controls.** Decoys are matched on slope within 3 degrees, de-duplicated, and used to measure a placebo rate. Method precedent is `notebooks/wellsight_v2/s7_analysis/_change_features_9t.py` and `notebooks/wellsight_v2/s5_eval/_nisar_feat_dedupe_9t.py`.
8. **Report negatives** in the same format as positives.
9. **Candidates stay candidates.** Nothing is called a confirmed well without field or record confirmation. Every candidate carries a score, the method and the distance to the nearest known well.
10. **Housekeeping.** Colourblind-safe figures validated over all pairs. Full paths for new files. Short descriptive names. Any file of 100 MB or more gets a `.gitignore` rule in the same change. Literature used in a design goes into `literature/CITATIONS.md` in the same change.

## 3. Geographic expansion

### 3.0 Shared design for any second area (the Year 3 transfer experiment)

**Goal.** Measure how much of the 9t performance survives in a new area, and how many local labels recover the rest.

**Method.**

1. Freeze the model as in rule 2.
2. Describe the shift before scoring. Build a table per area with ground-return density, share of empty cells at 1 m, slope and relief percentiles, canopy height, NLCD cover shares and the share of wells with a stated position accuracy. Train a tile-level classifier to tell 9t patches from target patches. An AUC near 0.5 means a small shift. Near 1.0 means a large one. This lets a failure be attributed to something.
3. Match the sensor. Score once at native density and once after thinning to the 9t ground density of 2.70 points per m² on a 1 m grid. The backlog shows 0.5 m is finer than the data supports.
4. Score against agency wells inside the stated match radius. Metric 1 is recall at fixed K. Metric 2 is feature-level precision from a blind review stratified by score, weighted back to the full candidate pool by each stratum's share. Metric 3 is calibration error before and after a Platt refit. Platt scaling is monotonic, so it keeps the candidate order and does not change recall at fixed K.
5. Run the adaptation ladder. Zero-shot. Recalibrate on 50 local labels. Fine-tune the last layers on N labels. Retrain pooled. Judge recalibration by probability accuracy (Brier score, log loss, calibration error), since it cannot move the ranking. Judge fine-tuning and retraining by ranking and by recall at fixed K, and plot that against N. The deliverable for an agency is the N it needs.
6. Run the controls in rule 5.

**Test.** The prereg sets a margin, for example recall at K no more than 10 points below 9t. The value is chosen before scoring and is not set here.

**Risks.** Agency position error looks like model failure. Reviewers who can see the scores tend to agree with them. Use blind sheets.

**Effort.** M for the framework, then S to M per area.

### 3.1 Same-survey neighbours (added)

**Why.** The cheapest transfer test. Same lidar survey, same sensor density, same agency records, different tiles.

**Data.** `PA_WesternPA_2019_D20` is QL2 at about 4.8 points per m² and covers western Warren and western Forest as well as Venango. A July 2026 note counts about 2,848 abandoned or orphan targets in Warren and 1,445 in Forest. The ANF QL1 collection (`PA_Northcentral_2019_B19`) covers McKean, Elk, eastern Warren and eastern Forest, and barely overlaps the Venango-adjacent wells. The same note records McKean as set aside by the professor's call. Confirm that is still true before planning around it. Counts are from that note and need re-checking.

**Method.** Follow 3.0 with tiles from Warren and Forest. Tile the area on the 9t scheme. No retraining. Add the pad held-out test the project lacks, with pad labels drawn by someone who has not seen the model output.

**Test.** Recall at fixed K on agency wells and blind precision. Compare to the 9t cross-validated numbers with block-bootstrap intervals.

**Risks.** Pumpjack and tank infrastructure is more common in Warren, so the base rate of active wells is higher. Score orphan and abandoned statuses only.

**Effort.** M. Depends on 3.0.

### 3.2 Appalachian neighbours (Ohio, West Virginia, New York, Kentucky)

**What differs.** Terrain and forest are similar. The records, the lidar programs and the well ages differ.

**Data to verify.** Each state's oil and gas regulator and its orphan or abandoned list. Each state's lidar program, with ground density measured per county. The list says all four have QL2-level programs. Measure, as the July note says, and do not infer from file size.

**Method.**

1. Pick one county per state with a dense, documented orphan population and measured ground density of at least 2 points per m².
2. Convert agency tables to one schema. Keep a position-accuracy field. Do not overwrite `output_wells.csv`. Write new files.
3. Run 3.0 per county.
4. Add one cross-state test. Pool the states and report between-state variance against within-state variance of recall.

**Test.** Does recall fall by more between states than between tiles inside one state?

**Risks.** Depth and era differ, so some target wells are gas wells with little surface expression. Stratify by well type where the record says.

**Effort.** M per state.

### 3.3 Illinois Basin and Michigan Basin

**What differs.** Flat, glaciated, farmed. Pits are subtle against low relief.

**Method.**

1. Run a context-reliance test on 9t first. It needs no new data. Paste a pit crop with its immediate rim into synthetic flat terrain and score it. Then keep the real terrain and replace the surroundings of known pits with shuffled terrain from elsewhere. If the score collapses, the model uses slope context more than pit shape.
2. Pick a county with a dense, documented orphan list on farmland. Verify the agency list.
3. Run 3.0.
4. Add a land-use covariate (NLCD cultivated crops against pasture). Plowing erases pits, so report recall by cover.

**Test.** Recall on cultivated ground against pasture and forest. A drop on cultivated ground is expected. A drop on all flat ground points to context reliance.

**Risks.** Many wells in fields were removed. Records may list them as plugged while the surface is regraded. Treat low recall with care.

**Effort.** S for the context test. M for the area.

### 3.4 Gulf Coast and East Texas piney woods

**What differs.** Flat, wet, dense pine and understory. Ground returns are thin.

**Data to verify.** The Texas RRC orphan layer (layer 2) is already documented in the repo and filters by county. The pasted list says Houston has a data advantage. Check what that means before relying on it. The Harris County mirror holds locations only, with no status.

**Method.**

1. Measure ground density and void fraction in candidate counties before choosing.
2. Replace slope-heavy channels with relief-normalised ones (openness, local relief rank). Pits on flat ground show up as local depressions.
3. Run 3.0. Report by void fraction.
4. Include flooded and wet-soil flags from NLCD wetlands. Exclude wetlands from one arm.

**Test.** A negative result is informative. Pre-register what recall below which level counts as failure.

**Risks.** Surface features may be too subtle for any lidar model. Then the finding is the detection limit, which is publishable.

**Effort.** M.

### 3.5 Oklahoma and Kansas

**What differs.** Open grassland. Canopy no longer limits lidar. Optical imagery becomes usable.

**Method.**

1. Choose counties with dense early-1900s fields and an agency list. Verify the lists from the Oklahoma and Kansas regulators.
2. Build three arms on the same wells. Lidar only, optical only (NAIP, 0.6 to 1 m), and fused.
3. Score each arm on recall at fixed K with the 3.0 controls.
4. Report the optical arm against the Permian result, where only about 35% of orphans sat near an optical pad.

**Test.** Does fusion add over lidar alone on open ground, with a block-bootstrap interval on the gain? This repeats the NISAR gain test with a better chance of a positive.

**Risks.** Active production infrastructure is dense. Score orphan status only.

**Effort.** M.

### 3.6 California (Kern County and the Los Angeles Basin)

**What differs.** Sparse vegetation, dense active fields, urban encroachment.

**Method.**

1. Frame the task as status classification. A lidar model can find a pad. It cannot tell an idle well from an active one.
2. Take idle and orphan lists from the state regulator. Verify the schema.
3. Add ancillary inputs for status. Pumpjack presence from imagery, access road wear, and recent activity.
4. Run 3.0 for pad detection. Run a second test for status classification with spatial splits.
5. In urban parts of the Los Angeles Basin, mask buildings with a footprint layer first.

**Test.** Status classification AUC on held-out blocks against a baseline of distance to the nearest active well.

**Risks.** The baseline may win. That is a valid result.

**Effort.** M to L.

### 3.7 Alberta, British Columbia and Ontario

**What differs.** Different regulators and record formats. Ontario's Oil Springs and Petrolia area has some of the oldest wells in North America, including hand-dug wells with large diameter pits.

**Data to verify.** Alberta's Orphan Well Association inventory and the regulator's list. Provincial lidar programs, coverage and density. Ontario's lidar program. Well ages in Ontario need a source. Coordinate systems (NAD83(CSRS), UTM 17N may apply near Oil Springs) need checking per rule.

**Method.**

1. Start with Ontario because hand-dug pits fit the pit class.
2. Convert records to the repo schema. Log the position accuracy class of each record.
3. Run 3.0. Report separately for hand-dug and drilled wells if the record separates them.

**Test.** Recall by well type at fixed K.

**Risks.** Coverage and licence terms. Lidar may not be public everywhere.

**Effort.** M to L.

### 3.8 Alaska North Slope and permafrost

**What differs.** The signal is thaw subsidence, not a rim or pit. Statewide elevation data is mostly interferometric radar at coarse grid, not lidar. Verify what exists over the legacy well sites.

**Method.**

1. Get the legacy well list and pad footprints from the federal land manager.
2. Build an InSAR displacement time series on pad footprints and matched tundra. L-band is the better band over vegetated ground. Apply the NISAR lessons. Check registration against an independent target, de-duplicate decoys, and report gain over a non-radar baseline.
3. Test whether pad subsidence rates differ from matched tundra, with a placebo rate.

**Test.** Pad against matched-control difference in seasonal and long-term displacement.

**Risks.** High cost, small sample, and our NISAR record gives no prior of success. Defer.

**Effort.** L.

## 4. Modality expansion

### 4.1 Magnetometry (UAV and ground)

**Why.** Steel casing is magnetic. This is the only item that breaks the label circularity directly.

**Method.**

1. Pilot on known wells. Start with 3 to 5 sites with agency coordinates of good accuracy. Measure the anomaly amplitude and noise at ground height and at drone height. Casing signal falls steeply with distance, between one over r squared and one over r cubed. A drone that must clear tree tops may not see a single casing. Run this check before anything else.
2. Choose the sensor and platform from the pilot. Options are a walking gradiometer under canopy or a UAV total-field magnetometer in open ground.
3. Draw 12 to 20 survey sites in four groups. Documented orphan wells. High-score candidates not in any record. Matched low-score controls. Lidar-visible pads with no record.
4. Survey on lines 2 to 5 m apart. Log a base station for diurnal correction. Correct for heading. Remove the regional field with a high-pass or upward continuation.
5. Detect anomalies with a rule written before the survey. For example amplitude above a stated multiple of local noise within a stated radius of the site. Use analytic signal or reduction to the pole to place the source.
6. Keep the surveyor blind to which group a site belongs to.
7. Record a handheld methane reading at each site (see 6.5).

**Test.** The share of sites with an anomaly by group. The offset between anomaly and lidar candidate. P(anomaly | score bin), which feeds 5.1 and 5.4.

**Risks.** Other iron (fences, pipes, tanks, junk) makes false anomalies. A cut and plugged well may show weakly. A magnetic anomaly shows steel, not a well, so call matches "candidate, steel confirmed". The reverse also holds. No anomaly does not show that no well is there. Gas can accumulate near leaking wells. Use a gas detector and follow site-safety practice. Landowner and state-land permission is needed.

**Effort.** L for a campaign. S for the pilot. Needs funding and a partner.

### 4.2 Thermal infrared

**Note.** No thermal work was found in `docs/`. The pasted list says "ties to your thermal feature work", which may refer to something outside the repo. Tell me where it is.

**Method.**

1. Satellite arm. Use Landsat thermal (about 100 m) and ECOSTRESS (about 70 m). Resolutions are from memory, verify. Build multi-date median land-surface temperature on clear, leaf-off, snow-free dates (the 9t leaf and snow date table already exists). Normalise by elevation and aspect.
2. Compare each pad with matched forest within 500 m and the same slope and aspect. Use a paired difference with a block bootstrap.
3. Drone arm. Fly dawn leaf-off passes over a few known leaking and non-leaking wells with a thermal camera. Compare pad, wellhead and surrounding ground.
4. Add a placebo. The same difference at random cleared patches of pad size.

**Test.** Pad against matched ground, with the placebo as the null.

**Risks.** A pad is 30 to 60 m wide, about one pixel. Gas itself has little thermal signal. Expect weak results from satellites. Stop if the satellite arm fails.

**Effort.** S for the satellite arm. M for the drone arm.

### 4.3 Vegetation stress and spectral anomalies

**Method.**

1. Use Sentinel-2 at 10 m (20 m for red-edge bands). Build NDVI and a red-edge index per date. The leaf and snow date screen for 9t exists.
2. For each pad or well, compute a seasonal anomaly. Compare the pixel with matched neighbours within 500 m that share NLCD class, slope and aspect. Use a multi-year median.
3. Test wells with a documented problem against wells without one. Obtain labels from the DEP complaint, violation or leak records. Verify what exists.
4. For hyperspectral data (EMIT at about 60 m, AVIRIS-NG by campaign), check coverage first. Most sites will have none.

**Test.** Anomaly difference between problem wells and matched controls, with a placebo from random forest pixels.

**Risks.** Few labelled leaks. Pads are a few pixels. Forest phenology varies with slope aspect. Use as a pad screen, not a well detector.

**Effort.** M.

### 4.4 Methane plumes

**Method.**

1. Regional arm. Divide an area into cells of 5 to 10 km. Count model candidates per cell. Count plume detections from Carbon Mapper, GHGSat or EMIT, and column enhancement from TROPOMI where available. Verify product access, pixel size and detection limits. From memory, satellite limits sit well above typical orphan-well leak rates.
2. Fit a count model for plumes with candidate density as the predictor. Include an offset for observation count and covariates for active well density, so active infrastructure is not credited to orphans.
3. Point arm. For each plume, list wells inside its source uncertainty and report whether any is a candidate.
4. Choose the Permian first. Plumes are abundant there and orphan ground truth is already in the repo.

**Test.** Is the coefficient for candidate density positive after controlling for active wells?

**Risks.** Forest, low albedo and snow lower retrieval quality in Pennsylvania. A regional result cannot name a well.

**Effort.** M.

### 4.5 Multitemporal lidar

**State.** Done for 9t and limited. See `docs/iterations/icp_change_9t.md`.

**Method for a next step.**

1. Close the open items first. Flight dates, column-seam cause, overlap offsets and the assumed 2019 coordinate system.
2. Run a plug-date test. The DEP table has a plug date for about 36% of wells. Take wells plugged between the two surveys. Test for fill or cut at the pad against slope-matched controls using the placebo-calibrated flag from `_change_features_9t.py`.
3. Check USGS 3DEP for a newer Pennsylvania acquisition. A third epoch would test the 2019 to now interval.
4. Use the slope-normalised field (`--zscale`) for any new patch work.

**Test.** Flag rate for plugged-between-epoch wells against the measured placebo rate. In aggregate the pad flags were 19 of 404 against about 15 by chance, so the prior is a null.

**Risks.** Small sample. The detection floor is 0.235 m on flat ground.

**Effort.** S to M.

### 4.6 Historic aerials and topographic maps

**Why.** Labels that do not come from lidar. Old derricks, tanks and roads show on sheets and photos that predate the records.

**Data to verify.** The USGS Historical Topographic Map Collection, USGS EarthExplorer aerials, and Pennsylvania state or county historic imagery. Check dates, scale and licence for each.

**Method.**

1. Georeference. Use ground control at road crossings, stream confluences and bridges. Use a second-order polynomial or thin-plate spline. Hold out a third of the control points and report RMSE. Reject sheets above a stated limit.
2. Digitise symbols in sample windows of about 25 km². Record symbol type (well, derrick, tank), sheet date and sheet scale. Use two digitisers on a 20% overlap to measure agreement.
3. Match symbols to DEP wells and to lidar pad candidates with a radius of 50 to 75 m. Cartographic displacement is real, so report the offset distribution.
4. Define a historic-only set. Symbols with no DEP record within the radius.
5. Test the historic-only set. Compare lidar pad and pit scores at those points against random forest points matched on slope.
6. Keep the first version as an audit set and never train on it. After the audit works, test it as weak supervision with label-noise estimates.

**Test.** Median model score at historic-only points against matched random points, with a block bootstrap. A match rate between historic symbols and DEP wells as a sanity check.

**Risks.** Symbol meaning changes across sheets. Many map symbols mark wells later plugged and removed. Georeferencing error can be tens of metres.

**Probe (2026-11-04).** The TNM API lists 31 sheets over 9t. One sheet (Oil City 1922, 1:62,500) was cropped to 9t. No well symbols were visible in the mapped part, and the sheet's north edge runs through the tile. One sheet and one look. Topo sheets now look low-yield here. Test aerials and state geological survey oil-field maps next. See `docs/iterations/expansion_gameplan_feasibility.md`.

**Effort.** M. High value only if aerials or oil-field maps show wells.

### 4.7 Drone lidar (added)

**Why.** NETL has flown drone lidar at Oil Creek and located 63 well sites from lidar alone, per the July note. Only the well coordinates are public. A data request is needed.

**Method.** Request the point clouds. Run our pipeline on them and on the 4.8 points per m² aerial data over the same sites. Compare detection by density. This sets the ceiling for what denser lidar buys and tests the "is it just resolution" question.

**Test.** Recall of the 63 sites at fixed K for each density.

**Effort.** S once data arrive. Depends on the request.

### 4.8 Leaf-off optical imagery (added)

**State.** A leaf-off photo pass over pits gave ten blank chips out of thirteen and is uncommitted. Check coverage dates before trying again. If coverage exists, run the optical arm of 3.5 in forest as a negative control.

### 4.9 More radar (added, recommend drop)

NISAR gave no gain over lidar at pit or pad scale. A re-test needs a new reason, such as the Alaska subsidence signal in 3.8.

## 5. Task expansion

### 5.1 Associated infrastructure and context

**Why.** A pit with a road and a bench is more credible than an isolated depression.

**Method.**

1. Build candidate-level context features. Distance to the nearest road, pad, drainage line and slope break, pad geometry, number of other candidates within 200 m.
2. Take roads and pads from out-of-fold model output, not from annotation. Annotators drew pits near the roads they saw, so annotated roads leak the label. The backlog already lists an out-of-fold pad raster.
3. Fit a second-stage classifier (logistic regression and gradient boosting) on the first-stage score plus context. Use block cross-validation.
4. Ablate. First-stage score alone. Add each feature group. A shuffled-context control permutes context features within a block.
5. Do not use lidar intensity for tanks. The pumpjack pilot did not support it.

**Test.** Gain in AP and AUC over the first-stage score, with a block-bootstrap interval, as in the NISAR gain test. A gain also requires beating the shuffled-context control.

**Risks.** Circularity. Context may pick up where annotators looked.

**Effort.** S to M. Uses existing layers.

### 5.2 Well type or era classification

**State.** `docs/iterations/well_age_morphology.md` found a weak signal among wells with real dates, which begin in 1956.

**Method.**

1. Get era labels that reach before 1956. Use presence on the early map or photo from 4.6 as a binary target (on an early sheet or not).
2. Features. Pad area and compactness, pit depth and volume, canopy height on the pad against the surround as a regrowth proxy, road class.
3. Fit an ordinal or binary model with block cross-validation. Compare with a baseline of area alone.

**Test.** AUC over the area-only baseline.

**Risks.** Few early labels. Defer until 4.6 produces them.

**Effort.** M. Depends on 4.6.

### 5.3 Risk ranking

**Method.**

1. Define three parts. Hazard (status, age bin, plug record). Exposure (distance to streams, water wells, buildings, roads, protected land, source-water areas). Vulnerability (soil, slope, aquifer). Check the DEP ranking rubric first and match it where it exists.
2. Score each well or candidate as P(well exists) times the risk score. This carries detection uncertainty into the ranking.
3. Run a sensitivity analysis. Draw weights from a range 200 times and report rank stability (Kendall tau) and how often each candidate stays in the top K.
4. Output a map of expected exposed wells per km², not a list of decisions.

**Test.** Rank agreement with the DEP list for documented wells. This is a comparison, not validation.

**Risks.** Weights are a judgment call. State them. Not worth building until detections are trusted.

**Effort.** M. Depends on 5.4 and on blind precision.

### 5.4 Probabilistic undocumented-well density

**Why.** This matches how funders frame the methane inventory. It gives a number with an interval, not a list.

**Method.**

1. Fix the counting unit first. A well is not a pit or a pad. Resolve several pits or pads per well and several wells per pad into one unit, the borehole, and state the rule. Then count what is seen. Documented wells and model detections in each cell.
2. Estimate detection probability by group and covariate (canopy, slope, point density). Use blind-review precision and recall from labelled areas.
3. Combine, under strong assumptions that must be stated. With D candidates, well precision p and recall r, the estimated total is D × p ÷ r. The estimated wells the detector missed are D × p × (1 − r) ÷ r. The estimated undocumented wells are the estimated total minus the complete documented population in the same scope and unit. Subtracting only the documented overlap would mix different quantities. Sample p from a Beta posterior and r from the field or historic-map audit. A spatial smoothing prior can share strength across cells. It cannot identify a detection rate the data do not identify.
4. Add a cross-check from capture and recapture with three lists (agency records, model detections, historic-map symbols). Log-linear models handle some list dependence. Positive dependence between lists tends to bias the total low and negative dependence tends to bias it high. Unequal capture across sites can push either way. Do not call the estimate a lower bound without a reason specific to the data.
5. Test the key assumption that detection works equally on documented and undocumented wells. Use the bounty-era diff. Between the 2022 orphan list and the April 2026 export, 1,316 Venango wells were newly documented, 6 inside 9t and 71 within 2 km. This is a proxy and includes reclassifications. Run the frozen model county-wide and compare recall on the newly documented wells with recall on the older ones.
6. Report the density per 5 km cell with a 90% interval.

**Test.** The recall gap between newly documented and older wells. A large gap means the undocumented population is harder to see, and the estimate must be inflated.

**Risks.** Well precision needs independent evidence, and lidar-only blind review gives feature precision only. Intervals must carry that.

**Effort.** M to L. Depends on blind review and 4.6.

### 5.5 Polygon segmentation and footprint area

**State.** The pad and pit U-Nets already train on polygons.

**Method.**

1. Measure area bias on the U-Net output. The backlog records that hybrid pad outlines in the road driving-surface work come out 8% smaller than drawn at 2 m. It also records that 22% of annotated pit floors are under 20 m², below the deployed minimum area.
2. Measure annotation reproducibility. Have two annotators redraw 30 pads. Their IoU is a reference for how repeatable the drawing is. It is not a mathematical limit on model performance.
3. Correct area bias with a calibration curve fitted on out-of-fold polygons.
4. Convert area to restoration cost with public reclamation contract unit costs. Verify the source.
5. Report boundary F-score and area error per size class.

**Test.** Area error against the annotator reproducibility reference.

**Effort.** S to M.

### 5.6 Agency record association (added)

**Why.** DEP positions are tens of metres off. Proposing an association between each record and a nearby detected feature could make the model a record-checking tool. A pad centroid is not a borehole, so the output is a proposed association and not a corrected coordinate.

**Method.**

1. For each record in a target set, take candidates within 100 m with score above the operating cutoff.
2. Choose the association unit first. At pit level, solve a one-to-one assignment (Hungarian) on distance and score with a distance gate. At pad level, allow many records to one pad and make no claim about where the borehole sits inside it. The two rules answer different questions, so run and report them separately.
3. Estimate the offset distribution by status, age and county.
4. Add a spatial null. Shift the records by a random 200 to 500 m vector and re-run. The match rate on shifted records estimates chance matching under that null. It is not the error rate of the accepted matches.
5. Judge improvement only against independent coordinates, such as GNSS points or the NETL sites. Without them nothing is shown to be corrected.
6. Write proposed associations to a new file with an offset, a confidence and a flag. Never overwrite the source table.

**Test.** Real match rate against the shifted-record rate, and the offset against independent coordinates.

**Risks.** A wrong snap makes a record look better and hides a real error. Keep the original position beside the new one.

**First result (2026-11-04).** Run on 9t against held-out detections. Orphan and abandoned records were not distinguishable from the shifted-record null at any radius. Active records were. The test has low power and no independent coordinates. See `docs/iterations/record_assoc_pits_9t.md`. Next step is to repeat it on the full annotated features and to add independent coordinates.

**Effort.** S for the association. M if independent coordinates must be collected.

## 6. Adjacent problems

### 6.1 CO₂ storage and geothermal siting

**Why.** Class VI injection permits require a check of old wellbores in the area of review (40 CFR 146.84, verify). A completeness estimate for that inventory is a product.

**Method.**

1. Pick a real or hypothetical area of review of a few hundred km².
2. Build the inventory in three layers. Documented wells. Detected undocumented candidates. Historic-map symbols.
3. Apply 5.4 to report expected missed wells with an interval.
4. Write the result in a regulator-readable form. A table of wells by confidence, and an inventory completeness statement.
5. Run a retrospective on a county where wells were later found, using the bounty-era diff.

**Test.** Completeness estimate against later discoveries.

**Risks.** Needs a real project partner. Lidar sees no depth or casing detail.

**Effort.** M. Depends on 5.4.

### 6.2 Abandoned coal mines

**Features.** Portals (benches with a highwall cut), air shafts (circular depressions), subsidence pits and troughs, refuse piles, strip-mine highwalls.

**Method.**

1. Obtain the state abandoned mine land inventory and mine maps. Verify names, formats and licences.
2. Choose a coal-bearing county with lidar of known density. Venango has little coal. Western and southwestern Pennsylvania and West Virginia have more.
3. Start with point-like targets, portals and shafts. Reuse the pit U-Net with new class heads.
4. Evaluate by block against the inventory with a 50 m radius. Include a confusion matrix against well pits so the two classes do not trade errors.

**Test.** Recall at fixed K by feature type, with the 3.0 controls.

**Effort.** M to L.

### 6.3 Legacy land features as negative classes

**Why.** This is the cheapest fix for false alarms. It follows the standing preference to fix confusion in training by adding the confusing class as a negative, not by a filter after the fact.

**Features.** Charcoal hearths (flat circular platforms, about 10 m across, from memory), mill dams and races, old quarries and borrow pits, splash dams, railroad grades and tram roads, cellar holes, farm ponds, beaver ponds, and tree-throw pit-and-mound ground.

**Method.**

1. Freeze an audit set first. Hold out blocks that are never mined and never trained on. Then harvest review candidates from the rest. Take the top-scoring pit and pad candidates with no annotation or record within the match radius. These are not negatives. Some may be real undocumented wells, which is what the project looks for. Build contact sheets with `notebooks/wellsight_v2/s6_review/_build_pit_review_package.py`.
2. Write a codebook. A definition, a thumbnail set and a decision tree for each confuser class. Two reviewers label independently. Report Cohen's kappa. Resolve ties by a third reviewer.
3. Harvest more by template. For hearths, search for circular benches 8 to 14 m across with an uphill cut and downhill berm, often in groups along a slope. Use DEM cross-correlation against a template.
4. Support labels with independent sources when they exist, such as furnace locations and old map symbols.
5. Retrain with only the adjudicated confusers as extra classes or hard negatives, on the same block split. Leave the uncertain category out of training.
6. Evaluate on the frozen audit set. Confuser detections at fixed recall, split by class, before and after. Add a control that adds the same number of random negatives, so "more negatives" is separated from "the right negatives".
7. Keep the hearth and quarry inventory as a side product.

**Test.** Adjudicated-confuser detections per km² at fixed recall, against the random-negatives control. Unmatched candidates are counted separately and are not called false positives.

**Risks.** Training on unmatched candidates would teach the model to suppress the undocumented wells it exists to find. Confuser labels are also lidar-derived, so use outside evidence such as furnace sites and old maps where it exists, and keep the uncertain category. A wrong rejection costs a miss that recall on the audit set reports.

**Effort.** S to M. Start here.

### 6.4 Hydrogen storage and subsurface repurposing

Same logic and method as 6.1 with a different area of review. Defer. Lidar gives no depth or casing information, which these projects need.

### 6.5 Field methane at sites (added to 4.1 and 7.5)

A handheld laser methane detector gives a reading per site. It is a field measurement, not a plume product. Record the reading, the distance and the wind.

### 6.6 WiSAR and LLM viewshed project

**Method.** Share only the terrain tooling. A DEM derivative builder, a tile cache and a viewshed routine on a 1 m DEM. Keep the downstream model and the data in a separate module. Nothing here tests a well hypothesis.

**Effort.** S for the shared module.

## 7. Scale and methodology

### 7.1 Self-supervised pretraining

**Method.**

1. Gather unlabelled QL2 tiles from many regions. Build the same DEM derivative channels used downstream.
2. Pretrain the downstream encoder. Choose masked reconstruction (mask 60 to 75% of patches) or a contrastive objective. Use augmentations that keep elevation meaning, such as flips and rotations, and avoid rescaling relief.
3. Fine-tune on the 9t labels with the same blocks as the cross-validation.
4. Run a label-efficiency curve. Fine-tune on 10, 25, 50 and 100% of labels and compare with random initialisation. Add an ImageNet-initialised arm and an arm pretrained on 9t only. The last arm separates the value of diversity from the value of the method.
5. Test on a held-out area, not only held-out blocks.
6. Record the masked-autoencoder and contrastive references in `literature/CITATIONS.md` when this is acted on.

**Test.** Does pretraining with 50% of labels match scratch training with 100%? Report with block-bootstrap intervals.

**Risks.** It helps label scarcity and does nothing for label circularity. Pretraining on more lidar will not show whether the labels are right.

**Effort.** L. Needs GPU time that I have not sized.

### 7.2 Active learning

**Method.**

1. Score unlabelled candidates with the calibrated model.
2. Choose a batch of K by uncertainty (calibrated probability near 0.5), diversity (cluster in embedding space) and field access cost where a field arm exists.
3. Label the batch in QGIS using the road-correction loop already built, then retrain on the difference.
4. Keep a random audit set stratified by score bin. It is never used to train. It also gives feature-level precision when each score stratum is weighted back to its share of the candidate pool (Phase 5).
5. Compare with random sampling at the same label budget.
6. Stop when AP on the audit set changes by less than a set margin for two rounds.

**Test.** Learning curve against random sampling on the audit set.

**Risks.** Uncertainty sampling skews class balance. The audit set protects the evaluation.

**Effort.** M. Worth doing once labels are independent.

### 7.3 Public benchmark dataset

**Method.**

1. Package labelled patches (for example 256 by 256 at 1 m) with masks, block ids and area-level splits.
2. Include baselines with confidence intervals and the metric scripts.
3. Write a datasheet. Provenance, label process, annotator agreement, known biases, label circularity and position error.
4. Check licences. USGS lidar is public domain. Check the DEP data terms and any location-sensitivity concern.
5. Host with a version number and a hash of the test split.

**Test.** An outside group reproduces the baseline within its interval from the release alone.

**Risks.** Releasing unreliable labels. Do it after the independent audit set exists.

**Effort.** M.

### 7.4 State agency tooling

**Method.**

1. Package a command-line tool. Input is LAS or LAZ or a DEM. Output is a candidate file with score, method, distance to the nearest record and a review sheet.
2. Build in a quality check (coordinate system, point density, void fraction) that stops the run on a mismatch.
3. Add a Platt refit step that takes 50 to 100 local labels.
4. Pin the environment. Document hardware and runtime.
5. Acceptance. It reproduces the reference-tile numbers within tolerance on a clean machine. One agency runs it blind on a tile.
6. Use the outreach contact list in `docs/articles/well_reporting_outreach_contacts_pa_2026-08.md` to find a first user.

**Effort.** M to L.

### 7.5 Field validation campaign

**Why.** It answers the outside reviewers' main point. It supplies the independent truth every other item uses.

**Design.**

1. Sampling frame. Candidates in five score bins, documented orphan wells as a positive control, and random forest points as a negative control.
2. Sample size. For a proportion near 0.5, n = 1.96² × 0.25 ÷ d². About 43 sites gives ±15 points, about 96 gives ±10 points, and about 24 gives ±20 points. Plan on 40 sites per estimate you need. These figures hold per estimate under simple random sampling. Five bins, clustered sites and spatial correlation widen the intervals. Inflate by a design effect and size the campaign from the number of estimates needed.
3. Instruments. A magnetometer or gradiometer (4.1), a handheld methane detector, a GNSS receiver that averages to under 1 m, a camera, and a standard form with fixed fields.
4. Blind labels. Site ids carry no score. The recorder does not see the bin.
5. Safety and permission. Gas detection, landowner and state-land permits, and a plan for reporting any undocumented well. The outreach document lists contacts.
6. Analysis. Wilson intervals for precision by bin, then a population-weighted overall estimate. Offset between candidate and anomaly. P(steel | score bin). Methane reading against anomaly.
7. Language. Results say "candidate" or "steel-confirmed candidate". Nothing says "confirmed well" without a record or a visual wellhead.

**Test.** Precision by score bin and the offset distribution.

**Effort.** L. Needs people and funding.

## 8. Order, dependencies and value

My effort figures are rough.

| Order | Item | Creates independent labels | Effort | Why this position |
|---|---|---|---|---|
| 1 | 6.3 Negative classes | No | S to M | Cheap, on 9t now. Only adjudicated confusers become negatives. |
| 2 | 5.6 Record association | No | S | Cheap. Proposes matches only, and improvement needs independent coordinates. |
| 3 | 5.1 Context features | No | S to M | Uses layers we have. Needs out-of-fold inputs. |
| 4 | 4.6 Historic maps and aerials | Yes | M | Independent labels with no field trip. |
| 5 | 3.1 Same-survey neighbours | Needs blind pad labels | M | Closes the pad held-out gap. |
| 6 | 4.1 and 7.5 Magnetometry and field campaign | Yes | L | The decisive test. Start the pilot early because it takes lead time. |
| 7 | 5.4 Density maps | Uses 4.6, 7.5 | M to L | Needs trusted precision and recall. |
| 8 | 3.2 to 3.7 Other regions | Depends | M each | After a nearby area works. Choose by terrain difference, not well count. |
| 9 | 7.2 and 7.1 Active learning, pretraining | No | M, L | Only after labels are independent. |
| 10 | 6.1 CO₂ and geothermal framing | No | M | A funding angle built on 5.4. |

Defer. 3.8 Alaska, 4.9 more radar, 5.2 era classification until 4.6 gives labels, 5.3 risk ranking until detections are trusted, 6.4 hydrogen.

## 9. Claims that need checking before they go in a proposal

- County and state well counts for Warren, Forest, McKean and Elk come from a July 2026 note. Re-count.
- McKean being set aside is from a July 2026 note. Confirm.
- The agency names, list formats and lidar program coverage in section 3 are from memory. Measure ground density per county.
- The Houston data advantage and the Ontario well ages in the pasted list are unverified.
- Satellite resolutions and methane detection limits in sections 4.2 to 4.4 are from memory.
- The charcoal hearth size is from memory.
- The Class VI rule citation and the DEP ranking rubric need confirming.
- The statewide elevation data type in Alaska needs confirming.
- Thermal feature work mentioned in the list was not found in this repo.

## 10. Corrections to my earlier advice in this conversation

- I said McKean first. The July note says McKean was set aside and that the ANF QL1 collection barely overlaps Venango-adjacent wells. The cheaper same-survey test is Warren and Forest under D20 (3.1).
- I said Allegheny National Forest QL1 would serve as a near neighbour. It is about 52 km from Oil Creek per that note.
- I understated the existing transfer evidence. A saved 613590 pit test exists (section 1). The missing pieces are pad transfer, precision, a fixed-K comparison and independent well validation.
- An outside review on 2026-11-04 corrected six points, now fixed in this file. Feature and well are separate claims (rules 3 and 5). Platt scaling cannot change recall at fixed K (3.0). The density equation was wrong (5.4). Record snapping gives proposed associations, not coordinates (5.6). Unmatched candidates are not negatives (6.3). Sample-size and ceiling wording was too strong (5.5, 7.5).
