# Adversarial code review of expansions/ (TARGET = ALL), 2026-11-06

**Verdict.** No expansion is READY. 5 are BROKEN (3.4, 3.6, 4.9, 5.3, 6.4). 20 run but are untrusted. 12 are incomplete. All 247 tests pass, but most cannot fail on the defects below.

The review was read-only. No source file was edited. The prompt was `docs/plans/expansion_code_review_blank_prompt.md`.
Five independent reviewers covered the groups. The lead reviewer re-checked one headline blocker per group by hand. Those are marked **[lead-verified]**.
The earlier drafts `docs/plans/expansion_code_review_20261106.md` and `tmp/expansion_review_20261106/` were deliberately not read. This keeps the findings independent.
This document is separate from `docs/plans/expansion_consolidated_review_20261106.md`, which another session wrote. The two have not been reconciled.

Probe scripts are in the session scratchpad, which is temporary:
`C:\Users\colto\AppData\Local\Temp\claude\ea748db540cb3e4e\033c106c-62ab-4afc-8624-d42bba36ce2e\scratchpad\`.
They are `probe_expkit.py` and the subfolders `p1p2\`, `geo\`, `mod\`, `tasks\` and `adjscale\`.

## 0. Code baseline and changes made during the review

The review started at commit `6aed32b`. Another session changed 11 files in the working tree while it ran.
They were re-checked at 10:21 CST. None of the changes closes a finding in this document.

| Changed file | What changed | Effect on findings |
|---|---|---|
| `_shared/src/expkit.py` | `decide()` rejects bad kind or margin, and returns inconclusive on non-finite bounds | none. SH-01, SH-02 and the `new_run` and `clopper_pearson` issues re-probed and still reproduce |
| `p1/src/_pit_unet_iso_train_9t.py` | `P2_SRC` path fixed | none. `--buffer-m` still defaults to 0 (P1-02) |
| `3_0/src/_transfer_score_lib.py` | void raster must match the probability grid | none. The one-NaN-pixel edge rule (G-05) is unchanged |
| `7_1/src/_ssl_label_subsets_9t.py` | reads the P1 split through the producer's reader, with role names mapped | partly helps P1-01 for 7.1 only. 7.1-01 still holds: `_ssl_finetune_pit_9t.py:200` still uses `audit = set()`, and subsets never read the audit list |
| `7_1/src/_ssl_corpus_chips_us.py` | not reviewed after the change | unknown |
| `7_5/src/_field_analysis_bounds.py` | inclusion-probability validation, and an inconclusive result for fewer than 2 clusters | none. `sensitivity()` is unchanged (7.5-02) |
| the five matching `test_*.py` | regression tests added | not re-run |

## 1. Coverage ledger

Tests: the loop in `expansions/README.md` was run over 38 files. Result: 247 passed, 0 failed, 0 skipped, 0 errors.
The tests pass, but most could not fail on the defects below. See "Tests that cannot fail".

| ID | Files read | Skipped or skimmed | Tests |
|---|---|---|---|
| _shared | expkit.py, test_expkit.py, INTERFACES.md | fw_00_common.md (claims) | 5/5 |
| P1 | all 8 src + test, README, dry-run outputs | docs/*.md, .npz contents | 9/9 |
| P2 | all 6 src + config + test, README, dry-run CSV | docs/*.md | 8/8 |
| 3.0 | all 9 src, config, README, test, result JSON/CSV | docs | 9/9 |
| 3.1 | xfer_lib, score_k40, frozen_infer, blocks_roles, projected_width, tile_inventory, test, config | build_derivs, annot_tools, error_review, prereg_draft (grep) | 11/11 |
| 3.2 | config, loaders, harmonise, window_cover, density_void, stage_runner, state_table, thin, adapt_finetune | wells_inventory | 8/8 |
| 3.3 | config, slope_recall_tercile, terrain_edit, confound_logit, area_gate, S1 results | seam_check | 6/6 |
| 3.4 | geo_transfer_core, adapt_train, transfer_tables, wetland_strata, config, test | observable_depth_audit, relief_norm, rrc_orphans, window_choice | 10/10 |
| 3.5 | label_budget, modality_compare, modality_train | coreg, optical_stack, registry, blocks_roles, adjudicate | 6/6 |
| 3.6 | config, pad_recall_by_class, status_by_pad, equipment_rule | field_area_scores, label_packs, unmatched_sample, wells_snapshot | 6/6 |
| 3.7 | config, record_assoc | inventory_rows, tile_probe, window_rank | 4/4 |
| 3.8 | config, rate_difference, injection_recovery, site_matching, placebo, insar_series | active_layer, observability, reference_stability, wells_sites | 6/6 |
| 4.1 to 4.9 | every src/*.py and config, README tables, key result JSONs | docs/*; 4.6 source_search/aerial_probe, 4.8 coverage_table, 4.9 fetch/figure skimmed only | 45/45 |
| 5.1 | leakage_audit, stage2_learner, stage2_features (part) | reliance_edits, retrain_manifest, shared_folds, upstream_inventory | 11/11 |
| 5.2 | core_tools, interval_labels, model_arms | date_audit, strata, label_audit_sample, pair_features, sentinel_support | 12/12 |
| 5.3 | core, io, scenarios, bootstrap, endpoint_check, sensitivity (part) | data_audit, report_tables, exposure_layers body | 7/7 |
| 5.4 | all 5 scripts, config, outputs | test bodies | 6/6 |
| 5.5 | geometry_tools, by_pad, agreement, cost_mc | survey_ingest, redraw_sample | 8/8 |
| 5.6 | all src, config, test, both run folders, both gpkgs | — | 12/12 |
| 6.1 to 6.6 | configs and main stage scripts | 6.1 map; 6.2 reverse_confusion; 6.3 agreement/sheets/figure; 6.4 test; 6.5 claim_audit | 34/34 |
| 7.1 to 7.5 | configs and main stage scripts | 7.1 pretrain_objectives, identity_probe, runtime_bench; 7.3 card/validity/fresh_checkout; 7.4 fixture_build; 7.5 sheet_generate/ingest | 16/16 |
| _template | README (only file) | — | — |

## 2. Findings, worst first

Most findings fall into eight patterns that cut across expansions. The patterns come first. The individual findings follow.

### Cross-cutting patterns
1. **Cutoff mismatch.** Targets are scored at 0.10, and references or baselines at 0.35 (pit) or 0.525 (pad). Affected: 3.4, 3.5, 3.6, 3.7, 3.8 and 7.3.
2. **Bootstrap silently drops NaN draws.** Affected: expkit `block_bootstrap` and `bootstrap_diff`, and local copies in 4.9 and 7.4. The consumers that hit it are 3.x pooled recall on sparse targets, 4.2, 4.3, 4.4, 5.2 AUC and 5.3 enrichment.
3. **Recall can exceed 1.** Hits on truth outside the denominator are counted. Affected: expkit `recall_at_k`, 3.4 core, 7.3 scorer, 6.3 pooled score.
4. **The audit set is not usable.** It is not frozen on disk, every consumer's reader crashes on its header, the guard has holes, and 7.1 runs on silently without it.
5. **The footprint is chosen from truth.** The 9t reference uses only the 115 pit-bearing blocks of 144. Affected: 3.0 tables (and therefore all of 3.x), 3.3, 5.3, 5.4, 5.6.
6. **Handoff contracts are broken.** Split role names, buffer JSON keys, the audit header, the policy checkpoint, `proposals_56_9t.csv`, and pit/pad `det_id` collisions.
7. **"Latest run" is picked by name, not time.** Affected: 4.2, 4.3, 3.2.
8. **Tests assert only that a verdict is a valid word**, i.e. `verdict in {success, failure, inconclusive}`. Affected: 3.0, 4.3, 4.5, 7.1, 7.2.

### BLOCKER

**[SH-01] block_bootstrap and bootstrap_diff drop NaN draws without counting them**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: `expansions/_shared/src/expkit.py:209`, `:224` (`np.nanpercentile`).
- What: resamples where the statistic is undefined, such as draws with zero truth, are discarded. The interval is then conditioned on the outcome.
- Evidence: in `probe_expkit.py`, 1 of 10 blocks holds truth. 687 of 2000 draws were dropped. The CI collapsed to [1.0, 1.0].
- Impact: 18 expansions use it. A local copy exists in 4.9 `paired_gain_boot`. 4.4's rate ratio dropped 65 of 2000 draws. On a sparse geography target (2 of 20 blocks with truth), 231 of 2000 draws were dropped.
- Test: `_,_,_,d = block_bootstrap(stat, [(1,1)]+[(0,0)]*9); assert not np.isnan(d).any() or <function reports n_dropped>`.

**[P1-01] The split CSV's role words differ from its consumers'**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: `0_prerequisites/p1_splits_manifests/src/_split_future_csv_9t.py:19` writes `val` and `heldout`.
- Readers: 6.3 `_confuser_unet_cv5_9t.py:71` raises on anything other than `train`/`inner_val`/`held_out`. 5.2 `_era_model_arms_9t.py:241` filters on `held_out` and gets 0 rows.
- Impact: 6.3 crashes. 5.2 gets an empty fold map. 3.3 is also affected.
- Test: `assert {r[2] for r in fc.flatten(doc)["pit"]} == {"train","inner_val","held_out"}`.

**[P2-01] The audit CSV starts with `#` header lines, and every consumer reads it with plain read_csv**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: the writer is `p2_audit_set/src/_audit_draw_blocks_9t.py:178-184`. The readers are:

  | Reader | Line |
  |---|---|
  | 4.2 | :102 |
  | 4.3 | :45 |
  | 5.1 `_context_shared_folds_9t.py` | :109 |
  | 5.2 | :231 |
  | 7.1 | :202 |
  | 7.2 | :134 |
  | 7.3 | :73 |
  | 7.5 | :251 |
  | 3.3 `_slope_terrain_edit_9t.py` | :246 |

