# Framework 6.6. Search and rescue viewshed (scoped)

**Tier C.** Deferred. A separate project.
**Evidence level.** None for wells.

## 1. Problem and objective
The same terrain models support search planning, such as what an observer can see from a point. It adds no evidence about wells.

## 2. Gate before any build
A named user and a decision (for example search planning for volunteer teams) and agreed resources kept separate from the well work.

## 3. Minimum feasibility step
Define inputs (bare-earth versus surface models), observer height, resolution and line-of-sight algorithm. Write `docs/iterations/sar_viewshed_scope.md`.

## 4. What a full framework would add
`_viewshed.py` with parameters, validation against field sight lines within a stated tolerance, and a performance check at tile scale.

## 5. Inputs, risks, resources
Inputs. DEM and DSM. Risks. Scope creep. Resources. 12 hours when approved.

## 6. Documentation updates
Scope doc, master plan.
