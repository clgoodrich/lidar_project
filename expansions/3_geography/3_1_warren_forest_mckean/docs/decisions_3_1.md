# 3.1 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review fix pass (F02 F03 F08 F11 G-03 G-06 G-07 P1-03, minors). Made by the review-fix agent, change freely.
  - Scoring is the 3.0 scorer. `_geo_xfer_lib` keeps `candidates_from_prob`, `match_iou` and `score_area` as thin wrappers. Matching is in score order. The old `test_match_iou` locked in IoU order and now asserts the score-order result.
  - Blocks are credited by centroid (the 3.0 rule that made the 9t reference), not by representative point. One rule keeps 3.1 and the reference comparable. A seam centroid goes to the lower block id.
  - Extraction (F03). One shared window over all scored blocks. The halo doubles while any above-cutoff cell touches an inner window side. The result equals the whole-raster oracle.
  - The reference is the 3.0 tables, not the 3.3 S1 blocks CSV. The reference rule is per fold, as stamped in the tables.
  - S7a writes an inference record with checkpoint lineage and `provisional_cv5`. S7b refuses to run without it.
  - A historical or provisional checkpoint on either side makes every decision "descriptive". The would-be decision is kept as `decision_if_confirmatory`.
  - Low-density blocks (G-07) enter the role draw. Main strata are drawn first in the old order, so main roles do not move. Low-density blocks never enter the primary statistic.
  - Warren roles were redrawn from the stored measures. Main roles and recheck blocks are identical. 14 low-density test blocks and 5 low-density audit blocks were added.
  - `il_cumberland` is added under `areas` (assumed, not fetched) so the 3.3 gate commands resolve.
- 2026-11-05. Proposal cutoff is the frozen archival rule (0.35 on 9t), not the 0.10 in fw_00 section 4. At 0.10 fold 0 recall before any budget is 0.553, against 0.922 at the archival cutoff. Made by the build agent, change freely.
- 2026-11-05. Heavy rasters go to `data/processed/<area>/05/` in this expansion, not `data/<area>/derived/05/`, until the lead adds a `.gitignore` rule there. Made by the build agent, change freely.
- 2026-11-05. Small tables go to `results/tables/<area>/` in this expansion, not `data/<area>/results/transfer/`. Made by the build agent, change freely.
- 2026-11-05. The 9t reference is the 3.3 S1 rebuild of the CV5 out-of-fold recall (provisional, original sampler). Swap to the P1 isolated table when it exists. Made by the build agent, change freely.
- 2026-11-05. Matching is greedy one-to-one by IoU as fw_00 says. The CV5 code matches greedy by score. Made by the build agent, change freely.
- 2026-11-05. K is round(40 x km²) as in `ek.recall_at_k`. The archival sweep floors it per fold. Made by the build agent, change freely.
- 2026-11-05. A hit is credited to the block that holds the truth feature. Made by the build agent, change freely.
- 2026-11-05. Adaptation is one contiguous strip from a seeded side. It is dropped when the strip is under 7 km². Made by the build agent, change freely.
- 2026-11-05. `--provisional-buffer` uses 192 m (pad patch support). It is not a derived buffer. Made by the build agent, change freely.
- 2026-11-05. Density rule is the 9t block 5th percentile (1.91 ground points per m²). Blocks under it form a low-density stratum. Made by the build agent, change freely.
- 2026-11-05. Model policy is the mean probability of the five fold checkpoints. Made by the build agent, change freely.
- 2026-11-05. Rasters in another CRS are warped to EPSG:6346 on read with an alert. Warren 1 m slope is EPSG:26917. Made by the build agent, change freely.
- 2026-11-05. roughness_11 is the builder roughness formula with an 11-cell window at 0.5 m. It matches the 9t band exactly. Made by the build agent, change freely.
- 2026-11-05. The committed preregistration is expected at `docs/prereg_xfer_<area>.md` in this expansion. The scorer refuses to run without it. Made by the build agent, change freely.

## Needs user decision

- Low-density stratum. Its 5 audit blocks are now in `xfer_audit_blocks_warren_v1.csv`. Decide whether low-density audit blocks belong in the sealed audit set.
- Reference rule. The 3.0 tables are ranked per fold, as the archival sweep did. The target is ranked once over all test blocks. Confirm this pairing in the preregistration.
- No multiplicity correction is applied across arms (Warren, McKean, Forest) and secondaries. Decide whether any secondary is gated.
