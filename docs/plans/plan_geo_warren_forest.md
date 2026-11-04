# 3.1 Warren and Forest counties

**Problem.** The 9t model was trained on one tile in Venango County. It is unknown whether it ranks well in neighbouring Warren and Forest counties. The seven Warren tiles on disk are the same USGS D20 program as 9t, so this is a within-survey test. Forest lidar is unverified.

**Why it matters.** It is the nearest and cheapest test of whether the model generalises. A pass justifies Phase B. A fail shows what to fix.

**Evidence level produced.** (a) feature detection. A separate analysis covers record association (b to d).

**Inputs.** Seven Warren LAZ files are on disk (paths and dates to be listed). Forest lidar readiness is **unverified**. DEP export for wells. Frozen checkpoints.

**Architecture.**
1. Preregistration at `docs/iterations/transfer_warren_prereg.md` (draft exists). Fill the brackets and commit before scoring.
2. `_warren_inventory.py` lists tiles, CRS, point counts, and measured ground density per tile into `data/warren/results/transfer/warren_tile_inventory.csv`.
3. Choose adaptation, test and audit blocks. Write them to `data/warren/results/transfer/warren_blocks.gpkg` with a role column.
4. Run `_transfer_infer.py` and `_transfer_score.py` from plan 3.0.
5. Annotation package for the test blocks. Follow `docs/iterations/confuser_codebook.md` classes. Two reviewers, blinded to score.
6. Separate association report using plan 5.6.

**Method outline.** Complete blocks chosen before scores. Recall at fixed K with block bootstrap. Margin against 9t recall set in the preregistration.

**Acceptance test.** Preregistration committed before any scoring. Output includes the interval for the difference against 9t and a pass, fail or inconclusive label.

**Risks and unknowns.** Ground density may be lower than 9t. Forest County may lack suitable lidar. Annotation needs reviewers. Labelling time is not in the earlier 25-hour estimate.

**Depends on.** 3.0, P1, P2.

**Executor notes.** Do not look at probability maps before the preregistration is committed.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign as a within-survey case study.

- The seven Warren tiles are the same USGS D20 program as 9t. This tests spatial transfer inside one survey, not a new sensor.
- The area is about 7 km² (reviewer figure, not measured) against 20 km² for 9t. Before annotating, project the interval width by resampling as many 9t blocks as Warren can supply. Drop the adaptation role if the area cannot hold it. If the projected width exceeds twice the margin, change the design.
- The Warren preregistration draft is invalid as written. K is the count of annotated features and the reference 0.928 is cutoff-based. Rewrite it from protocol section 2 before use.
- Rebuild Warren derivatives at 0.5 m with the 9t code. The 1 m derivatives on disk break the preprocessing freeze. Report void fraction per block and thin to 9t ground density.
- Derive the buffer. Score complete blind blocks including empty ones. Time one block of annotation first.
- Eastern Warren and Forest QL1 (B19, about 9 points per m²) is a separate sensor-shift arm, gated on the within-survey result. Forest readiness is unverified.

**Downloads and requests.** D1 now. D11 gated. R4 and R6 needed.

**Scope update 2026-11-04.** McKean is in scope for the expansion (user). Use its B19 data (about 9 points per m², same program as the Forest B19 piece) as the sensor-shift arm. A 36-tile, 2.1 GB window is listed below. K is 40 per km². The recall-loss margin is set in the preregistration before scoring.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

Warren (7 D20 tiles) is already on disk. The Warren window below is a larger and denser block of the same D20 program. Forest has D20 and a small B19 piece. McKean is B19. Venango is the 9t reference county.

| State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB | Centre lon, lat |
|---|---|---|---|---|---|---|---|
| Pennsylvania | Venango | 782 | PA_WesternPA_2019_D20 | 2019 | 20 | 0.81 | -79.538, 41.5056 |
| Pennsylvania | McKean | 597 | PA_Northcentral_2019_B19 | 2019 | 36 | 2.11 | -78.5524, 41.9725 |
| Pennsylvania | Forest | 548 | PA_WesternPA_2019_D20 | 2019 | 20 | 0.91 | -79.4834, 41.5605 |
| Pennsylvania | Warren | 500 | PA_WesternPA_2019_D20 | 2019 | 15 | 0.79 | -79.0553, 41.7768 |
| Pennsylvania | Butler | 104 | PA_WesternPA_2019_D20 | 2019 | 20 | 1.31 | -79.8062, 40.998 |

## Review revision 2 (third review, 2026-11-04)
Set the margin from missed-feature burden at K=40, not fold spread. Forecast interval width over plausible target density and clustering, not by resampling 9t only. Native target data is primary and thinning is a separate arm. McKean is a joint geography and acquisition contrast. Verify footprint coverage from tile geometries first.
Source. `docs/plans/protocol_gates_and_metrics.md` section 16.
