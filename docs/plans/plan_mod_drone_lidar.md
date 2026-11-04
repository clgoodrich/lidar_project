# 4.7 Drone lidar

**Problem.** Drone lidar at Oil Creek covers 63 wells. It is denser than the state airborne survey. How much detection depends on point density is unknown.

**Why it matters.** It separates the effect of density from the effect of sensor and season.

**Evidence level produced.** (a), and (d) if the 63 wells are confirmed.

**Inputs.** NETL point clouds and metadata, by data request (not yet made). The reason the 63 sites were chosen. If chosen for lidar visibility, they are a biased sensitivity sample.

**Architecture.**
1. Data request (see `outreach_requests_drafts.md`) asking for metadata, site selection, coordinates and validation notes.
2. `docs/iterations/drone_lidar_provenance.md` records acquisition details.
3. `_thin_drone_lidar.py` thins the native cloud repeatedly to a ladder of densities. Writes thinned clouds to `data/oil_creek/derived/drone_thinned/` (add a `.gitignore` rule).
4. Run the frozen model on native and thinned data. Compare detection by density.
5. Airborne against drone comparison reported separately because sensor, season and processing also differ.

**Method outline.** Native against thinned drone data isolates density. Cross-platform comparison alone confounds density with other factors.

**Acceptance test.** A table of recall against density for the same sites.

**Risks and unknowns.** Data may not be released. Site selection bias.

**Depends on.** Outreach.

**Executor notes.** Do not call the sample representative.
