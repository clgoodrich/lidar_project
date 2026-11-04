# 4.8 Leaf-off optical imagery

**Problem.** Leaf-off aerial imagery can show bare ground, roads and pads under deciduous cover. How much of the study area has usable leaf-off imagery is unknown.

**Why it matters.** It is a cheap second modality and a way to confirm or reject lidar candidates by eye.

**Evidence level produced.** (a) and (b).

**Inputs.** State orthophoto programs and acquisition dates (**unverified**).

**Architecture.**
1. `docs/iterations/leafoff_coverage_probe.md` lists programs, dates, resolution and season for the study area.
2. `_leafoff_chip_check.py` pulls chips at annotated sites and records blank or unavailable chips separately from true non-detection into `data/9t/results/optical/leafoff_chip_status_9t.csv`.
3. Verify date, georegistration and visible-ground fraction before measuring usefulness.

**Method outline.** Coverage first, usefulness second. Separate missing chips from non-detections.

**Acceptance test.** A coverage table and a chip status table with the visible-ground fraction.

**Risks and unknowns.** Registration offsets. Evergreen cover.

**Depends on.** None.

**Executor notes.** Do not mix missing data with negatives.
