# 3.5 Oklahoma and Kansas

**Problem.** Large orphan inventories sit in open terrain with active infrastructure. Lidar, optical and fusion approaches have not been compared there.

**Why it matters.** It tests whether combining modalities helps where lidar alone is weak.

**Evidence level produced.** (a) per modality.

**Inputs.** State well records and public lidar and optical imagery (all **unverified**).

**Architecture.**
1. `docs/iterations/okks_data_inventory.md` lists records, lidar, optical, dates.
2. One shared site list and one spatial split used by all three arms (lidar, optical, fusion).
3. Matched label budgets and tuning effort across arms, recorded in the prereg.
4. `_modality_compare.py` scores the three arms on identical sites.
5. Missingness and active-infrastructure confounding tables.

**Method outline.** Identical sites, splits and effort. Report modality-specific missing data.

**Acceptance test.** Three arms scored on the same test blocks with paired differences and intervals.

**Risks and unknowns.** Substantial data engineering. Active infrastructure may look like abandoned sites.

**Depends on.** 3.0.

**Executor notes.** Do not tune one arm harder than the others.
