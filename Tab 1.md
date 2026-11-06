# Expansion plans: adversarial review

Nov 4, 2026 · @Me

Few of the 38 plans can produce defensible evidence about wells as written. Most can produce evidence about lidar terrain features that one annotator drew, and the plans mostly say so honestly. The problem is that the near-term work is aimed at feature-level questions, while the uncertainty that decides the project's value is whether drawn features are wells. On 9t only 6.4% of annotated pits have a DEP record within 25 m, and orphan or abandoned records match held-out detections at chance. The repo's own results put that question first, and it should be first in the plans too. Six plans should proceed or run as bounded pilots now (P1, P2, 3.0, 4.6, 4.7 request, 5.6 reanalysis). Seven need redesign before any labels are spent (3.1, 3.3, 5.1, 5.4, 6.3, 4.1, 7.5). The rest should be deferred, and satellite methane attribution in Pennsylvania (4.4) should be rejected.

## Most consequential findings

1. **Drawn features and wells are nearly disjoint populations, and no near-term plan measures the overlap.** Only 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m, and the median distance is 75 m (`docs/iterations/LEADERBOARD.md:491-492`). At the pre-fixed 50 m radius, orphan or abandoned records match held-out pits at 0.116 against a shifted-record null of 0.086, with a 95% null range of 0.038 to 0.141 (`record_assoc_pits_9t.md:56`). That makes the implied predictive value of a proposed orphan match about 1 − 0.086/0.116 ≈ 0.26, with an interval that includes zero. Every plan whose evidence level is (a) is therefore silent on wells. The only plans that could bridge that gap (4.1, 4.6, 4.7, 7.5) all sit behind outreach.
2. **Magnetometry cannot be the independent arbiter for the oldest wells.** Hammack et al. (2023) report that helicopter and sUAS magnetic surveys in forested Pennsylvania missed many 1860 to 1880 wells because those wells had wood casing. Venango's oil-creek pits are disproportionately from that era. A magnetic null at a pit is close to uninformative exactly where undocumented wells are most likely. Plans 4.1, 7.5 and 5.4 treat steel as the bridge from feature to well, and they need an era-aware design.
3. **The transfer comparison (3.0, 3.1) has no coherent metric yet.** K is defined two incompatible ways. It is candidates per km² in the operating-point work, where the policy is still "not yet chosen" (`operating_point_policy_plan.md:47,54`). It is the count of annotated features in the Warren prereg (`transfer_warren_prereg.md:29`). The 9t reference cited there (0.928) is a cutoff-based recall, not recall at fixed K (`expansion_options_methods.md:31`). Recall at a per-km² budget also rises or falls mechanically with target density: on 9t pits it moves from 0.781 at 30 per km² to 0.909 at 40 (`operating_point_policy_sweep_pit_pad_9t.md:96-97`). Methods 3.0 step 4 and gameplan B1 score against agency wells. Plan 3.0 scores against drawn polygons. These are different experiments.
4. **The CV inner split is not reproducible, and the saved split manifest does not match the trained models.** Verified by re-running the trainers' fold logic. In Python 3.10 and later, `hash(nan)` depends on object identity. So `sorted(set(block_ids) - held)` places the NaN block (the 209 off-tile pits) in a different position on each run. That changes `rng.permutation`, and with it the inner validation and training blocks. In six runs, fold 1 validation pits came out 71 or 61, and fold 3 came out 56, 70 or 79. The logged training run had 73 (`_pit_cv5_ann712_train.log:248`). `_save_cv_split_manifests_9t.py:37` drops NaN before shuffling, so its saved validation lists differ from the trainer's in all five folds (3 to 16 blocks swapped). Held-out folds are unaffected and still valid. Threshold choice, epoch choice, P2's training history and any exact reproduction are affected.
5. **Record-based recall is dominated by chance matches and confounded by coordinate quality.** The A6 recall-gap result compares a 22 of 141 (15.6%) detection rate against a chance rate near 10% (`recall_gap_newly_documented_9t.md:19`). Wells documented in 2022 to 2026 were plausibly located by field crews with GNSS, while 1800-sentinel records were not. A recall gap between those cohorts would measure coordinate quality as readily as detectability. Plan 5.4's density equation then inherits an r that the current design cannot identify.

## A. Coverage table

Ordered as in `docs/plans/README.md`, prerequisites first. Evidence levels are the plans' own (a) drawn feature, (b) historical, (c) steel, (d) confirmed well.

