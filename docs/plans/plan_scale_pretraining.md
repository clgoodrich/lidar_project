# 7.1 Self-supervised pretraining

**Problem.** Labels are scarce. Pretraining a network on unlabelled terrain may help with few labels.

**Why it matters.** It could lift performance and cut labelling needs in new regions.

**Evidence level produced.** (a).

**Inputs.** Unlabelled lidar derivatives from several areas. Compute is a single 8 GB GPU. Runtime must be benchmarked first.

**Architecture.**
1. `_pretrain_benchmark.py` measures time per epoch for a small model on the available GPU. Writes `docs/iterations/pretrain_runtime.md`.
2. `_pretrain_ssl.py` trains with a masked-patch or contrastive objective on unlabelled terrain, excluding the test area.
3. Fine-tune and compare against matched random-init runs. Same architecture, budget and seeds.
4. Label-efficiency curve at several label counts, repeated across seeds.

**Method outline.** Keep test-area pretraining excluded unless explicitly evaluating transductive learning. Small compute does not rule out a useful result.

**Acceptance test.** A label-efficiency curve with seed variation on a held-out area.

**Risks and unknowns.** Eight GB memory limits model size.

**Depends on.** P1.

**Executor notes.** Match budgets exactly between arms.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Defer.

- Name the comparison. Benefit at fixed annotation budget, at fixed total compute, or after counting pretraining cost. These are three questions. Baseline integrity (P1) comes first.

**Downloads and requests.** None.
