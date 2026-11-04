# Framework 6.5. Field methane screening

**Tier B.** A protocol that rides with 7.5.
**Evidence level.** A concentration reading. It is not an emission rate. A non-detection is not proof of no leak.
**Depends on.** 7.5, an instrument, safety training.

## 1. Problem and objective
Remote data cannot tell whether a candidate well is leaking. A handheld methane check at a site can screen. It also acts as a safety check before approaching an open well.

**Objective.** A repeatable protocol and data sheet that separates screening readings from quantitative emission measurement, with background, weather, repeat visits and limits.

## 2. Scope
In. Protocol, sheet, analysis rules.
Out. Quantitative emission rates (needs enclosure or tracer methods).

## 3. Definitions
- **Screening reading.** Peak and local concentration above background in ppm, with the instrument model and detection limit.
- **Enhancement.** Reading minus upwind background, same time window.
- **Quantitative measurement.** Flux by chamber or other method. Out of scope.

## 4. Inputs
Instrument and calibration gas (user or partner). DOI measurement guidance (screening against quantitative) to be read (cite when used). Safety plan.

## 5. Prerequisites and decisions
Instrument choice. Training. Whether to measure at wellhead, at 1 m, at 5 m downwind.

## 6. Procedure
1. **Protocol** `docs/iterations/field_methane_protocol.md`. Instrument zero and span check at the start of each day. Upwind background reading (at least 5 minutes, 20 to 50 m upwind). Downwind transect at 1, 5, 10 m. Wellhead and casing readings if safe. Repeat visit on a different day at least once per site. Record wind speed and direction, temperature, pressure, time. Stop rules (reading above a safety threshold, odour, hissing).
2. **Sheet** `docs/iterations/field_methane_sheet.md`.
3. **Assembly script** `s5_eval/_field_methane_table.py` (new). Output `data/<area>/results/field/field_methane_by_site.csv`.
4. **Reporting rules.** Report ranges and background, never a single reading. Say screening. Non-detection means below the instrument's limit at that time and place.

## 7. Statistical analysis plan
Descriptive. Enhancement with repeat-visit agreement. No emission rates.

## 8. Quality control
Calibration logs. Background comparison. Repeat-visit differences.

## 9. Gates
Protocol approved by the partner and safety reviewer.

## 10. Deliverables
Protocol, sheet, table script, `C:\Users\colto\Documents\GitHub\lidar_project\data\<area>\results\field\`.

## 11. Failure modes
Gas hazard. Wind variability. Instrument drift.

## 12. Resources
Protocol 6 hours. Field time inside 7.5.

## 13. Handoff
Instrument and training.

## 14. Documentation updates
Protocol, `analysis_log.md`, master plan.

## Review revision 2 (third review, 2026-11-04)
Concentration is not flux. Non-detection is conditional on the instrument, visit and weather.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
