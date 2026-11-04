# Common framework (inherited by every process)

**Date:** 2026-11-04
**Status:** plan only. Nothing here has been run.
**Authority:** `docs/plans/protocol_gates_and_metrics.md` wins on any conflict. This file adds the shared machinery so each process framework does not repeat it.

## 1. How the frameworks are tiered
Depth follows value and readiness.
- **Tier A (exhaustive).** Processes that can run soon or that decide the program. P1, P2, 3.0, 3.1, 3.3, 4.1, 4.5, 4.6, 4.7, 5.1, 5.6, 6.3, 7.5.
- **Tier B (full).** Processes with a clear design but a later start. 3.2, 3.4, 3.5, 4.4, 4.8, 4.9, 5.2, 5.4, 6.5, 7.2, 7.3.
- **Tier C (scoped).** Deferred processes. Each lists the gate that must pass before any build, the minimum feasibility step, and what a full framework would add. 3.6, 3.7, 3.8, 4.2, 4.3, 5.3, 5.5, 6.1, 6.2, 6.4, 6.6, 7.1, 7.4.

## 2. Anatomy of a framework
Every framework has these sections in this order.
1. Problem and objective, with hypotheses where a test exists.
2. Scope (in, out).
3. Definitions and estimand (unit, population, metric, K, matching rule).
4. Inputs and data inventory (held, downloadable, requested), with paths.
5. Prerequisites and decisions.
6. Procedure, in stages. Each stage lists the script, its inputs, outputs, parameters, algorithm and checks.
7. Statistical analysis plan.
8. Quality control and leakage checks.
9. Gates. Success, failure, inconclusive, and the action for each.
10. Deliverables with full paths.
11. Failure modes and mitigations.
12. Resources.
13. Handoff checklist and open questions.
14. Documentation updates.

## 3. Environment and reproducibility
- Python only. Use plain `python`. `python -I` breaks here because the project packages live in user site. Pin the real interpreter and package versions in `requirements_lock.txt` at the repo root, produced once with `python -m pip freeze`. Record the interpreter path and version in every run.
- Paths come from `path_for` in `notebooks/wellsight_v2/_common.py`. Never spell a data path in a script.
- CRS is EPSG:6346 (NAD83(2011) UTM 17N) for Pennsylvania lidar. Assert the CRS of every raster and vector on read. Elevations are NAVD88.
- Seeds. One master seed per experiment written in the preregistration. Child seeds are `master + 1000 * fold + arm`. Never share one generator across folds, which caused the inner-split drift.
- Every run writes to `data/<area>/results/<section>/<run_id>/`. `run_id` is `YYYYMMDD_<short_name>_<hash7>` with the hash of the config JSON.
- Every run folder holds `_PROVENANCE.json` (inputs with SHA-256, checkpoints with SHA-256, split file hash, commit, interpreter, package list hash, command line, start and end time, seeds) and `_RUN.md` (what was run and why, in five lines).
- Provenance helper. One shared function `write_provenance(run_dir, inputs, outputs, params)` in `notebooks/wellsight_v2/_provenance.py` (new). Every script in the frameworks calls it.
- Inference and training run on the GTX 1070 Ti (8 GB). Use mixed precision as the existing trainers do. Measure epoch time on one fold before planning a retrain. The backlog notes epoch time was under-reported by 1.8 times.

## 4. Standard statistical machinery
**Candidates and matching (feature level)**
- Probability raster to candidates. Threshold at the lowest cutoff in the sweep (0.10), polygonise connected blobs, drop blobs under 4 m², score each blob by its mean probability. Same code as the operating-point sweep. Find it with `grep -rn "operating_point" notebooks/wellsight_v2/s5_eval/`.
- Matching to annotated floors. Greedy by IoU, threshold 0.3, one candidate to one truth feature. A second blob inside an already-matched feature is a duplicate, not a new detection.
- **Recall at K.** Rank all candidates in the scored footprint by score. Keep the top K per km² of scored eligible area. Recall is matched truth features over all truth features in that footprint. Ties are broken by larger area, then by blob id. K is 40 per km² (user, 2026-11-04). Report 30 as a sensitivity only.
- **Scored footprint.** Complete blocks, including blocks with no features. Never only blocks where the model found something.

**Intervals**
- Unit of resampling is the block (375 m on 9t, the target block elsewhere). Resample blocks with replacement, B = 2000, percentile 95% interval. Recompute pooled counts on each resample.
- Difference between two areas. Resample each area independently, subtract, take percentiles.
- Paired arms on the same blocks. Use the same resampled blocks for both arms.
- If a target has fewer than 15 blocks, also report a permutation interval and say the bootstrap is unreliable.
- Proportions with small n (field sites, newly documented wells). Clopper-Pearson exact for one group, Newcombe for a difference.
- **Projected width.** Before spending annotation time, resample n_target blocks from the 9t out-of-fold blocks, B = 2000, and take the median interval width. If it exceeds twice the margin, change the design before labelling.

**Calibration** (reported separately from ranking). Brier score, log loss, and expected calibration error with 10 equal-mass bins. Platt scaling is monotonic and cannot change recall at fixed K.

**Sample size for a proportion.** n = 1.96 squared times 0.25 over d squared, per estimate, under simple random sampling. 43 gives plus or minus 15 points, 96 gives 10, 24 gives 20. Inflate by a design effect for clustering (default 1.5 until measured).

