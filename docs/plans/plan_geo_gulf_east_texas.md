# 3.4 Gulf Coast and East Texas

**Problem.** Wetland, vegetation and ground-return conditions differ. Lidar may have poor ground coverage under dense or flooded cover.

**Why it matters.** Texas has a documented orphan well layer, the Railroad Commission layer 2. Its locations carry a reliability field and are not automatically accurate coordinates.

**Evidence level produced.** (a) and (b). RRC records are administrative evidence, not level (d). Association is separate.

**Inputs.** RRC orphan layer (documented). Public lidar for chosen counties (**unverified**). Frozen checkpoints.

**Architecture.**
1. Measure ground-return density and void fraction per block into `data/<area>/results/transfer/ground_density_by_block.csv` before any scoring.
2. Zero-shot baseline with unchanged preprocessing, using plan 3.0.
3. Separate adaptation arm with relief-normalised channels, written as its own experiment.
4. Stratify results by wetland and by void fraction.
5. An exclusion arm for wetland blocks is reported as a different target population.

**Method outline.** Keep the unchanged baseline in every table. Do not mix arms.

**Acceptance test.** Baseline and adaptation arm both reported with block-bootstrap intervals and stratum tables.

**Risks and unknowns.** Earlier work found only about 35% of RRC orphans within 100 m of an optical pad detection, but that was in the Permian. It does not apply to East Texas.

**Depends on.** 3.0.

**Executor notes.** Measure density first. Do not infer from file size.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Level (d) removed. RRC records carry location reliability and coordinate source fields.
- Measure ground density and void fraction per block before anything else. Keep the unchanged zero-shot baseline.

**Downloads and requests.** D13 gated.

## Areas and lidar list (added 2026-11-04)
Listed only. Nothing is downloaded. Windows are the densest 25 km² cluster of documented orphan wells in each county, chosen by well count alone. Tile URLs are in `data/_source/reference/lidar_catalogue/lidar_download_list_pilot_5km_us.csv`. Method and cautions are in `docs/plans/download_list_areas_and_lidar.md`. Measure ground density on one tile before fetching a window.

Texas Pecos is West Texas, not East Texas. No East Texas county met the listing threshold in this database. Measure ground return density before anything else.

| State | County | Orphans in 25 km² window | Newest project | Year (guess) | Tiles | GB | Centre lon, lat |
|---|---|---|---|---|---|---|---|
| Louisiana | Caddo | 142 | LA_Sabine_River_Lidar_2018_D18 | 2018 | 36 | 7.69 | -93.9433, 32.7439 |
| Texas | Pecos | 95 | TX_WestTexas_2018_D19 | 2018 | 24 | 2.35 | -102.8184, 31.2363 |
| Arkansas | Ouachita | 85 | AR_Ouachita_FEMA_R6_Lidar_2016_D17 | 2016 | 16 | 1.19 | -93.0892, 33.4073 |
