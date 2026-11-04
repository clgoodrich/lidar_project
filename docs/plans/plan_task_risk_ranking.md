# 5.3 Risk ranking

**Problem.** Agencies need to decide which wells to plug first. A ranking should combine the chance a well exists, the hazard it poses, and who or what is exposed.

**Why it matters.** It turns detections into a work list.

**Evidence level produced.** A ranking, not evidence about wells.

**Inputs.** Detections and records. Exposure layers (water wells, streams, buildings, roads, land cover). A hazard proxy (**to be defined**).

**Architecture.**
1. `docs/iterations/risk_ranking_design.md` defines three separate quantities. Probability a well exists. Hazard if it does. Exposure of receptors.
2. `_exposure_layers.py` assembles exposure layers into `data/9t/results/risk/exposure_layers_9t.gpkg`. This step can proceed now.
3. `_risk_scenarios.py` computes transparent scenario rankings under different weights and reports rank stability.
4. Comparison with any agency ranking is described as agreement, not validation of harm.

**Method outline.** Keep the three quantities separate in every table. Use scenarios, not one score.

**Acceptance test.** Rank-stability table across scenarios.

**Risks and unknowns.** No ground truth for harm.

**Depends on.** 5.6 for record linkage.

**Executor notes.** Do not call a ranking validated.
