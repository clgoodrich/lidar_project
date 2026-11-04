# 7.3 Benchmark dataset

**Problem.** No public benchmark exists for lidar detection of well-related terrain features. A released one would let others compare methods.

**Why it matters.** It makes the work citable and checkable.

**Evidence level produced.** (a). Call it a terrain-feature benchmark, never a confirmed-well benchmark.

**Inputs.** Annotated features, saved splits, licences of the underlying data.

**Architecture.**
1. `docs/iterations/benchmark_card.md` records label provenance, exclusions, spatial buffers, uncertainty, licences and intended use.
2. `_benchmark_export.py` writes tiles, labels and split files to `data/benchmark/` with hashes.
3. Baseline scripts that reproduce the reported numbers from the export.
4. Check that no 100 MB file enters git.

**Method outline.** Include label provenance and uncertainty. Do not wait for every well identity to be established.

**Acceptance test.** A fresh checkout reproduces baseline numbers from the export alone.

**Risks and unknowns.** Licences of source lidar and records.

**Depends on.** P1, P2.

**Executor notes.** Use the word "feature" throughout.
