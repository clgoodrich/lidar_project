# 6.2 Coal and mine features

**Problem.** Mine portals, subsidence and spoil heaps are legacy hazards. They also look like well features, which creates confusion.

**Why it matters.** It adds a second hazard inventory and reduces false positives.

**Evidence level produced.** (a) per feature type.

**Inputs.** State mine inventories (**unverified**, position error unknown). Lidar.

**Architecture.**
1. `docs/iterations/coal_feature_scope.md` defines feature classes and matching tolerances per class.
2. Assess inventory completeness and position error with a small check.
3. Train or apply a classifier with a mutual-confusion test against well pits. Allow an uncertain identity class.
4. Outputs at `data/<area>/results/coal/`.

**Method outline.** Feature-specific tolerances. Test mutual confusion with well pits.

**Acceptance test.** A confusion matrix between mine features and well pits with intervals.

**Risks and unknowns.** Inventory incompleteness.

**Depends on.** 6.3 for shared class design.

**Executor notes.** Keep this separate from the well work.
