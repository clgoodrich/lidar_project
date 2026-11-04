# Framework 5.3. Risk ranking (scoped)

**Tier C.** Deferred.
**Evidence level.** A ranking, not evidence about wells.

## 1. Problem and objective
Agencies decide which wells to plug first. A ranking should combine the chance a well exists, the hazard it poses and who or what is exposed. No P(well) exists, only P(feature).

**Objective of the first step.** Define a decision, an independently measurable hazard endpoint, and the three quantities kept separate.

## 2. Gate before any build
`docs/iterations/risk_ranking_design.md` naming the decision (for example the plugging order for a year), the user, the endpoint (for example methane flux, water-well proximity incidents) and the data source for it. Without an outcome-based comparison, a ranking is an engineering product, not a scientific result.

## 3. Minimum feasibility step
Assemble exposure layers (water wells, streams, buildings, roads, land cover) into `data/9t/results/risk/exposure_layers_9t.gpkg`. This can proceed now and needs no model. Compute transparent scenario rankings and rank stability under different weights.

## 4. What a full framework would add
A hazard model with real endpoints, existence probability from 7.5, validation against agency priority lists (agreement is not validation of harm).

## 5. Inputs, risks, resources
Inputs. Exposure layers, detections, records. Risks. No ground truth for harm. Resources. 15 hours for layers and scenarios.

## 6. Documentation updates
Design doc, master plan.
