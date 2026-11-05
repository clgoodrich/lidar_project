# 5.6 Record association

**Problem.** Agency well records have coordinates of uncertain accuracy. A detected feature near a record might be that well. Linking them could improve positions.

**Why it matters.** Wrong coordinates waste field time.

**Evidence level produced.** A proposed association. Not a corrected coordinate.

**Inputs.** DEP export, held-out detections, annotated features, saved splits. Independent coordinates (GNSS points, NETL sites) are needed to test any improvement.

**Status.** A first test on 9t is already written up in `docs/iterations/record_assoc_pits_9t.md`. Orphan and abandoned records were not above chance at the primary radii. Active records were above chance at small radii. Treat that as a reason to stop automatic snapping, not all association work.

**Architecture.**
1. Association against the full annotated features with a footprint-based null, as a separate script from the detector version.
2. Pit level uses one-to-one Hungarian assignment. Pad level allows many records per pad.
3. Primary radius fixed in the prereg. Other radii are sensitivity.
4. Independent coordinate test when GNSS or NETL positions exist. Report position error before and after.
5. Keep ambiguous and unmatched outcomes.

**Method outline.** The null estimates chance matching, not the error of accepted matches. Within-block shifting must be defined precisely, and independent moves break clustering.

**Acceptance test.** Position error with intervals against independent points.

**Risks and unknowns.** Without independent coordinates nothing is validated.

**Depends on.** Outreach for GNSS data.

**Executor notes.** A pad centroid is not a borehole.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign. First repair the input.

- The first run is withdrawn. All matched detections were dropped and the pad file held only unmatched leftovers. The proposals were not globally one-to-one.
- Input contract, footprints, assignment, null and statistics are in protocol section 4. Mark the rerun exploratory.
- Run a full-output analysis and a novel-candidates-only analysis separately.
- Report normalised excess association with an interval, and a positive control (active wells at pad level). It is not link precision. Link PPV needs adjudicated sampling (protocol section 4 rule 5).
- Annotators did not see DEP points (answered 2026-11-04). Other annotation context is unrecorded. Stratify by coordinate source once DEP answers (R1).
- Validation needs independent coordinates.

**Downloads and requests.** R1. R4 is answered.

## Record sources now on disk (added 2026-11-04)
Public well databases with coordinates are downloaded for New York, Kentucky, Oklahoma, Illinois, West Virginia, Ohio and Kansas, plus the USGS national orphan dataset (2022). They carry different status definitions and coordinate methods, so harmonise before pooling. Paths and hashes are in `data/_source/_download_ledger.csv`. None of them gives independent GNSS positions, so none of them validates a coordinate correction.

## Review revision 2 (third review, 2026-11-04)
Rename the statistic normalised excess association. Link PPV comes from adjudicated sampling with ambiguous outcomes kept. Coordinate correction needs paired error on independently surveyed identities. A pad-level positive control does not validate a different cohort.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