| Plan | Decision | Evidence it can legitimately produce | Main unresolved issue | Smallest defensible next step |
| --- | --- | --- | --- | --- |
| P1 `plan_prereq_splits_manifests.md` | Proceed (rescoped) | Reproducible splits. No scientific evidence | Root cause is NaN hash order, not only NaN rows. The saved manifest is not the trained split | Make inner split deterministic. Recover the historical split from logs and checkpoints, not by re-deriving it |
| P2 `plan_prereq_audit_set.md` | Proceed (rescoped) | A guarded audit set for comparative 9t tests | "No use" leaves zero 9t blocks. Every block trained 4 of 5 CV models | Define audit blocks as excluded from all new models. Reserve absolute claims for a new area |
| 3.0 `plan_geo_transfer_protocol.md` | Bounded pilot | Feature detection (a) in a new area on fully annotated blocks | K undefined. Reference metric mismatched. Acceptance test unreachable | User fixes K policy. Validate the protocol on saved 9t out-of-fold rasters |
| 3.1 `plan_geo_warren_forest.md` | Redesign | (a) for one within-survey site. A case study, not generalisation | Same D20 survey as 9t, not "different lidar". 7 km² may not hold adaptation, test and audit with 500 m buffers | Project interval width from 9t before annotating. Time one block of annotation |
| 3.2 `plan_geo_appalachian_states.md` | Defer | (a) per county as case studies | Depends on a working 3.0 and 3.1 | Desk inventory table only |
| 3.3 `plan_geo_low_relief_midwest.md` | Redesign | (a) sensitivity to slope context on 9t | A synthetic plane lacks 0.5 m interpolation texture, so it is out of distribution. 9t benches are not Illinois plains | Stratify existing 9t out-of-fold recall by local slope first. Synthetic edits second |
| 3.4 `plan_geo_gulf_east_texas.md` | Defer | (a) with a ground-density stratum table | Claims (d) from RRC records, which contradicts README rule 9. The 35% figure is Permian, not East Texas | Ground-density measurement only, if ever |
| 3.5 `plan_geo_oklahoma_kansas.md` | Defer | (a) per modality | Optical and fusion arms need new target-area labels. "Matched effort" is not measurable | None now |
| 3.6 `plan_geo_california.md` | Defer | Target definition document | A different research question (status) | None now |
| 3.7 `plan_geo_canada.md` | Defer | Data inventory | Licence, access and local reviewers unverified | Inventory table only |
| 3.8 `plan_geo_alaska.md` | Defer | Reconnaissance note | A new method with no prior success | None now |
| 4.1 `plan_mod_magnetometry.md` | Redesign, then pilot | (c) steel anomaly at a few sites | Blind to wood-cased 1860-1880 wells. Cut casing may be weak | Add an era stratum and casing-removal documentation to the site list |
| 4.2 `plan_mod_thermal.md` | Defer | Land-cover differences already visible in lidar | No physical mechanism beyond canopy openness | None |
| 4.3 `plan_mod_vegetation_stress.md` | Defer | Vegetation-index differences, not leaks | No leak labels. Average leak rates are tiny | Check whether DEP complaint records exist |
| 4.4 `plan_mod_methane_plumes.md` | Reject for PA. Defer elsewhere | None at well scale | Satellite detection threshold sits about 10^4 above the mean leak rate | Close with a one-paragraph detection-limit note |
| 4.5 `plan_mod_multitemporal_lidar.md` | Blocked | (a) pad-scale change at dated wells | Flight dates unknown. The eligible n is unknown | Pull the 2006-08 and 2019 flight dates from USGS metadata |
| 4.6 `plan_mod_historic_maps_aerials.md` | Proceed (probe), elevated | (b), the only route to pre-1880 positions | 1922 topo had no symbols. Better sources untested | Probe 1870s-80s survey maps, oil-region atlases and 1937-42 aerials |
| 4.7 `plan_mod_drone_lidar.md` | Proceed (request) | (a) density-degradation curve for lidar-visible sites | The 63 sites were chosen by lidar visibility | Send the request now |
| 4.8 `plan_mod_leafoff_optical.md` | Bounded pilot | Coverage table. (a) or (b) visual corroboration | 10 of 13 chips blank before | Coverage and date table only |
| 4.9 `plan_mod_more_radar.md` | Proceed (note only) | A scope note | Omits the 613590 held-out result and the ceiling caveat | Write the note with both |
| 5.1 `plan_task_context_features.md` | Redesign | (a) ranking gain from context | Pit, pad and road models use different splits. Stacking needs one shared fold scheme | Inventory checkpoints. Pick one block-fold scheme for all upstream models |
| 5.2 `plan_task_era_classification.md` | Defer | Era as an attribute | No dated wells before 1956. 92% of orphan dates are the 1800 sentinel | Wait on 4.6 |
| 5.3 `plan_task_risk_ranking.md` | Defer | A scenario ranking, not evidence | No P(well) exists, only P(feature) | Exposure layers only if needed for a product |
| 5.4 `plan_task_undocumented_density.md` | Redesign | Identifiability and sensitivity statement | r is unidentified. Recall gap is confounded by coordinate quality | Identifiability note. Get DEP coordinate provenance |
| 5.5 `plan_task_polygon_area_cost.md` | Defer | Area agreement (a) | Low decision value now. Pad model already over-claims area about 2x | None now |
| 5.6 `plan_task_record_association.md` | Proceed (reanalysis) | A null result on 9t. Proposals with stated predictive value | No working positive control for pits at the primary radius | Report the predictive value per group. Wait for GNSS before validation |
| 6.1 `plan_adj_co2_geothermal.md` | Defer | A limits-first layer package | Its methods version promises a completeness estimate 5.4 cannot give | None |
| 6.2 `plan_adj_coal_features.md` | Defer | (a) per class | Venango has little coal. A separate study | None |
| 6.3 `plan_adj_negative_classes.md` | Redesign, then pilot | (a) comparative reduction of reviewer-defined confusers | New detections after retraining are unlabelled. Seed noise. Labels are lidar-only | Pre-label a pooled candidate set blind to arm. 3 or more seeds per arm |
| 6.4 `plan_adj_hydrogen.md` | Defer | A note | None beyond 6.1 | None |
| 6.5 `plan_adj_field_methane.md` | Proceed (protocol) with 7.5 | Concentration readings, not rates | Instrument access | Protocol only |
| 6.6 `plan_adj_sar_viewshed.md` | Defer, separate project | Nothing about wells | Out of scope | None |
| 7.1 `plan_scale_pretraining.md` | Defer | (a) label-efficiency | Label validity, not label count, is the bottleneck | None |
| 7.2 `plan_scale_active_learning.md` | Defer | (a) learning curves | Equal label count is not equal effort | None |
| 7.3 `plan_scale_benchmark.md` | Defer | A terrain-feature benchmark | Depends on P1 and on licence terms | Datasheet draft only |
| 7.4 `plan_scale_agency_tooling.md` | Defer | Software | Transfer not yet shown | None |
| 7.5 `plan_scale_field_campaign.md` | Redesign, highest value | (d) and (c), precision by stratum, a recall audit | Unresolved site outcomes may dominate. Wood casing. Sampling frame | Sample drawn features as well as candidates. Pre-register how unresolved sites are counted |

