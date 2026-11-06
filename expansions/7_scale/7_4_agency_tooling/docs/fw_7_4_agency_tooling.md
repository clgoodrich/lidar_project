# Framework 7.4. Agency tooling (command-line tool on an agency's own lidar)

**Tier A by instruction (user, 2026-11-05, stop deferring).** Written to full depth so it can be modified later. Nothing here has been run or built.
**Evidence level.** (a) drawn feature. The tool outputs are candidates, not wells. No (b), (c) or (d) claim.
**Depends on.** P1 (isolated trainers and split files), P2 (audit set), 3.0 scorer, 3.1 (Warren transfer), a frozen reference pipeline.
**Blocks.** Operational use. The trust statement (section 8) is conditional on 3.0 and 3.1 results.

## 1. Problem and objective
An agency has a folder of its own lidar. It needs candidate pit and pad locations, scores, and a clear statement of how far to believe them, without installing our environment.

**Question 1 (usability).** Can a person who did not write the code run the tool on a sample tile from the instructions alone and get the documented outputs?
**Question 2 (validity checks).** Does the tool refuse or warn on every unsupported input class in a fixed test set, and never return a quiet low score for bad input?
**Question 3 (reproducibility).** Does the same input give byte-identical candidates on two runs and on a second machine?

## 2. Scope
In. Command-line tool, input validity checks, candidate scoring, provenance and model-hash stamping, optional local calibration, install and packaging, trust statement, test plan, documentation for a non-author.
Out. A graphical interface. A web service. Training on agency data. Any claim that a candidate is a well. Operational deployment and support contracts.

## 3. Definitions
- **Candidate.** A polygon from the probability raster at the frozen cutoff, scored by mean probability (as 3.0 and fw_00_common section 4).
- **Refuse.** The tool exits with a non-zero code and writes a report. No candidates are produced.
- **Warn.** The tool runs, writes candidates, and stamps the warning on the run and on each affected tile. The warning travels with the output.
- **Frozen reference pipeline.** One model or ensemble, one preprocessing recipe at 0.5 m, one cutoff, one proposal extractor, hashed.
- **Local calibration.** A monotonic mapping from score to agency-labelled precision, fitted on 50 to 100 agency labels. A trial size, not a reliability guarantee.
- **Run folder.** `<out>/<run_id>/` with `run_id` equal to `YYYYMMDD_<short_name>_<hash7>`.

## 4. Inputs
| Input | Path | State |
|---|---|---|
| Frozen models | `data/9t/models/pit/unet_cv5/`, `data/9t/models/pad/unet_cv5_iso/` (final choice from 3.0 and P1) | held, final model to be frozen |
| Derivative builder | `notebooks/wellsight_v2/s1_build/_build_derivatives.py` | held |
| Inference scripts | `notebooks/wellsight_v2/s4_infer/_predict_on_tile.py`, `_postfilter_tile_candidates.py` | held |
| PDAL helper pattern | `notebooks/wellsight_v2/_common.py` (`PDAL_EXE`, CLI via subprocess) | held |
| Provenance helper | `notebooks/wellsight_v2/_provenance.py` | proposed (fw_00_common section 3) |
| Environment lock | `requirements_lock.txt` | proposed |
| Transfer evidence | 3.0 and 3.1 result files | future |
| 9t test tile and a held-out tile | `data/9t/`, a P2 audit block or the 3.1 Warren window | held and future |

## 5. Assumed data
Every item is assumed to exist. Each carries VERIFY. Nothing below is confirmed.

| Item | Assumption | VERIFY |
|---|---|---|
| Agency lidar | A folder of LAS or LAZ tiles (LAS 1.2 to 1.4), ASPRS classes present, a CRS in the header or a stated EPSG, QL2 or denser. | Run the validity checks on a sample. Record failures per tile. |
| Ground classification | Class 2 is populated by the vendor. | Measure class 2 share and ground points per m² per tile. Do not infer from file size. |
| Named agency user | A named person and a decision (for example a candidate list for site visits). | User confirms. Record the name and decision in the handoff. |
| Agency labels | Optional. 50 to 100 drawn or field-checked locations for calibration. | Count them. Check they are independent of any lidar-visible annotation by the agency. |
| Target machine | Windows or Linux, Python 3.11 or newer, an optional NVIDIA GPU, PDAL 2.x on the path. | Run `wells_cli check-env` (section 6). |
| Pretrained weights | The frozen checkpoints can be redistributed to the agency. | Confirm licence and size. Check the `.gitignore` rule for any file of 100 MB or more. |
| Transfer evidence | 3.0 and 3.1 will have run before release. | Check that their results files exist and match the model hash. If not, the trust statement says "not yet evaluated outside 9t". |

