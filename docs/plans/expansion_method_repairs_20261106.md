# Method correctness: repairs and remaining evidence

This is a repair addendum to `expansion_code_review_20261106.md`, whose line citations describe the pre-repair snapshot at HEAD `6aed32b30d77cb22814fd54b274c829afc808791`. The working-tree repairs do **not** establish that all methods are accurate or that scientific claims are validated. No production models were retrained and no scientific result artifacts were regenerated.

## Implemented corrections

| Review finding | Change | Verification / limits |
|---|---|---|
| F01 | SSL corpus exclusion geometries are transformed into each stack's CRS, cached by CRS instead of assuming Pennsylvania coordinates. | Real GeoPackage/raster test places the same exclusion in EPSG:6346 and imagery in EPSG:3857; all overlapping chips must be rejected. Rotated stacks now fail explicitly. |
| F12 | SSL normalization uses masked reads, removes nonfinite values, preserves valid zeros, and rejects channels with no valid observations. Admission checks every channel; undersized windows are not admitted. | Independent fixture `[0, 2, -9999, NaN]` has mean 1 and SD 1. Nodata in channel 2 rejects a chip. Index output is delayed until statistics succeed. |
| F14 | Nonfinite or reversed interval bounds yield inconclusive. Invalid margins raise errors. | Both gate types, NaN, infinity, reversed bounds, negative margins, and exact-threshold equality are tested. |
| F06 | Corrected isolated pit trainer's path to the P2 audit guard. | Real frozen CSV/sidecar test admits disjoint lists and rejects audit overlap and an insufficient buffer; this does not establish actual training isolation on unavailable production inputs. |
| F04, partial | Single-cluster field summaries cannot pass the precision gate. They return logical bounds [0,1] and explicitly state that cluster variance is unidentified. Invalid inclusion probabilities and missing cluster IDs fail. | Regression uses 100 confirmed observations from one lease. Multi-cluster weighting, stratification, approximate Kish intervals, and era comparisons still require design-specific correction. |
| F05, partial | SSL label subsets consume P1's task-specific `pit` folds through its hash-checking reader, mapping `inner_val` and `held_out` explicitly. | Producer-schema fixture and tampered-content rejection. Benchmark/audit and field/density consumers remain unresolved. |
| F11, partial | Transfer void masks must match probability raster CRS, shape, and affine transform exactly. | A half-pixel shift fails before scoring. This is a guard, not automatic resampling; broader metric-unit/compound-CRS contracts remain unresolved. |

Eight new regression tests cover these counterexamples. Existing tests are additional compatibility evidence, not independent scientific validation.

## Better methods and when they help

1. **One versioned scoring implementation and policy manifest.** Consolidate regional and reference extraction, task-specific cutoffs, matching, area budgets, numeric tie ordering and undefined outcomes. Refuse comparative gates when checkpoint/preprocessing/channel order/calibration/deployment policies differ. This recommendation follows directly from F02/F07/F08/F09/F10; changing models before making evaluation comparable would obscure the source of any apparent gain.
2. **Spatially buffered, nested validation over full supports.** Buffered validation excludes nearby training observations; the blockCV documentation explicitly defines metre-based separation and recommends considering spatial autocorrelation. For this image pipeline, extend that reasoning to complete windows and augmentation support, with fitting/tuning confined to training and inner validation. Point buffers alone do not prove window isolation. [blockCV documentation](https://search.r-project.org/CRAN/refmans/blockCV/html/cv_buffer.html).
3. **Design-based survey inference.** Use the declared strata, primary sampling units, inclusion probabilities and finite-population information when applicable. A single non-certainty PSU cannot supply the usual variance estimate; automatic adjustments require additional assumptions. The current single-cluster guard prevents one false success but does not substitute for a validated survey estimator. [Survey package author's explanation](https://r-survey.r-forge.r-project.org/survey/exmample-lonely.html).
4. **Explicit raster validity masks.** Read band masks along with values; preserve the distinction between zero, nodata and NaN. Rasterio documents that explicit masks can override nodata metadata. For upstream artifacts, record the mask authority and retain mask sidecars through export/import. [Rasterio masks documentation](https://rasterio.readthedocs.io/en/stable/topics/masks.html).
5. **Seam-consistent candidate extraction and prediction-only deduplication.** Reconcile connected components across tile boundaries before computing area/score and assigning blocks. A fixed halo cannot guarantee preservation of objects larger than that halo. Deployment deduplication must not consult truth annotations. These recommendations follow from the reproduced F03/F15 counterexamples.
6. **Paired method comparisons at the same physical budget.** Compare model/context/modalities on the same eligible footprint, independent evaluation units, held-out truths and declared K. Preserve sampled-unit multiplicity and paired draws. A monotonic calibration transform alone cannot improve ranking at fixed K absent ties or another policy change. New architectures are candidates to test, not established improvements.

## Remaining repair order and readiness

The open findings in the original review remain open unless explicitly resolved above. Priority: shared spatial/policy contracts; regional scoring and footprint denominators; seam handling; baseline compatibility; all producer/consumer contracts; field sampling inference and per-well outcomes; unknown-terrain visibility; deployment deduplication. Do not use affected outputs for scientific success claims until their specific regression tests and actual artifact round trips pass.

Execution readiness is limited to tested synthetic fixtures. Integration is incomplete. Leakage controls have improved but require a full exposure ledger and actual training-window audit. Scientific evidence still requires independent complete labels, defensible sampling, acquisition/observability checks and a genuinely prospective evaluation; historically exposed 9t is not an untouched test set. No evidence in this pass establishes that one model family is universally superior.

## Reproduction record

Environment: Windows, Python 3.13.5 at `C:\Python313\python.exe`; package inventory is in `tmp/expansion_review_20261106/environment.json`.

Run `C:\Python313\python.exe tmp/expansion_review_20261106/validate_repairs.py`. It executes each of the 38 expansion test files in a fresh interpreter and records every exact command, return code and output in `tmp/expansion_review_20261106/repair_tests.json` and `repair_tests.log`. The first sandboxed targeted pytest attempt failed while creating temporary directories; the authorized rerun uses normal pytest temporary directories. The initial targeted pretraining run passed 6 tests; shared/field tests passed 9. The added manifest regression is included in the complete suite.

Complete-suite result: **245 tests passed across 38 files**, zero failed files. After adding the final actual audit-reader regression, the P1 file was rerun: **10 passed in 14.93 seconds**, giving 246 distinct passing tests in the final working tree across these runs. Exact follow-up command: `C:\Python313\python.exe -m pytest -q expansions/0_prerequisites/p1_splits_manifests/src/test_p1.py -p no:cacheprovider`. `git diff --check` passes. Existing warnings, including curve-fit covariance and all-NaN slices, remain recorded in the suite log and are not scientific validation.

Not run: full training, production imagery processing, field acquisition, benchmark release export with real frozen prerequisites, or prospective accuracy validation. Required real inputs and compatible isolated checkpoints were not supplied by this repair pass. These omissions prevent a universal accuracy assurance.
