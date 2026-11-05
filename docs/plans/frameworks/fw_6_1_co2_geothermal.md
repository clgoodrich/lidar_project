# Framework 6.1. CO2 storage and geothermal screening (limits-first layer package)

**Tier A (rewritten 2026-11-05).** The user withdrew the deferral. This file assumes a partner and the data in section 4A exist, so it can be edited when real answers arrive.
**Status.** Plan only. Nothing here has been run, downloaded or measured.
**Evidence level.** A screening layer package. Surface-feature candidates are level (a). Records are (b). Field results are (c) and (d). The package never merges levels. It is not a wellbore-completeness estimate and not a wellbore-integrity estimate.
**Depends on.** 5.6 corrected (well-level units and record links), 3.0 (out-of-fold candidate scores), P1. 4.6 and 7.5 add layers if they exist.
**Blocks.** 6.4 (reuses this package). 7.4 agency tooling.

## 1. Problem and objective
Carbon storage and geothermal projects need to know about old wells that could leak. Under the Class VI rules for CO2 injection (40 CFR 146.84) an applicant defines an area of review and identifies penetrating wells in it, then plans corrective action. A surface inventory cannot establish whether a well penetrates the target zone, how it was cased and cemented, how deep it is or whether and how it was plugged. It can only point to surface features that might be wells and to records that list wells.

**Objective.** Build a layered screening package for a partner. It reports surface-feature candidates, records and coverage. It states first what is not known. It does not estimate how many wells are missing. The adversarial review found that the methods version promised a completeness estimate that 5.4 cannot give. This framework removes that promise.

**Partner decision (proposed, VERIFY with a real partner).** For a proposed storage or geothermal site, which locations inside the screening area does the partner add to its records search and field verification list before it commits to an area of review and a corrective action plan.
**What the partner already has (assumed).** Regulatory well records, a reservoir model, a target formation and a candidate area of review.
**What the inventory can add.** Surface-feature candidates with no record near them, record points with a feature nearby, and a map of where the inventory has no sensitivity.
**What the inventory cannot add.** Penetration, depth, construction, cement, plugging, current integrity, wells with no surface expression.

**Questions.**
- Q1. Can a partner reader state the limits correctly after reading the summary and layers.
- Q2. Does the package carry every layer and every limit it promises, and no claim it does not support.
- Q3 (descriptive). In the pilot area, what share of records have a candidate near them, and how many candidates have no record. Both are labelled as association and review burden. Neither is recall or precision.

**Hypotheses.** Q1. Every reader in the check answers the completeness question correctly. No hypothesis for Q3.

## 2. Scope
In. Pilot on 9t (Venango) and one assumed partner area with lidar. The package structure, the limits sheet, the coverage mask, a reader check, an automated claim audit.
Out. Any wellbore-integrity or leakage-risk estimate. Any statement of total wells. Any area-of-review delineation, which needs a reservoir pressure model. Any regulatory compliance claim. Any recommendation on a site permit.

## 3. Definitions
- **Area of review (AoR).** The region around a project where pressure or fluid effects could reach, as defined in the regulation. The partner defines it. We do not.
- **Screening area.** A polygon the partner gives. Candidates are listed inside it and in a buffer.
- **Candidate.** A detector blob at or above the frozen cutoff 0.50, resolved to a well-level site by 5.6. Level (a). It is a possible well, never a confirmed one.
- **Documented well.** A record in the DEP file or a partner file. Position error is unknown unless stated.
- **Record-candidate link.** A 5.6 proposal. Proposed association only, with the adjudicated link PPV if one exists, else "not measured".
- **Eligible area.** Ground where the inventory had a chance to see a feature. Defined from ground density, void fraction, canopy and block annotation status. Everywhere else is a **blind zone**.
- **Review burden.** Candidates per km² at policy K = 40 per km².
- **Limits sheet.** A one-page document placed first in the package.
- **Penetrating well.** A well whose borehole crosses the storage or heat zone. Known from records only.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Out-of-fold candidates, well-level | `data/9t/results/records/detector_output_pit_full_9t.gpkg`, `detector_output_pad_full_9t.gpkg` | to build in 5.6 |
| 5.6 association proposals | `data/9t/results/records/<run_id>/proposals.csv` | to build |
| DEP wells | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held |
| 2022 and 2026 orphan lists | `data/_source/reference/wells_us_orphan_2022/`, `wells_us_orphan_2026/US_orphaned_wells_2026.csv` | held |
| Other state well databases | `data/_source/reference/wells_ny_dec/`, `wells_ky_kgs/`, `wells_oh_odnr/`, `wells_wv_dep/`, `wells_ok_occ/`, `wells_il_isgs/`, `wells_ks_kgs/` | held |
| Block annotation and void fraction | `qgis/annotations/annotations_proj.gpkg`, void fraction per block from 3.0 (`transfer_blocks.csv`) | held and to build |
| Ground density per tile | from lidar inventory, `data/_source/reference/lidar_catalogue/` | held, measure per block |
| Partner screening polygon and records | `data/_source/partners/co2_partner/` (proposed) | see 4A |
| Package target | `data/<area>/results/screening/` | to build |