- Evidence: `pd.read_csv(audit_blocks_9t_dryrun.csv)` raises `ParserError: Expected 1 fields in line 3, saw 3`. With `comment="#"` it reads 17 rows.
- Impact: every audit-aware stage crashes once the file is frozen. None of them goes through the sha256 guard `ag.load_audit`.
- Test: for each consumer, `reader(write_audit_csv(...))` returns 17 ids.

**[P1-02] The derived 100 m buffer is never applied by default. The leakage gate "passed" at 0 m**
- Severity BLOCKER. Certainty PROVEN.
- Where: `_pit_unet_iso_train_9t.py:150` and `_split_sampler_leakage_9t.py:358` both default `--buffer-m` to 0.0. The future split puts no gap between folds.
- Evidence: every fold in `sampler_leakage_test_9t.json` shows `buffer_m: 0.0` with `gate: pass`. Per pit fold, 49 to 59 of the 71 to 76 train blocks lie within 100 m of held-out ground.
- Impact: "zero leaking windows" holds only at a buffer of zero. Every isolated model inherits this.
- Test: `main([... "--dry-run"])` without `--buffer-m` must fail or read `buffer_derivation_9t.json`.

**[G-01] Transfer targets are scored at cutoff 0.10 against a reference built at 0.35 / 0.525**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: `3_4_gulf_texas/src/_geo_transfer_core.py:65` sets `CAND_THR = 0.10`. No caller of `score_raster` passes `thr`: `:1134`, 3.5 `_okks_modality_compare.py:84`, 3.5 `_okks_label_budget_9t.py:115`, 3.6 `_ca_pad_recall_by_class.py:40`. The reference `xfer_ref_block_tables_9t.json` uses `cutoff_by_task`.
- Evidence: on the same 9t raster, recall is 0.5746 at cutoff 0.10 and 0.9085 at 0.35.
- Impact: a built-in difference of about −0.33. Every transfer verdict from 3.4 to 3.8 comes out "failure", even with perfect transfer.
- Test: score the 9t mosaic through `gt.score_raster` against the 3.0 tables and assert `|diff| < 0.02`.

