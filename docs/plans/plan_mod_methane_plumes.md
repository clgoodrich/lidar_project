# 4.4 Methane plumes from satellites

**Problem.** Satellites report methane plumes. It is unknown whether any plume can be tied to a candidate or documented orphan well.

**Why it matters.** Emission is the main harm from open wells. A link would help prioritise.

**Evidence level produced.** Regional association. It cannot attribute emissions to a single candidate well.

**Inputs.** Public plume catalogues and their detection limits (**unverified**). Well and facility locations.

**Architecture.**
1. `docs/iterations/methane_catalogue_review.md` lists products, resolution, detection limit, revisit and retrieval quality flags.
2. `_plume_well_overlay.py` intersects plume footprints with well points and active facility layers into `data/<area>/results/methane/plume_well_overlay.csv`.
3. Observation opportunity table. How often each area was observed under usable conditions.
4. Repeat-observation handling for the same source.

**Method outline.** Account for observation opportunity, retrieval quality, detection limits and active facilities. Report association, not attribution.

**Acceptance test.** Overlay with counts of plumes per well category and the number of observations behind each.

**Risks and unknowns.** Small leaks fall below detection limits. Active facilities dominate emissions.

**Depends on.** None. Later.

**Executor notes.** Do not claim a plume belongs to a candidate well.
