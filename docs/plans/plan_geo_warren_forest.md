# 3.1 Warren and Forest counties

**Problem.** The 9t model was trained on one tile in Venango County. It is unknown whether it ranks well in neighbouring Warren and Forest counties, which have different lidar programs.

**Why it matters.** It is the nearest and cheapest test of whether the model generalises. A pass justifies Phase B. A fail shows what to fix.

**Evidence level produced.** (a) feature detection. A separate analysis covers record association (b to d).

**Inputs.** Seven Warren LAZ files are on disk (paths and dates to be listed). Forest lidar readiness is **unverified**. DEP export for wells. Frozen checkpoints.

**Architecture.**
1. Preregistration at `docs/iterations/transfer_warren_prereg.md` (draft exists). Fill the brackets and commit before scoring.
2. `_warren_inventory.py` lists tiles, CRS, point counts, and measured ground density per tile into `data/warren/results/transfer/warren_tile_inventory.csv`.
3. Choose adaptation, test and audit blocks. Write them to `data/warren/results/transfer/warren_blocks.gpkg` with a role column.
4. Run `_transfer_infer.py` and `_transfer_score.py` from plan 3.0.
5. Annotation package for the test blocks. Follow `docs/iterations/confuser_codebook.md` classes. Two reviewers, blinded to score.
6. Separate association report using plan 5.6.

**Method outline.** Complete blocks chosen before scores. Recall at fixed K with block bootstrap. Margin against 9t recall set in the preregistration.

**Acceptance test.** Preregistration committed before any scoring. Output includes the interval for the difference against 9t and a pass, fail or inconclusive label.

**Risks and unknowns.** Ground density may be lower than 9t. Forest County may lack suitable lidar. Annotation needs reviewers. Labelling time is not in the earlier 25-hour estimate.

**Depends on.** 3.0, P1, P2.

**Executor notes.** Do not look at probability maps before the preregistration is committed.