## B. Prioritized findings

Shared problems are grouped and list every affected plan. Status tags follow the brief: verified, contradicted, plausible but unverified, not assessable.

### B1. Feature-to-well validity is the central unknown, and it is unscheduled

- **Severity.** Invalidates inference for any well-level claim. Plans 3.0 to 3.7, 5.3, 5.4, 6.1, 6.4, 7.3 and 7.4.
- **Location and claim.** README rule 1 keeps evidence levels apart. That rule is correct. But the gameplan ranks feature-level work (A1 to A9) first, and leaves independent evidence to outreach (`expansion_gameplan_feasibility.md:123-127`, Phase D).
- **Evidence.** Verified. 27 of 424 annotated pits have a record within 25 m (`LEADERBOARD.md:491`). Orphan or abandoned matches at the primary radius sit inside the null (`record_assoc_pits_9t.md:56,62`). The LEADERBOARD explains the gap by mislocated records, wells with no surface expression and incomplete annotation (`LEADERBOARD.md:509-517`). None of those explanations has been tested.
- **Failure mechanism.** The drawn "pit" class could be mostly wells, partly wells, or mostly other depressions. Each case gives the same transfer recall, the same confuser reduction and the same benchmark score. So every downstream product is unanchored.
- **Minimum correction.** Make "what fraction of drawn pits are wells, by morphology and era" an explicit study. Answer it with a probability sample of drawn features, not only model candidates, using 4.6 historical positions and the 7.5 field visits.
- **Still unknowable after correction.** The well fraction among features nobody drew. That needs the independent search arm of 7.5.

### B2. Magnetometry is systematically blind to the oldest wells

- **Severity.** Materially weakens inference. Plans 4.1, 7.5, 5.4.
- **Location and claim.** "This is the only item that breaks the label circularity directly" (`expansion_options_methods.md:219`). Gameplan rates it "Highest" (`expansion_gameplan_feasibility.md:78`).
- **Evidence.** Verified externally. Hammack et al. (2023, *The Leading Edge*) found aeromagnetic surveys in forested Pennsylvania missed many 1860-1880 wells with wood casing. Plausible but unverified locally: casing was often pulled for reuse in early Pennsylvania fields. The methods doc already concedes cut-and-plugged wells may read weakly (`expansion_options_methods.md:233`).
- **Failure mechanism.** P(anomaly given well) varies by era. A pit-candidate stratum dominated by early wells would show a low anomaly rate even if every pit were a well. That biases P(steel | score bin) and any r fed into 5.4.
- **Minimum correction.** Stratify sites by an era proxy (record date class, 1800 sentinel, presence on a dated historic map). Add non-magnetic evidence for the early stratum: cellar walls, wood casing remnants, cable-tool debris, historic map position. Report P(anomaly) by stratum, never pooled. The same study also gives sUAS lidar a role, since decayed wood casing leaves a depression.
- **Still unknowable.** Sensitivity in the early stratum, unless some early wells have independent confirmation.

### B3. The transfer metric is undefined and the reference is mismatched

