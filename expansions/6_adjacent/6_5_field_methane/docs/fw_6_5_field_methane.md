# Framework 6.5. Field methane screening

**Tier B (rewritten to full depth 2026-11-05 by the build agent).** A protocol that rides with 7.5. The user asked that frameworks assume the data exist. Every assumption sits in section 4A and carries VERIFY.
**Status.** Plan and code. The protocol has not been used in the field. No reading exists.
**Evidence level.** A concentration reading. It is not an emission rate. A non-detection is not proof of no leak. A methane reading is not evidence that a candidate is a well. It sits beside levels (c) and (d) from 7.5 and never replaces them.
**Depends on.** 7.5 field campaign (sites, access, partner). An instrument and calibration gas. Safety training.
**Blocks.** Nothing. It informs 7.5 site reports and 4.4 (methane plumes) as a ground reference only.

## 1. Problem and objective
Remote data cannot tell whether a candidate well is leaking. A handheld methane check at a site can screen. It also acts as a safety check before anyone approaches an open well.

**Objective.** A repeatable protocol, a data sheet and an assembly script. The output separates screening readings from quantitative emission measurement. It records background, weather, calibration and repeat visits. It states the limits on every page.

**Questions.**
- Q1. Does each visit meet the protocol (calibration, background, wind, transect) so its reading can be used.
- Q2 (descriptive). At sites visited at least twice, how often do repeat visits agree on the screening category.
- Q3 (descriptive). What share of visited sites show an enhancement above the instrument limit on at least one visit.

**Hypotheses.** None. This is a measurement protocol. Q2 and Q3 are descriptive. They carry intervals and no gate on wells.

## 2. Scope
In. Protocol, data sheet, sheet checks, assembly into a per-site table, reporting rules, a claim audit, a worked example.
Out. Quantitative emission rates. Those need enclosure chambers, tracer release or another flux method. Any claim that a site does not leak. Any ranking of sites by leak risk. Any use of methane to decide whether a candidate is a well.

## 3. Definitions
- **Instrument.** A named model with its measurement type. A point sampler reads concentration in ppm at the inlet. An open-path laser reads a path-integrated value in ppm·m. The two are never mixed in one table.
- **Detection limit (DL).** The instrument's stated lower limit in its own units. It is taken from the manufacturer sheet and checked against the zero readings.
- **Background.** Upwind readings over at least 5 minutes, 20 to 50 m upwind, in the same visit. The median is the background level. The spread is the 95th percentile minus the median.
- **Screening reading.** A peak reading at a fixed position (wellhead, casing, 1, 5 or 10 m downwind).
- **Enhancement.** Screening reading minus the background median from the same visit.
- **Detected.** Enhancement above the larger of the DL and the background spread. Else the reading is **below the limit at that time and place**.
- **Visit.** One site on one date by one crew. A **valid visit** passed calibration, has a background record and has wind inside the stated range.
- **Repeat agreement.** Two valid visits at one site on different days give the same category (detected or below the limit).
- **Quantitative measurement.** Flux by chamber, tracer or another method. Out of scope.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| 7.5 site list | `data/<area>/results/field/field_sites_<area>.csv` | to build in 7.5 |
| Field sheet (one row per reading) | `data/<area>/source/field_methane/field_methane_sheet_<area>.csv` | assumed, see 4A |
| Instrument registry | `expansions/6_adjacent/6_5_field_methane/src/config_6_5.json` | written, values VERIFY |
| Kang et al. (2014) context numbers | `docs/papers/kang_2014_methane_abandoned_wells_PA.pdf` | held |
| DOI orphaned well measurement guidance | not held | to read, cite when used |
| Safety plan | partner or 7.5 | assumed |

## 4A. Assumed data
Every row is an assumption. The executor verifies each row before the first field day.
| Item | What is assumed | VERIFY how |
|---|---|---|
| Instrument | A point methane sampler with a stated DL of about 1 ppm, or an open-path laser in ppm·m | Read the manufacturer sheet. Record model, serial, units and DL in the config |
| Calibration gas | A certified span gas near 100 ppm and zero air | Check the certificate and expiry date. Record the span value |
| Calibration tolerance | Zero within 1 ppm and span within 10% at the start of each day | Confirm against the instrument manual. Change the config if it differs |
| Safety stop threshold | 10% of the lower explosive limit, about 5,000 ppm for a point sampler | Confirm with the safety reviewer. Methane LEL is about 5% by volume. Record the reviewer's value |
| Wind range | Readings are usable between 0.5 and 8 m/s | Confirm with the instrument guidance. Calm air pools gas. Strong wind dilutes it |
| Field sheet | Crews fill a CSV with the schema in the config | Pilot one visit. Run the sheet check |
| Site access | 7.5 provides sites with permission | 7.5 access log |
| Repeat visits | At least one repeat visit per site on a different day | 7.5 schedule |
| DOI guidance | The DOI orphaned well program distinguishes screening from quantitative measurement | Read the current guidance and record the access date in `literature/CITATIONS.md` |

## 5. Prerequisites and decisions
- 7.5 site list and access.
- Instrument choice and its DL on file. User decision.
- Safety plan approved. The stop threshold is the safety reviewer's.
- Positions measured. Default wellhead if safe, casing if safe, 1, 5 and 10 m downwind. User decision.
- Repeat schedule. At least one repeat per site on a different day.

