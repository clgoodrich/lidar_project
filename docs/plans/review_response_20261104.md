# Response to the two adversarial reviews

**Date:** 2026-11-04
**Reviews:** `docs/plans/adversarial_codex_review_20261104.md` (Codex) and `docs/plans/adversarial_review_claude.md` (Claude).
**Authoritative result:** `docs/plans/protocol_gates_and_metrics.md`. Acquisition needs: `docs/plans/download_manifest.md`.

Status words. **Reproduced** means I re-ran a check here and got the same result. **Confirmed in files** means I read the code or document. **Confirmed at source** means I read the external page. **Reviewer only** means I did not check it. **Narrowed** means the finding stands in a smaller form.

## 1. What I got wrong
These are errors in my own work, found by the reviews and checked.
1. **The association and recall-gap results used the wrong input. Reproduced.** The matched layer holds 481 detections and all carry `dup_on_pit = 1`. My loader dropped every row with that flag, so it kept only the 204 unmatched leftovers. The pad file is the unmatched leftover set from the matching step. The conclusion that orphan records are not above chance, and the recall-gap figures 22 of 141 and 0 of 6, are withdrawn. The corrected result may go either way.
2. **The saved split manifest is not the trained split. Reproduced.** In four fresh processes the inner validation blocks differed in folds 0, 2 and 4. The cause is NaN block ids landing at a changing position in a sorted set. My manifest script dropped NaN, so its train and validation roles match no trained model. Its held-out lists are valid. I wrote that "the saved split is the one they use". That is false.
3. **"Different lidar programs" for Warren is false. Confirmed in files.** The seven files are `USGS_LPC_PA_WesternPA_2019_D20_17TPG*`, the same program as 9t.
4. **"63 wells" at Oil Creek is false. Confirmed at source.** NETL says "a total of 63 potential well sites were located on two hillsides using LiDAR data". They are potential sites found with lidar, not confirmed wells, and the page does not say any data are released.
5. **The min separation of 6.8 m is in two pit folds, not one.** My own output shows it in folds 3 and 4.
6. **My gameplan gate table contradicted its own revisions.** The half-score rule, the overlapping-interval gate, the matched-random historic gate and the density surface stayed in the tables.
7. **Plan 3.4 claimed level (d) from RRC records** against my own rule 9, and cited the Permian 35% figure as if it applied to East Texas.
8. **I described the 209 and 345 rows with no block id as unscored in-tile features.** They are off-tile annotations (`LEADERBOARD.md`, line 303).
9. **I never checked that an isolated pad trainer already existed.** `_pad_unet_iso_cv5.py` exists and is documented in `nisar_checks_9t.md` section 7.

