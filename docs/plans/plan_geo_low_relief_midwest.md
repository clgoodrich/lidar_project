# 3.3 Illinois and Michigan (low relief)

**Problem.** The model learned pits in steep, forested terrain. In flat farmland a depression has a different background. It is unknown how the model behaves there.

**Why it matters.** Many orphaned wells sit in low-relief areas. A model that fails there has limited reach.

**Evidence level produced.** (a). A synthetic test adds a controlled check on terrain sensitivity.

**Inputs.** County lidar and well records for one Illinois and one Michigan county (**unverified**). Frozen checkpoints. Real 9t pit examples for the edit test.

**Architecture.**
1. Real-area test. `_transfer_infer.py` and `_transfer_score.py` from plan 3.0 on one flat county per state.
2. Synthetic edit test. `notebooks/wellsight_v2/s5_eval/_terrain_edit_test.py` inserts a pit shape into a DEM, recomputes every derivative channel from the edited DEM, and rescores. Writes `data/9t/results/terrain/terrain_edit_paired_scores.csv`.
3. Sham edits. Same script inserts shapes that are not pits (smooth bumps, ramps) as controls.
4. Real low-slope pits. Select annotated 9t pits on low slopes as a natural comparison.

**Method outline.** Paired score and rank changes per inserted pit. Seam checks. Never paste derivative layers, always regenerate them from the edited DEM.

**Acceptance test.** Sham edits score near the background. Pit edits are reported as paired change with intervals. No half-score gate.

**Risks and unknowns.** Pasted terrain may create seams or out-of-distribution inputs.

**Depends on.** 3.0.

**Executor notes.** Report paired differences, not a pass threshold on raw score.

## Review revisions (2026-11-04, override the text above)
Source. `docs/plans/review_response_20261104.md`. Rules. `docs/plans/protocol_gates_and_metrics.md`. Acquisitions. `docs/plans/download_manifest.md`.

**Decision.** Redesign.

- Step 4 first. Stratify existing 9t out-of-fold recall by local slope and relief. It uses no new data.
- Insert edits only into real low-relief 9t backgrounds. A plane plus noise lacks 0.5 m interpolation texture and is out of distribution.
- Claim slope-context sensitivity, not Midwest performance. Report paired score and rank changes.

**Downloads and requests.** D15 gated on step 4.
