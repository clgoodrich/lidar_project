# 4.1 Magnetometry

**Problem.** Lidar sees the surface. Steel casing is below it. A magnetometer can detect buried steel, which gives independent evidence about whether a feature hides a well.

**Why it matters.** It is the main way to turn a candidate feature into evidence about a well, and it gives independent coordinates for testing record association.

**Evidence level produced.** (c) steel anomaly. Not a well identification.

**Inputs.** A ground magnetometer and base station (to be borrowed, see `outreach_requests_drafts.md`). Three to five field sites. Site access permission.

**Architecture.**
1. `docs/iterations/magnetometry_pilot_protocol.md` states instrument, sensor height, line spacing, base-station use, GNSS method and datum.
2. Site list `data/<area>/results/magnetometry/pilot_sites.csv` with category per site (documented well, candidate pit with no record, metal confuser, blank control).
3. Field data sheet template `docs/iterations/magnetometry_field_sheet.md`.
4. `notebooks/wellsight_v2/s5_eval/_mag_process.py` reads raw files, removes diurnal drift with the base station, grids to a residual field, and writes `mag_residual_<site>.tif` and an anomaly table.
5. Reporting table. Anomaly present or absent, amplitude, offset from the candidate centroid.

**Method outline.** Include confusers such as culverts, fences and buried pipe so anomalies are not only tested on easy wells. Ground and UAV are separate sub-studies.

**Acceptance test.** Each site has a processed grid, a position accuracy statement and a labelled outcome. The pilot reports practicality, not population sensitivity.

**Risks and unknowns.** Instrument access. Interference from nearby metal. Three to five sites cannot estimate sensitivity.

**Depends on.** Outreach (A0). No code dependency.

**Executor notes.** Keep steel evidence separate from well identity in every table.