## 4A. Assumed data
Every row is an assumption. The executor verifies each row or removes the layer.
| Item | What is assumed | Proposed path | VERIFY how |
|---|---|---|---|
| Partner | A named project developer or consultant with a stated decision, willing to read the package | `docs/iterations/co2_screening_scope.md` | A written one-paragraph decision statement from the partner. If none exists, run the package on a hypothetical partner and label it so |
| Partner screening polygon | Shapefile or GeoPackage in a known CRS | `data/_source/partners/co2_partner/screening_area.gpkg` | Assert CRS. Compare extent with available lidar |
| Partner well records | Their own well list with fields for depth, status, completion, plugging, operator | `.../partner_wells.csv` | List columns. Report missingness. Compare overlap with DEP by permit key and position |
| State well records | DEP and neighbours hold depth, status, plugging fields | `venango_wells_all.gpkg` | List columns. Report share with depth. Report share with plugging data. Mark the 1800 sentinel |
| Target zone depths | Top and base of the storage or heat zone, in feet or metres, from the partner or the state geological survey | `.../target_zone_tops.csv` | Confirm datum and units. Check coverage over the screening area |
| Regulatory text | 40 CFR 146.84 (Class VI area of review and corrective action) | cited in `literature/CITATIONS.md` | Read the current text at the Code of Federal Regulations site and record the access date. Geothermal rules differ by state and project type. VERIFY the applicable regime |
| Lidar over the partner area | Open lidar with ground classification | `data/<area>/` | Measure ground density per block. Do not infer from file size |
| Historic evidence | Old maps or aerials with well symbols over the area | `data/_source/reference/historic_maps/` (proposed) | 4.6 readiness table. Skip if not ready |
| Field results | Magnetometry or visits at sampled candidates | 7.5 outputs | Only if 7.5 ran. Else the layer is absent and the sheet says so |

## 5. Prerequisites and decisions
- 5.6 corrected and run on the pilot. Without it the candidate layer is a blob list, not a site list.
- Partner decision paragraph on file, or a declared hypothetical partner.
- Policy K = 40 per km², the blind-zone rule, and the reader-check questions preregistered before any partner reads the package.
- User decisions. Which partner. Whether the package may leave the repo. Whether candidate points may be shared at full precision (location sensitivity, landowner issues).
- Compliance. Use only data the user holds or public data. Respect licences of partner files.

## 6. Procedure
**S0. Scope document.**
- Write `docs/iterations/co2_screening_scope.md`. Partner, decision, what the partner has, what the inventory adds and cannot add, the limits list, the layer list and the area. Verification result for each row of 4A.

**S1. Eligibility and blind-zone mask.**
- Script `notebooks/wellsight_v2/s7_analysis/_screen_eligibility_mask_9t.py` (new). Per block compute ground density, void fraction at 0.5 m (45.2% on 9t overall per `BACKLOG.md`), canopy class, annotation status. Eligible if ground density meets the chosen rule (a stated eligibility rule, not the QL2 definition) and void fraction is under the declared limit. Output `screen_eligible_mask_9t.gpkg` with an eligible layer and a blind-zone layer.
- The reason for each cut is written in the summary JSON.