**[5.3-01] Candidates outrank every documented record because missing hazard components are skipped**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: `5_tasks/5_3_risk_ranking/src/_risk_ranking_core.py:210-219` (`index_from` averages finite components only) and `:265` (`h_no_plug_record` is NaN for candidates).
- Evidence: every one of the 327 candidates has H = 0.665824. The maximum record H is 0.652649. E has 2 unique values.
- Impact: the top 50 of scenarios A and B are all candidates. Within the top 50, H is constant, so row order decides the ranking. A P = 0 site (`cand_474`) is in the A top 50.
- Test: `index_from(df(h_a=[3,3], h_b=[0,nan]))[1] <= [...][0]`.

**[5.3-02] Scenario A is driven by one 0/1 road column**
- Severity BLOCKER. Certainty PROVEN.
- Where: `_risk_ranking_core.py:326`. Six of seven receptors are missing and are skipped (`strict=False`).
- Evidence: redrawing H at random leaves `rank_A` unchanged.
- Test: fail when E has fewer than 2 components or fewer than N+1 distinct values.

**[4.9-01] The `lidar_weak` stratum is selected on the baseline score, so a worthless arm shows significant gain**
- Severity BLOCKER. Certainty PROVEN. **[lead-verified]**
- Where: `4_modalities/4_9_more_radar/src/_sar_new_score_9t.py:121-122` (`(y==0) | (sb <= q25)`). The same rule is in `_sar_power_baseline_9t.py:35-38`.
- What: regression to the mean favours any second score. The lidar_weak row is also flagged `primary`. The placebo is computed but never subtracted.
- Evidence: an arm with the same information as the baseline shows overall gain +0.0016. In lidar_weak it shows +0.077, CI [0.048, 0.103], which clears the 0.05 bar.
- Test: `sa = latent+e2`; assert the lidar_weak decision is not `success`.

