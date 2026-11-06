# Framework 6.4. Hydrogen storage screening (delta from 6.1)

**Tier A (rewritten 2026-11-05).** The user withdrew the deferral. This file is the delta from `fw_6_1_co2_geothermal.md`. It does not repeat the 6.1 pipeline. Read 6.1 first.
**Status.** Plan only. Nothing here has been run, downloaded or measured.
**Evidence level.** Same as 6.1. Surface-feature candidates are (a), records (b), field results (c) and (d). It cannot establish casing integrity, hydrogen compatibility of steel or cement, or subsurface suitability.
**Depends on.** 6.1 package built and its Q1 and package gates passed. 5.6 corrected.
**Blocks.** Nothing.

## 1. Problem and objective
Underground hydrogen storage in depleted gas fields, salt caverns or saline aquifers needs a list of old wells that could act as leak paths. Hydrogen differs from CO2 in ways that change what a partner asks of a well inventory. A small molecule leaks through smaller defects. It can embrittle steel casing. Storage cycles pressure up and down, often seasonally or daily, where CO2 injection mostly raises pressure once. A depleted field is full of wells by design, so the question moves from "which wells fall inside a pressure plume" to "which wells cross the reservoir or its seal inside the field".

**Objective.** Reuse the 6.1 package unchanged in structure. Change only the profile, the limits text, two layers, one filter and the reader check questions. State what the surface inventory still cannot say. Do not promise a completeness estimate. Do not build a second pipeline.

**Partner decision (proposed, VERIFY).** For a proposed hydrogen storage field, which surface candidates and records inside the field boundary does the operator add to its wellbore review before it chooses a storage zone and a monitoring plan.
**Missing subsurface information (all of it, none obtainable from lidar).** Which wells penetrate the reservoir and the seal. Casing and cement type and condition. Steel grade and hydrogen compatibility. Plugging depth and material. Current pressure integrity. Well deviation. Whether a record's depth is measured or reported. Gas composition history.

**Questions.**
- Q1. Can a partner reader state the hydrogen-specific limits correctly. Same form of test as 6.1.
- Q2. Does the delta package carry every layer and limit it promises, and no claim it does not support.
- Q3 (descriptive). Inside the pilot field boundary, what is the record count, the share with a depth and formation, and the candidate count with no record.

## 2. Scope
In. The delta list in section 3. A hydrogen profile of the 6.1 scripts. A pilot field boundary (a gas storage or depleted field in western Pennsylvania, assumed, VERIFY).
Out. Everything 6.1 excludes. Any hydrogen compatibility assessment of materials. Any leak rate or loss estimate. Any storage capacity estimate. Any regulatory claim. Any new detection method.

## 3. What differs from 6.1
| Item | 6.1 CO2 and geothermal | 6.4 hydrogen | Effect on the package |
|---|---|---|---|
| Question the partner asks | Which wells lie in the area of review of an injection plume | Which wells cross the reservoir or seal within the field | Screening polygon is a field or pool boundary, not an AoR |
| Screening area | Partner AoR or buffer | Field boundary plus a stated buffer | New layer `L7_field_boundary` replaces `L7_screen_area` |
| Regulatory text | 40 CFR 146.84 Class VI | No dedicated federal analogue assumed. VERIFY state storage rules and any applicable UIC class | Citation row changes. The limits sheet does not cite 146.84 for hydrogen |
| Well density | Sparse, many wells are outside the plume | Dense. The field holds many documented wells | Review burden per km² is expected to be higher. Report it and warn |
| Record fields that matter | Depth versus target zone | Depth versus reservoir top and seal top, completion type, casing grade, last workover | New record fields in `L1_records` (`reservoir_penetration_flag` from depth and tops, `completion_year`). Missing stays missing |
| Penetration flag | Optional | Core attribute from records | Derived from records only. Never from lidar. Labelled "from records" |
| Cyclic loading | Not central | Central. Cycling raises fatigue and leak sensitivity | Limits sheet adds a hydrogen limit. No layer. The inventory has nothing to say about it |
| Leak sensitivity | Normal | Higher for small defects | Limits text adds that surface candidates cannot give a leak pathway size |
| Material compatibility | Not asked | Asked. Steel embrittlement and cement permeability | Stated as unknown. No layer |
| Monitoring | Pressure front and plume monitoring | Gas surveys at wellheads and observation wells | Optional layer `L8_monitor_sites` only if the partner supplies sites. Else absent |
| Reader check | Completeness plus 5 other limits | Completeness plus 5 other limits, two replaced by hydrogen items | Section 6 S3 |
| Code | `_screen_*_9t.py` | Same scripts with `--profile hydrogen` | Config only. No new detection code |
| Evidence-level rules | (a) to (d) separate | Same | None |
| Completeness estimate | None | None | None |
| Success gates | Package and Q1 | Package and Q1, same margin logic | Same |