**S2. Layer build.**
- Script `notebooks/wellsight_v2/s7_analysis/_screen_layers_9t.py` (new). Builds the package at `data/9t/results/screening/screening_package_9t.gpkg` with these layers.
  - `L0_limits`. A table of limits (below) and the policy used.
  - `L1_records`. Documented wells with status, depth where present, plugging field, coordinate source, evidence level (b). Missing fields stay missing.
  - `L2_candidates`. Candidate sites with score band, K rank, matched or not to a record, nearest documented well distance, method name and version, evidence level (a). Wording "candidate" only.
  - `L3_links`. 5.6 proposals with association strength and link PPV if adjudicated. If not, the field says "not measured".
  - `L4_eligible`. Eligible area and blind zones.
  - `L5_historic`. Level (b) historic symbols if 4.6 produced them. Absent otherwise.
  - `L6_field`. Level (c) and (d) results if 7.5 produced them. Absent otherwise.
  - `L7_screen_area`. The partner polygon and buffer.
- Every layer holds CRS EPSG:6346 and a `evidence_level` column. A test asserts no layer mixes levels in one row.

**S3. Limits sheet and summary.**
- Script `notebooks/wellsight_v2/s7_analysis/_screen_summary_9t.py` (new). Writes `screening_summary_9t.md` from saved numbers. Order is fixed. Limits first, then coverage, then candidates, then records. No results before limits.
- Fixed limits text (edited by the partner scope).
  1. Completeness is unknown. The inventory does not say how many wells exist.
  2. The detector sees surface features. Wells with no surface expression are not seen.
  3. Subsurface facts are unknown. Penetration, depth, casing, cement, plugging and integrity cannot be read from the surface.
  4. A candidate is a possible well. Its share that are wells is unmeasured unless 7.5 Arm B reports it.
  5. A record may be mislocated. Link proposals are not coordinate corrections.
  6. Blind zones are listed. Candidates absent there are not evidence of absence.
  7. Numbers on drawn features measure agreement with drawings (level a). They are not well-level recall.

**S4. Descriptive tables (Q3).**
- Script `notebooks/wellsight_v2/s7_analysis/_screen_descriptives_9t.py` (new). Output `screening_counts_9t.csv`. Counts of records, candidates, links, candidates with no record within 50 m, records with no candidate within 50 m, review burden per km², eligible share of area. Labels read "association" and "burden". None is called recall.
- Context stat from the repo for the limits text. On 9t, 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m (`docs/iterations/LEADERBOARD.md`, line 491). That shows most drawn pits have no record near them. It does not say they are wells.

**S5. Claim audit and reader check.**
- Script `notebooks/wellsight_v2/s7_analysis/_screen_claim_audit_9t.py` (new). Greps the summary, layer attributes and docs for banned phrases ("complete", "completeness estimate", "confirmed well" on a level (a) row, "leak", "integrity", "safe", "risk-free", "validated"). Writes `screen_claim_audit_9t.csv`. Zero hits required.
- Reader check. The partner (at least 5 readers, or 3 if fewer exist) reads the summary and layers, then answers six questions mapped to the limits. A form is written in `docs/iterations/co2_screening_reader_check.md`. Answers saved in `data/9t/results/screening/screen_reader_answers_9t.csv`. Readers are told this is a test of the document.

## 7. Statistical analysis plan
- No inferential claim about wells.
- **Q1 primary.** Share of readers who answer the completeness question correctly. Clopper-Pearson exact interval. A reader is the unit.
- **Secondary.** Share correct per limit. Time to find the limits sheet.
- **Q3.** Counts with block bootstrap intervals (blocks of 375 m, B = 2000) for the share of records with a candidate and for candidates per km². Labelled association and burden. Use level (a) and (b) labels.
- **No completeness estimate.** If a reader or partner asks for one, point to the 5.4 identifiability note. It states what must be known (well-level precision and recall from field arms) before any bound exists.
- **Evidence levels.** Separate tables per level.