**Decision function.** For a difference with interval [lo, hi] and margin Δ.
- Non-inferiority. Success if lo > −Δ. Failure if hi < −Δ. Else inconclusive.
- Superiority. Success if lo > 0. Failure if hi < the smallest useful gain. Else inconclusive.
- Inconclusive is reported as inconclusive. It is never described as no effect.

**Multiplicity.** One primary estimand per experiment. Everything else is labelled exploratory. Radii, thresholds and cutoffs other than the preregistered one are sensitivity analyses.

**Effective sample.** Blocks, pads, sites or counties. Detections, seeds, site-seasons, repeated visits and extra bootstrap draws are not independent.

## 5. Quality control checks every process must pass
1. Row counts asserted at every join. State the expected and observed counts.
2. CRS and extent asserted. No raster read without a transform check.
3. No NaN block ids in any fold or split list.
4. No duplicate ids. No candidate counted twice.
5. **Leakage tests.** (a) No training window intersects any held-out or audit block geometry. (b) Normalisation statistics are fitted on training windows only. (c) No audit block appears in any training, calibration, mining or selection list. (d) A second run with the same config gives identical outputs.
6. Hash match for every input and checkpoint against the provenance file.
7. A sanity render for every new raster or vector product. Check position against hillshade for two known features.
8. Every number in a document comes from a saved file. No typed numbers.

## 6. Documentation updates after every process
- `docs/iterations/<name>.md`. Goal, inputs and provenance, parameters, results, interpretation, reproduce command.
- `docs/analysis_log.md`. Entry at the top.
- `docs/iterations/BACKLOG.md`. Add deferred ideas. Remove finished ones.
- `docs/iterations/LEADERBOARD.md`. Any model result.
- `literature/CITATIONS.md`. Any literature-based decision, in the same change.
- `docs/plans/EXPANSION_MASTER_PLAN.md`. Update the status of the process.
- Replace nothing silently. If a result overturns a plan, add a Review revisions entry to the plan.

## 7. Conventions
- Names follow `<section>_<what>_<meaning>_<area>`, about 45 characters or fewer. Scripts start with an underscore.
- State the full path of every new file.
- Any file of 100 MB or more gets a `.gitignore` rule in the same change. After any step that writes large outputs run
  `find . -type f -size +100M -not -path './.git/*' | while read f; do [ -z "$(git check-ignore "$f")" ] && echo "LEAKING: $f"; done`
  and fix until empty.
- Colourblind-safe figures. Blue `#1F5FA8`, orange `#D97706`, grey `#8E959B`. No red and green with different meanings. Run the dataviz validator over all pairs and write the worst pair in a comment beside the palette.
- Never write "WellSight" in audience-facing material.
- Never overwrite `output_wells.csv` or the DEP export.
- Downloaded files are untrusted. Own folder per source, no script from a download is ever run, read with a reader script from a different folder.
- Commit and push after each major change. Stage selectively. About 160 unrelated modified files exist.
- Voice in documents. Short declaratives. No em-dashes. No prose colons or semicolons. They/them.

## 8. Negative and inconclusive results
- Write them up with the same detail as a success.
- Do not retune on the test area. Do not change the primary metric after seeing results. Changes after scoring go in an Amendments section with the date and the reason.
- A failed implementation is not evidence that the mechanism cannot work. Say which it is.

## 9. Evidence labels
Every table and sentence carries one of (a) drawn feature, (b) historical, (c) steel, (d) confirmed well. Never merge levels. Say exploratory or confirmatory.

## 10. Handoff checklist for the executing assistant
Before starting a process confirm
- the framework file and its dependencies are read
- every input path exists and its hash is recorded
- every user decision it needs is on file (see the master plan section 6)
- the preregistration is committed, when the process scores anything
- the run folder name and seed are chosen

Stop and report, do not improvise, when
- a gate fails
- an input is missing or its hash differs
- a leakage check fails
- a result contradicts the framework's own assumptions
- the process needs a user-only step (outreach, labelling, a field visit, a manual download)

Prompt skeleton for the executor.
> Execute `docs/plans/frameworks/<file>.md`. Read `fw_00_common.md` and `docs/plans/protocol_gates_and_metrics.md` first. Do the stages in order. Write every output to the paths listed. Do not spawn agents. Do not retune after scoring. Stop at the first failed gate and write what happened. Commit with selective staging after each stage.

## 11. Resource accounting template
| Item | Estimate | Measured | Notes |
|---|---|---|---|
| Inventory and setup hours | | | |
| Annotation hours (people) | | | |
| Machine runtime hours (GPU) | | | |
| Disk (GB, on C: or F:) | | | |
| Calendar dependencies | | | |

C: has about 108 GB free. F: has about 3.0 TB free. Heavy products go on F:.

## 12. Risk register template
| Risk | Likelihood | Effect | Mitigation | Owner |
|---|---|---|---|---|

## Revision 2 (third review, 2026-11-04)
- One decision threshold in the statistic's units serves both success and failure. The band between is inconclusive. Margins come from the burden tradeoff, never from variance or fold spread.
- Block bootstrap suits block-sampled maps. A weighted field sample or a design with few independent clusters needs inference matched to its design.
- Lidar catalogue totals are discovery estimates. Verify union coverage from tile geometries before a total becomes a budget.
- QC addition. Any query helper must separate successful-empty, failed and incomplete results, and must paginate and compare the returned total with the count retrieved.