- **Severity.** Invalidates inference for the 3.1 decision rule as drafted. Plans 3.0, 3.1, 3.2 to 3.7, 7.4.
- **Location and claim.** `transfer_warren_prereg.md:29-30` sets K equal to the count of annotated features and compares against 9t "held-out recall 0.928 (F2 cutoff)". Plan 3.0's acceptance test says rerunning on 9t "reproduces the saved 9t cross-validation recall within rounding" (`plan_geo_transfer_protocol.md:19`).
- **Evidence.** Verified. K per km² is the recommended policy, still unchosen (`operating_point_policy_plan.md:47-54`). The 0.928 figure comes from inner-val-selected cutoffs (`expansion_options_methods.md:31` says so itself). The saved CV numbers depend on a non-deterministic inner split (B4). Recall at budget is steep in K (0.664 at 25, 0.781 at 30, 0.909 at 40 per km²). Fold min to max at 30 per km² is 0.723 to 0.900 inside one tile (`operating_point_policy_sweep_pit_pad_9t.md:95-97`). Contradicted: methods 3.0 step 4 and gameplan B1 score against agency wells, while plan 3.0 scores against drawn polygons.
- **Failure mechanism.** At a fixed per-km² budget, an area with half 9t's pit density shows higher recall from fewer targets alone. With K equal to the annotated count, recall becomes R-precision, and it moves with annotation completeness. The test can pass or fail on target density.
- **Minimum correction.** Primary metric: recall at a per-km² K fixed by the chosen policy, computed with the same code on the 9t out-of-fold raster and on the new area. Report target density per km² in both. Add a pre-specified secondary at K scaled to target density (K = c × density, with c fixed from 9t) so density effects can be separated. Replace the 0.928 reference with 9t recall at that K from `pit_prob_floor_outoffold_9t_05.tif`, which is deterministic. Score against completely annotated test blocks only. Agency records go to 5.6.
- **Still unknowable.** Whether one area's result generalises. One transfer site gives n = 1 at the area level.

### B4. Inner CV split is non-deterministic, and the saved manifest is not the trained split

- **Severity.** Execution risk, with a materially weakening effect on P2 and 5.1. Plans P1, P2, 3.0, 5.1, 6.3, 7.1, 7.3.
- **Location and claim.** `_save_cv_split_manifests_9t.py:2-4` claims "the saved split is the one they use". P1 says the NaN block id "carries" into the set difference (`plan_prereq_splits_manifests.md:3`).
- **Evidence.** Verified by running the trainer's fold logic on `data/9t/derived/05/pit_dataset_manifest.csv` (209 NaN block ids) six times under Python 3.13. The NaN position in `sorted(rest)` changed between runs, and so did the validation set. Fold 1 gave 71 or 61 validation pits. Fold 3 gave 56, 70 or 79. The logged training run had 73. Training-block counts in the log include the NaN entry (fold 0 has 73 against 72 in the saved manifest). The saved manifest drops NaN at line 37, so its validation lists differ in every fold. `_pad_unet_cv5.py:289` has the same pattern. Contradicted: the docstring claim. Unaffected: held-out folds, because `assign_folds` uses a groupby that drops NaN.
- **Failure mechanism.** Cutoffs and best epochs were chosen on a validation set nobody can reconstruct. Rerunning a fold gives different numbers for code reasons. A P2 history built from the saved manifest records the wrong train and val roles.
- **Minimum correction.** Drop NaN before building `rest`, as P1 step 1 proposes. Record the actual historical split from `checkpoint_extra["held_out_blocks"]` and the log counts. Mark the train and val roles as unrecoverable unless something else stored them. For audit purposes, treat every non-held-out block as "used" by model k. The 209 and 345 rows are off-tile annotations (`LEADERBOARD.md:303`), not unscored in-tile features. Correct the wording in methods line 30.
- **Still unknowable.** The exact validation blocks behind the published cutoffs.

### B5. Record-based recall is chance-dominated and confounded by coordinate provenance

- **Severity.** Invalidates inference for A6 and the 5.4 r term. Plans 5.4, 5.6, 3.4, 6.1, gameplan B1 and B7.
- **Location and claim.** "Compare recall with the frozen model against older documented wells" (`expansion_gameplan_feasibility.md:166-168`). Gate: "Newly documented wells have recall within the interval of older wells" (line 232).
- **Evidence.** Verified. Observed 0.156 for the 2022 cohort (`recall_gap_newly_documented_9t.md:19`), against a chance rate of about 0.09 for pits plus about 0.03 for pad interiors (`record_assoc_pits_9t.md:56,60`). Plausible but unverified: the newer cohort has better coordinates. The DEP outreach draft already asks how the coordinates were produced (`outreach_requests_drafts.md:41-44`).
- **Failure mechanism.** Raw match rates are mostly chance. If newer records are GNSS-located, their excess rises from coordinate accuracy alone. The test could then show "no gap" while true detectability is lower for undocumented wells.
- **Minimum correction.** Use excess over a cohort-specific shifted null as the statistic. Stratify by coordinate source once DEP answers. Run county-wide inference (records only, no annotation) to reach adequate n. Treat the gate's "within the interval" wording as invalid (see C).
- **Still unknowable.** Detectability of wells never documented. No record-based design can reach it.

### B6. Record association lacks a working positive control for pits

- **Severity.** Materially weakens inference. Plan 5.6.
- **Location and claim.** "Treat that as a reason to stop automatic snapping, not all association work" (`plan_task_record_association.md:11`). The conclusion is sound, and the coverage repair and whole-set translation are acknowledged as fixed (`record_assoc_pits_9t.md:49-62`).
- **Evidence.** Verified. At the pre-fixed 50 m pit radius, active records (0.111 against 0.090, null to 0.114) are also inside the null. The active excess appears only at 25 m, a sensitivity radius. Active pads inside polygons do exceed chance (0.058 against 0.021). Many active wells postdate cellar-pit practice, so active is not a clean pit control. Plausible.
- **Failure mechanism.** A test that cannot detect known-real association cannot interpret a null for orphans. Running A2 against the full annotations raises both observed and chance rates, so power need not improve. Annotations also may have been drawn with records visible, which would make association circular. Not assessable from the files.
- **Minimum correction.** Report predictive value (1 − null/observed) with an interval per group. Use active pads as the positive control. State whether annotators saw DEP points. Hold validation until independent coordinates exist.
- **Still unknowable.** Record position error. Only GNSS or NETL points give it.

