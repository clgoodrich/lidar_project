# Framework 3.5. Oklahoma and Kansas modality comparison

**Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded, trained or scored.**
**Evidence level.** (a) drawn feature, reported per modality arm and per truth origin. Records enter only as level (b) through 5.6. No level (d).
**Depends on.** 3.0 scorer, P1 (isolated trainer, derived buffer), P2 (audit guard), 3.1 annotation guide. The label-budget curve on 9t (S2) needs no new data and can run first.
**Blocks.** Any claim that optical or fusion inputs help in open terrain.

## 1. Problem and objective
Oklahoma and Kansas hold large orphan inventories in open terrain with active infrastructure. Lidar sees the ground. Optical imagery sees pads, tanks, gravel and vegetation scars. Whether adding imagery to lidar helps ranking there is unknown.

**Q1 (primary).** Does a fusion model (lidar plus optical channels) beat a lidar-only model by at least δ_gain in recall at K = 40 per km², when both are trained from scratch on the same labelled blocks with the same recipe and tuning budget?
**Q2 (descriptive).** How do lidar-only and optical-only models compare on the same test blocks, paired?
**Q3 (descriptive).** How do missing data and active infrastructure change each arm's scores?
**Q4 (reference).** How does the frozen 9t lidar model (zero-shot) do on the same test blocks?

**Hypothesis (Q1).** H0 paired gain at or below δ_gain. H1 above δ_gain.

**What this study can show.** Whether early fusion raises ranking of drawn features on common blocks, and by how much, under one recipe.
**What it cannot show.**
- That any candidate is a well. All results are level (a).
- That fusion is better with a different architecture, a late-fusion design or more tuning. A null here is not evidence that the mechanism fails.
- Transfer of the answer beyond these windows and these two imagery sources.
- A fair comparison of effort in minutes. Effort is matched by trial count, compute cap and identical labels. Annotator minutes are logged but not matched.
- Anything about wells with no surface expression.

## 2. Scope
In. Imagery coverage and date audit, co-registration, one common footprint, two independent annotation passes, five arms (section 3), paired scoring, missingness and activity tables.
Out. Late fusion, SAR, thermal and other modalities. Missouri windows (backlog). Level (d). Roads.

## 3. Definitions
- **Arms.** All use the same U-Net family, patch sampler (whole-window exclusion of held-out ground), augmentation, epoch cap and three seeds.
  - **L0.** Frozen isolated 9t lidar model, zero-shot. Reference.
  - **L1.** Lidar-only, trained from scratch on the target training blocks.
  - **O1.** Optical-only, trained from scratch.
  - **F1.** Fusion by channel concatenation of the L1 and O1 inputs, trained from scratch. Only the input channel count differs from L1.
  - **L2.** Lidar fine-tuned from the 9t checkpoint. Reference, never in the primary contrast, because initialisation differs.
