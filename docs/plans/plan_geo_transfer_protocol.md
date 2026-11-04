# 3.0 Transfer protocol

**Problem.** Every geographic item needs the same test of whether the 9t model still works in a new place. Without one shared protocol each region gets a different, hard-to-compare test.

**Why it matters.** It is the base of items 3.1 to 3.8. Done once and well, each later region costs less.

**Evidence level produced.** (a) only. It tests feature detection against drawn polygons.

**Inputs.** Frozen 9t checkpoints in `data/9t/models/pit/unet_cv5` and the pad equivalent. Prereg template. Saved 9t splits from P1.

**Architecture.**
1. `docs/iterations/transfer_protocol.md` states the target population, candidate unit, scored footprint, K, matching rule (IoU 0.3 for features), spatial buffers, uncertainty method, and separate adaptation and test sets.
2. `notebooks/wellsight_v2/s4_infer/_transfer_infer.py` takes a region name and a lidar tile list. It builds derivatives with the same code as 9t, runs frozen weights, and writes probability rasters to `data/<area>/results/transfer/`.
3. `notebooks/wellsight_v2/s5_eval/_transfer_score.py` takes the preregistration file path. It reads the footprint, labels and K, and writes recall at K, calibration, block-bootstrap intervals and a JSON summary.
4. `data/<area>/results/transfer/_PROVENANCE.json` holds hashes, versions and commit.

**Method outline.** Freeze weights, preprocessing, proposal extraction and calibration. Pick complete evaluation blocks before viewing scores. Report detection and record association separately. Report calibration separately from ranking.

**Acceptance test.** Rerunning the protocol on 9t held-out blocks reproduces the saved 9t cross-validation recall within rounding. A second person can run it from the prereg file alone.

**Risks and unknowns.** Derivative generation for a new area may differ in ground density. Measure it per block first.

**Depends on.** P1, P2.

**Executor notes.** Do not retune anything on the test area. Use the existing `path_for` helper for data paths.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Bounded pilot.

- K is candidates per km² of scored area. Section 2 of the protocol sets metric, reference raster and density reporting. K policy is a user decision.
- Step 1 is deterministic. Reproduce the 9t operating-point sweep from `pit_prob_floor_outoffold_9t_05.tif` exactly before any new area.
- Use the isolated trainer family. The original sampler can read held-out windows.
- Preprocessing stays at 0.5 m. Fold-local normalisation.
- The acceptance test is a readiness gate. The scientific gate is in protocol section 5.

**Downloads and requests.** None