## 4. Inputs
| Input | Path | State |
|---|---|---|
| The 6.1 package, built | `data/9t/results/screening/screening_package_9t.gpkg` | to build in 6.1 |
| Hydrogen profile config | `data/9t/results/screening/screen_profile_hydrogen.json` | to write |
| Field boundary polygon | `data/_source/partners/h2_partner/field_boundary.gpkg` | see 4A |
| Reservoir and seal tops | `data/_source/partners/h2_partner/reservoir_seal_tops.csv` | see 4A |
| DEP wells | `data/_source/reference/dep_wells/venango_wells_all.gpkg` | held |
| 6.1 scripts | `notebooks/wellsight_v2/s7_analysis/_screen_*_9t.py` | to build in 6.1 |

## 4A. Assumed data
Only items that differ from or add to the 6.1 assumptions. Every row is an assumption.
| Item | What is assumed | Proposed path | VERIFY how |
|---|---|---|---|
| Partner | An operator or developer studying a hydrogen storage field, with a stated decision | `docs/iterations/hydrogen_scope.md` | A written paragraph from the partner. Else a declared hypothetical |
| Field boundary | A polygon of the pool or storage field, in a known CRS | `.../h2_partner/field_boundary.gpkg` | Assert CRS. Check that it covers known producing wells in DEP data. Source from the state survey if the partner has none |
| Reservoir and seal tops | Depth tops for reservoir and the seal across the field | `.../reservoir_seal_tops.csv` | Confirm datum and units. Check coverage. Report wells with no top assigned |
| Well depths in records | Total depth for a usable share of wells | in `venango_wells_all.gpkg` | Report share with depth. If under 50% the penetration flag is unusable and is dropped from the package |
| Completion and workover history | Year and type | `.../completion_history.csv` | Ask the partner or state. Mark absent if not supplied |
| Material data | Casing grade and cement type for some wells | `.../casing_material.csv` | Likely absent. If absent the sheet says so |
| Monitoring sites | Partner observation wells and gas survey points | `.../monitor_sites.gpkg` | Ask the partner. Else drop `L8` |
| Hydrogen regulatory regime | A rule that applies to the field's state | cited in `literature/CITATIONS.md` | Read the state's current storage and UIC rules. Record access date. Do not assume Class VI applies |

## 5. Prerequisites and decisions
- 6.1 package and gates passed on the pilot. If 6.1 fails its Q1 gate, stop here.
- A hydrogen partner paragraph, or a declared hypothetical.
- Preregister the two hydrogen reader questions and the profile config before any reader sees the package.
- User decisions. Pilot field. Sharing precision.

## 6. Procedure
**S0. Scope note.**
- Write `docs/iterations/hydrogen_scope.md`. It lists the table in section 3, the partner decision and the verification results for 4A. It is a delta note and points to the 6.1 scope document for everything else.

**S1. Hydrogen profile.**
- Write `data/9t/results/screening/screen_profile_hydrogen.json`. Fields. Screening polygon source, buffer metres, penetration-flag rule (record depth greater than reservoir top minus the depth uncertainty), limits text version, layer list with `L7_field_boundary` and optional `L8_monitor_sites`.
- Change the 6.1 scripts only to read this profile. No new script for detection or ranking. Script names stay `_screen_layers_9t.py` and `_screen_summary_9t.py`. Run with `--profile hydrogen` and a separate output folder.

**S2. Run the package under the profile.**
- Output `data/9t/results/screening/h2/screening_package_h2_9t.gpkg` and `screening_summary_h2_9t.md`. Layer rules from 6.1 hold. Penetration flag is a record-derived column with its source named. A candidate has no penetration flag. The sheet says so.
- Limits sheet. The seven 6.1 limits stay. Hydrogen adds these.
  8. Hydrogen is a small, fast-leaking molecule. A surface feature says nothing about defect size or leak pathways.
  9. Material compatibility and cycling effects are unknown from surface data.
  10. Penetration flags come from record depths. Records can be wrong or missing. A candidate has none.

