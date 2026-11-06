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

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign, then pilot.

- Magnetics need intact steel casing. NETL says wooden or removed casing is invisible (confirmed at its page). A review cites Hammack et al. (2023) for missed 1860 to 1880 wells in forested Pennsylvania. That citation is reported, not read.
- Add era strata to the site list. Documented steel-era wells, early-era wells (independently dated, for example on a historic map), unknown-date wells (1800 sentinel, its own stratum), pits with no record, metal confusers, blanks. Report P(anomaly) by stratum, never pooled.
- Add non-magnetic evidence for the early stratum (cellar walls, wood casing remnants, cable-tool debris, historic map position).
- Record localisation error. An anomaly need not coincide with the borehole. Ground and UAV are separate sub-studies.
- Three to five sites test practicality, not sensitivity.

**Downloads and requests.** R3. Hammack and NETL page snapshot (D3).

## Review revision 2 (third review, 2026-11-04)
Unknown dates (1800 sentinel) are their own stratum, not early era. Magnetometry detects ferromagnetic material of any kind, so pilot with known targets, metal confusers and blanks. Record identity status apart from the outcome.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
