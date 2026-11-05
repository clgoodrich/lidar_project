# Framework 3.4. Gulf Coast and East Texas

**Tier B, rewritten to full depth 2026-11-05 at the user's request (no deferral). Plan only. Nothing here has been run, downloaded or scored.**
**Evidence level.** (a) drawn feature for every transfer result. Texas Railroad Commission (RRC) records are administrative evidence at level (b), used only through 5.6. Level (d) is never claimed from RRC records.
**Depends on.** 3.0 scorer, P1, P2, the density and void audit in S2. Adaptation (arm A1) needs a labelled adaptation window.
**Blocks.** Any statement about Gulf Coast programs. D13 download of RRC layer 2.

## 1. Problem and objective
The 9t model learned pits in steep, forested Appalachian terrain. In the Gulf Coastal Plain the ground is flat, wet and often flooded. Lidar may return few ground points under dense or flooded cover. Old well sites may look like earthen pits, borrow pits, canals or board roads. The first question is whether the target can be seen at all. The second is whether the frozen model ranks it.

**Q0 (observability, no model).** At the vertical noise and ground density of each Gulf window, what share of 9t-like pit depths is detectable?
**Q1 (primary).** Is recall at K = 40 per km² for the unchanged zero-shot model on Gulf blocks not worse than the 9t reference by more than Δ?
**Q2 (separate experiment).** Does an adapted model with relief-normalised channels beat the zero-shot model on the same test blocks by at least δ_gain?
**Q3 (contrast, labelled).** How does the same zero-shot model do in West Texas (Pecos), an arid shrubland setting that is not Gulf?

**Hypotheses.** Q1. H0 recall difference at or below minus Δ. H1 above it. Q2. H1 paired gain above δ_gain.

**What this study can show.** Whether the target is observable in these windows, and how the frozen and adapted models rank drawn features there, by wetland and void stratum.
**What it cannot show.**
- That any candidate is a well. All results are level (a).
- Anything about East Texas if the East Texas window is not scored. Louisiana Caddo and Arkansas Ouachita are neighbouring Gulf Coastal Plain settings. They are not East Texas.
- A reading of Pecos as Gulf. Vegetation, acquisition and industrial setting shift together there.
- RRC match rates. The earlier figure that about 35% of RRC orphans sat within 100 m of an optical pad detection came from the Permian. It is not used here as a prior or a benchmark.
- Performance on wells with no surface expression.

## 2. Scope
In. Observability audit, ground density and void audit, zero-shot baseline, wetland and void strata, a separate adaptation experiment, a Pecos contrast arm, hand-off of RRC records to 5.6.
Out. Level (d) claims. A single pooled Gulf statistic that mixes arms. Roads. Offshore and coastal marsh outside the windows.

## 3. Definitions
- **Window.** A 25 km² square (about 177 blocks of 375 m) from `lidar_win_windows_us.csv`, or a proposed East Texas window chosen by the rule in S1.
- **Void fraction.** Share of 0.5 m cells with no ground return, per block.
- **Wetland share.** Share of a block in NLCD 2021 classes 90 and 95, and in USFWS National Wetlands Inventory polygons. Strata dry, mixed, wet with cut points in the prereg.
- **Minimum detectable depth.** Three times the robust standard deviation of detrended 0.5 m ground DEM on stable ground in the window (pasture or cropland by NLCD), checked against the 3DEP QL2 vertical accuracy claim.
- **Hydro-flattened water.** 3DEP breaklines flatten water bodies, which erases depressions inside them. Water polygons are masked and listed, never scored.
- **Relief-normalised channels.** Per-block deterministic channels. The local plane is removed and elevation scaled by the block's own robust relief. No label use. Normalisation statistics for the adapted model are fitted on adaptation windows only.
- **Arms.** A0 zero-shot, unchanged pipeline. A1 adapted, own preregistration. A2 wetland exclusion, a different target population. C0 Pecos contrast.
- **Roles.** Test (scored once), adaptation (A1 only), audit (final claim, opened once). Test and adaptation are different windows. Roles inside one window are separated by the derived P1 buffer.
- Unit, K, scored footprint, matching and intervals follow `fw_00_common.md` section 4. K = 40 per km² of eligible area.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| USGS 2026 orphan file (TX, LA, AR) | `data/_source/reference/wells_us_orphan_2026/US_orphaned_wells_2026.csv`, `area_orphan_counts_by_county_us.csv` | held |
| Rebuilt windows and projects | `data/_source/reference/lidar_catalogue/lidar_win_windows_us.csv`, `lidar_win_projects_us.csv`, `lidar_win_download_summary_us.csv` | held (discovery only) |
| 9t annotated pits for depth distribution | `qgis/annotations/annotations_proj.gpkg` layers `pit_inside`, `pit_full` | held |
| 9t derivative builders, scorer, inference wrapper | `s1_build/_build_derivatives.py`, `_build_extra_channels.py`, `s5_eval/_transfer_score.py`, `s4_infer/_transfer_infer.py` | held / 3.0 |
| Isolated checkpoints, audit guard | P1, P2 outputs | future |
| NLCD fetch pattern | `notebooks/wellsight_v2/s1_build/_fetch_nlcd_9t.py` | held |

