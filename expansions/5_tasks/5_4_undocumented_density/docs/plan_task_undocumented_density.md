# 5.4 Undocumented well density

**Problem.** How many wells are not in any record is unknown. Detector output alone cannot answer that.

**Why it matters.** It sizes the problem for agencies and funders.

**Evidence level produced.** An estimate under stated assumptions. Not a count.

**Inputs.** Detections, records, and the recall-gap results. With D candidates, well precision p and recall r, the estimated total is D times p over r. Missed wells are D p (1 minus r) over r. Undocumented wells are the total minus the complete documented population in the same unit.

**Architecture.**
1. `docs/iterations/density_identifiability.md` writes the equation, what must be known for each term, and which terms are currently unidentified.
2. `_density_sensitivity.py` sweeps p and r over plausible ranges and writes `data/9t/results/density/density_sensitivity_9t.csv`.
3. Cohort association comparison (formerly the recall-gap study, with no recall-equivalence gate) as in `recall_gap_newly_documented_9t.md`, once more data is available. Match groups on location, status and acquisition eligibility. Separate new discoveries from reclassifications.
4. Define the counting unit as a well, not a blob.

**Method outline.** Sensitivity and identifiability first. A density surface comes only after well-level precision and detection probability are supported by field data.

**Acceptance test.** A sensitivity table and a stated list of unidentified quantities.

**Risks and unknowns.** Smoothing cannot identify an unidentified detection rate. Capture-recapture is not automatically a lower bound.

**Depends on.** 7.5 for field data.

**Executor notes.** Do not publish a density map.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Identifiability note only.

- Withdraw reliance on the A6 recall-gap result. Its input was wrong.
- D times p over r is valid only for distinct true wells in the same eligible population. If recall can approach zero a finite upper bound may not exist.
- Get DEP coordinate provenance before any record-based recall.

**Downloads and requests.** R1.

## Review revision 2 (third review, 2026-11-04)
Write distinct-well accounting and show bounds as recall varies. No density gate from spatial excess alone.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
