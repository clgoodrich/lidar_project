# 4.5 Multitemporal lidar

**Problem.** Two lidar surveys exist for parts of the area (2006 to 2008 and 2019). Plugging or site restoration may leave a change in terrain. Whether that is detectable is unknown.

**Why it matters.** It could show restoration without a field visit and give a before and after test.

**Evidence level produced.** (a) terrain change. Plugging does not necessarily imply surface earthwork.

**Inputs.** Both lidar sets. Plug dates from the DEP export. **Actual flight dates are not yet established.**

**Architecture.**
1. `docs/iterations/lidar_acquisition_dates.md` establishes flight date bounds per tile from metadata. Do this before any test.
2. `_plug_eligibility.py` keeps wells whose plug date falls clearly between the bounded flights. Others are dropped or run only as a labelled exploratory set. Writes `data/9t/results/dod/plug_eligible_wells_9t.csv`.
3. Analyse at pad or complex level. Match controls on baseline terrain and disturbance opportunity.
4. Change statistic from the existing change-detection work. Seams and registration error are reported.

**Method outline.** Plugging between 2006 and 2019 does not put plugging between the flights. Ambiguous dates are excluded. The confirmatory test is blocked until dates are known.

**Acceptance test.** A dated eligibility table and a matched-control comparison with intervals. Everything else is labelled exploratory.

**Risks and unknowns.** The eligible subset may be tiny.

**Depends on.** Acquisition dates.

**Executor notes.** Establish dates first. Do not run the test on undated wells.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Blocked.

- Establish flight-date bounds first. File creation dates are not flight dates.
- Controls are eligible pads without the intervention. The existing controls exclude mapped pads, pits and roads and match slope. They are ordinary terrain.
- Plugging is not surface restoration. Seek independently dated earthwork.
- The 3,368 m² threshold belongs to one spatial-null procedure. Test signal recovery through the whole processing chain.
- The saved result is 19 of 404 flagged pads against about 15.3 expected. That is not evidence of absence.

**Downloads and requests.** D1. R7.

## Review revision 2 (third review, 2026-11-04)
Success and failure use one threshold δ_rate in rate units. The 0.16 to 0.22 m height floor is a separate measurement spec. Show recovery of a specified physical change through the full chain first.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
