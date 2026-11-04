# 4.9 More radar

**Problem.** The tested NISAR radar features did not add to detection. The question is whether any other radar signal or application would.

**Why it matters.** It prevents over-reading a negative result and avoids repeating the same test.

**Evidence level produced.** (a) or (c), depending on the signal.

**Inputs.** Existing NISAR write-up and results. Other SAR sources (**unverified**).

**Architecture.**
1. `docs/iterations/radar_scope_note.md` restates the conclusion with its scope. Tested products, features, areas and targets only. Pits gain was -0.004 and pads -0.008 after de-duplicating decoys.
2. For any new radar work, a new rationale and a new prereg are required. The note lists what would count as a genuinely different signal, such as a different wavelength, polarimetry or time-series displacement.

**Method outline.** No new experiment until a new rationale exists.

**Acceptance test.** The scope note is committed and cited from the NISAR write-up.

**Risks and unknowns.** None beyond scope creep.

**Depends on.** None. Deprioritised.

**Executor notes.** Do not claim that every coarse sensor fails.