**[7.1-01] Pretraining fine-tune scores audit blocks every run, and drops the guard when the file is missing**
- Severity BLOCKER. Certainty TRACED.
- Where: `7_scale/7_1_pretraining/src/_ssl_finetune_pit_9t.py:201-203` uses `audit = set()` when the file is absent. At `:241`, held-out prediction never subtracts audit. `_ssl_label_subsets_9t.py:93-122` never reads audit.
- Context: `data/9t/results/splits/audit_blocks_9t_v1.csv` does not exist. So all 7.1, 7.2 and 7.3 runs on disk ran with no audit exclusion.
- Test: `run(..., audit_csv=f)`; assert the audit block is absent from `oof_blocks_*.csv`.

**[6.4-01] DEP depth is 100% null, so the hydrogen penetration flag can never be produced**
- Severity BLOCKER for 6.4 (it removes its only analytic output). Certainty PROVEN. **[lead-verified]**
- Where: config `record_fields.depth = TOTAL_MAXI`; `6_4_hydrogen/src/_h2_screen_run_9t.py:91-96`.
- Evidence: `venango_wells_all.gpkg` has 20,108 rows. `TOTAL_MAXI` is non-null in 0 of them.
- Impact: depth coverage is always 0, so the flag is always dropped. 6.1's `records_with_depth` is always 0.

### MAJOR (grouped by area)

**Shared and prerequisites**
- **[SH-02] recall_at_k has no scope check.** `expkit.py:198-200`. Recall reached 3.0 in the probe. `block_of_cand` is unused. PROVEN.
- **[P1-03] Consumers read `pit_buffer_m` and `pad_buffer_m`; P1 writes `buffer_m`.** 3.1 `_xfer_blocks_roles_wfm.py:140` and 3.3 `:241` raise KeyError, which `--provisional-buffer` cannot catch. No pad buffer is derived. PROVEN.
- **[P1-04] The buffer "range" comes from a flat variogram.** `_split_buffer_derive_9t.py:86-91`. The semivariogram is flat within about 2%. Lag 1 misses the 95%-of-sill mark by 0.12%. That choice decides between a 75 m and a 100 m buffer. The test enshrines white noise returning `lags[0]`. PROVEN.
- **[P1-05] `verify()` passes tampered seed, frac or list hashes and self-declared exclusions after a rehash.** `_split_future_write_9t.py:98-120`. PROVEN.
- **[P2-02] The audit hash breaks after checkout.** With `core.autocrlf=true` and `* text=auto`, checkout converts the file to CRLF and `load_audit` refuses it. `_audit_guard_lib.py:51-79`. PROVEN in a scratch repo.
- **[P2-03] Guard holes.** `_audit_guard_lib.py:105-140`. PROVEN.
  - The guard ignores `buffer_m`: a window 1 m away passes.
  - It never checks held_out: audit blocks reach calibration.
  - Audit ids missing from `blocks` give a silent PASS.
- **[P1-06] Dead handoffs.**
  - 5.1 names `_pit_unet_iso_cv5.py`, which does not exist.
  - 3.4, 3.5 and 3.7 read `policy/best.pt`, which has no producer.
  - 3.3 already ran against a non-canonical audit path.

  PROVEN.

**Geography**
- **[G-02] The reference footprint is selected on truth.** The 29 zero-pit blocks have no out-of-fold prediction and are marked edge. The reference is therefore 115 of 115 truth-bearing blocks, while targets use every block. PROVEN.
- **[G-03] Three scorers disagree on identical input.** One A/B fixture gives recall 1.0 under 3.0, 0.0 under 3.1, and a third convention under 3.4 (no dedupe). PROVEN.
- **[G-04] Two 3.4 core bugs.** PROVEN.
  - Truth id 0 can never match (`fill=0` at `:751`).
  - A straddling truth is matched but sits outside the denominator. Recall is reported as 1.0 where the true value is 0.0.
