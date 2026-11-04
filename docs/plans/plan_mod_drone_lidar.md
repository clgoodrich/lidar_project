# 4.7 Drone lidar

**Problem.** NETL reports that 63 potential well sites were located on two hillsides at Oil Creek using lidar. They are potential sites, not confirmed wells. It is denser than the state airborne survey. How much detection depends on point density is unknown.

**Why it matters.** It separates the effect of density from the effect of sensor and season.

**Evidence level produced.** (a). Level (d) only for sites with independent confirmation.

**Inputs.** NETL point clouds and metadata, by data request (not yet made). How the 63 potential sites were chosen and whether any were confirmed. They were found with lidar, so they are a biased sensitivity sample.

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

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Proceed as a request.

- NETL's wording is potential well sites located with lidar. Do not call them wells. Ask for selection history, coordinates, confirmation status and release terms. The page does not say the data are released.
- Thinning measures sensitivity to retained points within that acquisition. It does not reproduce another platform's footprint, scan geometry, occlusion or ground classification.
- Label every curve as conditional on selection by lidar visibility.

**Downloads and requests.** R2. D12 gated, size unknown, goes to F:.