- **Arm policy.** Mean probability over three seeds, declared in the prereg. Seed spread is descriptive.
- **Matched tuning.** The same number of random-search trials (12, proposed), the same GPU-hour cap and the same seeds per arm. A ledger JSON per trial records config, GPU-seconds and validation score, failures included. Selection uses validation blocks only.
- **Truth origin.** Each drawn feature carries `seen_in` (lidar pass, optical pass, both) and `activity` (active-looking, inactive-looking, unclear). The primary truth is all drawn pit and pad features. Strata are exploratory.
- **Roles.** Train, validation, test, audit. Different windows, separated by the derived P1 buffer. Audit is opened once.
- **Common footprint.** Eligible blocks present in both modalities and inside the imagery date rule.
- Unit, K, scored footprint, matching and intervals follow `fw_00_common.md` section 4. K = 40 per km² of eligible area.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| OK RBDMS wells, orphan list, dictionaries | `data/_source/reference/wells_ok_occ/` | held |
| KS KGS wells | `data/_source/reference/wells_ks_kgs/ks_kgs_oil_gas_wells.csv.gz` | held |
| USGS 2026 orphan file | `data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| Rebuilt windows and projects | `data/_source/reference/lidar_catalogue/lidar_win_windows_us.csv`, `lidar_win_projects_us.csv`, `lidar_win_download_summary_us.csv` | held (discovery only) |
| 9t derivative builders, trainer pattern | `s1_build/_build_derivatives.py`, `s3_train/_pit_unet_cv5.py`, isolated pad trainer `_pad_unet_iso_cv5.py` | held |
| Scorer and inference wrapper | `s5_eval/_transfer_score.py`, `s4_infer/_transfer_infer.py` | 3.0 |
| Isolated pit trainer, splits, guard | P1, P2 | future |

Windows (documented orphans in window, project, tiles, GB). OK Washington (420, `OK_Statewide_D22`, 16, 1.40), OK Okmulgee (150, D22, 20, 1.47), OK Creek (70, D22, 16, 1.48), OK Rogers (255, D22, 16, 1.43), OK Nowata (175, `FEMA_R6_OK_Craig_Nowata_QL2_Lidar`, 21, 0.54), KS Montgomery (135, `KS_Statewide_2018_A18`, 4 large tiles, 2.06), KS Labette (100, A18, 4, 1.58). OK Kay and Pawnee are held in reserve for audit. Window coverage figures are upper bounds from tile boxes.

### 4A. Assumed data
| Item | Assumed | Format, resolution, fields, CRS, licence | VERIFY |
|---|---|---|---|
| Lidar | The listed projects cover the windows with class 2 | LAZ, 3DEP QL2, UTM 15N (EPSG:6344) expected for all windows listed. USGS public domain | `pdal info --summary` per window. Union cover from geometries. Ground density per block |
| Lidar flight dates | Recoverable from project metadata | XML. D22 publication dates are 2024 but flight dates are unknown | Read metadata. Record in `docs/iterations/lidar_acquisition_dates.md` |
| NAIP | Four-band (R, G, B, NIR) orthoimagery for OK and KS, one or two cycles after 2018 | GeoTIFF, 0.6 m or 1 m, UTM 14 or 15 by tile. USDA public domain | Query the source for window coverage and acquisition dates per tile. Save to own folder with hashes |
| NAIP geometric accuracy | A horizontal accuracy specification of metres, not centimetres | Specification document | Read the contract spec. Measure shift against lidar-derived road and field edges per block (S3) |
| State orthoimagery | Optional second source (Oklahoma and Kansas portals) | Unknown resolution and dates | Inventory only. Not used in the primary |
| Well records | Coordinates and status usable at pad scale | OK RBDMS (status, type, dates), OK orphan list, KS KGS, USGS file | Read dictionaries. Count status classes. Annotators never see them |
| Labels | Do not exist yet | Two blind passes with the 9t guide, extended for activity | Time one block per pass |
| Annotators | Four reviewers (two per pass) and an adjudicator | People | Roster and exposure log |
| Compute | One GTX 1070 Ti (8 GB), mixed precision | Hardware | Measure epoch time on one fold before the plan is sized |

## 5. Prerequisites and decisions
P1 and P2 done. The label-budget curve (S2) fixes the minimum labelled training features. δ_gain, the tuning budget, the imagery date rule, the registration tolerance, N_min and the seed count are fixed in the prereg before any arm is trained. δ_gain is the extra recall at K = 40 that pays for acquiring and registering imagery and for a second review workflow. The prereg is committed before training.

## 6. Procedure
**S0. Coverage and temporal eligibility.** Script `s1_build/_optical_coverage_okks.py` (new). Per block record lidar date, imagery date, imagery sensor and resolution, cloud or gap flag, gap in years, and any visible new pad after the lidar date. Output `data/ok_washington/results/modality/mod_coverage_dates_okks.csv` and one table per window. Eligibility rule. Gap at most the prereg value. Others form a stratum.

**S1. Fetch (gated).** Script `s1_build/_fetch_naip_okks.py` (new, resumable, hash, own folder, no credentials). Lidar windows through the 3.2 pattern. Heavy files on F: with `.gitignore` rules per new directory.

**S2. Label-budget curve on 9t.** Script `s5_eval/_label_budget_curve_9t.py` (new). Train the lidar recipe on 25, 50 and 100 percent of the isolated 9t training blocks and score recall at K. Output `data/9t/results/transfer/label_budget_curve_9t.csv`. It sets the minimum train features for Q1. The earlier instance-segmentation result (74 pits, 51 platforms, overfit) is the warning that too few labels make every arm unstable.

**S3. Co-registration.** Script `s1_build/_coreg_optical_to_lidar_okks.py` (new). Estimate a per-block shift of imagery to lidar-derived road and field-edge features. Report the shift distribution. Apply the same coregistered imagery to O1 and F1. Fusion without co-registration is a sensitivity arm.

**S4. Stacks.** Script `s1_build/_build_optical_stack_okks.py` (new). Resample imagery to the 0.5 m grid of the lidar stack. Resampling adds no information and is stated as such. Normalisation statistics fitted on training windows only. Outputs `data/<area>/derived/05/features_okks_<tag>_05.tif` and optical stacks (own `.gitignore` rule per directory).

**S5. Roles and blocks.** Train and validation windows. OK Okmulgee, Creek and Washington. Test windows. OK Rogers (same program, new ground), OK Nowata (program shift), KS Montgomery and Labette (state and program shift, a joint contrast). Audit. OK Kay or Pawnee. Blocks of 375 m, roles drawn with a seed in the prereg, stratified by slope tercile. Output `data/<area>/results/modality/mod_blocks_roles_<tag>.gpkg`.

**S6. Projected width and prereg.** Resample 9t paired out-of-fold blocks and grids of density and clustering. If projected paired width exceeds 2δ_gain, add test blocks or change the design before labelling. Commit `docs/iterations/transfer_prereg_okks.md`.

**S7. Two independent annotation passes.** Pass L uses lidar derivatives and hillshade only. Pass O uses imagery only. Different reviewers. No model output, no well records. Adjudicate by IoU 0.3 into one truth with `seen_in` and `activity`. Complete blocks, empty ones included. Re-annotate 20% of blocks for agreement per pass. Log minutes per block per pass. Output `data/<area>/results/modality/mod_truth_features_<tag>.gpkg`.

**S8. Train arms.** Script `s3_train/_modality_unet_train_okks.py` (new) with `_trial_ledger_okks.py`. Arms L1, O1, F1 with identical recipe, 12 trials each, three seeds, validation blocks only for selection. L2 as a reference. Isolated sampler rejects windows touching test or audit ground. Time an epoch first.

**S9. Score once.** L0, L1, O1, F1, L2 on the same test blocks with `_transfer_score.py` and `s5_eval/_modality_compare_okks.py` (new). Paired block bootstrap, same resampled blocks for every arm.

**S10. Missingness, activity and truth-origin tables.** Recall by `seen_in`, by `activity`, by imagery gap stratum and by block missingness. Tank batteries and fresh gravel are expected optical lures. Candidates that are not matched go to the 6.3 codebook.

**S11. Hand-off.** Pass records to 5.6 without scoring. Active wells give a pad-level positive control there (annotators did not see records). Pit-level association is not validated.

## 7. Statistical analysis plan
- **Estimand.** Paired gain G = recall(F1) minus recall(L1) at K = 40 per km² of eligible area, pooled over complete eligible test blocks in the Oklahoma windows (Rogers and Nowata). Block resampling is stratified by window.
- **Unit.** The block. Pits on one pad are one cluster.
- **Interval.** Paired block bootstrap, B = 2000, same resampled blocks for all arms. Fewer than 15 blocks in a window adds a permutation interval.
- **K policy.** 40 per km². Candidate extraction, tie rule and matching are identical across arms.
- **Roles.** Train fits weights. Validation picks trials and epochs. Test is scored once. Audit supports the final claim and is opened once. Margins and thresholds never come from test or audit.
- **Secondary and descriptive.** L1 versus O1 and F1 versus O1 paired differences. Kansas windows as a separate joint-contrast table. L0 and L2 beside the primary arms, never in the primary contrast. Density-scaled K. K = 30. Calibration.
- **Seeds.** Arm policy is the three-seed mean probability. Seed spread is descriptive and never a margin.
- **Truth origin.** Primary uses the union truth. Sensitivity on the intersection (`seen_in` both). A truth built from one modality would favour that modality, which is why two passes are used.
- **Multiplicity.** One primary. Everything else is exploratory.

## 8. Quality control and leakage
1. Row counts at every join. Blocks per arm identical.
2. CRS asserted (zone 15 for these windows). Imagery shift per block saved.
3. No training window intersects any validation, test or audit ground. Normalisation fitted on training windows only.
4. No audit block in any training, tuning or selection list. Test scored once.
5. Tuning ledger complete for every arm. Equal trials, equal GPU-hour cap, equal seeds. Failed trials kept.
6. Both annotation passes blind to model output and to records. Exposure logged.
7. Hashes for imagery, tiles, checkpoints, splits, prereg. Second run reproduces outputs.
8. Registration plots of ten features per window on hillshade and imagery.
9. Every number in a doc comes from a saved file.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Coverage and date table complete, at least N_min common blocks, label-budget curve met, projected paired width at most 2δ_gain | Annotate and train |
| Success (Q1) | Lower bound of G above δ_gain | Fusion helps at least δ_gain under this recipe. Level (a) |
| Failure (Q1) | Upper bound of G below δ_gain | Fusion does not deliver δ_gain here. A smaller positive gain is real but not worth the extra pipeline |
| Inconclusive | Interval spans δ_gain | Report. Add blocks |
| Descriptive arms | Intervals only | No gate |
Margin source. δ_gain comes from the review-visit and workflow cost of imagery against the recall it buys, fixed in the prereg before training. It never comes from seed spread or fold spread. A failed implementation is not evidence that fusion cannot work. State which it is.

## 10. Deliverables
All paths are repo-relative.
- `notebooks/wellsight_v2/s1_build/_optical_coverage_okks.py`, `_fetch_naip_okks.py`, `_coreg_optical_to_lidar_okks.py`, `_build_optical_stack_okks.py`
- `notebooks/wellsight_v2/s3_train/_modality_unet_train_okks.py`, `_trial_ledger_okks.py`
- `notebooks/wellsight_v2/s5_eval/_label_budget_curve_9t.py`, `_modality_compare_okks.py`
- `data/9t/results/transfer/label_budget_curve_9t.csv`
- `data/ok_washington/results/modality/`, `data/ok_rogers/results/modality/`, `data/ok_nowata/results/modality/`, `data/ks_montgomery/results/modality/` (coverage, shifts, blocks, truth, ledgers, scores, figures)
- `docs/iterations/transfer_prereg_okks.md`, `modality_compare_okks.md`, `lidar_acquisition_dates.md`
- Figures use blue `#1F5FA8`, orange `#D97706`, grey `#8E959B` with marker shapes for arms. Validator worst-pair numbers go beside each palette.

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Imagery misregistered by metres against 5 to 10 m features | Per-block co-registration. Sensitivity without it |
| Truth favours one modality | Two blind passes. Union primary, intersection sensitivity |
| Tuning imbalance | Ledger, equal trials, equal cap, equal seeds |
| Too few labels for from-scratch training | Label-budget curve sets the minimum. L2 reference |
| Imagery older or newer than lidar | Date rule and stratum |
| Active infrastructure read as abandoned | `activity` class. Tables by activity |
| Large Kansas tiles | Window fetch on F:. Time one tile |
| Fusion gain only from extra parameters | Same architecture, only input channels change. State it |
| Modality missingness | Common-footprint blocks. Missingness table |