- **[G-05] One NaN pixel marks a whole block as edge** and drops its truth. `_transfer_score_lib.py:115`. PROVEN.
- **[G-06] The preregistration is hashed, never enforced.** `_transfer_decision_report.py:291-306` and 3.1 `_xfer_score_k40_wfm.py:151-160`. Cutoff, IoU and dedupe are not in the prereg. TRACED.
- **[G-07] The 3.1 low-density stratum is never scored.** All 19 such blocks are `ineligible`. PROVEN.
- **[G-08] The 3.8 injection test is insensitive to noise.** `_ak_injection_recovery_ak1.py:52-55` computes `invert(phi+dphi)-invert(phi)`, which equals `invert(dphi)`. Recovered rate: 2.0208 at noise 0.3, 2.0208 at noise 300. PROVEN.
- **[G-09] The 3.7 shifted null collapses.** At 100 records, 0 of 49,950 shifts were kept, and excess is NaN. PROVEN.
- **[G-10] The 3.6 equipment union cannot lose.** The rule is evaluated on truth pads only, not at equal K. PROVEN by construction.
- **[G-11] Partial checkpoint loads are silent.** `_geo_transfer_core.py:968-974`: shape-mismatched keys are skipped (3.4 A1 first conv, 3.5 L2 head). Band order is not checked. TRACED.
- **[G-12] 3.3 terrain-edit donors include the scoring model's training pits.** `_slope_terrain_edit_9t.py:255`. TRACED.
- **[G-13] 3.4 "complete blocks only" is not enforced.** No footprint is passed, `void_frac.fillna(0)` is applied, the water mask is unused, and `--classes pit,pad` scores pads as pit truth. TRACED.

**Modalities**
- **[4.4-01] The tail gate extrapolates about 100× past the data** and declares success. The `lo_lower > 0` check is always true. A largest rate of 0.092 kg/h against a limit of 9 kg/h still gives `success`. PROVEN.
- **[4.8-01] Undated chips count as negatives.** With PEMA `date: null`, every chip gives `failure` and the gate outputs "unusable here". PROVEN.
- **[4.1-01] The outcome follows identity even when the magnetometer disagrees.** A confirmed well with no anomaly gives `confirmed_well_d`. A blank with a 50 nT pick still passes the gate. PROVEN.
- **[4.3-01] Sentinel-2 indices come from 5 m upsampled DN stacks**, while the config says the values are reflectance. SCL keeps water and snow as valid. PROVEN.
- **[4.5-01] S3 recovery tests a different chain** (global DEM shift) from the one S4 analyses (per-pass point shift). The disc injection is a step function. TRACED.
- **[4.5-02] Survey seams confound results.** Treated pads sit a median 36 m from a seam, controls 220 m. Seams are not modelled. The late flight date is wrong. TRACED.
- **[4.2-01 / 4.3-02] Baseline uninformative by design.** Added value is measured on a population matched on the baseline's own features, so lidar AUC is 0.506. TRACED.
- **[4.2-02] Registration and tie points are never used** in the verdict or in T2. TRACED.
- **[4.2-03] `latest_run` sorts by hash name.** In the probe, an older run was returned. PROVEN.
- **[4.3-03] V0 leak labels have no date filter.** Placeholder leak codes yield a pre-specified "CLOSED". TRACED.
- **[4.7-01] Thinned rungs keep the native ground classification**, so the density curve is optimistic. TRACED.
- **[4.6-01] Historic marks are compared against all records with no date filter** (1,024 of 1,068 wells are post-1930). The agreement CI counts pair members twice. TRACED.

**Tasks**
- **[5.6-01] The adjudication sheet is not blind.** `det_id` 0 to 480 are matched rows. Spearman correlation of det_id with score is −1.0 within each source. PROVEN.
- **[5.6-02] The default null cannot be computed for plugged pits.** 0 of 6000 shifts were accepted. About 85% are rejected elsewhere, a direction-biased selection. PROVEN.
- **[5.5-01] The IoU ≥ 0.3 gate caps |ln area ratio| at 1.204.** 392 of 995 pads are dropped, including 276 of 332 small pads. PROVEN.
- **[5.5-02] Costs have no unit check, and road length is never written**, so the road cost term is always 0. TRACED.
- **[5.4-01] The D bootstrap interval reaches 678, above the possible maximum of 647.** PROVEN.
- **[5.4-02] The density footprint is chosen from truth** (blocks with n_pits > 0). TRACED.
- **[5.2/5.3 NaN] AUC and enrichment stat_fns return NaN** for one-class or no-event resamples, which feeds SH-01. TRACED.