## 8. Quality control and leakage checks
1. Row counts at joins. Records in equals records out. Candidates in equals candidates out.
2. CRS asserted on every layer. Distances in metres.
3. Candidates for 9t come from out-of-fold rasters only. Candidates in a partner area come from a model that did not train there. State which.
4. No audit block appears in any training, calibration or selection list used for the pilot.
5. Each layer has one evidence level. Test asserts it.
6. Blind-zone logic applied identically to every candidate query.
7. Claim audit passes with zero hits.
8. Partner data hashed. Licences stated in the package README.
9. Sanity render of ten records and ten candidates over hillshade.
10. Same configuration run twice gives identical outputs.
11. Every number in the summary comes from a saved file.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | Partner decision paragraph (or declared hypothetical), 5.6 pilot run, 4A rows verified | Build the package. Otherwise stop |
| Package success | Claim audit has zero hits, all layers present or explicitly absent with reason, evidence-level test passes | Offer to the partner |
| Package failure | Any banned claim, mixed level layer, or missing limits sheet | Fix and rerun. Do not send |
| Q1 success | Every reader answers the completeness question correctly and at least 80% of all limit answers correct, with at least 5 readers | The limits are readable |
| Q1 failure | Any reader states the inventory is complete or states a count of wells | Rewrite the sheet. Retest with new readers |
| Q1 inconclusive | Fewer than 5 readers | Report counts. Do not call it a pass |
**The margin comes from the decision.** One reader who believes the inventory is complete can cause the partner to skip a records search. That harm sets the zero tolerance on the completeness question. The 80% floor for other limits is the proposed tolerance and is the partner's to change before the check.

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\co2_screening_scope.md`, `co2_screening_reader_check.md`, `co2_screening_pilot_9t.md`
- Scripts in `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\` named `_screen_eligibility_mask_9t.py`, `_screen_layers_9t.py`, `_screen_summary_9t.py`, `_screen_descriptives_9t.py`, `_screen_claim_audit_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\screening\` holding `screening_package_9t.gpkg`, `screen_eligible_mask_9t.gpkg`, `screening_summary_9t.md`, `screening_counts_9t.csv`, `screen_claim_audit_9t.csv`, `screen_reader_answers_9t.csv`, `_PROVENANCE.json`, `_RUN.md`
- Figure `screening_map_9t.png` with candidates as orange triangles, records as blue circles, blind zones hatched grey. Shape carries meaning as well as colour.
- Update `literature/CITATIONS.md` (40 CFR 146.84 with access date), `docs/analysis_log.md`, `BACKLOG.md`, master plan.

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Overclaiming completeness | Limits first, banned-phrase audit, reader check |
| Partner reads candidates as wells | Word "candidate". Share of candidates that are wells shown as "unmeasured" |
| Blind zones missed | Eligibility mask, listed on the first page |
| Record positions wrong | Show coordinate source. Links are proposals |
| No real partner | Declared hypothetical, stated on every page |
| Partner area has different terrain and density | Measure ground density and void fraction. Run 3.1 style checks before claiming anything about candidate quality there |
| Location sensitivity | Decide sharing precision with the user. Keep a coarse version |
| Geothermal rules differ | Mark regime as VERIFY. Do not cite CO2 rules for geothermal |
| Wells with no surface expression | Stated in limit 2 |

## 12. Resources
S0 about 6 hours. S1 about 8 hours. S2 to S4 about 20 hours. S5 about 8 hours plus partner time. No GPU. Disk under 3 GB. About 42 hours plus partner calendar time. Measure one S2 run on a small block first.

## 13. Handoff and open questions
- Name the partner and the decision.
- Which regime applies (Class VI, state geothermal, other).
- Can partner records be shared.
- What the partner's reservoir and AoR model gives.
- Confirm 5.6 ran before building L2 and L3.
- Stop and report if any limits sheet sentence is contradicted by a result.

## 14. Documentation updates
`co2_screening_scope.md`, `co2_screening_pilot_9t.md`, `analysis_log.md`, `BACKLOG.md`, master plan, `literature/CITATIONS.md`.

## Review revision (2026-11-05)
Deferral withdrawn at the user's request. Partner and data are assumed, each tagged VERIFY. The completeness promise in the methods version is removed.
Source. `docs/plans/protocol_gates_and_metrics.md` sections 1, 5 and 12, and `docs/plans/adversarial_review_claude.md`.
