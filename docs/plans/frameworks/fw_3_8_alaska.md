# Framework 3.8. Alaska (scoped)

**Tier C.** Deferred. A different question from detection.
**Evidence level.** Not well detection. A displacement time series at known wells.

## 1. Problem and objective
Wells in permafrost may show surface displacement as ground thaws. That monitoring question does not test whether a model can find wells. Only 12 Alaska wells are in the USGS 2022 orphan dataset.

**Objective of the first step.** A metadata-only feasibility note.

## 2. Gate before any build
`docs/iterations/alaska_feasibility.md` that states the observable (line-of-sight displacement), available SAR stacks and revisit, coherence expectations on tundra and wetland, stable reference points, controls for seasonal thaw and hydrology, and the elevation data type (IfSAR or lidar). Go, no-go or defer with reasons.

## 3. Minimum feasibility step
Search catalogues for SAR coverage over the legacy wells, record dates and polarisations. No downloads. Eighty hours buys reconnaissance, not a validated study.

## 4. What a full framework would add
A time-series pipeline, control sites without wells, a thaw and hydrology model, and an acceptance test on known displacement.

## 5. Inputs, risks, resources
Inputs. SAR archive listings, a list of legacy wells. Risks. Decorrelation, seasonal confounding. Resources. 10 hours for the note.

## 6. Documentation updates
Note, master plan.

## Review revision 2 (third review, 2026-11-04)
Motion is not well integrity. Write the observability and stable-reference note first.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
