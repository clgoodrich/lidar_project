# 5.5 Polygon area and cost

**Problem.** Pad polygons give a disturbed area. Agencies may want area for restoration planning and cost. How accurate the polygon area is, and how area relates to cost, is unknown.

**Why it matters.** It makes the output usable for budgeting.

**Evidence level produced.** (a) with area as an attribute.

**Inputs.** Annotated pad polygons. Independent redraws by other reviewers (to be arranged). Cost data from agencies (**unverified**).

**Architecture.**
1. `docs/iterations/polygon_area_protocol.md` defines the redraw task and the area metric.
2. `_area_agreement.py` compares model polygons, annotator polygons and redraws. Writes `data/9t/results/pad/pad_area_agreement_9t.csv`.
3. Cost component only if an agency supplies plugging and restoration cost records.

**Method outline.** Inter-annotator IoU is a reproducibility reference, not a ceiling. Do not use F1 alone for area.

**Acceptance test.** Area error with intervals against annotator redraws.

**Risks and unknowns.** Surface footprint alone cannot estimate total cost.

**Depends on.** Reviewers.

**Executor notes.** Keep cost out of scope unless data arrives.