### B7. Warren site: power, buffers and the "different lidar" premise

- **Severity.** Materially weakens inference. Plans 3.1, 3.0, and README rule 7.
- **Location and claim.** "Neighbouring Warren and Forest counties, which have different lidar programs" (`plan_geo_warren_forest.md:3`). "Held-out blocks at least 500 m from adaptation blocks" (README rule 7).
- **Evidence.** Contradicted. 9t uses "all nine 2019 D20" tiles (`icp_change_9t.md:332`). The seven Warren files are `USGS_LPC_PA_WesternPA_2019_D20_17TPG*` (verified listing, 311.9 MB, about 7 km²). Methods 3.1 itself says same survey. The 500 m figure has no stated basis. Pit patches are 128 m, pad patches 192 m, so label leakage needs only about half a patch plus jitter. Landscape dependence (same field, operator, era) runs for kilometres and no buffer removes it.
- **Failure mechanism.** Three roles with 500 m gaps on about 7 km² leave few test blocks. Expected intervals will likely span any margin, making "inconclusive" the probable outcome after the annotation is paid for.
- **Minimum correction.** Reframe 3.1 as a within-survey spatial transfer test. Treat eastern Warren and Forest QL1 (B19) as a separate sensor-shift arm. Justify the buffer from receptive field plus an empirical correlogram of 9t out-of-fold residuals. Before annotating, project the interval width by resampling as many 9t blocks as Warren can supply. Drop the adaptation role if the area cannot hold it.
- **Still unknowable.** Transfer to other counties from one site.

### B8. "Freeze preprocessing" conflicts with the resolution and thinning steps

- **Severity.** Execution risk, with possible OOD confounding. Plans 3.0, 3.1, 3.3, 4.7.
- **Evidence.** Verified. Pit and pad models ingest `features_pit_9t_05.tif` at 0.5 m (`_pit_unet_cv5.py:95`, `_pad_unet_cv5.py:91`). At 0.5 m, 45.2% of 9t cells hold no ground return (`BACKLOG.md:93-95`). Methods 3.0 step 3 thins "on a 1 m grid". The existing Warren derivatives are 1 m, from a different pipeline (`data/warren/derived/1m/full/`).
- **Failure mechanism.** Different ground density changes the void fraction and the interpolated scan texture at 0.5 m. Transfer then mixes sensor texture with landscape. A 1 m grid would violate the freeze.
- **Minimum correction.** Rebuild Warren at 0.5 m with the 9t code. Report void fraction at 0.5 m per block in the shift table. Thin to 9t ground density, then grid at 0.5 m. The existing `ground_density_warren_1m.tif` already supports the density table.

### B9. Confuser retraining cannot be scored as designed

- **Severity.** Materially weakens inference. Plans 6.3, 7.2.
- **Location and claim.** "Confuser false positives fall with feature recall loss within the preregistered margin" (`plan_adj_negative_classes.md:20`).
- **Evidence.** Plausible, by design reading. Retraining changes which detections score high in the audit blocks, and those new detections have no labels. LEADERBOARD flags single-seed deltas as "promising, not conclusive" (line 366). Confuser labels come from the same lidar morphology the model reads.
- **Failure mechanism.** Post-hoc labelling of each arm's new detections lets reviewers learn which arm produced them. Seed variance can exceed the treatment effect. A reviewer category such as "charcoal hearth" that partly holds early well platforms would teach the model to suppress real targets.
- **Minimum correction.** Retrain all three arms (baseline, confuser negatives, random negatives) on the same non-audit blocks, with 3 or more seeds each. Pool every arm's top-K audit detections, deduplicate, label once blind to arm, then score each arm against the pooled labels. Track the "P" and "U" counts suppressed by each arm.

### B10. Stacked context features need one shared fold scheme

- **Severity.** Execution risk, with leakage risk. Plan 5.1.
- **Evidence.** Verified that pit and pad folds are balanced separately (pit and pad `assign_folds` on different counts) and that the saved checks list different block counts. Plausible that roads use a different split (`road_chunking_by_split_40m_9t.png`, `_road_unet_1m_recall.py`). The plan's rule that every upstream model must exclude outer fold k cannot hold when pad fold k is not pit fold k.
- **Minimum correction.** Assign one block-fold scheme to pit, pad and road. Retrain the upstream pad and road models on it. Budget GPU time from measured epoch time. The backlog notes epoch time was under-reported by 1.8x (`BACKLOG.md:117-120`).

### B11. The synthetic terrain test answers a narrower question than 3.3 needs