## 2. Findings, checked and dispositioned
| Finding | Source | How checked | Verdict | Change made |
|---|---|---|---|---|
| Association and recall-gap exclude matched detections | Codex 1 | Read layers and flags | **Reproduced** | Results withdrawn. Section 4 of the protocol sets the input contract |
| Proposals are not one-to-one globally | Codex 4 | 197 rows, 153 unique detections | **Reproduced** | Global assignment rule |
| Pit footprint reused for pads | Codex 4 | 115 pit and 129 pad blocks in the manifests | **Reproduced** | Modality-specific footprints |
| Null population and exchangeability | Codex 4 | Read script | Accepted | State what the null conditions on |
| Sampler reads held-out windows | Codex 2 | Read `_dl.py` lines 235 to 290 | **Confirmed in files** | Isolation rule, iso pit trainer in P1 |
| Inner split not reproducible | Claude B4, Codex 2 | Ran fold logic in 4 processes | **Reproduced** | P1 rescoped, split roles labelled |
| 14 global normalisation numbers leak into each fold | trainer docstring | Read | **Confirmed in files** | Fold-local normalisation rule |
| No untouched 9t block exists | Claude P2 | Each block trains 4 of 5 models | Accepted (follows from design) | P2 rescoped to comparative tests, new area for absolute claims |
| Warren K and reference mismatched | Codex 3, Claude B3 | My own prereg line 29 and 30 | **Confirmed in files** | Protocol section 2. Warren prereg needs rewriting before use |
| K policy not chosen | Claude B3 | Policy doc says "not yet chosen" | **Confirmed in files** | User decision, provisional 40 per km² |
| Warren is the same survey | Claude B7 | File names | **Confirmed in files** | 3.1 reframed within-survey |
| Warren area may be too small for three roles | Claude B7 | Seven tiles, about 7 km² (reviewer figure) | Accepted, **not measured** | Project interval width from 9t before annotating |
| 500 m buffer has no basis | Codex 2, Claude B7 | Reasoned | Accepted | Derive from receptive field and a correlogram |
| Freeze preprocessing conflicts with 1 m Warren derivatives | Claude B8 | Models read `features_pit_9t_05.tif` | Accepted | Rebuild at 0.5 m |
| Warren header CRS contradicts earlier note | Codex 11 | Not checked | **Reviewer only** | Verify during P1 |
| 63 potential sites, not wells | Codex 6 | WebFetch of NETL page | **Confirmed at source** | 4.7 premise rewritten |
| Magnetometry misses wood or removed casing | Codex 5, Claude B2 | NETL page says so | **Confirmed at source** | Era strata in 4.1 and 7.5 |
| Hammack 2023 found missed 1860 to 1880 wells | Claude B2 | Not read | **Reviewer only** | Cite as reported, fetch the paper |
| Field search sensitivity not identified | Codex 5 | Reasoned | Accepted | Three-arm design, bounds |
| 27 of 424 pits have a record within 25 m | Claude B1 | `LEADERBOARD.md` line 491 | **Confirmed in files** | Feature-to-well question made first |
| Feature-to-well share is the unmeasured central unknown | Claude B1 | Follows from the above | Accepted | Arm A of the field design |
| Active-record 50 m rate is inside the null | Claude B6 | My own table, 0.111 against 0.090 (0.067 to 0.114) | **Confirmed in files**, but on withdrawn input | Positive control must be re-established |
| Implied predictive value about 0.26 | Claude B1 | Computed from withdrawn input | **Not used** | Rule keeps the statistic, drops the number |
| Recall gap confounded by coordinate quality | Claude B5 | Reasoned, DEP answer pending | Accepted | Cohort-specific nulls, stratify by source |
| Confuser retraining cannot be scored as designed | Claude B9 | Reasoned | Accepted | Pooled blind labelling, 3 seeds, random-negative arm |
| Stacking needs one shared fold scheme | Claude B10, Codex 7 | Pit and pad folds balance on different counts | Accepted | Protocol section 8 |
| Codebook positive class uses context | Codex 7 | Read codebook | **Confirmed in files** | Target morphology defined without score or context |
| Synthetic terrain test too narrow | Claude B11 | Reasoned | Accepted | Slope stratification first |
| Historic gate uses matched random points | Claude B12 | Read gameplan | **Confirmed in files** | In-oil-field shifted null |
| Satellite methane threshold far above a mean leak | Claude B13 | Kang checked at source. Tanager number not checked | **Narrowed** | 4.4 closes for PA only after the detection-limit table is read |
| Thermal pixel size limits the test | Codex 8 | Not read at source | **Reviewer only** | Observability gate first |
| Change-detection controls are ordinary terrain | Codex 9 | Read control script description | Accepted | Eligible pads without the intervention |
| 3,368 m² is not a physical floor | Codex 9 | Reasoned | Accepted | Recovery test through the whole chain |
| Acceptance tests were readiness gates | Codex 10 | Read plans | **Confirmed in files** | Readiness and scientific gates split |
| Dependent units (site-seasons, seeds) | Codex 10 | Reasoned | Accepted | Effective sample rule |
| Pretraining needs a named comparison | Codex 10 | Reasoned | Accepted | Three budgets named |
| Methods document still holds superseded claims | Codex 12, Claude B14 | Read | **Confirmed in files** | Superseded list, protocol section 15 |
| Minor inconsistencies (19 or 18 of 404, 111 or 115 blocks, 6.8 m folds, 4.9 omissions) | Claude B15 | Folds checked. Others not | Partly checked | Fixed where I own the text |
| Codebook budget is 30 reviewer-hours | Codex 11 | Arithmetic | Accepted | Pilot measures real throughput |
| Isolated pad trainer lowers F2 recall 0.912 to 0.891 | Codex 2 | Doc exists. Numbers not read | **Reviewer only** | Cited as reported |
| Domain classifier does not identify cause | Codex 12 | Reasoned | Accepted | Methods text superseded |
| Pretrained benchmark and tooling rely on stable inputs | Codex | Reasoned | Accepted | Stay deferred |

## 3. Where I narrowed or disagree
- **Claude B13 asks to reject 4.4 for Pennsylvania.** The arithmetic is plausible. Kang is real but covers 19 wells, and 3 of 19 were high emitters. The 90 to 180 kg per hour figure is not checked. I close 4.4 only after reading the Carbon Mapper detection table. It costs one small download (D4).
- **Claude's implied predictive value.** It was computed from the withdrawn input. I keep the statistic and drop the number.
- **Claude calls A6 repairable with a cohort-specific null. Codex shows its input was wrong.** Both hold. A6 needs the corrected input first, then the cohort-specific null, and DEP's coordinate answers.
- **Codex rates several modality plans Redesign. Claude rates them Defer.** I defer 4.2 and 4.3 until the observability gate shows a target fraction and contrast worth testing.
- **Claude says Warren "may not hold" three roles. Codex says run a bounded pilot.** I take both. Project the interval width from 9t block resampling first, and drop the adaptation role if the area is too small.
- **Both reviews state sizes, resolutions and detection limits I have not seen.** The manifest marks these **estimate**, **measure** or **unverified**. I did not accept any of them as fact.

