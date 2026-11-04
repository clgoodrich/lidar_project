# Framework 4.2. Thermal (scoped)

**Tier C.** Deferred behind an observability gate.
**Evidence level.** (a) at best. Thermal differences do not identify a well.

## 1. Problem and objective
Disturbed ground or leaking wells may have a different surface temperature. No earlier thermal work exists in the repo and the user does not recall where it lives (2026-11-04). Treat as new.

**Objective of the first step.** Decide whether any thermal sensor could resolve a pad-sized target under canopy.

## 2. Gate before any build (observability)
Quantify
- target fraction of a pixel (a 30 to 100 m pad is under one pixel for Landsat TIRS, which is 100 m native and resampled to 30 m, or ECOSTRESS at about 70 m, per specifications cited by a review and not yet read)
- usable acquisitions (cloud free, leaf-off, similar time of day)
- registration uncertainty
- plausible contrast against natural variability (canopy, emissivity, soil moisture, clearing history)

A smaller delivered pixel is not more target information.

## 3. Minimum feasibility step
Write `docs/iterations/thermal_observability.md` with numbers. If contrast is below variability, stop. A satellite null excludes only a specified contrast and does not exclude a drone signal.

## 4. What a full framework would add
Sample sets (pads, non-well clearings, forest), land-surface temperature extraction, a covariate-adjusted comparison (vegetation, moisture, weather, time of day), and a drone design if the satellite gate fails but a drone could resolve the target.

## 5. Inputs, risks, resources
Inputs. Landsat or ECOSTRESS products, pad polygons. Risks. Target dilution, canopy, emissivity. Resources. 8 hours for the note.

## 6. Documentation updates
Note, `literature/CITATIONS.md` (NASA and LP DAAC specs once read), master plan.
