# 4.3 Vegetation stress

**Problem.** Leaking wells can stress nearby vegetation. It is unknown whether vegetation indices around pads differ from disturbed non-well ground.

**Why it matters.** It could flag pads that need a field visit.

**Evidence level produced.** (a). Without independently documented leak labels, a difference is a vegetation difference, not leakage.

**Inputs.** Multi-date optical imagery (**unverified** for 9t). Pad polygons. Non-well disturbance polygons.

**Architecture.**
1. `docs/iterations/vegstress_protocol.md` defines indices, seasons and dates.
2. `_vegstress_extract.py` computes an index per pad and per control across seasons into `data/<area>/results/vegstress/vegstress_by_site.csv`.
3. Matched controls. Non-well disturbance with similar age and cover type.
4. Statistical comparison with repeated seasonal observations.

**Method outline.** Add non-well disturbance controls. Use more than one season. Report differences with intervals.

**Acceptance test.** A table of pad minus control index differences with intervals and the number of site-seasons.

**Risks and unknowns.** Fifteen hours is a pilot budget. Cloud cover and canopy shadow.

**Depends on.** None.

**Executor notes.** Do not label differences as leakage.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Choose the question first. Either morphology screening or independently labelled leakage. Without leak labels the result is a vegetation difference. Check whether DEP complaint records exist.

**Downloads and requests.** None.