- **Severity.** Materially weakens inference. Plan 3.3.
- **Evidence.** Plausible. A plane plus noise lacks 0.5 m interpolation texture and scan-pattern structure (B8), so sham and pit edits are both out of distribution. Corrections are acknowledged: sham edits, recomputed derivatives and all-pit sampling now appear in the plan.
- **Minimum correction.** Run step 4 first, stratifying existing out-of-fold recall by local slope and relief. It costs no new data. Insert edits into real low-relief 9t backgrounds only. Claim slope-context sensitivity, not Midwest performance.

### B12. Historical evidence needs a null that preserves oil-field context

- **Severity.** Materially weakens inference. Plans 4.6, 5.2.
- **Evidence.** Verified. The gameplan gate "historic-only points score above matched random" (`expansion_gameplan_feasibility.md:235`) conflicts with plan 4.6's rule to judge by interpretability. The gameplan revisions acknowledge this (line 22), but the gate table was not updated. Slope-matched random forest points sit outside oil fields, so the gate passes trivially.
- **Minimum correction.** Use the 5.6 shifted-set null within the oil field, with a radius set from measured georeferencing RMSE. Probe higher-yield sources first: 1870s-80s Second Geological Survey oil-region maps, 1860s oil-region atlases, and PennPilot 1937-42 aerials. All are plausible but unverified for 9t coverage.

### B13. Plume, thermal and vegetation arms lack an observable signal at these sites

- **Severity.** Invalidates inference for well-scale claims. Plans 4.4, 4.2, 4.3.
- **Evidence.** Verified externally. Tanager's 90% detection probability is 90 to 180 kg/h at 3 m/s wind (Carbon Mapper product guide). Kang et al. (2014) measured a mean of 0.27 kg/day per abandoned Pennsylvania well, about 0.011 kg/h. That is roughly four orders of magnitude below the threshold. For thermal, the only plausible pad-versus-clearing contrast is land cover, which the lidar CHM already measures.
- **Minimum correction.** Close 4.4 for Pennsylvania with a detection-limit note. Keep 4.2 and 4.3 deferred unless a leak-labelled dataset appears.

### B14. The gameplan's gate and phase tables contradict its own revisions

- **Severity.** Execution risk. It matters because the file is written for handoff to another assistant (`expansion_gameplan_feasibility.md:4,257`).
- **Evidence.** Verified. The half-score rule remains in the gate table (line 230) and in A3 (line 152). B7 still promises "density per 5 km cell with a 90% interval" (line 197), against plan 5.4's "Do not publish a density map". The A2 gate (line 229) predates the primary-radius rule. The "within the interval" recall-gap gate equates non-significance with equivalence (line 232). The A1 audit draw takes "about 20% of scored blocks" with no use history (line 132).
- **Minimum correction.** Replace sections 5 and 6 with the gates in C, or mark them superseded line by line.

### B15. Minor inconsistencies

- **Severity.** Minor. Several plans.
- Pad change flags read "19 of 404, about 15 by chance" in methods line 295 but "18 of 404, about 16" in `icp_change_9t.md:750`.
- "111 of which contain pits" (`_pit_unet_cv5.py:19`) against 115 pit-bearing blocks in the log and footprint.
- P1 says 6.8 m separation in "one pit fold". It appears in folds 3 and 4 (`cv_split_check_9t.json`).
- Plan 4.9 omits the stronger 613590 held-out pit result (gain −0.017, +0.05 excluded) and the ceiling caveat ("no gain" and "no room" cannot be told apart on 9t pits; `outside_review_response_20261103.md:9,37`).
- Plan 3.4 claims level (d) from RRC records, against README rule 9. It also cites the Permian 35% figure as if it applied to East Texas.
- Plan 7.5's sample sizes are correct (n = 42.7, 96.0, 24.0 for d = 0.15, 0.10, 0.20). The methods text "plan on 40 sites per estimate" slightly undershoots 43.
- Acknowledged as corrected: Platt monotonicity (README rule 5), the repaired association footprint and whole-set translation, the 5.4 equation subtracting the full documented population, the 3.4 unchanged baseline, and the 4.5 block on undated wells.

## C. Revised experimental gates

Every gate uses a 95% block-bootstrap interval for the difference, with Δ as the margin. Success means the interval clears the bar. Failure means it lies wholly past the bar. Anything else is inconclusive, and inconclusive is reported as such, never as no effect. No margin is set here. Each row names where its basis must come from, and the value is fixed in the prereg before scoring.