**Adjacent and scale**
- **[7.4-01] Refused tiles re-enter the derivative build** through the folder glob `*.la[sz]`. PROVEN (code).
- **[7.4-02] The `--features` CRS check is a tautology:** `assert_crs(r, r.crs)`. A feet stack passes. PROVEN.
- **[7.3-01] The leaderboard scores at 0.10; the config says 0.35 / 0.525.** The shipped baseline has `"thr": 0.1`. PROVEN. **[lead-verified]**
- **[7.3-02] The benchmark scorer matches across blocks**, so a bootstrap draw reached recall 2.0. This is latent: 0 of 73 pit matches cross blocks, but 7 pad matches do. PROVEN.
- **[7.2-01] G is chosen from the same replay and floored to 0** (G_raw = −0.0043). The same pattern is in 7.1. PROVEN.
- **[7.2-02] The live retrain burns all truth**, not only acquired labels. SUSPECTED (intent), TRACED (code).
- **[7.1-02] `--audit-once` is a stub.** It re-scores the same out-of-fold set. PROVEN.
- **[7.5-01] The target width is unreachable.** At n = 182, the bound width is 0.407 against a target of 0.30. About 800 sites would be needed. PROVEN.
- **[7.5-02] Control sensitivity mixes cells and wells.** 4 of 4 controls found gives 0.5. PROVEN.
- **[6.6-01] The walk-time filter drops every segment at 1 Hz with 2 to 3 m GNSS error.** Modelled time is 0. PROVEN.
- **[6.6-02] The cumulative viewshed counts void cells as "seen by nobody".** The 9t void fraction is 0.47. PROVEN.
- **[6.5-01] Unit and instrument errors do not invalidate a visit.** A ppm·m row stays `valid=True`. PROVEN.
- **[6.1-01] Pit and pad `det_id` values collide.** `proposals_56_9t.csv` has no producer. PROVEN.
- **[6.3-01] Confuser negatives can be centred on matched truth pits.** TRACED.

### MINOR (abbreviated)
- **Shared:** `new_run` silently reuses one directory for the same config on the same day. `clopper_pearson(0,0)` returns (nan, 0, 1).
- **P1:** the normalisation trace passes with folds missing. `committed_hash` raises when git is missing. Frozen CSVs are overwritten without a check. `_audit_reserve_warren` compares bounds without reprojecting.
- **P2:** the audit draw uses pit-bearing blocks only, but is also applied to pads.
- **3.x:**
  - There is no multiplicity correction anywhere.
  - The `resolve` string compare refuses `40` against `40.0`.
  - The 3.3 area-gate commands point at a missing area.
  - `assign_roles` uses `buffer_m: 0`.
  - The 3.5 gain plot clips negative gains.
  - The 3.8 season mixing is unhandled.
  - A LAS file with no CRS is treated as EPSG:6346.
- **4.x:**
  - 4.4 has quasi-separation in its rate ratio.
  - 4.9 runs a permutation across arms on different scales.
  - 4.9 S4 overwrites a tracked "frozen" CSV.
  - About 30% of 4.8 road "intersections" are pass-through joints.
  - 4.1 has era-stratum gaps and a circular assert.
  - Sensor scaling is unverified for ECOSTRESS and Sentinel-2.
- **5.x:**
  - Degenerate capture-recapture rows print se = 0.
  - The 5.4 frame-hash guard is skippable.
  - `build_sites` merges only the nearest candidate.
  - The `rank01` extremes are mishandled.
  - The endpoint fallback key is unread.
  - The cohort definitions disagree.
  - The 5.6 other-states runner assumes a projected CRS.
  - The `cx` column name collides with `GeoDataFrame.cx`.
  - Absolute paths are written into outputs.
- **6.x / 7.x:**
  - 6.6 agreement uses a one-sided tolerance, and its coarse-grid cell mapping is wrong (45 of 100 rows).
  - 7.1 fine-tuning reuses the same windows every epoch.
  - 7.4:
    - A NaN known-well fails late, as exit 4.
    - Lon/lat input is accepted silently.
    - `--calibration` with `--model both` always fails.
    - K is applied per class, which doubles the budget.
    - An unparseable CRS is overridden silently.
    - Feet conversion happens only in the check (SUSPECTED).
  - 7.5 arm B is not restricted to the frame.
  - 6.3 reuses a stale label raster, and its pooled score includes out-of-audit truth.
  - 6.2 point records can never match an IoU rule (SUSPECTED).
  - The 7.3 export check skips a layer on any exception.
  - 6.1 blind-zone candidates use up K.
  - The 7.2 stop rule is ignored, and 3 seeds were run against 10 preregistered.

