# 3.6 California

**Problem.** California has many idle and orphaned wells in oil fields with visible surface activity. Administrative status cannot be read from the surface alone.

**Why it matters.** It is a different setting with a strong state inventory and a large idle-well problem.

**Evidence level produced.** (a) and (b). Status is a record, not an observation.

**Inputs.** State well inventory and public lidar and imagery (**unverified**).

**Architecture.**
1. `docs/iterations/ca_target_definition.md` defines the observable target (for example, a pad with surface equipment visible), separate from administrative status.
2. Align label dates with imagery dates.
3. Many wells share a pad. Define the unit as the pad and count wells per pad.
4. Prototype scoring using plan 3.0.

**Method outline.** Define the target before collecting labels. Keep status as an attribute, not the label.

**Acceptance test.** The target definition is committed. A prototype on a small area reports detection by target class.

**Risks and unknowns.** This is a distinct research project. Forty hours is a prototype budget.

**Depends on.** 3.0.

**Executor notes.** Do not label wells as orphaned from imagery.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Write the observable-target definition and its decision use first. It is a different research question.

**Downloads and requests.** None.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

Only Los Angeles County met the threshold. Its density is diluted by urban area, and the window sits in the city. Kern and Ventura were not listed and need a separate look.

| State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB | Centre lon, lat |
|---|---|---|---|---|---|---|---|
| California | Los Angeles | 832 | CA_LosAngeles_B23 | 2025 | 35 | 2.9 | -118.2653, 34.0608 |