## 6. Procedure
**S0. Protocol and sheet.**
- Protocol `expansions/6_adjacent/6_5_field_methane/docs/methane_field_protocol.md`. Zero and span check at the start of each day. Upwind background for at least 5 minutes, 20 to 50 m upwind. Downwind transect at 1, 5 and 10 m. Wellhead and casing readings only if safe. Record wind speed and direction, temperature, pressure and time on every reading. Stop rules are a reading above the safety threshold, odour, or hissing. A stop ends the visit and is logged.
- Sheet schema in `src/config_6_5.json`. A worked example is written by `_methane_field_table.py --example`.

**S1. Sheet check.**
- Script `src/_methane_sheet_check.py`. Checks columns, units per instrument, one calibration pair per crew-day, background duration and distance, transect positions, wind range, stop rows and duplicate readings. Output `methane_sheet_check_<area>.csv` (one row per problem) and a pass or fail line per visit.

**S2. Assembly.**
- Script `src/_methane_field_table.py`. Per visit it computes background median and spread, enhancement per position, and the detected flag. Per site it reports ranges over valid visits and repeat agreement. Outputs `data/<area>/results/field/field_methane_by_visit.csv`, `field_methane_by_site.csv` and `field_methane_summary.json`.

**S3. Reporting rules and claim audit.**
- Script `src/_methane_claim_audit.py`. Searches outputs and listed docs for banned phrases such as "no leak", "leak-free", "emission rate", "flux", "kg/h". Requires the word "screening" in every summary. Zero hits required.
- Rules. Report ranges and background, never a single reading. Say screening. A non-detection means below the instrument limit at that time and place.

## 7. Statistical analysis plan
- Descriptive only. No emission rates. No inference about wells.
- Unit is the site. Visits at one site are not independent.
- Q2. Share of repeat-visited sites whose valid visits all agree, with a Clopper-Pearson interval.
- Q3. Share of sites with a detected enhancement on any valid visit, with a Clopper-Pearson interval. Report it separately for each 7.5 identity status and era stratum. Never pool strata.
- Context. Kang et al. (2014) measured 19 abandoned Pennsylvania wells with a mean near 0.27 kg per day per well and 3 high emitters. Readings here cannot be compared with those flux numbers.

## 8. Quality control
1. Calibration log per crew-day. A visit after a failed check is invalid.
2. Background present for every visit. A visit without one is invalid.
3. Wind recorded on every reading. Readings outside the wind range are flagged and excluded.
4. Units consistent per instrument. Point and path-integrated readings never share a column.
5. Repeat-visit differences reported, never averaged away.
6. Row counts asserted at every join. Readings in equals readings out.
7. Same sheet run twice gives identical tables.
8. Every number in a report comes from a saved file.

## 9. Gates
| Outcome | Rule | Action |
|---|---|---|
| Protocol ready | Protocol and worked example committed, approved by the partner and the safety reviewer | Use in 7.5 |
| Visit valid | Sheet check passes for the visit | Include in the table |
| Visit invalid | Any failed calibration, missing background or wind outside range | Keep the row, mark invalid, exclude from shares |
| Report pass | Claim audit has zero hits and "screening" appears | Release with 7.5 |
| Report fail | Any banned phrase | Rewrite and rerun |
No scientific gate exists here. The margins belong to 7.5.

## 10. Deliverables
- `expansions/6_adjacent/6_5_field_methane/docs/methane_field_protocol.md`
- `expansions/6_adjacent/6_5_field_methane/src/config_6_5.json`, `_methane_sheet_check.py`, `_methane_field_table.py`, `_methane_claim_audit.py`, `test_6_5.py`
- `expansions/6_adjacent/6_5_field_methane/results/tables/methane_example_sheet.csv` (synthetic worked example, labelled so)
- `data/<area>/results/field/` holding `field_methane_by_visit.csv`, `field_methane_by_site.csv`, `field_methane_summary.json`, `methane_sheet_check_<area>.csv`, `_PROVENANCE.json`

## 11. Failure modes
| Risk | Mitigation |
|---|---|
| Gas hazard | Stop threshold, odour and hissing stop rules. Readings at the wellhead only if safe |
| Wind variability | Wind on every reading. Range check. Repeat visits |
| Instrument drift | Daily zero and span. Invalid visit after a failed check |
| Mixed units | One instrument type per column. Sheet check fails on a mix |
| Reading read as a rate | Banned phrases. "Concentration, not flux" on every summary |
| Non-detection read as no leak | Fixed wording. Claim audit |
| Selection toward known emitters | Sites come from the 7.5 probability sample, not from smell or reports |

## 12. Resources
Protocol 6 hours. Code built 2026-11-05. Field time inside 7.5. About 20 minutes per visit for background and transect (estimate, measure on the pilot). No GPU. Disk under 100 MB.

## 13. Handoff and open questions
- Instrument model, DL and units.
- Safety reviewer and stop threshold.
- Which positions are measured.
- Whether the DOI guidance sets a background method that differs from this one.
- Stop and report if a reading crosses the stop threshold, if calibration fails twice in one day, or if the sheet check fails on a whole crew-day.

## 14. Documentation updates
Protocol, `docs/analysis_log.md`, master plan, `literature/CITATIONS.md` (DOI guidance, Kang et al. 2014), the 7.5 site report template.

## Review revision 2 (third review, 2026-11-04)
Concentration is not flux. Non-detection is conditional on the instrument, visit and weather.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.

## Review revision 3 (build agent, 2026-11-05)
Brought to full depth with every assumption in section 4A. The script names moved into the expansion `src/` folder.