### Tests that cannot fail, or miss the bug they claim to cover
- **Verdict is any valid word:** `test_4_3::test_chain`, `test_4_5::test_controls_and_compare`, the 3.0 `test_harness_from_prereg_and_decision`, 7.1 `test_subsets_finetune_and_curves`, 7.2 `test_split_items_replay_curves`.
- **`test_expkit::test_bootstrap_and_decide`** asserts only `lo < p < hi`. It misses SH-01.
- **Leakage at zero buffer:** P1 `test_sampler_leakage_isolated_is_zero` runs at a 0 m buffer. P2 `test_split_file_check` treats an audit block in held_out as correct. P1 `test_semivariogram_and_range` enshrines the degenerate range.
- **Fixtures that sit inside the safe region:**
  - 3.4 `test_score_raster_end_to_end` uses ids 1 and 2, so it misses G-04.
  - 3.1 `test_match_iou` locks in G-03.
  - 3.7 uses few records, so it misses G-09.
  - 3.8's injection test cannot fail (G-08).
  - 4.9 tests the `all` stratum only.
  - 4.1 uses a confirmed well that has an anomaly.
  - 4.4 checks only that the fit runs.
- **Circular construction:** 7.4 fixtures are built by the code under test, and its expected strings copy the checker's messages. 5.5 uses a constant scale inside the gate.
- **No test at all for:** the P1 CSV writer, any consumer reading the audit or split files, or the cutoff parity between target and reference.

## 3. Claims versus reality

| Claim (source) | What the code does | Verdict |
|---|---|---|
| "canonical split interface (block_id, fold, role)" (INTERFACES.md, P1 csv doc) | roles `val`/`heldout`; consumers expect `inner_val`/`held_out` | FALSE |
| S5 leakage "gate pass" (P1 README) | ran at `buffer_m: 0.0` | TRUE as stated, misleading |
| Mode `window` "forbids any training window within the buffer of an audit block" (P2 doc) | the guard ignores buffer_m | FALSE |
| "`--verify` fails on any difference" (P1) | ignores seed, frac and exclusion provenance | FALSE |
| "One deterministic scorer for 9t and every target" (3.0) | three scorers disagree | FALSE |
| Prereg example "proposal cutoff 0.10" (3.0) vs harness 0.35 | inconsistent | FALSE |
| 3.1 "low-density stratum, never a silent drop" | never scored | FALSE |
| 3.1 S7b "refuses to run without the committed preregistration" | checks existence only | FALSE |
| 3.8 "injection-recovery through the whole inversion chain" | noise-insensitive | FALSE |
| 3.0 and 4.1 README "Plan only. Nothing here has been run" | runs and results exist | FALSE |
| 4.3 config "values look like reflectance already" | DN 0 to 6646 | FALSE |
| 4.5 "Recovery from S3 bounds what the chain can see" | different chain | FALSE |
| 4.8 "missing data (never a negative)" | counted as not usable | FALSE |
| 5.3 "top 50 all candidates is from the configured prior" | mainly NaN-skipping | FALSE |
| 5.4 D "block bootstrap 567 to 678" | exceeds the maximum of 647 | FALSE |
| 5.6 sheet "blind to score" | det_id encodes rank | FALSE |
| 5.6 "nothing missing" | pit/plugged primary is NaN | FALSE |
| 6.4 penetration flag "from records" | depth is 100% null | FALSE |
| 6.5 path-integrated "never mixed with ppm" | invalid visits stay valid | FALSE |
| 7.1 `--audit-once` "score the audit candidates" | re-scores out-of-fold | FALSE |
| 7.1/7.2 "G frozen before the arm was scored" | same call, floored to 0 | FALSE |
| 7.3 "never tune cutoffs" (0.35 / 0.525) | baseline and leaderboard at 0.10 | FALSE |
| 7.4 "refused tiles are not covered" | they enter the build via glob | FALSE |
| 7.5 "supports ±0.10 at n=182" | bound width 0.407 | FALSE |
| P1 "15 of 15 held-out lists equal the exporter" | output says 15/15 (not re-run) | UNVERIFIABLE here |
| 5.2 / 5.1 gate and VOID labels | accurate | TRUE |