Listed windows. Louisiana Caddo (`LA_Sabine_River_Lidar_2018_D18`, 36 tiles, 9.72 GB, large tiles, 218 documented wells in window). Texas Pecos (`TX_WestTexas_2018_D19`, 18 tiles, 1.67 GB, 191). Arkansas Ouachita (`AR_Ouachita_FEMA_R6_Lidar_2016_D17`, 16 tiles, 1.18 GB, 82, cover 0.999).

### 4A. Assumed data
| Item | Assumed | Format, resolution, fields, CRS, licence | VERIFY |
|---|---|---|---|
| East Texas window (test T2) | A county in the East Texas oil region with QL2 or better lidar since 2015 and at least 15 eligible km². Candidates to evaluate are Gregg, Rusk, Smith and Upshur (proposed, none met the USGS listing threshold) | LAZ from USGS 3DEP or TNRIS StratMap, Texas State Plane South Central or UTM 15N (EPSG:6344), NAVD88. Public | Run the listing script with paging for each candidate. Record project, tiles, union cover and flight dates. Choose by the rule in S1 |
| Caddo window (T1) | Sabine River D18 covers the window | 36 tiles of about 270 MB. UTM 15N expected | `pdal info --summary` on one tile. Union cover from geometries |
| Adaptation windows | Arkansas Ouachita (listed) and Louisiana Ouachita or Morehouse (proposed, 330 and 454 county orphans, no window listed) | LAZ, QL2 | Same checks. Both must be at least the derived buffer from every test and audit block |
| Pecos contrast window (C0) | TX_WestTexas_2018_D19 covers the window | 18 tiles, UTM 13N (EPSG:6342) | Same checks. Label arid |
| RRC orphan layer 2 | Orphan Wells ArcGIS layer with a location reliability field and a coordinate source field | Point layer, geographic CRS, public | Page the layer, compare returned and retrieved counts. Read the real field names and value domains. Write the schema to `docs/iterations/rrc_orphan_schema.md` (proposed) |
| RRC coordinate reliability | Classes distinguish surveyed from digitised or approximate positions | Coded field | Tabulate classes. Treat unknown as its own class |
| Wetlands | NLCD 2021 (30 m, EPSG:5070) and NWI polygons | GeoTIFF and shapefile, public | Fetch with a resumable script. Hash. Compare to Q0 void maps for agreement |
| Ground classification and water class | ASPRS classes 2 and 9, breaklines | LAS 1.4 | Count classes per block. If class 2 is missing, reclassify through the PDAL CLI and call it a separate arm |
| Flight dates | Leaf-off or low-water season | Project metadata XML | Record in `docs/iterations/lidar_acquisition_dates.md`. Flood or high-water dates are listed per block |
| Annotators | Two reviewers per block and an adjudicator with no model exposure | People | Roster and exposure log |

## 5. Prerequisites and decisions
P1, P2 and the 3.0 scorer are done. The observability audit (S2 and S3) passes its readiness gate. The East Texas window rule is committed before any picture of candidate windows is viewed. Margin Δ in burden units (missed features per km² against review cost), δ_gain for A1 (extra recall that justifies maintaining a second model), minimum eligible blocks, void cap and wetland cut points are fixed in the prereg.

## 6. Procedure
**S0. Fetch and schema (gated).** Script `s1_build/_fetch_rrc_orphans_tx.py` (new, resumable, no credentials, hash). Page RRC layer 2. Reconcile returned versus retrieved counts and keep failed, empty and incomplete pages apart. Write `data/_source/reference/wells_rrc_orphans_tx/` (new folder, ignore if large) and the schema doc.

**S1. Window choice.** Rule fixed in the prereg. Pick the East Texas county with the highest documented-orphan density among counties with usable lidar and at least 15 eligible km². Ties go to the newer acquisition. Build windows for T1, T2, adaptation sites and C0.

**S2. Ground density, void and water audit.** Script `s1_build/_ground_density_by_block_us.py` (new, shared with 3.2 and 3.5). One tile per window first. Output `data/<area>/results/transfer/xfer_density_void_<tag>.csv` with ground density, void fraction, water-class share and wetland share per block. Compare against 9t (2.70 points per m², void 45.2% at 0.5 m). Never infer from file size.