## 4. Merged decision per plan
| Plan | Decision | One-line reason |
|---|---|---|
| P1 | Proceed, rescoped | Deterministic inner split, label historical roles, spec an isolated pit trainer, hash everything |
| P2 | Proceed, rescoped | Comparative audit on 9t only, new area for absolute claims |
| 3.0 | Bounded pilot | Fix K, reproduce 9t from the saved raster first |
| 3.1 | Redesign | Within-survey case study. Project interval width. Rebuild at 0.5 m |
| 3.2 | Defer | Desk inventory only |
| 3.3 | Redesign | Slope stratification of existing recall first |
| 3.4 | Defer | Remove level (d) and the Permian figure |
| 3.5 to 3.7 | Defer | Metadata-only inventories |
| 3.8 | Defer | Feasibility note only |
| 4.1 | Redesign, then pilot | Era strata, casing evidence |
| 4.2, 4.3 | Defer | Observability gate |
| 4.4 | Close for Pennsylvania after one check | Detection limit against mean leak rate |
| 4.5 | Blocked | Flight dates, matched eligible controls |
| 4.6 | Proceed, elevated | Only route to pre-1880 positions. Several sources, several dates |
| 4.7 | Proceed as a request | Reframed as potential sites found with lidar |
| 4.8 | Bounded pilot | Coverage and chip status only |
| 4.9 | Note only | Add the 613590 held-out result and the ceiling caveat |
| 5.1 | Redesign | Shared fold scheme, retrain upstream |
| 5.2, 5.3 | Defer or blocked | Dates, no P(well) yet |
| 5.4 | Identifiability only | Withdraw the recall-gap input |
| 5.5 | Defer | Low decision value now |
| 5.6 | Redesign | Repair the input contract first |
| 6.1, 6.2, 6.4, 6.6 | Defer | No distinct well question |
| 6.3 | Redesign, then pilot | Pooled blind labels, seeds, random negatives |
| 6.5 | Protocol only, with 7.5 | |
| 7.1 to 7.4 | Defer | Baseline integrity, input contract |
| 7.5 | Redesign, highest value | Three arms, bounds |

## 5. Merged sequence
Desk work now, no outside party, no labels.
1. **User decisions.** K policy, margin basis, R4 (did annotators see DEP points), R5, R6 in the manifest.
2. **P1.** Remove NaN before the inner shuffle, label split roles, specify the isolated pit trainer.
3. **Outreach R1 to R3.** Drafts exist. Longest lead time.
4. **3.0.** Reproduce the operating-point sweep from the saved raster. Project the Warren interval width by resampling 9t blocks.
5. **4.6 search.** D6 and D7 as searches. Then D5.
6. **Association repair.** Input contract, modality footprints, global assignment, predictive value, positive control. Mark the rerun exploratory.
7. **3.3 step 4.** Slope stratification.
8. **4.5 step 1.** Flight dates (D1) and eligible well count.
9. **Notes.** 4.9 radar scope, 4.4 detection-limit note after D4, 5.4 identifiability.

Then, after decisions or labels. 3.1 annotation (only if projected width is at most 2Δ), 6.3 pilot, 5.1, A6 at scale. After outside parties. 4.7, 4.1 and 7.5, 5.6 validation.

What would justify scaling up. A 7.5 pilot or a 4.6 source showing that a stated share of drawn pits are wells, with a usable interval width. Without that, more geographic transfer only measures agreement with one annotator's feature concept.

## 6. Questions that would change the plan
**Answered 2026-11-04.** Q1 annotators did not see DEP points. Q4 K is 40 per km². Recall-loss margin is set per experiment before scoring. Still open Q2, Q3, Q5, Q6, Q7.

1. Did annotators have DEP well points visible while drawing? If yes, association with annotations is partly circular.
2. How were DEP orphan and abandoned coordinates produced, and are the 2022 to 2026 additions GNSS-located?
3. Does any pre-1880 source give well positions over 9t with RMSE in the tens of metres or better?
4. Which K, and what recall loss would an agency accept?
5. How many Warren blocks survive the derived buffers, and how many features do they hold?
6. Which independent area and reviewers can be reserved without exposure to model output?
7. Is there a partner who can support probability-sampled area searches?

## 7. Not checked
**Resolved 2026-11-05.** The 18 or 19 of 404 pad flags are both correct. 18 is the v1 surface (`change_features_summary_9t.json`, placebo 4.04%, 16.3 expected by chance). 19 is the v2 surface (`change_features_summary_v2_9t.json`, placebo 3.79%, 15.3 by chance). `icp_change_9t.md:750` quotes v1 and the methods text quotes v2. The pit-bearing block count is 115 (`pit_dataset_manifest.csv`), so "111" in the pit trainer docstring was stale and is fixed. Both trainers now drop NaN block ids before the inner shuffle (P1 step 1, reproduced as 8 identical splits in 8 fresh processes).

Still not checked. Warren header CRS. Warren area and block counts. Hammack et al. (2023). The Tanager detection threshold. Landsat and ECOSTRESS pixel sizes. The isolated pad comparison numbers. All sizes and coverage claims in the manifest.