| Experiment | Question | Primary statistic | Success | Failure | Inconclusive | Where Δ comes from |
| --- | --- | --- | --- | --- | --- | --- |
| P1 split repair | Are splits reproducible? | Identical block lists across 3 fresh processes | Identical in all folds | Any difference | Not applicable | None. This is a software check |
| 3.0 protocol check | Does the protocol reproduce 9t? | Recall at policy K from the saved out-of-fold raster, run against the operating-point sweep | Matches the sweep exactly | Any mismatch | Not applicable | None. The computation is deterministic |
| 3.1 Warren transfer | Does pit and pad ranking survive within-survey transfer? | Recall difference at policy K, with target density per km² reported. Secondary at density-scaled K | Lower bound > −Δ | Upper bound < −Δ | Interval spans −Δ. Declare in advance if the projected width exceeds 2Δ | Agency-tolerable recall loss, or 9t between-fold spread at that K (0.723 to 0.900 at 30 per km²) as the floor below which a difference is not interpretable |
| 3.3 slope context | Does recall depend on local slope given pit size? | Recall by slope tercile on 9t out-of-fold. Paired score change for edits on real low-relief backgrounds | Lowest-tercile recall lower bound > top-tercile − Δ | Upper bound < top-tercile − Δ | Otherwise | The recall loss that would change the decision to try a flat county |
| 4.5 change at plugging | Does plugging between flights leave pad-scale change? | Flag rate at eligible wells minus the placebo rate, matched controls | Lower bound > 0 and n meets the prereg minimum | Upper bound < the smallest change worth detecting | Otherwise, including n below the minimum | The 0.16 to 0.22 m detectable mean change on slopes under 15° (`outside_review_response_20261103.md:77`) |
| 4.6 historic sources | Is source S a usable well-position source? | Georeferencing RMSE on held-out control points, symbol interpretability (two-digitiser agreement), excess match to DEP over a shifted null | RMSE under the limit, and excess lower bound > 0 | RMSE over the limit, or no interpretable symbols on several dates | Otherwise | The RMSE limit at which the null match rate within that radius stays under a stated share |
| 4.7 drone density | How fast does detection of lidar-visible sites degrade with density? | Recall at policy K versus thinned ground density, same sites | Not a gate. Report the curve, with the 9t density rung as anchor | Not a gate | Not a gate | None. Label it conditional on selection by visibility |
| 5.6 association | Do records mark features beyond chance? | Excess over the shifted null, and predictive value 1 − null/observed, per group, at the primary rule | Positive control (active pads) excess lower bound > 0 and the target group's predictive-value lower bound > the field-use minimum | Positive control passes and the target group's excess upper bound < the field-use minimum | Positive control fails, which means the test is uninformative | The field-use minimum predictive value, from what a crew accepts as wasted visits |
| A6 recall gap | Are newly documented wells harder to detect? | Difference in excess over cohort-specific nulls, stratified by coordinate source | Lower bound > −Δ (equivalent within Δ) | Upper bound < −Δ | Otherwise | The size of gap that would change a density estimate by a stated factor |
| 6.3 confusers | Do adjudicated confuser negatives beat random negatives? | Difference in labelled-confuser detections per km² at policy K (confuser arm minus random arm), plus the change in drawn-feature recall, pooled blind labels, 3 or more seeds | Confuser reduction lower bound > 0 and recall-loss lower bound > −Δ | Reduction upper bound < 0, or recall-loss upper bound < −Δ | Otherwise | Acceptable feature-recall loss, against seed spread |
| 4.1 and 7.5 pilot | Is casing detectable at lidar sites, by era? | Anomaly presence by stratum (documented steel-era wells, early-era wells, pits with no record, metal confusers, blanks) | Not a gate at 3 to 5 sites. Report practicality and per-site outcomes | Not a gate | Not a gate | Population sensitivity needs the 7.5 design |
| 7.5 campaign | What share of candidates and drawn features are wells? | Stratum-weighted proportion with outcome (d), (c) or unresolved. Pre-registered bounds with all unresolved counted as non-wells and as wells | Bound interval width at or under the target | Not applicable | Width over the target. Report bounds | Required precision from the decision the estimate feeds |

## D. Feasible sequence

The critical path runs through independent evidence, not code. Three things decide it: DEP's answer on coordinate provenance and GNSS points, a usable pre-1880 historical source, and a field partner. Everything else is ordered by information per hour.

**Begin now (desk, no labels, no outside party).**

1. User decisions. Choose the K policy and how margins will be set (C). Both are blocking and cost nothing.
2. P1 repair. Drop NaN before the inner shuffle in both trainers. Record the historical split as recoverable (held-out) and unrecoverable (val and train). Do not retrain yet.
3. Send A0 outreach the same day: NETL drone lidar, the DEP coordinate questions plus GNSS points, the magnetometer partner. These have the longest lead time.
4. 3.0 on existing rasters. Implement the scorer and reproduce the operating-point sweep from `pit_prob_floor_outoffold_9t_05.tif` exactly. Project the Warren interval width by resampling 9t blocks.
5. 4.6 source probe. Check 1870s-80s survey maps, oil-region atlases and 1937-42 aerials. This is the cheapest route to evidence about the earliest wells.
6. 5.6 reanalysis. Add predictive value and the active-pad positive control to the existing outputs. Record whether annotators saw DEP points.
7. 3.3 step 4 only. Stratify existing out-of-fold recall by slope.
8. 4.5 step 1 only. Pull flight dates from USGS project metadata, then count eligible wells.
9. Notes: the 4.9 radar scope note, the 4.4 detection-limit note, the 5.4 identifiability note.

**Wait for decisions or labels.**

- 3.1 Warren annotation waits on items 1 and 4. If the projected width exceeds 2Δ, change the design before annotating. Time one block of annotation to replace the missing labelling estimate.
- 6.3 waits on P1 and on a reviewer pair. Budget 30 h of review for 150 candidates (`confuser_codebook.md:26`), plus the pooled post-retrain labelling.
- 5.1 waits on one shared fold scheme and road and pad retraining.
- A6 at scale waits on DEP coordinate provenance and county-wide inference.