**S3. Observability audit (Q0).** Script `s5_eval/_observable_depth_audit_gulf.py` (new). Compute the 9t pit depth distribution from the annotated floors. Compute minimum detectable depth in each window. Report the share of 9t pits that would pass, by wetland and void stratum, with the registration and support quantities of protocol section 9. Output `data/<area>/results/transfer/xfer_observable_depth_<tag>.csv`. Readiness rule. If the share is under the prereg floor the window is labelled "target not observable" and scoring is not run. That is a statement about the data, not a model failure.

**S4. Strata and blocks.** Script `s1_build/_wetland_strata_gulf.py` (new). Mask hydro-flattened water. Assign wetland and void strata. Lay 375 m blocks, mark edge blocks, assign roles by seeded draw, send audit blocks to P2.

**S5. Projected width and prereg.** Run the width tool with block counts per stratum, target density grid and clustering. If projected width exceeds 2Δ for the primary or 2δ_gain for A1, change the design before labelling. Fill and commit the prereg (K = 40, model policy, hashes, roles, buffer, strata, Δ, δ_gain, annotation protocol).

**S6. Derivatives and blind annotation.** Build 0.5 m derivatives with the 9t builders on native points. Time one block first. Two reviewers annotate complete blocks, including empty ones, with the 9t guide. Add a drawn class for confusers (borrow pit, farm pond, canal, board road, pipeline scar) that goes to the 6.3 codebook. No model output and no RRC points are shown. Re-annotate 20% independently. Output `data/<area>/results/transfer/xfer_truth_features_<tag>.gpkg`.

**S7. A0 zero-shot, once.** `_transfer_infer.py` and `_transfer_score.py` on T1 and T2 with the frozen policy. Tables for all blocks and by wetland and void stratum. Output `xfer_score_k40_<tag>.json`.

**S8. C0 contrast.** The same model on the Pecos window, labelled arid contrast. It is not part of the Gulf estimand and is never merged into A0 tables.

**S9. A1 adaptation (own prereg).** Script `s1_build/_build_relief_norm_gulf.py` (new) and `s3_train/_pit_unet_adapt_gulf.py` (new). Fine-tune from the isolated checkpoint on adaptation windows with whole-window exclusion of test and audit ground, normalisation fitted on adaptation windows, three seeds, one declared policy. Score on the same test blocks as A0. Paired.

**S10. A2 wetland exclusion.** Re-score A0 and A1 on dry and mixed blocks only. Report as a different target population beside, never instead of, the A0 table.

**S11. Error review and hand-off.** Characterise misses and unmatched candidates by stratum and class. Hand RRC records to 5.6 with reliability class as a stratum. Do not score them here.

## 7. Statistical analysis plan
- **Estimand.** For each test area, recall at K = 40 per km² of eligible area minus the 9t reference recall, pooled over complete eligible blocks. Strata are tables, not extra gates.
- **Unit.** The block. Features on one pad or lease are one cluster.
- **Interval.** Independent block bootstraps per area, B = 2000, percentile 95%. A stratum with fewer than 15 blocks gets a permutation interval and a warning.
- **Primary.** A0 on T1 and T2 separately. Non-inferiority against minus Δ.
- **A1.** Same resampled blocks for both arms, paired difference of recall at K = 40, superiority against δ_gain. Report drawn-feature recall loss in dry blocks as a guard.
- **Secondary.** Density-scaled K. K = 30. Calibration. Feature density per stratum. Void fraction and ground density as exploratory covariates.
- **Roles.** Adaptation fits A1. Test is scored once. Audit supports the final claim and is opened once. The stopping and tuning set for A1 is separate from the audit.
- **Buffers.** Derived from the P1 correlogram range, never fixed. Super-block bootstrap is a sensitivity.
- **Multiplicity.** One primary per area. Strata, Pecos and A2 are labelled exploratory or contrast.

