# 6.1 CO2 storage and geothermal screening

**Problem.** Carbon storage and geothermal projects must know about old wells that could be leakage paths. A surface-feature inventory could help screen a site.

**Why it matters.** It gives the detector a second use and a possible funding route.

**Evidence level produced.** Evidence layers for screening. Not a wellbore-completeness estimate.

**Inputs.** A scoped demonstration area. Documented wells and detections. Subsurface information and partner needs (**unverified**).

**Architecture.**
1. `docs/iterations/co2_screening_scope.md` states the demonstration area, the layers delivered and the limits.
2. `_screening_layers.py` outputs documented wells, candidate features, confidence and the inventory limits as a layered package at `data/<area>/results/screening/`.
3. A one-page summary for a partner with limits stated first.

**Method outline.** Report evidence layers, not completeness. State what a feature inventory cannot say about casing or cement.

**Acceptance test.** A partner can read the summary and the layers and see the limits.

**Risks and unknowns.** Actual use depends on subsurface data and partner requirements.

**Depends on.** 5.6.

**Executor notes.** Do not claim a wellbore integrity estimate.
