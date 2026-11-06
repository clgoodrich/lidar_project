# 5.6 decisions

Newest first. One line per decision, with the date and who made it.

## Decisions

- 2026-11-06. Dedupe gap. User accepted the default 2.0 m ("take defaults"). Change freely.
- 2026-11-06. Held-out products are re-cut at the policy cutoffs by the new script src/_records_policy_recut_9t.py. It thresholds the existing held-out probability rasters. notebooks/ is not edited. User accepted the default pit 0.35 and pad 0.525 ("take defaults"). Change freely.

## Needs user decision

- The 29 zero-pit blocks have no out-of-fold pit prediction. The complete grid gives them records but no pit detections. Scoring them needs a choice of model and a check that no training patch reached them.

## Log

- 2026-11-06. Defaults pass by the review-fix agent. S0 now reads data/interim/records_pit_recut_policy_9t.gpkg and data/interim/records_pad_recut_policy_9t.gpkg. S0 refuses a product whose thr_used is not the policy cutoff. Change freely.
- 2026-11-06. The 0.50 pit product from 2026-08-12 is older than the CV5 fold rasters (2026-09-17) and the pit manifest (2026-09-04). Re-cutting today's rasters at 0.50 gives 658 pit blobs, not 688. Pads reproduce exactly (1005). So part of the pit change comes from the newer rasters, not from the cutoff.
- 2026-11-06. Rerun on 9t. Pit rows 677 to 768 (779 before dedupe, 11 merged). Pad rows 1005 to 996. Matched pits 481 to 486. Novel pits 196 to 282. Matched pads 604 to 607.
- 2026-11-06. Positive control (active, pad, 0 m) still passes. Normalised excess 0.373 [0.316, 0.410] to 0.363 [0.305, 0.395].
- 2026-11-06. Orphan and abandoned at pit 50 m 0.043 [-0.082, 0.171] to 0.015 [-0.108, 0.136]. At pad 0 m 0.054 [0.000, 0.109] to 0.060 [0.007, 0.111].
- 2026-11-06. Plugged at pit 50 m 0.039 [-0.023, 0.103] to 0.084 [0.012, 0.153]. At pad 0 m 0.171 [0.123, 0.216] to 0.168 [0.126, 0.211].
- 2026-11-06. New default run results/20261106_recassoc_23e82bc. Old-rule sensitivity results/20261106_recassoc_74b4c0c. The adjudication sheet was redrawn from the new default run.
- 2026-11-06. Review fix pass by the review-fix agent. Change freely.
- 2026-11-06. F15. The deployment dedupe read the truth flag dup_on_pit. It is refused now. The default is geometric. Blobs whose polygons lie within 2.0 m merge, and the highest score stays. Pit rows went from 685 to 677. All 481 truth-matched blobs stay. 11 undecided blobs merge. The truth flag and source stay as evaluation columns only.
- 2026-11-06. Gap counts on 9t. At 0.5 m 6 pairs touch. At 1 m 8. At 2 m 11. At 3 m 15. At 5 m 25. Above 2 m truth-matched pairs start to merge with each other.
- 2026-11-06. 5.6-01. det_id is a seeded random permutation of a prediction-only order (cx, cy, score, area). Pits run 1 to 677 with seed 20261106. Pads run 1000001 to 1001005 with seed 20261107. Spearman of det_id with score is 0.06 (matched pits) and 0.03 (undecided pits). It was -1.0. cand_id is dropped because it ranks score within a layer. link_id in proposals is also a seeded permutation. The adjudication sheet row order stays random.
- 2026-11-06. 5.6-02. The null is toroidal by default. A shift past one tile edge re-enters at the opposite edge. Every direction is accepted and no record is lost. The old reject rule accepted 0 of 300 plugged pit shifts. Its accepted directions spread by 0.34 to 0.80 in acceptance share across 45 degree sectors. The torus spread is 0.
- 2026-11-06. Footprint is the complete grid (144 blocks) for both modalities. truth_bearing and intersection are sensitivities.
- 2026-11-06. Hungarian is gated. A KD-tree finds pairs within the gate and each connected component is solved alone. It equals the dense gated solution.
- 2026-11-06. Cohorts use the config group orphan_abandoned. The old list also held Abandoned, which S1 did not use. No 9t record has that status, so counts did not change.
- 2026-11-06. The other-states runner refuses a CRS that is missing, geographic or not in metres.
- 2026-11-06. Outputs written by 5.6 code hold repo-relative paths. ek.write_provenance still writes absolute paths. That is in _shared.

- 2026-11-05. Dedupe rule is deployment. Matched rows stay. An unmatched blob inside a drawn pit is dropped. keep_all is the sensitivity. Made by the build agent, change freely.
- 2026-11-05. Assignment is global Hungarian across statuses with a 100 m gate. per_status gives labelled competing proposals. Made by the build agent, change freely.
- 2026-11-05. Footprints are per modality (115 pit blocks, 129 pad blocks). intersection is the alternative switch. Made by the build agent, change freely.
- 2026-11-05. The null rejects shifts losing more than 10% of records and redraws up to 20 times. report_retained keeps every shift and logs its retained count. Made by the build agent, change freely.
- 2026-11-05. Under the 10% rule plugged records at pit level get no accepted shift. The default run marks that cell unattainable. The retained-count run fills it as a sensitivity. Made by the build agent, change freely.
- 2026-11-05. Normalised excess is observed minus null mean, over one minus null mean. Its interval uses the null 2.5 and 97.5 percentiles. It is not PPV. Made by the build agent, change freely.
- 2026-11-05. The pad full output is the model_geometry layer of the 0.50 threshold products, matched to plat by greedy IoU 0.3. No raster rebuild. Made by the build agent, change freely.
- 2026-11-05. The annotated analysis uses pit_inside centroids and plat polygons. Made by the build agent, change freely.
- 2026-11-05. The adjudication sample is 60 pit links stratified by distance band (0, 10, 25, 50, 100 m). Slack moves to larger bands. Made by the build agent, change freely.
- 2026-11-05. Outputs stay in this folder, not data/9t/results/records/, under the build rule. Made by the build agent, change freely.
