# 6.6 Search and rescue viewshed tooling

**Problem.** The same terrain models support search planning, such as what an observer can see from a point. It is a separate tool, not a well result.

**Why it matters.** It is a low-cost use of existing data that other groups may want.

**Evidence level produced.** None for wells. It contributes no direct validation evidence.

**Inputs.** Terrain and surface models. Observer settings.

**Architecture.**
1. `docs/iterations/sar_viewshed_scope.md` defines inputs, assumptions and checks.
2. `_viewshed.py` computes line of sight over a bare-earth model and a surface model, with observer height and resolution as parameters.
3. Validation against known sight lines in the field.

**Method outline.** Check bare-earth against surface-model assumptions, observer height, resolution and line-of-sight behaviour.

**Acceptance test.** Results match the field sight lines within a stated tolerance.

**Risks and unknowns.** Scope creep.

**Depends on.** None.

**Executor notes.** Keep it out of well reports.