**Wait for an outside party.**

- 4.7 waits on NETL data. 4.1 and 7.5 wait on a partner, access and instruments. 5.6 validation waits on GNSS or NETL points.

**Deferred.** 3.2, 3.4 to 3.8, 4.2, 4.3, 5.2, 5.3, 5.5, 6.1, 6.2, 6.4, 6.6, 7.1 to 7.4.

**What would justify scaling up.** A 7.5 pilot, or a 4.6 source, showing that a stated share of drawn pits are wells with a usable interval width. Without that, further geographic transfer only measures agreement with one annotator's feature concept.

## E. Strongest surviving ideas

1. **7.5 field campaign, reframed to sample drawn features as well as candidates.** It is the only design that can measure the share of drawn features that are wells. That number decides whether every (a)-level result means anything for wells. Its value holds whether the answer is high or low.
2. **4.6 historical positions.** It is the only plausible independent evidence for pre-1880 wells, the stratum magnetometry misses. A negative result can also be clear: no source with RMSE under the limit and interpretable symbols.
3. **4.7 drone density ladder.** Native against thinned clouds on the same sites isolates point density cleanly. It costs about 10 h once data arrive. It answers whether denser lidar would buy detection, provided the result is labelled conditional on visibility-based site selection.
4. **5.6 association as a negative result.** The repaired 9t analysis already supports a clear claim: proximity alone cannot assign orphan records to features at these radii. Adding predictive values and the positive control makes it publishable as a negative result. GNSS points would turn it into a measurement of record position error.
5. **3.0 and 3.1 as a within-survey case study.** Once K is fixed and the reference is recomputed, this gives a defensible answer to whether the feature detector holds outside one tile. Its value is mainly as a precondition, since it says nothing about wells.
6. **6.3 confusers, with the pooled blind design.** The random-negatives control is the right idea. With pooled labels and seeds, a null can retire the specific hypothesis, not the whole idea.
7. **4.5 plugging-change test, if dates allow.** It is a clean natural experiment with a measured placebo. A null is informative at the stated detection floor.

## Open questions that would most change these recommendations

- Did annotators have DEP well points visible while drawing pits and pads? If yes, any association with annotations is partly circular, and B6 becomes an invalidating finding.
- How were DEP orphan and abandoned coordinates produced, and are the 2022-2026 additions GNSS-located? This decides whether A6 can be repaired.
- Does any source give pre-1880 well positions over 9t with RMSE in the tens of metres or better? If yes, 4.6 moves onto the critical path ahead of magnetometry.
- Which K policy will you adopt, and what recall loss would an agency accept? Without these, no transfer gate can be pre-registered.
- How many Warren test blocks can the seven D20 tiles supply after buffers, and how many features do they hold? If too few, 3.1 should drop its adaptation role or wait for more tiles.

## Sources

All local paths are relative to `C:\Users\colto\Documents\GitHub\lidar_project`. Everything was read as is. Nothing was modified, trained or downloaded.

- Plans: all 38 files in `docs/plans/`, including `README.md`, P1 and P2.
- Method and gameplan: `docs/iterations/expansion_options_methods.md`, `docs/iterations/expansion_gameplan_feasibility.md`.
- Results: `record_assoc_pits_9t.md`, `recall_gap_newly_documented_9t.md`, `operating_point_policy_plan.md`, `operating_point_policy_sweep_pit_pad_9t.md`, `icp_change_9t.md`, `well_age_morphology.md`, `outside_review_response_20261103.md`, `LEADERBOARD.md`, `BACKLOG.md`, `transfer_prereg_template.md`, `transfer_warren_prereg.md`, `confuser_codebook.md`, `outreach_requests_drafts.md`.
- Code: `notebooks/wellsight_v2/s3_train/_pit_unet_cv5.py`, `_pad_unet_cv5.py`, `_save_cv_split_manifests_9t.py`, `s5_eval/_record_assoc_pits_9t.py`, `_common.py`.
- Data: `data/9t/derived/05/pit_dataset_manifest.csv`, `data/9t/results/splits/*`, `data/9t/models/pit/unet_cv5/_pit_cv5_ann712_train.log`, `data/9t/models/pad/unet_cv5/_pad_cv5_ann712_train.log`, plus listings of `data/_source/lidar/warren_sheffield/` and `data/warren/`.
- Split check: the trainer's fold logic was re-run six times in separate Python 3.13 processes against the manifest above.
- [Hammack, Veloski, Sams and Kohnke (2023), Aeromagnetic surveys for the location of undocumented orphaned wells, The Leading Edge 42(12)](https://www.citedrive.com/en/discovery/aeromagnetic-surveys-for-the-location-of-undocumented-orphaned-wells)
- [Kang et al. (2014), Direct measurements of methane emissions from abandoned oil and gas wells in Pennsylvania, PNAS 111(51)](https://collaborate.princeton.edu/en/publications/direct-measurements-of-methane-emissions-from-abandoned-oil-and-g/)
- [Carbon Mapper product guide, Tanager detection specification](https://carbonmapper.org/articles/product-guide)
