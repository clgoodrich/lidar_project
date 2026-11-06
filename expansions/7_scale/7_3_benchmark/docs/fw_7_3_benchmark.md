# Framework 7.3. Terrain-feature benchmark release

**Tier A (full depth, 2026-11-05).** The user withdrew the deferral. The plan assumes the licences and hosting in section 5 permit release. Each assumption is tagged VERIFY.
**Evidence level.** (a). It is a terrain-feature benchmark. It is never a confirmed-well benchmark.
**Depends on.** P1 (saved splits, buffer). P2 (audit sets, guard). 6.3 for label uncertainty. 7.1 and 7.2 may add baselines.
**Blocks.** Public claims that others can reproduce.

## 1. Problem and objective
No public benchmark exists for lidar detection of well-related terrain features. A release would let others compare methods and check ours. A careless release does harm. Labels are one annotator's reading of terrain. A test set that was tuned on is worthless. Source licences may limit release.

**Objective.** A versioned release with tiles, labels, splits, an evaluation script, baselines, a datasheet and leaderboard rules. A fresh checkout reproduces every baseline number from the release alone.

**Hypotheses (tested on the benchmark itself).**
- H1. The benchmark separates two models known to differ (plain U-Net and `unetpp_r34_imagenet`, which beat plain U-Net in every fold, `LEADERBOARD.md`).
- H2. It does not separate two seeds of one model.
- H3. Its test interval is narrow enough to decide a margin of the size we use elsewhere.

## 2. Scope
In. Pit floor and pad polygon tasks on 9t at 0.5 m. Train, validation and test splits. Data, labels, scorer, baselines, datasheet, rules.
Out. Road task in v1 (listed for v2). Wells, well identity and any association with DEP records as a task. Other states.

## 3. Definitions
- **Feature.** A drawn polygon for a pit floor, pit rim, or pad. Never "well".
- **Release.** A frozen versioned folder with a manifest of SHA-256 hashes. A change makes a new version.
- **Public splits.** Train and validation folds from P1 (`cv_splits_future_9t_v1.json`) plus a development test.
- **Hidden test.** The comparative audit blocks (P2 S1) and, later, the absolute audit area (P2 S4). Labels are withheld by the maintainers.
- **Track A.** Train only on the released training data. **Track B.** Any extra data allowed, declared. Extra unlabelled data is declared in both tracks.
- **Primary metric.** Recall of annotated features at K = 40 per km² of scored eligible area, with the matching, ties and footprint rules of `fw_00_common.md` section 4.
- **Label uncertainty.** Disagreement between the annotator and a second reviewer on a random subset, and the share of features with no catalogued context.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Annotations | `qgis/annotations/annotations_proj.gpkg` (`pit_inside`, `pit_full`, pad layers) | held |
| 9t derivatives and DEM | `data/9t/derived/` | held |
| Splits and buffer | `data/9t/results/splits/cv_splits_future_9t_v1.json`, `buffer_derivation_9t.json` | from P1 |
| Audit files | `data/9t/results/splits/audit_blocks_9t_v1.csv`, `data/warren/results/transfer/audit_blocks_warren_v1.csv` | from P2 |
| Exposure history | `docs/iterations/audit_set_history.md` | from P2 |
| Scorer | 3.0 scorer, `notebooks/wellsight_v2/s5_eval/` (candidate extraction with `grep -rn "operating_point"`) | held, proposed |
| Baseline models | `data/9t/models/pit/unet_cv5/`, `pad/unet_cv5/`, `pad/unet_cv5_iso/` (held). `pit/unet_iso_cv5/` (P1 isolated pit trainer, not built yet) | partly held |
| Uncertainty subset | 6.3 second-reviewer labels, `data/9t/results/confusers/` | from 6.3, proposed |
| Datasheet draft | `docs/iterations/benchmark_card.md` | proposed |

## 5. Assumed data
| # | Assumption | Tag | How to verify |
|---|---|---|---|
| 1 | Source lidar (PA 2019 D20 and related 3DEP projects) is public domain or open for redistribution of derived rasters and clipped point clouds | VERIFY | Read each project's metadata and the PASDA or USGS terms. Save the terms text with a date in `data/benchmark/terrain_v1/LICENCE_SOURCES.md`. Ask the data owner if unclear |
| 2 | The well record used for any context column (USGS 2026 well file, DEP export) allows redistribution of derived flags | VERIFY | Read the licence of each file. If unclear, release no well coordinates and no distances |
| 3 | The annotator permits release of labels under a stated licence (CC BY 4.0 proposed) | VERIFY | User confirms in writing. Record the date |
| 4 | A second reviewer labelled a random 10% of blocks, giving a label-uncertainty estimate | VERIFY | Count rows from 6.3 and P2. If missing, the datasheet says "uncertainty not measured" |
| 5 | A host exists for about 20 GB (proposed Zenodo or an institutional store) with a DOI | VERIFY | Check size limits and terms. Files at or above 100 MB are never committed to git |
| 6 | Maintainers can run the scorer on submitted rasters (a person, not a server) | VERIFY | Proposed process in section 7 S6 |
| 7 | Annotators did not see DEP well points while drawing (user, 2026-11-04). Other context seen is unrecorded | VERIFY | Ask the annotator and record the answer in the datasheet |
| 8 | Test blocks have never had model output shown to anyone (P2 rule) | VERIFY | `audit_set_history.md` exposure table |