If a VERIFY fails, stop and report.

## 6. Interface specification (no code)
**Command.** `wells_cli` with subcommands `check-env`, `validate`, `run`, `calibrate`, `report`, `version`. Proposed file `tools/wells_cli.py`, with a thin package `wells_cli/` for the logic.

**Inputs.**
- `run --lidar <folder> --out <folder>` required.
- `--crs <EPSG>` override, used only when the header CRS is missing, never to override a present CRS.
- `--aoi <vector file>` optional, in any CRS, reprojected and logged.
- `--model <pit|pad|both>` default both.
- `--cutoff <float>` default the frozen value. Changing it is recorded and flagged.
- `--k-per-km2 <int>` optional review budget, default 40, caps the output list.
- `--res 0.5` fixed. A different value is refused.
- `--device <cpu|cuda>` default auto.
- `--strict` turns every warning into a refusal.
- `--calibration <file>` optional, from `calibrate`.
- `--seed <int>` for any stochastic step. Default fixed.
- `--workers <int>`. `--resume` continues an interrupted run from the per-tile cache.

**Outputs (in `<out>/<run_id>/`).**
- `candidates.gpkg` with layers `pit` and `pad`.
- `candidates.csv` with the same rows.
- `validity_report.csv` and `validity_report.json`, one row per tile.
- `coverage.gpkg` showing scored, warned and refused tiles.
- `_PROVENANCE.json` and `_RUN.md`.
- `probability/` rasters only with `--keep-rasters`.

**Candidate schema.** `cand_id` (stable hash of run, class, rounded centroid), `class` (pit or pad), `score` (raw probability), `score_cal` (calibrated, empty if no calibration), `area_m2`, `centroid_x`, `centroid_y` (in the output CRS), `tile_id`, `rank_in_run`, `rank_per_km2`, `validity_flag` (ok, warn, and reason codes), `model_id`, `model_sha256`, `method` (text, "unet_cv5 frozen policy"), `evidence_level` (always "a"), `label` (always "candidate"), `dist_nearest_known_m` (only when `--known-wells` is given, see below), `run_id`.
- Optional `--known-wells <file>` adds the distance to the nearest known well for context. The file is read-only and its hash is recorded.
- The tool never writes the words "well found" or "confirmed". The label is candidate.

**CRS handling.** Read the CRS from each header. Refuse if absent and no `--crs`. Refuse if tiles disagree and no `--crs` can unify them. Accept any projected CRS in metres or US feet, and convert units explicitly. Reject geographic CRS. Output in the input CRS by default, with `--out-crs` to reproject. Every raster and vector asserts its CRS on read. Vertical datum is recorded when present.

**Exit codes.** 0 ok. 2 refused on validity. 3 environment problem. 4 internal error. 5 interrupted (resume possible).

## 7. Input-validity checks (refuse or warn)
Thresholds are proposed starting values. They are fixed from 9t and the held-out area before release. Each is documented with its reason. A threshold is an eligibility rule, not a quality grade.
| Check | Measure | Refuse | Warn |
|---|---|---|---|
| CRS | Header present, projected, known units | Missing with no `--crs`, geographic, tiles disagree | Units in feet (converted), vertical datum missing |
| Ground density | Class 2 points per m² per tile, measured | Below the floor set from 3.1 and the density sensitivity | Between the floor and the 9t-like value |
| Ground classification | Class 2 share of all points | Zero ground points | Share far from the 9t distribution |
| Return structure | Return number and class fields present | Fields missing | Single-return only |
| Void fraction | Share of 0.5 m cells with no ground return | Above the ceiling set from 3.1 | Between 9t value (45.2%) and the ceiling |
| Canopy | Canopy height and cover from first returns | None. Always a warn | Different from 9t range (deciduous forest) |
| Tile size and coverage | Extent, gaps, overlap, edge buffer | Unreadable tile | Gaps, overlaps, tile smaller than the model window plus margin |
| Point format | LAS version, point format, scale and offset | Corrupt header | Old format, odd scale |
| Vintage and sensor | GPS time range, scan angle | None | Scan angles beyond the 9t range, leaf-off versus leaf-on unknown |
| Terrain | Slope and relief distribution | None | Outside the 9t range (3.3 evidence) |
| Resolution | Native density versus 0.5 m grid | None | Grid finer than the data supports |

