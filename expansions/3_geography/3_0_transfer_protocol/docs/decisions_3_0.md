# 3.0 decisions

Newest first. One line per decision, with the date and who made it.

- 2026-11-06. Review fix pass (F02 F08 F11 G-02 G-03 G-05 G-06, minors). Made by the review-fix agent, change freely.
  - The scorer takes cutoff, minimum area, IoU and match order from `ek.policy_for(task)`. The dict and its hash are stamped into every score JSON, the reference tables and the decision report. `CUTOFF` (0.10) is the sensitivity only.
  - 3.1 and 3.2 now call this scorer in memory (`extract`, `score_tables`). There is one matcher.
  - Dedupe never ran before. Unmatched candidates were NaN, not None, so `dedupe_mask` saw no unmatched candidate. It now drops second pieces. On 9t pits it removes one candidate and adds one hit (per-fold recall 457 to 458 of 503).
  - A centroid exactly on a block seam now goes to the lower block id. Before, it fell in no block and was lost.
  - Edge rule (G-05). An edge block touches the data boundary. Interior nodata counts toward the void fraction. The cap is the preregistered `void_cap`, else `void_cap_default` 0.5.
  - Grid contract (F11). Projected CRS in metres with an EPSG:6346 horizontal part, all six affine terms, no rotation, same shape. Feet and degrees raise. A compound CRS passes.
  - Reference footprint (G-02). The 29 pit-free and 15 pad-free 9t blocks were in no fold of the split and no trainer patch reached them. The trainers centre patches on features inside train blocks and clip them to train-block bounds. So every fold model is out of sample there. The tables now fill them from the full-tile fold rasters, one fold model per block by round robin. The pit fill is quantised to DN / 254 so the 115 old blocks stay bit-identical.
  - Old to new pooled recall at K 40 (tables, global rank / per-fold rank). Pit 0.917 / 0.909 to 0.946 / 0.938. Pad 0.815 / 0.809 to 0.855 / 0.848. The new code on the old 115 and 129 blocks gives pit 0.917 / 0.911 and pad 0.815 / 0.809, so the change is the footprint. Fold-mean fill gives the same global recall, pit 0.946 and pad 0.855.
  - The truth-only footprint made the 9t reference pessimistic. The added blocks bring more budget area than false candidates.
  - Tables schema. Old block keys stay. New keys `policy` (policy_for dict) and `meta` (footprint, fill rule, per-fold rule, dedupe, checkpoint lineage, recall). Each block also carries `fold`. Read them with `read_ref_tables`.
  - Compatibility (F08, G-06). The preregistration declares `scoring.cutoff`, `scoring.iou`, `scoring.dedupe`, `scoring.k` and `checkpoint`. The harness and the decision report compare them with the run and the reference through `ek.assert_same_policy`. A reference with no policy stamp or a truth-only footprint is refused. An archival reference, a historical CV5 checkpoint or a provisional one gives verdict "descriptive". Today both 9t references are provisional, so no transfer verdict can be "supported".
  - The prereg example now says cutoff 0.35 (it said 0.10). The fill tool refuses a declared policy that differs from `policy_for` unless `policy_override_reason` is given.
  - `resolve` compares numbers as numbers, so 40 equals 40.0.
  - The sign-flip interval returns "not identifiable" with fewer than 2 blocks with truth.
  - No multiplicity correction is applied anywhere. fw_00 names one primary estimand. Everything else is exploratory. This is recorded, not changed.
- 2026-11-05. Scripts live in `src/` of this folder. The framework's `notebooks/wellsight_v2/s4_infer` and `s5_eval` paths are superseded. Made by the build agent, change freely.
- 2026-11-05. The harness proposal cutoff is the sweep's, per task (pit 0.35, pad 0.525, the median of 0.50 to 0.55). The protocol asks for the sweep's proposal extraction. fw_00's 0.10 merges blobs and drops 9t pit recall at K 40 from 0.909 to 0.575. 0.10 stays a sensitivity. Made by the build agent, change freely.
- 2026-11-05. Matching pairs are taken in score order, as in the code that made the 9t reference. fw_00's "greedy by IoU" is the `--order iou` sensitivity. Made by the build agent, change freely.
- 2026-11-05. The dedupe rule reads truth, so it is a scoring rule, not a deployment rule. `--dedupe none` turns it off. Made by the build agent, change freely.
- 2026-11-05. Hits are credited to the block of the truth feature. Candidates and truth join blocks by centroid. Made by the build agent, change freely.
- 2026-11-05. The 9t reference uses `k_rule per_group` (budget floored per fold area, as the sweep). Targets use one global K. Made by the build agent, change freely.
- 2026-11-05. An edge block is any block with a cell outside valid raster data. Edge blocks are dropped by default. Made by the build agent, change freely.
- 2026-11-05. Under 15 blocks the extra interval is a sign-flip interval on block residuals about the pooled ratio. Made by the build agent, change freely.
- 2026-11-05. Output files carry the area in their names (`transfer_score_<area>.json`) to follow the filename rule. Made by the build agent, change freely.
- 2026-11-05. The preregistration embeds a `json prereg` block. The harness reads it and refuses any flag that disagrees. Made by the build agent, change freely.
- 2026-11-05. The projected width resamples the 115 archival pit blocks without fold strata. Made by the build agent, change freely.
- 2026-11-05. Pad truth is layer `pad`, which `read_layer` maps to `plat`. Made by the build agent, change freely.
- 2026-11-05. The void raster is 1 where the 0.5 m ground density is zero. Made by the build agent, change freely.

## Needs user decision

- Void cap default. Interior nodata now counts toward the void fraction. The default cap is 0.5, the value in the preregistration example. Each preregistration should state its own `void_cap`.
- Fill rule for feature-free 9t blocks. Round robin (one fold model per block, like a held-out block) is the default. Fold mean is the sensitivity and gives the same pit recall (0.946 global).
- Small-sample interval. fw_00 asks for a permutation interval under 15 blocks. A residual sign-flip interval collapses with one block that has truth. The code now says "not identifiable" there. A valid small-sample interval is not designed yet.
- Multiplicity. There is no correction for several arms, K values or sensitivities. Decide whether any secondary is ever gated.
- Prereg template `docs/iterations/transfer_prereg_template.md` sits outside 3.0. It should list `scoring.cutoff`, `scoring.iou`, `scoring.dedupe`, `scoring.order`, `scoring.void_cap` and the `checkpoint` block (family, lineage, sha256). The fill tool already checks them.
