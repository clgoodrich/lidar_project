# Framework 7.3. Terrain-feature benchmark

**Tier B.**
**Evidence level.** (a). Call it a terrain-feature benchmark, never a confirmed-well benchmark.
**Depends on.** P1, P2, licences.

## 1. Problem and objective
No public benchmark exists for lidar detection of well-related terrain features. A released one would let others compare methods and make the work checkable.

**Objective.** A release package with tiles, labels, splits, baselines, a datasheet and a licence statement, reproducible from a fresh checkout.

## 2. Scope
In. Export, datasheet, baselines, licences, hosting plan.
Out. Hosting decisions and publication venue.

## 3. Definitions
- **Release unit.** 0.5 m feature stack or point cloud tiles plus polygon labels per block.
- **Partial labels.** Blocks fully annotated and blocks not. State clearly.
- **Baselines.** The isolated U-Net (P1) with the recall-at-K protocol (3.0).

## 4. Inputs
Annotations and splits, features, licences of lidar (public domain 3DEP) and annotation terms, DEP data terms (not part of labels).

## 5. Prerequisites and decisions
P1 and P2 done. Who owns the annotations and under what licence. Whether to include off-tile annotations (209 and 345 rows).

## 6. Procedure
1. **Datasheet** `docs/iterations/benchmark_card.md`. Label provenance (who, when, guide), exclusions, spatial buffers, uncertainty (annotator agreement), licences, intended use, limits, known biases.
2. **Export** `s5_eval/_benchmark_export.py` (new). Write tiles, labels, split files, hashes to `data/benchmark/` (F:, `.gitignore`).
3. **Baseline scripts** that reproduce reported numbers from the export alone.
4. **Reproduction test.** A fresh clone runs the baseline on the export and reproduces recall at K = 40 within rounding.
5. **Licence and ethics check.** No coordinates of private wells that raise safety concerns without a review.

## 7. Statistical analysis plan
Report baseline recall at K with block bootstrap intervals and the fold spread.

## 8. Quality control
Hashes. Split buffers. No 100 MB file in git.

## 9. Gates
Reproduction passes on a clean checkout. Licence statement complete.

## 10. Deliverables
Card, export script, `C:\Users\colto\Documents\GitHub\lidar_project\data\benchmark\`.

## 11. Failure modes
Licence issues. Partial labels misread as full. Baseline leakage (fix with P1).

## 12. Resources
20 hours after P1 and P2.

## 13. Handoff
Annotation licence decision.

## 14. Documentation updates
Card, `analysis_log.md`, master plan.