## 12. Resources
Estimates to be replaced by measurement.
- Desk S0 to S1. About 12 hours.
- Fetch. Lidar about 1.4 to 2 GB compressed per window and 3 to 9 times that decompressed. NAIP about 0.3 GB per 25 km² window at four bands. F: only.
- Annotation. Two passes, two reviewers each. Placeholder 60 blocks per test window at 15 minutes per block per reviewer is about 60 reviewer-hours per window for both passes. Training windows need more. Replace with S7 timing.
- Training. Three arms, 12 trials, three seeds on one 1070 Ti. Placeholder 2 hours per trial gives about 72 GPU-hours for tuning and about 18 for final seeds. Measure epoch time first and multiply by 1.8 for the known under-reporting.
- Run the large-file audit after every fetch and build.

## 13. Handoff and open questions
- Optical source choice (NAIP, state orthos or both) and the imagery date rule.
- δ_gain, tuning budget, seed count and N_min.
- Reviewers for two passes and an adjudicator.
- Confirm class 2 coverage and flight dates.
- Whether Missouri windows join as an extension.
- Whether late fusion should be a second experiment.

## 14. Documentation updates
`transfer_prereg_okks.md`, `modality_compare_okks.md`, `analysis_log.md`, `LEADERBOARD.md` (arm rows), `BACKLOG.md`, `literature/CITATIONS.md` (NAIP specification, fusion references), master plan status.

## Review revision 2 (third review, 2026-11-04)
Verify coverage and target morphology before any data expansion.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

## Review revision 3 (full rewrite, 2026-11-05)
Built in from `adversarial_review_claude.md` and `review_response_20261104.md`. Matched effort is made measurable by trial count, compute cap and shared labels. New target-area labels are planned with two blind passes. Fusion is compared with lidar-only trained the same way. Initialisation is separated from the primary contrast.
