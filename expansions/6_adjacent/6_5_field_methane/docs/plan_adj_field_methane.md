# 6.5 Field methane screening

**Problem.** Remote data cannot tell whether a candidate well is leaking. A handheld or vehicle methane check at a site could.

**Why it matters.** It adds a direct measurement to the field campaign and gives priority information.

**Evidence level produced.** A concentration reading. It is not an emission rate. A non-detection is not proof of no leak.

**Inputs.** An instrument, a protocol, and field sites (see 7.5).

**Architecture.**
1. `docs/iterations/field_methane_protocol.md` defines instrument output, background measurements, calibration, wind recording, repeat visits and detection limits. It separates screening readings from quantitative emission measurement.
2. Data sheet `docs/iterations/field_methane_sheet.md`.
3. `_field_methane_table.py` assembles readings per site into `data/<area>/results/field/field_methane_by_site.csv`.

**Method outline.** Repeat visits. Record weather. Report ranges, not single readings.

**Acceptance test.** Protocol committed with a worked example sheet.

**Risks and unknowns.** Instrument access and safety training.

**Depends on.** 7.5.

**Executor notes.** Do not write "no leak" for a non-detection.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Protocol only, with 7.5.

- Instrument-specific background and repeat protocol. A reading is not an emission rate. A non-detection is not proof of no leak.

**Downloads and requests.** None.

## Review revision 2 (third review, 2026-11-04)
Concentration is not flux. Non-detection is conditional on the instrument, visit and weather.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
