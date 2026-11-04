# 4.2 Thermal

**Problem.** Disturbed ground or leaking wells may have a different surface temperature. It is not known whether thermal data separates well pads from other clearings.

**Why it matters.** Thermal data is cheap from satellites and drones. A signal would add a modality.

**Evidence level produced.** (a) at best. Thermal differences do not identify a well.

**Inputs.** Satellite thermal products and optionally a drone thermal camera (**unverified**). Known pads and non-well clearings. Where earlier thermal work lives is an open question. None was found in `docs/`.

**Architecture.**
1. `docs/iterations/thermal_feasibility.md` lists sensors, pixel size, revisit rate and acquisition times.
2. Sample sets. Pads, non-well clearings and forest controls, in `data/<area>/results/thermal/thermal_samples.gpkg`.
3. `_thermal_extract.py` pulls land-surface temperature per sample and per date.
4. Covariate table for vegetation, moisture, weather and time of day.
5. Comparison script with controls, written as a regression with those covariates.

**Method outline.** Compare pads with non-well clearings, not only forest. Satellite pixels are large. A satellite null result does not stop a drone study.

**Acceptance test.** A feasibility note and a comparison table with covariate-adjusted differences and intervals.

**Risks and unknowns.** Resolution mismatch. Weather control.

**Depends on.** None. Low priority.

**Executor notes.** Do not claim leak detection.