## 4. Per-expansion verdict

| ID | Verdict | Biggest reason |
|---|---|---|
| _shared | RUNS BUT UNTRUSTED | the bootstrap drops NaN draws (SH-01) |
| P1 | RUNS BUT UNTRUSTED | buffer never applied; CSV and buffer-key handoffs broken |
| P2 | RUNS BUT UNTRUSTED | frozen file unreadable by all consumers; guard holes; CRLF hash break |
| 3.0 | RUNS BUT UNTRUSTED | reference footprint selected on truth; prereg not enforced |
| 3.1 | RUNS BUT UNTRUSTED | divergent scorer; dead low-density stratum |
| 3.2 | INCOMPLETE | no window lidar; confounded adaptation arm |
| 3.3 | RUNS BUT UNTRUSTED | donor leakage; truth-only reference |
| 3.4 | BROKEN | cutoff 0.10 vs 0.35; id-0 and straddle bugs |
| 3.5 | INCOMPLETE | inherits G-01 and G-04; silent partial init |
| 3.6 | BROKEN | pad cutoff 0.10 vs 0.525; union cannot lose |
| 3.7 | INCOMPLETE | null collapses |
| 3.8 | INCOMPLETE | injection gate cannot fail |
| 4.1 | RUNS BUT UNTRUSTED | magnetometry never confronted with identity |
| 4.2 | RUNS BUT UNTRUSTED | registration ignored; matched baseline; latest_run misorder |
| 4.3 | RUNS BUT UNTRUSTED | 5 m upsampled DN; undated labels |
| 4.4 | RUNS BUT UNTRUSTED | tail gate succeeds by extrapolation |
| 4.5 | RUNS BUT UNTRUSTED | recovery chain does not match analysis; seams |
| 4.6 | INCOMPLETE | no inputs; no date filter |
| 4.7 | INCOMPLETE | no data; ladder optimistic |
| 4.8 | RUNS BUT UNTRUSTED | undated means unusable |
| 4.9 | BROKEN | lidar_weak manufactures gain |
| 5.1 | INCOMPLETE | VOID pipeline only |
| 5.2 | INCOMPLETE | all labels E3; stops at gate |
| 5.3 | BROKEN | ranking driven by one road bit, then a constant, then row order |
| 5.4 | RUNS BUT UNTRUSTED | impossible D interval; truth-chosen footprint |
| 5.5 | RUNS BUT UNTRUSTED | IoU gate truncates error; zero road cost |
| 5.6 | RUNS BUT UNTRUSTED | unblinded sheet; null missing for plugged |
| 6.1 | INCOMPLETE | proposals have no producer; id collision |
| 6.2 | INCOMPLETE | no coal data |
| 6.3 | RUNS BUT UNTRUSTED | negatives on truth pits; role-name crash (P1-01) |
| 6.4 | BROKEN | depth column all null |
| 6.5 | RUNS BUT UNTRUSTED | unit errors do not invalidate |
| 6.6 | RUNS BUT UNTRUSTED | walk-time filter, void cumulative, one-sided tolerance |
| 7.1 | RUNS BUT UNTRUSTED | audit blocks scored; audit-once stub |
| 7.2 | RUNS BUT UNTRUSTED | G chosen after results; live retrain uses all truth |
| 7.3 | RUNS BUT UNTRUSTED | leaderboard and baseline cutoff mismatch; latent recall > 1 |
| 7.4 | RUNS BUT UNTRUSTED | refused tiles leak in; tautological CRS check |
| 7.5 | INCOMPLETE | width unreachable at configured n |
| _template | READY | README only |

No expansion is READY.

## 5. What could not be checked
- GPU training of any kind. That includes the isolated pit trainer with a non-zero buffer, and fine-tunes.
- Real-data stage runs: full rasters, PDAL thinning, S3 recovery, 6.1 S1/S2, network fetchers. Real-data numbers above come from committed outputs.
- The direction and size of the G-02 bias. Settling it means scoring the 29 zero-pit 9t blocks.
- Sensor product scaling against vendor docs (ECOSTRESS, Sentinel-2, Landsat), Kang 2014 numbers, Tanager limits.
- Notebook helpers outside `expansions/`: `_dl.predict_full_tile`, `CenteredPatchSampler`, `_build_derivatives.py` feet handling, and the `_operating_point_policy_sweep` internals.
- Whether pits 489 and 490 are one feature digitised twice (6.8 m apart, different folds).
- The scripts listed as skipped in section 1.
