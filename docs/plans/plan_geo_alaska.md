# 3.8 Alaska

**Problem.** Wells in permafrost may show surface displacement as ground thaws. This is a different question from detecting a well.

**Why it matters.** Legacy Arctic wells are a known problem. Displacement would be a monitoring signal.

**Evidence level produced.** Not well detection. It produces a displacement time series at known wells.

**Inputs.** A suitable SAR time series and elevation data (**unverified**). A list of legacy wells.

**Architecture.**
1. Reconnaissance note `docs/iterations/alaska_feasibility.md` listing available SAR stacks, elevation data type, coherence expectations and reference-point stability.
2. If feasible, a time-series pipeline with controls for seasonal thaw and hydrology.
3. Control sites without wells.

**Method outline.** Assess coherence first. Use stable references. Compare with matched controls.

**Acceptance test.** The note recommends go, no-go or defer, with reasons.

**Risks and unknowns.** Eighty hours buys reconnaissance, not a validated study.

**Depends on.** Nothing. Deferred.

**Executor notes.** Do not start processing until the feasibility note is approved.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Metadata-only feasibility note. Specify line-of-sight displacement, reference stability and seasonal and hydrology confounding before any well-related claim.

**Downloads and requests.** None.
