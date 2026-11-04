# 7.4 Agency tooling

**Problem.** An agency needs to run the model on its own lidar without our environment and know how far to trust the output.

**Why it matters.** It is the route from research to use.

**Evidence level produced.** (a) with calibrated confidence.

**Inputs.** The frozen models, the inference scripts, a pinned environment.

**Architecture.**
1. `tools/wells_cli.py` takes a lidar folder and writes candidates with scores and provenance.
2. `requirements_lock.txt` and an environment note. Pin the actual interpreter and package versions. Do not depend on plain `python` and a user-site install.
3. Input contract check. Report unsupported input (CRS, density, tile size) separately from low-confidence output.
4. Local calibration step using 50 to 100 labels from the agency. That is a trial size, not a reliability guarantee.
5. Provenance file with every run.

**Method outline.** Quality checks before inference. Calibration validated locally.

**Acceptance test.** A person who did not write the code runs it on a sample tile from the instructions alone.

**Risks and unknowns.** Operational deployment comes later.

**Depends on.** 3.0, P1.

**Executor notes.** Do not hide unsupported inputs behind low scores.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Freeze a reference pipeline first. Pin the interpreter and package versions in a lock file. Separate unsupported input from low-confidence output.

**Downloads and requests.** None.