If assumption 1 fails, release labels and scripts only, with a recipe to rebuild tiles from public sources. If 3 fails, nothing is released.

## 6. Prerequisites and decisions
P1 and P2 done. User decisions. Label licence. Whether the absolute audit area joins v1.1. Submission limit. Name of the release.

## 7. Procedure
**S0. Datasheet first.** Write `docs/iterations/benchmark_card.md` before any export. Sections follow the datasheet pattern.
- Motivation. Why the release exists and who funded it.
- Composition. Counts by split, task, class and block. Feature density per km². Share of annotated blocks with no features.
- Collection. Lidar projects, dates (publication date is not flight date), point density, CRS EPSG:6346, vertical datum NAVD88, builder versions.
- Label provenance. One annotator drew polygons in QGIS from derivative views. Layers, codebook, rules for partial features, known gaps. The labels are one person's interpretation of terrain. They are not ground truth for wells. On 9t, 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m (`LEADERBOARD.md`).
- Exclusions. Off-tile rows (209 of 712 pit rows and 345 of 995 pad rows have no block id and are excluded from split use). Blocks with partial annotation. Nodata chips.
- Spatial buffers. The derived buffer from P1 S4 around every test block. Buffer blocks are not in train or validation.
- Uncertainty. Second-reviewer agreement (percent and kappa) with intervals. An upper bound on recall from the second reviewer scored against the first.
- Uses. Intended use and out-of-scope use (section 8).
- Distribution, licences, maintenance, versioning, contact.

**S1. Export.** Script `notebooks/wellsight_v2/s7_analysis/_bench_export_9t.py` (proposed).
- Write `data/benchmark/terrain_v1/` with `tiles/` (derivative stacks as COG tiles of 256 m, with the DEM), `labels/` (GeoPackage per split), `splits/` (JSON copied from P1 and P2, test labels absent), `manifest.csv` (path, SHA-256, bytes), `LICENCE_SOURCES.md`, `README.md`.
- Test blocks ship with tiles and no labels. Buffer blocks ship with tiles and no labels, flagged.
- Assert CRS on every tile. Assert no label file contains a test block.

**S2. Scorer.** Script `notebooks/wellsight_v2/s5_eval/_bench_score_9t.py` (proposed, shipped in the release as `evaluate.py`). Input a probability raster per tile. Steps are candidate extraction at the task cutoff from `ek.policy_for` (pit 0.35, pad 0.525, 0.10 only as a sensitivity, amended 2026-11-06), polygonise, drop blobs under 4 m², greedy score-order IoU match at 0.3 within each block, rank, keep top K per km², recall, block-bootstrap interval, calibration. Deterministic. Same inputs give byte-identical output.

**S3. Baselines.** Scripts under `notebooks/wellsight_v2/s3_train/` reuse P1 trainers. Rows.
- Plain U-Net pit and pad (isolated, P1), three seeds.
- `unetpp_r34_imagenet` pit.
- Optional. 7.1 pretrained and 7.2 active models, labelled as such.
- Prediction rasters for dev blocks ship in the release so the scorer can be rerun without training.
- Output `data/benchmark/terrain_v1/baselines/baseline_scores.csv`.

**S4. Benchmark validity checks.** Script `_bench_validity_9t.py` (proposed).
- Known-difference control (H1). Paired block bootstrap of unetpp minus plain U-Net.
- Sham control (H2). Seed A minus seed B of the same model.
- Projected width (H3). Resample the test block count from 9t out-of-fold blocks, B = 2000, median interval width.
- Label ceiling. Second reviewer scored against first.

**S5. Fresh-checkout test.** Clone into an empty folder on a clean environment. Run `evaluate.py` on shipped dev predictions. Compare to `baseline_scores.csv`. The retrain path is documented but not required to match bitwise.

**S6. Leaderboard rules.** Write `data/benchmark/terrain_v1/RULES.md`.
- Submit a probability raster per test tile, float, 0.5 m, EPSG:6346, plus a one-page method note and the track.
- Candidates are extracted by the official scorer only. K is fixed at 40 per km².
- At most 3 submissions per team per 90 days. Each submission is scored once. Test labels are never returned, only aggregate scores.
- Report the difference from the plain U-Net baseline with a paired block-bootstrap interval. Ranks are shown only with intervals. Two entries whose difference interval spans 0 are listed as tied.
- Track B declares every extra dataset. Test tiles are never used for training, self-training or normalisation. Transductive use is declared and listed apart.
- Entries from the maintainers are marked.
- After v1 closes, the test labels may be released as v2 and a fresh hidden set made. A released test set is never reused as hidden.