## 8. Quality control and leakage
1. Row counts at every join. RRC returned counts equal retrieved counts.
2. CRS per window asserted (zone 15 or 13, not 17). Vertical datum recorded.
3. No training or adaptation window touches a test or audit block. Normalisation fitted on training or adaptation windows only.
4. Unchanged A0 appears in every table. Arms never mixed.
5. Water masks applied before candidate counting. Masked area removed from eligible area.
6. Annotators had no model output and no RRC points. Exposure logged.
7. Hashes for tiles, checkpoints, splits, prereg. Second run reproduces outputs.
8. Registration check of ten features per window against hillshade.
9. Every number in a doc comes from a saved file.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness (observability) | Share of 9t-like depths detectable at least the prereg floor, at least N_min eligible blocks, projected width within 2Δ | Annotate. Else report "not observable" |
| A0 success | Lower bound of difference above minus Δ | Zero-shot ranking holds in this window at level (a) |
| A0 failure | Upper bound below minus Δ | Error review by stratum. Plan A1. No transfer claim |
| A0 inconclusive | Interval spans minus Δ, or projected width above 2Δ | Report. Add blocks |
| A1 success | Paired gain lower bound above δ_gain | Adaptation justified for this setting |
| A1 failure | Gain upper bound below δ_gain | A positive gain below δ_gain is real but does not justify a second model |
Margin source. Δ comes from the missed-feature burden at K = 40 against review cost. δ_gain comes from the value of recall against the cost of maintaining and validating a second model. Both are fixed in the prereg before scoring. They never come from fold spread.

## 10. Deliverables
All paths are repo-relative.
- `notebooks/wellsight_v2/s1_build/_fetch_rrc_orphans_tx.py`, `_wetland_strata_gulf.py`, `_build_relief_norm_gulf.py`, `_ground_density_by_block_us.py`
- `notebooks/wellsight_v2/s3_train/_pit_unet_adapt_gulf.py`
- `notebooks/wellsight_v2/s5_eval/_observable_depth_audit_gulf.py`, `_gulf_transfer_tables.py`
- `data/_source/reference/wells_rrc_orphans_tx/`
- `data/la_caddo/results/transfer/`, `data/tx_east/results/transfer/`, `data/ar_ouachita/results/transfer/`, `data/tx_pecos/results/transfer/` (density, observability, blocks, truth, scores, figures)
- `docs/iterations/rrc_orphan_schema.md`, `transfer_prereg_gulf.md`, `transfer_gulf_9t_model.md`, `lidar_acquisition_dates.md`
- Figures use blue `#1F5FA8`, orange `#D97706`, grey `#8E959B` and a second encoding (marker shape or hatching) for strata. Validator worst-pair numbers go beside each palette.

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Few ground returns or flooded cover | Observability gate before scoring. Void and water strata |
| Hydro-flattening hides depressions | Mask and report water area |
| Pits shallower than vertical noise | Minimum detectable depth. State "not observable", not model failure |
| Confusers dominate (borrow pits, canals, ponds, board roads) | Confuser class at drawing. 6.3 codebook |
| Large tiles (Caddo about 270 MB each) | Window fetch on F:. Time one tile |
| RRC reliability or coordinate fields differ from assumed | Read the schema in S0. Stratify by class |
| Adaptation overfits a small adaptation window | Isolated trainer, three seeds, separate stopping set |
| East Texas county has too little lidar | Rule fallback. Report that East Texas is unscored |
| Pecos read as Gulf | Separate table, labelled contrast |

## 12. Resources
Estimates to be replaced by measurement.
- Desk, fetch scripts and schema. About 12 hours.
- Fetch. Caddo 9.7 GB compressed, expect 3 to 9 times that decompressed. Other windows 1.2 to 4 GB. About 25 to 60 GB across windows plus 0.4 GB per derivative channel per 25 km². F: only. Run the large-file audit after each step.
- Annotation. Placeholder 60 blocks at 15 minutes per block with two reviewers is about 30 hours per window. Replace with S6 timing.
- Inference. Minutes to an hour per window. A1 needs measured epoch time first (the backlog notes it was under-reported by 1.8 times).

## 13. Handoff and open questions
- East Texas county rule and the Louisiana Ouachita or Morehouse window.
- Δ, δ_gain, void cap, wetland cut points, observability floor.
- The actual RRC field names and reliability classes.
- Annotators and the confuser class list.
- Whether Pecos stays in this framework or moves to the arid backlog.

## 14. Documentation updates
`rrc_orphan_schema.md`, `transfer_prereg_gulf.md`, `transfer_gulf_9t_model.md`, `analysis_log.md`, `LEADERBOARD.md`, `BACKLOG.md`, `literature/CITATIONS.md` (NWI, NLCD, 3DEP specifications), master plan status.

## Review revision 2 (third review, 2026-11-04)
Pecos is not East Texas. Vegetation, acquisition and industrial setting shift together. Define observable targets first.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

## Review revision 3 (full rewrite, 2026-11-05)
Built in from `adversarial_review_claude.md` and `review_response_20261104.md`. Level (d) removed. The Permian 35% figure removed. Observability comes before scoring. The unchanged baseline is in every table. Adaptation is a paired, separately gated experiment with its own windows. Pecos is a labelled contrast.