Rules. Unsupported input is reported as unsupported in the validity report and never hidden as a low score. A warn travels with each candidate in `validity_flag`. A refused tile produces no candidates and appears in `coverage.gpkg`.

## 8. Trust statement (shipped with every run)
Text in `report` output and in `docs/agency/trust_statement.md` (proposed). It says only what the evidence supports.
- The candidates are drawn-feature predictions (level (a)). A candidate is not a well. On 9t, 27 of 424 annotated pits (6.4%) have a catalogued well within 25 m (`docs/iterations/LEADERBOARD.md`). Expect most candidates not to be wells.
- Reference performance is measured on 9t only. It is a historical diagnostic, not a new baseline (protocol section 2).
- **Transfer evidence.** The statement carries a transfer table. Each row names an area, its recall at 40 per km² with interval, its target density and its input class. The rows come from 3.0 and 3.1. An area that is not in the table has no evidence.
- Conditional wording. If 3.1 passed, the text states the tested conditions and says results on other terrain, density or vintage are untested. If 3.1 failed or was inconclusive, the text says "not shown to transfer". If neither ran, "evaluated on 9t only".
- Score meaning. Raw scores rank candidates. They are not probabilities of a well and not calibrated across areas. With `--calibration`, `score_cal` estimates precision against the agency's own labels, with an interval, on the stated sample. 50 to 100 labels is a trial.
- Missed features. Recall is below 100% at any K. Absence of a candidate is not absence of a well. Wells with no surface expression stay invisible.
- Warned and refused tiles are listed, and they are not covered.
The numbers come from saved files. None are typed.

## 9. Provenance and model-hash stamping
- Every run writes `_PROVENANCE.json` through `write_provenance` (fw_00_common section 3). Fields. Input file list with SHA-256 (or size and mtime plus a sampled hash for folders over a set size, stated), checkpoint SHA-256 for every model, config JSON hash, split-file hash that produced the model, code commit, tool version, interpreter and package list hash, PDAL version, command line, start and end time, seeds, validity summary.
- Each candidate row carries `model_id`, `model_sha256`, `run_id`.
- The tool refuses to run if a checkpoint hash does not match the manifest `models/MANIFEST.json` (proposed). The manifest is signed by the commit hash and lists the training split hash.
- Calibration files carry the model hash and are refused for a different model.

## 10. Install without our environment
- Pure Python package with pinned requirements. A `requirements_lock.txt` made once with `python -m pip freeze` (fw_00_common). Document torch CPU and CUDA wheel choices.
- PDAL is called by the CLI binary through `subprocess.run` with a pipeline JSON written to a temp file, using the `run_pipeline()` pattern in CLAUDE.md. The PDAL Python bindings are never imported and never listed as a requirement.
- `check-env` verifies the interpreter, package versions, PDAL binary and version, GPU presence, free disk, and a write test. It prints exactly what is missing.
- Offline install bundle (wheelhouse) for agencies without internet. A container image (proposed) with the same lock.
- No path literals. The package resolves its own paths from `--out` and a config file.
- Checkpoints ship in a release archive with SHA-256 sums, never in git history. Any file of 100 MB or more gets a `.gitignore` rule in the same change.

## 11. Test plan
**T0. Environment test.** Fresh machine or clean virtual environment from the lock. `check-env` passes.
**T1. Validity tests.** A fixture set of small LAZ files, each built to trigger one check (no CRS, geographic CRS, tiles with different CRS, zero ground, low density, high void, single return, truncated file, mixed units). The tool must refuse or warn as the table states. Zero silent passes allowed.
**T2. 9t sample tile.** Run on one 9t tile. Compare candidates to the saved 3.0 reference run. Expect identical IDs, scores to numerical tolerance, same row counts.
**T3. Held-out area.** Run on a tile from a P2 audit block or the 3.1 Warren window that the model never saw. Check candidates, validity flags and runtime. Compare to the 3.1 result for the same window.
**T4. Reproducibility.** Same input twice gives identical candidate files and provenance (apart from times). A second machine or container gives the same candidates.
**T5. Resume and failure.** Kill a run. `--resume` gives the same output as an uninterrupted run.
**T6. Non-author run.** A person who did not write the code runs the sample tile from the instructions alone. Record time, questions asked and failures. Acceptance is the run completes with the documented outputs.
**T7. Calibration.** With 50 to 100 held-out labels, check the monotonic mapping preserves ranking at fixed K and report the interval.
**T8. Schema.** Validate every output against the written schema and CRS assertion.