**S7. Release.** Tag the release, deposit with the host, record the DOI. Run the large-file audit before any commit.

## 8. Statistical analysis plan
- Baseline numbers. Recall at K with block-bootstrap interval (B = 2000, percentile 95%). Fewer than 15 test blocks adds a permutation interval.
- Validity decisions. H1 is a superiority test with threshold 0 on the paired difference. H2 passes if the interval contains 0 and the point estimate is below half the H1 estimate. H3 passes if projected width is at most twice the margin used in the leaderboard rules.
- Margin for declaring a difference on the leaderboard. Set from the burden of one extra reviewer hour per km² (the K policy), not from baseline seed spread. User decision.
- Evidence levels. Every table is labelled (a). No table carries (b), (c) or (d), and no row mixes them. Well-context columns, if released, are level (b) and kept in a separate file.
- Label uncertainty is reported as a ceiling, not folded into the score.

**Intended use.** Compare terrain-feature detectors on pit and pad features in forested Appalachian lidar. Study label-efficiency and transfer methods.
**Out of scope.** Locating wells for entry or plugging. Regulatory or legal decisions. Counting wells or estimating density. Claims about any other state or lidar vintage. Safety decisions in the field. Any claim that a detected feature is a well.

## 9. Quality control and leakage checks
1. No test or buffer block label in any shipped file (scripted scan).
2. Hash of every released file equals `manifest.csv`.
3. Test blocks match `audit_blocks_9t_v1.csv` by id and by geometry.
4. No training window in the baselines reaches a test block plus buffer (guard).
5. Duplicate and near-duplicate check. No feature centroid within 5 m across splits.
6. Same scorer inputs give identical outputs on two runs.
7. CRS, units (metres) and nodata declared on every tile.
8. Every number in the datasheet comes from a saved file.
9. Large-file audit. Nothing at or above 100 MB enters git. `.gitignore` rule for `data/benchmark/` in the same change.

## 10. Gates
| Outcome | Rule | Action |
|---|---|---|
| Success | Fresh-checkout test reproduces dev baseline scores exactly. H1 lower bound above 0. H2 interval contains 0. H3 width at most twice the margin. Licences confirmed. Datasheet complete | Release v1 |
| Failure | Any test label found in the release, or reproduction fails, or licence blocks release | Do not release. Fix or restrict to scripts and recipe |
| Inconclusive | H1 interval spans 0, or H3 width too large | The benchmark cannot yet rank methods. Add test blocks or lower the claim to descriptive. Report |

## 11. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\benchmark_card.md`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s7_analysis\_bench_export_9t.py`, `_bench_validity_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\notebooks\wellsight_v2\s5_eval\_bench_score_9t.py`
- `C:\Users\colto\Documents\GitHub\lidar_project\data\benchmark\terrain_v1\` (tiles, labels, splits, manifest, `RULES.md`, `LICENCE_SOURCES.md`, `baselines\baseline_scores.csv`, `evaluate.py`)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\benchmark_validity_9t.md`

## 12. Failure modes
| Risk | Mitigation |
|---|---|
| Labels read as well locations | Word "feature" throughout. Out-of-scope statement on the first page of the release |
| One annotator's bias becomes the standard | Report second-reviewer ceiling. Invite relabelled versions as v2 |
| Test set tuned on by repeated submission | Submission cap. Aggregate scores only. Fresh hidden set after release of old |
| Test blocks seen informally | P2 rule. No figures of test blocks with model output |
| Licence blocks tiles | Release recipe and labels only |
| Single area, single sensor vintage | Say so. Do not generalise. Plan v2 with Warren |
| Partial annotation near block edges | Exclusions list. Complete blocks only in scoring |
| Sensitive location data | No well coordinates or distances unless the licence permits |

## 13. Resources
Datasheet and export 20 hours. Baselines reuse P1 models plus 3 seeds, GPU hours from the P1 S6 measurement. Validity checks 6 hours, no GPU. Release size about 20 GB (proposed, VERIFY) on F:.

## 14. Handoff and open questions
- Label licence and annotator consent.
- Host and DOI.
- Who runs submissions.
- Whether the absolute audit area joins v1.1.
- Leaderboard margin.

## 15. Documentation updates
`benchmark_card.md`, `benchmark_validity_9t.md`, `analysis_log.md`, `LEADERBOARD.md` (link only), `BACKLOG.md` (road task, v2), `literature/CITATIONS.md` (datasheet and benchmark practice sources), master plan.

## Review revision (2026-11-05)
Deferral withdrawn by the user. Written to full depth on assumed licences and hosting. Nothing here has been run.
Source. `docs/plans/protocol_gates_and_metrics.md` sections 3 and 12.