**S3. Reader check and claim audit.**
- Same method as 6.1 S5. Two of the six questions are replaced by hydrogen items (items 8 and 9 above). Same banned-phrase list plus "hydrogen-ready", "compatible", "suitable".
- Output `data/9t/results/screening/h2/screen_reader_answers_h2_9t.csv` and `screen_claim_audit_h2_9t.csv`.

**S4. Descriptive counts.**
- Same table as 6.1 S4 inside the field boundary. Add the share of records with depth, share with a penetration flag, and review burden per km². Labelled association and burden.

## 7. Statistical analysis plan
Same as 6.1. Q1 primary is the share of readers correct on the completeness question, exact interval. Q3 descriptive with block bootstrap. No inference about wells. No completeness estimate. If asked, point to the 5.4 note.
The penetration flag is a record fact. It has no interval and is not tested.

## 8. Quality control and leakage checks
Every 6.1 check applies. Added checks.
1. Penetration flag derived only from record depth and tops. Test that no lidar-derived column feeds it.
2. Tops units and datum asserted equal to record depth units. A mismatch fails the run.
3. Wells with no depth stay in the package with the flag "unknown". Count reported.
4. Field boundary CRS asserted. Boundary and DEP wells compared. Wells just outside the polygon are listed.
5. Profile hash stored in `_PROVENANCE.json`. The 6.1 package and the hydrogen package are never overwritten by each other.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Readiness | 6.1 passed its package and Q1 gates, hydrogen partner paragraph or declared hypothetical, 4A rows verified | Build the delta. Otherwise stop |
| Package success | Claim audit zero hits, layers present or absent with reason, penetration flag test passes | Offer to the partner |
| Package failure | Banned phrase, lidar-derived penetration flag, or missing hydrogen limits | Fix and rerun |
| Q1 success | Every reader answers the completeness question correctly and at least 80% of other limit answers correct, at least 5 readers | The limits are readable |
| Q1 failure | Any reader claims completeness, hydrogen suitability or a leak rate | Rewrite the sheet and retest |
| Q1 inconclusive | Fewer than 5 readers | Report counts. Not a pass |
**Margin source.** Same as 6.1. A reader who believes the inventory is complete or that a candidate is hydrogen-compatible could skip a wellbore review. That harm sets zero tolerance on those questions. The 80% floor is the proposed tolerance and is the partner's to change before the check.

## 10. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\hydrogen_scope.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\screening\screen_profile_hydrogen.json`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\screening\h2\` holding `screening_package_h2_9t.gpkg`, `screening_summary_h2_9t.md`, `screening_counts_h2_9t.csv`, `screen_claim_audit_h2_9t.csv`, `screen_reader_answers_h2_9t.csv`, `_PROVENANCE.json`, `_RUN.md`
- Small edits to `notebooks/wellsight_v2/s7_analysis/_screen_layers_9t.py` and `_screen_summary_9t.py` so they accept `--profile`
- Update `literature/CITATIONS.md` (the state hydrogen storage rule with access date), `docs/analysis_log.md`, `BACKLOG.md`, master plan

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Scope creep into material or leak modelling | Out of scope. State it in the limits sheet |
| Treating 6.4 as a copy | The section 3 table is the contract. Anything not listed there is identical to 6.1 |
| Record depths missing | Drop the flag if under 50% coverage. Say so |
| Dense field overwhelms the reader | Report burden. Provide tiers by record status, not by risk |
| Regulatory regime assumed wrong | VERIFY step. Do not cite Class VI for hydrogen |
| Partner expects a completeness number | Point to 5.4. Offer field arms from 7.5 as the only route |
| 6.1 fails its own gate | Stop 6.4 |

## 12. Resources
S0 about 3 hours. S1 about 3 hours. S2 to S4 about 8 hours. S3 reader check needs partner time. About 14 hours. No GPU. Disk under 1 GB. The delta is small because the package is reused.

## 13. Handoff and open questions
- Name the hydrogen partner and the decision.
- Which pilot field. What rule governs it.
- Whether tops and completion history can be shared.
- Confirm 6.1 passed before starting.
- Stop and report if the penetration flag needs lidar data to fill.

## 14. Documentation updates
`hydrogen_scope.md`, `analysis_log.md`, `BACKLOG.md`, master plan, `literature/CITATIONS.md`.

## Review revision (2026-11-05)
Deferral withdrawn at the user's request. The earlier "no separate pipeline" rule is kept. The work is a profile and a delta, not a new pipeline.
Source. `docs/plans/protocol_gates_and_metrics.md` section 5 and `fw_6_1_co2_geothermal.md`.