## 12. Statistical analysis plan
- Q1 and Q2 are acceptance tests, not statistical estimates. Counts and rates are reported with exact intervals.
- T3 compares recall and density against 3.1 with the block bootstrap from fw_00_common section 4. It is a consistency check, not a new claim.
- Calibration (T7). Brier score, log loss and expected calibration error with equal-mass bins, intervals by resampling agency labels. A calibrated score cannot change recall at fixed K.

## 13. Quality control
- Row counts asserted between tiles, probability rasters and candidates.
- CRS asserted at every read and write.
- No NaN tile ids, no duplicate candidate ids.
- Leakage. The shipped model was trained with splits that exclude the T3 area. Check the split file hash against the manifest.
- Hash match of every checkpoint against the provenance file.
- Sanity render of two known features on T2.
- Every number in a document comes from a saved file.

## 14. Gates (protocol form)
| Outcome | Rule | Action |
|---|---|---|
| Release success | T0, T1 (zero silent passes), T2, T4, T5, T8 pass and T6 passes with a non-author | Release with the trust statement |
| Release failure | Any silent pass in T1, a hash mismatch, or a non-author cannot finish the sample tile | Do not release. Fix and re-run the failed test |
| T3 transfer consistency | Held-out recall lower bound above minus Δ from 3.1 (same Δ, same source) | State "tested on" in the trust statement |
| T3 failure | Upper bound below minus Δ | Trust statement says "not shown to transfer". Do not hide it |
| Inconclusive | Intervals straddle | State "not shown to transfer or to fail" |
Δ is the tolerable missed-feature burden from the 3.1 preregistration. It is never fold spread. Tool release is an engineering gate. It does not depend on scientific success, but the trust statement does.

## 15. Deliverables
- `C:\Users\colto\Documents\GitHub\lidar_project\tools\wells_cli.py` and package `tools\wells_cli\` (proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\requirements_lock.txt`
- `C:\Users\colto\Documents\GitHub\lidar_project\models\MANIFEST.json` (proposed, checkpoints stay outside git)
- `C:\Users\colto\Documents\GitHub\lidar_project\tests\agency\` fixtures and tests (proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\agency\README.md`, `trust_statement.md`, `input_contract.md`, `schema.md` (proposed)
- `C:\Users\colto\Documents\GitHub\lidar_project\data\9t\results\agency\` test runs
- `C:\Users\colto\Documents\GitHub\lidar_project\docs\iterations\agency_tool_acceptance.md`
- Packaging. A source archive, a wheelhouse, a container image, and a release archive of checkpoints with SHA-256 sums.

## 16. Failure modes
| Risk | Mitigation |
|---|---|
| Scientific input contract not yet stable | Freeze after 3.0 and 3.1. Version the contract. Refuse unknown versions |
| Agency reads a high score as a well | Candidate label, trust statement, 6.4% context line |
| Bad input hidden as low score | Refuse and warn rules, T1 with zero silent passes |
| Environment drift | Lock file, `check-env`, container |
| PDAL version differences | Record the version. Test against the pinned version |
| Model leakage into the test tile | Split-file hash and audit-block exclusion |
| Calibration over-read | State sample size and interval. Trial only |
| Licence or size of checkpoints | Release archive, hash sums, no git history |

## 17. Resources
About 30 hours for the tool and tests after the gate, plus 8 hours for documentation and the non-author trial (their time, not ours). Compute is inference on the GTX 1070 Ti or CPU. Measure runtime per tile in T2 and T3 before quoting an agency timeline. Disk for the release archive and wheelhouse several GB on F:.

## 18. Handoff and open questions
- Named agency user and decision. Final frozen model. Refuse and warn thresholds (set from 3.1). Δ. Redistribution rights for checkpoints. Container or wheelhouse as the primary path.
- Stop and report if a gate fails, a hash differs, or a leakage check fails.

## 19. Documentation updates
`agency_tool_acceptance.md`, `docs/agency/*`, `requirements_lock.txt`, `analysis_log.md`, `BACKLOG.md`, `LEADERBOARD.md` (if a calibrated score is reported), `literature/CITATIONS.md` (calibration method), master plan, `docs/RUNBOOK.md` (pointer to the tool).
