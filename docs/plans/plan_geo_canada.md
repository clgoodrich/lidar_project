# 3.7 Canada

**Problem.** Alberta, British Columbia and Ontario hold large orphan and legacy well inventories. Coverage, access and record completeness are not established.

**Why it matters.** The inventories are large. Ontario has old shallow wells in settings close to Pennsylvania. The reason to try Ontario first is **unverified**.

**Evidence level produced.** (a) and (b).

**Inputs.** Provincial well databases and lidar programs (**unverified**). Reviewers who know local well types.

**Architecture.**
1. `docs/iterations/canada_data_inventory.md` records, per province, lidar coverage, point density, access terms, record fields, documented well types and licence.
2. Choose the first province from the inventory, not from assumption.
3. One county or region per province, with a prereg.
4. Reuse plan 3.0.

**Method outline.** Verify actual coverage before ranking provinces. Include reviewer requirements in the plan.

**Acceptance test.** The inventory table is complete for the three provinces. A ranked recommendation cites the table.

**Risks and unknowns.** Licensing and access may block use. Record completeness varies.

**Depends on.** 3.0.

**Executor notes.** This is not only a download task. It needs people with local knowledge.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Province comparison from actual metadata only. Licence, access and local reviewers are unverified. The Ontario-first rationale is unverified.

**Downloads and requests.** None.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

Not listed. The USGS 3DEP catalogue covers the United States only. Provincial and Alaska lidar would need their own inventory.
