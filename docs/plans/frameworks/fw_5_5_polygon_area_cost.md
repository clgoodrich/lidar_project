# Framework 5.5. Polygon area and cost (scoped)

**Tier C.** Deferred. Low decision value now.
**Evidence level.** (a) with area as an attribute.

## 1. Problem and objective
Pad polygons give a disturbed area. Agencies may want area for restoration planning. How accurate the area is and how it relates to cost is unknown. A drawn footprint is not an excavation, contamination or restoration footprint. The pad model already over-claims area (reported about 2 times).

**Objective of the first step.** Measure the repeatability of drawn polygons.

## 2. Gate before any build
A protocol with explicit boundary definitions (disturbed surface, graded pad, including or excluding access road) and reviewers for independent redraws.

## 3. Minimum feasibility step
Pick 30 pads. Two reviewers independently redraw. Compute IoU and area ratio between reviewers and against the model polygons. Inter-annotator IoU is a reproducibility reference, not a ceiling. Do not use F1 alone for area.

## 4. What a full framework would add
Cost component only if an agency supplies plugging and restoration cost records. Surface footprint alone cannot estimate total cost.

## 5. Inputs, risks, resources
Inputs. Annotated pad polygons, model polygons, reviewers. Risks. Boundary ambiguity. Resources. 10 hours.

## 6. Documentation updates
Protocol doc, master plan.
